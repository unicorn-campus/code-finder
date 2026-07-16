"""인덱싱 실행 진입점.

사용 예:
  python -m kg.indexer.run --reset                 # 전체 재인덱싱(그래프 초기화 후)
  python -m kg.indexer.run --limit-chapters 1      # 1개 장만(스모크 테스트)
  python -m kg.indexer.run --no-vector             # 벡터 인덱스 생략(임베딩 비용 절감)
  python -m kg.indexer.run --retry-failed          # 실패·미적재 청크만 재추출(초기화 안 함)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from langgraph.checkpoint.sqlite import SqliteSaver

from ..store.neo4j_store import Neo4jStore
from .config.settings import Settings, load_settings
from .llm import build_llm
from .nodes.extract import build_transformer
from .nodes.load import load_documents
from .nodes.split import split_documents
from .pipeline import build_graph

_STAT_KEYS = (
    "nodes", "entities", "documents", "communities", "relationships",
    "mentions", "entity_rels", "entity_embeddings", "chunk_embeddings", "orphan_entities",
)


def _parse_args(argv):
    p = argparse.ArgumentParser(description="교재 GraphRAG 인덱서")
    p.add_argument("--reset", action="store_true", help="적재 전 그래프 전체 초기화")
    p.add_argument("--limit-chapters", type=int, default=None, help="앞 N개 장만 처리")
    p.add_argument("--max-chunks", type=int, default=None, help="앞 N개 청크만 처리")
    p.add_argument("--no-vector", action="store_true", help="벡터 인덱스 생성 생략")
    p.add_argument("--skip-community", action="store_true", help="커뮤니티 탐지·요약 생략")
    p.add_argument("--retry-failed", action="store_true",
                   help="실패 리포트 + Neo4j 미적재 청크만 재추출(초기화 안 함)")
    p.add_argument("--thread-id", default="textbook-index", help="체크포인트 스레드 ID")
    return p.parse_args(argv)


def _all_chunk_ids(settings: Settings) -> list[str]:
    """전체 코퍼스를 결정적으로 분할해 얻은 chunk_id 목록(재현 가능)."""
    docs = load_documents(settings)
    return [c.metadata["chunk_id"] for c in split_documents(docs, settings)]


def _report_failures(settings: Settings) -> list[str]:
    path = settings.extract_report_path
    if not os.path.exists(path):
        return []
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except Exception:
        return []
    return [f["chunk_id"] for f in data.get("failures", []) if f.get("chunk_id")]


def _write_report(settings: Settings, result: dict) -> None:
    path = settings.extract_report_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = {
        "failures": result.get("failures", []),
        "empty_chunk_ids": result.get("empty_chunk_ids", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _retry_targets(settings: Settings, store: Neo4jStore) -> list[str]:
    """재추출 대상 = 직전 리포트 실패분 ∪ Neo4j 미적재(Document 없는) 청크."""
    all_ids = set(_all_chunk_ids(settings))
    existing = store.existing_chunk_ids()
    missing = all_ids - existing
    targets = missing | (set(_report_failures(settings)) & all_ids)
    return sorted(targets)


def main(argv=None) -> int:
    args = _parse_args(argv)
    settings = load_settings()
    if args.no_vector:
        settings.embedding.enabled = False

    store = Neo4jStore(settings.neo4j)
    if args.reset:
        store.wipe()
        print("[run] 그래프 초기화 완료")

    only_chunk_ids = None
    skip_community = args.skip_community
    if args.retry_failed:
        only_chunk_ids = _retry_targets(settings, store)
        print(f"[run] 재추출 대상 청크 {len(only_chunk_ids)}건")
        if not only_chunk_ids:
            print("[run] 재추출 대상 없음 — 종료")
            return 0

    llm = build_llm(settings)
    transformer = build_transformer(llm, settings.schema())

    os.makedirs(os.path.dirname(settings.sqlite_path), exist_ok=True)
    with SqliteSaver.from_conn_string(settings.sqlite_path) as saver:
        graph = build_graph(
            settings, store, llm, transformer, checkpointer=saver, skip_community=skip_community
        )
        state_in = {
            "reset": args.reset,
            "limit_chapters": args.limit_chapters,
            "max_chunks": args.max_chunks,
            "only_chunk_ids": only_chunk_ids,
            "log": [],
        }
        config = {"configurable": {"thread_id": args.thread_id}}
        result = graph.invoke(state_in, config=config)

    _write_report(settings, result)

    print("\n===== 실행 로그 =====")
    for line in result.get("log", []):
        print(line)

    stats = result.get("stats", {})
    print("\n===== 최종 통계 =====")
    for k in _STAT_KEYS:
        if k in stats:
            print(f"  {k}: {stats[k]}")
    print(f"  integrity_ok: {stats.get('integrity_ok')}")
    print(f"  잔여 실패: {len(result.get('failures', []))}건 · 엔티티없음: {len(result.get('empty_chunk_ids', []))}건")

    return 0 if stats.get("integrity_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
