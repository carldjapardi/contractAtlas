# Research team implementation contract

Read PIVOT.md. Project `/Users/carl/CS/hackathons/spending-atlas`. Existing source snapshot/index stay unchanged. Never print credentials.

## Source document

`{id: str, title: str, kind: 'award'|'agency_guidance'|'company_capability'|'internal_brief', url: str|null, retrieved_at: str, text: str, notes: str[]}`.

`data/team_sources.json` = `{version:1, sources: Source[], notes: str[]}`. Include around 20–35 relevant real awards (stable IDs), one official CISA/DHS requirements/guidance document, and two actual vendor capability pages. Prefer HTML; if using a PDF follow the PDF skill. Source text is actual retrieved content, not invented summaries. Label vendor claims self-reported, and never present guidance or historical awards as an open solicitation. Source IDs are stable and included as markers in Cognee documents. Data builder supplies collection script and tests; no secrets.

## Runtime functions owned by Cognee builder

`backend/team_memory.py`:

- `get_status() -> {available:bool, ready:bool, reason:str, source_count:int, dataset_name:str|null}`. Fast/lazy, no provider calls.
- `async seed_memory(emit=None) -> dict` ingest multi-source docs into an isolated shared dataset using real Cognee. Disable auto-improve so checkpoint is controlled. Persist safe manifest separate from old index. Add native agent tracing/session configuration as required.
- `async research(question:str, profile:str, run_id:str, emit) -> dict` actual role agents via native `agent_memory` decorator if feasible, same dataset/different session IDs, provider calls, real retrieved memory. `emit(event:dict)` is an async callback owned by lead. Emit progress with `{kind, title, detail, agent_role?, metrics?}`. Return run fields below.
- `async improve_research(run:dict, feedback:str, emit) -> dict` records accepted feedback in a real reviewer session turn, runs explicit `cognee.improve`, captures actual stages/new lessons, then executes a fresh agent on original question/profile (no feedback injected in its prompt). Return updated fields below, preserving before output. Verify from actual durable memory, not answer text alone.
- `TeamMemoryUnavailable` typed sanitized exception.

Use actual SDK session tracing and shared dataset. Keep role prompts source-grounded. Findings are interpretations, not official facts. Native agent memory context may be summarized but must preserve actual excerpts/IDs for verification. If session distillation writes zero documents, show it honestly. Never fabricate source retrieval, stage counts, before failures, or improvement. File lock prevents simultaneous mutations; may reuse old adapter's store lock if same embedded stores. Runtime libraries: existing Cognee1.6.8, dotenv, OpenAI/LiteLLM as installed. Use project-local storage. No Cloud switch until lead confirms credentials/compatibility.

`scripts/seed_team_memory.py` invokes seed_memory and emits a sanitized status/count summary. No provider key output.

## Research result fields

- `agents: [{role: 'opportunity'|'partner'|'reviewer', name:str, session_id:str, status:'complete'|'error', report:str, source_ids:str[], memory_excerpt:str, trace_recorded:bool}]`
- `before_report: str` partner/capture research output captured before learning
- `review: {findings:str[], suggested_learning:str}`
- `memory_graph: Graph|null` same nodes/edges/truncated as existing contract. Extracted semantic concepts use type `topic`, edges origin `inferred`; node/edge award_ids may carry source document IDs for this view. Markers/provenance connect them to Source IDs. Show actual bounded Cognee graph, never a hand-authored fake graph. If unavailable, return null with event explaining why.
- `memory_stats: {nodes?:int, edges?:int, source_count:int, dataset_name:str}`
- After improvement: `after_report:str`, `fresh_session_id:str`, `improvement:{status:str, stages:[{name:str,status:str,counts:dict,reason?:str}], lesson_count:int, lessons:[{id:str,text:str}], learning_verified:bool, durable_recall_excerpt:str, notes:str[]}`

Do not return private provider settings, raw exception messages, credentials, or full debug trace payloads.

## HTTP/job manager owned by lead

- `GET /api/team/status` → module get_status
- `GET /api/team/sources` → public Source metadata and text (bounded local docs)
- `GET /api/team/runs` → `{runs: Run[]}` latest10
- `POST /api/team/runs` `{question:str,profile:str}` → Run queued, HTTP202. One active job at a time.
- `GET /api/team/runs/{id}` → Run
- `POST /api/team/runs/{id}/improve` `{feedback:str}` → Run improving, HTTP202. Requires status awaiting_review. No automatic execution on page mount.

Run = `{id,created_at,updated_at,status:'queued'|'running'|'awaiting_review'|'improving'|'complete'|'error',stage,question,profile,events:[{id,at,kind,title,detail,agent_role?,metrics?}], sources:Source[],agents:[],before_report:null|str,after_report:null|str,review:null|object,improvement:null|object,memory_graph:null|Graph,memory_stats:null|object,error:null|str}`.

Lead persists run artifacts locally (ignored) and catches sanitized exceptions. Background tasks are awaited by task registry; server restart marks interrupted runs explicitly. Do not erase the initial comparison results.

## Frontend owned by frontend builder

Add primary `Research team` view (default), preserve Explore/Awards/Benchmark. New standalone TeamResearch component + types/styles, integrate App minimal. Company BD persona, concise research brief and company profile inputs with clearly labeled demo defaults. No fabricated open opportunities.

Show three research roles, shared source collection with source kind labels/links, actual event timeline, agent reports + retrieved memory excerpts, a review textarea initialized from actual reviewer suggestion, and `Improve team memory` action. Poll active run every~2s with cancellation; show last runs. Before/after output, real improve stage table, lesson count and fresh-session memory proof. Zero lessons are a valid honest state. Display bounded actual memory_graph using existing graph component if practical, selected node source IDs reveal actual Source records. No fake graphs or scripted results.

Source endpoint can include text; collapse long source text in UI. Clearly label public historical awards, official guidance, self-reported company claims, internal/demo brief, and learned team guidance. Disable action during active jobs. Empty/unavailable states actionable. Do not leak provider details into product flow.

All builders keep to owned files and send progress. Lead handles commits frequently and review checkpoints.
