"""LangGraph 파이프라인 조립 — load → split → extract → load_graph → community → verify.

노드 간 데이터는 StateGraph의 State(IndexState)로 공유하며, 의존성(설정·스토어·LLM·트랜스포머)은
클로저로 주입해 테스트에서 개별 노드를 독립 호출 가능하게 함.
체크포인트(SqliteSaver)는 호출부(run.py)에서 주입함.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes.community import community_node
from .nodes.extract import extract_node
from .nodes.load import load_node
from .nodes.load_graph import load_graph_node
from .nodes.split import split_node
from .nodes.verify import verify_node
from .state import IndexState


def build_graph(settings, store, llm, transformer, checkpointer=None, skip_community=False):
    builder = StateGraph(IndexState)

    builder.add_node("load", lambda s: load_node(s, settings))
    builder.add_node("split", lambda s: split_node(s, settings))
    builder.add_node("extract", lambda s: extract_node(s, settings, transformer))
    builder.add_node("load_graph", lambda s: load_graph_node(s, settings, store))
    builder.add_node("verify", lambda s: verify_node(s, store))

    builder.add_edge(START, "load")
    builder.add_edge("load", "split")
    builder.add_edge("split", "extract")
    builder.add_edge("extract", "load_graph")
    if skip_community:
        # 소규모 재시도 등에서 전체 커뮤니티 재요약을 생략함
        builder.add_edge("load_graph", "verify")
    else:
        builder.add_node("community", lambda s: community_node(s, settings, store, llm))
        builder.add_edge("load_graph", "community")
        builder.add_edge("community", "verify")
    builder.add_edge("verify", END)

    return builder.compile(checkpointer=checkpointer)
