# Stage 1A single-rally input inventory

This inventory records what is available in the repository without claiming that
an ignored local video or an untracked model artifact is present. Stage 1A imports
existing outputs read-only; it does not run detection, tracking or segmentation.

| Input | Location | Origin / current format | Approval | Local | Importable | Limitations |
|---|---|---|---|---|---|---|
| Reference video | `data/clips/nivel_a2_01/source.mp4` | Selected external Nivel A2 clip | Asset alignment passed | Local external | Yes | Not copied to Git or bundle |
| Canonical clip metadata | `data/clips/nivel_a2_01/clip_manifest.json` | Stage 2 manifest JSON | Historical approved metadata | Yes | Yes | Source video is not versioned |
| Stage 3 ball track | `outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv` | Existing ignored Stage 3 CSV | Asset alignment passed | Local ignored | Yes | 383 visible, 19 interpolated, 125 missing |
| Stage 4 events | `data/clips/nivel_a2_01/manual_annotation.json` | Human-reviewed `narrative_events` JSON | Stage 4 A2 human evidence | Yes | Yes | Manual events, not automatic segmentation |
| VFR timestamps | `data/clips/nivel_a2_01/frame_timestamps.json` | VFR frame sidecar JSON | Existing timing evidence | Yes | Yes | Tied to the absent source clip |
| Court calibration | `data/clips/nivel_a2_01/homography.json` | Existing pixel-to-court homography JSON | Existing 2D calibration evidence | Yes | Yes | Imported as image-pixel polygon plus court-meter target; no 3D claim |
| P1 → Analytics | `tests/fixtures/integration/p1_analytics_accepted/` | Accepted serialized P1/Stage 4 fixture | P1 functional wiring passed | Yes | Optional | Evidence is fixture/serialized output, not a new inference run |
| Contract fixture | `tests/fixtures/product/single_rally_v1/` | `synthetic_contract_fixture` JSON/CSV | Test-only | Yes | Yes | Synthetic records are never labeled as real |

The selected assets align to `nivel_a2_01` and produced a real candidate outside
Git. The source remains external; the Stage 3 CSV remains local and ignored. The
candidate is `partial` because missing observations are preserved, and its surface
is `unknown` because no authoritative surface metadata was found. Human audit is
required before the real bundle gate can pass. The synthetic fixture remains
separate and is not used for this candidate.
