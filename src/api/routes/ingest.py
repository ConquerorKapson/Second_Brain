from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.agents.root_agent import RootAgent

router = APIRouter()
root_agent = RootAgent()

class IngestResponse(BaseModel):
    status: str
    ingested_chunks: int
    source_id: Optional[str] = None

@router.post("/", response_model=IngestResponse)
async def ingest_text(content: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    """
    Provide either:
    - form field `content` (text), OR
    - file upload field `file` (UploadFile)
    """
    if not content and not file:
        raise HTTPException(status_code=400, detail="Please provide `content` or upload a `file`")

    if file:
        fb = await file.read()
        res = await root_agent.handle_ingest(file_bytes=fb, filename=file.filename)
    else:
        res = await root_agent.handle_ingest(content=content)

    return res

