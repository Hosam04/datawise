from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.database.models import (
    Dataset,
    Analysis,
    DatasetProfile,
    CleaningRun,
    CleaningAction,
    Insight,
    Visualization,
    MLResult,
    Report,
    ReportVisualization,
)


def _file_content_hash(file_path: str) -> Optional[str]:
    """SHA-256 of file bytes. Returns None if the path is missing/unreadable."""
    try:
        if not file_path or not os.path.isfile(file_path):
            return None
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _schema_hash_from_preview(preview: dict) -> Optional[str]:
    """Stable hash of column names (+ dtypes when available)."""
    if not isinstance(preview, dict):
        return None
    columns = preview.get("columns") or []
    # columns may be list[str] or list[dict] with name/dtype
    normalized: list[dict] = []
    for col in columns:
        if isinstance(col, dict):
            normalized.append(
                {
                    "name": str(col.get("name") or col.get("column") or ""),
                    "dtype": str(col.get("dtype") or col.get("type") or ""),
                }
            )
        else:
            normalized.append({"name": str(col), "dtype": ""})
    if not normalized:
        return None
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dataset_fingerprint(content_hash: Optional[str], schema_hash: Optional[str]) -> Optional[str]:
    if not content_hash and not schema_hash:
        return None
    raw = f"{content_hash or ''}:{schema_hash or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_dataset_and_analysis(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: str,
    original_filename: str,
    file_path: str,
    file_size: Optional[int],
    mime_type: Optional[str],
    user_query: str,
) -> tuple[Dataset, Analysis]:
    """Create (or reuse) a Dataset row and always create a new Analysis.

    Re-uploading the same file for the same user must NOT insert a second
    Dataset with the same (user_id, dataset_fingerprint). That violated
    uq_dataset_user_fingerprint and returned HTTP 500.

    Strategy:
      1. Hash file bytes (content_hash).
      2. Look up an existing Dataset for this user with matching
         content_hash OR dataset_fingerprint (provisional fingerprint is
         content_hash at upload time).
      3. If found → reuse it (refresh storage/session metadata) and only
         insert a new Analysis.
      4. If not found → insert Dataset + Analysis as before.
    """
    content_hash = _file_content_hash(file_path)

    existing: Optional[Dataset] = None
    if content_hash:
        existing = (
            db.query(Dataset)
            .filter(
                Dataset.user_id == user_id,
                (
                    (Dataset.content_hash == content_hash)
                    | (Dataset.dataset_fingerprint == content_hash)
                ),
            )
            .order_by(Dataset.created_at.desc())
            .first()
        )

    try:
        if existing is not None:
            # Reuse dataset — update pointers to the latest upload session
            # without changing the unique fingerprint key.
            dataset = existing
            dataset.session_id = session_id
            dataset.storage_key = file_path
            dataset.name = original_filename or dataset.name
            dataset.original_filename = original_filename or dataset.original_filename
            if file_size is not None:
                dataset.file_size = file_size
            if mime_type:
                dataset.mime_type = mime_type
            if content_hash and not dataset.content_hash:
                dataset.content_hash = content_hash
            # Keep dataset_fingerprint stable; complete_analysis may refine it.
        else:
            dataset = Dataset(
                user_id=user_id,
                session_id=session_id,
                name=original_filename,
                original_filename=original_filename,
                storage_key=file_path,
                file_size=file_size,
                mime_type=mime_type,
                content_hash=content_hash,
                # schema_hash / refined fingerprint filled in complete_analysis
                # once column metadata is known.
                schema_hash=None,
                dataset_fingerprint=content_hash,  # provisional; refined after profile
            )
            db.add(dataset)
            db.flush()

        analysis = Analysis(
            dataset_id=dataset.id,
            user_query=user_query,
            status="pending",
            started_at=datetime.now(timezone.utc),
        )
        db.add(analysis)
        db.commit()
        db.refresh(dataset)
        db.refresh(analysis)
    except Exception:
        db.rollback()
        raise

    return dataset, analysis


def mark_analysis_failed(db: Session, analysis_id: uuid.UUID, error: str) -> None:
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return
        analysis.status = "failed"
        analysis.error_message = (error or "")[:2000]
        analysis.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise


def complete_analysis(
    db: Session,
    *,
    analysis_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return

        preview = payload.get("preview") or {}
        insights_data = payload.get("insights") or {}
        ml = payload.get("ml_analysis") or {}
        target_det = (
            payload.get("target_detection")
            or ml.get("target_detection")
            or {}
        )
        profile_data = payload.get("dataset_profile") or {}
        charts = payload.get("chartData") or payload.get("charts") or []
        cleaning_report = payload.get("cleaning_report") or {}
        plan_data = payload.get("plan")

        # ── Analysis ──────────────────────────────────────────
        analysis.status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.analysis_type = payload.get("analysis_type") or analysis.analysis_type
        analysis.target_column = (
            target_det.get("target_column")
            or target_det.get("column")
            or analysis.target_column
        )
        analysis.target_detection = target_det or None
        analysis.plan_json = _as_dict(plan_data)
        analysis.statistics_json = payload.get("statistics") or {}
        analysis.evidence_json = {
            "correlations": payload.get("correlations"),
            "outliers": payload.get("outliers"),
            "dataset_profile": profile_data,
        }

        # ── Dataset row/col counts + schema fingerprint ───────
        dataset = analysis.dataset
        if dataset:
            dataset.row_count = preview.get("total_rows")
            dataset.column_count = preview.get("total_cols")
            schema_hash = _schema_hash_from_preview(preview)
            if schema_hash:
                dataset.schema_hash = schema_hash
            # Prefer content_hash already set at upload; fall back to storage file.
            content_hash = dataset.content_hash or _file_content_hash(dataset.storage_key or "")
            if content_hash and not dataset.content_hash:
                dataset.content_hash = content_hash
            fp = _dataset_fingerprint(dataset.content_hash, dataset.schema_hash)
            if fp and fp != dataset.dataset_fingerprint:
                # Avoid UniqueViolation if another row for this user already
                # owns this refined fingerprint (e.g. prior upload of same file).
                conflict = (
                    db.query(Dataset.id)
                    .filter(
                        Dataset.user_id == dataset.user_id,
                        Dataset.dataset_fingerprint == fp,
                        Dataset.id != dataset.id,
                    )
                    .first()
                )
                if conflict is None:
                    dataset.dataset_fingerprint = fp
                # else: keep existing fingerprint; analysis still completes

        # ── Profile ───────────────────────────────────────────
        if profile_data or preview:
            db.add(
                DatasetProfile(
                    analysis_id=analysis.id,
                    row_count=preview.get("total_rows"),
                    column_count=preview.get("total_cols"),
                    target_column=analysis.target_column,
                    target_confidence=_to_float(target_det.get("confidence")),
                    profile_json=profile_data or None,
                    columns_json={"columns": preview.get("columns", [])},
                )
            )

        # ── Cleaning ──────────────────────────────────────────
        _persist_cleaning(db, analysis.id, cleaning_report, preview)

        # ── Insights ──────────────────────────────────────────
        for i, finding in enumerate(insights_data.get("key_findings") or []):
            if not isinstance(finding, dict):
                continue
            title = (finding.get("title") or f"Finding {i + 1}")[:255]
            insight_type = (
                finding.get("type")
                or finding.get("insight_type")
                or "key_finding"
            )
            evidence = finding.get("evidence")
            evidence_json = None
            if evidence is not None:
                # Store evidence plus optional metrics for auditability
                if isinstance(evidence, dict):
                    evidence_json = dict(evidence)
                    if finding.get("metrics"):
                        evidence_json.setdefault("metrics", finding.get("metrics"))
                else:
                    evidence_json = {"value": evidence}

            importance = _to_float(finding.get("importance_score"))
            if importance is None:
                importance = max(0.0, 1.0 - (i * 0.05))

            # Prefer numeric confidence_score; fall back to label mapping in _to_float
            conf = _to_float(
                finding.get("confidence_score")
                if finding.get("confidence_score") is not None
                else finding.get("confidence")
            )

            db.add(
                Insight(
                    analysis_id=analysis.id,
                    type=str(insight_type)[:50],
                    title=title,
                    finding=finding.get("description") or finding.get("finding"),
                    interpretation=(
                        finding.get("interpretation")
                        or finding.get("business_interpretation")
                    ),
                    evidence_json=evidence_json,
                    confidence=conf,
                    importance_score=importance,
                )
            )

        # ── Visualizations
        # chartData items look like:
        #   {id, type, title, labels, datasets, options, xAxisLabel, ...}
        # Paths live in a parallel list: chart_paths / visualization_paths.
        viz_objects: list[Visualization] = []
        chart_paths = (
            payload.get("chart_paths")
            or payload.get("visualization_paths")
            or []
        )
        if not isinstance(chart_paths, list):
            chart_paths = []

        for idx, chart in enumerate(charts):
            if not isinstance(chart, dict):
                continue

            # data_json: prefer explicit nested "data"; otherwise store the
            # chart payload itself (labels/datasets/options) so the column
            # is never left empty when real chart data exists.
            raw_data = chart.get("data")
            if isinstance(raw_data, dict):
                data_json = raw_data
            else:
                data_json = {
                    k: v
                    for k, v in chart.items()
                    if k
                    not in (
                        "path",
                        "image_path",
                        "image_storage_key",
                        "url",
                    )
                } or None

            image_key = (
                chart.get("path")
                or chart.get("image_path")
                or chart.get("image_storage_key")
            )
            if not image_key and idx < len(chart_paths):
                p = chart_paths[idx]
                if isinstance(p, str):
                    image_key = p
                elif isinstance(p, dict):
                    image_key = p.get("path") or p.get("url") or p.get("image_path")

            viz = Visualization(
                analysis_id=analysis.id,
                type=(
                    chart.get("type")
                    or chart.get("chart_type")
                    or "unknown"
                )[:50],
                title=(chart.get("title") or f"Chart {idx}")[:255],
                config_json=chart.get("options") if isinstance(chart.get("options"), dict) else chart,
                data_json=data_json,
                image_storage_key=image_key,
                sort_order=idx,
            )
            db.add(viz)
            viz_objects.append(viz)

        # ── ML ─────────────────
        _persist_ml(db, analysis.id, ml, target_det)

        # ── Report ────────────────────────────────────────────
        report_path = payload.get("report_path") or ""
        report_meta = payload.get("report") or {}
        report_obj: Optional[Report] = None
        if report_path or report_meta:
            # Keep exactly one persisted report for each analysis. This makes
            # completion idempotent if the persistence step is retried.
            report_obj = (
                db.query(Report)
                .filter(Report.analysis_id == analysis.id)
                .first()
            )
            if report_obj is None:
                report_obj = Report(analysis_id=analysis.id)
                db.add(report_obj)

            # Persist ownership + label so Clean Datasets does not hide reports.
            ds = analysis.dataset
            if ds is not None:
                report_obj.user_id = ds.user_id
                report_obj.dataset_label = (
                    ds.original_filename or ds.name or "Dataset"
                )[:255]

            filename = None
            if report_path:
                filename = report_path.replace("\\", "/").split("/")[-1]
            report_obj.title = (report_meta.get("title") or "Analysis Report")[:255]
            report_obj.filename = filename
            report_obj.storage_key = report_path or report_obj.storage_key
            report_obj.status = "completed" if report_path else "pending"

        # Flush so Python-side uuid defaults are applied and PKs become available
        # before we create the junction rows (report_id / visualization_id).
        if report_obj is not None or viz_objects:
            db.flush()

        # ── Report ↔ Visualization links (junction table) ─────
        if report_obj is not None and viz_objects:
            for idx, viz in enumerate(viz_objects):
                db.add(
                    ReportVisualization(
                        report_id=report_obj.id,
                        visualization_id=viz.id,
                        sort_order=idx,
                    )
                )

        db.commit()
    except Exception:
        db.rollback()
        raise


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _extract_cleaning_actions(report: dict) -> list[dict]:
    """Collect cleaning actions from every known report shape.

    The CleaningEngine / cleaner tool stores actions under several keys
    depending on version and path:
      - top-level: actions | actions_applied | applied_actions
      - nested in cleaning_steps[*].applied_actions
      - full engine log: cleaning_log.log | cleaning_log (list)
      - engine_decisions that were actually applied
    """
    collected: list[dict] = []
    seen: set[tuple] = set()

    def _push(item: dict) -> None:
        if not isinstance(item, dict):
            return
        action_type = (
            item.get("action_type")
            or item.get("action")
            or item.get("type")
            or "unknown"
        )
        column = item.get("column_name") or item.get("column")
        key = (str(action_type), str(column) if column is not None else "", str(item.get("decision") or item.get("verdict") or item.get("decision_verdict") or ""))
        if key in seen:
            return
        seen.add(key)
        collected.append(item)

    for key in ("actions", "actions_applied", "applied_actions"):
        raw = report.get(key)
        if isinstance(raw, list):
            for item in raw:
                _push(item if isinstance(item, dict) else {"action": item})

    steps = report.get("cleaning_steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            nested = (
                step.get("applied_actions")
                or step.get("actions")
                or step.get("actions_applied")
            )
            if isinstance(nested, list):
                for item in nested:
                    _push(item if isinstance(item, dict) else {"action": item})

    # Engine log: may be under cleaning_log.log or cleaning_log as a list
    clog = report.get("cleaning_log")
    log_entries: list = []
    if isinstance(clog, dict):
        log_entries = clog.get("log") or clog.get("entries") or []
        # decisions that were approved/applied
        for d in clog.get("decisions") or []:
            if not isinstance(d, dict):
                continue
            verdict = str(d.get("verdict") or "").lower()
            if verdict in ("apply", "applied", "approve", "approved", "annotating"):
                _push({
                    "action_type": d.get("action") or d.get("action_type") or "unknown",
                    "column_name": (d.get("evidence") or {}).get("column") if isinstance(d.get("evidence"), dict) else d.get("column"),
                    "reason": "; ".join(d.get("reasons") or []) if isinstance(d.get("reasons"), list) else d.get("reason"),
                    "decision": d.get("verdict"),
                    "status": "applied" if verdict.startswith("appl") or verdict.startswith("appro") else verdict,
                    "evidence": d.get("evidence"),
                    "parameters": d.get("parameters"),
                })
    elif isinstance(clog, list):
        log_entries = clog

    for entry in log_entries if isinstance(log_entries, list) else []:
        if not isinstance(entry, dict):
            continue
        applied = entry.get("applied")
        rolled_back = entry.get("rolled_back")
        status = "rolled_back" if rolled_back else ("applied" if applied is not False else "skipped")
        reasons = entry.get("reasons")
        if isinstance(reasons, list):
            reason_text = "; ".join(str(r) for r in reasons)
        else:
            reason_text = entry.get("reason")
        _push({
            "action_type": entry.get("action") or entry.get("action_type") or "unknown",
            "column_name": entry.get("column") or entry.get("column_name"),
            "reason": reason_text,
            "decision": entry.get("decision_verdict") or entry.get("decision") or entry.get("verdict"),
            "status": status,
            "before": entry.get("before_state") or entry.get("before"),
            "after": entry.get("after_state") or entry.get("after"),
            "evidence": {
                "problem_type": entry.get("problem_type"),
                "detector": entry.get("detector"),
                "method": entry.get("method"),
                "confidence": entry.get("confidence"),
                "rows_affected": entry.get("rows_affected"),
                "validation": entry.get("validation"),
            },
            "rows_affected": entry.get("rows_affected"),
        })

    # Top-level engine_decisions (cleaner report)
    for d in report.get("engine_decisions") or []:
        if not isinstance(d, dict):
            continue
        verdict = str(d.get("verdict") or "").lower()
        if verdict not in ("apply", "applied", "approve", "approved", "annotating"):
            continue
        evidence = d.get("evidence") if isinstance(d.get("evidence"), dict) else {}
        reasons = d.get("reasons")
        reason_text = "; ".join(str(r) for r in reasons) if isinstance(reasons, list) else d.get("reason")
        _push({
            "action_type": d.get("action") or d.get("action_type") or "unknown",
            "column_name": evidence.get("column") or d.get("column"),
            "reason": reason_text,
            "decision": d.get("verdict"),
            "status": "applied",
            "evidence": evidence or d.get("evidence"),
            "parameters": d.get("parameters"),
        })

    return collected


def _persist_cleaning(
    db: Session,
    analysis_id: uuid.UUID,
    cleaning_report: Any,
    preview: dict,
) -> None:
    if not cleaning_report and not preview:
        return

    report = _as_dict(cleaning_report) or {}
    actions_raw = _extract_cleaning_actions(report)

    # Shape / row counts — prefer explicit report fields, then original/final_shape
    original_shape = report.get("original_shape") or []
    final_shape = report.get("final_shape") or []
    initial_rows = (
        report.get("initial_rows")
        or report.get("rows_before")
        or (original_shape[0] if len(original_shape) > 0 else None)
    )
    final_rows = (
        report.get("final_rows")
        or report.get("rows_after")
        or (final_shape[0] if len(final_shape) > 0 else None)
        or preview.get("total_rows")
    )
    initial_cols = (
        report.get("initial_columns")
        or report.get("cols_before")
        or (original_shape[1] if len(original_shape) > 1 else None)
    )
    final_cols = (
        report.get("final_columns")
        or report.get("cols_after")
        or (final_shape[1] if len(final_shape) > 1 else None)
        or preview.get("total_cols")
    )

    now = datetime.now(timezone.utc)
    # Prefer timestamps from the cleaning report when present.
    started_raw = (
        report.get("started_at")
        or report.get("start_time")
        or report.get("started")
    )
    started_at = now
    if isinstance(started_raw, datetime):
        started_at = started_raw if started_raw.tzinfo else started_raw.replace(tzinfo=timezone.utc)
    elif isinstance(started_raw, str) and started_raw.strip():
        try:
            parsed = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
            started_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            started_at = now

    run = CleaningRun(
        analysis_id=analysis_id,
        status="completed" if report or actions_raw else "pending",
        initial_rows=_to_int(initial_rows),
        final_rows=_to_int(final_rows),
        initial_columns=_to_int(initial_cols),
        final_columns=_to_int(final_cols),
        summary_json=report or None,
        started_at=started_at,
        completed_at=now if report or actions_raw else None,
    )
    db.add(run)
    db.flush()

    for action in actions_raw:
        if not isinstance(action, dict):
            continue
        action_type = (
            action.get("action_type")
            or action.get("action")
            or action.get("type")
            or "unknown"
        )
        status = action.get("status")
        if status is None:
            if action.get("rolled_back"):
                status = "rolled_back"
            elif action.get("applied") is False:
                status = "skipped"
            else:
                status = "applied"
        # Prefer explicit reason; fall back to joined reasons list if present
        reason = action.get("reason")
        if reason is None and isinstance(action.get("reasons"), list):
            reason = "; ".join(str(r) for r in action["reasons"])

        evidence = action.get("evidence") or action.get("evidence_json")
        if evidence is None and action.get("parameters") is not None:
            evidence = {"parameters": action.get("parameters")}
        if isinstance(evidence, dict) and action.get("rows_affected") is not None:
            evidence = {**evidence, "rows_affected": action.get("rows_affected")}

        db.add(
            CleaningAction(
                cleaning_run_id=run.id,
                action_type=str(action_type)[:100],
                column_name=action.get("column_name") or action.get("column"),
                reason=reason,
                decision=action.get("decision") or action.get("verdict") or action.get("decision_verdict"),
                status=str(status)[:50],
                before_json=_as_dict(action.get("before") or action.get("before_json") or action.get("before_state")),
                after_json=_as_dict(action.get("after") or action.get("after_json") or action.get("after_state")),
                evidence_json=_as_dict(evidence),
            )
        )


def _persist_ml(
    db: Session,
    analysis_id: uuid.UUID,
    ml: dict,
    target_det: dict,
) -> None:
   
    ml_results = ml.get("results")
    if ml_results is None:
        # fallback
        if any(k in ml for k in ("status", "selected_model", "metrics", "problem_type")):
            ml_results = ml
        else:
            return

    if not isinstance(ml_results, dict):
        return

    status = str(ml_results.get("status") or "success")[:50]
    if status in ("skipped", "pending") and not ml_results.get("selected_model"):
        db.add(
            MLResult(
                analysis_id=analysis_id,
                status=status,
                problem_type=ml_results.get("problem_type"),
                target_column=target_det.get("target_column") or target_det.get("column"),
                model_metadata={"reason": ml_results.get("reason")},
            )
        )
        return

    metrics = ml_results.get("metrics")
    if hasattr(metrics, "model_dump"):
        metrics = metrics.model_dump()
    metrics = _as_dict(metrics)

    fi = ml_results.get("feature_importance")
    if isinstance(fi, list):
        # List[FeatureImportanceItem] → dict بسيط
        feature_importance = {
            "items": [
                (x.model_dump() if hasattr(x, "model_dump") else x)
                for x in fi
            ]
        }
    else:
        feature_importance = _as_dict(fi)

    db.add(
        MLResult(
            analysis_id=analysis_id,
            status=status,
            problem_type=(ml_results.get("problem_type") or None),
            target_column=(
                ml_results.get("target_column")
                or target_det.get("target_column")
                or target_det.get("column")
            ),
            selected_model=(ml_results.get("selected_model") or None),
            fallback_model=(ml_results.get("fallback_model") or None),
            confidence=_to_float(ml_results.get("confidence")),
            metrics_json=metrics,
            feature_importance=feature_importance,
            model_metadata={
                "data_modality": ml_results.get("data_modality"),
                "used_fallback": ml_results.get("used_fallback"),
                "selection_reason": ml_results.get("selection_reason"),
                "warnings": ml_results.get("warnings"),
                "confusion_matrix": ml_results.get("confusion_matrix"),
                "reason": ml_results.get("reason"),
            },
            training_time_sec=_to_float(ml_results.get("training_time_sec")),
            rows_used=_to_int(ml_results.get("rows_used")),
        )
    )


def _as_dict(val: Any) -> Optional[dict]:
    if val is None:
        return None
    if hasattr(val, "model_dump"):
        val = val.model_dump()
    if isinstance(val, dict):
        return val
    return None


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        mapping = {"high": 0.9, "medium": 0.6, "low": 0.3}
        if val.lower() in mapping:
            return mapping[val.lower()]
        try:
            return float(val)
        except ValueError:
            return None
    return None


def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None