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
    supporters.sponsors.read      see sponsors and packages (no contact details)
    supporters.sponsors.update    add and change them, with contact details
    supporters.goals.update       run fundraising goals
    supporters.donations.read_amounts  see what each donor gave
                                  (or finance.transactions.read)
    supporters.bookings.manage    record and delete donations, which books
                                  income (or finance.transactions.create)
    supporters.invoices.manage    invoice sponsors for the year
                                  (or finance.invoices.create)

"manage" is in no role's "Bearbeiten" level: booking money and invoicing
take a finance right or one of these, given on purpose.

Public (for the club website, no sign-in):
    GET /api/v1/app/supporters/public/<club>             sponsors and goals
    GET /api/v1/app/supporters/public/<club>/logo/<id>   a sponsor's logo
"""

from hubra.core.contracts import WidgetField, widget_contract
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
    permissions=(
        ("supporters.donations.read_amounts", "See what each donor gave"),
        ("supporters.bookings.manage", "Record and delete donations (books income)"),
        ("supporters.invoices.manage", "Invoice sponsors"),
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
    # Dashboard widgets (hubra_supporters/widgets.py).
    provides=(
        widget_contract(
            "supporters.goals",
            "hubra_supporters.widgets:goals",
            label="supporters.widget.goals",
            description="supporters.widget.goalsHint",
            size="m",
            view="list",
            fields=(WidgetField("count", "supporters.widget.count", "number", 3),),
        ),
        widget_contract(
            "supporters.sponsors",
            "hubra_supporters.widgets:sponsors",
            label="supporters.widget.sponsors",
            description="supporters.widget.sponsorsHint",
            size="s",
            view="stat",
            perm="supporters.sponsors.read",
        ),
    ),
)
