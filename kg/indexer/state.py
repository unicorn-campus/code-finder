"""LangGraph 파이프라인 상태 정의.

StateGraph의 State(TypedDict)로 노드 간 데이터를 공유함.
`log`는 Reducer(operator.add)로 각 노드의 메시지를 누적함.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.documents import Document


class IndexState(TypedDict, total=False):
    # --- 제어 입력 ---
    reset: bool
    limit_chapters: Optional[int]      # 앞 N개 장만 처리(테스트용)
    max_chunks: Optional[int]          # 앞 N개 청크만 처리(테스트용)
    only_chunk_ids: Optional[list]     # 지정 chunk_id만 처리(--retry-failed)

    # --- 노드 산출 ---
    raw_docs: list[dict]               # load: [{source, path, text}]
    chunks: list[Document]             # split: chunk_id/source/heading_path 부여된 청크
    graph_documents: list[Any]         # extract: 정규화된 List[GraphDocument]
    empty_chunk_ids: list[str]         # extract: 추출 성공했으나 엔티티 0인 청크
    failures: list[dict]               # extract: 실패 청크 [{chunk_id, reason, detail}]
    stats: dict                        # verify: 최종 통계·무결성

    # --- 누적 로그 (Reducer) ---
    log: Annotated[list[str], operator.add]
