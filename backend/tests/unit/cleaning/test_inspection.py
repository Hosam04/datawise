"""Inspection layer unit tests.

Covers :func:`backend.cleaning.inspection.inspect_dataframe`,
``build_column_profiles`` and ``profile_lookup`` against the committed
deterministic datasets.

Verified expected values were probed against the real backend on 2026-09-01.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.cleaning.inspection import build_column_profiles, inspect_dataframe, profile_lookup
from backend.tests.assertions import check

COMPONENT = "Cleaning/Inspection"
STAGE = "inspection"


def test_inspection_shape_normal_csv(load_dataset):
    df = load_dataset("normal.csv")
    insp = inspect_dataframe(df)
    assert insp.rows == 60, f"rows={insp.rows}"
    assert insp.column_count == 6
    assert insp.total_cells == 360
    assert insp.total_missing == 0
    assert insp.duplicate_row_count == 0
    assert insp.memory_usage_mb > 0
    assert set(insp.column_names) == set(df.columns)
    assert insp.dtypes is not None and len(insp.dtypes) == 6


def test_inspection_counts_missing_values(load_dataset):
    df = load_dataset("missing_values.csv")
    insp = inspect_dataframe(df)
    check(
        insp.total_missing == 62,
        "CLN-002", COMPONENT, STAGE,
        "total_missing == 62 (6 age + 20 score + 36 category)",
        insp.total_missing,
        dataset="missing_values.csv",
        artifact="InspectionResult.total_missing",
    )
    assert insp.rows == 60
    assert insp.total_cells == 300


def test_inspection_duplicate_row_count_excludes_identifier_columns(load_dataset):
    """Regression: duplicates.csv has 21 duplicate rows once 'id' is excluded.

    ``inspection.duplicate_row_count`` is computed over ALL columns
    (inspection.py:51) and reports 0 because every duplicated row carries a
    distinct 'id'. The DuplicateDetector later reports 21 for the same file.
    This is the seed of BUG-CLN-08: ``duplicate_ratio=0.0`` even when 52.5% of
    rows are exact duplicates ignoring the identifier column.
    """
    df = load_dataset("duplicates.csv")
    insp = inspect_dataframe(df)
    expected_rows = int(df.drop(columns=["id"]).duplicated().sum())
    check(
        insp.duplicate_row_count == expected_rows,
        "CLN-009", COMPONENT, STAGE,
        f"duplicate_row_count == {expected_rows} (duplicates ignoring identifier col)",
        insp.duplicate_row_count,
        dataset="duplicates.csv",
        artifact="InspectionResult.duplicate_row_count",
        root_cause="inspection.py:51 uses df.duplicated() over all columns (identifier included)",
        severity="HIGH",
    )
    check(
        insp.duplicate_ratio > 0.5,
        "CLN-010", COMPONENT, STAGE,
        f"duplicate_ratio > 0.5 (actual {expected_rows}/40)",
        insp.duplicate_ratio,
        dataset="duplicates.csv",
        artifact="InspectionResult.duplicate_ratio",
        root_cause="inspection.py:69 divides duplicate_row_count by rows",
        severity="HIGH",
    )


def test_inspection_constant_and_near_constant(load_dataset):
    df = load_dataset("constant_columns.csv")
    insp = inspect_dataframe(df)
    assert "brand" in insp.constant_columns, insp.constant_columns
    # near-constant requires dominant-share threshold; constant_columns.csv only
    # carries an exact-constant column, so use a synthetic frame below.
    df2 = pd.DataFrame(
        {"id": range(100), "mostly_x": ["x"] * 99 + ["y"], "unique": range(100)}
    )
    insp2 = inspect_dataframe(df2)
    assert "mostly_x" in insp2.near_constant_columns, insp2.near_constant_columns


def test_column_profiles_on_missing_values(load_dataset):
    df = load_dataset("missing_values.csv")
    profiles = profile_lookup(build_column_profiles(df))
    assert "age" in profiles and "category" in profiles
    age = profiles["age"]
    assert age.semantic_type == "numeric", age.semantic_type
    assert age.missing_ratio == pytest.approx(0.1, abs=1e-6)
    cat = profiles["category"]
    assert cat.semantic_type == "categorical"
    assert cat.missing_ratio == pytest.approx(0.6, abs=1e-6)
    assert cat.cardinality > 0
    assert age.numeric_stats is not None and "mean" in age.numeric_stats


def test_column_profiles_mixed_types(load_dataset):
    df = load_dataset("mixed_types.csv")
    profiles = profile_lookup(build_column_profiles(df))
    check(
        profiles["mixed"].semantic_type == "categorical",
        "CLN-012", COMPONENT, STAGE,
        "semantic_type == 'categorical' (10 distinct values on 40 rows)",
        profiles["mixed"].semantic_type,
        dataset="mixed_types.csv",
        artifact="ColumnProfile.semantic_type",
    )
    assert profiles["mixed"].cardinality == 10


def test_column_profiles_identifier_detection(load_dataset):
    df = load_dataset("normal.csv")
    profiles = profile_lookup(build_column_profiles(df))
    assert profiles["id"].is_possible_id is True
    assert profiles["id"].semantic_type == "identifier"


def test_build_profiles_empty_frame():
    from backend.tests.factories import empty_df

    assert build_column_profiles(empty_df()) == []


def test_build_profiles_constant_column():
    df = pd.DataFrame({"a": [1, 1, 1, 1], "b": [1, 2, 3, 4]})
    profs = profile_lookup(build_column_profiles(df))
    assert profs["a"].constant is True
    assert profs["b"].constant is False


def test_inspection_empty_dataframe():
    from backend.tests.factories import empty_df

    insp = inspect_dataframe(empty_df())
    assert insp.rows == 0
    assert insp.column_count == 0
    assert insp.total_cells == 0
    check(
        insp.total_missing == 0,
        "CLN-014", COMPONENT, STAGE, "total_missing == 0 on empty", insp.total_missing,
        dataset="empty", root_cause="empty DataFrame guard",
    )


def test_inspection_one_row():
    from backend.tests.factories import one_row_df

    insp = inspect_dataframe(one_row_df())
    assert insp.rows == 1
    assert insp.duplicate_row_count == 0


def test_inspection_bom_utf8_survives_csv_reader():
    from backend.tests.factories import bom_utf8_csv_bytes

    import io
    import pandas as pd

    df = pd.read_csv(io.BytesIO(bom_utf8_csv_bytes()))
    insp = inspect_dataframe(df)
    assert insp.rows == 3
    assert insp.column_names == ["id", "name", "numeric_value"]