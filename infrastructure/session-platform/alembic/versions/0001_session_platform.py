"""create Stage 2A session platform tables"""

from alembic import op
import sqlalchemy as sa

revision = "0001_session_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("processing_profile", sa.String(80), nullable=False),
        sa.Column("surface", sa.String(20), nullable=False),
        sa.Column("source_video_id", sa.Uuid()),
        sa.Column("latest_analysis_run_id", sa.Uuid()),
        sa.Column("bundle_fingerprint", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_started_at", sa.DateTime(timezone=True)),
        sa.Column("analysis_completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_status", "sessions", ["status"])
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])
    op.create_table(
        "videos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("integrity_status", sa.String(32), nullable=False),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("encoded_width", sa.Integer()),
        sa.Column("encoded_height", sa.Integer()),
        sa.Column("canonical_width", sa.Integer()),
        sa.Column("canonical_height", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_videos_object_key"),
    )
    op.create_index("ix_videos_session_id", "videos", ["session_id"])
    op.create_index("ix_videos_sha256", "videos", ["sha256"])
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("processing_profile", sa.String(80), nullable=False),
        sa.Column("core_version", sa.String(40)),
        sa.Column("bundle_fingerprint", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_runs_session_id", "analysis_runs", ["session_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(80)),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_artifacts_analysis_run_id", "artifacts", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index("ix_artifacts_analysis_run_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_analysis_runs_session_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index("ix_videos_sha256", table_name="videos")
    op.drop_index("ix_videos_session_id", table_name="videos")
    op.drop_table("videos")
    op.drop_index("ix_sessions_created_at", table_name="sessions")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_table("sessions")
