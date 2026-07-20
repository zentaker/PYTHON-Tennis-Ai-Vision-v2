# Product pivot: TennisAI Training Session Analyzer

## Decision

The previous experimental product was monocular XYZ reconstruction with synthetic
top/side views. The product direction is now **TennisAI Training Session Analyzer**:
turn training video into rallies, clips, events, statistics, tactical patterns and
coaching recommendations.

## Available capabilities

- ball detection and smoothed ball tracking;
- court calibration;
- contact and bounce events;
- near/far player selection;
- player pose at relevant frames;
- P1 → Analytics contracts.

True monocular XYZ, metric top/side reconstruction, validated 3D speed and
competitive line calling remain experimental/non-blocking. Stage 5B is archived as
research and does not block the product baseline.

Stage 0A defines contracts only. Runtime refactoring, rally segmentation and a web
repository are deferred to later stages.
