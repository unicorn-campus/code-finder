"""extract 노드 — LLMGraphTransformer로 엔티티·관계 추출(비동기 병렬) 후 ID 정규화.

- 추출 범위는 graph_schema.yaml의 allowed_nodes/allowed_relationships로 제한
- Structured Output(스키마 강제) 방식은 LLMGraphTransformer가 내부적으로 사용
- LLM 표기 흔들림(예: 'Neo4J' vs 'Neo4j')은 entity_id(slug) 정규화로 흡수해 병합 안정화
"""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j.graphs.graph_document import GraphDocument, Node, Relationship

from ..config.settings import GraphSchema, Settings
from ..ids import entity_id, relation_id


def build_transformer(llm, schema: GraphSchema) -> LLMGraphTransformer:
    return LLMGraphTransformer(
        llm=llm,
        allowed_nodes=list(schema.allowed_nodes),
        allowed_relationships=schema.relationship_tuples,
        node_properties=list(schema.node_properties),
    )


def normalize_graph_document(gd: GraphDocument) -> GraphDocument:
    """엔티티 id를 ent_<slug>로 정규화, 원본명은 name 속성 보존, 관계 재배선·rel_id 부여."""
    id_map: dict[str, Node] = {}

    def norm(node: Node) -> Node:
        new_id = entity_id(node.id)
        if new_id not in id_map:
            props = dict(node.properties or {})
            props.setdefault("name", str(node.id))
            id_map[new_id] = Node(id=new_id, type=node.type, properties=props)
        return id_map[new_id]

    for n in gd.nodes:
        norm(n)

    rels: list[Relationship] = []
    for r in gd.relationships:
        s = norm(r.source)
        t = norm(r.target)
        props = dict(r.properties or {})
        props["rel_id"] = relation_id(s.id, r.type, t.id)
        rels.append(Relationship(source=s, target=t, type=r.type, properties=props))

    return GraphDocument(nodes=list(id_map.values()), relationships=rels, source=gd.source)


# 재시도 대상 실패 사유(빈 추출은 정상으로 간주 → 재시도 안 함)
RETRYABLE = ("rate_limit", "parse_error")


def _classify(exc: BaseException) -> str:
    """예외를 실패 사유로 분류. 429/rate limit → rate_limit, 그 외 → parse_error."""
    s = f"{type(exc).__name__}: {exc}".lower()
    if "429" in s or "rate limit" in s or "ratelimit" in s or "too many requests" in s:
        return "rate_limit"
    return "parse_error"


async def _extract_one(transformer, doc: Document, sem: asyncio.Semaphore) -> tuple[str, Document, object]:
    """단일 청크 추출. 반환: (사유, doc, GraphDocument|detail).

    사유: ok(엔티티 추출) / empty(추출 성공했으나 엔티티 0) / rate_limit / parse_error
    """
    async with sem:
        try:
            gds = await transformer.aconvert_to_graph_documents([doc])
            gd = gds[0] if gds else None
            if gd is None or not gd.nodes:
                return ("empty", doc, None)
            return ("ok", doc, gd)
        except BaseException as e:  # noqa: BLE001 - 사유 분류 후 상위에서 처리
            return (_classify(e), doc, f"{type(e).__name__}: {e}"[:200])


async def _extract_async(
    transformer, chunks: list[Document], concurrency: int, retry: bool = True
) -> list[tuple[str, Document, object]]:
    sem = asyncio.Semaphore(concurrency)
    total = len(chunks)
    done = 0
    lock = asyncio.Lock()

    async def run(doc: Document):
        nonlocal done
        rec = await _extract_one(transformer, doc, sem)
        async with lock:
            done += 1
            if done % 25 == 0 or done == total:
                print(f"[extract] 진행 {done}/{total} 청크", file=sys.stderr, flush=True)
        return rec

    records = list(await asyncio.gather(*[run(c) for c in chunks]))

    # 재시도 대상(429·파싱 실패)만 동시성 1로 순차 재시도 1회
    if retry:
        retry_idx = [i for i, (reason, _, _) in enumerate(records) if reason in RETRYABLE]
        if retry_idx:
            print(f"[extract] 실패 {len(retry_idx)}건 순차 재시도", file=sys.stderr, flush=True)
            rsem = asyncio.Semaphore(1)
            for i in retry_idx:
                records[i] = await _extract_one(transformer, records[i][1], rsem)
    return records


def extract_node(state: dict, settings: Settings, transformer) -> dict:
    chunks: list[Document] = state["chunks"]
    records = asyncio.run(_extract_async(transformer, chunks, settings.llm.max_concurrency))

    graph_documents: list[GraphDocument] = []
    empty_chunk_ids: list[str] = []
    failures: list[dict] = []
    for reason, doc, payload in records:
        cid = doc.metadata.get("chunk_id")
        if reason == "ok":
            graph_documents.append(normalize_graph_document(payload))
        elif reason == "empty":
            empty_chunk_ids.append(cid)
        else:
            failures.append({"chunk_id": cid, "reason": reason, "detail": payload})

    n_nodes = sum(len(g.nodes) for g in graph_documents)
    n_rels = sum(len(g.relationships) for g in graph_documents)
    reasons: dict[str, int] = {}
    for f in failures:
        reasons[f["reason"]] = reasons.get(f["reason"], 0) + 1
    return {
        "graph_documents": graph_documents,
        "empty_chunk_ids": empty_chunk_ids,
        "failures": failures,
        "log": [
            f"[extract] 추출성공 {len(graph_documents)}건·엔티티없음 {len(empty_chunk_ids)}건·"
            f"실패 {len(failures)}건{reasons or ''} / 총 {len(chunks)}청크, "
            f"엔티티 {n_nodes}건·관계 {n_rels}건(병합 전 합계)"
        ],
    }
