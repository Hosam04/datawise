from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.services.artifacts import get_artifacts, download_report, download_processed_dataset

router = APIRouter(prefix="/datasets", tags=["Artifacts"])


@router.get("/{dataset_id}/artifacts")
async def get_artifacts_endpoint(dataset_id: str):
    """The only API contract consumed by the artifact panel."""
    return get_artifacts(dataset_id)


@router.get("/{dataset_id}/report/download")
async def download_report_endpoint(dataset_id: str):
    return download_report(dataset_id)


@router.get("/{dataset_id}/processed-dataset/download")
async def download_processed_dataset_endpoint(dataset_id: str):
    return download_processed_dataset(dataset_id)