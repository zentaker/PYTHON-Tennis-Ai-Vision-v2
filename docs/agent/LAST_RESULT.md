# Last result

- Stage 5B research archived at `research-stage5b-v351-final`; PR #5 closed without merge.
- Approved main baseline tagged `tennisai-core-approved-baseline-2026-07-20`.
- Product pivot recorded as `CORE_PRODUCTIZATION_STAGE0A_READY_FOR_REVIEW`.
- Analysis Bundle V1 schema, fixture, processing profiles, inventory and roadmap published.
- Web repository not created; runtime pipeline unchanged; cloud/GPU/spend: 0/0/0.
- Stage 0A merged as `d5a00c23f267c91371ce575343979b8bc2d06061` and tagged
  `tennisai-core-stage0a`.
- Stage 0B CLI packages existing outputs only, validates paths/checksums/fingerprint,
  and produces a deterministic fixture without loading models.
- Consistency patch hardened session/rallies schemas, cross-file semantic checks,
  descriptor-relative inputs and symlink rejection; CI passed.
- Stage 0B final human gate passed: `STAGE0B_FINAL_HUMAN_GATE_PASSED`.
- Analysis Bundle V1 transport contract frozen:
  `ANALYSIS_BUNDLE_V1_TRANSPORT_CONTRACT_FROZEN`. The freeze covers layout,
  manifest/session/rallies envelopes, packaging statuses, checksums, fingerprint,
  profile names and Core CLI; detailed analytical record schemas remain independent
  versioned contracts.
- Stage 1A importer, versioned record schemas, rally CLI and integrity validator
  are implemented read-only. Synthetic fixture: 1 rally, 5 ball observations,
  3 events, 1 contact and 1 bounce; deterministic fingerprint verified.
- Real reference video and versioned Stage 3 track are unavailable locally:
  `REAL_REFERENCE_VIDEO_MISSING`. Stage 4 manual events, VFR timestamps, 2D court
  calibration and accepted serialized P1 fixture are inventoried and importable.
- Stage 1A court contract corrected: image-pixel polygon, court-meter coordinate
  system, `homography_pixel_to_court`, provenance and synthetic calibration status.
  Gate: `STAGE1A_COURT_CONTRACT_CORRECTED`.
- Real rally gate remains blocked by `REAL_REFERENCE_VIDEO_MISSING` and
  `REAL_STAGE3_BALL_TRACK_MISSING`; Stage 4/P1 fixtures do not substitute for a
  complete Stage 3 track and real video.

- Status: `P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED`.
- Upstream: `P1_TEN_FRAME_ACCEPTANCE_PASSED`.
- Contacts / Analytics records / schema-valid records: 5 / 5 / 5.
- Real timestamps, tracks, poses, court positions, wrist evidence: 5 each.
- Stage 4 informative labels / unavailable labels: 1 / 4.
- Unknown stroke dimensions: 23; hitting hand unknown for all five.
- Kinematics: null; blocker `APPROVED_STAGE5B_XYZ_REQUIRED`.
- Full rally: not validated.
- Cloud calls / GPU calls / spend: 0 / 0 / 0.
