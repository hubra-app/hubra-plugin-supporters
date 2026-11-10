"""Dashboard widgets of Supporters (docs/dashboards.md in hubra-app/hubra).

supporters.goals     list  open fundraising goals and how far each one is
supporters.sponsors  stat  active sponsors and what they give a year

They read as the viewing member.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from hubra.core.extensions import db

from .models import SupportersGoal, SupportersPackage, SupportersSponsor
from .routes import _active, _counted, _donations_of, _paid_invoices, _yearly


def _chf(amount) -> str:
    return f"CHF {Decimal(amount or 0):,.0f}".replace(",", "'")


def _count(config: dict) -> int:
    try:
        return max(1, min(int(config.get("count") or 3), 20))
    except (TypeError, ValueError):
        return 3


def goals(ctx, config: dict) -> dict:
    """Goals not closed or over, the newest first: raised of the target."""
    today = date.today()
    rows = [
        g
        for g in db.session.scalars(
            select(SupportersGoal)
            .where(SupportersGoal.closed_at.is_(None))
            .order_by(SupportersGoal.id.desc())
        )
        if g.ends_on is None or g.ends_on >= today
    ]
    shown = rows[: _count(config)]
    donations = _donations_of([g.id for g in shown])
    paid = _paid_invoices(d.invoice_id for ds in donations.values() for d in ds)
    items = []
    for g in shown:
        raised = sum((d.amount for d in donations[g.id] if _counted(d, paid)), Decimal("0"))
        share = int(raised * 100 / g.target) if g.target else 0
        items.append(
            {
                "label": g.title,
                "sub": f"{_chf(raised)} / {_chf(g.target)} · {share}%",
                "path": f"/app/supporters/goals/{g.id}",
            }
        )
    return {"items": items, "total": len(rows)}


def sponsors(ctx, config: dict) -> dict:
    """How many sponsors are active today, and their yearly amount."""
    today = date.today()
    packages = {p.id: p for p in db.session.scalars(select(SupportersPackage))}
    active = [s for s in db.session.scalars(select(SupportersSponsor)) if _active(s, today)]
    total = sum((_yearly(s, packages) or Decimal("0") for s in active), Decimal("0"))
    german = (getattr(ctx.actor, "language", None) or "de").lower().startswith("de")
    sub = f"{_chf(total)} / {'Jahr' if german else 'year'}"
    return {"value": len(active), "sub": sub, "path": "/app/finance/sponsors"}
