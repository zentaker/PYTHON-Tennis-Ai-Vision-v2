# TennisAI Session Analyzer roadmap

| Stage | Objective | Inputs / outputs | Dependency | Verifiable gate | Out of scope |
|---|---|---|---|---|---|
| 0A | Product baseline and contracts | docs, schema, fixture | approved main | manifest schema and inventory review | runtime refactor |
| 0B | Stable CLI and Bundle producer | existing outputs → Analysis Bundle | 0A | deterministic fixture bundle and validator | inference, Web repo |
| 0C | Performance baseline on approved short clip | approved clip/profile | 0B | CPU/resource report | cloud optimization |
| 1A | Single Rally Contract & Existing-Output Import | existing short-rally outputs → one Analysis Bundle | 0B | contract fixture and integrity audit | inference, long-video scan, Web |
| 1B | Real Single Rally Bundle Candidate | aligned external reference assets → derived real candidate bundle | 1A | `REAL_REFERENCE_ASSET_ALIGNMENT_PASSED`; human audit pending | video/model copy, inference, Stage 5B |
| 1 | Single Rally Analyzer | one rally → events/clip/metrics | 1A | rally bundle acceptance | long-video scan |
| 2 | Long-video activity scan and segmentation | session video → rallies | 1 | boundary precision audit | web UI |
| 3 | Court Analytics 2D | rallies + court map | 2 | 2D event/zone audit | validated XYZ |
| 4 | TennisAI Web Viewer MVP | Analysis Bundle | 3 | separate web smoke test | model execution in web |
| 5 | Shot Intelligence | contacts/poses → labels | 3 | taxonomy audit | spin |
| 6 | Tactical Pattern Engine | events/metrics → patterns | 5 | evidence-linked patterns | coaching automation |
| 7 | Session Analytics and rally ranking | patterns + rallies | 6 | ranking reproducibility | match mode |
| 8 | Highlights and export | rallies/patterns | 7 | export integrity | mobile app |
| 9 | Coaching Engine | session analytics | 7 | coach review gate | autonomous advice |
| 10 | RTX 2060 versus disposable cloud benchmark | stable CLI | 0C | measured benchmark | always-on cloud |
| 11 | Match Mode | match video/scoring | 7 | separate match contract | MVP scope |

The web repository is created only after Analysis Bundle V1 is frozen in Stage 0B.
