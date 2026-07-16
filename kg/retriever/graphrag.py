"""교재 GraphRAG 리트리버 (§3.5) — Local / Global / Hybrid.

인덱서 산출 그래프를 소비:
- __Entity__(id·name·description·embedding·community), Document(chunk_id·text·source·embedding),
  Community(id·summary·size·members), 엔티티 간 관계(rel_id·type), MENTIONS.
- 벡터 인덱스: entity_vector(__Entity__), chunk_vector(Document).

모드별 검색:
- Local : chunk_vector로 랭킹 청크 + entity_vector로 엔티티·1홉 관계 확장(특정 개체 중심)
- Global: 관련 엔티티의 커뮤니티 요약 집계(주제 요약형) + 근거 청크 일부
- Hybrid: Local + Global 통합(복합·모호)
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from langchain_openai import OpenAIEmbeddings

from app.common.logging_utils import get_logger
from kg.store.neo4j_store import Neo4jStore
from .config import GraphRetrieverConfig, load_graph_retriever_config
from .mode_select import Mode, select_mode

log = get_logger()


class GraphRAGRetriever:
    """교재 지식그래프 리트리버."""

    def __init__(self, cfg: Optional[GraphRetrieverConfig] = None):
        self.cfg = cfg or load_graph_retriever_config()
        self.store = Neo4jStore(self.cfg.neo4j)
        self.embeddings = OpenAIEmbeddings(
            model=self.cfg.embedding.model, api_key=self.cfg.embedding.api_key)

    # ------------------------------------------------------------------ #
    # 하위 조회 (Cypher)
    # ------------------------------------------------------------------ #
    def _rank_chunks(self, qvec: list[float], k: int) -> list[dict]:
        """chunk_vector 유사도 상위 청크(랭킹 — NDCG·근거 문맥용)."""
        rows = self.store.query(
            "CALL db.index.vector.queryNodes($idx, $k, $qvec) YIELD node, score "
            "WHERE node.chunk_id IS NOT NULL "
            "RETURN node.chunk_id AS chunk_id, node.text AS text, node.source AS source, "
            "node.heading_path AS heading_path, score ORDER BY score DESC",
            {"idx": self.cfg.chunk_index, "k": k, "qvec": qvec},
        )
        return [dict(r) for r in rows]

    def _match_entities(self, qvec: list[float], k: int) -> list[dict]:
        """entity_vector 유사도 상위 엔티티 + 1홉 관계."""
        rows = self.store.query(
            "CALL db.index.vector.queryNodes($idx, $k, $qvec) YIELD node AS e, score "
            "OPTIONAL MATCH (e)-[r]->(nb:__Entity__) "
            "WITH e, score, collect(DISTINCT {rel_id: r.rel_id, type: type(r), "
            "  source: e.id, target: nb.id, target_name: nb.name})[0..$rk] AS rels "
            "RETURN e.id AS id, e.name AS name, coalesce(e.description,'') AS description, "
            "e.community AS community, score, rels ORDER BY score DESC",
            {"idx": self.cfg.entity_index, "k": k, "qvec": qvec, "rk": self.cfg.rels_per_entity},
        )
        return [dict(r) for r in rows]

    def _communities(self, community_ids: list[str], n: int) -> list[dict]:
        """엔티티가 속한 커뮤니티 요약(주제 요약형 Global 근거)."""
        if not community_ids:
            return []
        rows = self.store.query(
            "MATCH (c:Community) WHERE c.id IN $ids AND c.summary IS NOT NULL "
            "RETURN c.id AS id, c.summary AS summary, c.size AS size "
            "ORDER BY c.size DESC LIMIT $n",
            {"ids": community_ids, "n": n},
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # 모드별 검색
    # ------------------------------------------------------------------ #
    def retrieve(self, query: str, mode: Optional[Mode] = None) -> dict:
        """GraphRAG 검색. mode 미지정 시 질의 신호로 자동 선택."""
        mode = mode or select_mode(query)
        qvec = self.embeddings.embed_query(query)

        entities: list[dict] = []
        chunks: list[dict] = []
        relations: list[dict] = []
        communities: list[dict] = []

        if mode in ("local", "hybrid"):
            chunks = self._rank_chunks(qvec, self.cfg.chunk_k)
            ents = self._match_entities(qvec, self.cfg.entity_k)
            for e in ents:
                entities.append({"id": e["id"], "name": e.get("name"),
                                 "description": e.get("description", ""), "score": e["score"]})
                for r in (e.get("rels") or []):
                    if r.get("target"):
                        relations.append(r)

        if mode in ("global", "hybrid"):
            if not entities:
                ents = self._match_entities(qvec, self.cfg.entity_k)
                entities = [{"id": e["id"], "name": e.get("name"),
                             "description": e.get("description", ""), "score": e["score"]} for e in ents]
            rows = self.store.query(
                "MATCH (e:__Entity__) WHERE e.id IN $ids AND e.community IS NOT NULL "
                "RETURN DISTINCT e.community AS c",
                {"ids": [e["id"] for e in entities]},
            )
            comm_ids = [r["c"] for r in (rows or [])]
            communities = self._communities(comm_ids, self.cfg.community_n)
            if not chunks:
                chunks = self._rank_chunks(qvec, self.cfg.global_chunk_k)

        # 관계 중복 제거(rel_id 기준)
        seen, uniq_rels = set(), []
        for r in relations:
            key = r.get("rel_id") or f"{r.get('source')}|{r.get('type')}|{r.get('target')}"
            if key not in seen:
                seen.add(key)
                uniq_rels.append(r)

        log.info("[tool] textbook_search(mode=%s): entities=%d chunks=%d rels=%d communities=%d",
                 mode, len(entities), len(chunks), len(uniq_rels), len(communities))
        return {
            "mode": mode,
            "entities": entities,
            "chunks": chunks,
            "relations": uniq_rels,
            "communities": communities,
        }


@lru_cache(maxsize=1)
def get_graph_retriever() -> GraphRAGRetriever:
    """프로세스 단위 싱글턴."""
    return GraphRAGRetriever()
