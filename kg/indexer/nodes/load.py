"""load 노드 — 교재 마크다운 로드. 파일명(장 번호·제목)을 source 메타데이터로 보존."""
from __future__ import annotations

import glob
import os

from ..config.settings import Settings


def _source_name(path: str) -> str:
    """파일 경로 → source 이름. 예: '.../14.GraphRAG.md' → '14.GraphRAG'."""
    return os.path.splitext(os.path.basename(path))[0]


def load_documents(settings: Settings) -> list[dict]:
    """교재 glob을 파일명 정렬 순으로 로드(결정적 순서 → chunk_id 재현성)."""
    pattern = os.path.expanduser(settings.textbook_glob)
    paths = sorted(glob.glob(pattern))
    docs: list[dict] = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            text = f.read()
        docs.append({"source": _source_name(p), "path": p, "text": text})
    return docs


def load_node(state: dict, settings: Settings) -> dict:
    docs = load_documents(settings)
    limit = state.get("limit_chapters")
    if limit:
        docs = docs[:limit]
    names = ", ".join(d["source"] for d in docs)
    return {
        "raw_docs": docs,
        "log": [f"[load] 교재 {len(docs)}개 파일 로드: {names}"],
    }
