import math
import os
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState
from backend.statistics import StatisticalEngine
from backend.tools.cleaner import clean_data_tool
from backend.tools.csv_reader import read_any_file


def _json_safe(value: Any):
    if value is None:
        return None

    if isinstance(value, (np.bool_, bool)):
        return bool(value)

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # pandas NA / NaT
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass

    return str(value)


class DataAgent(BaseAgent):
    def __init__(self):
        super().__init__("DataAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)

        try:
            print("DATA STEP 1: reading file")

            # Never cap the dataset at 1000 rows. Every downstream cleaning,
            # missing-value, duplicate, statistics and outlier calculation
            # must see the complete uploaded dataset.
            raw_df = read_any_file(state.file_path)

            if raw_df is None or raw_df.empty:
                raise ValueError("Uploaded file contains no usable data.")

            os.makedirs(state.session_dir, exist_ok=True)

            raw_pickle = os.path.join(state.session_dir, "raw_dataset.pkl")
            raw_df.to_pickle(raw_pickle)

            # Keep df_path pointing at the original/raw data for traceability.
            state.df_path = raw_pickle

            print("DATA STEP 2: cleaning + preprocessing")
            cleaned_pickle = os.path.join(
                state.session_dir, "cleaned_dataset.pkl"
            )

            clean_result = clean_data_tool(
                raw_pickle,
                output_path=cleaned_pickle,
                add_features=True,
                impute_missing=True,
                add_outlier_flags=True,
                optimize_dtypes=True,
                outlier_threshold=1.5,
            )

            if not isinstance(clean_result, dict) or clean_result.get("status") != "success":
                raise RuntimeError(
                    f"Data cleaning failed: {clean_result.get('error', clean_result)}"
                )

            if not os.path.exists(cleaned_pickle):
                raise RuntimeError("Cleaner reported success but produced no output file.")

            cleaned_df = pd.read_pickle(cleaned_pickle)
            if cleaned_df.empty:
                raise ValueError("Cleaning produced an empty dataset.")


            # NOTE: this step used to also build a separate
            # "model_ready_dataset.pkl" here via prepare_model_data_tool()
            # (one-hot encoding + scaling of the *entire* dataset, with
            # target_column=None). That artifact is never read anywhere
            # else in the codebase — backend/ml/analyzer.py builds its own
            # sklearn ColumnTransformer (StandardScaler/OneHotEncoder) from
            # the cleaned analysis dataframe once the real target column is
            # known, which is also the correct place to do it (encoding a
            # dataset before the target is known risks encoding/scaling the
            # target itself). Running full one-hot encoding + scaling over
            # every column of every uploaded dataset just to write a file
            # that's discarded was pure wasted work on every single
            # preprocessing run, regardless of dataset type or size, so it
            # has been removed. prepare_model_data_tool() itself is left in
            # tools/cleaner.py in case a future caller needs an ad-hoc
            # model-ready export.

            # Stats/correlation/outlier evidence operate on the cleaned
            # analysis dataset. Since the Statistical Engine refactor, ONE
            # read-only engine run produces all structured results; the
            # historical per-tool pickle round-trips are gone.
            # Pass the COMPLETE cleaned dataframe to the Statistical Engine.
            # The engine itself excludes identifiers from analyses where they
            # are statistically meaningless (correlation/outliers), while
            # still reporting their structural/category statistics.
            print("DATA STEP 3: statistical analysis (StatisticalEngine)")
            stats_engine = StatisticalEngine(
                correlation_method="spearman",
                outlier_method="iqr",
                outlier_threshold=1.5,
            )
            statistical_results = stats_engine.analyze(cleaned_df)

            # Structured engine results travel in state for every downstream
            # consumer (insights / visualization / report / API).
            state.statistical_results = statistical_results.model_dump(
                mode="json"
            )

            # Extract views directly from StatisticalResults (modern contract).
            stats_clean = {}
            categorical_stats = {}
            for col_name, summary in statistical_results.column_statistics.items():
                kind = getattr(summary, "kind", None)
                if kind == "numeric":
                    stats_clean[col_name] = {
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
                        stats_clean[col_name]["percentiles"] = {
                            k: v for k, v in summary.percentiles.items() if v is not None
                        }
                    if summary.count > 1:
                        stats_clean[col_name]["cv"] = summary.cv
                        stats_clean[col_name]["sem"] = summary.sem
                    if summary.count == 0:
                        stats_clean[col_name].pop("unique_count", None)
                        stats_clean[col_name]["note"] = "All values are null"
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
                    categorical_stats[col_name] = {
                        "count": summary.count,
                        "null_count": summary.null_count,
                        "null_pct": summary.null_pct,
                        "unique_count": unique_count,
                        "top_values": top_values,
                    }

            corr_clean = {}
            if statistical_results.correlations and len(statistical_results.correlations.columns_used) >= 2:
                corr_clean = {
                    outer: {
                        inner: (round(float(value), 3) if value is not None else value)
                        for inner, value in row.items()
                    }
                    for outer, row in statistical_results.correlations.matrix.items()
                }

            outliers_clean = {}
            if statistical_results.outlier_evidence:
                for item in statistical_results.outlier_evidence.columns:
                    if not item.analyzed:
                        if item.note and "bounded" in item.note.lower():
                            outliers_clean[item.column] = {
                                "count": "N/A",
                                "percentage": "Skipped",
                                "note": "Excluded: bounded domain (e.g., confidence, probability, rating)",
                                "action": "none",
                            }
                        else:
                            outliers_clean[item.column] = {
                                "count": 0,
                                "percentage": 0.0,
                                "note": item.note or "Not analyzed",
                            }
                        continue

                    if item.count == 0:
                        outliers_clean[item.column] = {
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
                    outliers_clean[item.column] = dict(sorted(entry.items()))

            llm_context = (
                f"Dataset Summary: {len(cleaned_df)} rows, "
                f"{len(cleaned_df.columns)} columns. "
                f"Columns: {', '.join(map(str, cleaned_df.columns))}. "
                f"Missing values remaining: {int(cleaned_df.isna().sum().sum())}."
            )

            state.df = cleaned_df
            self.logger.info(f"State updated with cleaned DataFrame: {len(cleaned_df)} rows, {len(cleaned_df.columns)} columns")

            state.data_summary = {
                "columns": [str(c) for c in cleaned_df.columns],
                "rows": _json_safe(
                    cleaned_df.head(20).to_dict(orient="records")
                ),
                "total_rows": len(cleaned_df),
                "total_cols": len(cleaned_df.columns),
                "statistics": _json_safe(stats_clean),
                "categorical_statistics": _json_safe(categorical_stats),
                "correlation": _json_safe(corr_clean),
                "outliers": _json_safe(outliers_clean),
                "cleaning_report": _json_safe(
                    clean_result.get("report", {})
                ),
                "column_types": {
                    str(col): str(dtype)
                    for col, dtype in cleaned_df.dtypes.items()
                },
                "missing_values_remaining": int(
                    cleaned_df.isna().sum().sum()
                ),
                "llm_context": llm_context,
            }

            print("DATA STEP 6: DONE")
            return state

        except Exception as e:
            self.logger.error(f"DATA AGENT ERROR: {str(e)}")
            raise