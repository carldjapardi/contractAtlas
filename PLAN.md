# Spending Atlas — four-hour prototype plan

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
