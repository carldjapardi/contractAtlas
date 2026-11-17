# Shared implementation contract

Use snake_case JSON throughout. Absolute project path: `/Users/carl/CS/hackathons/spending-atlas`.

## Records

Award: `id: str`, `award_id: str`, `description: str`, `agency: str`, `sub_agency: str|null`, `recipient_id: str`, `recipient_name: str`, `recipient_uei: str|null`, `parent_uei: str|null`, `parent_name: str|null`, `obligation: float`, `start_date: str|null`, `end_date: str|null`, `source_url: str`.

`obligation` is the USAspending award summary amount, not FY-only spending or cash paid. Never label it FY2025 obligations without transaction-based calculation.

Dataset metadata: `name`, `status` (`live_snapshot` or `empty`), `retrieved_at`, `fiscal_year`, `agency`, `keywords: str[]`, `award_count`, `recipient_count`, `total_obligation`, `snapshot_id`, `truncated: bool`, `notes: str[]`.

Node: `id`, `type` (`agency`, `award`, `recipient`, `parent`, `topic`), `label`, `sublabel`, `award_ids: str[]`.

Edge: `id`, `source`, `target`, `relationship`, `origin` (`reported` or `inferred`), `award_ids: str[]`.

Graph: `{nodes: Node[], edges: Edge[], truncated: bool}`.

Evidence: `id` (award's id), `title` (recipient + award ID), `description`, `source_url`, `obligation`, `agency`, `recipient_name`.

Answer: `{answer: str, evidence: Evidence[], graph: Graph, mode: 'baseline'|'cognee', elapsed_ms: number, coverage_notes: str[], matched_count: number}`.

## HTTP routes owned by lead

- `GET /api/health` → `{status:'ok', cognee: {available:bool, ready:bool, reason:str}}`
- `GET /api/dataset` → metadata
- `GET /api/graph?limit=12&recipient_id=...` → graph; recipient_id optional
- `GET /api/awards?search=...&recipient_id=...&limit=50` → `{awards: Award[], total: number}`
- `POST /api/query` body `{question: str, mode:'baseline'|'cognee'}` → Answer; 503 for unavailable Cognee
- `GET /api/evaluation` → benchmark artifact or explicit not-run state

## Python interfaces

Builder A owns `backend/data.py`, `backend/baseline.py`, `scripts/ingest.py`, `data/snapshot.json`, and data/baseline tests. stdlib or base dependencies only. `data.py`: `load_snapshot() -> dict` where snapshot `{metadata, awards}`; `get_metadata() -> dict`; `get_awards(search='', recipient_id=None, limit=50) -> dict`; `build_graph(awards: list[dict], limit=12) -> dict`. `baseline.py`: `query(question: str) -> Answer dict`. Keep fixture data in tests only. Stable deterministic IDs.

Builder B owns `backend/cognee_adapter.py`, `scripts/index_cognee.py`, provider tests. `get_status() -> {available,ready,reason}`; `async query(question: str) -> Answer dict`. Raise a typed `CogneeUnavailable` exception for unavailable provider/index. Use A's `load_snapshot`/`build_graph`; lazy imports; no dependency on FastAPI. Index metadata must bind to snapshot_id. Provider operations are local CLI actions, not public HTTP mutations. Do not expose raw exception messages/secrets to browser. You may add an optional dependency group to pyproject only after messaging lead. Consult current official docs and installed APIs; never claim validated provider operation without running it.

Builder C owns `frontend/**`. React/TypeScript/Vite with @xyflow/react and lucide-react. Package scripts `dev`, `build`, `typecheck`. Proxy `/api` to `http://127.0.0.1:8000`. Use this HTTP contract; no fake data in the user interface. Empty states if no snapshot. Distinct reported/inferred links. Clear unavailable Cognee state. Polished light investigative workbench, navy/teal with subtle grid, responsive. Sidebar navigation Explore/Awards/Benchmark may be implemented as tabs. Functional filtering/search, graph node selection and source evidence. API on same origin. Lead owns root scripts and backend/app.py.

Base Python dependencies owned by lead: FastAPI, uvicorn, python-dotenv, httpx, pytest. Project uses uv; Python >=3.11,<3.14. All agents share checkout: don't commit, reset, or overwrite others' files. Report integration milestones promptly. Do not print secret values or read `.env` into tool output.
