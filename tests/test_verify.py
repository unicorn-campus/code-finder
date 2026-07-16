"""verify 노드 단위 테스트 — 통계·무결성 판정(mock store)."""
from unittest.mock import MagicMock

from kg.indexer.nodes.verify import verify_node


def _store_ok() -> MagicMock:
    store = MagicMock()
    store.stats.return_value = {
        "nodes": 10, "entities": 6, "documents": 3, "communities": 2,
        "relationships": 8, "mentions": 9, "entity_rels": 4,
    }
    store.query.side_effect = [
        [{"n": 6}],   # entity_embeddings
        [{"n": 3}],   # chunk_embeddings
        [{"n": 0}],   # orphan_entities
        [{"entity": "ent_x", "chunks": ["chunk_0"], "sources": ["01.x"]}],  # reverse samples
    ]
    return store


def test_verify_integrity_pass():
    out = verify_node({}, _store_ok())
    stats = out["stats"]
    assert stats["integrity_ok"] is True
    assert stats["checks"]["mentions>0"] is True
    assert len(stats["reverse_samples"]) == 1
    assert stats["entity_embeddings"] == 6


def test_verify_integrity_fail_when_no_community():
    store = MagicMock()
    store.stats.return_value = {
        "nodes": 5, "entities": 3, "documents": 2, "communities": 0,
        "relationships": 4, "mentions": 3, "entity_rels": 2,
    }
    store.query.side_effect = [[{"n": 0}], [{"n": 0}], [{"n": 1}], []]
    out = verify_node({}, store)
    assert out["stats"]["integrity_ok"] is False
    assert out["stats"]["checks"]["communities>0"] is False
