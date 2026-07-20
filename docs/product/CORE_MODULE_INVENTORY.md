# TennisAI Core module inventory

This inventory freezes the product boundary without deleting or refactoring the
experimental pipeline. The future product consumes versioned Analysis Bundles.

| Component | Location | Category | Purpose / status | Dependency | Future product | Action |
|---|---|---|---|---|---|---|
| Stage 1 court calibration | `src/calibration`, `src/geometry` | PRODUCT_REQUIRED | Court map and pixel geometry; validated | video/court points | yes | KEEP |
| Stage 2 ball detection | `src/ball_detection`, `src/detector` | PRODUCT_REQUIRED | Ball observations; approved with limits | model checkpoint | yes | LAZY_LOAD |
| Stage 3 tracking/smoothing | `src/tracker` | PRODUCT_REQUIRED | Continuous ball track and confidence | Stage 2 | yes | KEEP |
| Stage 4 events | `src/analytics/adapters`, `src/analytics` | PRODUCT_REQUIRED | Contacts, bounces and event contracts | Stage 3/manual labels | yes | KEEP |
| Stage 5A camera/calibration | `src/ground_plane_calibration`, `src/geometry` | PRODUCT_OPTIONAL | Calibration diagnostics and uncertainty | court map/P1 | yes | LAZY_LOAD |
| Stage 5B research | `src/stage5b_v3`, `.artifacts/stage5b-*` | EXPERIMENTAL_ARCHIVED | Monocular XYZ research; gates not met | Stage 5A/P1 | no | ARCHIVE |
| Player perception P1 | `src/player_perception`, `config/player_perception` | PRODUCT_REQUIRED | Player selection, pose and contacts | detector/pose model | yes | KEEP |
| Player selection | `src/player_perception` | PRODUCT_REQUIRED | Near/far player identity | P1 tracks | yes | KEEP |
| P1 → Analytics | `src/analytics/p1_wiring.py` | PRODUCT_REQUIRED | Schema-valid event records | P1 + Stage 4 | yes | KEEP |
| Stroke taxonomy | `src/analytics` | PRODUCT_OPTIONAL | Shot dimensions and labels | event/pose evidence | yes | REVIEW |
| Kinematics | `src/analytics` | DEPRECATED_OR_SUPERSEDED | Real metric 3D speed remains blocked | approved XYZ required | no | REPLACE |
| Validation scripts | `scripts/check_*`, `tests` | TEST_AND_VALIDATION | Reproducible gates and evidence | all stages | yes | KEEP |
| Artifacts | `.artifacts`, `docs/validation/assets` | TEST_AND_VALIDATION | Evidence, not runtime input | workflow outputs | no | ARCHIVE |
| Models/checkpoints | `models`, `config` | DEVELOPMENT_TOOLING | Optional model assets | profile selection | yes | LAZY_LOAD |
| Replit support | `scripts/replit_smoke_test.py`, `replit.nix` | DEVELOPMENT_TOOLING | CPU smoke environment | core imports | no | KEEP |
| CI | `.github/workflows/ci.yml` | DEVELOPMENT_TOOLING | Tests, schemas and artifacts | GitHub Actions | yes | KEEP |
| Documentation | `docs`, `ROADMAP.md` | DEVELOPMENT_TOOLING | Contracts, decisions and gates | repository | yes | KEEP |

No module is deleted by Stage 0A. Web UI is intentionally outside this repository
for now.
