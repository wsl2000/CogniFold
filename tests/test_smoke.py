"""Smoke tests for the cognifold package.

These exercise the core public API without requiring any LLM API keys or
network access, giving CI a real test suite to run.
"""

import cognifold
from cognifold import ConceptGraph, Node, NodeType


def test_package_exposes_public_api() -> None:
    for name in ("ConceptGraph", "Node", "NodeType", "Event", "CognifoldConfig"):
        assert hasattr(cognifold, name), f"missing public export: {name}"


def test_concept_graph_add_and_get_node() -> None:
    graph = ConceptGraph()
    node = Node(id="c1", type=NodeType.CONCEPT, data={"name": "test"})
    graph.add_node(node)

    assert graph.node_count == 1
    assert graph.get_node("c1").id == "c1"
    assert len(graph.get_all_nodes()) == 1


def test_concept_graph_missing_node_is_none() -> None:
    graph = ConceptGraph()
    assert graph.get_node_or_none("does-not-exist") is None
