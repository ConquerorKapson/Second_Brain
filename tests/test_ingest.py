import asyncio
from src.agents.ingest_agent import IngestAgent

import asyncio
import json
import os
from fastapi.testclient import TestClient
from src.api.app import app
from src.agents.ingest_agent import IngestAgent

client = TestClient(app)

def test_chunking_in_agent():
    ing = IngestAgent(chunk_size_chars=10)
    text = "Hello world. This is a test. We will chunk this text into small pieces."
    ch = asyncio.run(ing.process_text(text))
    # expect at least 2 chunks
    assert isinstance(ch, list)
    assert len(ch) >= 2

def test_ingest_endpoint_text():
    resp = client.post("/ingest/", data={"content": "Quick brown fox. Jumps high."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ingested_chunks"] >= 1
    # check persisted file exists
    source_id = body.get("source_id")
    path = os.path.join("data/chunks", f"{source_id}.json")
    assert os.path.exists(path)
    # cleanup (optional)
    os.remove(path)
