"""검색 품질 평가 (§3.7) — RAGAS + GraphRAG Local NDCG.

- RAG(코드) 테스트셋: 코드 하이브리드 리트리버 → 문맥 + 답변 생성 → RAGAS 4지표 + 청크 NDCG
- GraphRAG(교재) 테스트셋: GraphRAG 리트리버 → 문맥 + 답변 생성 → RAGAS 4지표
  Local류(FACTOID/RELATIONAL/MULTI_HOP 등, gt_chunk_ids 보유) → NDCG 별도 계산
- RAGAS 판정 LLM·임베딩: OpenAI(gpt-4o-mini, text-embedding-3-large)
- 산출: datasets/eval-report.json (지표별 실측 평균·NDCG·버전·일시·건수)

실행: python -m app.eval.run_eval [--dataset rag|graphrag|both] [--limit N]
"""
from __future__ import annotations

# ragas import 전 vertexai shim 설치(필수)
from . import ragas_compat  # noqa: F401  (side-effect: install shim)

import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from app.common.config import PROJECT_ROOT
from app.common.llm_router import LLMRouter
from app.common.logging_utils import get_logger
from app.search.synthesize import synthesize_summary

log = get_logger()

DATASETS_DIR = PROJECT_ROOT / "datasets"
REPORT_PATH = DATASETS_DIR / "eval-report.json"
SAMPLES_PATH = DATASETS_DIR / "eval-samples.jsonl"

TOP_K = 10           # 검색·NDCG 대상 상위 개수
CONTEXT_K = 8        # RAGAS 문맥 개수
EVAL_VERSION = "1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ndcg_at_k(ranked_ids: list[str], gt_ids: set, k: int = TOP_K) -> float:
    """이진 관련도 NDCG@k (gt에 포함되면 1)."""
    if not gt_ids:
        return float("nan")
    rels = [1.0 if cid in gt_ids else 0.0 for cid in ranked_ids[:k]]
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
    ideal = min(len(gt_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal))
    return (dcg / idcg) if idcg > 0 else 0.0


# ---------------------------------------------------------------------- #
# 샘플 생성(검색 + 답변)
# ---------------------------------------------------------------------- #
def _retrieve_rag(query: str) -> tuple[list[str], list[str]]:
    from rag.retriever import get_code_retriever
    hits = get_code_retriever().retrieve(query, top_k=TOP_K)
    contexts = [f"{h.get('signature', '')}\n{h.get('text', '')}" for h in hits]
    chunk_ids = [h.get("chunk_id", "") for h in hits]
    return contexts, chunk_ids


def _retrieve_graphrag(query: str) -> tuple[list[str], list[str]]:
    from kg.retriever import get_graph_retriever
    out = get_graph_retriever().retrieve(query)
    chunks = out.get("chunks", [])
    contexts = [c.get("text", "") for c in chunks]
    chunk_ids = [c.get("chunk_id", "") for c in chunks]
    # 커뮤니티 요약도 문맥에 보강(Global 답변 근거)
    for c in out.get("communities", [])[:3]:
        contexts.append(c.get("summary", ""))
    return contexts[:TOP_K + 3], chunk_ids


def build_sample(item: dict, kind: str, router: LLMRouter) -> dict:
    """단일 테스트 항목 → 검색·생성 샘플."""
    query = item["query"]
    if kind == "rag":
        contexts, chunk_ids = _retrieve_rag(query)
    else:
        contexts, chunk_ids = _retrieve_graphrag(query)

    context_str = "\n\n".join(f"[{i+1}] {c[:600]}" for i, c in enumerate(contexts[:CONTEXT_K]))
    response, _ = synthesize_summary(query, context_str, "openai", router)

    gt_ids = set(item.get("gt_chunk_ids", []) or [])
    ndcg = ndcg_at_k(chunk_ids, gt_ids)
    return {
        "id": item.get("id"),
        "kind": kind,
        "type": item.get("type"),
        "user_input": query,
        "retrieved_contexts": contexts[:CONTEXT_K],
        "retrieved_chunk_ids": chunk_ids,
        "response": response or "",
        "reference": item.get("expected_answer", "") or "",
        "gt_chunk_ids": list(gt_ids),
        "ndcg": ndcg,
    }


def _warmup(kind: str) -> None:
    """병렬 실행 전 리트리버 싱글턴을 단일 스레드로 초기화(Chroma 클라이언트 레이스 방지)."""
    if kind == "rag":
        from rag.retriever import get_code_retriever
        get_code_retriever().retrieve("warmup", top_k=1)
    else:
        from kg.retriever import get_graph_retriever
        get_graph_retriever().retrieve("warmup")


def build_samples(items: list[dict], kind: str, router: LLMRouter, workers: int = 4) -> list[dict]:
    log.info("[eval] %s: %d건 검색·생성 시작", kind, len(items))
    _warmup(kind)
    samples: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for s in ex.map(lambda it: build_sample(it, kind, router), items):
            samples.append(s)
            log.info("[eval] %s %s ndcg=%.3f resp=%dchars", kind, s["id"],
                     s["ndcg"] if s["ndcg"] == s["ndcg"] else float("nan"), len(s["response"]))
    return samples


# ---------------------------------------------------------------------- #
# RAGAS 실행
# ---------------------------------------------------------------------- #
def run_ragas(samples: list[dict]) -> dict:
    """RAGAS 4지표 실측(Context Recall·Precision·Faithfulness·Answer Relevancy)."""
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )
    from ragas.run_config import RunConfig
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    import os
    key = os.getenv("OPENAI_API_KEY")
    judge = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=key, temperature=0))
    emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-large", api_key=key))

    rows = [{
        "user_input": s["user_input"],
        "retrieved_contexts": s["retrieved_contexts"] or [""],
        "response": s["response"] or " ",
        "reference": s["reference"] or " ",
    } for s in samples]
    dataset = EvaluationDataset.from_list(rows)
    metrics = [
        LLMContextRecall(), LLMContextPrecisionWithReference(),
        Faithfulness(), ResponseRelevancy(),
    ]
    log.info("[eval] RAGAS 실행: %d 샘플 × %d 지표", len(rows), len(metrics))
    result = evaluate(dataset=dataset, metrics=metrics, llm=judge, embeddings=emb,
                      run_config=RunConfig(max_workers=4, timeout=120), show_progress=True)
    df = result.to_pandas()
    metric_cols = [c for c in df.columns if c in
                   ("context_recall", "llm_context_precision_with_reference",
                    "faithfulness", "answer_relevancy", "nv_context_precision", "semantic_similarity")]
    means = {c: float(df[c].mean(skipna=True)) for c in metric_cols}
    return {"metrics": means, "n": len(rows)}


# ---------------------------------------------------------------------- #
# 메인
# ---------------------------------------------------------------------- #
def _agg_ndcg(samples: list[dict]) -> dict:
    vals = [s["ndcg"] for s in samples if s["ndcg"] == s["ndcg"]]  # NaN 제외
    return {"mean_ndcg": (sum(vals) / len(vals)) if vals else None, "n_with_gt": len(vals)}


def evaluate_dataset(kind: str, path: Path, router: LLMRouter, limit: int | None) -> dict:
    items = load_jsonl(path)
    if limit:
        items = items[:limit]
    samples = build_samples(items, kind, router)
    # 샘플 저장(재현·RAGAS 재실행용)
    with SAMPLES_PATH.open("a", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    ragas_res = {}
    try:
        ragas_res = run_ragas(samples)
    except Exception as e:  # noqa: BLE001 — RAGAS 실패해도 NDCG·생성 통계는 보고
        log.exception("[eval] RAGAS 실패")
        ragas_res = {"error": str(e)}
    return {
        "dataset": kind,
        "n": len(samples),
        "ragas": ragas_res,
        "ndcg": _agg_ndcg(samples),
        "ndcg_by_type": _ndcg_by_type(samples),
    }


def _ndcg_by_type(samples: list[dict]) -> dict:
    by: dict[str, list[float]] = {}
    for s in samples:
        if s["ndcg"] == s["ndcg"]:
            by.setdefault(s["type"] or "?", []).append(s["ndcg"])
    return {t: {"mean_ndcg": sum(v) / len(v), "n": len(v)} for t, v in by.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["rag", "graphrag", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if SAMPLES_PATH.exists():
        SAMPLES_PATH.unlink()
    router = LLMRouter()
    report = {
        "generated_at": _now_iso(),
        "eval_version": EVAL_VERSION,
        "judge_model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-large",
        "top_k": TOP_K,
        "context_k": CONTEXT_K,
        "datasets": {},
    }
    targets = []
    if args.dataset in ("rag", "both"):
        targets.append(("rag", DATASETS_DIR / "testset-rag.jsonl"))
    if args.dataset in ("graphrag", "both"):
        targets.append(("graphrag", DATASETS_DIR / "testset-graphrag.jsonl"))

    for kind, path in targets:
        report["datasets"][kind] = evaluate_dataset(kind, path, router, args.limit)

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("[eval] 리포트 저장: %s", REPORT_PATH)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
