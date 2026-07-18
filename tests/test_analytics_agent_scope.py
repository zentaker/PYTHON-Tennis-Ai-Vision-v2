from scripts.check_analytics_agent_scope import allowed


def test_allowlist_accepts_owned_files_and_rejects_agent1_files():
    assert allowed("src/analytics/kinematics.py")
    assert allowed("tests/test_analytics_kinematics.py")
    assert not allowed("src/player_perception/pipeline.py")
    assert not allowed("pyproject.toml")
    assert not allowed("docs/agent/CURRENT_STATE.json")
