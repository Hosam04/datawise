"""Persistent repository for canonical analysis artifacts.

The analysis workflow runs in-memory, but the dataset/session itself is stored
under storage/sessions/<session_id>.  Keeping a small JSON manifest alongside
that directory prevents the Chat endpoint from losing datasets whenever the
FastAPI process is restarted.
"""
from __future__ import annotations

import json
import os
from threading import RLock
from typing import Any

from backend.core.config import Config


class AnalysisRepository:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    @staticmethod
    def _session_dir(dataset_id: str) -> str:
        # Anchored to Config.STORAGE_PATH (absolute, repo-root based) rather
        # than a bare relative "storage" path, so lookups are consistent no
        # matter what directory the server process was started from.
        return os.path.join(Config.STORAGE_PATH, "sessions", dataset_id)

    @classmethod
    def _manifest_path(cls, dataset_id: str) -> str:
        return os.path.join(cls._session_dir(dataset_id), "analysis.json")

    @classmethod
    def _load_persisted(cls, dataset_id: str) -> dict[str, Any] | None:
        """Load a completed session from disk when memory was lost.

        Older sessions may not have an analysis.json manifest.  If their
        df.pkl still exists, reconstruct a minimal completed record so chat
        remains usable instead of returning a misleading 404.
        """
        manifest_path = cls._manifest_path(dataset_id)
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    record = json.load(f)
                if isinstance(record, dict):
                    return record
            except (OSError, json.JSONDecodeError):
                pass

        session_dir = cls._session_dir(dataset_id)
        df_path = os.path.join(session_dir, "df.pkl")
        if os.path.isfile(df_path):
            return {
                "status": "completed",
                "df_path": df_path,
                "preview": {},
                "statistics": {},
                "correlations": {},
                "outliers": {},
                "insights": {},
                "ml_analysis": None,
                "dataset_profile": {},
                "target_detection": {},
                "charts": [],
                "chartData": [],
                "chart_paths": [],
                "report": {},
                "report_path": "",
            }

        return None

    def create(self, dataset_id: str) -> None:
        record = {"status": "processing"}
        with self._lock:
            self._records[dataset_id] = record

            # Persist immediately (not just on complete/fail) so that if the
            # process restarts while analysis is still running, the session
            # is recoverable as "processing" instead of vanishing into a
            # misleading 404 "Dataset not found".
            session_dir = self._session_dir(dataset_id)
            os.makedirs(session_dir, exist_ok=True)
            manifest_path = self._manifest_path(dataset_id)
            try:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=2)
            except OSError:
                pass

    def get(self, dataset_id: str) -> dict[str, Any] | None:
        dataset_id = dataset_id.strip()
        with self._lock:
            record = self._records.get(dataset_id)
            if record is not None:
                return dict(record)

            record = self._load_persisted(dataset_id)
            if record is not None:
                # Rehydrate memory so subsequent chat requests are fast.
                self._records[dataset_id] = record
                return dict(record)

            return None

    def complete(self, dataset_id: str, artifacts: dict[str, Any]) -> None:
        record = {"status": "completed", **artifacts}
        with self._lock:
            self._records[dataset_id] = record

            session_dir = self._session_dir(dataset_id)
            os.makedirs(session_dir, exist_ok=True)
            manifest_path = self._manifest_path(dataset_id)
            temp_path = f"{manifest_path}.tmp"
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=2, default=str)
                os.replace(temp_path, manifest_path)
            except OSError:
                # The in-memory record is still valid for the current process.
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass

    def fail(self, dataset_id: str, error: str) -> None:
        record = {"status": "failed", "error": error}
        with self._lock:
            self._records[dataset_id] = record

            session_dir = self._session_dir(dataset_id)
            os.makedirs(session_dir, exist_ok=True)
            manifest_path = self._manifest_path(dataset_id)
            try:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=2)
            except OSError:
                pass

    def delete(self, dataset_id: str) -> None:
        """Remove in-memory record for a dataset (disk cleanup is caller's job)."""
        with self._lock:
            self._records.pop(dataset_id, None)

            
analysis_repository = AnalysisRepository()