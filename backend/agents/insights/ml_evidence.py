"""ML evidence integration for the Insights Agent."""
from backend.utils.target_detection import is_identifier_column


def _add_ml_evidence(evidence, ml_results, df=None):
    """Integrate ML results as evidence."""
    if not ml_results or ml_results.status != "success":
        return evidence

    fi = ml_results.feature_importance
    if not fi:
        return evidence

    target = (evidence.get("target_detection") or {}).get("target_column") or ""
    target_lower = str(target).lower()
    LEAKAGE_KEYWORDS = ("confidence", "prob", "score", "likelihood", "certainty")

    ml_top5 = []
    for item in fi[:10]:
        feature_name = str(item.feature)
        feature_lower = feature_name.lower()

        # FIX 1a: Skip leakage columns (meta-info about the target itself)
        if (target_lower and target_lower in feature_lower
                and feature_lower != target_lower
                and any(kw in feature_lower for kw in LEAKAGE_KEYWORDS)):
            continue

        if df is not None and feature_name in df.columns:
            series = df[feature_name]

            if is_identifier_column(series, feature_name):
                continue

            missing_pct = series.isna().sum() / max(1, len(series))
            if missing_pct > 0.80:
                continue
            elif missing_pct > 0.50:
                item.importance *= 0.25
            elif missing_pct > 0.30:
                item.importance *= 0.5

            # Structural leakage checks (presence-side AND missing-side)
            # A feature is definitional leakage when its presence (or absence)
            # almost perfectly determines the target class.
            if target and target in df.columns and missing_pct > 0.05:
                present_mask = series.notna()
                missing_mask = ~present_mask

                # Presence side: when feature is present, one target class dominates
                if present_mask.any():
                    target_when_present = df.loc[present_mask, target]
                    if len(target_when_present) >= 10:
                        present_mode_pct = target_when_present.value_counts(normalize=True).iloc[0]
                        if present_mode_pct > 0.95:
                            dominant = target_when_present.mode().iloc[0]
                            continue

                # Missing side: when feature is missing, one target class dominates
                if missing_mask.any():
                    target_when_missing = df.loc[missing_mask, target]
                    if len(target_when_missing) >= 10:
                        missing_mode_pct = target_when_missing.value_counts(normalize=True).iloc[0]
                        if missing_mode_pct > 0.85:
                            dominant = target_when_missing.mode().iloc[0]
                            continue

                ratio = series.nunique(dropna=True) / max(1, len(series))
                if ratio > 0.2:
                    continue

        ml_top5.append({
            "feature": feature_name,
            "importance": item.importance,
            "type": "ml_predictive"
        })
        if len(ml_top5) >= 5:
            break

    # Merge with existing feature importance
    existing = evidence.get("feature_importance", {})
    if isinstance(existing, dict):
        existing_top5 = existing.get("top_5", [])
        combined = existing_top5 + ml_top5
        combined.sort(key=lambda x: x.get("importance", 0), reverse=True)
        evidence["feature_importance"] = {
            "target": existing.get("target"),
            "method": "mixed_statistical_ml",
            "top_5": combined[:5]
        }

    evidence["ml_analysis"] = {
        "selected_model": ml_results.selected_model,
        "used_fallback": ml_results.used_fallback,
        "problem_type": ml_results.problem_type,
        "metrics": ml_results.metrics.model_dump() if ml_results.metrics else {},
        "top_predictive_features": [
            {"feature": f, "importance": imp} for f, imp in
            [(x["feature"], x["importance"]) for x in ml_top5]
        ],
        "warnings": ml_results.warnings,
    }
    return evidence


def _build_limitations(ml_results):
    """Build limitations from ML results."""
    limitations = []
    if ml_results:
        if ml_results.status == "skipped":
            limitations.append(f"ML analysis skipped: {ml_results.reason}")
        elif ml_results.status == "failed":
            limitations.append(f"ML model training failed: {ml_results.reason}")
        elif ml_results.used_fallback:
            limitations.append(f"Primary model failed; used fallback: {ml_results.fallback_model}")
        if ml_results.warnings:
            limitations.extend(ml_results.warnings)
    return limitations