"""Local API for Contract Atlas. Run with uvicorn backend.app:app."""

import asyncio
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models import Answer, Graph, ImproveRequest, QueryRequest, ResearchRequest
from backend.team_jobs import TeamJobConflict, load_sources, manager as team_manager

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from backend import baseline, cognee_adapter, data  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    team_manager.recover_interrupted()
    yield
    await team_manager.shutdown()


app = FastAPI(title="Contract Atlas", version="0.2.0", lifespan=lifespan)
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


@app.get("/api/comparison")
def memory_comparison():
    path = ROOT / "data" / "expansion" / "comparison_results.json"
    if not path.exists():
        return {"status": "not_run"}
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        raise HTTPException(503, "Comparison artifact is unavailable.") from None


@app.get("/api/team/status")
def team_status():
    try:
        status = team_manager.memory.get_status()
    except ImportError:
        status = {"available": False, "ready": False, "reason": "The research memory service is being prepared.", "source_count": len(load_sources()), "dataset_name": None}
    return {**status, "busy": team_manager.busy or status.get("busy", False)}


@app.get("/api/team/sources")
def team_sources():
    return {"sources": load_sources()}


@app.get("/api/team/runs")
def team_runs():
    return {"runs": team_manager.list()}


@app.post("/api/team/runs", status_code=202)
async def start_team_run(request: ResearchRequest):
    status = team_status()
    if status.get("busy"):
        raise HTTPException(409, "A team memory operation is already running.")
    if not status.get("available") or not status.get("source_count"):
        raise HTTPException(503, status.get("reason") or "The shared source collection is not ready.")
    try:
        return team_manager.start(request.question, request.profile)
    except TeamJobConflict as exc:
        raise HTTPException(409, str(exc)) from None


@app.get("/api/team/runs/{run_id}")
def team_run(run_id: str):
    try:
        return team_manager.get(run_id)
    except KeyError:
        raise HTTPException(404, "Research run not found.") from None


@app.post("/api/team/runs/{run_id}/improve", status_code=202)
async def improve_team_run(run_id: str, request: ImproveRequest):
    try:
        return team_manager.improve(run_id, request.feedback)
    except KeyError:
        raise HTTPException(404, "Research run not found.") from None
    except TeamJobConflict as exc:
        raise HTTPException(409, str(exc)) from None


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
