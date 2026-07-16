"""Chroma Vector DB 저장소 래퍼.

- 청크별 메타데이터(chunk_id·path·lang·symbol·signature·start_line·end_line·indexed_at) 부여.
- 사전 계산된 임베딩을 컬렉션에 upsert(재현성·증분 갱신 대응).
- 증분 인덱싱용 파일 매니페스트(경로→해시·청크ID) 관리.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .chunker import Chunk
from .config import Settings

# Chroma 컬렉션 단일 upsert 최대 배치(내부 상한 5461 미만으로 분할)
MAX_UPSERT_BATCH = 5000


def now_iso() -> str:
    """UTC ISO-8601(초 단위) 타임스탬프를 반환함."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_metadata(chunk: Chunk, indexed_at: str) -> dict:
    """Chroma 메타데이터 레코드를 생성함(값은 str/int만 사용)."""
    return {
        "chunk_id": chunk.chunk_id(),
        "path": chunk.path,
        "lang": chunk.lang,
        "symbol": chunk.symbol,
        "signature": chunk.signature or "",
        "start_line": int(chunk.start_line),
        "end_line": int(chunk.end_line),
        "indexed_at": indexed_at,
    }


class CodeVectorStore:
    """Chroma 컬렉션 + 파일 매니페스트를 함께 다루는 저장소."""

    def __init__(self, settings: Settings, embeddings: OpenAIEmbeddings):
        self.settings = settings
        self.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.vs = Chroma(
            collection_name=settings.collection_name,
            embedding_function=embeddings,
            persist_directory=str(settings.chroma_dir),
        )

    # --- 컬렉션 ---
    def count(self) -> int:
        """컬렉션 내 청크 수를 반환함."""
        return self.vs._collection.count()

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]], indexed_at: str) -> None:
        """청크·임베딩·메타데이터를 컬렉션에 upsert함(Chroma 최대 배치 제한 대응 분할)."""
        if not chunks:
            return
        ids = [c.chunk_id() for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [build_metadata(c, indexed_at) for c in chunks]
        step = MAX_UPSERT_BATCH
        for i in range(0, len(ids), step):
            self.vs._collection.upsert(
                ids=ids[i : i + step],
                embeddings=embeddings[i : i + step],
                documents=documents[i : i + step],
                metadatas=metadatas[i : i + step],
            )

    def delete_ids(self, ids: Iterable[str]) -> None:
        """지정 ID의 청크를 컬렉션에서 삭제함."""
        ids = [i for i in ids]
        if ids:
            self.vs._collection.delete(ids=ids)

    def clear(self) -> None:
        """컬렉션 전체를 삭제(전체 재인덱싱용)함."""
        existing = self.vs._collection.get(include=[])
        ids = existing.get("ids", [])
        if ids:
            self.vs._collection.delete(ids=ids)

    def similarity_search(self, query: str, k: int = 5):
        """쿼리 임베딩 기반 유사도 검색 상위 k건을 반환함."""
        return self.vs.similarity_search(query, k=k)

    def all_metadatas(self) -> list[dict]:
        """컬렉션 전체 메타데이터를 조회함(리포트·매니페스트 산출용)."""
        got = self.vs._collection.get(include=["metadatas"])
        return got.get("metadatas", []) or []

    # --- 파일 매니페스트(증분 인덱싱) ---
    def load_manifest(self) -> dict:
        """파일 매니페스트를 로드함(없으면 빈 dict)."""
        p: Path = self.settings.file_manifest_path
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}

    def save_manifest(self, manifest: dict) -> None:
        """파일 매니페스트를 저장함."""
        p: Path = self.settings.file_manifest_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
