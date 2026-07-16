"""LLM·임베딩 팩토리.

- 추출·커뮤니티 요약 LLM: Groq LPU, 모델 openai/gpt-oss-120b (재현성 우선 temperature 0)
- 임베딩: OpenAI text-embedding-3-large (Local 검색·NDCG용 벡터 인덱스)
"""
from __future__ import annotations

from langchain_groq import ChatGroq
from langchain_openai import OpenAIEmbeddings

from .config.settings import Settings


def build_llm(settings: Settings) -> ChatGroq:
    cfg = settings.llm
    return ChatGroq(
        model=cfg.model,
        api_key=cfg.api_key,
        temperature=cfg.temperature,
        timeout=cfg.timeout,
        max_retries=cfg.max_retries,
    )


def build_embeddings(settings: Settings) -> OpenAIEmbeddings:
    cfg = settings.embedding
    return OpenAIEmbeddings(model=cfg.model, api_key=cfg.api_key)
