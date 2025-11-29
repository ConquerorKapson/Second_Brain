from fastapi import FastAPI
from src.api.routes import ingest, query

app = FastAPI(title="ADK Personal Memory Architect - API")

app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(query.router, prefix="/query", tags=["query"])

@app.get("/")
async def root():
    return {"status": "ok", "service": "ADK Personal Memory Architect"}
