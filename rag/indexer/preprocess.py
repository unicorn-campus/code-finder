"""임베딩 전처리.

각 청크 앞에 `파일 경로 + 함수 시그니처 + 독스트링` 프리픽스를 결합하여
코드 검색 재현율을 높인 임베딩 입력 텍스트를 생성함.
"""

from __future__ import annotations

import ast

from .chunker import Chunk


def _docstring_for(chunk: Chunk) -> str:
    """청크 텍스트에서 함수/클래스 독스트링을 추출함(python 한정, 실패 시 빈 문자열)."""
    if chunk.lang != "python" or not chunk.signature:
        return ""
    try:
        tree = ast.parse(chunk.text)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc:
                # 프리픽스 1행 요약: 첫 비어있지 않은 라인
                for line in doc.splitlines():
                    if line.strip():
                        return line.strip()
    return ""


def build_embed_text(chunk: Chunk) -> str:
    """청크의 임베딩 입력 텍스트(프리픽스 + 원본 코드)를 생성함."""
    doc = _docstring_for(chunk)
    header = [f"# path: {chunk.path}"]
    if chunk.signature:
        header.append(f"# signature: {chunk.signature}")
    if doc:
        header.append(f"# doc: {doc}")
    return "\n".join(header) + "\n" + chunk.text
