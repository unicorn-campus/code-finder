"""split 노드 — 마크다운 헤더 기준 분할 후 크기 보정.

각 청크에 chunk_id(안정·재현), source, heading_path 메타데이터를 부여함.
langchain_neo4j는 source Document를 metadata['id']로 MERGE하므로 id=chunk_id로 설정함.
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from ..config.settings import Settings
from ..ids import chunk_id


def _heading_path(meta: dict) -> str:
    parts = [meta[k] for k in ("h1", "h2", "h3", "h4") if meta.get(k)]
    return " > ".join(parts)


def split_documents(raw_docs: list[dict], settings: Settings) -> list[Document]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=settings.split.headers_to_split_on,
        strip_headers=False,
    )
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.split.chunk_size,
        chunk_overlap=settings.split.chunk_overlap,
    )
    chunks: list[Document] = []
    idx = 0
    for doc in raw_docs:
        for hc in header_splitter.split_text(doc["text"]):
            heading = _heading_path(hc.metadata)
            for piece in size_splitter.split_text(hc.page_content):
                if not piece.strip():
                    continue
                cid = chunk_id(idx)
                chunks.append(
                    Document(
                        page_content=piece,
                        metadata={
                            "id": cid,            # Document 노드 MERGE 키
                            "chunk_id": cid,
                            "source": doc["source"],
                            "heading_path": heading,
                        },
                    )
                )
                idx += 1
    return chunks


def split_node(state: dict, settings: Settings) -> dict:
    # 전체 코퍼스를 결정적으로 분할해 chunk_id를 전역 일관되게 부여한 뒤 선택함
    chunks = split_documents(state["raw_docs"], settings)
    only = state.get("only_chunk_ids")
    if only:
        wanted = set(only)
        chunks = [c for c in chunks if c.metadata["chunk_id"] in wanted]
    max_chunks = state.get("max_chunks")
    if max_chunks:
        chunks = chunks[:max_chunks]
    by_source: dict[str, int] = {}
    for c in chunks:
        s = c.metadata["source"]
        by_source[s] = by_source.get(s, 0) + 1
    return {
        "chunks": chunks,
        "log": [f"[split] 청크 {len(chunks)}개 생성 (장별 건수: {by_source})"],
    }
