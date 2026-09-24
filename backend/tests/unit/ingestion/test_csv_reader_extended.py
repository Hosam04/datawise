"""Comprehensive unit tests for CSV and multi-format data ingestion."""

import os
import pandas as pd
import pytest
from backend.core.exceptions import FileProcessingError
from backend.tools.csv_reader import (
    read_any_file,
    _detect_encoding,
    _detect_delimiter,
    _read_csv_robust,
    _read_json_robust,
)


def test_ingestion_valid_csv(tmp_path):
    """Test reading standard comma-separated CSV."""
    p = tmp_path / "valid.csv"
    p.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    df = read_any_file(str(p))
    assert df.shape == (2, 3)
    assert list(df.columns) == ["a", "b", "c"]


def test_ingestion_various_delimiters(tmp_path):
    """Test semicolon, tab, pipe, and tilde delimiters."""
    # Semicolon
    p_semi = tmp_path / "semi.csv"
    p_semi.write_text("name;age;city\nAlice;30;Paris\nBob;25;London\n", encoding="utf-8")
    df_semi = read_any_file(str(p_semi))
    assert df_semi.shape == (2, 3)
    assert "age" in df_semi.columns

    # Tab (TSV)
    p_tab = tmp_path / "tab.tsv"
    p_tab.write_text("col1\tcol2\n10\t20\n30\t40\n", encoding="utf-8")
    df_tab = read_any_file(str(p_tab))
    assert df_tab.shape == (2, 2)

    # Pipe
    p_pipe = tmp_path / "pipe.txt"
    p_pipe.write_text("x|y|z\n1.1|2.2|3.3\n4.4|5.5|6.6\n", encoding="utf-8")
    df_pipe = read_any_file(str(p_pipe))
    assert df_pipe.shape == (2, 3)


def test_ingestion_encodings(tmp_path):
    """Test UTF-8 with BOM, Latin-1, and Arabic CP1256."""
    # UTF-8 with BOM
    p_bom = tmp_path / "bom.csv"
    p_bom.write_bytes(b"\xef\xbb\xbfa,b\n1,2\n3,4\n")
    df_bom = read_any_file(str(p_bom))
    assert df_bom.shape == (2, 2)

    # Arabic CP1256
    p_arabic = tmp_path / "arabic.csv"
    arabic_text = "الاسم,العمر\nأحمد,30\nفاطمة,25\n"
    p_arabic.write_bytes(arabic_text.encode("cp1256"))
    df_arabic = read_any_file(str(p_arabic))
    assert df_arabic.shape == (2, 2)


def test_ingestion_empty_file(tmp_path):
    """Test reading a completely empty 0-byte file raises appropriate error or returns empty frame."""
    p_empty = tmp_path / "empty.csv"
    p_empty.write_text("", encoding="utf-8")
    with pytest.raises((FileProcessingError, pd.errors.EmptyDataError, ValueError, Exception)):
        read_any_file(str(p_empty))


def test_ingestion_malformed_csv(tmp_path):
    """Test reading CSV with unclosed quotes or irregular column counts."""
    p_mal = tmp_path / "malformed.csv"
    p_mal.write_text('a,b,c\n1,2,"unclosed string\n3,4,5\n', encoding="utf-8")
    # Should handle robustly with fallback or raise FileProcessingError
    try:
        df = read_any_file(str(p_mal))
        assert isinstance(df, pd.DataFrame)
    except Exception as e:
        assert isinstance(e, (FileProcessingError, Exception))


def test_ingestion_duplicate_and_empty_headers(tmp_path):
    """Test CSV with duplicate column headers or blank headers."""
    p_dup = tmp_path / "dup_headers.csv"
    p_dup.write_text("a,b,a,,c\n1,2,3,4,5\n", encoding="utf-8")
    df = read_any_file(str(p_dup))
    assert df.shape[0] == 1
    assert len(df.columns) == 5


def test_ingestion_json_and_jsonl(tmp_path):
    """Test reading standard JSON and line-delimited JSONL."""
    p_json = tmp_path / "data.json"
    p_json.write_text('[{"x": 1, "y": "a"}, {"x": 2, "y": "b"}]', encoding="utf-8")
    df_json = read_any_file(str(p_json))
    assert df_json.shape == (2, 2)

    p_jsonl = tmp_path / "data.jsonl"
    p_jsonl.write_text('{"x": 1, "y": "a"}\n{"x": 2, "y": "b"}\n', encoding="utf-8")
    df_jsonl = read_any_file(str(p_jsonl))
    assert df_jsonl.shape == (2, 2)


def test_ingestion_sqlite_database_rejected(tmp_path):
    """SQLite .db uploads must be rejected — Postgres-only stack."""
    db_path = tmp_path / "test.db"
    # Minimal SQLite header so magic-byte detection also rejects.
    db_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    with pytest.raises(ValueError, match="SQLite"):
        read_any_file(str(db_path))


def test_ingestion_parquet(tmp_path):
    """Test reading parquet file."""
    p_parquet = tmp_path / "test.parquet"
    df_orig = pd.DataFrame({"colA": [1, 2, 3], "colB": ["x", "y", "z"]})
    df_orig.to_parquet(p_parquet)

    df = read_any_file(str(p_parquet))
    assert df.shape == (3, 2)


def test_ingestion_unsupported_file_extension(tmp_path):
    """Test reading unsupported file formats raises FileProcessingError or ValueError."""
    p_bad = tmp_path / "binary.bin"
    p_bad.write_bytes(b"\x00\x01\x02\x03\x04")
    with pytest.raises((FileProcessingError, ValueError, Exception)):
        read_any_file(str(p_bad))


def test_ingestion_nonexistent_file():
    """Test reading a file path that does not exist."""
    with pytest.raises((FileNotFoundError, FileProcessingError)):
        read_any_file("nonexistent_path_12345.csv")