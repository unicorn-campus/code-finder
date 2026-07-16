"""embedder 단위 테스트: 배치·순서보존·지수 백오프 재시도(Mock)."""

from __future__ import annotations

import pytest

from indexer.config import Settings
from indexer.embedder import embed_texts


class FakeEmbeddings:
    """aembed_documents를 흉내내는 테스트 더블."""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0
        self.seen_batches: list[list[str]] = []

    async def aembed_documents(self, batch):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated rate limit")
        self.seen_batches.append(list(batch))
        # 각 텍스트를 길이 기반 1차원 벡터로 매핑(순서 검증용)
        return [[float(len(t))] for t in batch]


async def test_order_preserved_across_batches() -> None:
    settings = Settings(embed_batch_size=2, embed_base_delay=0.001)
    emb = FakeEmbeddings()
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    out = await embed_texts(emb, texts, settings)
    assert out == [[1.0], [2.0], [3.0], [4.0], [5.0]]  # 입력 순서 보존


async def test_retries_then_succeeds() -> None:
    settings = Settings(embed_batch_size=10, embed_base_delay=0.001, embed_max_retries=3)
    emb = FakeEmbeddings(fail_times=2)
    out = await embed_texts(emb, ["x", "yy"], settings)
    assert out == [[1.0], [2.0]]
    assert emb.calls == 3  # 2회 실패 후 3번째 성공


async def test_gives_up_after_max_retries() -> None:
    settings = Settings(embed_batch_size=10, embed_base_delay=0.001, embed_max_retries=2)
    emb = FakeEmbeddings(fail_times=99)
    with pytest.raises(RuntimeError):
        await embed_texts(emb, ["x"], settings)


async def test_empty_input_returns_empty() -> None:
    settings = Settings()
    assert await embed_texts(FakeEmbeddings(), [], settings) == []
