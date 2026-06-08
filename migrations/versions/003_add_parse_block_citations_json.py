from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_add_parse_block_citations_json"
down_revision = "002_split_classify_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parse_blocks",
        sa.Column(
            "citations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("parse_blocks", "citations_json", server_default=None)


def downgrade() -> None:
    op.drop_column("parse_blocks", "citations_json")
