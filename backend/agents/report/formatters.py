"""Report formatters for ReportBuilderAgent.

Extracted formatting logic to keep the main agent class focused on orchestration.
"""
import re
from typing import Any

from backend.core.constants import ID_EXACT, ID_PATTERNS


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'(\d)([a-zA-Z])', lambda m: f"{m.group(1)} {m.group(2)}", text)
    text = re.sub(r'([a-zA-Z])(\d)', lambda m: f"{m.group(1)} {m.group(2)}", text)
    text = re.sub(r'([a-zA-Z0-9])\(', lambda m: f"{m.group(1)} (", text)
    text = re.sub(r'\)([a-zA-Z0-9])', lambda m: f") {m.group(1)}", text)
    text = re.sub(r'(%)([a-zA-Z])', lambda m: f"{m.group(1)} {m.group(2)}", text)
    text = re.sub(r'([a-zA-Z]):([a-zA-Z])', lambda m: f"{m.group(1)}: {m.group(2)}", text)
    text = re.sub(r'\.([a-zA-Z])', lambda m: f". {m.group(1)}", text)
    text = re.sub(r';([a-zA-Z])', lambda m: f"; {m.group(1)}", text)
    text = re.sub(
        r'(\d)(chars|char|entries|entry|categories|category)',
        lambda m: f"{m.group(1)} {m.group(2)}",
        text,
    )
    text = text.replace(
        "data_quality,distribution,segment",
        "data quality, distribution, and segment",
    )
    text = text.replace(",", ", ")
    text = re.sub(r' +', ' ', text)
    text = text.replace(" .", ".").replace(" ,", ",")
    text = text.replace("(s)", "s")
    return text.strip()


def _looks_like_identifier(col: str) -> bool:
    c = str(col).lower()
    return c in ID_EXACT or any(c.endswith(p) for p in ID_PATTERNS)


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _format_statistical_results(raw) -> str:
    """Render the complete StatisticalEngine result without dropping fields."""
    if not raw or not isinstance(raw, dict):
        return "No Statistical Engine results available."

    nl = "\n"
    parts = []

    metadata = raw.get("metadata") or {}
    dataset = raw.get("dataset") or {}
    column_stats = raw.get("column_statistics") or {}
    correlations = raw.get("correlations")
    distributions = raw.get("distributions") or {}
    outliers = raw.get("outlier_evidence")
    groups = raw.get("group_statistics") or {}
    associations = raw.get("target_associations")
    warnings = raw.get("warnings") or []

    # 1. Engine metadata — keeps the report auditable.
    lines = [
        "## Statistical Engine",
        "",
        "### Engine Configuration",
        "",
        "| Setting | Value |",
        "|---------|-------|",
    ]
    for key, value in metadata.items():
        lines.append(f"| {key} | {_fmt(value)} |")
    parts.append(nl.join(lines))

    # 2. Dataset overview — every field from DatasetOverview.
    lines = [
        "### Dataset Overview",
        "",
        "| Statistic | Value |",
        "|-----------|-------|",
    ]
    scalar_keys = [
        "rows",
        "column_count",
        "memory_usage_mb",
        "total_missing_cells",
        "duplicate_rows",
        "duplicate_ratio",
    ]
    for key in scalar_keys:
        if key in dataset:
            lines.append(f"| {key} | {_fmt(dataset.get(key))} |")
    for key in [
        "constant_columns",
        "numeric_columns",
        "categorical_columns",
        "boolean_columns",
        "datetime_columns",
        "text_columns",
        "identifier_columns",
    ]:
        values = dataset.get(key, [])
        lines.append(
            f"| {key} | {', '.join(map(str, values)) if values else 'None'} |"
        )
    dtypes = dataset.get("dtypes") or {}
    lines.append(
        f"| dtypes | {', '.join(f'{k}: {v}' for k, v in dtypes.items()) if dtypes else 'None'} |"
    )
    lines.append(
        f"| column_names | {', '.join(map(str, dataset.get('column_names', []))) or 'None'} |"
    )
    parts.append(nl.join(lines))

    # 3. Complete per-column summaries. Nested top_values / percentiles are rendered too.
    parts.append("### Column Statistics")
    if not column_stats:
        parts.append("No column statistics available.")
    for col, data in column_stats.items():
        data = data or {}
        kind = data.get("kind", "unknown")
        lines = [
            f"#### {col} ({kind})",
            "",
            "| Statistic | Value |",
            "|-----------|-------|",
        ]
        nested = {"top_values", "percentiles"}
        for key, value in data.items():
            if key in nested or key == "warnings":
                continue
            if isinstance(value, (dict, list)):
                value = (
                    ", ".join(map(str, value))
                    if isinstance(value, list)
                    else ", ".join(f"{k}: {v}" for k, v in value.items())
                )
            lines.append(f"| {key} | {_fmt(value)} |")
        if "percentiles" in data:
            lines.append(
                "| percentiles | "
                + "; ".join(
                    f"{k}: {_fmt(v)}"
                    for k, v in (data.get("percentiles") or {}).items()
                )
                + " |"
            )
        top_values = data.get("top_values") or []
        if top_values:
            lines.extend(
                [
                    "",
                    "Top values:",
                    "",
                    "| Value | Count | Percentage |",
                    "|-------|-------|------------|",
                ]
            )
            for item in top_values:
                lines.append(
                    f"| {_fmt(item.get('value'))} | {_fmt(item.get('count'))} | {_fmt(item.get('percentage'))} |"
                )
        column_warnings = data.get("warnings") or []
        if column_warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {w}" for w in column_warnings)
        parts.append(nl.join(lines))

    # 4. Correlations: configuration, exclusions, full matrix and ranked pairs.
    parts.append("### Correlations")
    if not correlations:
        parts.append("No correlation analysis available.")
    else:
        lines = [
            f"Method: {correlations.get('method', 'N/A')}",
            "",
            "Columns used: "
            + (
                ", ".join(
                    map(str, correlations.get("columns_used", []))
                )
                or "None"
            ),
            "",
            "Excluded columns:",
        ]
        excluded = correlations.get("excluded_columns") or {}
        lines.extend(f"- {k}: {v}" for k, v in excluded.items())
        if not excluded:
            lines.append("- None")
        lines.extend(
            [
                "",
                "#### Correlation Matrix",
                "",
                "| Variable | "
                + " | ".join(
                    map(str, correlations.get("matrix", {}).keys())
                )
                + " |",
            ]
        )
        matrix = correlations.get("matrix") or {}
        matrix_cols = list(matrix.keys())
        lines[-1] = (
            "| Variable | " + " | ".join(matrix_cols) + " |"
            if matrix_cols
            else "| Variable | Value |"
        )
        lines.append("|---|" + "---|" * max(1, len(matrix_cols)))
        for row_name in matrix_cols:
            row = matrix.get(row_name) or {}
            lines.append(
                "| "
                + str(row_name)
                + " | "
                + " | ".join(_fmt(row.get(c)) for c in matrix_cols)
                + " |"
            )
        pairs = correlations.get("top_pairs") or []
        lines.extend(
            [
                "",
                "#### Ranked Correlation Pairs",
                "",
                "| Column A | Column B | Correlation | Strength | Direction | P-value | N | Significant |",
                "|----------|----------|-------------|----------|-----------|---------|---|-------------|",
            ]
        )
        for pair in pairs:
            lines.append(
                "| "
                + " | ".join([
                    _fmt(pair.get("column_a")),
                    _fmt(pair.get("column_b")),
                    _fmt(pair.get("correlation")),
                    _fmt(pair.get("strength")),
                    _fmt(pair.get("direction")),
                    _fmt(pair.get("p_value")),
                    _fmt(pair.get("n")),
                    _fmt(pair.get("significant")),
                ])
                + " |"
            )
        lines.extend(["", f"Note: {correlations.get('note', '')}"])
        parts.append(nl.join(lines))

    # 5. Distribution checks.
    lines = [
        "### Distribution Checks",
        "",
        "| Column | N | Skewness | Shapiro Statistic | Shapiro P-value | Shape | Note |",
        "|--------|---|----------|-------------------|-----------------|-------|------|",
    ]
    for col, item in distributions.items():
        lines.append(
            "| "
            + " | ".join([
                str(col),
                _fmt(item.get("n")),
                _fmt(item.get("skewness")),
                _fmt(item.get("shapiro_statistic")),
                _fmt(item.get("shapiro_p_value")),
                _fmt(item.get("shape")),
                _fmt(item.get("note")),
            ])
            + " |"
        )
    parts.append(
        nl.join(lines)
        if distributions
        else "### Distribution Checks\n\nNo distribution checks available."
    )

    # 6. Outlier evidence — all fields.
    if outliers:
        lines = [
            "### Outlier Evidence",
            "",
            f"Method: {_fmt(outliers.get('method'))} | Threshold: {_fmt(outliers.get('threshold'))} | Total rows: {_fmt(outliers.get('total_rows'))}",
            "",
            "| Column | Analyzed | Count | Percentage | Severity | Lower | Upper | Mean | Std | MAD Extreme Share | Min Outlier | Max Outlier | Note |",
            "|--------|----------|-------|------------|----------|-------|-------|------|-----|-------------------|-------------|-------------|------|",
        ]
        for item in outliers.get("columns") or []:
            lines.append(
                "| "
                + " | ".join([
                    _fmt(item.get("column")),
                    _fmt(item.get("analyzed")),
                    _fmt(item.get("count")),
                    _fmt(item.get("percentage")),
                    _fmt(item.get("severity")),
                    _fmt(item.get("lower_bound")),
                    _fmt(item.get("upper_bound")),
                    _fmt(item.get("mean")),
                    _fmt(item.get("std")),
                    _fmt(item.get("mad_extreme_share")),
                    _fmt(item.get("min_outlier_value")),
                    _fmt(item.get("max_outlier_value")),
                    _fmt(item.get("note")),
                ])
                + " |"
            )
        lines.extend(
            [
                "",
                f"Action: {_fmt(outliers.get('action'))}",
                f"Note: {_fmt(outliers.get('note'))}",
            ]
        )
        for item in outliers.get("columns") or []:
            samples = item.get("sample_row_indices") or []
            if samples:
                lines.append(
                    f"- {item.get('column')} sample row indices: {', '.join(map(str, samples))}"
                )
        parts.append(nl.join(lines))
    else:
        parts.append("### Outlier Evidence\n\nNo outlier evidence available.")

    # 7. Group statistics.
    lines = ["### Group Statistics"]
    entries = groups.get("entries") if isinstance(groups, dict) else []
    if entries:
        for entry in entries:
            lines.extend(
                [
                    "",
                    f"#### {entry.get('value_column')} by {entry.get('group_column')}",
                    "",
                    "| Group | Count | Mean | Median | Std |",
                    "|-------|-------|------|--------|-----|",
                ]
            )
            for item in entry.get("groups") or []:
                lines.append(
                    "| "
                    + " | ".join([
                        _fmt(item.get("group")),
                        _fmt(item.get("count")),
                        _fmt(item.get("mean")),
                        _fmt(item.get("median")),
                        _fmt(item.get("std")),
                    ])
                    + " |"
                )
            if entry.get("note"):
                lines.append(f"Note: {entry.get('note')}")
    else:
        lines.append("No group statistics available.")
    group_warnings = (
        groups.get("warnings") if isinstance(groups, dict) else []
    )
    if group_warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {w}" for w in group_warnings)
    parts.append(nl.join(lines))

    # 8. Target associations.
    lines = ["### Target Associations"]
    if associations:
        lines.extend([
            f"Target: {_fmt(associations.get('target'))}",
            f"Target kind: {_fmt(associations.get('target_kind'))}",
        ])
        for label, key in (
            ("Numeric associations", "numeric"),
            ("Categorical associations", "categorical"),
        ):
            items = associations.get(key) or []
            lines.extend(
                [
                    "",
                    f"#### {label}",
                    "",
                    "| Feature | Target | Test | Score | Statistic | P-value | N | Method |",
                    "|---------|--------|------|-------|-----------|---------|---|--------|",
                ]
            )
            for item in items:
                lines.append(
                    "| "
                    + " | ".join([
                        _fmt(item.get("feature")),
                        _fmt(item.get("target")),
                        _fmt(item.get("kind")),
                        _fmt(item.get("score")),
                        _fmt(item.get("statistic")),
                        _fmt(item.get("p_value")),
                        _fmt(item.get("n")),
                        _fmt(item.get("method")),
                    ])
                    + " |"
                )
            if not items:
                if key == "numeric":
                    lines.append(
                        "| — | — | — | — | — | — | — | "
                        "No numeric features showed a significant association "
                        "(after leakage filtering / non-applicable types). |"
                    )
                else:
                    lines.append("| None | | | | | | | |")
    else:
        lines.append("No target associations available.")
    parts.append(nl.join(lines))

    # 9. Engine-level warnings.
    lines = ["### Statistical Engine Warnings"]
    if warnings:
        lines.extend(f"- {w}" for w in warnings)
    else:
        lines.append("None")
    parts.append(nl.join(lines))

    return (nl * 2).join(parts)


def _format_insights(insights_raw) -> str:
    if not insights_raw or isinstance(insights_raw, str):
        return str(insights_raw) if insights_raw else "No insights generated."

    if not isinstance(insights_raw, dict):
        return "Invalid insights format."

    nl = chr(10)
    parts = []

    exec_summary = insights_raw.get('executive_summary', 'Analysis completed.')
    exec_summary = _clean_text(exec_summary)
    parts.append(f"## Executive Summary{nl}{nl}{exec_summary}")

    findings = insights_raw.get("key_findings", [])
    if findings:
        parts.append(f"## Key Findings{nl}")

        critical = [f for f in findings if f.get('evidence', {}).get('severity') == 'critical']
        strong = [f for f in findings if f.get('evidence', {}).get('severity') == 'strong']
        moderate = [f for f in findings if f.get('evidence', {}).get('severity') == 'moderate']
        other = [f for f in findings if f.get('evidence', {}).get('severity') not in ('critical', 'strong', 'moderate')]

        idx = 1
        for tier_name, tier_list in [("Critical Findings", critical), ("Strong Findings", strong), ("Moderate Findings", moderate), ("Other Findings", other)]:
            if tier_list:
                parts.append(f"### {tier_name}{nl}")
                for f in tier_list:
                    title = _clean_text(f.get('title', 'Finding'))
                    desc = _clean_text(f.get('description', ''))
                    conf = f.get('confidence', '')
                    # BUG-002: Distinguish insight confidence from model importance
                    conf_str = f" *(Insight confidence: {conf})*" if conf else ""
                    parts.append(f"**{idx}. {title}**{conf_str}{nl}{nl}{desc}")
                    idx += 1

    recs = insights_raw.get("recommendations", [])
    if recs:
        parts.append(f"## Recommendations{nl}")
        for r in recs:
            cleaned = _clean_text(r)
            parts.append(f"- {cleaned}")

    lims = insights_raw.get("limitations", [])
    if lims:
        parts.append(f"## Limitations{nl}")
        for l in lims:
            cleaned = _clean_text(l)
            parts.append(f"- {cleaned}")

    return (nl * 2).join(parts)


def _format_ml_results(ml_results, df=None, target=None) -> str:
    if not ml_results:
        return ""

    nl = chr(10)

    status = getattr(ml_results, "status", None)
    reason = getattr(ml_results, "reason", "")
    selected_model = getattr(ml_results, "selected_model", "Unknown")
    problem_type = getattr(ml_results, "problem_type", "unknown")
    data_modality = getattr(ml_results, "data_modality", "tabular")
    used_fallback = getattr(ml_results, "used_fallback", False)
    fallback_model = getattr(ml_results, "fallback_model", "")
    selection_reason = getattr(ml_results, "selection_reason", None)
    metrics = getattr(ml_results, "metrics", None)
    feature_importance = getattr(ml_results, "feature_importance", None)
    warnings = getattr(ml_results, "warnings", None)

    if status == "skipped":
        return f"## Machine Learning Analysis{nl}{nl}*ML analysis skipped: {reason}*{nl}"

    if status == "failed":
        return f"## Machine Learning Analysis{nl}{nl}*ML analysis failed: {reason}*{nl}"

    if status != "success":
        return ""

    lines = [
        "## Machine Learning Analysis",
        "",
        f"**Selected Model:** {selected_model}",
        f"**Problem Type:** {problem_type}",
        f"**Data Modality:** {data_modality or 'tabular'}",
    ]

    if used_fallback and fallback_model:
        lines.append(f"**Fallback Used:** Yes ({fallback_model})")

    if selection_reason:
        if isinstance(selection_reason, (list, tuple)) and len(selection_reason) > 0:
            lines.extend(["", "### Selection Rationale", ""])
            for r in selection_reason:
                lines.append(f"- {r}")

    lines.extend(["", "### Performance Metrics", ""])

    if metrics is not None:
        if isinstance(metrics, dict):
            if problem_type in ("classification", "text_classification"):
                lines.extend([
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Accuracy | {metrics.get('accuracy', 'N/A')} |",
                    f"| Precision | {metrics.get('precision', 'N/A')} |",
                    f"| Recall | {metrics.get('recall', 'N/A')} |",
                    f"| F1 Score | {metrics.get('f1', 'N/A')} |",
                    f"| AUC-ROC | {metrics.get('auc_roc', 'N/A')} |",
                ])
            else:
                lines.extend([
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| R² | {metrics.get('r2', 'N/A')} |",
                    f"| RMSE | {metrics.get('rmse', 'N/A')} |",
                    f"| MAE | {metrics.get('mae', 'N/A')} |",
                    f"| MSE | {metrics.get('mse', 'N/A')} |",
                ])
        else:
            if problem_type in ("classification", "text_classification"):
                lines.extend([
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| Accuracy | {getattr(metrics, 'accuracy', 'N/A')} |",
                    f"| Precision | {getattr(metrics, 'precision', 'N/A')} |",
                    f"| Recall | {getattr(metrics, 'recall', 'N/A')} |",
                    f"| F1 Score | {getattr(metrics, 'f1', 'N/A')} |",
                    f"| AUC-ROC | {getattr(metrics, 'auc_roc', 'N/A')} |",
                ])
            else:
                lines.extend([
                    "| Metric | Value |",
                    "|--------|-------|",
                    f"| R² | {getattr(metrics, 'r2', 'N/A')} |",
                    f"| RMSE | {getattr(metrics, 'rmse', 'N/A')} |",
                    f"| MAE | {getattr(metrics, 'mae', 'N/A')} |",
                    f"| MSE | {getattr(metrics, 'mse', 'N/A')} |",
                ])
    else:
        lines.append("No metrics available.")

    # ─── BUG-007 FIX: Render Per-Class Metrics if available ───
    if hasattr(metrics, 'per_class') and metrics.per_class:
        lines.extend(["", "### Per-Class Performance Breakdown", ""])
        lines.append("| Class | Precision | Recall | F1-Score | Support (Count) |")
        lines.append("|-------|-----------|--------|----------|-----------------|")

        # Sort classes to ensure consistent ordering (e.g., negative, neutral, positive)
        for cls_name in sorted(metrics.per_class.keys()):
            cls_metrics = metrics.per_class[cls_name]
            lines.append(
                f"| {cls_name} | {cls_metrics.precision:.4f} | {cls_metrics.recall:.4f} | "
                f"{cls_metrics.f1:.4f} | {cls_metrics.support} |"
            )
    # ──────────────────────────────────────────────────────────

    if feature_importance:
        target_lower = str(target).lower() if target else ""
        leak_kw = ("confidence", "prob", "score", "likelihood", "certainty")
        rows = []
        for item in feature_importance[:10]:
            if isinstance(item, dict):
                name = str(item.get("feature", ""))
                imp = item.get("importance", 0)
            else:
                name = str(getattr(item, "feature", ""))
                imp = getattr(item, "importance", 0)

            name_l = name.lower()
            if _looks_like_identifier(name):
                continue
            if (target_lower and target_lower in name_l and name_l != target_lower
                    and any(k in name_l for k in leak_kw)):
                continue

            annotation = ""
            if df is not None and name in df.columns:
                series = df[name]
                missing_pct = float(series.isna().sum()) / max(1, len(series))
                if missing_pct > 0.80:
                    continue
                ratio = series.nunique(dropna=True) / max(1, len(series))
                if ratio > 0.2:
                    continue

                # BUG-001: Structural / definitional leakage detection
                # (same logic as InsightsAgent). Annotate instead of silent drop
                # so the importance remains visible but is not over-interpreted.
                if target and target in df.columns and missing_pct > 0.05:
                    present_mask = series.notna()
                    missing_mask = ~present_mask
                    if present_mask.any():
                        target_when_present = df.loc[present_mask, target]
                        if len(target_when_present) >= 10:
                            present_mode_pct = float(
                                target_when_present.value_counts(normalize=True).iloc[0]
                            )
                            if present_mode_pct > 0.95:
                                dominant = target_when_present.mode().iloc[0]
                                annotation = (
                                    f" ⚠️ definitional leakage "
                                    f"(non-null almost only when target='{dominant}')"
                                )
                    if not annotation and missing_mask.any():
                        target_when_missing = df.loc[missing_mask, target]
                        if len(target_when_missing) >= 10:
                            missing_mode_pct = float(
                                target_when_missing.value_counts(normalize=True).iloc[0]
                            )
                            if missing_mode_pct > 0.85:
                                dominant = target_when_missing.mode().iloc[0]
                                annotation = (
                                    f" ⚠️ structural leakage "
                                    f"(missingness correlated with target='{dominant}')"
                                )

            display_name = f"{name}{annotation}" if annotation else name
            rows.append(f"| {display_name} | {imp:.4f} |")
        if rows:
            lines.extend(["", "### Top Predictive Features", ""])
            lines.append("| Feature | Importance |")
            lines.append("|---------|------------|")
            lines.extend(rows)
            # Help text when any leakage annotation is present
            if any("leakage" in r for r in rows):
                lines.append("")
                lines.append(
                    "*Features marked with a leakage warning are definitional or "
                    "structurally tied to the target (e.g. only populated for one class). "
                    "Their high importance often reflects that structure rather than "
                    "true predictive signal; interpret with caution.*"
                )

    if warnings:
        if isinstance(warnings, (list, tuple)) and len(warnings) > 0:
            lines.extend(["", "### Warnings", ""])
            for w in warnings:
                lines.append(f"-  {w}")

    return nl.join(lines)


def _format_cleaning_summary(cleaning_report) -> str:
    # 1. Safe guard: if it's not a dict, return fallback message
    if not cleaning_report or not isinstance(cleaning_report, dict):
        return "## Data Cleaning Summary\n\n*No detailed cleaning operations recorded.*"

    nl = "\n"
    lines = [
        "## Data Cleaning Summary",
        "",
        "The following automated cleaning operations and data quality assessments were performed on the dataset:",
        ""
    ]

    # 2. Shape overview (rows/columns before and after cleaning).
    original_shape = cleaning_report.get("original_shape") or []
    final_shape = cleaning_report.get("final_shape") or []
    if len(original_shape) >= 2 and len(final_shape) >= 2:
        lines.append("###  Cleaning Overview")
        lines.append("| Metric | Before | After |")
        lines.append("|--------|--------|-------|")
        lines.append(f"| Rows | {int(original_shape[0])} | {int(final_shape[0])} |")
        lines.append(f"| Columns | {int(original_shape[1])} | {int(final_shape[1])} |")
        lines.append("")

    # 3. Cleaning Engine decisions (verdict counts + applied actions).
    cleaning_steps = cleaning_report.get("cleaning_steps", [])
    if not isinstance(cleaning_steps, list):
        cleaning_steps = []

    engine_decisions = cleaning_report.get("engine_decisions", [])
    if not isinstance(engine_decisions, list):
        engine_decisions = []

    applied_actions = []
    flagged_issues = 0
    for step in cleaning_steps:
        if isinstance(step, dict) and step.get("step") == "cleaning_engine":
            applied_actions = step.get("applied_actions", [])
            flagged_issues = step.get("flagged_issues", 0)
            break

    skipped_actions = sum(
        1
        for d in engine_decisions
        if isinstance(d, dict) and str(d.get("verdict")).lower() == "skip"
    )

    try:
        flagged_count = int(flagged_issues)
    except (TypeError, ValueError):
        flagged_count = 0

    applied_count = 0
    if isinstance(applied_actions, list):
        for action in applied_actions:
            if isinstance(action, dict) and action.get("applied"):
                applied_count += 1

    if skipped_actions or flagged_count:
        lines.append("###  Cleaning Decisions")
        lines.append(f"- **Actions applied:** {applied_count}")
        lines.append(f"- **Issues flagged for review:** {flagged_count}")
        if skipped_actions:
            lines.append(f"- **Actions skipped:** {skipped_actions}")
        lines.append("")

    # 4. Actions Applied (Safe list/dict access)
    if isinstance(applied_actions, list) and applied_actions:
        lines.append("###  Actions Applied")
        lines.append("| Action Type | Target Column | Rows Affected |")
        lines.append("|-------------|---------------|---------------|")
        for action in applied_actions:
            if isinstance(action, dict):
                if action.get("rolled_back"):
                    continue
                if action.get("validated") is False:
                    continue
                act_type = action.get("action", "Unknown Action")
                col = action.get("column")
                # Dataset-level actions (duplicates, etc.) have no column
                if col is None or col == "" or str(col).lower() == "none":
                    col = "<entire dataset>"
                rows = action.get("rows_affected", 0)
                lines.append(f"| `{act_type}` | `{col}` | {rows} |")
        lines.append("")

    # 5. Empty state when no cleaning action was applied.
    if not isinstance(applied_actions, list) or not applied_actions:
        lines.append("*No cleaning actions were applied.*")
        lines.append("")

    # 6. Columns Dropped (Safe list/dict access)
    # Decision.column lives under evidence.column (not top-level).
    dropped_columns = []
    for decision in engine_decisions:
        if not isinstance(decision, dict):
            continue
        if (
            decision.get("action") == "DropColumnAction"
            and decision.get("verdict") == "apply"
        ):
            evidence = decision.get("evidence") or {}
            col = None
            if isinstance(evidence, dict):
                col = evidence.get("column")
            # Fallback: some serializers may flatten column
            if not col:
                col = decision.get("column")
            if col:
                dropped_columns.append(str(col))

    # Also catch drops recorded only in applied_actions
    if not dropped_columns:
        for step in cleaning_steps:
            if not isinstance(step, dict):
                continue
            for action in step.get("applied_actions") or []:
                if (
                    isinstance(action, dict)
                    and action.get("action") == "DropColumnAction"
                    and action.get("column")
                ):
                    dropped_columns.append(str(action["column"]))

    # Deduplicate while preserving order
    seen = set()
    unique_dropped = []
    for c in dropped_columns:
        if c not in seen:
            seen.add(c)
            unique_dropped.append(c)

    if unique_dropped:
        lines.append("###  Columns Dropped")
        for col in unique_dropped:
            lines.append(
                f"- **`{col}`**: High missing rate or target leakage"
            )
        lines.append("")
    else:
        # Explicit empty state so the section never shows a misleading "None"
        lines.append("###  Columns Dropped")
        lines.append("- *No columns were dropped.*")
        lines.append("")

    # 7. Information Loss Warnings (from CleaningEngine validation)
    info_loss = cleaning_report.get("information_loss_warnings") or []
    if isinstance(info_loss, list) and info_loss:
        lines.append("###  Information Loss Warnings")
        for w in info_loss:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    # 8. Rows Removed (Safe numeric check)
    rows_removed = cleaning_report.get("rows_removed", 0)
    try:
        rows_removed_num = int(rows_removed)
    except (TypeError, ValueError):
        rows_removed_num = 0
    if rows_removed_num > 0:
        lines.append("###  Rows Removed")
        lines.append(
            f"- **Total rows removed:** {rows_removed_num} "
            "(e.g., exact duplicates or blocked rows)"
        )
        lines.append("")

    return nl.join(lines)