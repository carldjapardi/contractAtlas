# Contract Atlas

**New to the project? Read [the plain-English explanation](PROJECT_SIMPLE.md) first.**

**Filming:** [Two-minute walkthrough script](DEMO_SCRIPT.md), with screen actions and verified run selection.

**Latest measured result:** the isolated 68-source comparison completed 16 answers. Document RAG scored 22/24 checks before and after review; Cognee hybrid scored 20/24 before and after. One new lesson was saved and retrieved. No answer-quality advantage is established. See [observed comparison](COMPARISON_RESULTS.md) and **Benchmark** in the app.

**A shared research memory for cybersecurity contractors pursuing federal work.** Three research agents connect historical awards, agency guidance, and vendor capabilities, review their findings, and carry accepted lessons into a fresh agent session through Cognee.

## Motivation and user

The user is a small cybersecurity contractor's business-development/capture team. They need to understand agency needs, identify relevant incumbents and potential teaming partners, and distinguish demonstrated past performance from a company's marketing claims.

Their evidence is fragmented: USAspending contains historical awards, agency pages describe priorities, company pages describe capabilities, and the team's own review decisions live in conversations. Research gets repeated and useful corrections disappear between sessions.

Contract Atlas turns these into a shared, source-linked memory that the next researcher can use.

**Example task:** “We implement identity and access management. Which companies could complement us on DHS cybersecurity work, what evidence supports the fit, and what still needs verification?”

## Hackathon scope

One company-focused research workflow, one agency domain, three agent roles, and an explicit review-and-improve cycle:

1. **Opportunity analyst** identifies agency needs and unknowns from the brief and guidance.
2. **Partner researcher** connects those needs with award history and vendor capability evidence, using the shared memory and earlier agent traces.
3. **Evidence reviewer** flags unsupported conclusions and proposes a reusable team research lesson.
4. **Human review** accepts or edits that lesson.
5. **Cognee `improve()`** consolidates actual sessions and traces and attempts to distill durable guidance.
6. **Fresh-session researcher** receives the original task/profile, retrieves permanent memory, and produces an inspectable after report. Accepted feedback is not copied into its prompt.

The source collection contains **28 genuine documents**: 25 selected historical DHS awards, CISA's zero-trust guidance page, and Leidos/GuidePoint capability excerpts. The broader supporting award explorer contains 265 awards and 150 recipient identities. Internal company/task inputs are separately labeled. Guidance and past awards are not presented as live solicitations.

The four-hour scope excludes live SAM.gov opportunity feeds, automatic bidding, outreach, verified eligibility/certification checks, a comprehensive federal market index, and production access management.

## Deliverables

- A local web application with a primary **Research team** workspace.
- Three actual provider-backed research roles with distinct persistent sessions.
- A shared collection showing source types, URLs, excerpts and evidence limitations.
- Recorded activity, reports, retrieved memory, agent traces and a bounded actual Cognee graph.
- An unchanged before checkpoint, editable review lesson, native improvement stage results, new-lesson counts and a fresh-session memory check.
- Supporting award graph/search and an openly reported initial retrieval comparison.
- Reproducible source collection, setup commands, tests, locked dependencies and small reviewable commits.

## Why this fits the Cognee track

| Sponsor emphasis | What the demo must make visible |
| --- | --- |
| **Shared agent memory** | Distinct research roles read the same persistent dataset and retrieve earlier agents' recorded traces. |
| **Self-improvement** | Accepted guidance enters a real session; `improve()` returns actual stages/counts; a fresh session attempts to retrieve the resulting durable lesson. |
| **Connecting different sources** | Award records, official agency guidance, vendor claims and internal research inputs participate in one memory graph. |
| **Inspectable graph memory** | Users can inspect retrieved context, sources, recorded sessions and extracted relationships. |

The strongest demonstration is a visible learning loop: a team reviews a source-backed finding once, and a later agent retrieves the lesson from shared memory. It ties the sponsor's capabilities to a specific company workflow and gives judges evidence they can inspect.

This makes the project a credible track submission; winning depends on the final execution and judging. We will not claim a lesson was learned merely because an API call completed. **Learning verification requires a newly distilled document and its actual retrieval in a fresh session.** Report quality remains subject to human review. Improvement changes persistent memory and retrieval, not model weights.

## Current verification checkpoint

- Real source collection, award explorer and initial Cognee index: verified.
- Cognee Cloud authentication and required REST endpoints: verified.
- Research-team UI and Cloud session/trace orchestration: verified in a real run.
- Native Cloud improvement: four new lesson documents created; a fresh partner session retrieved all four. Original report preserved. See [demo results](DEMO_RESULTS.md).
- Regression checks: 83 backend tests passed; production frontend build passed. GitHub CI is configured but has not been run remotely in this session.
- Initial retrieval benchmark: preserved, including cases where the lexical baseline performs better. Those results are not evidence of the revised team's learning quality.

## Start

Requires Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), and Node.js 22+.

```sh
make setup
make dev
```

Open http://127.0.0.1:5173. The backend runs at http://127.0.0.1:8000; interactive API documentation is at `/docs`. Stop both development servers with Ctrl+C. For a single-server local build, run `make preview` and open http://127.0.0.1:8000.

The real USAspending snapshot is included. Baseline search and reported graph exploration require no API key. Shared research requires a configured Cognee runtime and seeded source memory. Credentials, runtime databases and research-run artifacts are excluded from Git.

## Shared research memory setup

For the Cloud demo, add these to your local `.env`:

```dotenv
COGNEE_TEAM_RUNTIME=cloud
COGNEE_SERVICE_URL=https://your-tenant.aws.cognee.ai
COGNEE_API_KEY=your_key
```

Then seed the real source collection once:

```sh
uv run --extra cognee python -m scripts.seed_team_memory
```

Open **Research team**, review the editable hypothetical company/task defaults, and start research. Inspect the three agents' findings and sources, edit the accepted lesson, and choose **Improve team memory**. Inspect the actual stage results and fresh-session evidence.

The Cloud path uses Cognee's REST endpoints for ingestion, graph retrieval, agent registration, typed session traces, review turns, improvement and graph visualization. Keeping these operations in the same tenant avoids splitting local SDK sessions from remote memory. Model work on this path uses the configured Cognee Cloud account/credits.

To use the local SDK implementation, set `COGNEE_TEAM_RUNTIME=local`, configure an LLM/embedding provider, and run the same seed command. Native SDK agent tracing and session improvement remain local in that mode. A run should stay within one runtime.

## Supporting local award-retrieval comparison

Copy `.env.example` to `.env` if you do not already have a `.env`. Configure an OpenAI key under `OPENAI`, `OPENAI_API_KEY`, or `LLM_API_KEY`. `OPENAI` is accepted as a convenience alias for LLM and embedding credentials. Do not commit `.env`.

If you use separate providers, configure both the LLM and embedding settings. An empty `LLM_MODEL` uses the pinned Cognee package default; override it with a model available to your provider account. `.env.example` supplies an explicit OpenAI embedding configuration.

Start with a small paid-provider smoke test:

```sh
uv run --extra cognee python -m scripts.index_cognee --limit 3 --smoke
```

Then index the entire frozen snapshot:

```sh
uv run --extra cognee python -m scripts.index_cognee --smoke
```

Indexing and embedding use the configured provider and may incur usage charges. Partial indexes are labeled in the application. Comparisons require an index over the exact full source snapshot. Provider credentials, the index, and local databases remain on your machine. The adapter uses project-local Cognee storage and does not prune unrelated databases.

## What is in the snapshot?

The initial snapshot contains **265 awards from 150 reported recipients**, retrieved November 16, 2026 (Pacific time). It uses USAspending's `cyber` keyword search for DHS contracts with activity during FY2025. The keyword may match recipient or agency fields as well as descriptions. It is not a complete or classified inventory of cybersecurity contracts.

All 265 award detail requests succeeded for this snapshot. Parent relationships are shown only when a reported parent UEI exists. Missing parent fields mean unknown; names do not establish corporate relationships.

**Financial meaning:** the amount shown for an award is its reported award-summary lifetime obligation. A fiscal-year activity filter does not make that amount fiscal-year spending. The app has no transaction-level cash payments, outcome measures, or subaward records.

The machine-readable metadata includes exact filters, retrieval timestamp, a content hash, source coverage, and limitations. Public raw responses are retained under `data/raw/` for inspection.

To refresh:

```sh
uv run --extra cognee python -m scripts.ingest --limit 300 --fiscal-year 2025 --keyword cyber
```

Refreshing changes the snapshot identity and invalidates stale indexes and evaluation results. Reindex before using Cognee again. Ingestion is a CLI action; the application cannot silently refresh the source corpus.

## Supporting award-explorer walkthrough

1. Open Explore and inspect the reported agency → award → recipient relationships.
2. Ask `Find award 70B04C23F00001108` using the baseline.
3. Select the award or recipient and inspect its evidence; open the original USAspending record.
4. Switch to Cognee and ask a discovery question, such as who provides vulnerability management support. Inspect candidate descriptions instead of treating retrieval as a verified conclusion.
5. Open Awards to search the snapshot and Benchmark to inspect the recorded retrieval checks.

## Evaluation

```sh
make test
uv run --extra cognee python -m scripts.evaluate --mode baseline
uv run --extra cognee python -m scripts.evaluate --mode both
```

The eight exploratory cases cover identity lookup, lexical and semantic discovery, and questions unsupported by the dataset. Positive source anchors were chosen by reading real record descriptions. They are not exhaustive relevance judgments or a held-out benchmark.

- **Anchor recall:** fraction of those selected source anchors returned in evidence.
- **Citation validity:** fraction of returned evidence IDs present in the source snapshot. This checks identity, not whether the source entails an answer.
- **Latency:** observed wall time for each retrieval call; it includes cold-start costs when present.
- **Abstention check:** no evidence returned for designated unsupported questions. This is a limited automated check; inspect the answer text as well.

The initial award-only baseline uses reported relationships and lexical token matching. Cognee uses graph-assisted hybrid retrieval over the same source records and returns source-validated candidates. Both render deterministic summaries. The supporting award graph reconstructs reported USAspending fields. The research-team view separately displays the actual extracted Cognee graph with inferred relationships labeled.

This comparison does **not** isolate graph reasoning from embedding effects. A structured graph plus vector search is the stronger follow-up baseline. Do not generalize these exploratory results into a claim that Cognee outperforms that baseline.

## Engineering layout

```text
backend/       API, persistent research jobs, Cloud/local shared memory, award retrieval
frontend/      React + TypeScript + React Flow investigation workspace
scripts/       Source collection, ingestion, seeding, indexing, evaluation, dev runner
data/          Frozen real snapshot, raw public responses, evaluation artifacts
tests/         Identity, financial semantics, retrieval, provider, and API checks
CONTRACT.md    Shared schemas and module ownership
PLAN.md        Four-hour scope and milestone plan
PIVOT.md       Confirmed company persona and sponsor-focused acceptance criteria
TEAM_CONTRACT.md Research-team interfaces and source/learning invariants
```

Python and JavaScript dependencies are locked in `uv.lock` and `frontend/package-lock.json`. Secrets and provider exception details are withheld from API responses. The service binds to loopback for local use. Hosting, authentication, live ingestion, and production operations are outside this prototype.

Sources: [USAspending API](https://api.usaspending.gov/docs/), [USAspending data disclosures](https://www.usaspending.gov/data/about-the-data-download.pdf), [Cognee documentation](https://docs.cognee.ai/).
