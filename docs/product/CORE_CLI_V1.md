# TennisAI Core CLI V1

The `tennisai` CLI packages existing Core outputs; it does not run inference,
tracking, perception or rally segmentation.

```bash
tennisai profile show FAST --json
tennisai bundle build --source-video session.mp4 --inputs bundle-inputs.json \
  --session-id session_001 --profile FAST --surface clay \
  --output analysis/session_001 --created-at 2026-07-20T00:00:00Z
tennisai bundle validate --bundle analysis/session_001 --json
```

Source video is external by default and only its sanitized name, size and SHA256
are stored. `--verify-source` is optional during validation. Existing outputs are
copied into canonical bundle paths; absent optional outputs are omitted.
