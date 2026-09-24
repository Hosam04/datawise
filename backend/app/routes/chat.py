from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.auth.dependencies import get_current_user_optional
from backend.database.models import User
from backend.services.chat import chat_with_dataset

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/datasets/{dataset_id}/chat")
async def chat_with_dataset_endpoint(
    dataset_id: str,
    data: ChatRequest,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    return await chat_with_dataset(dataset_id, data.message, current_user, db)