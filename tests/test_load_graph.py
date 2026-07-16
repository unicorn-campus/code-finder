"""load_graph 노드 단위 테스트 — 적재·bare Document·벡터 인덱스 분기(mock store)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.documents import Document

from kg.indexer.config.settings import Settings
from kg.indexer.nodes.load_graph import load_graph_node


def _chunk(cid: str) -> Document:
    return Document(page_content="t", metadata={"id": cid, "chunk_id": cid, "source": "01.x"})


def _gd_for(cid: str):
    """load_graph가 참조하는 gd.source.metadata['chunk_id']만 갖춘 경량 가짜 GraphDocument."""
    return SimpleNamespace(source=SimpleNamespace(metadata={"chunk_id": cid}))


def test_load_graph_creates_bare_documents_for_uncovered_chunks():
    s = Settings()
    s.embedding.enabled = False
    store = MagicMock()
    store.stamp_relation_ids.return_value = 0
    store.rel_id_coverage.return_value = (5, 5)
    store.create_bare_documents.return_value = 2

    chunks = [_chunk("chunk_0"), _chunk("chunk_1"), _chunk("chunk_2")]
    gdocs = [_gd_for("chunk_0")]  # chunk_0만 엔티티 있음 → chunk_1,2는 bare 대상
    out = load_graph_node({"graph_documents": gdocs, "chunks": chunks}, s, store)

    store.add_graph_documents.assert_called_once()
    # 미커버 청크(chunk_1, chunk_2)만 bare Document로 적재
    (missing_arg,), _ = store.create_bare_documents.call_args
    assert {c.metadata["chunk_id"] for c in missing_arg} == {"chunk_1", "chunk_2"}
    assert any("엔티티없는 청크 Document 2건" in line for line in out["log"])


def test_load_graph_with_vector(monkeypatch):
    s = Settings()
    s.embedding.enabled = True
    store = MagicMock()
    store.stamp_relation_ids.return_value = 0
    store.rel_id_coverage.return_value = (3, 3)
    store.create_bare_documents.return_value = 0
    store.create_vector_indexes.return_value = {"entity_vector": 10, "chunk_vector": 4}
    monkeypatch.setattr(
        "kg.indexer.nodes.load_graph.build_embeddings", lambda settings: object()
    )
    out = load_graph_node({"graph_documents": [_gd_for("chunk_0")], "chunks": [_chunk("chunk_0")]}, s, store)
    store.create_vector_indexes.assert_called_once()
    assert any("벡터 인덱스" in line for line in out["log"])
