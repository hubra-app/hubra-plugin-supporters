"""Supporters: sponsors and fundraising goals.

- Sponsors with a package (Gold, Silber, Gönner ...), the yearly invoice
  to each sponsor, and their logos. The club website reads the sponsors
  who want to be shown, with their logos, from a public address.
- Fundraising goals: a project (a new boat, a trip, a machine) with a
  target and a progress bar. The treasurer records donations from anyone;
  a member can pledge an amount, which becomes an invoice they can pay
  like any other (online too, with the payments plugin). A pledge counts
  once its invoice is paid.

Logos sit in Hubra's file store, encrypted per club.

Permissions:
    supporters.sponsors.read      see sponsors and packages
    supporters.sponsors.update    add and change them, invoice them
    supporters.goals.update       run fundraising goals and record donations

Public (for the club website, no sign-in):
    GET /api/v1/app/supporters/public/<club>             sponsors and goals
    GET /api/v1/app/supporters/public/<club>/logo/<id>   a sponsor's logo
"""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="supporters",
    # Access the standard roles get when a club first switches it on
    # (docs/roles.md in hubra-app/hubra).
    role_defaults={"member": "view", "board": "view", "secretary": "edit", "treasurer": "all"},
    name="Supporters",
    description="Sponsors and fundraising goals",
    default_enabled=False,
    depends_on=("members", "finance"),
    blueprints=(
        Blueprint("hubra_supporters.routes", "supporters_bp", "/api/v1/app/supporters"),
    ),
    nav=(
        NavItem(
            "/app/supporters",
            "shell.nav.supporters",
            "heart-handshake",
            section="more",
            order=26,
        ),
    ),
    # They check the club's module themselves, like the events feed.
    public_endpoints=(
        "supporters_bp.public_page",
        "supporters_bp.public_logo",
    ),
    tables=(
        "supporters_packages",
        "supporters_sponsors",
        "supporters_goals",
        "supporters_donations",
    ),
    # Hubra's features it uses, through contracts (docs/contracts.md in hubra).
    consumes={
        "finance.invoice.create": ">=1,<2",
        "finance.invoice.delete": ">=1,<2",
        "finance.external_party.save": ">=1,<2",
    },
)
