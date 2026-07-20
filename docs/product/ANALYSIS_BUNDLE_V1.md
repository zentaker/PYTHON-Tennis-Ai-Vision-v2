# Analysis Bundle V1

Bundles are immutable, versioned directories related to one source video:

```text
analysis/<session_id>/
├── manifest.json
├── session.json
├── rallies.json
├── events.jsonl
├── ball_track.jsonl
├── player_tracks.jsonl
├── poses.jsonl
├── court_map.json
├── metrics.json
├── tactical_patterns.json
├── coaching_input.json
├── clips/
└── thumbnails/
```

`manifest.json` is produced by the Core and consumed by the future Web viewer and
CLI. It identifies the source video, processing profile, capabilities, limitations,
checksums and status. JSONL records use source-video timestamps in seconds and
include frame identifiers, confidence and schema versions where applicable. Metric
units are explicit SI or pixels; optional files are omitted rather than fabricated.
Checksums bind every file to the original session and bundle version.

Stage 0B freezes `schema_version: analysis_bundle.v1`. Source video metadata is
external by default (`display_name`, format, size and SHA256 only); personal
absolute paths are never persisted. Every packaged file has a relative path,
producer, consumer, media type, schema version, size and checksum. The
`bundle_fingerprint` is a SHA256 over the normalized manifest, internal checksums
and source-video checksum, making builds reproducible for fixed inputs and time.

The web repository will be created only after this contract is frozen during Stage
0B.
