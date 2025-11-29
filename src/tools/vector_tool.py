"""
VectorTool (REST implementation) — robust and stable.

This module talks to Weaviate via HTTP REST calls (requests).
It avoids client-library compatibility issues by using the stable
HTTP API: /objects (create), /graphql (search), /schema (optional).

Requirements:
- requests (already a common dependency; add to requirements if missing)

Behavior:
- upsert(id, vector, metadata, text): attempts to POST /objects with the provided id.
  If POST fails with 409 (already exists), it will attempt to PUT /objects/{id}.
- search(vector, top_k): uses GraphQL with nearVector to retrieve nearest neighbors.
- Logs via print() so outputs show in docker logs.
"""

import os
import uuid
import json
import requests
from typing import List, Dict, Any

WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "http://weaviate:8080").rstrip("/")
OBJECTS_ENDPOINT = f"{WEAVIATE_URL}/v1/objects"
GRAPHQL_ENDPOINT = f"{WEAVIATE_URL}/v1/graphql"
SCHEMA_ENDPOINT = f"{WEAVIATE_URL}/v1/schema"

HEADERS = {"Content-Type": "application/json"}
CLASS_NAME = "Chunk"

def _pretty(v):
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)

class VectorTool:
    def __init__(self):
        self.base = WEAVIATE_URL
        print(f"[VectorTool-REST] initialized with WEAVIATE_URL={self.base}")

    def _ensure_schema(self):
        """
        Create a simple schema for the Chunk class if it does not exist.
        If schema already exists or creation fails, we continue (auto_schema may be enabled).
        """
        try:
            resp = requests.get(f"{SCHEMA_ENDPOINT}")
            if resp.status_code == 200:
                schema = resp.json()
                # check if class exists
                classes = [c.get("class") for c in schema.get("classes", [])]
                if CLASS_NAME in classes:
                    print(f"[VectorTool-REST] schema '{CLASS_NAME}' already exists.")
                    return
            # create class
            payload = {
                "class": CLASS_NAME,
                "vectorizer": "none",
                "properties": [
                    {"name": "text", "dataType": ["text"]},
                    {"name": "source_id", "dataType": ["text"]},
                    {"name": "chunk_index", "dataType": ["int"]},
                    {"name": "page", "dataType": ["int"]},
                ],
            }
            r = requests.post(SCHEMA_ENDPOINT, headers=HEADERS, json=payload)
            if r.status_code in (200, 201):
                print(f"[VectorTool-REST] created schema '{CLASS_NAME}'")
            else:
                print(f"[VectorTool-REST] schema create returned {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[VectorTool-REST] schema check/create error: {e}. Proceeding (auto_schema may handle it).")

    async def upsert(self, id: str, vector: List[float], metadata: Dict[str, Any], text: str):
        """
        Upsert object into Weaviate using REST.
        We avoid sending 'id' on POST if it's not a valid UUID. Instead we store the original
        chunk id in the object properties under 'chunk_id'. This prevents 422 errors.
        """
        # prepare properties, include original chunk id as chunk_id
        props = {
            "text": text,
            "source_id": metadata.get("source_id"),
            "chunk_index": metadata.get("chunk_index"),
            "page": metadata.get("page"),
            "chunk_id": id,  # original chunk id stored as property
        }

        # Ensure schema: include chunk_id property type text
        try:
            self._ensure_schema()
        except Exception:
            pass

        # Build payload WITHOUT 'id' (let Weaviate generate UUID) if id is not a valid UUID.
        def is_valid_uuid(u: str) -> bool:
            try:
                uuid.UUID(str(u))
                return True
            except Exception:
                return False

        payload = {
            "class": CLASS_NAME,
            "properties": props,
            "vector": vector,
        }

        # If caller passed a valid UUID, include it (so callers who already have UUIDs keep them)
        # Otherwise omit 'id' so Weaviate assigns one.
        if is_valid_uuid(id):
            payload["id"] = id

        # POST
        try:
            resp = requests.post(OBJECTS_ENDPOINT, headers=HEADERS, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                print(f"[VectorTool-REST] POST /objects created id_prop={payload.get('id', '<generated>')}")
                return
            elif resp.status_code == 409:
                # If we sent an id and conflict occurred, try PUT. If no id was sent, conflict won't happen.
                if payload.get("id"):
                    put_url = f"{OBJECTS_ENDPOINT}/{payload['id']}"
                    r2 = requests.put(put_url, headers=HEADERS, json=payload, timeout=30)
                    if r2.status_code in (200, 204):
                        print(f"[VectorTool-REST] PUT /objects/{payload['id']} replaced existing object.")
                        return
                    else:
                        print(f"[VectorTool-REST] PUT returned {r2.status_code}: {r2.text}")
                        raise RuntimeError(f"PUT failed: {r2.status_code}")
                else:
                    # Unexpected: conflict without id; just log and raise
                    print(f"[VectorTool-REST] POST returned 409 but no id in payload.")
                    raise RuntimeError("POST conflict without id")
            else:
                print(f"[VectorTool-REST] POST /objects returned {resp.status_code}: {resp.text}")
                raise RuntimeError(f"POST failed: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[VectorTool-REST] Exception during upsert: {e}")
            raise

    async def search(self, vector: List[float], top_k: int = 5):
        """
        Run a GraphQL nearVector query to get nearest chunks.
        Query:
        {
          Get {
            Chunk(nearVector: {vector: [...], certainty: 0.7}, limit: 5) {
              text source_id chunk_index page
            }
          }
        }
        We'll build nearVector with distance-based approach: use certainty fallback.
        """
        # GraphQL doesn't like huge float arrays in string formatting; build JSON payload
        try:
            # build nearVector argument
            near_vector = {"vector": vector}
            # craft GraphQL query with variable usage is not supported directly in all weaviate setups,
            # so we'll post a JSON payload containing the query with an embedded vector; this is acceptable.
            gql_query = {
                "query": f"""
                {{
                  Get {{
                    {CLASS_NAME}(nearVector: {{vector: {json.dumps(vector)}, distance: 0.8}}, limit: {top_k}) {{
                      text
                      source_id
                      chunk_index
                      page
                      chunk_id
                    }}
                  }}
                }}
                """
            }
            resp = requests.post(GRAPHQL_ENDPOINT, headers=HEADERS, json=gql_query, timeout=30)
            if resp.status_code != 200:
                print(f"[VectorTool-REST] GraphQL returned {resp.status_code}: {resp.text}")
                return []
            body = resp.json()
            objs = body.get("data", {}).get("Get", {}).get(CLASS_NAME, [])
            hits = []
            for obj in objs:
                hits.append({
                    "text": obj.get("text"),
                    "source_id": obj.get("source_id"),
                    "chunk_index": obj.get("chunk_index"),
                    "page": obj.get("page"),
                })
            return hits
        except Exception as e:
            print(f"[VectorTool-REST] Exception during search: {e}")
            return []
