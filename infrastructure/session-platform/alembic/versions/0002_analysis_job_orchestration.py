"""add Stage 2B analysis job orchestration fields"""

from alembic import op
import sqlalchemy as sa


revision = "0002_analysis_job_orchestration"
down_revision = "0001_session_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("input_video_id", sa.Uuid(), nullable=True))
    op.add_column("analysis_runs", sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("analysis_runs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("analysis_runs", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("lease_owner", sa.String(128), nullable=True))
    op.add_column("analysis_runs", sa.Column("lease_token", sa.String(64), nullable=True))
    op.add_column("analysis_runs", sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("worker_version", sa.String(80), nullable=True))
    op.add_column("analysis_runs", sa.Column("result_manifest", sa.Text(), nullable=True))
    op.add_column("analysis_runs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_runs", sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_analysis_runs_input_video_id",
        "analysis_runs",
        "videos",
        ["input_video_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_analysis_runs_attempt_bounds",
        "analysis_runs",
        "attempt >= 0 AND max_attempts >= 1 AND attempt <= max_attempts",
    )
    op.create_index("ix_analysis_runs_queue", "analysis_runs", ["status", "queued_at"])
    op.create_index(
        "uq_analysis_runs_active_profile",
        "analysis_runs",
        ["session_id", "processing_profile"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'QUEUED', 'RUNNING')"),
        sqlite_where=sa.text("status IN ('PENDING', 'QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_analysis_runs_active_profile", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_queue", table_name="analysis_runs")
    op.drop_constraint("ck_analysis_runs_attempt_bounds", "analysis_runs", type_="check")
    op.drop_constraint("fk_analysis_runs_input_video_id", "analysis_runs", type_="foreignkey")
    for name in (
        "terminal_at",
        "updated_at",
        "result_manifest",
        "worker_version",
        "cancel_requested_at",
        "heartbeat_at",
        "lease_expires_at",
        "lease_acquired_at",
        "lease_token",
        "lease_owner",
        "queued_at",
        "max_attempts",
        "attempt",
        "input_video_id",
    ):
        op.drop_column("analysis_runs", name)
