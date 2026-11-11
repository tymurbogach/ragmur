"""Limita owner_id sin modificar los datos existentes."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM documents WHERE char_length(owner_id) > 256"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"Cannot add owner_id limit: {count} document(s) exceed 256 characters. "
            "Resolve these records before retrying the migration."
        )
    op.create_check_constraint(
        op.f("ck_documents_owner_id_length"),
        "documents",
        "owner_id IS NULL OR char_length(owner_id) <= 256",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_documents_owner_id_length"), "documents", type_="check")
