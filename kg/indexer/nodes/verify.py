"""verify 노드 — 노드·엣지·커뮤니티 통계 집계 및 청크↔엔티티 매핑 무결성 검증."""
from __future__ import annotations

from ...store.neo4j_store import Neo4jStore


def verify_node(state: dict, store: Neo4jStore) -> dict:
    stats = store.stats()

    stats["entity_embeddings"] = store.query(
        "MATCH (e:__Entity__) WHERE e.embedding IS NOT NULL RETURN count(e) AS n"
    )[0]["n"]
    stats["chunk_embeddings"] = store.query(
        "MATCH (d:Document) WHERE d.embedding IS NOT NULL RETURN count(d) AS n"
    )[0]["n"]
    stats["orphan_entities"] = store.query(
        "MATCH (e:__Entity__) WHERE NOT (:Document)-[:MENTIONS]->(e) RETURN count(e) AS n"
    )[0]["n"]

    # 매핑 무결성 역추적 샘플 (엔티티 → 원문 청크)
    reverse_samples = store.query(
        "MATCH (d:Document)-[:MENTIONS]->(e:__Entity__) "
        "WITH e, collect(DISTINCT d.chunk_id)[..5] AS chunks, "
        "collect(DISTINCT d.source)[..5] AS sources "
        "RETURN e.id AS entity, chunks, sources "
        "ORDER BY size(chunks) DESC LIMIT 3"
    )

    checks = {
        "nodes>0": stats["nodes"] > 0,
        "relationships>0": stats["relationships"] > 0,
        "communities>0": stats["communities"] > 0,
        "mentions>0": stats["mentions"] > 0,
    }
    integrity_ok = all(checks.values())

    logs = [
        f"[verify] 통계: {stats}",
        f"[verify] 무결성 검사: {checks} => {'PASS' if integrity_ok else 'FAIL'}",
        f"[verify] 엔티티→청크 역추적 샘플 {len(reverse_samples)}건: {reverse_samples}",
    ]
    return {
        "stats": {
            **stats,
            "checks": checks,
            "integrity_ok": integrity_ok,
            "reverse_samples": reverse_samples,
        },
        "log": logs,
    }
