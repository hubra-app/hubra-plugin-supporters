"""supporters packages, sponsors, goals and donations

Runs in public and in every club's schema, tracked in its own version table
(alembic_version_supporters). has_table() keeps it safe to run twice.

Revision ID: 3b8f6d2e9a41
Revises:
Create Date: 2026-11-05 11:30:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table

revision = "3b8f6d2e9a41"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(col, target, ondelete="SET NULL"):
    return sa.ForeignKeyConstraint([col], [target], ondelete=ondelete)


def upgrade():
    if not has_table("supporters_packages"):
        op.create_table(
            "supporters_packages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("benefits", sa.Text(), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if not has_table("supporters_sponsors"):
        op.create_table(
            "supporters_sponsors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("contact_name", sa.String(200), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("website", sa.String(300), nullable=True),
            sa.Column("street", sa.String(255), nullable=True),
            sa.Column("postal_code", sa.String(20), nullable=True),
            sa.Column("city", sa.String(255), nullable=True),
            sa.Column("package_id", sa.Integer(), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("since", sa.Date(), nullable=True),
            sa.Column("until", sa.Date(), nullable=True),
            sa.Column("show_public", sa.Boolean(), nullable=False),
            sa.Column("logo_key", sa.String(120), nullable=True),
            sa.Column("logo_type", sa.String(100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("external_party_id", sa.Integer(), nullable=True),
            sa.Column("last_invoiced_year", sa.Integer(), nullable=True),
            sa.Column("last_invoice_id", sa.Integer(), nullable=True),
            _ts("created_at", nullable=False),
            _fk("package_id", "supporters_packages.id"),
            _fk("external_party_id", "external_parties.id"),
            _fk("last_invoice_id", "invoices.id"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not has_table("supporters_goals"):
        op.create_table(
            "supporters_goals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("target", sa.Numeric(12, 2), nullable=False),
            sa.Column("ends_on", sa.Date(), nullable=True),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column("show_public", sa.Boolean(), nullable=False),
            _ts("closed_at"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            _ts("created_at", nullable=False),
            _fk("category_id", "transaction_categories.id"),
            _fk("created_by", "members.id"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not has_table("supporters_donations"):
        op.create_table(
            "supporters_donations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("goal_id", sa.Integer(), nullable=False),
            sa.Column("member_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(200), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("donated_on", sa.Date(), nullable=False),
            sa.Column("anonymous", sa.Boolean(), nullable=False),
            sa.Column("message", sa.String(500), nullable=True),
            sa.Column("invoice_id", sa.Integer(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            _ts("created_at", nullable=False),
            _fk("goal_id", "supporters_goals.id", "CASCADE"),
            _fk("member_id", "members.id"),
            _fk("invoice_id", "invoices.id"),
            _fk("transaction_id", "transactions.id"),
            _fk("created_by", "members.id"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_supporters_donations_goal_id", "supporters_donations", ["goal_id"]
        )
        op.create_index(
            "ix_supporters_donations_member_id", "supporters_donations", ["member_id"]
        )


def downgrade():
    for table in (
        "supporters_donations",
        "supporters_goals",
        "supporters_sponsors",
        "supporters_packages",
    ):
        if has_table(table):
            op.drop_table(table)
