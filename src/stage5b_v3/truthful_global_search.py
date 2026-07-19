"""Small deterministic helpers for candidate-based shared-node search."""

from __future__ import annotations


def candidate_selection_changes_cost(base: dict, alternative: dict) -> bool:
    """Confirm that changing a node choice is observable in the global objective."""
    return base.get("candidate_ids") != alternative.get("candidate_ids") and base.get("total_cost") != alternative.get("total_cost")


def shared_node_consistency(hypothesis: dict, event_count: int = 10) -> bool:
    choices = hypothesis.get("candidate_ids", [])
    return len(choices) == event_count and len(set(choices)) == event_count
