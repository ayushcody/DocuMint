from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_split_classify_runs"
down_revision = "001_initial_with_rls"
branch_labels = None
depends_on = None


RLS_TABLES = ("split_runs", "classification_runs")


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
        "split_runs",
        *_workspace_columns(),
        sa.Column(
            "parse_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_runs.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("segments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    op.create_table(
        "classification_runs",
        *_workspace_columns(),
        sa.Column(
            "parse_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parse_runs.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("taxonomy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("page_labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )

    for table_name in RLS_TABLES:
        _enable_rls(table_name)


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS workspace_isolation_{table_name} ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
    op.drop_table("classification_runs")
    op.drop_table("split_runs")
