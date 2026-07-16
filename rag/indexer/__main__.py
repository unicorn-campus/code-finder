"""인덱서 CLI 진입점.

실행 예:
    python -m indexer --full                 # 전체 재인덱싱
    python -m indexer                         # 증분 인덱싱
    python -m indexer --limit 20              # 상위 20개 파일만(스모크)
    python -m indexer --sample-only           # 인덱싱 없이 샘플 질의만
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import Settings
from .pipeline import log, run_dry, run_index, run_sample_queries

# 정상 동작 확인용 샘플 질의(자연어→코드)
DEFAULT_SAMPLE_QUERIES = [
    "LangGraph로 상태를 공유하는 에이전트 그래프를 만드는 예제 코드",
    "RAG 검색을 위한 벡터 임베딩과 유사도 검색 예제",
    "OpenAI 함수 호출(function calling) 도구를 정의하고 사용하는 예제",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="indexer", description="예제 코드 Vector DB 인덱서")
    parser.add_argument("--full", action="store_true", help="전체 재인덱싱(컬렉션 초기화)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 파일 수 제한(스모크 테스트)")
    parser.add_argument("--base-dir", default=None, help="인덱싱 대상 루트(기본: 설정값)")
    parser.add_argument("--no-sample", action="store_true", help="인덱싱 후 샘플 질의 생략")
    parser.add_argument("--sample-only", action="store_true", help="인덱싱 없이 샘플 질의만 실행")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="임베딩·적재 없이 수집·청킹·전처리만 실증(키 불필요)",
    )
    parser.add_argument("--top-k", type=int, default=5, help="샘플 질의 top-k(기본 5)")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB",
        help="추가 제외 경로 글로브(반복 지정 가능). 기본값에 explain/data.js 포함",
    )
    args = parser.parse_args(argv)

    settings = Settings.load(base_dir=args.base_dir)
    if args.exclude:
        settings.exclude_globs = tuple(settings.exclude_globs) + tuple(args.exclude)
        log(f"제외 글로브: {settings.exclude_globs}")
    if not settings.openai_api_key:
        log("경고: OPENAI_API_KEY 미설정 — .env를 확인하세요")

    if args.dry_run:
        report = run_dry(settings, limit=args.limit)
        log(
            "DRY-RUN 요약: "
            f"파일 {report['files_scanned']}건 · "
            f"예상 청크 {report['prospective_chunks']}건 · "
            f"{report['elapsed_seconds']}s"
        )
        return 0

    if args.sample_only:
        run_sample_queries(settings, DEFAULT_SAMPLE_QUERIES, k=args.top_k)
        return 0

    report = asyncio.run(run_index(settings, full=args.full, limit=args.limit))
    log(
        "요약: "
        f"파일 {report['files_scanned']}건 스캔 · "
        f"청크 {report['total_chunks']}건 · "
        f"{report['elapsed_seconds']}s"
    )

    if not args.no_sample and report["total_chunks"] > 0:
        log("샘플 질의 실행")
        run_sample_queries(settings, DEFAULT_SAMPLE_QUERIES, k=args.top_k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
