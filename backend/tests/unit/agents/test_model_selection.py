"""Pure model-selection logic and DataAgent JSON-safe helpers."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.agents.data.data_agent import _json_safe
from backend.agents.model_selection.model_selection_agent import ALLOWED_MODELS, ModelSelectionAgent

COMPONENT = "Agents/ModelSelection"
STAGE = "selection"


@pytest.fixture
def agent():
    return ModelSelectionAgent()


def _pick(agent, **kwargs):
    defaults = dict(
        problem_type="classification",
        data_modality="tabular",
        rows=300,
        numeric_ratio=0.8,
        categorical_ratio=0.2,
        text_cols=[],
        catboost_available=False,
        xgboost_available=False,
        lightgbm_available=False,
        profile={},
    )
    defaults.update(kwargs)
    return agent._select_model(**defaults)


def test_text_classification_forced_tfidf(agent):
    m, f, _, conf = _pick(agent, problem_type="text_classification")
    assert m == "tfidf_logistic_regression"
    assert f is None


def test_small_numeric_classification_svm(agent):
    m, f, _, conf = _pick(agent, rows=300, numeric_ratio=0.9)
    assert m == "svm"
    assert f == "logistic_regression"


def test_small_mixed_classification_rf(agent):
    m, f, _, conf = _pick(agent, rows=300, numeric_ratio=0.5)
    assert m == "random_forest"
    assert f == "logistic_regression"


def test_high_categorical_catboost(agent):
    m, f, _, conf = _pick(agent, rows=1000, categorical_ratio=0.5, catboost_available=True)
    assert m == "catboost"
    assert f == "random_forest"


def test_large_numeric_regression_ridge(agent):
    m, f, _, conf = _pick(agent, problem_type="regression", rows=300, numeric_ratio=0.9)
    assert m == "ridge"
    assert f == "linear_regression"


def test_unknown_problem_returns_empty(agent):
    m, f, reasons, _ = _pick(agent, problem_type="bogus")
    assert m == ""
    assert f is None
    assert reasons


def test_allowed_models_whitelist_consistent_with_selector_bug():
    """BUG-AGENT-01: ``_select_model`` can return 'svm' (classification) and
    'ridge' (regression), but the ``ALLOWED_MODELS`` whitelist does not
    contain either. ModelSelectionAgent.run then detects the selected model
    as 'not in allowed list' and silently swaps to the fallback, so the
    SVM/Ridge selection decision is thrown away."""
    from backend.tests.assertions import check

    for model in ("svm", "ridge"):
        present = any(model in wl for wl in ALLOWED_MODELS.values())
        check(
            present,
            "AGENT-001", COMPONENT, STAGE,
            f"'{model}' must be present in the ALLOWED_MODELS whitelist "
            f"(it is returned by _select_model)",
            "NOT in any allowed list",
            artifact="ModelSelectionAgent.ALLOWED_MODELS",
            root_cause="model_selection_agent.py whitelist is missing svm/ridge that _select_model returns; run() swaps to fallback",
            severity="MEDIUM",
        )


# --------------------------------------------------------------------------
# _json_safe
# --------------------------------------------------------------------------

def test_json_safe_numpy_and_pandas():
    assert _json_safe(np_int(3)) == 3
    assert _json_safe(np_float(2.5)) == 2.5
    assert _json_safe(float("inf")) is None
    assert _json_safe(pd.NA) is None
    assert _json_safe("text") == "text"


def test_json_safe_nested():
    assert _json_safe({"a": [np_int(1), None], "b": float("nan")}) == \
        {"a": [1, None], "b": None}


def np_int(v):
    import numpy as np
    return np.int64(v)


def np_float(v):
    import numpy as np
    return np.float64(v)