"""멀티 LLM 라우터 (§3.2) — 태스크별 모델 선정·config 관리·Groq 폴백.

라우팅 정책(근거는 app/README.md 기록):
- routing/tool: Groq LPU gpt-oss-120b [고정] — 저지연 LPU로 ReAct 도구 라우팅에 적합
- code_synthesis: Claude Sonnet 5 — 코드 이해·설명 강점
- summary: OpenAI(기본, 비용·속도) / Gemini(대안, 다국어) — 요청 `llm` 힌트로 override
- provider 호출 실패 시 기본(Groq)로 폴백
"""
from __future__ import annotations

from typing import Optional

from langchain_core.language_models import BaseChatModel

from .config import ProviderConfig, Settings, load_settings
from .logging_utils import get_logger

log = get_logger()

# 힌트/태스크 → provider 매핑
TASK_ROUTING = {
    "summary": "openai",   # 개념 요약·다국어 기본
    "code": "claude",      # 코드 설명·예제 합성
}


class LLMRouter:
    """provider별 ChatModel 인스턴스 생성·캐시 및 태스크 라우팅."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self.p: ProviderConfig = self.settings.provider
        self._cache: dict[str, BaseChatModel] = {}

    # ------------------------------------------------------------------ #
    # provider별 모델 팩토리
    # ------------------------------------------------------------------ #
    def available(self, provider: str) -> bool:
        keys = {
            "groq": self.p.groq_api_key,
            "claude": self.p.claude_api_key,
            "openai": self.p.openai_api_key,
            "gemini": self.p.gemini_api_key,
        }
        return bool(keys.get(provider))

    def model_name(self, provider: str) -> str:
        return {
            "groq": self.p.groq_model,
            "claude": self.p.claude_model,
            "openai": self.p.openai_model,
            "gemini": self.p.gemini_model,
        }[provider]

    def build(self, provider: str) -> BaseChatModel:
        """provider ChatModel 생성(캐시). 키 부재 시 ValueError."""
        if provider in self._cache:
            return self._cache[provider]
        if not self.available(provider):
            raise ValueError(f"provider '{provider}' API 키 미설정")

        temp, timeout, retries = self.p.temperature, self.p.timeout, self.p.max_retries
        if provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(model=self.p.groq_model, api_key=self.p.groq_api_key,
                           temperature=temp, timeout=timeout, max_retries=retries)
        elif provider == "claude":
            from langchain_anthropic import ChatAnthropic
            # claude-sonnet-5 계열은 temperature 파라미터를 지원하지 않음("deprecated for this model")
            # → temperature 미전달(모델 기본값 사용). 재현성 [고정] 대상은 Groq 라우팅 LLM임.
            llm = ChatAnthropic(model=self.p.claude_model, api_key=self.p.claude_api_key,
                                timeout=timeout, max_retries=retries)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=self.p.openai_model, api_key=self.p.openai_api_key,
                             temperature=temp, timeout=timeout, max_retries=retries)
        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model=self.p.gemini_model, google_api_key=self.p.gemini_api_key,
                                         temperature=temp, timeout=timeout, max_retries=retries)
        else:
            raise ValueError(f"알 수 없는 provider: {provider}")
        self._cache[provider] = llm
        return llm

    # ------------------------------------------------------------------ #
    # 라우팅
    # ------------------------------------------------------------------ #
    def routing_llm(self) -> BaseChatModel:
        """ReAct 도구 라우팅 LLM [고정] Groq."""
        return self.build("groq")

    def resolve(self, task: str, hint: Optional[str] = None) -> tuple[str, BaseChatModel]:
        """태스크·힌트 → (provider, llm). 실패 시 Groq 폴백.

        - hint(claude|openai|gemini) 지정 시 해당 provider로 강제(합성 모델 힌트)
        - 미지정 시 TASK_ROUTING 기본 매핑
        """
        provider = hint if hint in ("claude", "openai", "gemini") else TASK_ROUTING.get(task, "openai")
        for candidate in (provider, "groq"):
            try:
                llm = self.build(candidate)
                if candidate != provider:
                    log.warning("[synthesis] provider '%s' 사용 불가 → '%s' 폴백", provider, candidate)
                return candidate, llm
            except Exception as e:  # noqa: BLE001 — 폴백 목적
                log.warning("[synthesis] provider '%s' 초기화 실패: %s", candidate, e)
        raise RuntimeError("사용 가능한 합성 LLM provider 없음(Groq 폴백 포함 실패)")

    def used_models(self, summary_provider: str, code_provider: str) -> dict[str, str]:
        """used_models 맵(라우팅·요약·코드합성 모델명)."""
        return {
            "routing": f"groq/{self.p.groq_model}",
            "summary": f"{summary_provider}/{self.model_name(summary_provider)}",
            "code_synthesis": f"{code_provider}/{self.model_name(code_provider)}",
        }
