"""Insight ranker / validator tests (LLM-free, deterministic)."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.models.insight import InsightCandidate
from backend.agents.insights.insight_ranker import (
    MIN_CORRELATION_KEEP,
    MIN_FEATURE_KEEP,
    MIN_GROUP_DIFF_KEEP,
    _assign_severity,
    _safe_float,
    rank_insights,
)
from backend.tests.assertions import check

COMPONENT = "Agents/InsightRanker"
STAGE = "ranking"


def _cand(type_, evidence=None, confidence=0.8):
    return InsightCandidate(
        type=type_, title="t", finding="f", evidence=evidence or {}, confidence=confidence,
        importance_score=0.0,
    )


def test_safe_float_nan_defaults():
    assert _safe_float(float("nan")) == 0.0
    assert _safe_float(None) == 0.0
    assert _safe_float("abc") == 0.0
    assert _safe_float("42") == 42.0


def test_empty_rank_returns_empty():
    assert rank_insights([]) == []


def test_rank_sorts_by_score_descending():
    weak = _cand("correlation", {"correlation": 0.2}, confidence=0.3)
    strong = _cand("correlation", {"correlation": 0.95, "p_value": 0.01}, confidence=0.9)
    ranked = rank_insights([weak, strong])
    assert ranked[0] is strong
    assert ranked[1] is weak
    assert ranked[0].evidence["_rank_score"] >= ranked[1].evidence["_rank_score"]


def test_feature_importance_relative_normalization():
    """The dominant feature must keep the highest relative_importance."""
    strong = _cand("feature_importance", {"importance": 0.9, "relative_importance": 0.9})
    weak = _cand("feature_importance", {"importance": 0.1, "relative_importance": 0.1})
    ranked = rank_insights([weak, strong])
    for i in ranked:
        ev = i.evidence
        assert 0.0 <= ev["relative_importance"] <= 1.0
        assert ev["importance_scale"] == "within_model_relative"
    assert ranked[0].evidence["relative_importance"] == pytest.approx(0.9)
    assert ranked[0].evidence["relative_importance"] >= ranked[1].evidence["relative_importance"]


def test_assign_severity_outlier_mapping():
    assert _assign_severity(_cand("outlier", {"severity": "severe"})) == "strong"
    assert _assign_severity(_cand("outlier", {"severity": "mild"})) == "moderate"


def test_assign_severity_low_baseline_capped():
    ev = {"gap_reliability": "low_baseline", "difference_percent": 300, "p_value": 0.001}
    assert _assign_severity(_cand("risk_segment", ev)) == "moderate"


def test_assign_severity_non_significant_capped():
    ev = {"difference_percent": 120, "p_value": 0.4}
    assert _assign_severity(_cand("group_difference", ev)) in ("moderate", "weak")


def test_should_keep_correlation_threshold():
    from backend.agents.insights.insight_ranker import _should_keep_insight

    keep = _cand("correlation", {"correlation": 0.6})
    drop = _cand("correlation", {"correlation": 0.1})
    assert _should_keep_insight(keep) is True
    assert _should_keep_insight(drop) is False


def test_min_price_constants_sane():
    assert 0 < MIN_CORRELATION_KEEP < 1
    assert MIN_GROUP_DIFF_KEEP > 0
    assert MIN_FEATURE_KEEP > 0