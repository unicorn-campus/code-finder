"""RAGAS 호환 shim.

ragas 0.4.x는 `langchain_community.chat_models.vertexai.ChatVertexAI`를 하드 import하나,
langchain-community 0.4.x에서 해당 서브모듈이 제거됨(VertexAI 미사용). 본 프로젝트는 VertexAI를
사용하지 않으므로 스텁 모듈을 sys.modules에 선등록하여 import를 통과시킴.

**주의**: ragas를 import하기 전에 반드시 본 모듈을 먼저 import할 것.
"""
from __future__ import annotations

import sys
import types

_NAME = "langchain_community.chat_models.vertexai"


def install() -> None:
    """제거된 vertexai 서브모듈을 스텁으로 등록(ragas import 호환)."""
    if _NAME in sys.modules:
        return
    shim = types.ModuleType(_NAME)

    class ChatVertexAI:  # 미사용 스텁
        def __init__(self, *a, **k):
            raise RuntimeError("ChatVertexAI는 본 프로젝트에서 사용하지 않음(shim)")

    shim.ChatVertexAI = ChatVertexAI
    sys.modules[_NAME] = shim


install()
