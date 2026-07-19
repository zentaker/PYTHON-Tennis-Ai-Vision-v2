from __future__ import annotations

from pathlib import Path

from src.stage5b_v3.event_node_graph import (
    allocate_event_and_interior_observations,
    build_shared_graph,
)
from src.stage5b_v3.event_topology import canonical_timeline, load_observations

ROOT = Path(__file__).parents[1]


def test_shared_nodes_and_event_observation_allocation() -> None:
    timeline = canonical_timeline(ROOT / "data/clips/nivel_a2_01/manual_annotation.json")
    contacts = {row["event_id"]: [[0, 0, 1]] for row in timeline if row["event_type"] == "contact"}
    bounces = {row["event_id"]: [[0, 0, 0]] for row in timeline if row["event_type"] == "bounce"}
    graph = build_shared_graph(timeline, contacts, bounces)
    assert len(graph["nodes"]) == 10 and len(graph["edges"]) == 9
    middle = graph["nodes"][1]
    assert middle["incoming_edge"] and middle["outgoing_edge"]
    assert graph["edges"][0]["end_node_reference"] == graph["edges"][1]["start_node_reference"]
    allocation = allocate_event_and_interior_observations(
        timeline, load_observations(ROOT / "tests/fixtures/stage5b_v3/smoothed_trajectory_real.csv")
    )
    assert allocation["contact_node_observations"] == 5
    assert allocation["bounce_node_observations"] == 5
    assert allocation["duplicated_observations"] == 0
