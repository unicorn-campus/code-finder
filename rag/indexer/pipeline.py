"""인덱싱 파이프라인 오케스트레이션.

워크플로우: 코드 파일 수집 → 언어 판별 → 함수·클래스 경계 청킹 → 임베딩 전처리
→ 비동기 배치 임베딩 → Chroma upsert → 인덱싱 리포트.

증분 인덱싱: 파일 SHA-256 해시를 매니페스트와 비교하여 변경분만 재인덱싱하고,
삭제된 파일의 청크는 컬렉션에서 제거함.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from .chunker import Chunk, chunk_file
from .collector import FileRecord, iter_code_files, read_text
from .config import Settings
from .embedder import embed_texts, make_embeddings
from .preprocess import build_embed_text
from .store import CodeVectorStore, now_iso


def log(msg: str) -> None:
    """진행 단계·처리 건수 로그를 출력함."""
    print(f"[indexer] {msg}", flush=True)


async def run_index(settings: Settings, full: bool = False, limit: int | None = None) -> dict:
    """인덱싱 파이프라인을 실행하고 리포트 dict를 반환함."""
    t0 = time.perf_counter()
    indexed_at = now_iso()

    embeddings = make_embeddings(settings)
    store = CodeVectorStore(settings, embeddings)

    log(f"수집 시작: base_dir={settings.base_dir}")
    files: list[FileRecord] = list(iter_code_files(settings))
    if limit is not None:
        files = files[:limit]
    current = {f.rel_path: f for f in files}
    lang_files = Counter(f.lang for f in files)
    log(f"수집 완료: 파일 {len(files)}건 (언어별 {dict(lang_files)})")

    manifest = {} if full else store.load_manifest()
    if full:
        log("전체 재인덱싱 모드: 기존 컬렉션 초기화")
        store.clear()

    to_index: list[FileRecord] = []
    unchanged = 0
    for rel, f in current.items():
        prev = manifest.get(rel)
        if (not full) and prev and prev.get("sha256") == f.sha256:
            unchanged += 1
        else:
            to_index.append(f)
    removed = [] if full else [rel for rel in manifest if rel not in current]
    log(f"변경 판별: 인덱싱 대상 {len(to_index)}건 · 미변경 {unchanged}건 · 삭제 {len(removed)}건")

    # 변경·삭제 파일의 기존 청크 제거
    for rel in [f.rel_path for f in to_index] + removed:
        prev = manifest.get(rel)
        if prev and prev.get("chunk_ids"):
            store.delete_ids(prev["chunk_ids"])

    # 청킹
    all_chunks: list[Chunk] = []
    per_file_ids: dict[str, list[str]] = {}
    for f in to_index:
        raw = read_text(f.abs_path)
        chunks = chunk_file(f.rel_path, f.lang, raw, settings)
        per_file_ids[f.rel_path] = [c.chunk_id() for c in chunks]
        all_chunks.extend(chunks)
    log(f"청킹 완료: 신규/변경 청크 {len(all_chunks)}건")

    # 임베딩 + 적재
    if all_chunks:
        texts = [build_embed_text(c) for c in all_chunks]
        done = {"n": 0}

        def progress(n: int) -> None:
            done["n"] += n
            log(f"임베딩 진행: {done['n']}/{len(texts)}")

        log(f"임베딩 시작: 모델={settings.embedding_model} · 청크 {len(texts)}건")
        vectors = await embed_texts(embeddings, texts, settings, progress=progress)
        store.upsert(all_chunks, vectors, indexed_at)
        log("Chroma 적재 완료")
    else:
        log("변경분 없음: 임베딩 생략")

    # 매니페스트 갱신
    new_manifest: dict = {}
    for rel, f in current.items():
        if rel in per_file_ids:
            new_manifest[rel] = {
                "sha256": f.sha256, "lang": f.lang,
                "chunk_ids": per_file_ids[rel], "indexed_at": indexed_at,
            }
        else:
            new_manifest[rel] = manifest[rel]
    store.save_manifest(new_manifest)

    # 컬렉션 실측 조회 → 청크 매니페스트·분포 산출
    metas = store.all_metadatas()
    _write_chunk_manifest(settings.chunk_manifest_path, metas)
    chunks_by_lang = dict(Counter(m.get("lang", "?") for m in metas))
    chunks_by_dir = dict(
        Counter((m.get("path", "").split("/", 1)[0] or "?") for m in metas).most_common()
    )
    collection_count = store.count()

    elapsed = round(time.perf_counter() - t0, 2)
    report = {
        "generated_at": indexed_at,
        "base_dir": str(settings.base_dir),
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "files_scanned": len(files),
        "files_indexed": len(to_index),
        "files_unchanged": unchanged,
        "files_removed": len(removed),
        "files_by_lang": dict(lang_files),
        "chunks_indexed_this_run": len(all_chunks),
        "total_chunks": collection_count,
        "chunks_by_lang": chunks_by_lang,
        "chunks_by_dir": chunks_by_dir,
        "elapsed_seconds": elapsed,
    }
    _write_report(settings.report_path, report)
    log(f"리포트 기록: {settings.report_path} (총 청크 {collection_count}건, {elapsed}s)")
    return report


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_chunk_manifest(path: Path, metas: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for m in sorted(metas, key=lambda x: x.get("chunk_id", "")):
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def run_dry(settings: Settings, limit: int | None = None) -> dict:
    """DRY-RUN: 수집·청킹·전처리만 수행하고 임베딩·Chroma 적재는 생략함.

    유효한 OpenAI 키 없이 파이프라인 전단(수집→청킹→프리픽스)을 실증하고,
    실제 파일/청크 수·언어분포를 산출하기 위한 경로임.
    """
    import time

    t0 = time.perf_counter()
    indexed_at = now_iso()
    log("DRY-RUN 모드: 임베딩·Chroma 적재 생략 (수집·청킹·전처리만 실증)")

    files: list[FileRecord] = list(iter_code_files(settings))
    if limit is not None:
        files = files[:limit]
    lang_files = Counter(f.lang for f in files)
    log(f"수집 완료: 파일 {len(files)}건 (언어별 {dict(lang_files)})")

    all_chunks: list[Chunk] = []
    for f in files:
        raw = read_text(f.abs_path)
        all_chunks.extend(chunk_file(f.rel_path, f.lang, raw, settings))
    log(f"청킹 완료: 청크 {len(all_chunks)}건")

    # 프리픽스 결합이 예외 없이 동작하는지 실증(임베딩 입력 생성)
    embed_texts_preview = [build_embed_text(c) for c in all_chunks]
    log(f"임베딩 전처리 완료: 입력 텍스트 {len(embed_texts_preview)}건 생성")

    metas = [
        {
            "chunk_id": c.chunk_id(), "path": c.path, "lang": c.lang, "symbol": c.symbol,
            "signature": c.signature or "", "start_line": c.start_line, "end_line": c.end_line,
            "indexed_at": indexed_at,
        }
        for c in all_chunks
    ]
    _write_chunk_manifest(settings.chunk_manifest_path, metas)

    elapsed = round(time.perf_counter() - t0, 2)
    report = {
        "mode": "dry-run",
        "embedded": False,
        "note": "OpenAI 키 없이 수집·청킹·전처리만 실증함. 실제 벡터 적재는 미수행.",
        "generated_at": indexed_at,
        "base_dir": str(settings.base_dir),
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "files_scanned": len(files),
        "files_by_lang": dict(lang_files),
        "prospective_chunks": len(all_chunks),
        "chunks_by_lang": dict(Counter(m["lang"] for m in metas)),
        "chunks_by_dir": dict(Counter(m["path"].split("/", 1)[0] for m in metas).most_common()),
        "elapsed_seconds": elapsed,
    }
    _write_report(settings.dryrun_report_path, report)
    log(f"DRY-RUN 리포트 기록: {settings.dryrun_report_path} (예상 청크 {len(all_chunks)}건, {elapsed}s)")
    return report


def run_sample_queries(settings: Settings, queries: list[str], k: int = 5) -> None:
    """샘플 질의를 실행하여 top-k 결과를 로그로 출력함(정상 동작 증거)."""
    embeddings = make_embeddings(settings)
    store = CodeVectorStore(settings, embeddings)
    for q in queries:
        log(f"[질의] {q}")
        docs = store.similarity_search(q, k=k)
        for rank, d in enumerate(docs, 1):
            md = d.metadata
            log(f"  #{rank} {md.get('chunk_id')} (lang={md.get('lang')}, symbol={md.get('symbol')})")
