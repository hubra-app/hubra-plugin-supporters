"""Supporters API: /api/v1/app/supporters.

GET    /options                      what the caller may do, categories
GET    /packages                     sponsorship packages
POST   /packages                     {name, amount, benefits?}
PATCH  /packages/<id>
DELETE /packages/<id>
GET    /sponsors                     with package, yearly amount, invoiced year
POST   /sponsors                     {name, packageId?, amount?, since?, until?, ...}
PATCH  /sponsors/<id>
DELETE /sponsors/<id>
PUT    /sponsors/<id>/logo           multipart: logo (an image)
DELETE /sponsors/<id>/logo
GET    /sponsors/<id>/logo
POST   /sponsors/invoice             {year, sponsorIds?, categoryId?, dueDays?}
GET    /goals                        fundraising goals with what was raised
POST   /goals                        {title, target, description?, endsOn?, categoryId?, showPublic?}
GET    /goals/<id>                   with donations (names as the donors chose)
PATCH  /goals/<id>
DELETE /goals/<id>                   only without donations
POST   /goals/<id>/close             {reopen?}
POST   /goals/<id>/donations         treasurer: {amount, name?, memberId?, donatedOn?, anonymous?, message?, method?}
DELETE /donations/<id>               treasurer; a booked one only if not paid by invoice
POST   /goals/<id>/pledge            member: {amount, anonymous?, message?}: an invoice
GET    /public/<club>                sponsors and goals the club shows (no sign-in)
GET    /public/<club>/logo/<id>      a shown sponsor's logo (no sign-in)
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, g, jsonify, request, send_file, url_for
from sqlalchemy import func, select

from hubra.core import files as store
from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice, TransactionCategory
from hubra.core.models.member import Member
from hubra.core.permissions import permission_required, require_member
from hubra.core.utils import log_audit

from .body import (
    Invalid,
    _body,
    _bool,
    _can,
    _category_id,
    _date,
    _get,
    _int,
    _iso,
    _money,
    _names,
    _num,
    _text,
)
from .models import (
    SupportersDonation,
    SupportersGoal,
    SupportersPackage,
    SupportersSponsor,
)

supporters_bp = Blueprint("supporters_bp", __name__)

OWNER = "supporters"
SPONSORS_READ = "supporters.sponsors.read"
SPONSORS = "supporters.sponsors.update"
GOALS = "supporters.goals.update"
LOGO_TYPES = ("image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/gif")
METHODS = ("IBAN", "Cash", "Twint", "Card")


@supporters_bp.errorhandler(Invalid)
def _invalid(exc: Invalid):
    return api_error("VALIDATION_ERROR", exc.message, 400)


def _website(data) -> str | None:
    value = _text(data, "website", 300)
    if value and not value.startswith(("https://", "http://")):
        value = "https://" + value
    # It goes out on the public endpoint, where club websites put it in an
    # href: no spaces, quotes or angle brackets that could break out of one.
    if value and (
        "." not in value
        or any(c.isspace() or c in '"<>`\\' or ord(c) < 32 for c in value)
    ):
        raise Invalid("website is not an address")
    return value


# ── Output ───────────────────────────────────────────────────────────────────


def _package(p: SupportersPackage) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "amount": _num(p.amount),
        "benefits": p.benefits,
        "position": p.position,
    }


def _yearly(s: SupportersSponsor, packages: dict) -> Decimal | None:
    if s.amount is not None:
        return s.amount
    p = packages.get(s.package_id or 0)
    return p.amount if p else None


def _active(s: SupportersSponsor, today: date) -> bool:
    return (s.since is None or s.since <= today) and (
        s.until is None or s.until >= today
    )


# Contact and invoice details of a sponsor. Only those who look after the
# sponsors (supporters.sponsors.update) get them; supporters.sponsors.read
# comes with the "Ansehen" level every member has by default, so a reader
# sees what the club shows anyway (name, package, amount, website, logo).
CONTACT_FIELDS = (
    "contactName",
    "email",
    "phone",
    "street",
    "postalCode",
    "city",
    "notes",
    "lastInvoiceId",
)


def _sponsor(
    s: SupportersSponsor, packages: dict, today: date, full: bool = True
) -> dict:
    p = packages.get(s.package_id or 0)
    out = {
        "id": s.id,
        "name": s.name,
        "contactName": s.contact_name,
        "email": s.email,
        "phone": s.phone,
        "website": s.website,
        "street": s.street,
        "postalCode": s.postal_code,
        "city": s.city,
        "packageId": s.package_id,
        "packageName": p.name if p else None,
        "amount": _num(s.amount),
        "yearly": _num(_yearly(s, packages)),
        "since": _iso(s.since),
        "until": _iso(s.until),
        "active": _active(s, today),
        "showPublic": s.show_public,
        "hasLogo": bool(s.logo_key),
        "notes": s.notes,
        "lastInvoicedYear": s.last_invoiced_year,
        "lastInvoiceId": s.last_invoice_id,
    }
    if not full:
        for key in CONTACT_FIELDS:
            out.pop(key)
    return out


def _counted(d: SupportersDonation, paid: set[int]) -> bool:
    """A recorded donation counts; a pledge once its invoice is paid."""
    return d.invoice_id is None or d.invoice_id in paid


def _paid_invoices(ids) -> set[int]:
    ids = {i for i in ids if i}
    if not ids:
        return set()
    return set(
        db.session.scalars(
            select(Invoice.id)
            .where(Invoice.id.in_(ids))
            .where(Invoice.status == "Paid")
        )
    )


def _goal(goal: SupportersGoal, donations: list, paid: set[int], today: date) -> dict:
    raised = sum((d.amount for d in donations if _counted(d, paid)), Decimal("0"))
    pledged = sum((d.amount for d in donations if not _counted(d, paid)), Decimal("0"))
    donors = {(d.member_id or d.name or d.id) for d in donations if _counted(d, paid)}
    target = goal.target or Decimal("0")
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "target": _num(goal.target),
        "raised": _num(raised),
        "pledged": _num(pledged),
        "percent": int(min(raised / target * 100, 999)) if target > 0 else 0,
        "donors": len(donors),
        "endsOn": _iso(goal.ends_on),
        "categoryId": goal.category_id,
        "showPublic": goal.show_public,
        "closed": goal.closed_at is not None,
        "open": goal.closed_at is None
        and (goal.ends_on is None or goal.ends_on >= today),
    }


def _donor_name(d: SupportersDonation, names: dict, full: bool) -> str | None:
    if d.anonymous and not full:
        return None
    return d.name or names.get(d.member_id or 0)


def _donation(d: SupportersDonation, names: dict, paid: set[int], full: bool) -> dict:
    out = {
        "id": d.id,
        "name": _donor_name(d, names, full),
        "anonymous": d.anonymous,
        "amount": _num(d.amount),
        "donatedOn": _iso(d.donated_on),
        "message": d.message,
        "counted": _counted(d, paid),
        "pledge": d.invoice_id is not None,
    }
    if full:
        out.update(
            memberId=d.member_id,
            invoiceId=d.invoice_id,
            transactionId=d.transaction_id,
        )
    return out


def _donations_of(goal_ids) -> dict[int, list[SupportersDonation]]:
    out: dict[int, list] = {i: [] for i in goal_ids}
    if not out:
        return out
    for d in db.session.scalars(
        select(SupportersDonation)
        .where(SupportersDonation.goal_id.in_(list(out)))
        .order_by(SupportersDonation.donated_on.desc(), SupportersDonation.id.desc())
    ):
        out[d.goal_id].append(d)
    return out


# ── Options ──────────────────────────────────────────────────────────────────


@supporters_bp.get("/options")
@require_member
def options():
    from hubra.core.tenant.context import current_tenant

    member = get_current_member()
    can = {
        "sponsorsRead": _can(member, SPONSORS_READ) or _can(member, SPONSORS),
        "sponsors": _can(member, SPONSORS),
        "goals": _can(member, GOALS),
    }
    out = {"can": can, "memberId": member.id}
    tenant = current_tenant()
    if tenant is not None:
        out["publicUrl"] = url_for(
            "supporters_bp.public_page", slug=tenant.slug, _external=True
        )
    if can["sponsors"] or can["goals"]:
        out["categories"] = [
            {"id": c.id, "name": c.name}
            for c in db.session.scalars(
                select(TransactionCategory).order_by(TransactionCategory.name)
            )
        ]
    return jsonify(out)


# ── Packages ─────────────────────────────────────────────────────────────────


def _sponsor_reader(member, **_kw):
    return "editor" if _can(member, SPONSORS) else None


@supporters_bp.get("/packages")
@permission_required("sponsors", "read", "See sponsors", allow=_sponsor_reader)
def list_packages():
    rows = db.session.scalars(
        select(SupportersPackage).order_by(
            SupportersPackage.position, SupportersPackage.amount.desc()
        )
    )
    return jsonify([_package(p) for p in rows])


def _apply_package(p: SupportersPackage, data: dict, partial: bool) -> None:
    if not partial or "name" in data:
        p.name = _text(data, "name", 120, required=True)
    if not partial or "amount" in data:
        p.amount = _money(data, "amount", required=True)
    if not partial or "benefits" in data:
        p.benefits = _text(data, "benefits", 2000)
    if "position" in data:
        p.position = _int(data, "position", 0, 1000, 0)


@supporters_bp.post("/packages")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def create_package():
    last = db.session.scalar(select(func.max(SupportersPackage.position))) or 0
    p = SupportersPackage(position=last + 1)
    _apply_package(p, _body(), partial=False)
    db.session.add(p)
    db.session.commit()
    return jsonify(_package(p)), 201


@supporters_bp.patch("/packages/<int:package_id>")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def update_package(package_id: int):
    p, err = _get(SupportersPackage, package_id)
    if err:
        return err
    _apply_package(p, _body(), partial=True)
    db.session.commit()
    return jsonify(_package(p))


@supporters_bp.delete("/packages/<int:package_id>")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def delete_package(package_id: int):
    p, err = _get(SupportersPackage, package_id)
    if err:
        return err
    used = db.session.scalar(
        select(func.count(SupportersSponsor.id)).where(
            SupportersSponsor.package_id == p.id
        )
    )
    if used:
        return api_error("PACKAGE_IN_USE", "sponsors still have this package", 409)
    db.session.delete(p)
    db.session.commit()
    return "", 204


# ── Sponsors ─────────────────────────────────────────────────────────────────


def _packages() -> dict[int, SupportersPackage]:
    return {p.id: p for p in db.session.scalars(select(SupportersPackage))}


@supporters_bp.get("/sponsors")
@permission_required("sponsors", "read", "See sponsors", allow=_sponsor_reader)
def list_sponsors():
    packages = _packages()
    today = date.today()
    full = _can(get_current_member(), SPONSORS)
    rows = list(db.session.scalars(select(SupportersSponsor)))
    out = [_sponsor(s, packages, today, full) for s in rows]
    out.sort(key=lambda s: (not s["active"], -(s["yearly"] or 0), s["name"].lower()))
    return jsonify(out)


def _apply_sponsor(s: SupportersSponsor, data: dict, partial: bool) -> None:
    def has(key):
        return not partial or key in data

    if has("name"):
        s.name = _text(data, "name", 200, required=True)
    for key, attr, limit in (
        ("contactName", "contact_name", 200),
        ("email", "email", 255),
        ("phone", "phone", 50),
        ("street", "street", 255),
        ("postalCode", "postal_code", 20),
        ("city", "city", 255),
        ("notes", "notes", 5000),
    ):
        if has(key):
            setattr(s, attr, _text(data, key, limit))
    if s.email and "@" not in s.email:
        raise Invalid("email is not an address")
    if has("website"):
        s.website = _website(data)
    if has("packageId"):
        package_id = _int(data, "packageId", 1, 2**31 - 1)
        if (
            package_id is not None
            and db.session.get(SupportersPackage, package_id) is None
        ):
            raise Invalid("packageId: no such package")
        s.package_id = package_id
    if has("amount"):
        s.amount = _money(data, "amount")
    if has("since"):
        s.since = _date(data, "since")
    if has("until"):
        s.until = _date(data, "until")
    if s.since and s.until and s.until < s.since:
        raise Invalid("until lies before since")
    if "showPublic" in data:
        s.show_public = _bool(data, "showPublic")


@supporters_bp.post("/sponsors")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def create_sponsor():
    member = get_current_member()
    s = SupportersSponsor(show_public=True)
    _apply_sponsor(s, _body(), partial=False)
    db.session.add(s)
    db.session.flush()
    log_audit(member.id, "supporters.sponsor.create", "SupportersSponsor", s.id, s.name)
    db.session.commit()
    return jsonify(_sponsor(s, _packages(), date.today())), 201


@supporters_bp.patch("/sponsors/<int:sponsor_id>")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def update_sponsor(sponsor_id: int):
    s, err = _get(SupportersSponsor, sponsor_id)
    if err:
        return err
    _apply_sponsor(s, _body(), partial=True)
    db.session.commit()
    return jsonify(_sponsor(s, _packages(), date.today()))


def _looks_like(blob: bytes, kind: str) -> bool:
    """The file is what its type says (the type comes from the browser)."""
    if kind == "image/png":
        return blob.startswith(b"\x89PNG\r\n\x1a\n")
    if kind == "image/jpeg":
        return blob.startswith(b"\xff\xd8\xff")
    if kind == "image/gif":
        return blob.startswith((b"GIF87a", b"GIF89a"))
    if kind == "image/webp":
        return blob[:4] == b"RIFF" and blob[8:12] == b"WEBP"
    if kind == "image/svg+xml":
        head = blob[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
        return head.startswith((b"<svg", b"<?xml", b"<!--", b"<!doctype svg"))
    return False


def _drop_logo(s: SupportersSponsor) -> None:
    if s.logo_key:
        try:
            store.remove(s.logo_key)
        except store.FileNotFound:
            pass
    s.logo_key = None
    s.logo_type = None


@supporters_bp.delete("/sponsors/<int:sponsor_id>")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def delete_sponsor(sponsor_id: int):
    member = get_current_member()
    s, err = _get(SupportersSponsor, sponsor_id)
    if err:
        return err
    _drop_logo(s)
    log_audit(member.id, "supporters.sponsor.delete", "SupportersSponsor", s.id, s.name)
    db.session.delete(s)
    db.session.commit()
    return "", 204


@supporters_bp.put("/sponsors/<int:sponsor_id>/logo")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def put_logo(sponsor_id: int):
    s, err = _get(SupportersSponsor, sponsor_id)
    if err:
        return err
    upload = request.files.get("logo")
    if upload is None or not upload.filename:
        raise Invalid("logo is required")
    blob = upload.read()
    kind = (upload.mimetype or "").lower()
    if not blob:
        raise Invalid("the logo is empty")
    if kind not in LOGO_TYPES or not _looks_like(blob, kind):
        raise Invalid("the logo must be a PNG, JPEG, WebP, GIF or SVG image")
    if len(blob) > 2 * 1024 * 1024:
        return api_error("FILE_TOO_LARGE", "a logo can be at most 2 MB", 413)
    try:
        stored = store.put(OWNER, blob, kind)
    except store.FileTooLarge as exc:
        return api_error("FILE_TOO_LARGE", str(exc), 413)
    except store.FileStoreError:
        return api_error(
            "FILE_STORE_UNAVAILABLE", "the file store is not reachable", 503
        )
    _drop_logo(s)
    s.logo_key, s.logo_type = stored.key, kind
    db.session.commit()
    return jsonify(_sponsor(s, _packages(), date.today()))


@supporters_bp.delete("/sponsors/<int:sponsor_id>/logo")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def delete_logo(sponsor_id: int):
    s, err = _get(SupportersSponsor, sponsor_id)
    if err:
        return err
    _drop_logo(s)
    db.session.commit()
    return jsonify(_sponsor(s, _packages(), date.today()))


def _send_logo(s: SupportersSponsor, max_age: int = 0):
    if not s.logo_key:
        return api_error("NOT_FOUND", "no logo", 404)
    try:
        blob = store.read(s.logo_key)
    except store.FileNotFound:
        return api_error("NOT_FOUND", "the logo is missing from the store", 404)
    except store.FileStoreError:
        return api_error(
            "FILE_STORE_UNAVAILABLE", "the file store is not reachable", 503
        )
    resp = send_file(io.BytesIO(blob), mimetype=s.logo_type or "image/png")
    # An SVG can carry script: never run it as a page.
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    if max_age:
        resp.headers["Cache-Control"] = f"public, max-age={max_age}"
        resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@supporters_bp.get("/sponsors/<int:sponsor_id>/logo")
@permission_required("sponsors", "read", "See sponsors", allow=_sponsor_reader)
def get_logo(sponsor_id: int):
    s, err = _get(SupportersSponsor, sponsor_id)
    if err:
        return err
    return _send_logo(s)


def _party_for(s: SupportersSponsor, actor: int) -> int:
    """The sponsor's outside party in Finance: made the first time, then kept
    up to date with the sponsor's invoice address."""
    from hubra.core.contracts import SYSTEM, call
    from hubra.core.models.external_party import ExternalParty

    known = bool(s.external_party_id) and (
        db.session.get(ExternalParty, s.external_party_id) is not None
    )
    address = {
        "name": s.name,
        "email": s.email,
        "address_street": s.street,
        "address_postal_code": s.postal_code,
        "address_city": s.city,
    }
    if not known:
        address["notes"] = "Sponsor"
    party = call(
        "finance.external_party.save",
        external_party_id=s.external_party_id if known else None,
        **address,
        actor_id=actor,
        actor=SYSTEM,
    )
    s.external_party_id = party["id"]
    return party["id"]


@supporters_bp.post("/sponsors/invoice")
@permission_required("sponsors", "update", "Add and change sponsors, invoice them")
def invoice_sponsors():
    """One invoice per sponsor for the year; a sponsor invoiced for that
    year already is left out, so it is safe to press twice."""
    from hubra.core.contracts import SYSTEM, call

    member = get_current_member()
    data = _body()
    today = date.today()
    year = _int(data, "year", 2000, 2100, today.year)
    ids = data.get("sponsorIds")
    if ids is not None and not (
        isinstance(ids, list)
        and all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
    ):
        raise Invalid("sponsorIds must be a list of ids")
    due = today + timedelta(days=_int(data, "dueDays", 0, 365, 30))
    category = _category_id(data)
    packages = _packages()
    made, skipped = [], []
    # Locked until the commit: two presses at once wait for each other, and
    # the second sees the year as invoiced instead of invoicing it again.
    query = (
        select(SupportersSponsor).order_by(SupportersSponsor.name).with_for_update()
    )
    if ids is not None:
        query = query.where(SupportersSponsor.id.in_(ids))
    for s in db.session.scalars(query):
        amount = _yearly(s, packages)
        year_start, year_end = date(year, 1, 1), date(year, 12, 31)
        in_year = (s.since is None or s.since <= year_end) and (
            s.until is None or s.until >= year_start
        )
        if s.last_invoiced_year == year or not amount or not in_year:
            skipped.append(s.id)
            continue
        package = packages.get(s.package_id or 0)
        label = f"Sponsoring {year}" + (f" ({package.name})" if package else "")
        invoice = call(
            "finance.invoice.create",
            external_party_id=_party_for(s, member.id),
            issued=today,
            due=due,
            amount=amount,
            purpose="other",
            description=f"{label}: {s.name}"[:512],
            category_id=category,
            actor_id=member.id,
            actor=SYSTEM,
        )
        s.last_invoiced_year, s.last_invoice_id = year, invoice["id"]
        made.append(s.id)
    log_audit(
        member.id,
        "supporters.sponsors.invoice",
        "SupportersSponsor",
        None,
        f"{len(made)} invoices {year}",
    )
    db.session.commit()
    return jsonify({"invoiced": made, "skipped": skipped, "year": year})


# ── Fundraising goals ────────────────────────────────────────────────────────


@supporters_bp.get("/goals")
@require_member
def list_goals():
    today = date.today()
    goals = list(
        db.session.scalars(
            select(SupportersGoal).order_by(
                SupportersGoal.closed_at.is_not(None), SupportersGoal.id.desc()
            )
        )
    )
    donations = _donations_of([x.id for x in goals])
    paid = _paid_invoices(d.invoice_id for ds in donations.values() for d in ds)
    return jsonify([_goal(x, donations[x.id], paid, today) for x in goals])


def _apply_goal(goal: SupportersGoal, data: dict, partial: bool) -> None:
    if not partial or "title" in data:
        goal.title = _text(data, "title", 200, required=True)
    if not partial or "target" in data:
        goal.target = _money(data, "target", required=True, positive=True)
    if not partial or "description" in data:
        goal.description = _text(data, "description", 10000)
    if not partial or "endsOn" in data:
        goal.ends_on = _date(data, "endsOn")
    if not partial or "categoryId" in data:
        goal.category_id = _category_id(data)
    if "showPublic" in data:
        goal.show_public = _bool(data, "showPublic")


@supporters_bp.post("/goals")
@permission_required("goals", "update", "Run fundraising goals and record donations")
def create_goal():
    member = get_current_member()
    goal = SupportersGoal(show_public=True, created_by=member.id)
    _apply_goal(goal, _body(), partial=False)
    db.session.add(goal)
    db.session.flush()
    log_audit(
        member.id, "supporters.goal.create", "SupportersGoal", goal.id, goal.title
    )
    db.session.commit()
    return jsonify(_goal(goal, [], set(), date.today())), 201


@supporters_bp.get("/goals/<int:goal_id>")
@require_member
def get_goal(goal_id: int):
    member = get_current_member()
    goal, err = _get(SupportersGoal, goal_id)
    if err:
        return err
    full = _can(member, GOALS)
    donations = _donations_of([goal.id])[goal.id]
    paid = _paid_invoices(d.invoice_id for d in donations)
    names = _names(d.member_id for d in donations)
    out = _goal(goal, donations, paid, date.today())
    shown = (
        donations
        if full
        else [d for d in donations if _counted(d, paid) or d.member_id == member.id]
    )
    out["donations"] = [_donation(d, names, paid, full) for d in shown]
    out["mine"] = [
        _donation(d, names, paid, True) for d in donations if d.member_id == member.id
    ]
    return jsonify(out)


@supporters_bp.patch("/goals/<int:goal_id>")
@permission_required("goals", "update", "Run fundraising goals and record donations")
def update_goal(goal_id: int):
    goal, err = _get(SupportersGoal, goal_id)
    if err:
        return err
    _apply_goal(goal, _body(), partial=True)
    db.session.commit()
    donations = _donations_of([goal.id])[goal.id]
    paid = _paid_invoices(d.invoice_id for d in donations)
    return jsonify(_goal(goal, donations, paid, date.today()))


@supporters_bp.delete("/goals/<int:goal_id>")
@permission_required("goals", "update", "Run fundraising goals and record donations")
def delete_goal(goal_id: int):
    member = get_current_member()
    goal, err = _get(SupportersGoal, goal_id)
    if err:
        return err
    if _donations_of([goal.id])[goal.id]:
        return api_error(
            "GOAL_HAS_DONATIONS", "close the goal instead; it has donations", 409
        )
    log_audit(
        member.id, "supporters.goal.delete", "SupportersGoal", goal.id, goal.title
    )
    db.session.delete(goal)
    db.session.commit()
    return "", 204


@supporters_bp.post("/goals/<int:goal_id>/close")
@permission_required("goals", "update", "Run fundraising goals and record donations")
def close_goal(goal_id: int):
    goal, err = _get(SupportersGoal, goal_id)
    if err:
        return err
    goal.closed_at = None if _bool(_body(), "reopen") else datetime.now(timezone.utc)
    db.session.commit()
    donations = _donations_of([goal.id])[goal.id]
    paid = _paid_invoices(d.invoice_id for d in donations)
    return jsonify(_goal(goal, donations, paid, date.today()))


def _open_goal(goal_id: int):
    goal, err = _get(SupportersGoal, goal_id)
    if err:
        return None, err
    today = date.today()
    if goal.closed_at is not None or (goal.ends_on and goal.ends_on < today):
        return None, api_error("GOAL_CLOSED", "this goal takes no more donations", 409)
    return goal, None


@supporters_bp.post("/goals/<int:goal_id>/donations")
@permission_required("goals", "update", "Run fundraising goals and record donations")
def record_donation(goal_id: int):
    """A donation that came in (bank, cash, Twint): booked as income now."""
    from hubra.core.models.finance import Transaction

    member = get_current_member()
    goal, err = _get(SupportersGoal, goal_id)
    if err:
        return err
    data = _body()
    donor_id = _int(data, "memberId", 1, 2**31 - 1)
    if donor_id is not None and db.session.get(Member, donor_id) is None:
        raise Invalid("memberId: no such member")
    name = _text(data, "name", 200)
    if donor_id is None and not name:
        raise Invalid("say who donated (a name or a member)")
    method = data.get("method") or "IBAN"
    if method not in METHODS:
        raise Invalid(f"method must be one of {', '.join(METHODS)}")
    donation = SupportersDonation(
        goal_id=goal.id,
        member_id=donor_id,
        name=name,
        amount=_money(data, "amount", required=True, positive=True),
        donated_on=_date(data, "donatedOn") or date.today(),
        anonymous=_bool(data, "anonymous"),
        message=_text(data, "message", 500),
        created_by=member.id,
    )
    payee = name or _names([donor_id]).get(donor_id or 0)
    # The books' transactions table is core, so the income is written there
    # directly (plugins never import the Finances plugin).
    tx = Transaction(
        date=donation.donated_on,
        description=f"Spende: {goal.title}"[:255],
        category_id=goal.category_id,
        member_id=donor_id,
        payee_name=payee,
        amount=donation.amount,
        method=method,
        type="income",
    )
    db.session.add(tx)
    db.session.flush()
    log_audit(member.id, "create_transaction", "Transaction", tx.id, tx.description)
    donation.transaction_id = tx.id
    db.session.add(donation)
    db.session.commit()
    return jsonify(_donation(donation, _names([donor_id]), set(), True)), 201


@supporters_bp.delete("/donations/<int:donation_id>")
@permission_required("goals", "update", "Run fundraising goals and record donations")
def delete_donation(donation_id: int):
    from hubra.core.models.finance import Transaction

    member = get_current_member()
    d, err = _get(SupportersDonation, donation_id)
    if err:
        return err
    if d.invoice_id is not None:
        invoice = db.session.get(Invoice, d.invoice_id)
        if invoice is not None and invoice.status == "Paid":
            return api_error("DONATION_PAID", "a paid pledge stays for the books", 409)
        if invoice is not None:
            # The pledge was not paid: withdraw its invoice too.
            from hubra.core.contracts import SYSTEM, call

            d.invoice_id = None
            db.session.flush()
            call(
                "finance.invoice.delete",
                invoice_id=invoice.id,
                actor_id=member.id,
                actor=SYSTEM,
            )
    if d.transaction_id:
        tx = db.session.get(Transaction, d.transaction_id)
        if tx is not None:
            log_audit(
                member.id, "delete_transaction", "Transaction", tx.id, tx.description
            )
            db.session.delete(tx)
    log_audit(
        member.id,
        "supporters.donation.delete",
        "SupportersDonation",
        d.id,
        f"{d.amount}",
    )
    db.session.delete(d)
    db.session.commit()
    return "", 204


@supporters_bp.post("/goals/<int:goal_id>/pledge")
@require_member
def pledge(goal_id: int):
    """A member gives: an invoice to themselves, paid like any other."""
    from hubra.core.contracts import SYSTEM, call

    member = get_current_member()
    goal, err = _open_goal(goal_id)
    if err:
        return err
    data = _body()
    amount = _money(data, "amount", required=True, positive=True)
    if amount > Decimal("100000"):
        raise Invalid("amount is out of range")
    today = date.today()
    # A member pledges to themselves; giving needs no invoice right.
    made = call(
        "finance.invoice.create",
        member_id=member.id,
        issued=today,
        due=today + timedelta(days=30),
        amount=amount,
        purpose="other",
        description=f"Spende: {goal.title}"[:512],
        category_id=goal.category_id,
        actor_id=member.id,
        actor=SYSTEM,
    )
    invoice = db.session.get(Invoice, made["id"])
    donation = SupportersDonation(
        goal_id=goal.id,
        member_id=member.id,
        amount=amount,
        donated_on=today,
        anonymous=_bool(data, "anonymous"),
        message=_text(data, "message", 500),
        invoice_id=invoice.id,
        created_by=member.id,
    )
    db.session.add(donation)
    db.session.commit()
    return jsonify(_donation(donation, _names([member.id]), set(), True)), 201


# ── Public: for the club website ─────────────────────────────────────────────


def _public_club(slug: str):
    from hubra.core.models.tenant import Tenant
    from hubra.core.modules import is_enabled
    from hubra.core.tenant.context import set_search_path

    tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None or tenant.status != "active":
        return None
    g.tenant = tenant
    set_search_path(tenant.id)
    if not is_enabled("supporters"):
        return None
    return tenant


def _public(resp, max_age: int = 600):
    resp.headers["Cache-Control"] = f"public, max-age={max_age}"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@supporters_bp.get("/public/<string:slug>")
def public_page(slug: str):
    tenant = _public_club(slug)
    if tenant is None:
        return api_error("NOT_FOUND", "Unknown club", 404)
    today = date.today()
    packages = _packages()
    sponsors = [
        s
        for s in db.session.scalars(
            select(SupportersSponsor).where(SupportersSponsor.show_public.is_(True))
        )
        if _active(s, today)
    ]
    sponsors.sort(key=lambda s: (-(_yearly(s, packages) or 0), s.name.lower()))
    goals = list(
        db.session.scalars(
            select(SupportersGoal)
            .where(SupportersGoal.show_public.is_(True))
            .where(SupportersGoal.closed_at.is_(None))
            .order_by(SupportersGoal.id.desc())
        )
    )
    donations = _donations_of([x.id for x in goals])
    paid = _paid_invoices(d.invoice_id for ds in donations.values() for d in ds)
    out_goals = []
    for x in goals:
        item = _goal(x, donations[x.id], paid, today)
        if item["open"]:
            out_goals.append(
                {
                    k: item[k]
                    for k in (
                        "id",
                        "title",
                        "description",
                        "target",
                        "raised",
                        "percent",
                        "donors",
                        "endsOn",
                    )
                }
            )
    return _public(
        jsonify(
            {
                "club": {"name": tenant.name, "slug": tenant.slug},
                "sponsors": [
                    {
                        "name": s.name,
                        "website": s.website,
                        "package": (
                            packages.get(s.package_id or 0).name
                            if s.package_id in packages
                            else None
                        ),
                        "logoUrl": url_for(
                            "supporters_bp.public_logo",
                            slug=tenant.slug,
                            sponsor_id=s.id,
                            _external=True,
                        )
                        if s.logo_key
                        else None,
                    }
                    for s in sponsors
                ],
                "goals": out_goals,
            }
        )
    )


@supporters_bp.get("/public/<string:slug>/logo/<int:sponsor_id>")
def public_logo(slug: str, sponsor_id: int):
    if _public_club(slug) is None:
        return api_error("NOT_FOUND", "Unknown club", 404)
    s = db.session.get(SupportersSponsor, sponsor_id)
    if s is None or not s.show_public or not _active(s, date.today()):
        return api_error("NOT_FOUND", "not found", 404)
    return _send_logo(s, max_age=3600)
