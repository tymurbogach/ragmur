"""Crea la tabla de documentos y la deduplicación por espacio."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("owner_id", sa.Text()),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("chunk_count", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'indexed', 'failed', 'unsupported', 'deleting')",
            name=op.f("ck_documents_status"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "owner_id", "content_sha256", postgresql_nulls_not_distinct=True
        ),
    )
    op.create_index("ix_documents_tenant_id_owner_id", "documents", ["tenant_id", "owner_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_id_owner_id", table_name="documents")
    op.drop_table("documents")
