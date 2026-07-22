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
- Recovery found a corresponding external `nivel_a2_01` video and local ignored
  Stage 3 track. SHA, frame range, VFR timestamps, Stage 4 events and calibration
  align; surface metadata is unavailable and remains `unknown`.
- Real candidate built deterministically: 1 rally, 527 observations, 10 events,
  4 contacts and 5 bounces. Session/rally status is `partial` because the source
  track contains non-visible observations. Gate:
  `REAL_SINGLE_RALLY_BUNDLE_CANDIDATE_PENDING_HUMAN_AUDIT`.
- Synthetic importer acceptance gate passed:
  `CORE_STAGE1A_SYNTHETIC_IMPORT_GATE_PASSED`. Real evidence gate remains
  `REAL_SINGLE_RALLY_EVIDENCE_GATE_BLOCKED`; no real bundle is claimed and the
  detailed schemas remain candidates pending real-asset audit.

- Status: `P1_ANALYTICS_FUNCTIONAL_WIRING_PASSED`.
- Upstream: `P1_TEN_FRAME_ACCEPTANCE_PASSED`.
- Contacts / Analytics records / schema-valid records: 5 / 5 / 5.
- Real timestamps, tracks, poses, court positions, wrist evidence: 5 each.
- Stage 4 informative labels / unavailable labels: 1 / 4.
- Unknown stroke dimensions: 23; hitting hand unknown for all five.
- Kinematics: null; blocker `APPROVED_STAGE5B_XYZ_REQUIRED`.
- Full rally: not validated.
- Cloud calls / GPU calls / spend: 0 / 0 / 0.
- Stage 1B final evidence patch: alignment is derived (22 checks passed), not
  hardcoded. The six selected asset SHA-256 values are published without paths.
- Reports now include ffprobe side-data rotation, encoded/canonical dimensions,
  timestamp and track audits, calibration audit, event-level alignment and
  sanitized asset hashes. The track preview is segmented around missing frames;
  smoothed segments are solid and interpolated segments are dashed.
- Event alignment: 10 exact frames, 8 smoothed/detected and 2 interpolated;
  missing positions 0; maximum timestamp delta 0 seconds.
- New gate state: `STAGE1B_BUNDLE_INTEGRITY_PASSED`,
  `STAGE1B_REAL_ASSET_PROVENANCE_CONFIRMED`,
  `STAGE1B_ALIGNMENT_EVIDENCE_PATCH_IMPLEMENTED`, with
  `REAL_SINGLE_RALLY_INTEGRATION_GATE_PENDING_FINAL_AUDIT` remaining.
- Full local suite: 321 passed; the five remaining failures are
  `tests/test_modal_adapter.py::test_modal_adapter_is_import_safe_and_core_stays_provider_neutral`,
  `tests/test_modal_adapter.py::test_modal_contract_uses_one_dockerfile_and_guarded_limits`,
  `tests/test_modal_adapter.py::test_smoke_package_has_exactly_ten_verified_frames`,
  `tests/test_vertical_reference_tool.py::test_self_test_passes_without_gpu_or_event_annotator_state`,
  and `tests/test_vertical_reference_tool.py::test_post_classification_uses_regulation_geometry`;
  each requires ignored local Stage 3/5A or Modal smoke assets absent from this worktree.
- Fixture publication safety patch implemented: `--fixture-output` now accepts
  only the exact Stage 1B fixture path, rejects traversal/external/root/fixture
  variants and symlink segments, and uses owned staging with atomic replacement
  and rollback. A failed alignment gate is blocked before publication.
- Bad video SHA was exercised through `evaluate_asset_alignment` with an all-zero
  expected SHA; the gate failed, `video_sha_expected` was a blocker, and the
  publication helper rejected the failed result. Bundle fingerprint remained
  `1c0bd683ea349b682be852d02fe7917bea181d8daad42aa97737578d8ceb8009`.
- Gates: `STAGE1B_REAL_EVIDENCE_AUDIT_PASSED`,
  `REAL_SINGLE_RALLY_DATA_GATE_PASSED`,
  `STAGE1B_FIXTURE_PUBLICATION_SAFETY_PATCH_IMPLEMENTED`, and
  `REAL_SINGLE_RALLY_MERGE_GATE_PENDING_FINAL_RELEASE_AUDIT`.
- Stage 1B release accepted: `STAGE1B_RELEASE_AUDIT_PASSED` and
  `REAL_SINGLE_RALLY_INTEGRATION_GATE_PASSED`. The first bundle derived from
  real assets is accepted; source video remains external, the track is from the
  existing Stage 3 output, and events are from existing Stage 4 annotations.
  Session/rally remain `partial`, surface remains `unknown`, calibration remains
  approved 2D, and no 3D claim or inference was made. TennisWebAI can consume
  the approved fixture through Stage 0B.
- The five local asset-dependent tests remain separate debt and are not Stage 1B
  failures.
