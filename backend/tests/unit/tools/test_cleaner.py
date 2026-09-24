"""cleaner tool (clean_data_tool) unit tests.

BUG-TOOL-01 (the headline finding): :func:`clean_data_tool` only ever reads
its input via ``pd.read_pickle`` (tools/cleaner.py:36-42). Passing the path of
a CSV (the everyday usage) makes ``pd.read_pickle`` raise
``UnpicklingError: could not find MARK``, which ``clean_data_tool`` swallows
and returns as ``{"status": None, "error": "Cleaning failed: could not find
MARK", "report": {}}``. The CleaningEngine itself handles the same CSV
perfectly, proving the defect is confined to the tool's I/O layer.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from backend.tests.assertions import check

COMPONENT = "Tools/Cleaner"
STAGE = "clean_data_tool"


def test_clean_data_tool_on_pickle(tmp_path, load_dataset):
    from backend.tools.cleaner import clean_data_tool

    path = str(tmp_path / "data.pkl")
    load_dataset("normal.csv").to_pickle(path)
    res = clean_data_tool(path)
    assert res.get("status") == "success", res
    assert res.get("error") is None


def test_clean_data_tool_generated_defaults(load_dataset):
    """clean_data_tool with no session dir must produce a cleaning result."""
    from backend.tools.cleaner import clean_data_tool
    import tempfile

    import pandas as pd

    path = os.path.join(tempfile.mkdtemp(), "d.pkl")
    load_dataset("normal.csv").to_pickle(path)
    res = clean_data_tool(path)
    assert res.get("status") == "success"


def test_clean_data_tool_csv_path_bug(load_dataset):
    """BUG-TOOL-01: feeding a CSV path (not a pickle) must work, but the tool
    mishandles it because _get_dataframe uses pd.read_pickle unconditionally."""
    from backend.tools.cleaner import clean_data_tool

    import tempfile

    src = load_dataset("normal.csv")
    path = os.path.join(tempfile.mkdtemp(), "data.csv")
    src.to_csv(path, index=False)

    res = clean_data_tool(path)
    check(
        res.get("status") == "success",
        "TOOL-011", COMPONENT, STAGE,
        "status == 'success' for a CSV input (same file the CleaningEngine cleans fine)",
        res.get("status"),
        artifact="clean_data_tool(status/error)",
        root_cause="tools/cleaner.py:_get_dataframe uses pd.read_pickle, CSV bytes fail with 'could not find MARK'",
        severity="HIGH",
    )


def test_clean_data_tool_missing_file():
    from backend.tools.cleaner import clean_data_tool

    import tempfile

    res = clean_data_tool(os.path.join(tempfile.mkdtemp(), "missing.csv"))
    assert res.get("status") is None
    assert "not found" in (res.get("error") or "").lower()


def test_engine_succeeds_on_same_csv(cleaning_engine, load_dataset, tmp_path):
    from backend.tools.cleaner import clean_data_tool

    src = load_dataset("normal.csv")
    path = str(tmp_path / "data.csv")
    src.to_csv(path, index=False)
    # Control: Feeding the CSV through clean_data_tool must succeed.
    res = clean_data_tool(path)
    assert res.get("status") == "success", res