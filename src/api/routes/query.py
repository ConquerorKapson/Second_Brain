from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.agents.root_agent import RootAgent

router = APIRouter()
root_agent = RootAgent()

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class QueryResponse(BaseModel):
    answer: str
    sources: list[dict] = []

@router.post("/", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    if not req.query:
        raise HTTPException(status_code=400, detail="query is required")
    res = await root_agent.handle_query(req.query, top_k=req.top_k)
    return {"answer": res.get("answer", ""), "sources": res.get("sources", [])}
