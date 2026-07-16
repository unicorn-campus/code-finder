"""통합 테스트 — 실제 Neo4j·Groq·OpenAI 호출.

기본 실행에서 제외됨(`pytest.ini`의 addopts=-m "not integration").
실행: `pytest -m integration`
전제: code-finder-neo4j 컨테이너 기동 + .env의 유효 GROQ/OPENAI 키.
"""
import pytest

from kg.indexer.config.settings import load_settings
from kg.indexer.llm import build_llm
from kg.indexer.nodes.extract import build_transformer, extract_node
from kg.store.neo4j_store import Neo4jStore

pytestmark = pytest.mark.integration


def test_neo4j_connection_and_stats():
    settings = load_settings()
    store = Neo4jStore(settings.neo4j)
    stats = store.stats()
    assert set(["nodes", "entities", "documents", "relationships"]).issubset(stats)


def test_reverse_lookup_returns_results():
    """인덱싱이 1회 이상 수행된 상태에서 엔티티→청크 역추적이 동작함."""
    settings = load_settings()
    store = Neo4jStore(settings.neo4j)
    rows = store.query(
        "MATCH (d:Document)-[:MENTIONS]->(e:__Entity__) "
        "RETURN e.id AS entity, collect(DISTINCT d.chunk_id)[..5] AS chunks LIMIT 3"
    )
    assert len(rows) >= 1
    assert all(r["chunks"] for r in rows)


def test_live_extract_one_chunk():
    """Groq gpt-oss-120b로 실제 청크 1건 추출 → 노드/관계 반환."""
    from langchain_core.documents import Document

    settings = load_settings()
    llm = build_llm(settings)
    transformer = build_transformer(llm, settings.schema())
    chunk = Document(
        page_content=(
            "GraphRAG는 기존 Vector RAG의 멀티홉 추론 한계를 확장하는 기법이다. "
            "GraphRAG는 Neo4j를 사용하여 지식그래프를 구축한다."
        ),
        metadata={"id": "chunk_it", "chunk_id": "chunk_it", "source": "it"},
    )
    out = extract_node({"chunks": [chunk]}, settings, transformer)
    assert len(out["graph_documents"]) == 1
    assert out["graph_documents"][0].nodes
