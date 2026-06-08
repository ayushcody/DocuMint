from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial_with_rls"
down_revision = None
branch_labels = None
depends_on = None


RLS_TABLES: Sequence[str] = (
    "documents",
    "parse_runs",
    "parse_blocks",
    "citations",
    "extraction_schemas",
    "extraction_runs",
    "index_collections",
    "chunks",
    "human_review_actions",
)


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def _workspace_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        *_timestamps(),
    ]


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY workspace_isolation_{table_name}
        ON {table_name}
        USING (workspace_id = current_setting('app.workspace_id')::uuid)
        WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid)
        """
    )


def upgrade() -> None:
    op.create_table(
        "documents",
        *_workspace_columns(),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False, index=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=128),
            nullable=False,
            server_default="application/pdf",
        ),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "parse_runs",
        *_workspace_columns(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_credits", sa.Float(), nullable=False, server_default="0"),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "agent_timings_ms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "parse_blocks",
        *_workspace_columns(),
        sa.Column(
            "parse_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_runs.id"),
            nullable=False,
        ),
        sa.Column("block_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ast", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verifier", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reading_order_rank", sa.Integer(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "extraction_schemas",
        *_workspace_columns(),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("json_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    op.create_table(
        "extraction_runs",
        *_workspace_columns(),
        sa.Column(
            "parse_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "schema_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extraction_schemas.id"),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "citations",
        *_workspace_columns(),
        sa.Column(
            "parse_block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_blocks.id"),
            nullable=True,
        ),
        sa.Column(
            "extraction_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extraction_runs.id"),
            nullable=True,
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("matching_text", sa.Text(), nullable=False),
        sa.Column("bboxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    op.create_table(
        "index_collections",
        *_workspace_columns(),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column(
            "enable_binary_quantization",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.create_table(
        "chunks",
        *_workspace_columns(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column(
            "parse_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_runs.id"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vector_ref", sa.String(length=1024), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    op.create_table(
        "human_review_actions",
        *_workspace_columns(),
        sa.Column(
            "parse_block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_blocks.id"),
            nullable=True,
        ),
        sa.Column("actor_id", sa.String(length=256), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    for table_name in RLS_TABLES:
        _enable_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS workspace_isolation_{table_name} ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_table("human_review_actions")
    op.drop_table("chunks")
    op.drop_table("index_collections")
    op.drop_table("citations")
    op.drop_table("extraction_runs")
    op.drop_table("extraction_schemas")
    op.drop_table("parse_blocks")
    op.drop_table("parse_runs")
    op.drop_table("documents")
