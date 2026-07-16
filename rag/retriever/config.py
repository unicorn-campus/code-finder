"""코드 하이브리드 리트리버 설정.

- 인덱서(`rag/indexer`)가 만든 Chroma 스토어(컬렉션·경로·임베딩 모델)를 그대로 소비함.
- 하이브리드 가중치·top-k·fetch-k는 dev-prompt-guide_v2 §3.4 [고정] 사양을 따름.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rag.indexer.config import Settings as IndexerSettings


@dataclass
class RetrieverConfig:
    """RAG 하이브리드 리트리버 파라미터 [고정]."""

    # 하이브리드 서치 가중치: BM25 0.4 + Vector 0.6
    bm25_weight: float = 0.4
    vector_weight: float = 0.6
    # 벡터 서치타입 mmr, top-k 5, fetch-k 10
    search_type: str = "mmr"
    top_k: int = 5
    fetch_k: int = 10
    # BM25 후보 수(융합 전 후보 풀)
    bm25_k: int = 10

    # 인덱서 스토어 설정(컬렉션·경로·임베딩 모델·키)
    indexer: IndexerSettings = field(default_factory=IndexerSettings.load)


def load_retriever_config() -> RetrieverConfig:
    return RetrieverConfig()
