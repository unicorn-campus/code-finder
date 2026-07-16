"""NDCG 계산 단위 테스트."""
from __future__ import annotations

import math

from app.eval.run_eval import ndcg_at_k


def test_perfect_ranking():
    assert ndcg_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0


def test_no_hits():
    assert ndcg_at_k(["x", "y"], {"a", "b"}, k=2) == 0.0


def test_partial_ranking_between_0_and_1():
    v = ndcg_at_k(["x", "a", "y"], {"a"}, k=3)
    assert 0.0 < v < 1.0


def test_top_rank_beats_low_rank():
    top = ndcg_at_k(["a", "x", "y"], {"a"}, k=3)
    low = ndcg_at_k(["x", "y", "a"], {"a"}, k=3)
    assert top > low


def test_empty_gt_returns_nan():
    assert math.isnan(ndcg_at_k(["a"], set()))
