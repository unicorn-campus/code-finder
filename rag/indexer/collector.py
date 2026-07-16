"""코드 파일 수집 + 언어 판별 + 파일 해시(증분 인덱싱용).

- `base_dir` 하위를 재귀 순회하며 지원 확장자 파일만 수집함.
- 가상환경·패키지 캐시·빌드 산출물 디렉토리는 제외함.
- 파일 내용 SHA-256 해시로 변경분 판별에 사용함.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .config import Settings


@dataclass(frozen=True)
class FileRecord:
    """수집된 코드 파일 1건."""

    abs_path: Path
    rel_path: str  # base_dir 기준 상대경로(POSIX 형식)
    lang: str
    size: int
    sha256: str


def _is_excluded_dir(path: Path, settings: Settings) -> bool:
    """경로 세그먼트에 제외 디렉토리가 포함되는지 판별함."""
    return any(part in settings.exclude_dir_parts for part in path.parts)


def compute_sha256(data: bytes) -> str:
    """바이트 내용의 SHA-256 16진 다이제스트를 반환함."""
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path) -> str:
    """UTF-8로 파일을 읽되, 디코드 실패 문자는 대체함."""
    return path.read_text(encoding="utf-8", errors="replace")


def iter_code_files(settings: Settings) -> Iterator[FileRecord]:
    """`base_dir` 하위 지원 코드 파일을 FileRecord로 순회 생성함."""
    base = settings.base_dir
    if not base.exists():
        raise FileNotFoundError(f"인덱싱 대상 디렉토리 없음: {base}")

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        lang = settings.lang_for(suffix)
        if lang is None:
            continue
        # base_dir 이하의 상대경로로 제외 판별(상위 경로의 우연한 일치 방지)
        rel = path.relative_to(base)
        if _is_excluded_dir(rel, settings):
            continue
        if path.name.endswith(settings.exclude_suffixes):
            continue
        if settings.is_excluded_path(rel.as_posix()):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size == 0 or size > settings.max_file_bytes:
            continue
        data = path.read_bytes()
        yield FileRecord(
            abs_path=path,
            rel_path=rel.as_posix(),
            lang=lang,
            size=size,
            sha256=compute_sha256(data),
        )
