"""Neo4j 그래프 스토어 연동·스키마 관리.

- 제약조건(멱등성·무결성): __Entity__.id / Document.id / Community.id 유니크
- 적재: langchain_neo4j Neo4jGraph.add_graph_documents (청크+엔티티+MENTIONS+관계)
- 관계 ID 안정 부여: testset gt_relations 일치용 rel_id 스탬프
- 벡터 인덱스: Neo4jVector.from_existing_graph (엔티티·청크 임베딩)
- 통계: 노드·엣지·커뮤니티·MENTIONS 건수 집계
"""
from __future__ import annotations

from typing import Optional

from langchain_neo4j import Neo4jGraph, Neo4jVector

from ..indexer.config.settings import EmbeddingConfig, Neo4jConfig


class Neo4jStore:
    """Neo4jGraph 래퍼."""

    def __init__(self, cfg: Neo4jConfig):
        self.cfg = cfg
        self.graph = Neo4jGraph(
            url=cfg.uri,
            username=cfg.username,
            password=cfg.password,
            database=cfg.database,
            refresh_schema=False,
        )

    # ------------------------------------------------------------------ #
    # 제약조건 (멱등성·무결성)
    # ------------------------------------------------------------------ #
    def ensure_constraints(self) -> None:
        stmts = [
            "CREATE CONSTRAINT entity_id IF NOT EXISTS "
            "FOR (e:__Entity__) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT document_id IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT community_id IF NOT EXISTS "
            "FOR (c:Community) REQUIRE c.id IS UNIQUE",
        ]
        for s in stmts:
            self.graph.query(s)

    # ------------------------------------------------------------------ #
    # 적재
    # ------------------------------------------------------------------ #
    def add_graph_documents(
        self, graph_documents, include_source: bool = True, base_entity_label: bool = True
    ) -> None:
        self.graph.add_graph_documents(
            graph_documents,
            include_source=include_source,
            baseEntityLabel=base_entity_label,
        )

    def stamp_relation_ids(self) -> int:
        """엔티티 간 관계에 안정 rel_id 부여. 예: rel_<src>_<type>_<tgt>."""
        res = self.graph.query(
            "MATCH (a:__Entity__)-[r]->(b:__Entity__) "
            "WHERE r.rel_id IS NULL AND a.id IS NOT NULL AND b.id IS NOT NULL "
            "SET r.rel_id = 'rel_' + substring(a.id, 4) + '_' + "
            "toLower(type(r)) + '_' + substring(b.id, 4) "
            "RETURN count(r) AS n"
        )
        return res[0]["n"] if res else 0

    def rel_id_coverage(self) -> tuple[int, int]:
        """엔티티 간 관계의 rel_id 커버리지 (rel_id 보유 수, 전체 수)."""
        res = self.graph.query(
            "MATCH (:__Entity__)-[r]->(:__Entity__) "
            "RETURN count(r.rel_id) AS with_id, count(r) AS total"
        )
        row = res[0] if res else {"with_id": 0, "total": 0}
        return row["with_id"], row["total"]

    # ------------------------------------------------------------------ #
    # 조회·초기화
    # ------------------------------------------------------------------ #
    def create_bare_documents(self, chunks) -> int:
        """엔티티가 추출되지 않은 청크도 Document 노드로 적재(검색 사각지대 방지).

        langchain_neo4j의 include_source 동작(`d.text=page_content`, `d += metadata`)과 동일하게
        text·chunk_id·source·heading_path를 기록함. chunk_id 키로 MERGE하여 멱등적임.
        """
        if not chunks:
            return 0
        rows = [
            {
                "id": c.metadata["chunk_id"],
                "text": c.page_content,
                "chunk_id": c.metadata["chunk_id"],
                "source": c.metadata.get("source"),
                "heading_path": c.metadata.get("heading_path"),
            }
            for c in chunks
        ]
        self.graph.query(
            "UNWIND $rows AS row "
            "MERGE (d:Document {id: row.id}) "
            "SET d.text = row.text, d.chunk_id = row.chunk_id, "
            "d.source = row.source, d.heading_path = row.heading_path",
            {"rows": rows},
        )
        return len(rows)

    def existing_chunk_ids(self) -> set:
        """이미 Document 노드로 적재된 chunk_id 집합."""
        rows = self.graph.query("MATCH (d:Document) WHERE d.chunk_id IS NOT NULL RETURN d.chunk_id AS cid")
        return {r["cid"] for r in rows}

    def query(self, cypher: str, params: Optional[dict] = None):
        return self.graph.query(cypher, params or {})

    def wipe(self) -> None:
        """그래프 전체 삭제(--reset)."""
        self.graph.query("MATCH (n) DETACH DELETE n")

    def _count(self, cypher: str) -> int:
        res = self.graph.query(cypher)
        return res[0]["n"] if res else 0

    # ------------------------------------------------------------------ #
    # 벡터 인덱스 (Local 검색·NDCG)
    # ------------------------------------------------------------------ #
    def create_vector_indexes(self, emb_cfg: EmbeddingConfig, embeddings) -> dict:
        """엔티티·청크 벡터 인덱스 생성. 임베딩 없는 노드만 자동 임베딩됨."""
        common = dict(
            embedding=embeddings,
            url=self.cfg.uri,
            username=self.cfg.username,
            password=self.cfg.password,
            database=self.cfg.database,
            embedding_node_property="embedding",
        )
        # 엔티티 벡터
        Neo4jVector.from_existing_graph(
            node_label="__Entity__",
            text_node_properties=["id", "name", "description"],
            index_name="entity_vector",
            **common,
        )
        # 청크(원문) 벡터
        Neo4jVector.from_existing_graph(
            node_label="Document",
            text_node_properties=["text"],
            index_name="chunk_vector",
            **common,
        )
        return {
            "entity_vector": self._count(
                "MATCH (e:__Entity__) WHERE e.embedding IS NOT NULL RETURN count(e) AS n"),
            "chunk_vector": self._count(
                "MATCH (d:Document) WHERE d.embedding IS NOT NULL RETURN count(d) AS n"),
        }

    # ------------------------------------------------------------------ #
    # 통계
    # ------------------------------------------------------------------ #
    def stats(self) -> dict:
        return {
            "nodes": self._count("MATCH (n) RETURN count(n) AS n"),
            "entities": self._count("MATCH (e:__Entity__) RETURN count(e) AS n"),
            "documents": self._count("MATCH (d:Document) RETURN count(d) AS n"),
            "communities": self._count("MATCH (c:Community) RETURN count(c) AS n"),
            "relationships": self._count("MATCH ()-[r]->() RETURN count(r) AS n"),
            "mentions": self._count(
                "MATCH (:Document)-[r:MENTIONS]->(:__Entity__) RETURN count(r) AS n"),
            "entity_rels": self._count(
                "MATCH (:__Entity__)-[r]->(:__Entity__) RETURN count(r) AS n"),
        }
