# Contract Atlas

Explore federal contract relationships, retrieve relevant awards, and inspect the source records behind each result. Built as a local hackathon proof of concept with a structured/lexical baseline and a Cognee hybrid retrieval integration.

## Start

Requires Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), and Node.js 22+.

```sh
make setup
make dev
```

Open http://127.0.0.1:5173. The backend runs at http://127.0.0.1:8000; interactive API documentation is at `/docs`. Stop both development servers with Ctrl+C. For a single-server local build, run `make preview` and open http://127.0.0.1:8000.

The real USAspending snapshot is included. Baseline search and graph exploration require no API key. Cognee requires provider configuration and a local index, which are deliberately excluded from Git.

## Enable Cognee

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

## Demo walkthrough

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

The baseline uses reported relationships and token/prefix matching. Cognee uses graph-assisted hybrid retrieval over the same source records and returns source-validated candidates. Both render deterministic summaries, reducing the confounding effect of different generation models. The visible graph always reconstructs reported USAspending fields; it does not present Cognee's extracted internal relationships as official facts.

This comparison does **not** isolate graph reasoning from embedding effects. A structured graph plus vector search is the stronger follow-up baseline. Do not generalize these exploratory results into a claim that Cognee outperforms that baseline.

## Engineering layout

```text
backend/       FastAPI boundary, snapshot queries, baseline, Cognee adapter
frontend/      React + TypeScript + React Flow investigation workspace
scripts/       Reproducible ingestion, indexing, evaluation, dev runner
data/          Frozen real snapshot, raw public responses, evaluation artifacts
tests/         Identity, financial semantics, retrieval, provider, and API checks
CONTRACT.md    Shared schemas and module ownership
PLAN.md        Four-hour scope and milestone plan
```

Python and JavaScript dependencies are locked in `uv.lock` and `frontend/package-lock.json`. Secrets and provider exception details are withheld from API responses. The service binds to loopback for local use. Hosting, authentication, live ingestion, and production operations are outside this prototype.

Sources: [USAspending API](https://api.usaspending.gov/docs/), [USAspending data disclosures](https://www.usaspending.gov/data/about-the-data-download.pdf), [Cognee documentation](https://docs.cognee.ai/).
