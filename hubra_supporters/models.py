"""The Supporters tables (one copy per club schema)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _member_fk() -> ForeignKey:
    return ForeignKey("members.id", ondelete="SET NULL")


class SupportersPackage(db.Model):
    """A sponsorship package: what a sponsor pays a year and gets for it."""

    __tablename__ = "supporters_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    benefits: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SupportersSponsor(db.Model):
    __tablename__ = "supporters_sponsors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    website: Mapped[str | None] = mapped_column(String(300))
    street: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(255))
    package_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("supporters_packages.id", ondelete="SET NULL")
    )
    # A yearly amount of its own instead of the package's.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    since: Mapped[date | None] = mapped_column(Date)
    until: Mapped[date | None] = mapped_column(Date)
    # Hidden until the club says so: a sponsor may be a private person.
    show_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    logo_key: Mapped[str | None] = mapped_column(String(120))
    logo_type: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    # The invoice recipient in Finanzen, made with the first invoice.
    external_party_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("external_parties.id", ondelete="SET NULL")
    )
    last_invoiced_year: Mapped[int | None] = mapped_column(Integer)
    last_invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class SupportersGoal(db.Model):
    """A fundraising goal: one project with a target."""

    __tablename__ = "supporters_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    # Donations are booked under this finance category.
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transaction_categories.id", ondelete="SET NULL")
    )
    show_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(Integer, _member_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class SupportersDonation(db.Model):
    """A donation to a goal: recorded by the treasurer (booked as income
    right away), or pledged by a member (an invoice; counts once paid)."""

    __tablename__ = "supporters_donations"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("supporters_goals.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[int | None] = mapped_column(Integer, _member_fk(), index=True)
    # The donor's name when not a member (or as they want to be named).
    name: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    donated_on: Mapped[date] = mapped_column(Date, nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="SET NULL")
    )
    transaction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("transactions.id", ondelete="SET NULL")
    )
    created_by: Mapped[int | None] = mapped_column(Integer, _member_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
