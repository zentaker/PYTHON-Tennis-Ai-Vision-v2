# Parallel integration safety

Analytics uses `/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2-analytics` on
`agent/analytics-stroke-speed-foundation`; P1 uses a different worktree, branch, and Git index. The
allowlist confines modifications to Analytics-owned source, configuration, tests, documentation,
scope checker, track records, and one workflow. Upstream contracts are read-only.

The scope gate compares committed, staged, unstaged, and untracked paths with the validated base SHA.
It rejects the original P1 worktree and any shared/global edit, including `pyproject.toml` and
`docs/agent/CURRENT_STATE.json`. Integration should later occur on `agent/integration-p1-analytics`
after independent review; this task does not create that branch.
