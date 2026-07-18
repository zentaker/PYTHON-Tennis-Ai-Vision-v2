# P1 + Analytics Integration Report

The P1 runtime at `a15b91fadb2b0b1badb6ce1009896458b3dac718` and the Analytics foundation at `bab71a7b49e2b8de7aeccef61eb9836a3722f56e` share base `e81949bc01cbd2adfca12bd5b3a6a28c3e792fea`. They were combined by merge commit `f652be17d8c8fcf9165b65a725d4e8730cb62916` without conflicts.

Validation covers combined Analytics, Lightning offline, integration, clean baseline, Ruff, compileall, Replit smoke, serialized schema instances, and the integration scope checker. Five baseline tests are explicitly `ASSET_DEPENDENT_NOT_EXECUTED`:

- `tests/test_modal_adapter.py::test_modal_adapter_is_import_safe_and_core_stays_provider_neutral`
- `tests/test_modal_adapter.py::test_modal_contract_uses_one_dockerfile_and_guarded_limits`
- `tests/test_modal_adapter.py::test_smoke_package_has_exactly_ten_verified_frames`
- `tests/test_vertical_reference_tool.py::test_self_test_passes_without_gpu_or_event_annotator_state`
- `tests/test_vertical_reference_tool.py::test_post_classification_uses_regulation_geometry`

There is no functional wiring between P1 outputs and Analytics. Future inputs are `player_tracks.csv`, `player_pose.jsonl`, `player_court_positions.csv`, `contact_audit.json`, and approved Stage 5B XYZ. The next real gate is the ten-frame P1 smoke. Lightning remains unconfigured and offline; cloud calls, GPU calls, and spend are zero.
