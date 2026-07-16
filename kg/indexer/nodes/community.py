"""community 노드 — 커뮤니티 탐지 + LLM 요약 (주제 요약형 Global 검색 지원용).

Neo4j Community Edition에 GDS가 없으므로 커뮤니티 탐지는 Python측(networkx Louvain)에서 수행하고
결과(community 속성)를 그래프에 write-back함. 커뮤니티별 LLM 요약을 Community 노드로 적재함.
재현성: Louvain seed 고정.
"""
from __future__ import annotations

import networkx as nx
from langchain_core.prompts import ChatPromptTemplate

from ...store.neo4j_store import Neo4jStore
from ..config.settings import Settings

# 시스템/유저 프롬프트 명확히 분리
_SUMMARY_SYSTEM = (
    "당신은 지식그래프 커뮤니티 요약 전문가임. 주어진 개념 목록과 근거 문맥만을 바탕으로 "
    "해당 커뮤니티가 공통으로 다루는 주제를 명사체로 2~3문장 요약함. "
    "근거 없는 내용은 절대 추가하지 않음."
)
_SUMMARY_USER = (
    "커뮤니티 개념 목록:\n{members}\n\n근거 문맥(발췌):\n{context}\n\n"
    "위 개념들이 공통으로 형성하는 주제를 명사체 2~3문장으로 요약하라."
)


def _build_nx(edges: list[dict]) -> nx.Graph:
    g = nx.Graph()
    for e in edges:
        g.add_edge(e["a"], e["b"])
    return g


def detect_communities(store: Neo4jStore, seed: int) -> dict[str, list[str]]:
    """엔티티 간 관계 그래프에 Louvain 적용 → {comm_id: [entity_id,...]}."""
    edges = store.query(
        "MATCH (a:__Entity__)-[]->(b:__Entity__) "
        "WHERE a.id IS NOT NULL AND b.id IS NOT NULL AND a.id <> b.id "
        "RETURN a.id AS a, b.id AS b"
    )
    g = _build_nx(edges)
    if g.number_of_nodes() == 0:
        return {}
    communities = nx.community.louvain_communities(g, seed=seed)
    return {f"comm_{k}": sorted(members) for k, members in enumerate(communities)}


def _summarize(chain, members: list[str], context: str) -> str:
    try:
        resp = chain.invoke(
            {"members": ", ".join(members[:40]), "context": context or "(문맥 없음)"}
        )
        return getattr(resp, "content", str(resp)).strip()
    except Exception as e:  # 요약 실패해도 파이프라인은 지속
        return f"(요약 실패: {type(e).__name__})"


def community_node(state: dict, settings: Settings, store: Neo4jStore, llm) -> dict:
    mapping = detect_communities(store, settings.community_seed)
    if not mapping:
        return {"log": ["[community] 엔티티 간 관계가 없어 커뮤니티 탐지 생략"]}

    chain = ChatPromptTemplate.from_messages(
        [("system", _SUMMARY_SYSTEM), ("user", _SUMMARY_USER)]
    ) | llm

    created = 0
    for comm_id, members in mapping.items():
        store.query(
            "UNWIND $members AS mid MATCH (e:__Entity__ {id: mid}) SET e.community = $cid",
            {"members": members, "cid": comm_id},
        )
        rows = store.query(
            "MATCH (e:__Entity__) WHERE e.id IN $members "
            "OPTIONAL MATCH (d:Document)-[:MENTIONS]->(e) "
            "RETURN collect(DISTINCT coalesce(e.name, e.id)) AS names, "
            "collect(DISTINCT d.text)[..3] AS ctx",
            {"members": members},
        )
        names = rows[0]["names"] if rows else members
        ctx = "\n---\n".join(t for t in (rows[0]["ctx"] if rows else []) if t)[:3000]
        summary = _summarize(chain, names, ctx)
        store.query(
            "MERGE (c:Community {id: $cid}) "
            "SET c.summary = $summary, c.size = $size, c.members = $members "
            "WITH c UNWIND $members AS mid "
            "MATCH (e:__Entity__ {id: mid}) MERGE (e)-[:IN_COMMUNITY]->(c)",
            {"cid": comm_id, "summary": summary, "size": len(members), "members": members},
        )
        created += 1

    return {
        "log": [
            f"[community] 커뮤니티 {created}개 탐지·요약·적재 "
            f"(networkx Louvain, seed={settings.community_seed})"
        ]
    }
