"""Integration: CSV upload -> pickle -> clean_data_tool (the DataAgent path).

This mirrors exactly the file-handling flow inside ``DataAgent.run``:
read_any_file(csv) -> raw.pkl -> clean_data_tool(raw.pkl) -> output.pkl.
It is deliberately cross-module to confirm the production compose path.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from backend.tests.assertions import check

COMPONENT = "Integration/CleanDataTool"
STAGE = "cleaning"


@pytest.fixture
def clean_data_tool():
    from backend.tools.cleaner import clean_data_tool

    return clean_data_tool


def _upload_csv_to_pickle(datasets_dir, tmp_path, name) -> str:
    """read_any_file -> raw.pkl (exactly like DataAgent.run step 1)."""
    from backend.tools.csv_reader import read_any_file

    src = datasets_dir / name
    raw_df = read_any_file(str(src))
    assert raw_df is not None and not raw_df.empty
    raw_pickle = str(tmp_path / "raw_dataset.pkl")
    raw_df.to_pickle(raw_pickle)
    return raw_pickle


def test_csv_to_pickle_to_clean_success(datasets_dir, tmp_path, clean_data_tool):
    """The packaged Data-Agent file flow returns success and writes a file."""
    raw_pickle = _upload_csv_to_pickle(datasets_dir, tmp_path, "tiny.csv")
    output = str(tmp_path / "cleaned_dataset.pkl")

    result = clean_data_tool(raw_pickle, output_path=output)
    assert result.get("status") == "success", result
    assert os.path.exists(output), "cleaned output pickle not written"
    out_df = pd.read_pickle(output)
    assert not out_df.empty


def test_csv_direct_to_clean_tool_fails_pickle_only_bug(datasets_dir, tmp_path, clean_data_tool):
    """BUG-TOOL-01 (integration-level): passing the CSV path directly to
    clean_data_tool reproduces the UnpicklingError surfaced as a generic
    "Cleaning failed: could not find MARK" error instead of reading the CSV."""
    src = datasets_dir / "tiny.csv"
    result = clean_data_tool(str(src), output_path=str(tmp_path / "out.pkl"))
    check(
        result.get("status") == "success",
        "TOOL-004", COMPONENT, STAGE,
        "clean_data_tool on a CSV path should return status='success' "
        "(DataAgent always pickles first so the bug hides in production)",
        f"got status={result.get('status')!r} error={result.get('error')!r}",
        artifact="clean_data_tool(csv_path)",
        root_cause="tools/cleaner.py:_get_dataframe is pickle-only (pd.read_pickle)",
        severity="HIGH",
    )


def test_missing_values_production_flow(datasets_dir, tmp_path, clean_data_tool):
    """On missing_values.csv the production flow must impute/flag and return
    success with a non-empty output (no raw MARK errors)."""
    raw_pickle = _upload_csv_to_pickle(datasets_dir, tmp_path, "missing_values.csv")
    output = str(tmp_path / "cleaned_dataset.pkl")
    result = clean_data_tool(raw_pickle, output_path=output, impute_missing=True, add_outlier_flags=True)
    assert result.get("status") == "success", result
    out_df = pd.read_pickle(output)
    assert len(out_df.columns) >= 4


def test_duplicates_production_flow(datasets_dir, tmp_path, clean_data_tool):
    raw_pickle = _upload_csv_to_pickle(datasets_dir, tmp_path, "duplicates.csv")
    output = str(tmp_path / "cleaned_dataset.pkl")
    result = clean_data_tool(raw_pickle, output_path=output)
    assert result.get("status") == "success", result
    out_df = pd.read_pickle(output)
    # duplicates.csv has 40 rows, 21 exact duplicates -> expect 19 retained.
    assert len(out_df) == 19, f"expected 19 rows after dedup, got {len(out_df)}"