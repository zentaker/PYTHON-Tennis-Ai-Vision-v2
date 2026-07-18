# A1 Stroke & Ball Analytics

- Agent: stroke-ball-analytics
- Mission: versioned taxonomy, contracts, deterministic kinematics, and integration boundaries
- Worktree: `/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2-analytics`
- Branch: `agent/analytics-stroke-speed-foundation`
- Base SHA: `e81949bc01cbd2adfca12bd5b3a6a28c3e792fea`
- Allowed: `src/analytics/**`, `docs/analytics/**`, `config/analytics/**`, Analytics tests and
  fixtures, scope checker, A1 track files, and the Analytics workflow
- Forbidden: Player Perception, events, video, project, infrastructure, containers, provider config,
  data, outputs, models, global coordination state, roadmap/readmes, dependency locks, and Agent 1 files
- Upstream inputs: Stage 4 manual events read-only; future P1/P2/approved Stage 5B contracts
- Outputs: typed records, schemas, conservative adapter, deterministic estimators, documentation
- Dependencies: Python, NumPy; no external provider, GPU, or OpenMMLab dependency
- Limitations: no real-video validation, classifier, spin/RPM measurement, or Stage 5B implementation
- Decisions: independent dimensions; unknown by default; planar speed explicitly not 3D
- State: local scope gate passed; publication gate pending
- Handoff: see `A1_ANALYTICS_HANDOFF.md`
