"""split 노드 단위 테스트 — 헤더 분할·크기 보정·chunk_id 결정성."""
from kg.indexer.config.settings import Settings
from kg.indexer.nodes.split import _heading_path, split_documents, split_node


def test_heading_path():
    assert _heading_path({"h1": "A", "h3": "C"}) == "A > C"
    assert _heading_path({}) == ""


def test_split_assigns_sequential_chunk_ids():
    s = Settings()
    s.split.chunk_size = 100
    s.split.chunk_overlap = 0
    raw = [{"source": "01.x", "path": "/x", "text": "# 제목\n" + ("가나다 " * 80)}]
    chunks = split_documents(raw, s)
    ids = [c.metadata["chunk_id"] for c in chunks]
    assert ids == [f"chunk_{i}" for i in range(len(chunks))]
    assert all(c.metadata["source"] == "01.x" for c in chunks)
    # Document 노드 MERGE 키(id)와 chunk_id 일치
    assert all(c.metadata["id"] == c.metadata["chunk_id"] for c in chunks)
    assert "제목" in chunks[0].metadata["heading_path"]


def test_split_is_deterministic():
    s = Settings()
    raw = [{"source": "01.x", "path": "/x", "text": "# H\n" + ("본문내용 " * 60)}]
    a = [c.page_content for c in split_documents(raw, s)]
    b = [c.page_content for c in split_documents(raw, s)]
    assert a == b


def test_split_node_max_chunks():
    s = Settings()
    s.split.chunk_size = 50
    s.split.chunk_overlap = 0
    raw = [{"source": "01.x", "path": "/x", "text": "# H\n" + ("단어 " * 100)}]
    out = split_node({"raw_docs": raw, "max_chunks": 3}, s)
    assert len(out["chunks"]) == 3
    assert out["log"]


def test_split_node_only_chunk_ids():
    # 전역 chunk_id를 유지한 채 지정 청크만 선택(--retry-failed)
    s = Settings()
    s.split.chunk_size = 50
    s.split.chunk_overlap = 0
    raw = [{"source": "01.x", "path": "/x", "text": "# H\n" + ("단어 " * 100)}]
    out = split_node({"raw_docs": raw, "only_chunk_ids": ["chunk_2", "chunk_5"]}, s)
    ids = {c.metadata["chunk_id"] for c in out["chunks"]}
    assert ids == {"chunk_2", "chunk_5"}
