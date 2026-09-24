"""Formatting and encoding detectors for the DataWise Cleaning Engine."""
from typing import Dict, List

import pandas as pd
import re

from backend.cleaning.detectors.base import (
    BaseDetector,
    Evidence,
    ColumnProfile,
    InspectionResult,
    _sample_indices,
    _MAX_EXAMPLES,
    _NUMERIC_VALUE_RE,
    _MOJIBAKE_PATTERNS,
    _HTML_ENTITY_RE,
    _HTML_TAG_RE,
    _jsonable,
)


class FormattingAnomalyDetector(BaseDetector):
    """Detects content-preserving formatting problems.

    Safe (APPLY-eligible): leading/trailing whitespace and repeated internal
    whitespace in text-like columns. Identifiers are NEVER touched ('00123'
    keeps its zeros).

    Unsafe (FLAG only): mixed date formats within one column and mixed
    currency-symbol usage — the intended canonical form is ambiguous.
    """

    name = "FormattingAnomalyDetector"
    problem_type = "formatting"

    _DATE_FORMAT_PATTERNS = [
        (re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"), "Y-M-D"),
        (re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$"), "Y/M/D"),
        (re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"), "D-M-Y"),
        (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"), "X/D/Y"),
    ]
    _CURRENCY_PREFIX_RE = re.compile(r"^[$€£¥]\s*\d")

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        evidence: List[Evidence] = []
        if inspection.rows == 0:
            return evidence

        for col in df.columns:
            profile = profiles.get(str(col))
            if profile is None or profile.semantic_type not in ("categorical", "text"):
                continue
            if profile.semantic_type == "identifier":
                continue
            series = df[col]
            non_null = series.dropna()
            if non_null.empty:
                continue
            strings = non_null.astype(str)

            # Whitespace is always reported as evidence. The orchestrator
            # decides whether a categorical column should defer this mutation
            # to the canonical categorical action, avoiding double mutation.
            ws_mask = (strings != strings.str.strip()) | strings.str.contains(
                r"\s{2,}", regex=True
            )
            ws_count = int(ws_mask.sum())
            if ws_count:
                bad_labels = strings.index[ws_mask]
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="whitespace_normalization",
                    affected_count=ws_count,
                    affected_row_indices=_sample_indices(
                        df.index[df.index.isin(bad_labels)].tolist()
                    ),
                    statistics={
                        "examples_before": [
                            str(v)[:60] for v in strings[ws_mask].head(_MAX_EXAMPLES)
                        ],
                        "transformation": "strip + collapse internal whitespace",
                    },
                    confidence=1.0,
                    severity="low",
                    explanation=(
                        f"{ws_count} value(s) in '{col}' carry stray/repeated "
                        "whitespace; trimming does not change content."
                    ),
                ))

            # --- unsafe: mixed date formats -------------------------------
            date_labels = {
                label
                for value in strings
                for pattern, label in self._DATE_FORMAT_PATTERNS
                if (pattern.match(value.strip()) is not None)
            }
            if len(date_labels) >= 2:
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="mixed_date_formats",
                    affected_count=int(len(strings)),
                    affected_row_indices=[],
                    statistics={
                        "formats_observed": sorted(date_labels),
                        "note": "day/month order is ambiguous between formats",
                    },
                    confidence=0.90,
                    severity="medium",
                    explanation=(
                        f"'{col}' mixes date formats {sorted(date_labels)}; "
                        "conversion order is ambiguous — flagged."
                    ),
                ))

            # --- unsafe: mixed currency symbols ---------------------------
            has_symbol = strings.str.match(self._CURRENCY_PREFIX_RE)
            plain_numeric = strings.str.match(_NUMERIC_VALUE_RE)
            if int(has_symbol.sum()) > 0 and int(plain_numeric.sum()) > 0:
                evidence.append(Evidence(
                    detector=self.name,
                    problem_type=self.problem_type,
                    column=str(col),
                    method="mixed_currency_formatting",
                    affected_count=int(has_symbol.sum()),
                    affected_row_indices=_sample_indices(
                        df.index[series.notna() & series.astype(str).str.match(self._CURRENCY_PREFIX_RE)].tolist()
                    ),
                    statistics={
                        "symbol_values": int(has_symbol.sum()),
                        "plain_numeric_values": int(plain_numeric.sum()),
                        "note": "stripping symbols alters representation, not clearly semantics-free",
                    },
                    confidence=0.75,
                    severity="low",
                    explanation=(
                        f"'{col}' mixes currency-prefixed and plain numeric "
                        "values; normalization direction is ambiguous — flagged."
                    ),
                ))
        return evidence


class EncodingArtifactDetector(BaseDetector):
    """Detects mojibake fragments and HTML entity/tag leakage inside string
    columns - classic symptoms of broken exports or scraped content.
    Evidence only: cleaning these requires an approved mapping."""

    name = "EncodingArtifactDetector"
    problem_type = "semantic_anomaly"

    def detect(self, df, profiles, inspection) -> List[Evidence]:
        del profiles, inspection
        findings: List[Evidence] = []
        for col in df.columns:
            series = df[col]
            if not (pd.api.types.is_object_dtype(series)
                    or pd.api.types.is_string_dtype(series)):
                continue
            strings = series.dropna().astype(str)
            if strings.empty:
                continue

            mojibake_rows = int(
                strings.str.contains(
                    "|".join(p.pattern for p in _MOJIBAKE_PATTERNS),
                    regex=True,
                ).sum()
            )
            html_entity_rows = int(strings.str.contains(_HTML_ENTITY_RE).sum())
            html_tag_rows = int(strings.str.contains(_HTML_TAG_RE).sum())

            total_signal = max(mojibake_rows, html_entity_rows, html_tag_rows)
            if total_signal == 0:
                continue
            findings.append(Evidence(
                detector=self.name,
                problem_type=self.problem_type,
                column=str(col),
                method="encoding_artifacts",
                affected_count=total_signal,
                affected_row_indices=[],
                statistics={
                    "mojibake_rows": mojibake_rows,
                    "html_entity_rows": html_entity_rows,
                    "html_tag_rows": html_tag_rows,
                    "column_rows": int(len(strings)),
                },
                confidence=0.80,
                severity="low" if total_signal <= len(strings) * 0.05 else "medium",
                explanation=(
                    f"'{col}' carries encoding/scraping artifacts "
                    f"(mojibake={mojibake_rows}, entities={html_entity_rows}, "
                    f"tags={html_tag_rows}); unescaping requires an "
                    "approved mapping - flagged."
                ),
            ))
        return findings