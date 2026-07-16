"""community 노드 단위 테스트 — networkx 그래프 구성·Louvain 탐지(mock store)."""
from unittest.mock import MagicMock

from kg.indexer.nodes.community import _build_nx, detect_communities


def test_build_nx():
    g = _build_nx([{"a": "x", "b": "y"}, {"a": "y", "b": "z"}])
    assert g.number_of_nodes() == 3
    assert g.number_of_edges() == 2


def test_detect_communities_two_clusters():
    store = MagicMock()
    # 두 밀집 클러스터: (1-2-3), (4-5-6)
    store.query.return_value = [
        {"a": "1", "b": "2"}, {"a": "2", "b": "3"}, {"a": "1", "b": "3"},
        {"a": "4", "b": "5"}, {"a": "5", "b": "6"}, {"a": "4", "b": "6"},
    ]
    mapping = detect_communities(store, seed=42)
    assert len(mapping) >= 2
    members = set().union(*mapping.values())
    assert members == {"1", "2", "3", "4", "5", "6"}


def test_detect_communities_empty():
    store = MagicMock()
    store.query.return_value = []
    assert detect_communities(store, seed=42) == {}
