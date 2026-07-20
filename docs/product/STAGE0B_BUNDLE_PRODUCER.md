# Stage 0B bundle producer

Stage 0B freezes the operational Analysis Bundle V1 producer. The builder validates
the input descriptor, copies existing JSON/JSONL outputs, creates `clips/` and
`thumbnails/`, computes per-file checksums and a deterministic bundle fingerprint,
validates the result, and atomically publishes it.

It never fabricates analytical files, decodes video, loads models or generates
clips. Clips, overlays and processing arrive in later stages. The source video is
external by default, so no long video is copied into Git or the bundle.
