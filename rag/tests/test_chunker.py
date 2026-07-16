"""chunker 단위 테스트: AST 청킹·시그니처·모듈세그먼트·서브분할·JS·ipynb."""

from __future__ import annotations

import json

from indexer.chunker import MODULE_SYMBOL, chunk_file, extract_signature
from indexer.config import Settings

SETTINGS = Settings()

PY_SRC = '''import os

@my_decorator
def foo(a, b):
    """Foo 함수 독스트링 첫줄.

    상세 설명.
    """
    return a + b


class Bar:
    """Bar 클래스 요지."""

    def method(self):
        return 1


x = 1
y = foo(1, 2)
'''


def test_extract_signature_function_and_class() -> None:
    assert extract_signature("@deco\ndef foo(a, b) -> int:\n    return a") == "def foo(a, b) -> int"
    assert extract_signature("class Bar(Base):\n    pass") == "class Bar(Base)"
    assert extract_signature("class Bar:\n    pass") == "class Bar"


def test_python_function_class_and_module_chunks() -> None:
    chunks = chunk_file("m.py", "python", PY_SRC, SETTINGS)
    by_symbol = {c.symbol: c for c in chunks}

    assert "foo" in by_symbol
    assert by_symbol["foo"].signature.startswith("def foo(a, b)")
    assert "Bar" in by_symbol
    assert by_symbol["Bar"].signature == "class Bar"
    # 모듈 레벨 코드(import/최상위 대입)는 <module> 청크로 수집
    assert MODULE_SYMBOL in by_symbol
    # 모든 청크 텍스트는 비어있지 않음
    assert all(c.text.strip() for c in chunks)


def test_chunk_id_format_and_uniqueness() -> None:
    chunks = chunk_file("pkg/m.py", "python", PY_SRC, SETTINGS)
    ids = [c.chunk_id() for c in chunks]
    assert len(ids) == len(set(ids))  # 유일성
    for c in chunks:
        assert c.chunk_id() == f"{c.path}#{c.symbol}#{c.start_line}"
        assert c.chunk_id().startswith("pkg/m.py#")


def test_decorator_included_in_start_line() -> None:
    chunks = chunk_file("m.py", "python", PY_SRC, SETTINGS)
    foo = next(c for c in chunks if c.symbol == "foo")
    # @my_decorator 라인(3)부터 시작하여 데코레이터를 포함
    assert foo.start_line == 3
    assert "@my_decorator" in foo.text


def test_long_function_subsplits() -> None:
    body = "\n".join(f"    x{i} = {i} + {i}" for i in range(400))
    src = f"def big():\n{body}\n"
    chunks = chunk_file("big.py", "python", src, SETTINGS)
    big_chunks = [c for c in chunks if c.symbol == "big"]
    assert len(big_chunks) >= 2  # 500토큰 초과 → 하위 분할
    assert len({c.chunk_id() for c in big_chunks}) == len(big_chunks)


def test_javascript_symbol_extraction() -> None:
    js = "export function greet(name) {\n  return `hi ${name}`;\n}\n"
    chunks = chunk_file("a.js", "javascript", js, SETTINGS)
    assert chunks
    assert any(c.symbol == "greet" for c in chunks)


def test_ipynb_code_cells_parsed() -> None:
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# 제목\n"]},
            {"cell_type": "code", "source": ["%matplotlib inline\n", "def cell_fn():\n", "    return 42\n"]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    chunks = chunk_file("nb.ipynb", "python", json.dumps(nb), SETTINGS)
    assert any(c.symbol == "cell_fn" for c in chunks)


def test_syntax_error_falls_back_to_token_split() -> None:
    bad = "def broken(:\n  this is not python !!!\n" * 3
    chunks = chunk_file("bad.py", "python", bad, SETTINGS)
    assert chunks  # 폴백으로 최소 1청크 생성
    assert all(c.symbol == MODULE_SYMBOL for c in chunks)
