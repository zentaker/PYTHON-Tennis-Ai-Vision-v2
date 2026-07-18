# Baseline test dependencies

Execution: `uv run pytest` from the Analytics worktree at the hardening change set.

- Collected: 230
- Passed: 225
- Blocked by missing local artifacts: 5
- Analytics tests: 24 passed

| Blocked test | Immediate missing artifact | Owning area |
|---|---|---|
| `tests/test_modal_adapter.py::test_modal_adapter_is_import_safe_and_core_stays_provider_neutral` | `outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv` | `outputs/**` |
| `tests/test_modal_adapter.py::test_modal_contract_uses_one_dockerfile_and_guarded_limits` | `outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv` | `outputs/**` |
| `tests/test_modal_adapter.py::test_smoke_package_has_exactly_ten_verified_frames` | `.modal_smoke/nivel_a2_01/inputs/p1_smoke_manifest.json` | P1 Modal smoke package |
| `tests/test_vertical_reference_tool.py::test_self_test_passes_without_gpu_or_event_annotator_state` | `outputs/nivel_a2_01/stage_5a/camera_model.json` (the absent `data/clips/nivel_a2_01/reference_frame.png` is also reported before construction fails) | `outputs/**`, `data/**` |
| `tests/test_vertical_reference_tool.py::test_post_classification_uses_regulation_geometry` | `outputs/nivel_a2_01/stage_5a/camera_model.json` (the absent `data/clips/nivel_a2_01/reference_frame.png` is also reported before construction fails) | `outputs/**`, `data/**` |

The same five dependency failures existed before this hardening pass. Their tracebacks do not enter
`src/analytics`, and all 24 Analytics tests pass. Resolving them would require creating/copying files
in `outputs/**`, `data/**`, or the P1 Modal smoke workspace, all outside the Analytics allowlist.
No placeholder was created, no artifact was copied from Agent 1, and no upstream test was changed.
