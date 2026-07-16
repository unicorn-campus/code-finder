"""서비스 전역 설정 모듈.

- 시크릿(LLM·검색 API 키)은 프로젝트 루트 `.env`에서 로드하여 Config와 소스를 분리함.
- provider별 모델·타임아웃·재시도 등 라우팅 정책은 본 모듈에서 관리함(하드코딩 금지, 환경변수 override 가능).
- `.env` 실제 변수명과 대조 후 사용: Anthropic=CLAUDE_API_KEY, Gemini=GEMINI_API_KEY,
  Cohere=COHERE_API_KEY(과거 오탈자 COHREE_API_KEY 폴백), YouTube=YOUTUBE_API_KEY.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 경로 상수 (app/common/config.py 기준 프로젝트 루트 산출)
COMMON_DIR = Path(__file__).resolve().parent        # app/common
APP_DIR = COMMON_DIR.parent                          # app
PROJECT_ROOT = APP_DIR.parent                        # code-finder
ENV_PATH = PROJECT_ROOT / ".env"
CHECKPOINT_DIR = APP_DIR / "checkpoints"

load_dotenv(ENV_PATH, override=False)


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if v not in (None, "") else default


def _get_int(key: str, default: int) -> int:
    v = os.getenv(key)
    try:
        return int(v) if v not in (None, "") else default
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    v = os.getenv(key)
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


@dataclass
class ProviderConfig:
    """멀티 LLM provider별 접속·모델 설정."""

    # 기본 추론·도구 라우팅 [고정]: Groq LPU gpt-oss-120b, temperature 0, timeout 30초, 429 백오프 2회
    routing_provider: str = "groq"
    groq_api_key: Optional[str] = field(default_factory=lambda: _get("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _get("LLM_ROUTING_MODEL", "openai/gpt-oss-120b"))

    # 코드 설명·예제 합성: Claude Sonnet 5 (코드 이해 강점)
    claude_api_key: Optional[str] = field(default_factory=lambda: _get("CLAUDE_API_KEY"))
    claude_model: str = field(default_factory=lambda: _get("LLM_CODE_MODEL", "claude-sonnet-5"))

    # 개념 요약·다국어: OpenAI(비용·속도 기준 기본) / Gemini(대안)
    openai_api_key: Optional[str] = field(default_factory=lambda: _get("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _get("LLM_SUMMARY_MODEL", "gpt-4o-mini"))

    gemini_api_key: Optional[str] = field(default_factory=lambda: _get("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _get("LLM_GEMINI_MODEL", "gemini-2.5-flash"))

    # 공통 LLM 파라미터 [고정]
    temperature: float = 0.0
    timeout: int = field(default_factory=lambda: _get_int("LLM_TIMEOUT", 30))
    max_retries: int = field(default_factory=lambda: _get_int("LLM_MAX_RETRIES", 2))


@dataclass
class RerankConfig:
    """Post 처리 Cohere 리랭킹 [고정]."""

    # .env 실제 변수명(COHERE_API_KEY) 우선, 과거 오탈자(COHREE_API_KEY) 폴백
    api_key: Optional[str] = field(
        default_factory=lambda: _get("COHERE_API_KEY") or _get("COHREE_API_KEY"))
    model: str = field(default_factory=lambda: _get("RERANK_MODEL", "rerank-multilingual-v3.0"))
    top_n: int = field(default_factory=lambda: _get_int("RERANK_TOP_N", 8))


@dataclass
class FanoutConfig:
    """4종 소스 병렬 팬아웃·소스별 타임아웃(도달 시간 KPI 보호) [고정]."""

    code_timeout: float = field(default_factory=lambda: _get_float("FANOUT_CODE_TIMEOUT", 12.0))
    textbook_timeout: float = field(default_factory=lambda: _get_float("FANOUT_TEXTBOOK_TIMEOUT", 12.0))
    # 웹 소스 팬아웃 예산: DDG 검색 + 병렬 페이지 스크레이프 총예산.
    # §3.8 페이지 요청 타임아웃 5초는 WebConfig.page_timeout(개별 요청)에 별도 적용됨.
    web_timeout: float = field(default_factory=lambda: _get_float("FANOUT_WEB_TIMEOUT", 8.0))
    youtube_timeout: float = field(default_factory=lambda: _get_float("FANOUT_YOUTUBE_TIMEOUT", 15.0))
    # ReAct 반복 상한 [고정] 7회 → LangGraph recursion_limit(super-step 기준 ≈ 2*iter+1)
    react_max_iterations: int = field(default_factory=lambda: _get_int("REACT_MAX_ITERATIONS", 7))


@dataclass
class Settings:
    """백엔드 검색 서비스 전역 설정."""

    provider: ProviderConfig = field(default_factory=ProviderConfig)
    rerank: RerankConfig = field(default_factory=RerankConfig)
    fanout: FanoutConfig = field(default_factory=FanoutConfig)

    # 세션 체크포인트 [고정]: 사용자 선택 = SqliteSaver(로컬 파일)
    checkpointer: str = field(default_factory=lambda: _get("CHECKPOINTER", "sqlite"))
    sqlite_path: str = field(default_factory=lambda: _get(
        "CHECKPOINT_SQLITE", str(CHECKPOINT_DIR / "search.sqlite")))

    youtube_api_key: Optional[str] = field(default_factory=lambda: _get("YOUTUBE_API_KEY"))

    @property
    def recursion_limit(self) -> int:
        return self.fanout.react_max_iterations * 2 + 1


def load_settings() -> Settings:
    return Settings()
