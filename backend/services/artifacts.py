"""Artifacts service for the DataWise API.

Handles dataset retrieval, artifact building, and data transformation.
"""
import os
import csv
import math
from typing import Any, Dict

import pandas as pd

from backend.core.storage import analysis_repository
from backend.statistics import StatisticalEngine


def _sanitize(obj: Any) -> Any:
    """Recursively replace NaN, Inf, -Inf with None for JSON compliance."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def get_dataset(dataset_id: str) -> Dict[str, Any]:
    """Retrieve dataset from storage, raising 404 if not found."""
    dataset = analysis_repository.get(dataset_id)
    if dataset is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


def _build_preview(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Return a usable preview payload, rebuilding from df.pkl if needed."""
    preview = dataset.get("preview")
    if isinstance(preview, dict):
        columns = preview.get("columns") or []
        rows = preview.get("rows") or []
        if columns and isinstance(rows, list):
            return {
                "columns": list(columns),
                "rows": rows,
                "total_rows": int(preview.get("total_rows") or len(rows)),
                "total_cols": int(preview.get("total_cols") or len(columns)),
            }

    df_path = dataset.get("df_path")
    if df_path and os.path.isfile(df_path):
        try:
            import pandas as pd
            df = pd.read_pickle(df_path)
            columns = [str(c) for c in df.columns]
            sample = df.head(20)
            rows = sample.where(pd.notnull(sample), None).to_dict(orient="records")
            return {
                "columns": columns,
                "rows": rows,
                "total_rows": int(len(df)),
                "total_cols": int(len(columns)),
            }
        except Exception:
            pass

    return {
        "columns": [],
        "rows": [],
        "total_rows": 0,
        "total_cols": 0,
    }


def _rebuild_statistics_from_df(df_path: str) -> Dict[str, Any]:
    """Compute descriptive stats on the fly when stored stats are missing."""
    try:
        import pandas as pd
        from backend.statistics import StatisticalEngine
    except Exception:
        return {
            "descriptive": {},
            "correlations": {},
            "outliers": {},
        }

    try:
        df = pd.read_pickle(df_path)
        engine = StatisticalEngine()
        results = engine.analyze(df)

        # Extract descriptive stats directly from StatisticalResults (modern contract)
        descriptive = {}
        categorical = {}
        for col_name, summary in results.column_statistics.items():
            kind = getattr(summary, "kind", None)
            if kind == "numeric":
                descriptive[col_name] = {
                    "count": summary.count,
                    "null_count": summary.null_count,
                    "null_pct": summary.null_pct,
                    "unique_count": summary.unique_count,
                    "min": summary.min,
                    "max": summary.max,
                    "mean": summary.mean,
                    "median": summary.median,
                    "std": summary.std,
                    "variance": summary.variance,
                    "skewness": summary.skewness,
                    "kurtosis": summary.kurtosis,
                    "range": summary.range,
                    "iqr": summary.iqr,
                }
                if summary.percentiles:
                    descriptive[col_name]["percentiles"] = {
                        k: v for k, v in summary.percentiles.items() if v is not None
                    }
                if summary.count > 1:
                    descriptive[col_name]["cv"] = summary.cv
                    descriptive[col_name]["sem"] = summary.sem
                if summary.count == 0:
                    descriptive[col_name].pop("unique_count", None)
                    descriptive[col_name]["note"] = "All values are null"
            elif kind in ("categorical", "text", "identifier", "boolean"):
                if kind == "boolean":
                    true_share = {
                        "value": "True",
                        "count": summary.true_count,
                        "percentage": summary.true_pct,
                    }
                    false_share = {
                        "value": "False",
                        "count": summary.false_count,
                        "percentage": round(100.0 - summary.true_pct, 2),
                    }
                    top_values = sorted(
                        [true_share, false_share],
                        key=lambda item: item["count"],
                        reverse=True,
                    )
                    unique_count = sum(
                        1 for item in (summary.true_count, summary.false_count) if item > 0
                    )
                elif kind == "text":
                    top_values = []
                    unique_count = getattr(summary, "unique_count", 0)
                else:
                    top_values = [
                        {"value": tv.value, "count": tv.count, "percentage": tv.percentage}
                        for tv in summary.top_values[:10]
                    ]
                    unique_count = summary.unique_count
                categorical[col_name] = {
                    "count": summary.count,
                    "null_count": summary.null_count,
                    "null_pct": summary.null_pct,
                    "unique_count": unique_count,
                    "top_values": top_values,
                }

        # Merge categorical into descriptive for backward compatibility
        for col, stats in categorical.items():
            if col not in descriptive and isinstance(stats, dict):
                descriptive[col] = stats

        # Extract correlation matrix directly from StatisticalResults
        correlations = {}
        if results.correlations and len(results.correlations.columns_used) >= 2:
            correlations = {
                outer: {
                    inner: (round(float(value), 3) if value is not None else value)
                    for inner, value in row.items()
                }
                for outer, row in results.correlations.matrix.items()
            }

        # Extract outlier summary directly from StatisticalResults
        outliers = {}
        if results.outlier_evidence:
            for item in results.outlier_evidence.columns:
                if not item.analyzed:
                    if item.note and "bounded" in item.note.lower():
                        outliers[item.column] = {
                            "count": "N/A",
                            "percentage": "Skipped",
                            "note": "Excluded: bounded domain (e.g., confidence, probability, rating)",
                            "action": "none",
                        }
                    else:
                        outliers[item.column] = {
                            "count": 0,
                            "percentage": 0.0,
                            "note": item.note or "Not analyzed",
                        }
                    continue

                if item.count == 0:
                    outliers[item.column] = {
                        "count": 0,
                        "percentage": 0.0,
                        "note": "No outliers detected",
                    }
                    continue

                entry = {}
                if item.method == "iqr":
                    entry["method"] = "IQR"
                    entry["threshold_multiplier"] = item.threshold
                    entry["bounds"] = {
                        "lower": item.lower_bound,
                        "upper": item.upper_bound,
                    }
                else:
                    entry["method"] = "Z-Score"
                    entry["threshold"] = item.threshold
                    entry["mean"] = item.mean
                    entry["std"] = item.std

                entry["count"] = int(item.count)
                entry["percentage"] = round(float(item.percentage), 2)
                entry["action"] = "detect_only"
                outliers[item.column] = dict(sorted(entry.items()))

        return {
            "descriptive": descriptive,
            "correlations": correlations,
            "outliers": outliers,
        }
    except Exception:
        return {
            "descriptive": {},
            "correlations": {},
            "outliers": {},
        }


def _build_statistics(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize statistics into {descriptive, correlations, outliers}."""
    raw = dataset.get("statistics")
    descriptive: Dict[str, Any] = {}

    if isinstance(raw, dict):
        nested = raw.get("statistics")
        if isinstance(nested, dict) and nested:
            descriptive = nested
        else:
            # Flat column -> stats map (current pipeline stores this)
            reserved = {
                "statistics",
                "categorical_statistics",
                "summary_table",
                "total_rows",
                "numeric_columns_analyzed",
                "categorical_columns_analyzed",
            }
            descriptive = {
                k: v
                for k, v in raw.items()
                if k not in reserved and isinstance(v, dict)
            }
            # Prefer explicit nested if filtering emptied the map
            if not descriptive and isinstance(nested, dict):
                descriptive = nested

        # Merge categorical column summaries when present (nested under
        # statistics, or stored as a sibling key on the dataset payload).
        categorical = raw.get("categorical_statistics")
        if not isinstance(categorical, dict):
            categorical = dataset.get("categorical_statistics")
        if isinstance(categorical, dict):
            for col, stats in categorical.items():
                if col not in descriptive and isinstance(stats, dict):
                    descriptive[col] = stats
    else:
        # statistics key missing entirely — still try sibling categorical map
        categorical = dataset.get("categorical_statistics")
        if isinstance(categorical, dict):
            for col, stats in categorical.items():
                if isinstance(stats, dict):
                    descriptive[col] = stats

    correlations = dataset.get("correlations") or {}
    outliers = dataset.get("outliers") or {}

    # Normalize correlation payloads so the frontend always receives a
    # column→column numeric matrix (never {error, ...} or {matrix: {...}}).
    if isinstance(correlations, dict):
        if isinstance(correlations.get("matrix"), dict):
            correlations = correlations["matrix"]
        elif "error" in correlations:
            correlations = {}

    result = {
        "descriptive": descriptive if isinstance(descriptive, dict) else {},
        "correlations": correlations if isinstance(correlations, dict) else {},
        "outliers": outliers if isinstance(outliers, dict) else {},
    }

    # Fallback: recompute from the cleaned dataframe when stored stats are empty.
    if not result["descriptive"]:
        df_path = dataset.get("df_path")
        if df_path and os.path.isfile(df_path):
            rebuilt = _rebuild_statistics_from_df(df_path)
            if rebuilt.get("descriptive"):
                result["descriptive"] = rebuilt["descriptive"]
            if not result["correlations"] and rebuilt.get("correlations"):
                result["correlations"] = rebuilt["correlations"]
            if not result["outliers"] and rebuilt.get("outliers"):
                result["outliers"] = rebuilt["outliers"]

    return result


def _normalize_insights_for_frontend(insights: Any) -> Dict[str, Any]:
    """Ensure insights match the frontend StructuredInsights contract.

    Older payloads stored confidence as a float (0-1). The UI badge expects
    'high' | 'medium' | 'low'. This normalizer is backward-compatible and
    does not drop extra fields (type, interpretation, metrics, ...).
    """
    if not isinstance(insights, dict):
        return {}

    def _label(value: Any) -> str:
        if value is None:
            return "medium"
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("high", "medium", "low"):
                return v
            try:
                value = float(v)
            except ValueError:
                return "medium"
        try:
            score = float(value)
        except (TypeError, ValueError):
            return "medium"
        if score > 1.0:
            score = score / 100.0
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "medium"
        return "low"

    findings = insights.get("key_findings") or []
    normalized = []
    if isinstance(findings, list):
        for f in findings:
            if not isinstance(f, dict):
                continue
            item = dict(f)
            # description is the FE field; finding is the BE/DB alias
            if not item.get("description") and item.get("finding"):
                item["description"] = item["finding"]
            conf = item.get("confidence")
            # Keep numeric score if present for advanced clients
            if isinstance(conf, (int, float)) and "confidence_score" not in item:
                item["confidence_score"] = conf
            item["confidence"] = _label(
                item.get("confidence_score") if item.get("confidence_score") is not None else conf
            )
            normalized.append(item)

    out = dict(insights)
    out["key_findings"] = normalized
    # Guarantee required list fields so the UI never crashes on missing keys
    for key in ("significant_segments", "recommendations", "limitations"):
        if key not in out or out[key] is None:
            out[key] = []
    if "executive_summary" not in out or out["executive_summary"] is None:
        out["executive_summary"] = ""
    return out


def _sanitize(obj: Any) -> Any:
    """Recursively replace NaN, Inf, -Inf with None for JSON compliance."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def get_artifacts(dataset_id: str) -> Dict[str, Any]:
    """The only API contract consumed by the artifact panel."""
    from backend.core.storage import analysis_repository
    from fastapi import HTTPException

    dataset = analysis_repository.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    status = dataset["status"]
    if status != "completed":
        response: Dict[str, Any] = {"status": status}
        if dataset.get("error"):
            response["error"] = dataset["error"]
        return response
    return _sanitize({
        "status": "completed",
        "preview": _build_preview(dataset),
        "statistics": _build_statistics(dataset),
        "insights": _normalize_insights_for_frontend(dataset.get("insights") or {}),
        "charts": dataset.get("charts") or [],
        "chartData": dataset.get("chartData") or [],
        "report": dataset.get("report") or {},
        "cleaning_report": dataset.get("cleaning_report") or {},
    })


def download_report(dataset_id: str):
    """Download the PDF report for a dataset."""
    from backend.core.storage import analysis_repository
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    dataset = analysis_repository.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    path = dataset.get("report_path")
    if dataset["status"] != "completed" or not path:
        raise HTTPException(status_code=409, detail="Report is not available yet.")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Report file is missing on disk.")
    # Prefer inline so browsers can embed the PDF. Export still uses
    # <a download> on the client, which forces a save dialog intentionally.
    try:
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=os.path.basename(path),
            content_disposition_type="inline",
        )
    except TypeError:
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=os.path.basename(path),
            headers={
                "Content-Disposition": (
                    f'inline; filename="{os.path.basename(path)}"'
                ),
            },
        )


def download_processed_dataset(dataset_id: str):
    """Export the dataframe produced by the existing cleaning step as CSV."""
    from backend.core.storage import analysis_repository
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    dataset = analysis_repository.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if dataset["status"] != "completed":
        raise HTTPException(status_code=409, detail="The processed dataset is not available yet.")

    df_path = dataset.get("df_path")
    if not isinstance(df_path, str):
        raise HTTPException(status_code=404, detail="Processed dataset is unavailable.")

    # DataAgent writes this alongside the persisted dataframe. Do not rerun cleaning here.
    cleaned_path = os.path.join(os.path.dirname(df_path), "cleaned_dataset.pkl")
    if not os.path.isfile(cleaned_path):
        raise HTTPException(status_code=404, detail="Processed dataset is unavailable.")

    output_path = os.path.join(os.path.dirname(cleaned_path), "processed_dataset.csv")
    if not os.path.isfile(output_path):
        try:
            import pandas as pd
            df = pd.read_pickle(cleaned_path)
            df.to_csv(output_path, index=False, quoting=csv.QUOTE_ALL, lineterminator='\n', encoding='utf-8')
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Could not export processed dataset: {error}") from error

    original_filename = dataset.get("original_filename")
    source_name = original_filename if isinstance(original_filename, str) else "dataset"
    filename_stem = os.path.splitext(os.path.basename(source_name))[0] or "dataset"
    return FileResponse(output_path, media_type="text/csv", filename=f"{filename_stem}_processed.csv")