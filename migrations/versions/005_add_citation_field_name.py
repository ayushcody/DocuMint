from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "005_add_citation_field_name"
down_revision = "004_webhook_endpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("citations", sa.Column("field_name", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("citations", "field_name")
