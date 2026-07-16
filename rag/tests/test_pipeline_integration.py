"""pipeline 통합 테스트: 실제 OpenAI 임베딩 + Chroma 적재.

`integration` 마커로 분리됨. 기본 `pytest` 실행에서 제외되며, 실행하려면:
    pytest -m integration
OPENAI_API_KEY 미설정 시 skip함.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from indexer.config import Settings
from indexer.pipeline import run_index

pytestmark = pytest.mark.integration


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def test_end_to_end_small_index(tmp_path: Path) -> None:
    settings = Settings.load()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY 미설정 — 통합 테스트 skip")

    base = tmp_path / "hands-on"
    _write(base / "graph.py", 'def build_graph():\n    """StateGraph를 구성함."""\n    return "graph"\n')
    _write(base / "rag.py", 'def similarity_search(q):\n    """벡터 유사도 검색."""\n    return [q]\n')

    settings = Settings(
        openai_api_key=settings.openai_api_key,
        base_dir=base,
        store_dir=tmp_path / "store",
        collection_name="integration_test",
    )

    report = await run_index(settings, full=True)
    assert report["files_scanned"] == 2
    assert report["total_chunks"] > 0

    from indexer.store import CodeVectorStore
    from indexer.embedder import make_embeddings

    store = CodeVectorStore(settings, make_embeddings(settings))
    docs = store.similarity_search("그래프를 만드는 함수", k=5)
    assert len(docs) > 0
    assert docs[0].metadata["chunk_id"]
