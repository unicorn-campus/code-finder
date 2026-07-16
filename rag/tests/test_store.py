"""store 단위 테스트: 메타데이터 생성·Chroma upsert/count/delete(오프라인).

precomputed 임베딩을 직접 넣으므로 OpenAI 원격 호출 없이 검증 가능함.
similarity_search(쿼리 임베딩 필요)는 integration 테스트에서 검증함.
"""

from __future__ import annotations

from pathlib import Path

from langchain_openai import OpenAIEmbeddings

from indexer.chunker import Chunk
from indexer.config import Settings
from indexer.store import CodeVectorStore, build_metadata, now_iso


def _chunk(symbol: str, line: int) -> Chunk:
    return Chunk(
        path="pkg/m.py", lang="python", symbol=symbol,
        signature=f"def {symbol}()", start_line=line, end_line=line + 2,
        text=f"def {symbol}():\n    return {line}\n",
    )


def test_build_metadata_types_and_fields() -> None:
    md = build_metadata(_chunk("foo", 1), now_iso())
    assert md["chunk_id"] == "pkg/m.py#foo#1"
    assert md["path"] == "pkg/m.py"
    assert md["lang"] == "python"
    assert md["symbol"] == "foo"
    assert isinstance(md["start_line"], int) and isinstance(md["end_line"], int)
    # Chroma 메타데이터는 None을 허용하지 않음 → 문자열 보장
    assert all(v is not None for v in md.values())


def test_now_iso_format() -> None:
    ts = now_iso()
    assert ts.endswith("+00:00")
    assert "T" in ts


def test_upsert_count_delete_offline(tmp_path: Path) -> None:
    settings = Settings(
        openai_api_key="test-key",
        store_dir=tmp_path / "store",
        collection_name="unit_test",
    )
    emb = OpenAIEmbeddings(model=settings.embedding_model, api_key="test-key")
    store = CodeVectorStore(settings, emb)

    chunks = [_chunk("foo", 1), _chunk("bar", 10)]
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    store.upsert(chunks, vectors, now_iso())
    assert store.count() == 2

    # upsert 재실행은 중복 생성하지 않음(동일 ID)
    store.upsert(chunks, vectors, now_iso())
    assert store.count() == 2

    store.delete_ids([chunks[0].chunk_id()])
    assert store.count() == 1

    store.clear()
    assert store.count() == 0
