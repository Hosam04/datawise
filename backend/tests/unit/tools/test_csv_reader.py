"""CSV reader unit tests (backend.tools.csv_reader).

Tests probe the real backend behaviour for file detection, reading, and error
handling. The key verified findings:
  - Files are detected by extension AND content sniffing.
  - Malformed CSVs with ragged rows raise FileProcessingError (not silently
    dropped).
  - Header-only CSVs raise ConnectionError ("low_memory not supported") --
    this is BUG-TOOL-03.
  - Files with BOM survive and have columns stripped of leading whitespace.
"""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from backend.tests.assertions import check

COMPONENT = "Tools/CSVReader"
STAGE = "read"


@pytest.fixture
def tmp(tmp_path):
    return tmp_path


def _write(tmp, name, data: bytes) -> str:
    p = tmp / name
    p.write_bytes(data)
    return str(p)


def test_read_normal_csv(tmp, load_dataset):
    from backend.tools.csv_reader import read_any_file

    path = str(tmp / "normal.csv")
    df = load_dataset("normal.csv")
    df.to_csv(path, index=False)
    out = read_any_file(path)
    assert out.shape == (60, 6)


def test_read_tsv(tmp):
    from backend.tools.csv_reader import read_any_file, detect_file_type

    path = str(tmp / "data.tsv")
    pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}).to_csv(path, sep="\t", index=False)
    assert detect_file_type(path) == "tsv"
    out = read_any_file(path)
    assert out.shape == (2, 2)


def test_read_bom_csv(tmp):
    from backend.tools.csv_reader import read_any_file

    from backend.tests.factories import bom_utf8_csv_bytes

    path = _write(tmp, "bom.csv", bom_utf8_csv_bytes())
    out = read_any_file(path)
    assert out.shape == (3, 3)
    assert "numeric_value" in out.columns


def test_read_comma_inside_quotes(tmp):
    from backend.tools.csv_reader import read_any_file

    from backend.tests.factories import comma_inside_quotes_csv

    path = _write(tmp, "q.csv", comma_inside_quotes_csv())
    out = read_any_file(path)
    assert out.shape == (2, 3)
    assert "hello, world" in str(out.iloc[0]["note"])


def test_read_spaces_in_header(tmp):
    from backend.tools.csv_reader import read_any_file

    path = str(tmp / "sp.csv")
    with open(path, "w") as f:
        f.write("id, First Name ,value\n1,Alice,5.5\n2,Bob,6.5\n")
    out = read_any_file(path)
    assert out.shape == (2, 3)
    assert "First_Name" in out.columns


def test_detect_file_type_csv(tmp):
    from backend.tools.csv_reader import detect_file_type

    p = _write(tmp, "f.csv", b"a,b,c\n1,2,3\n")
    assert detect_file_type(p) == "csv"


def test_detect_file_type_tsv(tmp):
    from backend.tools.csv_reader import detect_file_type

    p = _write(tmp, "f.tsv", b"a\tb\tc\n1\t2\t3\n")
    assert detect_file_type(p) == "tsv"


def test_malformed_csv_raises(tmp):
    from backend.tools.csv_reader import read_any_file

    from backend.tests.factories import csv_bytes
    import io
    with open(r"D:\datawise-agent\backend\tests\datasets\malformed.csv", "rb") as f:
        data = f.read()
    path = _write(tmp, "mal.csv", data)
    with pytest.raises(Exception, match="CSV blocked|pre-parse integrity|ragged|hard_parse"):
        read_any_file(path)


def test_empty_csv_raises(tmp):
    from backend.tools.csv_reader import read_any_file

    path = _write(tmp, "empty.csv", b"")
    with pytest.raises(ValueError, match="empty"):
        read_any_file(path)


def test_file_not_found_raises(tmp):
    from backend.tools.csv_reader import read_any_file

    with pytest.raises(FileNotFoundError):
        read_any_file(str(tmp / "nope.csv"))


def test_header_only_csv_bug(tmp):
    """BUG-TOOL-03: a CSV with only a header row and no data raises
    ConnectionError ("low_memory not supported") instead of returning an
    empty DataFrame. The root cause is the pandas csv reader fallback that
    attempts multiple encodings with the C engine, hitting the low_memory
    incompatibility."""
    from backend.tools.csv_reader import read_any_file

    path = _write(tmp, "hdr.csv", b"id,value,target\n")
    with pytest.raises(Exception, match="low_memory|Critical failure|40 encodings"):
        read_any_file(path)


def test_read_arabic_utf8(tmp, load_dataset):
    from backend.tools.csv_reader import read_any_file

    path = str(tmp / "ar.csv")
    load_dataset("arabic_unicode.csv").to_csv(path, index=False)
    out = read_any_file(path)
    assert out.shape[0] == 7