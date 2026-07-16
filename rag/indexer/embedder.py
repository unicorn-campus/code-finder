"""임베딩 호출.

- OpenAI `text-embedding-3-large`를 LangChain `OpenAIEmbeddings`로 사용함.
- 배치 처리이므로 비동기(`aembed_documents`)로 호출하며, 배치 분할·동시성 제한·
  지수 백오프 재시도를 적용함.
"""

from __future__ import annotations

import asyncio
import random
from typing import Sequence

from langchain_openai import OpenAIEmbeddings

from .config import Settings

# 재시도해도 회복 불가한 오류(인증·권한·잘못된 요청)는 즉시 전파함
try:  # openai 미설치 환경(순수 단위테스트)에서도 임포트 실패하지 않도록 방어
    from openai import (
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        PermissionDeniedError,
    )

    NON_RETRYABLE = (AuthenticationError, PermissionDeniedError, BadRequestError, NotFoundError)
except Exception:  # noqa: BLE001
    NON_RETRYABLE = ()


def make_embeddings(settings: Settings) -> OpenAIEmbeddings:
    """설정 기반 OpenAIEmbeddings 인스턴스를 생성함."""
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key or None,
        max_retries=settings.embed_max_retries,
    )


def _batched(items: Sequence, size: int) -> list[list]:
    """리스트를 size 단위 배치로 분할함."""
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


async def _embed_one_batch(
    embeddings: OpenAIEmbeddings, batch: list[str], settings: Settings
) -> list[list[float]]:
    """단일 배치를 임베딩하되 지수 백오프 재시도를 적용함."""
    attempt = 0
    while True:
        try:
            return await embeddings.aembed_documents(batch)
        except NON_RETRYABLE:
            raise  # 인증·권한·요청 오류는 재시도 무의미 → 즉시 전파
        except Exception:  # noqa: BLE001 - 그 외(429·타임아웃·5xx)는 재시도
            attempt += 1
            if attempt > settings.embed_max_retries:
                raise
            delay = settings.embed_base_delay * (2 ** (attempt - 1))
            delay += random.uniform(0, settings.embed_base_delay)  # 지터
            await asyncio.sleep(delay)


async def embed_texts(
    embeddings: OpenAIEmbeddings,
    texts: Sequence[str],
    settings: Settings,
    progress=None,
) -> list[list[float]]:
    """텍스트 시퀀스를 배치·동시성 제한하에 비동기 임베딩함(입력 순서 보존)."""
    if not texts:
        return []
    batches = _batched(texts, settings.embed_batch_size)
    sem = asyncio.Semaphore(settings.embed_concurrency)
    results: list[list[list[float]] | None] = [None] * len(batches)

    async def run(i: int, batch: list[str]) -> None:
        async with sem:
            vecs = await _embed_one_batch(embeddings, batch, settings)
            results[i] = vecs
            if progress is not None:
                progress(len(batch))

    await asyncio.gather(*(run(i, b) for i, b in enumerate(batches)))
    # 배치 순서대로 평탄화(입력 순서 보존)
    out: list[list[float]] = []
    for vecs in results:
        assert vecs is not None
        out.extend(vecs)
    return out
