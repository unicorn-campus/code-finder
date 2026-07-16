"""교재 GraphRAG 리트리버 설정.

- 인덱서(`kg/indexer`)가 만든 Neo4j 그래프·벡터 인덱스(entity_vector·chunk_vector)를 소비함.
- Neo4j·임베딩 설정은 인덱서 설정을 재사용(단일 출처).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from kg.indexer.config.settings import EmbeddingConfig, Neo4jConfig


@dataclass
class GraphRetrieverConfig:
    """GraphRAG 리트리버 파라미터."""

    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    # 벡터 인덱스명(인덱서 산출)
    entity_index: str = "entity_vector"
    chunk_index: str = "chunk_vector"

    # Local: 엔티티·청크 후보 수
    entity_k: int = 8
    chunk_k: int = 8
    rels_per_entity: int = 8

    # Global: 커뮤니티 요약 수
    community_n: int = 6
    # Global에서도 근거 청크 일부 포함
    global_chunk_k: int = 4


def load_graph_retriever_config() -> GraphRetrieverConfig:
    return GraphRetrieverConfig()
