import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from backend.core.storage import analysis_repository

router = APIRouter(tags=["Charts"])


@router.get("/datasets/{dataset_id}/charts/{chart_id}")
async def get_chart(dataset_id: str, chart_id: int) -> FileResponse:
    dataset = analysis_repository.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if dataset["status"] != "completed":
        raise HTTPException(status_code=409, detail="Dataset analysis has not completed.")
    paths = dataset.get("chart_paths", [])
    if chart_id < 0 or chart_id >= len(paths):
        raise HTTPException(status_code=404, detail="Chart not found.")
    if not os.path.isfile(paths[chart_id]):
        raise HTTPException(status_code=404, detail="Chart file is unavailable.")
    return FileResponse(paths[chart_id], media_type="image/png")
