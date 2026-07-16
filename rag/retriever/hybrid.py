"""코드 하이브리드 리트리버 (§3.4) — BM25 + Chroma(Vector) 앙상블.

- Vector: 인덱서가 적재한 Chroma 컬렉션(`code_chunks`)을 mmr(top-k 5, fetch-k 10)로 검색
- Keyword: 컬렉션 전체 문서로 BM25Retriever 구성
- 융합: EnsembleRetriever(weights=[0.4(BM25), 0.6(Vector)])
- 반환: chunk_id·path·symbol 등 `indexing-code.md` 메타데이터 계약을 그대로 전달(환각 차단 근거)
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from langchain_chroma import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.common.logging_utils import get_logger
from .config import RetrieverConfig, load_retriever_config

log = get_logger()


class CodeHybridRetriever:
    """코드 예제 하이브리드 리트리버."""

    def __init__(self, cfg: Optional[RetrieverConfig] = None):
        self.cfg = cfg or load_retriever_config()
        idx = self.cfg.indexer
        self.embeddings = OpenAIEmbeddings(model=idx.embedding_model, api_key=idx.openai_api_key)
        self.vs = Chroma(
            collection_name=idx.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(idx.chroma_dir),
        )
        self._ensemble: Optional[EnsembleRetriever] = None

    def count(self) -> int:
        return self.vs._collection.count()

    def _load_corpus(self) -> list[Document]:
        """컬렉션 전체 문서를 Document 리스트로 로드(BM25 구성용)."""
        got = self.vs._collection.get(include=["documents", "metadatas"])
        docs = []
        for text, meta in zip(got.get("documents", []) or [], got.get("metadatas", []) or []):
            docs.append(Document(page_content=text or "", metadata=meta or {}))
        return docs

    def _build(self) -> EnsembleRetriever:
        if self._ensemble is not None:
            return self._ensemble
        corpus = self._load_corpus()
        if not corpus:
            raise RuntimeError(
                f"Chroma 컬렉션 '{self.cfg.indexer.collection_name}'이 비어 있음 — 코드 인덱스 미구축")
        bm25 = BM25Retriever.from_documents(corpus)
        bm25.k = self.cfg.bm25_k
        vector = self.vs.as_retriever(
            search_type=self.cfg.search_type,
            search_kwargs={"k": self.cfg.top_k, "fetch_k": self.cfg.fetch_k},
        )
        self._ensemble = EnsembleRetriever(
            retrievers=[bm25, vector],
            weights=[self.cfg.bm25_weight, self.cfg.vector_weight],
        )
        log.info("[retriever] code hybrid 구성: BM25(%d docs, k=%d) + Vector(mmr,k=%d,fetch_k=%d) w=%.1f/%.1f",
                 len(corpus), self.cfg.bm25_k, self.cfg.top_k, self.cfg.fetch_k,
                 self.cfg.bm25_weight, self.cfg.vector_weight)
        return self._ensemble

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """하이브리드 검색 → 상위 후보를 dict 목록으로 반환.

        각 항목: chunk_id·path·symbol·signature·lang·start_line·end_line·text(근거 원문).
        """
        ensemble = self._build()
        docs = ensemble.invoke(query)
        k = top_k or self.cfg.top_k
        results = []
        for rank, d in enumerate(docs[:k]):
            m = d.metadata or {}
            results.append({
                "chunk_id": m.get("chunk_id", ""),
                "path": m.get("path", ""),
                "symbol": m.get("symbol", ""),
                "signature": m.get("signature", ""),
                "lang": m.get("lang", ""),
                "start_line": m.get("start_line"),
                "end_line": m.get("end_line"),
                "text": d.page_content,
                "rank": rank,
            })
        log.info("[tool] code_search: %d candidates (top_k=%d)", len(results), k)
        return results


@lru_cache(maxsize=1)
def get_code_retriever() -> CodeHybridRetriever:
    """프로세스 단위 싱글턴(코퍼스·BM25 재사용)."""
    return CodeHybridRetriever()
