"""The Supporters plugin: sponsors with packages, invoices and logos, and
fundraising goals with donations and pledges.

Runs with Hubra's fixtures once the plugin is in plugins/supporters of a
Hubra checkout (see README.md).
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from sqlalchemy import select

from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/app/supporters"
STAFF = [
    "supporters.sponsors.read",
    "supporters.sponsors.update",
    "supporters.goals.update",
    "supporters.bookings.manage",
    "supporters.invoices.manage",
]
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture
def club(client, app, db, seeded_db):
    """Kim runs sponsors and goals; Max is an ordinary member."""
    from hubra.core.models.finance import TransactionCategory

    set_modules(True, "supporters")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    kim = _make_role_and_member(db, tier, name="Kim", permission_keys=STAFF)
    max_ = _make_role_and_member(db, tier, name="Max")
    cat = TransactionCategory(name="Spenden")
    db.session.add(cat)
    db.session.commit()
    return {"kim": kim.id, "max": max_.id, "cat": cat.id}


def _slug(db):
    from hubra.core.models.tenant import Tenant

    tenant = Tenant(name="Open Club", slug="open-club", plan="starter", status="active")
    db.session.add(tenant)
    db.session.commit()
    return tenant.slug


# ── Sponsors ─────────────────────────────────────────────────────────────────


def test_sponsors_are_invoiced_once_a_year(client, db, club):
    from hubra.core.models.external_party import ExternalParty
    from hubra.core.models.finance import Invoice

    _login(client, "kim@test.ch")
    gold = client.post(
        f"{BASE}/packages",
        json={"name": "Gold", "amount": "2000", "benefits": "Logo auf dem Trikot"},
    ).get_json()
    a = client.post(
        f"{BASE}/sponsors",
        json={
            "name": "Garage Muster AG",
            "packageId": gold["id"],
            "email": "info@garage.ch",
            "website": "garage-muster.ch",
            "city": "Bern",
        },
    ).get_json()
    assert a["yearly"] == 2000.0 and a["website"] == "https://garage-muster.ch"
    b = client.post(
        f"{BASE}/sponsors", json={"name": "Bäckerei Brot", "amount": "300"}
    ).get_json()
    # Ended last year: not invoiced this year.
    last = date.today().year - 1
    client.post(
        f"{BASE}/sponsors",
        json={"name": "Alt AG", "amount": "100", "until": f"{last}-12-31"},
    )
    assert (
        client.post(
            f"{BASE}/sponsors", json={"name": "X", "website": "not a site"}
        ).status_code
        == 400
    )

    year = date.today().year
    res = client.post(
        f"{BASE}/sponsors/invoice", json={"year": year, "categoryId": club["cat"]}
    ).get_json()
    assert (
        sorted(res["invoiced"]) == sorted([a["id"], b["id"]])
        and len(res["skipped"]) == 1
    )
    invoices = db.session.scalars(
        select(Invoice).where(Invoice.purpose == "other")
    ).all()
    assert sorted(float(i.amount) for i in invoices) == [300.0, 2000.0]
    party = db.session.scalar(
        select(ExternalParty).where(ExternalParty.name == "Garage Muster AG")
    )
    assert party.email == "info@garage.ch" and party.address_city == "Bern"
    # Pressing again invoices nobody twice.
    again = client.post(f"{BASE}/sponsors/invoice", json={"year": year}).get_json()
    assert again["invoiced"] == []
    # A package in use stays.
    assert client.delete(f"{BASE}/packages/{gold['id']}").status_code == 409

    _login(client, "max@test.ch")
    assert client.get(f"{BASE}/sponsors").status_code == 403
    assert client.post(f"{BASE}/sponsors", json={"name": "Y"}).status_code == 403


def test_the_website_sees_shown_sponsors_with_logos(client, db, club):
    _login(client, "kim@test.ch")
    shown = client.post(
        f"{BASE}/sponsors",
        json={"name": "Garage Muster AG", "amount": "500", "showPublic": True},
    ).get_json()
    # Hidden unless the club shows it: a sponsor may be a private person.
    hidden = client.post(
        f"{BASE}/sponsors", json={"name": "Stiller Gönner", "amount": "50"}
    ).get_json()
    assert hidden["showPublic"] is False
    bad = client.put(
        f"{BASE}/sponsors/{shown['id']}/logo",
        data={"logo": (io.BytesIO(b"<html>"), "x.html", "text/html")},
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400
    ok = client.put(
        f"{BASE}/sponsors/{shown['id']}/logo",
        data={"logo": (io.BytesIO(PNG), "logo.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert ok.get_json()["hasLogo"] is True
    client.put(
        f"{BASE}/sponsors/{hidden['id']}/logo",
        data={"logo": (io.BytesIO(PNG), "logo.png", "image/png")},
        content_type="multipart/form-data",
    )
    slug = _slug(db)

    client.post("/api/v1/auth/logout")
    client.delete_cookie("access_token_cookie")
    page = client.get(f"{BASE}/public/{slug}")
    assert (
        page.status_code == 200 and page.headers["Access-Control-Allow-Origin"] == "*"
    )
    sponsors = page.get_json()["sponsors"]
    assert [s["name"] for s in sponsors] == ["Garage Muster AG"]
    assert client.get(f"{BASE}/public/{slug}/logo/{shown['id']}").data == PNG
    assert client.get(f"{BASE}/public/{slug}/logo/{hidden['id']}").status_code == 404
    assert client.get(f"{BASE}/public/no-such-club").status_code == 404


# ── Fundraising goals ────────────────────────────────────────────────────────


def test_a_goal_counts_donations_and_paid_pledges(client, db, club):
    from hubra.core.models.finance import Invoice, Transaction

    _login(client, "kim@test.ch")
    goal = client.post(
        f"{BASE}/goals",
        json={"title": "Neues Boot", "target": "12000", "categoryId": club["cat"]},
    ).get_json()
    gift = client.post(
        f"{BASE}/goals/{goal['id']}/donations",
        json={"amount": "2500", "name": "Stiftung Seeland", "method": "IBAN"},
    ).get_json()
    tx = db.session.get(Transaction, gift["transactionId"])
    assert (
        tx.type == "income"
        and float(tx.amount) == 2500
        and tx.category_id == club["cat"]
    )
    assert (
        client.post(
            f"{BASE}/goals/{goal['id']}/donations", json={"amount": "5"}
        ).status_code
        == 400
    )

    _login(client, "max@test.ch")
    assert (
        client.post(f"{BASE}/goals", json={"title": "x", "target": 1}).status_code
        == 403
    )
    pledge = client.post(
        f"{BASE}/goals/{goal['id']}/pledge", json={"amount": "100", "anonymous": True}
    ).get_json()
    assert pledge["pledge"] is True and pledge["counted"] is False
    view = client.get(f"{BASE}/goals/{goal['id']}").get_json()
    assert (
        view["raised"] == 2500.0 and view["pledged"] == 100.0 and view["percent"] == 20
    )
    # Max sees his own pledge; others don't see it until it is paid.
    assert len(view["mine"]) == 1

    # Max pays his invoice: the pledge counts, and stays anonymous to others.
    invoice = db.session.get(Invoice, pledge["invoiceId"])
    assert invoice.member_id == club["max"] and float(invoice.amount) == 100
    invoice.status = "Paid"
    db.session.commit()
    view = client.get(f"{BASE}/goals/{goal['id']}").get_json()
    assert view["raised"] == 2600.0 and view["donors"] == 2
    _login(client, "kim@test.ch")
    listed = client.get(f"{BASE}/goals/{goal['id']}").get_json()["donations"]
    assert {d["name"] for d in listed} == {
        "Test Max",
        "Stiftung Seeland",
    }  # the board sees who

    # A paid pledge stays; a goal with donations is closed, not deleted.
    assert client.delete(f"{BASE}/donations/{pledge['id']}").status_code == 409
    assert client.delete(f"{BASE}/goals/{goal['id']}").status_code == 409
    closed = client.post(f"{BASE}/goals/{goal['id']}/close", json={}).get_json()
    assert closed["open"] is False
    _login(client, "max@test.ch")
    assert (
        client.post(
            f"{BASE}/goals/{goal['id']}/pledge", json={"amount": "10"}
        ).status_code
        == 409
    )


def test_an_unpaid_pledge_can_be_withdrawn_with_its_invoice(client, db, club):
    from hubra.core.models.finance import Invoice

    _login(client, "kim@test.ch")
    goal = client.post(
        f"{BASE}/goals", json={"title": "Lager", "target": "1000"}
    ).get_json()
    _login(client, "max@test.ch")
    pledge = client.post(
        f"{BASE}/goals/{goal['id']}/pledge", json={"amount": "40"}
    ).get_json()
    _login(client, "kim@test.ch")
    assert client.delete(f"{BASE}/donations/{pledge['id']}").status_code == 204
    assert db.session.get(Invoice, pledge["invoiceId"]) is None
    assert client.delete(f"{BASE}/goals/{goal['id']}").status_code == 204


# ── Dashboard widgets ───────────────────────────────────────────────────────


def test_widgets(db, club):
    from datetime import timedelta
    from decimal import Decimal

    from hubra.core import contracts
    from hubra.core.models.member import Member
    from hubra_supporters.models import (
        SupportersDonation,
        SupportersGoal,
        SupportersPackage,
        SupportersSponsor,
    )

    today = date.today()
    goal = SupportersGoal(title="Neue Tore", target=Decimal("2000"))
    db.session.add_all([
        goal,
        SupportersGoal(title="Vorbei", target=Decimal("100"), ends_on=today - timedelta(days=1)),
    ])
    gold = SupportersPackage(name="Gold", amount=Decimal("1000"))
    db.session.add(gold)
    db.session.flush()
    db.session.add_all([
        SupportersDonation(goal_id=goal.id, member_id=club["max"], amount=Decimal("500"),
                           donated_on=today),
        SupportersSponsor(name="Bäckerei", package_id=gold.id),
        SupportersSponsor(name="Garage", amount=Decimal("250"), until=today + timedelta(days=30)),
        SupportersSponsor(name="Früher", amount=Decimal("999"), until=today - timedelta(days=1)),
    ])
    db.session.commit()

    max_ = db.session.get(Member, club["max"])
    out = contracts.widget_data("supporters.goals", {}, actor=max_)
    assert [i["label"] for i in out["items"]] == ["Neue Tore"]
    assert out["items"][0]["sub"] == "CHF 500 / CHF 2'000 · 25%"

    stat = contracts.widget_data("supporters.sponsors", {}, actor=contracts.SYSTEM)
    assert stat["value"] == 2 and stat["sub"].startswith("CHF 1'250 / ")

    offered = [o.contract.name for o in contracts.widgets(actor=max_)]
    assert "supporters.goals" in offered and "supporters.sponsors" not in offered


# ── Security ─────────────────────────────────────────────────────────────────


def test_a_reader_sees_no_contact_details(client, db, club, seeded_db):
    """supporters.sponsors.read comes with the "Ansehen" level every member
    gets: it shows what the club shows anyway, not who to call or the notes."""
    _make_role_and_member(
        db, seeded_db["tier"], name="Rea", permission_keys=["supporters.sponsors.read"]
    )
    _login(client, "kim@test.ch")
    client.post(
        f"{BASE}/sponsors",
        json={
            "name": "Garage Muster AG",
            "amount": "500",
            "contactName": "Hans Muster",
            "email": "hans@garage.ch",
            "phone": "079 000 00 00",
            "street": "Weg 1",
            "notes": "will mehr zahlen",
        },
    )
    full = client.get(f"{BASE}/sponsors").get_json()[0]
    assert full["email"] == "hans@garage.ch" and full["notes"]

    _login(client, "rea@test.ch")
    res = client.get(f"{BASE}/sponsors")
    assert res.status_code == 200
    row = res.get_json()[0]
    assert row["name"] == "Garage Muster AG" and row["yearly"] == 500.0
    for key in ("contactName", "email", "phone", "street", "postalCode", "city", "notes"):
        assert key not in row
    assert client.patch(f"{BASE}/sponsors/{row['id']}", json={"name": "Z"}).status_code == 403


def test_logo_content_and_website_are_checked(client, db, club):
    _login(client, "kim@test.ch")
    s = client.post(f"{BASE}/sponsors", json={"name": "A"}).get_json()
    # HTML sent as a PNG, or as an SVG.
    for blob, kind in ((b"<html><script>x</script>", "image/png"), (b"<html>", "image/svg+xml")):
        res = client.put(
            f"{BASE}/sponsors/{s['id']}/logo",
            data={"logo": (io.BytesIO(blob), "logo", kind)},
            content_type="multipart/form-data",
        )
        assert res.status_code == 400
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    res = client.put(
        f"{BASE}/sponsors/{s['id']}/logo",
        data={"logo": (io.BytesIO(svg), "logo.svg", "image/svg+xml")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    logo = client.get(f"{BASE}/sponsors/{s['id']}/logo")
    assert "sandbox" in logo.headers["Content-Security-Policy"]

    for bad in ('x.ch" onmouseover="alert(1)', "x.ch/<script>", "x.ch/\ttab"):
        res = client.patch(f"{BASE}/sponsors/{s['id']}", json={"website": bad})
        assert res.status_code == 400, bad
    ok = client.patch(f"{BASE}/sponsors/{s['id']}", json={"website": "x.ch/a?b=1&c=2"})
    assert ok.get_json()["website"] == "https://x.ch/a?b=1&c=2"


def test_members_cannot_run_goals_or_book_donations(client, db, club):
    _login(client, "kim@test.ch")
    goal = client.post(
        f"{BASE}/goals", json={"title": "Boot", "target": "1000", "categoryId": club["cat"]}
    ).get_json()
    d = client.post(
        f"{BASE}/goals/{goal['id']}/donations", json={"amount": "50", "name": "Anna"}
    ).get_json()

    _login(client, "max@test.ch")
    assert client.post(f"{BASE}/goals", json={"title": "X", "target": "1"}).status_code == 403
    assert client.patch(f"{BASE}/goals/{goal['id']}", json={"title": "X"}).status_code == 403
    assert client.post(f"{BASE}/goals/{goal['id']}/close", json={}).status_code == 403
    assert client.delete(f"{BASE}/goals/{goal['id']}").status_code == 403
    assert (
        client.post(f"{BASE}/goals/{goal['id']}/donations", json={"amount": "5", "name": "X"}).status_code
        == 403
    )
    assert client.delete(f"{BASE}/donations/{d['id']}").status_code == 403
    assert client.post(f"{BASE}/sponsors/invoice", json={}).status_code == 403
    # What a member sees of others' donations leaves out the books' links.
    seen = client.get(f"{BASE}/goals/{goal['id']}").get_json()["donations"][0]
    assert "transactionId" not in seen and "memberId" not in seen


def test_money_needs_a_finance_or_supporters_right(client, db, club, seeded_db):
    """Running goals and sponsors ("Bearbeiten") doesn't book income or send
    invoices; that takes a finance right or the plugin's own manage key."""
    tier = seeded_db["tier"]
    _make_role_and_member(
        db,
        tier,
        name="Sek",
        permission_keys=["supporters.goals.update", "supporters.sponsors.update"],
    )
    _make_role_and_member(
        db,
        tier,
        name="Fin",
        permission_keys=[
            "supporters.goals.update",
            "supporters.sponsors.update",
            "finance.transactions.create",
            "finance.invoices.create",
        ],
    )
    _login(client, "kim@test.ch")
    goal = client.post(
        f"{BASE}/goals", json={"title": "Boot", "target": "1000", "categoryId": club["cat"]}
    ).get_json()
    d = client.post(
        f"{BASE}/goals/{goal['id']}/donations", json={"amount": "50", "name": "Anna"}
    ).get_json()
    client.post(f"{BASE}/sponsors", json={"name": "A", "amount": "100"})

    _login(client, "sek@test.ch")
    can = client.get(f"{BASE}/options").get_json()["can"]
    assert can["goals"] and not can["book"] and not can["invoice"]
    assert (
        client.post(
            f"{BASE}/goals/{goal['id']}/donations", json={"amount": "5", "name": "X"}
        ).status_code
        == 403
    )
    assert client.delete(f"{BASE}/donations/{d['id']}").status_code == 403
    assert client.post(f"{BASE}/sponsors/invoice", json={}).status_code == 403

    _login(client, "fin@test.ch")
    assert (
        client.post(
            f"{BASE}/goals/{goal['id']}/donations", json={"amount": "5", "name": "X"}
        ).status_code
        == 201
    )
    assert client.post(f"{BASE}/sponsors/invoice", json={}).get_json()["invoiced"]


def test_members_see_donors_but_not_what_others_gave(client, db, club, seeded_db):
    _make_role_and_member(
        db,
        seeded_db["tier"],
        name="Rev",
        permission_keys=["supporters.donations.read_amounts"],
    )
    _login(client, "kim@test.ch")
    goal = client.post(
        f"{BASE}/goals", json={"title": "Boot", "target": "1000"}
    ).get_json()
    client.post(
        f"{BASE}/goals/{goal['id']}/donations", json={"amount": "50", "name": "Anna"}
    )
    _login(client, "max@test.ch")
    client.post(f"{BASE}/goals/{goal['id']}/pledge", json={"amount": "20"})
    seen = client.get(f"{BASE}/goals/{goal['id']}").get_json()
    anna = next(x for x in seen["donations"] if x["name"] == "Anna")
    assert "amount" not in anna
    own = next(x for x in seen["donations"] if x["name"] != "Anna")
    assert own["amount"] == 20.0
    assert seen["raised"] == 50.0

    _login(client, "rev@test.ch")
    seen = client.get(f"{BASE}/goals/{goal['id']}").get_json()
    assert all("amount" in x for x in seen["donations"])
