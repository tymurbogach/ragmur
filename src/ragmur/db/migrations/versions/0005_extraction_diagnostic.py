"""Conserva diagnósticos de extracción sin convertirlos en errores."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("diagnostic", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "diagnostic")
