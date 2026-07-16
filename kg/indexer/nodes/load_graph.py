"""load_graph 노드 — Neo4j 적재.

- 제약조건 보장 → add_graph_documents(원문 청크 + 엔티티 + MENTIONS + 개념 간 관계)
- include_source=True: Document 노드 생성 + MENTIONS 엣지 (청크↔엔티티 역추적 보장)
- baseEntityLabel=True: 엔티티에 __Entity__ 라벨 부여 (병합·조회 성능)
- 재실행 멱등성: 동일 id는 MERGE 기준으로 갱신
- 관계 rel_id 스탬프 후 벡터 인덱스(옵션) 생성
"""
from __future__ import annotations

from ...store.neo4j_store import Neo4jStore
from ..config.settings import Settings
from ..llm import build_embeddings


def load_graph_node(state: dict, settings: Settings, store: Neo4jStore) -> dict:
    gdocs = state.get("graph_documents", [])
    chunks = state.get("chunks", [])
    logs: list[str] = []

    store.ensure_constraints()
    if gdocs:
        store.add_graph_documents(gdocs, include_source=True, base_entity_label=True)

    # 엔티티가 추출되지 않은 청크(빈 추출·실패)도 Document 노드로 적재 → 검색 사각지대 방지
    covered = {
        gd.source.metadata.get("chunk_id")
        for gd in gdocs
        if getattr(gd, "source", None) is not None
    }
    missing = [c for c in chunks if c.metadata["chunk_id"] not in covered]
    bare = store.create_bare_documents(missing)

    new_ids = store.stamp_relation_ids()
    with_id, total = store.rel_id_coverage()
    logs.append(
        f"[load_graph] 그래프 적재 완료 (그래프문서 {len(gdocs)}건, 엔티티없는 청크 Document {bare}건), "
        f"관계 rel_id 커버리지 {with_id}/{total}건(신규 스탬프 {new_ids}건)"
    )

    if settings.embedding.enabled:
        embeddings = build_embeddings(settings)
        vec = store.create_vector_indexes(settings.embedding, embeddings)
        logs.append(
            f"[load_graph] 벡터 인덱스 생성 — 엔티티 {vec.get('entity_vector', 0)}건·"
            f"청크 {vec.get('chunk_vector', 0)}건 임베딩(text-embedding-3-large)"
        )
    else:
        logs.append("[load_graph] 벡터 인덱스 생성 생략(--no-vector)")

    return {"log": logs}
