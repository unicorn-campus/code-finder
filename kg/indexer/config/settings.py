"""인덱서 설정 모듈.

- 시크릿(API 키·Neo4j 접속정보)은 프로젝트 루트 `.env`에서 로드
- 엔티티/관계 타입 목록은 `graph_schema.yaml`에서 로드 (코드 하드코딩 금지)
- 비시크릿 튜너블은 환경변수로 override 가능
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# 경로 상수 (파일 위치 기준으로 프로젝트 루트 산출)
CONFIG_DIR = Path(__file__).resolve().parent          # kg/indexer/config
INDEXER_DIR = CONFIG_DIR.parent                        # kg/indexer
KG_DIR = INDEXER_DIR.parent                            # kg
PROJECT_ROOT = KG_DIR.parent                           # code-finder
SCHEMA_PATH = CONFIG_DIR / "graph_schema.yaml"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if v not in (None, "") else default


def _get_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v in (None, ""):
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Neo4jConfig:
    """Neo4j 접속 정보 (전용 컨테이너 code-finder-neo4j 기본값)."""
    uri: str = field(default_factory=lambda: _get("NEO4J_URI", "bolt://localhost:7690"))
    username: str = field(default_factory=lambda: _get("NEO4J_USERNAME", "neo4j"))
    password: str = field(default_factory=lambda: _get("NEO4J_PASSWORD", "codefinder"))
    database: str = field(default_factory=lambda: _get("NEO4J_DATABASE", "neo4j"))


@dataclass
class LLMConfig:
    """추출·요약 LLM (Groq LPU, gpt-oss-120b). 재현성 우선(temperature 0)."""
    api_key: Optional[str] = field(default_factory=lambda: _get("GROQ_API_KEY"))
    model: str = field(default_factory=lambda: _get("KG_LLM_MODEL", "openai/gpt-oss-120b"))
    temperature: float = 0.0
    timeout: int = 30
    max_retries: int = 2
    max_concurrency: int = field(default_factory=lambda: int(_get("KG_EXTRACT_CONCURRENCY", "5")))


@dataclass
class EmbeddingConfig:
    """Local 검색·NDCG용 벡터 인덱스 임베딩 (OpenAI text-embedding-3-large)."""
    enabled: bool = field(default_factory=lambda: _get_bool("KG_VECTOR_INDEX", True))
    api_key: Optional[str] = field(default_factory=lambda: _get("OPENAI_API_KEY"))
    model: str = field(default_factory=lambda: _get("KG_EMBEDDING_MODEL", "text-embedding-3-large"))


@dataclass
class SplitConfig:
    """마크다운 헤더 분할 + 크기 보정 설정."""
    headers_to_split_on: list = field(default_factory=lambda: [
        ("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4"),
    ])
    chunk_size: int = 1200        # 문자 기준
    chunk_overlap: int = 150


@dataclass
class GraphSchema:
    """graph_schema.yaml에서 로드한 엔티티/관계 타입."""
    allowed_nodes: list
    allowed_relationships: list   # list of [source, type, target]
    node_properties: list

    @property
    def relationship_tuples(self) -> list:
        """LLMGraphTransformer용 3-튜플 목록."""
        return [tuple(r) for r in self.allowed_relationships]

    @property
    def relationship_types(self) -> list:
        return sorted({r[1] for r in self.allowed_relationships})


def load_schema(path: Path = SCHEMA_PATH) -> GraphSchema:
    """엔티티/관계 타입 스키마를 YAML에서 로드."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return GraphSchema(
        allowed_nodes=list(data["allowed_nodes"]),
        allowed_relationships=list(data["allowed_relationships"]),
        node_properties=list(data.get("node_properties", [])),
    )


@dataclass
class Settings:
    """인덱서 전역 설정."""
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    textbook_glob: str = field(default_factory=lambda: _get(
        "KG_TEXTBOOK_GLOB", "~/workspace/aistudy/agentic-ai/textbook/*.md"))
    sqlite_path: str = field(default_factory=lambda: _get(
        "KG_SQLITE_PATH", str(INDEXER_DIR / "checkpoints" / "indexer.sqlite")))
    extract_report_path: str = field(default_factory=lambda: _get(
        "KG_EXTRACT_REPORT", str(INDEXER_DIR / "checkpoints" / "extract_report.json")))
    community_seed: int = 42       # Louvain 재현성용 시드

    def schema(self) -> GraphSchema:
        return load_schema()


def load_settings() -> Settings:
    return Settings()
