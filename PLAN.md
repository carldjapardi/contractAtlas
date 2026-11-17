# Spending Atlas — four-hour prototype plan

## Current plan and progress — November 16, 2026

This section is the active plan. The original four-hour plan below is retained as the starting scope. See PIVOT.md for the sponsor-focused acceptance criteria and TEAM_CONTRACT.md for runtime interfaces.

**Confirmed user:** a cybersecurity contractor's business-development/capture team.

**Current product:** Contract Atlas, a research team that connects historical awards, agency guidance, vendor capability claims, and internal briefs through shared Cognee memory. The demonstration centers on review → native `improve()` → a fresh agent retrieving durable guidance.

### Pivot log

1. **General spending graph → company research workflow.** We initially explored agency/vendor relationships without selecting a primary user. The user confirmed company business development: identify relevant work, incumbents, and potential teaming partners. Government oversight is no longer the primary demo persona.
2. **Award-only chatbot/graph → multi-source shared agent memory.** The sponsor specifically emphasized self-improvement and shared agent memory. A graph over existing award IDs alone would not demonstrate these. We preserved the explorer and benchmark as supporting views and added three research roles with persistent sessions and source-linked memory.
3. **Default hybrid retrieval → explicit, inspectable memory behavior.** The initial adapter retrieved Cognee chunks while hiding much of its internal graph contribution. Its initial exploratory benchmark favored the lexical baseline (83% versus 50% positive-anchor recall). We preserved those results and shifted the core demonstration to native agent traces, cross-agent recall, actual improvement stages and fresh-session learning proof. We did not claim the original results established Cognee superiority.
4. **Local SDK → end-to-end Cloud REST workflow for the research team.** The local SDK pipeline was working. Inspection showed that a simple `serve()` switch could leave native session helpers local while retrieval went remote. After Cloud credentials and credits were authorized, we implemented the verified Cloud endpoints directly so graph, agent registrations, Q&A, traces and improvement remain in one tenant. The award-only SDK explorer remains local and independent.
5. **Typed capability-graph expansion deferred.** Custom DataPoint/ontology exploration was considered before the sponsor clarification. It is not the current priority. Source-aware extraction, shared research sessions and evidence of durable learning provide a tighter hackathon story.

### Completed checkpoints

- [x] Real USAspending snapshot: 265 awards, 150 recipient identities; all detail requests succeeded.
- [x] Explicit graph, identity-safe parent links, deterministic baseline, financial/coverage labels.
- [x] Local Cognee full index and real retrieval smoke tests.
- [x] Supporting Explore, Awards and Benchmark views; production frontend build passed.
- [x] Data integrity protections, API/provider tests, dependency locks and CI configuration.
- [x] Multi-source corpus: 25 historical awards + CISA guidance + two vendor capability excerpts.
- [x] Cloud authentication and required APIs verified; the 28-source Cloud graph built successfully.
- [x] Primary Research team UI and persistent background-job API.
- [x] First actual Cloud run completed all three roles, recorded traces, and verified peer-agent trace retrieval.
- [x] Reviewer produced real source/evidence findings; original output preserved for inspection.

### Active implementation and validation

- [ ] Finish source-aware report rendering and retrieval provenance checks.
- [ ] Run a complete, readable research checkpoint through the UI after integration refinements.
- [ ] Accept a real reviewer lesson and execute Cloud `improve()` over actual agent sessions.
- [ ] Capture improvement stage statuses/counts and identify newly distilled documents.
- [ ] Verify a fresh session retrieves a new durable lesson without feedback copied into its prompt.
- [ ] Clearly report zero lessons or failed retrieval; never manufacture a successful learning result.
- [ ] Validate the actual memory graph layout, source navigation, responsive states and job recovery.
- [ ] Add focused Cloud/provenance regression tests and run final backend/frontend checks.
- [ ] Update README verification status, record the actual demo results, and commit remaining working slices.

### Reviewable commits so far

| Commit | Checkpoint |
| --- | --- |
| `07d5495` | Real data and source-grounded retrieval API |
| `317b926` | Interactive investigation workspace |
| `58d7e58` | Source integrity and canonical graph identities |
| `a744a3a` | Readability and complete award browsing |
| `01ea44b` | Initial comparison and reproducible workflow |
| `fd699ee` | Multi-source collection and sponsor pivot contracts |
| `9cc8ed3` | Company use case, scope and track rationale |
| `e74523b` | Cloud research agents, session traces and review UI |

### Success criteria for the revised demo

The user can inspect a real source-backed research run, accept a reusable review lesson, execute native improvement, and inspect a fresh agent's actual retrieved memory and report. Source classes remain explicit. A completed API call alone is insufficient evidence of learning. A new lesson document plus its retrieval in a fresh session establishes durable memory reuse; it does not by itself establish improved research quality or model training.

## Original starting plan

## Outcome

Build a local investigation workspace for discovering federal contractors and inspecting the award records behind each answer. Demonstrate a structured retrieval baseline and a Cognee-powered retrieval path over the same frozen data snapshot.

Timebox: four elapsed hours with one lead/integrator and three parallel builders. This is a proof of concept with a small exploratory evaluation, not a validated production case study.

## Scope

- Start with DHS contracts in FY2025, focusing on cybersecurity-related descriptions. Expand the search terms if the initial slice is too sparse; do not silently label this a comprehensive cybersecurity dataset.
- Target 200–500 award summaries. Record actual coverage and retrieval filters.
- Fetch award transactions and recipient parent information only where practical within the timebox. Missing fields remain unknown.
- Use one frozen snapshot for both retrieval paths, with source URLs and retrieval timestamps.
- Build one screen: question input, answer, interactive graph, and evidence panel.
- Include three example prompts and a retrieval-mode switch.
- Run locally. Hosting, authentication, live refresh, exhaustive subsidiary discovery, and fraud detection are outside this prototype.

## Demo questions

1. Which recipients have awards related to identity and access management in this dataset?
2. What awards connect a selected recipient to DHS, and what do their descriptions say?
3. Which recipients share a reported ultimate parent, where that information is available?
4. Which awards describe similar work using different terminology?
5. What cannot be established from these records?

Do not depend on finding shared parents for the demo. Single-agency scope cannot demonstrate cross-agency dependence; that is a later expansion.

## Architecture

Suggested implementation: React + TypeScript frontend, a graph library such as React Flow, and a Python/FastAPI backend for Cognee integration. Use SQLite for normalized records and deterministic queries. Verify available tooling and Cognee requirements at kickoff before committing to versions.

Data flow:

USAspending API/download → frozen raw snapshot → normalization → SQLite + explicit graph

Normalized source records → Cognee ingestion → retrieval with source record IDs

Both paths → shared answer/evidence/graph response → frontend

All financial totals come from deterministic queries. Never add repeated award totals across transaction rows or combine prime and subaward amounts. Display obligations as commitments, not cash paid. If transactions are unavailable, omit time-series claims and within-period obligation calculations.

## Shared contracts — freeze before parallel work

- `Award`: internal ID, source award ID, agency ID, recipient ID, description, available amount fields with explicit meanings, dates, source URL.
- `Recipient`: stable source ID, name, UEI when present, reported ultimate-parent UEI/name when present.
- `Evidence`: record ID, source URL, field name, supporting text/value, retrieval timestamp.
- `Node`: ID, type (`agency`, `award`, `recipient`, `topic`), label, source record IDs.
- `Edge`: ID, source, target, relationship, origin (`reported`, `inferred`), evidence IDs.
- `Answer`: answer text, evidence list, nodes, edges, retrieval mode, elapsed time, coverage notes.
- API: `GET /api/health`, `GET /api/dataset`, `GET /api/graph`, `POST /api/query` with `{question, mode}`.
- Retrieval modes: `baseline` and `cognee`. Unsupported questions receive an explicit insufficient-evidence response.

Keep schemas in a shared contract file and commit a small fixture response. LLM-extracted relationships must remain distinguishable from source-reported relationships. Link cited evidence back to the frozen source records; reject invented source IDs.

## Parallel assignments

### Lead / integrator

- Create the project skeleton, shared schemas, fixture responses, and start commands.
- Verify required provider credentials without printing secret values.
- Prepare evaluation questions and expected supporting record IDs.
- Own API wiring, integration, smoke checks, and demo narrative.
- Keep a single list of integration issues and enforce scope cuts.

### Builder A — data and baseline

- Own ingestion scripts, normalized data, explicit graph construction, and baseline module.
- Preserve raw responses and dataset metadata: filters, timestamp, counts, missingness, truncation.
- Resolve entities by source identifiers rather than name similarity.
- Implement structured filtering/traversal plus a simple description-search baseline.
- Expose deterministic award counts and correctly labeled amounts.

### Builder B — Cognee retrieval

- Own the Cognee adapter, ingestion, retrieval, and evidence mapping.
- Test provider connectivity and a tiny ingestion before scaling up.
- Consume the exact snapshot Builder A produces; develop against fixtures first.
- Constrain returned claims and graph relationships to traceable source evidence.
- Report setup, ingestion, and query timings separately.

### Builder C — interface

- Own frontend files; build against the shared fixture response immediately.
- Implement query input, example prompts, retrieval-mode switch, answer, graph, and evidence panel.
- Clicking a node selects its source records; clicking a citation opens the corresponding evidence.
- Keep the initial graph focused, with about 15–30 visible nodes and expansion on selection.
- Show reported versus inferred links, dataset scope, loading, empty, and error states.

Avoid overlapping ownership. The lead owns backend routes and shared contracts; builders expose modules for the lead to wire together.

## Schedule and gates

| Elapsed | Work | Exit condition |
|---|---|---|
| 0:00–0:20 | Scope, environment, schemas, fixtures, provider smoke test | All builders can work independently; credential availability known |
| 0:20–1:00 | Parallel implementation | Real data slice saved; tiny Cognee ingestion succeeds; fixture UI works |
| 1:00–2:00 | Complete both retrieval paths and UI | Each workstream produces its agreed output |
| 2:00–2:30 | Integrate | Real query returns cited evidence and a graph in the UI |
| 2:30–3:15 | Evaluate and fix | Same questions run through both paths; failures documented |
| 3:15–4:00 | Stabilize and package | Repeatable startup, successful demo, README and results table |

## Evaluation

Use 8–10 questions: structured lookups, relationship traversal, semantic discovery, and unanswerable questions. Establish expected records by inspecting the dataset before comparing outputs. Give both paths the same source snapshot and the same answer-generation model/prompt where feasible.

Measure answer correctness, supporting-record retrieval, citation validity, unsupported claims, and query latency. Report provider costs only if actually measured. Keep ingestion cost separate from query cost.

For four hours, prioritize structured/lexical baseline versus Cognee. This cannot isolate graph reasoning from embedding improvements. A stronger follow-up adds explicit graph + vector retrieval with matched model access and budgets. Do not claim Cognee beats that stronger baseline unless it is implemented and tested.

## Contingencies

- No valid model/provider credentials: complete data, baseline, and UI; identify the Cognee comparison as blocked, never substitute canned answers as live results.
- API access problems: use a real manually downloaded USAspending file if available. Fixtures must be clearly labeled and excluded from results.
- Cognee setup still failing at minute 60: cut interface polish and topic extraction, isolate the smallest failing ingestion, and preserve time for integration.
- Ingestion too slow: reduce to 50–100 awards and expose the reduced scope.
- Parent data sparse: demonstrate agency/award/recipient exploration without inventing corporate relationships.
- No time for valid comparison: deliver a working prototype and unvalidated benchmark harness; omit improvement claims.

## Definition of done

- A documented command starts the local application.
- A real USAspending snapshot is loaded, with visible scope and source metadata.
- At least three useful questions return inspectable supporting records.
- Graph selection and evidence navigation work.
- Both retrieval modes execute over the same records, or the missing mode is clearly documented.
- A small results table records observed outcomes without invented metrics.
- README documents setup, limitations, and a two-minute demo walkthrough.
