"""안정적·재현 가능한 ID 규칙.

testset-graphrag의 정답(gt_entities/gt_relations/gt_chunk_ids)이 그대로 소비하므로
동일 입력·동일 규칙에서 항상 같은 ID를 생성해야 함.

- chunk_id: `chunk_<전역순번>` (파일명 정렬 → 청크 순서 기준 결정적 부여)
- entity id: `ent_<slug>` (LLM 표기 흔들림을 slug 정규화로 흡수 → 병합 안정화)
- relation id: `rel_<source_slug>_<type>_<target_slug>`
"""
from __future__ import annotations

import re

# 영숫자·밑줄·유니코드 문자(한글 등)를 보존하고 그 외 기호만 구분자로 치환
_SLUG_RE = re.compile(r"[^\w]+", re.UNICODE)


def slug(text: str) -> str:
    """소문자화 후 영숫자·유니코드 문자(한글 등) 외 기호를 `_`로 치환, 양끝 `_` 제거.

    한글 엔티티명이 빈 문자열로 붕괴해 하나(ent_unknown)로 병합되는 문제를 방지함.
    """
    s = _SLUG_RE.sub("_", str(text).strip().lower()).strip("_")
    return s or "unknown"


def chunk_id(index: int) -> str:
    return f"chunk_{index}"


def entity_id(name: str) -> str:
    """엔티티명 → 안정 ID. 이미 `ent_` 접두면 그대로 유지."""
    name = str(name)
    if name.startswith("ent_"):
        return name
    return f"ent_{slug(name)}"


def _bare(entity_id_value: str) -> str:
    """`ent_` 접두를 제거한 slug 본체."""
    return entity_id_value[4:] if entity_id_value.startswith("ent_") else slug(entity_id_value)


def relation_id(source_id: str, rel_type: str, target_id: str) -> str:
    """관계 ID. 예: (ent_react, EXTENDS, ent_cot) → rel_react_extends_cot."""
    return f"rel_{_bare(source_id)}_{slug(rel_type)}_{_bare(target_id)}"
