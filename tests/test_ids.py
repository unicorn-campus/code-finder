"""ids 모듈 단위 테스트 — 안정적·재현 가능한 ID 규칙 검증."""
from kg.indexer.ids import chunk_id, entity_id, relation_id, slug


def test_slug_normalizes_case_and_symbols():
    assert slug("Neo4J") == slug("Neo4j") == "neo4j"
    assert slug("Chain-of-Thought") == "chain_of_thought"
    assert slug("  LangChain+Neo4j ") == "langchain_neo4j"


def test_slug_empty_fallback():
    assert slug("!!!") == "unknown"
    assert slug("") == "unknown"


def test_slug_preserves_hangul():
    # 한글이 제거되어 unknown으로 붕괴하면 안 됨 (엔티티 병합 방지)
    assert slug("가상환경") == "가상환경"
    assert slug("임베딩(Embedding)") == "임베딩_embedding"
    assert entity_id("가상환경") != entity_id("스케줄러")
    assert entity_id("가상환경") == "ent_가상환경"


def test_chunk_id_format():
    assert chunk_id(0) == "chunk_0"
    assert chunk_id(112) == "chunk_112"


def test_entity_id_idempotent():
    assert entity_id("ReAct") == "ent_react"
    assert entity_id("ent_react") == "ent_react"


def test_entity_id_dedup_across_casing():
    assert entity_id("Neo4J") == entity_id("Neo4j") == "ent_neo4j"


def test_relation_id_matches_testset_convention():
    # testset-graphrag 예시: rel_react_extends_cot 형태
    assert relation_id("ent_react", "EXTENDS", "ent_cot") == "rel_react_extends_cot"
    assert relation_id("ent_graphrag", "USES", "ent_neo4j") == "rel_graphrag_uses_neo4j"
