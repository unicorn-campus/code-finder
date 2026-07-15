"""인덱서 설정 로더.

- 비밀정보(API Key)는 프로젝트 루트 `.env`에서 로드하여 Config와 소스를 분리함.
- 경로·모델·청킹 파라미터 등 비-비밀 설정은 본 모듈의 기본값으로 관리함.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트: rag/indexer/config.py 기준 2단계 상위 → code-finder/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

# 인덱스 산출물 루트: rag/store/
STORE_DIR = PROJECT_ROOT / "rag" / "store"
CHROMA_DIR = STORE_DIR / "chroma"
REPORT_PATH = STORE_DIR / "index-report.json"
FILE_MANIFEST_PATH = STORE_DIR / "file-manifest.json"
CHUNK_MANIFEST_PATH = STORE_DIR / "chunks-manifest.jsonl"

# 언어 판별: 확장자 → 언어 라벨
EXT_LANG = {
    ".py": "python",
    ".ipynb": "python",  # 노트북 코드 셀을 python 소스로 취급
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# 수집 제외 디렉토리(경로 세그먼트 기준 완전일치)
EXCLUDE_DIR_PARTS = {
    ".git", ".venv", "venv", "env", "node_modules", "site-packages",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ipynb_checkpoints",
    "dist", "build", ".next", ".turbo", ".cache", "vendor",
}

# 수집 제외 파일 접미사(빌드 산출물·압축본)
EXCLUDE_SUFFIXES = (".min.js", ".bundle.js", ".d.ts")

# 단일 파일 최대 크기(bytes). 초과 시 스킵(미니파이·데이터 덤프 방지)
MAX_FILE_BYTES = 400_000


@dataclass
class Settings:
    """인덱서 실행 설정."""

    # 입력
    base_dir: Path = Path(os.path.expanduser("~/workspace/aistudy/hands-on"))

    # 임베딩
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"

    # 청킹(토큰 단위) [고정]
    chunk_size: int = 500
    chunk_overlap: int = 100
    tiktoken_encoding: str = "cl100k_base"  # text-embedding-3-* 계열 인코딩

    # 임베딩 배치·재시도
    embed_batch_size: int = 128
    embed_concurrency: int = 4
    embed_max_retries: int = 6
    embed_base_delay: float = 1.0  # 지수 백오프 기준 지연(초)

    # 저장
    collection_name: str = "code_chunks"
    chroma_dir: Path = CHROMA_DIR

    # 수집 대상 확장자
    include_exts: tuple[str, ...] = tuple(EXT_LANG.keys())
    exclude_dir_parts: frozenset[str] = field(default_factory=lambda: frozenset(EXCLUDE_DIR_PARTS))
    exclude_suffixes: tuple[str, ...] = EXCLUDE_SUFFIXES
    max_file_bytes: int = MAX_FILE_BYTES

    @classmethod
    def load(cls, base_dir: str | os.PathLike | None = None) -> "Settings":
        """`.env`에서 키를 로드하여 Settings를 생성함."""
        load_dotenv(dotenv_path=ENV_PATH, override=False)
        kwargs: dict = {"openai_api_key": os.getenv("OPENAI_API_KEY", "")}
        if base_dir is not None:
            kwargs["base_dir"] = Path(os.path.expanduser(str(base_dir)))
        return cls(**kwargs)

    def lang_for(self, suffix: str) -> str | None:
        """확장자에 대응하는 언어 라벨을 반환(미지원 시 None)."""
        return EXT_LANG.get(suffix.lower())
