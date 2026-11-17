"""Local API for Contract Atlas. Run with uvicorn backend.app:app."""

import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models import Answer, Graph, QueryRequest

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from backend import baseline, cognee_adapter, data  # noqa: E402

logger = logging.getLogger(__name__)
app = FastAPI(title="Contract Atlas", version="0.1.0")
cognee_lock = asyncio.Lock()


@app.get("/api/health")
def health():
    return {"status": "ok", "cognee": cognee_adapter.get_status()}


@app.get("/api/dataset")
def dataset():
    return data.get_metadata()


@app.get("/api/awards")
def awards(
    search: str = Query(default="", max_length=500),
    recipient_id: str | None = Query(default=None, max_length=250),
    limit: int = Query(default=50, ge=1, le=500),
):
    return data.get_awards(search=search, recipient_id=recipient_id, limit=limit)


@app.get("/api/graph", response_model=Graph)
def graph(
    limit: int = Query(default=12, ge=1, le=30),
    recipient_id: str | None = Query(default=None, max_length=250),
):
    records = data.get_awards(recipient_id=recipient_id, limit=500)["awards"]
    return data.build_graph(records, limit=limit)


@app.post("/api/query", response_model=Answer)
async def query(request: QueryRequest):
    if request.mode == "baseline":
        return await asyncio.to_thread(baseline.query, request.question)
    if cognee_lock.locked():
        raise HTTPException(429, "A Cognee query is already running. Try again shortly.")
    async with cognee_lock:
        try:
            return await asyncio.wait_for(cognee_adapter.query(request.question), timeout=90)
        except cognee_adapter.CogneeUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        except TimeoutError:
            raise HTTPException(504, "Cognee timed out. Try a narrower question.") from None
        except Exception:
            # Provider exceptions can contain credential-bearing URLs and request payloads.
            logger.error("Cognee query failed; details withheld from HTTP response.")
            raise HTTPException(502, "Cognee could not complete this query. Check provider configuration.") from None


@app.get("/api/evaluation")
def evaluation():
    path = ROOT / "data" / "evaluation.json"
    if not path.exists():
        return {"status": "not_run", "message": "No evaluation has been run. Results appear after the evaluation CLI completes."}
    try:
        result = json.loads(path.read_text())
    except (ValueError, OSError):
        raise HTTPException(503, "Evaluation artifact is unavailable.") from None
    if result.get("snapshot_id") != data.get_metadata().get("snapshot_id"):
        return {"status": "stale", "message": "These results refer to a different snapshot. Re-run evaluation."}
    return result


# The same backend can serve a production frontend build. Vite proxies API in development.
DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    if not (DIST / "index.html").exists():
        raise HTTPException(503, "Frontend is not built. Run npm --prefix frontend run build, or use its dev server.")
    return FileResponse(DIST / "index.html")


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    path = DIST / "favicon.svg"
    if not path.exists():
        raise HTTPException(404, "Favicon not found.")
    return FileResponse(path, media_type="image/svg+xml")
