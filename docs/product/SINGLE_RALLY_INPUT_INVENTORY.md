# Stage 1A single-rally input inventory

This inventory records what is available in the repository without claiming that
an ignored local video or an untracked model artifact is present. Stage 1A imports
existing outputs read-only; it does not run detection, tracking or segmentation.

| Input | Location | Origin / current format | Approval | Local | Importable | Limitations |
|---|---|---|---|---|---|---|
| Reference video | `data/reference_clip/madrid_R1.mov` (documented only) | Historical Nivel A clip, external and ignored | Reference documented, file absent | No | No | `REAL_REFERENCE_VIDEO_MISSING`; no real bundle is produced |
| Canonical clip metadata | `data/clips/nivel_a2_01/clip_manifest.json` | Stage 2 manifest JSON | Historical approved metadata | Yes | Yes | Source video is not versioned |
| Stage 3 ball track | `outputs/` and ignored local outputs | Stage 3 CSV contract (`trajectory_io`) | No current file found | No | No | Fixture only; no observations are invented |
| Stage 4 events | `data/clips/nivel_a2_01/manual_annotation.json` | Human-reviewed `narrative_events` JSON | Stage 4 A2 human evidence | Yes | Yes | Manual events, not automatic segmentation |
| VFR timestamps | `data/clips/nivel_a2_01/frame_timestamps.json` | VFR frame sidecar JSON | Existing timing evidence | Yes | Yes | Tied to the absent source clip |
| Court calibration | `data/clips/nivel_a2_01/homography.json` | Existing pixel-to-court homography JSON | Existing 2D calibration evidence | Yes | Yes | Imported as image-pixel polygon plus court-meter target; no 3D claim |
| P1 → Analytics | `tests/fixtures/integration/p1_analytics_accepted/` | Accepted serialized P1/Stage 4 fixture | P1 functional wiring passed | Yes | Optional | Evidence is fixture/serialized output, not a new inference run |
| Contract fixture | `tests/fixtures/product/single_rally_v1/` | `synthetic_contract_fixture` JSON/CSV | Test-only | Yes | Yes | Synthetic records are never labeled as real |

The real reference video and a versioned Stage 3 ball track are missing locally,
so the release artifact is a deterministic contract fixture only. Its calibration
is explicitly `synthetic` with provenance `synthetic_contract_fixture`; it is not
product evidence. The importer
accepts a real short rally when its source video and existing track are supplied;
it preserves their timestamps, confidence and provenance without rewriting them.
