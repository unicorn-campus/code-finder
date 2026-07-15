"""함수·클래스 경계 우선 청킹.

- Python: `ast`로 최상위 함수/클래스 경계를 정밀 추출(symbol·signature·라인) 후,
  경계 밖 모듈 레벨 코드는 `<module>` 세그먼트로 수집함.
- JavaScript/TypeScript: 언어별 스플리터로 분할 후 정규식으로 심볼을 best-effort 추출함.
- 미지원/파싱 실패: 토큰 기준 폴백 분할.
- 단일 심볼이 청크 사이즈(500토큰)를 초과하면 언어 스플리터로 하위 분할함.

청킹 사이즈 500토큰·오버랩 100토큰은 tiktoken 인코딩 기준으로 강제함.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import lru_cache

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from .config import Settings

# 언어 라벨 → LangChain Language(언어별 스플리터 세퍼레이터)
_LC_LANGUAGE = {
    "python": Language.PYTHON,
    "javascript": Language.JS,
    "typescript": Language.TS,
}

MODULE_SYMBOL = "<module>"


@dataclass
class Chunk:
    """인덱싱 단위 청크."""

    path: str
    lang: str
    symbol: str
    signature: str
    start_line: int
    end_line: int
    text: str  # 원본 코드 조각

    def chunk_id(self) -> str:
        """재현 가능한 결정적 청크 ID: `{상대경로}#{symbol}#{start_line}`."""
        return f"{self.path}#{self.symbol}#{self.start_line}"


@lru_cache(maxsize=None)
def _make_splitter(encoding: str, chunk_size: int, overlap: int, lang: str) -> RecursiveCharacterTextSplitter:
    """토큰 기준 + 언어 경계 세퍼레이터를 결합한 스플리터를 생성(캐시)함."""
    lc_lang = _LC_LANGUAGE.get(lang)
    separators = (
        RecursiveCharacterTextSplitter.get_separators_for_language(lc_lang)
        if lc_lang is not None
        else None
    )
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoding,
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=separators,
        keep_separator=True,
    )


def _token_len(encoding: str, text: str) -> int:
    """tiktoken 토큰 수를 반환함."""
    import tiktoken

    enc = tiktoken.get_encoding(encoding)
    return len(enc.encode(text))


def extract_signature(segment: str) -> str:
    """def/class 헤더에서 시그니처(선언부)를 한 줄로 추출함.

    데코레이터 라인을 건너뛰고 `def`/`class` 라인부터 괄호 depth 0의 종결 `:`까지를 취함.
    """
    lines = segment.splitlines()
    start_idx = 0
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith(("def ", "async def ", "class ")):
            start_idx = i
            break
    header_region = "\n".join(lines[start_idx:])

    depth = 0
    out: list[str] = []
    for ch in header_region:
        out.append(ch)
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            break
    sig = "".join(out).strip()
    return " ".join(sig.split())  # 개행·연속공백 정규화


def _split_line_ranges(
    segment: str, base_start_line: int, encoding: str, chunk_size: int, overlap: int, lang: str
) -> list[tuple[str, int, int]]:
    """긴 세그먼트를 하위 분할하고 각 하위청크의 (텍스트, 시작라인, 끝라인)을 반환함.

    하위청크 라인 번호는 세그먼트 내 순차 탐색으로 근사 계산함(메타데이터 용도).
    """
    if _token_len(encoding, segment) <= chunk_size:
        n_lines = segment.count("\n")
        return [(segment, base_start_line, base_start_line + n_lines)]

    splitter = _make_splitter(encoding, chunk_size, overlap, lang)
    parts = splitter.split_text(segment)
    results: list[tuple[str, int, int]] = []
    cursor = 0
    for part in parts:
        if not part.strip():
            continue
        probe = part[:60]
        idx = segment.find(probe, cursor)
        if idx == -1:
            idx = segment.find(probe)
        if idx == -1:
            idx = cursor
        start_line = base_start_line + segment.count("\n", 0, idx)
        end_line = start_line + part.count("\n")
        results.append((part, start_line, end_line))
        cursor = idx + max(1, len(part) // 2)  # 오버랩 고려하여 절반만 전진
    return results


def _chunk_python(path: str, source: str, settings: Settings) -> list[Chunk]:
    """Python: AST 기반 최상위 함수/클래스 + 모듈 레벨 세그먼트로 청킹함."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _chunk_fallback(path, "python", source, settings)

    source_lines = source.splitlines()
    total = len(source_lines)
    enc, cs, ov = settings.tiktoken_encoding, settings.chunk_size, settings.chunk_overlap

    chunks: list[Chunk] = []
    covered: set[int] = set()

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        # 데코레이터 포함 시작 라인
        deco_lines = [d.lineno for d in getattr(node, "decorator_list", [])]
        start = min([node.lineno] + deco_lines)
        end = node.end_lineno or start
        covered.update(range(start, end + 1))

        segment = "\n".join(source_lines[start - 1 : end])
        signature = extract_signature(segment)
        for text, s_line, e_line in _split_line_ranges(segment, start, enc, cs, ov, "python"):
            chunks.append(
                Chunk(
                    path=path, lang="python", symbol=node.name, signature=signature,
                    start_line=s_line, end_line=e_line, text=text,
                )
            )

    # 모듈 레벨(함수/클래스 밖) 연속 라인 세그먼트
    uncovered = sorted(set(range(1, total + 1)) - covered)
    for a, b in _group_consecutive(uncovered):
        segment = "\n".join(source_lines[a - 1 : b])
        if not segment.strip():
            continue
        for text, s_line, e_line in _split_line_ranges(segment, a, enc, cs, ov, "python"):
            chunks.append(
                Chunk(
                    path=path, lang="python", symbol=MODULE_SYMBOL, signature="",
                    start_line=s_line, end_line=e_line, text=text,
                )
            )
    return chunks


_JS_SYMBOL_RE = re.compile(
    r"(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s*\*?\s*(?P<fn>[A-Za-z_$][\w$]*)"
    r"|class\s+(?P<cls>[A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+(?P<var>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>))"
)


def _js_symbol(text: str) -> tuple[str, str]:
    """JS/TS 청크에서 심볼명·시그니처를 best-effort 추출함."""
    m = _JS_SYMBOL_RE.search(text)
    if not m:
        return MODULE_SYMBOL, ""
    name = m.group("fn") or m.group("cls") or m.group("var") or MODULE_SYMBOL
    sig_line = text[m.start():].splitlines()[0].strip()
    return name, sig_line


def _chunk_js(path: str, lang: str, source: str, settings: Settings) -> list[Chunk]:
    """JS/TS: 언어 스플리터 분할 후 정규식 심볼 추출로 청킹함."""
    enc, cs, ov = settings.tiktoken_encoding, settings.chunk_size, settings.chunk_overlap
    splitter = _make_splitter(enc, cs, ov, lang)
    parts = splitter.split_text(source)
    chunks: list[Chunk] = []
    cursor = 0
    for part in parts:
        if not part.strip():
            continue
        idx = source.find(part[:60], cursor)
        if idx == -1:
            idx = source.find(part[:60])
        if idx == -1:
            idx = cursor
        start_line = 1 + source.count("\n", 0, idx)
        end_line = start_line + part.count("\n")
        cursor = idx + max(1, len(part) // 2)
        symbol, signature = _js_symbol(part)
        chunks.append(
            Chunk(
                path=path, lang=lang, symbol=symbol, signature=signature,
                start_line=start_line, end_line=end_line, text=part,
            )
        )
    return chunks


def _chunk_fallback(path: str, lang: str, source: str, settings: Settings) -> list[Chunk]:
    """미지원 언어·파싱 실패: 토큰 기준 폴백 분할(심볼=<module>)."""
    enc, cs, ov = settings.tiktoken_encoding, settings.chunk_size, settings.chunk_overlap
    chunks: list[Chunk] = []
    for text, s_line, e_line in _split_line_ranges(source, 1, enc, cs, ov, lang):
        if not text.strip():
            continue
        chunks.append(
            Chunk(
                path=path, lang=lang, symbol=MODULE_SYMBOL, signature="",
                start_line=s_line, end_line=e_line, text=text,
            )
        )
    return chunks


def _group_consecutive(nums: list[int]) -> list[tuple[int, int]]:
    """정렬된 정수 리스트를 연속 구간 [(start, end), ...]로 묶음."""
    if not nums:
        return []
    ranges: list[tuple[int, int]] = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append((start, prev))
            start = prev = n
    ranges.append((start, prev))
    return ranges


def _ipynb_to_source(raw: str) -> str:
    """.ipynb JSON에서 코드 셀을 python 소스로 결합함(매직/셸 라인은 주석 처리)."""
    import json

    try:
        nb = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    blocks: list[str] = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", [])
        code = "".join(src) if isinstance(src, list) else str(src)
        # 노트북 매직(%)·셸(!) 라인은 ast 파싱 오류 방지를 위해 주석화
        lines = ["# " + ln[1:] if ln.lstrip()[:1] in {"%", "!"} else ln for ln in code.splitlines()]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _dedupe_ids(chunks: list[Chunk]) -> list[Chunk]:
    """chunk_id 충돌 시 접미사를 부여하여 유일성을 보장함."""
    seen: dict[str, int] = {}
    for c in chunks:
        cid = c.chunk_id()
        if cid in seen:
            seen[cid] += 1
            c.symbol = f"{c.symbol}~{seen[cid]}"  # ID 유일화(결정적)
        else:
            seen[cid] = 0
    return chunks


def chunk_file(rel_path: str, lang: str, raw: str, settings: Settings) -> list[Chunk]:
    """파일 1건을 청크 리스트로 변환함(빈 청크 제외, ID 유일성 보장)."""
    source = raw
    if rel_path.endswith(".ipynb"):
        source = _ipynb_to_source(raw)
    if not source.strip():
        return []

    if lang == "python":
        chunks = _chunk_python(rel_path, source, settings)
    elif lang in ("javascript", "typescript"):
        chunks = _chunk_js(rel_path, lang, source, settings)
    else:
        chunks = _chunk_fallback(rel_path, lang, source, settings)

    chunks = [c for c in chunks if c.text.strip()]
    return _dedupe_ids(chunks)
