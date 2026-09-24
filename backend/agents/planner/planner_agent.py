import os
import re
import warnings
from typing import List, Dict
import pandas as pd
from urllib.parse import urlparse
from collections import Counter
from backend.agents.base.base_agent import BaseAgent
from backend.core.state import AgentState
from backend.models.plan import Plan
from backend.models.chart import ChartConfig


class PlannerAgent(BaseAgent):
    """
    Smart Planner v6 — Context-aware chart generation.
    Analyzes actual data CONTENT (not just dtypes) to generate meaningful charts.
    """

    def __init__(self):
        super().__init__("PlannerAgent")

    def run(self, state: AgentState) -> AgentState:
        self.log_execution(state.session_id)

        df = state.get_df()
        if df is None or df.empty:
            raise ValueError("[PlannerAgent] DataFrame is empty or None")

        profile = state.dataset_profile or {}
        target_info = state.target_detection or {}
        target = target_info.get("target_column")
        task_type = target_info.get("task_type", "unknown")
        target_is_numeric = target_info.get("is_numeric", False)

        # Generate smart charts based on actual data content
        charts = self._generate_smart_charts(df, target, target_is_numeric, profile, state.ml_results)

        steps = self._build_analysis_steps(
            target, profile.get("numeric_columns", []), 
            profile.get("categorical_columns", []),
            profile.get("continuous_columns", []),
            profile.get("discrete_columns", []),
            profile.get("binary_columns", []),
            profile.get("date_columns", [])
        )

        analysis_focus = self._build_analysis_focus(
            target, profile.get("numeric_columns", []), 
            profile.get("categorical_columns", []),
            profile.get("continuous_columns", []),
            profile.get("discrete_columns", []),
            profile.get("binary_columns", []),
            profile.get("date_columns", [])
        )

        plan = Plan(
            steps=steps,
            charts=charts,
            requires_report=True,
            requires_cleaning=False,
            analysis_focus=analysis_focus,
        )

        state.plan = plan
        self.logger.info(f"Smart Planner generated {len(charts)} chart(s): {[c.chart_type for c in charts]}")
        for i, c in enumerate(charts):
            self.logger.info(f"  Chart {i}: {c.chart_type} | {c.title}")

        return state

    # ============================================================
    # COLUMN TYPE DETECTION (Content-aware, not just dtype)
    # ============================================================

    def _detect_column_types(self, df) -> Dict[str, str]:
        """
        Detect the REAL semantic type of each column based on content.
        Returns: {column_name: semantic_type}
        """
        types = {}
        for col in df.columns:
            types[col] = self._classify_column(df, col)
        return types

    def _classify_column(self, df, col: str) -> str:
        """Classify a single column by its actual content."""
        sample = df[col].dropna().head(100)
        if len(sample) == 0:
            return "empty"

        col_lower = str(col).lower()

        # === FIX 1: ID detection (EARLY — before anything else) ===
        id_keywords = {
            "id", "uuid", "guid", "_id", "pk", "passengerid", "userid",
            "customerid", "dbn", "code", "invoiceno", "invoice_no", "invoice",
            "stockcode", "stock_code", "hostid", "host_id", "listingid",
        }
        # Name hit is enough for well-known transaction keys even when
        # unique_ratio is moderate (one invoice → many line items).
        strong_id_tokens = {
            "invoiceno", "invoice_no", "stockcode", "stock_code",
            "hostid", "host_id", "passengerid", "customerid", "listingid",
        }
        if any(k in col_lower for k in strong_id_tokens):
            return "id"
        if any(k in col_lower for k in id_keywords):
            if sample.nunique() / max(len(df), 1) > 0.9:
                return "id"

        # === FIX 2: Numeric columns should be numeric FIRST ===
        # CSVs often load numeric measures as object/category because of
        # missing cells.  Detect lossless numeric strings before categorical
        # logic so measures such as *_confidence are not planned as huge bar
        # charts.
        if not pd.api.types.is_numeric_dtype(df[col]):
            numeric_probe = pd.to_numeric(
                df[col].dropna().astype("string").str.strip().str.replace(",", "", regex=False),
                errors="coerce",
            )
            if len(numeric_probe) >= 5 and numeric_probe.notna().mean() >= 0.98:
                # Protected identifiers/codes must remain categorical.
                protected_tokens = {"id", "uuid", "guid", "code", "zip", "postal"}
                if not any(tok in col_lower for tok in protected_tokens):
                    return "numeric"

        # Only override to date if column name strongly suggests date AND values look like dates
        if pd.api.types.is_numeric_dtype(df[col]):
            date_keywords = {"date", "time", "timestamp", "created", "updated", 
                             "published", "year", "month", "day"}
            if any(k in col_lower for k in date_keywords):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    parsed = pd.Series(
                        pd.to_datetime(sample.astype("string"), errors="coerce"),
                        index=sample.index,
                    )
                if parsed.notna().mean() > 0.5:
                    valid_dates = parsed.dropna()
                    if len(valid_dates) > 0 and valid_dates.min().year > 1990:
                        return "date"

            # Low-cardinality numeric columns are not automatically categorical.
            # Counts/measures such as retweet_count can legitimately have only a
            # few observed values in a dataset. Only clearly discrete domain
            # fields should be demoted to categorical.
            discrete_keywords = {
                "class", "pclass", "grade", "rating", "rank", "level",
                "children", "age_group", "year", "month", "day"
            }
            if sample.nunique() <= 20 and any(k in col_lower for k in discrete_keywords):
                return "categorical"

            return "numeric"

        # Numeric-looking object/string columns must be treated as numeric
        # before low-cardinality/categorical heuristics. CSV type inference can
        # produce object dtype when a numeric measure contains missing values
        # or a small amount of formatting noise.
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            numeric_probe = pd.to_numeric(
                sample.astype("string").str.strip().str.replace(",", "", regex=False),
                errors="coerce",
            )
            if len(numeric_probe) >= 5 and numeric_probe.notna().mean() >= 0.98:
                return "numeric"

        # 1. URL/Link detection
        if any(k in col_lower for k in ["link", "url", "href", "web", "source_url", "domain"]):
            return "url"
        url_pattern = re.compile(r'^https?://')
        url_ratio = sample.astype(str).str.match(url_pattern).mean()
        if url_ratio > 0.5:
            return "url"

        # 2. Date/Datetime detection — STRICTENED with Warning Suppression & Infer Format
        if any(k in col_lower for k in ["date", "time", "timestamp", "created", "updated", "published"]):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                date_ratio = pd.to_datetime(sample, errors="coerce", format="mixed").notna().mean()
            if date_ratio > 0.5:
                return "date"

        # Only classify as date by content if name doesn't contradict
        if not pd.api.types.is_numeric_dtype(df[col]):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                # Category/string columns can produce a Categorical result in
                # pandas. Convert through string and explicitly materialize a
                # datetime Series so min()/max() are always valid.
                parsed = pd.Series(
                    pd.to_datetime(
                        sample.astype("string"),
                        errors="coerce",
                        format="mixed",
                    ),
                    index=sample.index,
                )
                date_ratio = parsed.notna().mean()

            # REQUIRE: high ratio AND reasonable date range for non-date-named cols
            if date_ratio > 0.8:
                valid_dates = parsed.dropna()
                if len(valid_dates) > 0:
                    min_date = valid_dates.min()
                    max_date = valid_dates.max()
                    if min_date.year > 1990 and max_date.year < 2100:
                        return "date"

        # 3. Name/Username detection
        if any(k in col_lower for k in ["name", "user", "author", "creator", "handle", "screen_name"]):
            return "name"

        # 4. Email detection
        email_pattern = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
        email_ratio = sample.astype(str).str.match(email_pattern).mean()
        if email_ratio > 0.3:
            return "email"

        # 5. Phone detection
        phone_pattern = re.compile(r'^[\+\d\s\-\(\)]{7,20}$')
        phone_ratio = sample.astype(str).str.match(phone_pattern).mean()
        if phone_ratio > 0.3:
            return "phone"

        # 6. Currency/Money detection
        # Use word-boundary style matching so "fare" does not match "prefarea"
        # and "price" does not match unrelated compounds.
        currency_name_keywords = {
            "price", "cost", "revenue", "salary", "wage",
            "fee", "amount", "budget", "income", "fare",
            "payment", "charge", "total", "subtotal",
        }
        # Tokenize on non-letters so we match whole tokens only.
        tokens = set(re.findall(r"[a-z]+", col_lower))
        if tokens & currency_name_keywords:
            # Only classify as currency if the column is actually numeric /
            # money-like. A yes/no column that happens to contain a keyword
            # token (rare) must stay categorical.
            if pd.api.types.is_numeric_dtype(df[col]):
                return "currency"
            currency_pattern = re.compile(
                r"^[$€£¥]?\s*[\d,]+\.?\d*\s*[$€£¥]?$"
            )
            currency_ratio = sample.astype(str).str.match(currency_pattern).mean()
            if currency_ratio > 0.3:
                return "currency"

        # 7. Percentage detection — token-boundary only.
        # Substring match on "rate" wrongly classifies columns such as
        # test_preparation_course ("prepaRATE-ion") as percentage.
        tokens = set(re.findall(r"[a-z0-9]+", col_lower))
        pct_name_tokens = {"percent", "percentage", "pct", "ratio", "probability", "prob"}
        # "rate" and "score" are ambiguous (heart_rate, test_score, preparation)
        # — only accept when the column is numeric-like or values look like %.
        if tokens & pct_name_tokens:
            return "percentage"
        if tokens & {"rate", "score"} and pd.api.types.is_numeric_dtype(df[col]):
            return "percentage"
        pct_pattern = re.compile(r'^-?\d+\.?\d*\s*%$')
        pct_ratio = sample.astype(str).str.match(pct_pattern).mean()
        if pct_ratio > 0.3:
            return "percentage"

        # 8. Long text / Content detection
        avg_len = sample.astype(str).str.len().mean()
        if avg_len > 100:
            if any(k in col_lower for k in ["content", "body", "text", "description", 
                                            "article", "post", "review", "comment", "message"]):
                return "long_text"
            if sample.nunique() / len(sample) > 0.8:
                return "long_text"

        # 9. Short text / Title detection
        if avg_len > 20 and sample.nunique() / len(sample) > 0.5:
            if any(k in col_lower for k in ["title", "headline", "subject", "topic", "caption"]):
                return "title"
            return "short_text"

        # 10. Categorical (low cardinality)
        if sample.nunique() <= 20 or (sample.nunique() / len(df) < 0.05):
            return "categorical"

        # 11. Numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            return "numeric"

        # 12. Default
        return "other"

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(str(url))
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return "unknown"

    def _is_identifier(self, df, col: str, id_cols: List[str]) -> bool:
        """Helper to determine if a column acts as an identifier."""
        if col in id_cols:
            return True
        col_lower = str(col).lower()
        compact = re.sub(r"[^a-z0-9]+", "", col_lower)
        strong_id_tokens = {
            "invoiceno", "invoice", "stockcode", "hostid", "host_id",
            "passengerid", "customerid", "listingid", "orderid", "transactionid",
        }
        if compact in strong_id_tokens or any(t in compact for t in strong_id_tokens):
            return True
        id_keywords = {
            "id", "uuid", "guid", "_id", "pk", "passengerid", "userid",
            "customerid", "dbn", "code", "invoiceno", "stockcode", "hostid",
        }
        if any(k in col_lower for k in id_keywords):
            sample = df[col].dropna()
            if len(sample) > 0 and sample.nunique() / max(len(df), 1) > 0.9:
                return True
        return False

    # ============================================================
    # SMART CHART GENERATION
    # ============================================================

    def _generate_smart_charts(self, df, target, target_is_numeric, profile, ml_results=None) -> List[ChartConfig]:
        """Generate charts based on actual data content and insights potential."""
        charts = []

        # Detect semantic types
        col_types = self._detect_column_types(df)
        self.logger.info(f"[SmartPlanner] Column types: {col_types}")

        def _is_annotation_col(name: str) -> bool:
            """Skip derived flags / annotation columns (e.g. bmi_OutlierFlag)."""
            n = str(name).lower()
            return (
                n.endswith("_outlierflag")
                or n.endswith("_outlier_flag")
                or n.endswith("_flag")
                and ("outlier" in n or "missing" in n or "anomaly" in n)
            )

        # Group columns by type
        url_cols = [c for c, t in col_types.items() if t == "url" and c != target]
        date_cols = [c for c, t in col_types.items() if t == "date" and c != target]
        # High-cardinality categoricals are not useful standalone bar charts;
        # they are typically identifiers, free text, or continuous values that
        # were loaded with an object/category dtype.
        categorical_cols = [
            c for c, t in col_types.items()
            if t == "categorical"
            and c != target
            and not _is_annotation_col(c)
            and df[c].nunique(dropna=True) <= 35
        ]
        numeric_cols = [
            c for c, t in col_types.items()
            if t == "numeric" and c != target and not _is_annotation_col(c)
        ]
        currency_cols = [
            c for c, t in col_types.items()
            if t == "currency" and c != target and not _is_annotation_col(c)
        ]
        percentage_cols = [
            c for c, t in col_types.items()
            if t == "percentage" and c != target and not _is_annotation_col(c)
        ]
        long_text_cols = [c for c, t in col_types.items() if t == "long_text" and c != target]
        title_cols = [c for c, t in col_types.items() if t == "title" and c != target]
        id_cols = [c for c, t in col_types.items() if t == "id"]

        # === CHART 1: Target Distribution (ALWAYS) ===
        if target and target in df.columns:
            if target_is_numeric:
                charts.append(ChartConfig(
                    chart_type="histogram",
                    x_axis=target,
                    y_axis=None,
                    title=f"Distribution of {target}",
                    x_label=target,
                    y_label="Count",
                ))
            else:
                charts.append(ChartConfig(
                    chart_type="bar",
                    x_axis=target,
                    y_axis=None,
                    title=f"Distribution of {target}",
                    x_label=target,
                    y_label="Count",
                ))

        # === CHART 2: URL/Source Analysis (if URLs exist) ===
        for url_col in url_cols[:1]:
            if target and not target_is_numeric:
                charts.append(ChartConfig(
                    chart_type="bar",
                    x_axis=target,
                    y_axis=url_col,
                    title=f"Source Distribution by {target.title()}",
                    x_label=target,
                    y_label="Source Count",
                ))

        # === CHART 3: Categorical Analysis (if categorical target) ===
        if not target_is_numeric and target:
            for cat_col in categorical_cols[:2]:
                if cat_col != target:
                    charts.append(ChartConfig(
                        chart_type="bar",
                        x_axis=cat_col,
                        y_axis=None,
                        title=f"Distribution of {cat_col.title()}",
                        x_label=cat_col,
                        y_label="Count",
                    ))

        # === CHART 4: Numeric by Categorical Target ===
        if not target_is_numeric and target:
            for num_col in numeric_cols[:2]:
                if self._is_identifier(df, num_col, id_cols):
                    continue
                charts.append(ChartConfig(
                    chart_type="box",
                    x_axis=target,
                    y_axis=num_col,
                    title=f"{num_col.title()} by {target.title()}",
                    x_label=target,
                    y_label=num_col,
                ))

        # === CHART 5: Currency/Amount Analysis ===
        for curr_col in currency_cols[:1]:
            if target and not target_is_numeric:
                charts.append(ChartConfig(
                    chart_type="box",
                    x_axis=target,
                    y_axis=curr_col,
                    title=f"{curr_col.title()} by {target.title()}",
                    x_label=target,
                    y_label=curr_col,
                ))
            elif target and target_is_numeric:
                charts.append(ChartConfig(
                    chart_type="scatter",
                    x_axis=curr_col,
                    y_axis=target,
                    title=f"{curr_col.title()} vs {target.title()}",
                    x_label=curr_col,
                    y_label=target,
                ))

        # === CHART 6: Percentage/Score Analysis ===
        for pct_col in percentage_cols[:1]:
            if target and not target_is_numeric:
                charts.append(ChartConfig(
                    chart_type="box",
                    x_axis=target,
                    y_axis=pct_col,
                    title=f"{pct_col.title()} by {target.title()}",
                    x_label=target,
                    y_label=pct_col,
                ))

        # === CHART 7: Missing Data Analysis ===
        missing_cols = [c for c in df.columns if df[c].isna().sum() > 0 and c != target]
        if missing_cols and target and not target_is_numeric:
            miss_col = max(missing_cols, key=lambda c: df[c].isna().sum())
            miss_pct = df[miss_col].isna().sum() / len(df) * 100
            if miss_pct > 5:
                charts.append(ChartConfig(
                    chart_type="bar",
                    x_axis=target,
                    y_axis=f"__missing_rate__:{miss_col}",
                    title=f"Missing {miss_col.title()} Rate by {target.title()}",
                    x_label=target,
                    y_label=f"Missing {miss_col.title()} (%)",
                ))

        # === CHART 8: Date/Temporal Analysis ===
        for dt_col in date_cols[:1]:
            # FIX: Skip ID columns even if misclassified as date
            if col_types.get(dt_col) == "id" or self._is_identifier(df, dt_col, id_cols):
                continue
            if target:
                if target_is_numeric:
                    charts.append(ChartConfig(
                        chart_type="line",
                        x_axis=dt_col,
                        y_axis=target,
                        title=f"{target.title()} Over Time",
                        x_label="Date",
                        y_label=target,
                    ))
                else:
                    charts.append(ChartConfig(
                        chart_type="line",
                        x_axis=dt_col,
                        y_axis="count",
                        title=f"Records Over Time by {target.title()}",
                        x_label="Date",
                        y_label="Count",
                    ))

        # === CHART 9: Numeric Target Correlations ===
        if target_is_numeric and target:
            if len(numeric_cols) >= 2:
                for num_col in numeric_cols[:3]:
                    # FIX: never plot identifiers or target itself
                    if num_col == target or self._is_identifier(df, num_col, id_cols):
                        continue

                    n_unique = df[num_col].nunique()

                    # FIX: Binary/discrete → Box plot, Continuous → Scatter
                    if n_unique <= 5:
                        charts.append(ChartConfig(
                            chart_type="box",
                            x_axis=num_col,
                            y_axis=target,
                            title=f"{target.title()} by {num_col.title()}",
                            x_label=num_col,
                            y_label=target,
                        ))
                    else:
                        charts.append(ChartConfig(
                            chart_type="scatter",
                            x_axis=num_col,
                            y_axis=target,
                            title=f"{num_col.title()} vs {target.title()}",
                            x_label=num_col,
                            y_label=target,
                        ))

        # === CHART 10: Categorical vs Numeric Target ===
        # For binary / low-cardinality targets (e.g. Survived 0/1), a box plot
        # collapses to two horizontal lines and is hard to read. Prefer a bar
        # chart of the mean target rate per category instead.
        if target_is_numeric and target and categorical_cols:
            target_nunique = int(df[target].nunique(dropna=True))
            is_binary_like = target_nunique <= 5
            filtered_cats = [
                c for c in categorical_cols
                if col_types.get(c) not in ("id", "name", "url")
            ]
            for cat_col in filtered_cats[:5]:
                if cat_col == target or self._is_identifier(df, cat_col, id_cols):
                    continue
                if is_binary_like:
                    charts.append(ChartConfig(
                        chart_type="bar",
                        x_axis=cat_col,
                        y_axis=target,
                        title=f"Mean {target.title()} by {cat_col.title()}",
                        x_label=cat_col,
                        y_label=f"Mean {target}",
                    ))
                else:
                    charts.append(ChartConfig(
                        chart_type="box",
                        x_axis=cat_col,
                        y_axis=target,
                        title=f"{target.title()} by {cat_col.title()}",
                        x_label=cat_col,
                        y_label=target,
                    ))

        # === NEW: ML Charts ===
        charts = self._add_ml_charts(charts, ml_results, target)

        # === FALLBACK ===
        if not charts and target:
            charts.append(ChartConfig(
                chart_type="bar",
                x_axis=target,
                y_axis=None,
                title=f"Overview of {target}",
                x_label=target,
                y_label="Count",
            ))

        charts = self._deduplicate_charts(charts)
        return charts

    def _add_ml_charts(self, charts, ml_results, target):
        """Add ML-specific charts based on model results."""
        if not ml_results or ml_results.status != "success":
            return charts

        # Feature Importance chart
        if ml_results.feature_importance:
            charts.append(ChartConfig(
                chart_type="bar",
                x_axis="feature",
                y_axis="importance",
                title=f"ML Feature Importance ({ml_results.selected_model})",
                x_label="Feature",
                y_label="Importance",
            ))

        # Classification: Confusion Matrix
        if ml_results.problem_type in ("classification", "text_classification"):
            if ml_results.confusion_matrix:
                charts.append(ChartConfig(
                    chart_type="heatmap",
                    x_axis="predicted",
                    y_axis="actual",
                    title="Confusion Matrix",
                    x_label="Predicted",
                    y_label="Actual",
                ))

        # Regression: Actual vs Predicted
        if ml_results.problem_type == "regression":
            if ml_results.actual_vs_predicted:
                charts.append(ChartConfig(
                    chart_type="scatter",
                    x_axis="actual",
                    y_axis="predicted",
                    title="Actual vs Predicted",
                    x_label=f"Actual {target}",
                    y_label=f"Predicted {target}",
                ))

            # Residuals
            if ml_results.residuals:
                charts.append(ChartConfig(
                    chart_type="histogram",
                    x_axis="residual",
                    y_axis=None,
                    title="Residual Distribution",
                    x_label="Residual",
                    y_label="Count",
                ))

        return charts

    def _deduplicate_charts(self, charts: List[ChartConfig]) -> List[ChartConfig]:
        seen = set()
        unique = []
        for c in charts:
            key = f"{c.chart_type}:{c.x_axis}:{c.y_axis}"
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _build_analysis_steps(self, target, numeric_cols, categorical_cols,
                              continuous_cols, discrete_cols, binary_cols, date_cols) -> List[str]:
        steps = ["Analyze query", "Detect column semantics", "Select insight-driven charts"]
        if target:
            steps.append(f"Profile target variable: {target}")
        if continuous_cols:
            steps.append(f"Explore continuous variables: {', '.join(continuous_cols[:3])}")
        if categorical_cols:
            steps.append(f"Analyze categorical distributions: {', '.join(categorical_cols[:3])}")
        if binary_cols:
            steps.append(f"Compare binary groups: {', '.join(binary_cols[:2])}")
        if date_cols:
            steps.append(f"Analyze temporal trends: {', '.join(date_cols[:1])}")
        steps.append("Generate visualizations")
        steps.append("Build final report")
        return steps

    def _build_analysis_focus(self, target, numeric_cols, categorical_cols,
                              continuous_cols, discrete_cols, binary_cols, date_cols) -> List[str]:
        focus = []
        if target:
            focus.append(f"Distribution of {target}")
            for col in continuous_cols[:2]:
                if col != target:
                    focus.append(f"Relationship between {col} and {target}")
            for col in categorical_cols[:2]:
                if col != target:
                    focus.append(f"Impact of {col} on {target}")
            for col in binary_cols[:2]:
                if col != target:
                    focus.append(f"{col} effect on {target}")
            for col in date_cols[:1]:
                focus.append(f"Temporal patterns in {target}")
        else:
            focus.append("Explore dataset structure and patterns")
            if numeric_cols:
                focus.append(f"Analyze numeric variables: {', '.join(numeric_cols[:3])}")
            if categorical_cols:
                focus.append(f"Analyze categorical variables: {', '.join(categorical_cols[:3])}")
        return focus