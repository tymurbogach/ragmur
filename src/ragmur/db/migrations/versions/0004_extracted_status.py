"""Añade el estado de extracción terminada."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_documents_status"), "documents", type_="check")
    op.create_check_constraint(
        op.f("ck_documents_status"),
        "documents",
        "status IN ('pending', 'processing', 'extracted', 'indexed', 'failed', 'unsupported', 'deleting')",
    )


def downgrade() -> None:
    op.execute("UPDATE documents SET status = 'failed' WHERE status = 'extracted'")
    op.drop_constraint(op.f("ck_documents_status"), "documents", type_="check")
    op.create_check_constraint(
        op.f("ck_documents_status"),
        "documents",
        "status IN ('pending', 'processing', 'indexed', 'failed', 'unsupported', 'deleting')",
    )
