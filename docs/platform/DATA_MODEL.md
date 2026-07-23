# Data model

Alembic migration `0001_session_platform` creates four tables:

- `sessions`: title, lifecycle status, processing profile, surface, source/latest
  references, bundle fingerprint, timestamps, and error details.
- `videos`: one source-video record per session, content metadata, safe object key,
  declared checksum, and storage integrity status.
- `analysis_runs`: profile/versioned run metadata and lifecycle timestamps.
- `artifacts`: typed bundle/report objects linked to an analysis run.

Foreign keys and indexes cover session status, creation order, video session/role,
run session/status, and artifact run/kind. The API exposes metadata only; video
bytes never enter PostgreSQL.

Session statuses are `DRAFT`, `AWAITING_UPLOAD`, `UPLOADING`, `UPLOADED`,
`QUEUED`, `PROCESSING`, `COMPLETE`, `PARTIAL`, and `FAILED`. Legal transitions
are explicit in `src/platform/domain/transitions.py`. Analysis run statuses are
`PENDING`, `QUEUED`, `RUNNING`, `COMPLETE`, `PARTIAL`, `FAILED`, and `CANCELLED`.
