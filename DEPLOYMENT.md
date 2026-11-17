# Live Vercel + Supabase deployment

The deployed app uses the same React interface and Python Cloud integration as local development. Vercel serves the frontend and FastAPI endpoints. The Python Vercel Workflow SDK dispatches research independently of the HTTP request. Supabase stores run documents and the Cloud manifest; Cognee Cloud remains the source graph, agent-session memory, trace store and native improvement engine.

## Setup

1. Apply `supabase/migrations/202611160001_run_store.sql` in the project's SQL Editor. The two tables and admission RPCs are server-only, with RLS enabled and public/anonymous/authenticated access revoked.
2. Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in local `.env` for the migration/import tool. Legacy service-role JWTs and new `sb_secret_` server keys are supported. A publishable key is insufficient.
3. Run `.venv/bin/python -m scripts.publish_hosted_state`. It copies the verified Cloud manifest and completed demo into Supabase without re-ingesting or re-improving Cognee data. It refuses to replace state while a hosted job is active.
4. Link the repo root to the Vercel `contract-atlas` project. The `vercel.json` framework is FastAPI, and `pyproject.toml` declares the app and workflow registry. The build installs locked Python dependencies and builds the Vite frontend. The local Cognee SDK extra is unnecessary for this Cloud deployment.
5. Add the server-only variables below to the intended Vercel environments, deploy a preview, and verify API reads, access control and an actual research workflow before promoting.

| Variable | Value/source |
| --- | --- |
| `SUPABASE_URL` | Official project HTTPS URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only service-role/secret key |
| `COGNEE_SERVICE_URL` | Existing HTTPS tenant URL |
| `COGNEE_API_KEY` | Existing tenant API key |
| `COGNEE_TEAM_RUNTIME` | `cloud` |
| `ATLAS_JOB_RUNTIME` | `vercel` |
| `ATLAS_STATE_DIR` | `/tmp/contract-atlas` (scratch locks only) |
| `ATLAS_DEMO_ACCESS_CODE` | Random shared code for live paid actions |

No provider or Supabase service key belongs in a `VITE_` variable or the frontend bundle. The app unlock form sets an HTTP-only secure cookie on Vercel. Read access to the completed demo and benchmark remains available according to the deployment's Vercel access configuration. The local generated demo code is in ignored `.env`; unlock before filming. Local development does not require this gate unless `ATLAS_REQUIRE_DEMO_ACCESS=true` is explicitly set.

## Execution and limits

Database transaction locks atomically admit one active research/improvement operation across all serverless instances. Queued jobs are dispatched to native Vercel Workflow; function cold starts and shutdowns do not cancel them. The existing Cloud calls and saved progress execute inside a workflow step. Paid steps have `max_retries=0`, and the worker claims the queued state before running, so ordinary duplicate delivery cannot automatically repeat ingestion or improvement. Failed submission releases only a still-queued run; it cannot overwrite a worker that already started.

Provider side effects are not transactionally atomic with database writes. A hard interruption during a Cloud request can leave its result uncertain. Preserve recorded state and inspect the Cloud/workflow logs before manually retrying. This is a single shared hackathon workspace, not a tenant-isolated production service. The original local award-only Cognee index is not uploaded; the deterministic explorer remains available and the Research team uses the actual Cloud graph.

The Python Workflow SDK is pinned to beta version `0.13.0`. Native execution must be verified on the account before claiming the deployed learning loop works. A ready Vercel build alone is insufficient. Preview deployments can require Vercel sign-in; test public reachability separately when publishing the final production URL.

## November 16 deployment checkpoint

The protected preview built successfully. Its HTML and API respond, and native probe `wrun_41M7KSRQTQ0GGARD58T1DS4QCF` reached `completed` after the start request returned. The Supabase migration and state import then succeeded. A real hosted three-role research run and production native improvement completed, with two new lessons verified in a fresh session and the original report preserved. See [HOSTED_RESULTS.md](HOSTED_RESULTS.md).

Production is public at https://contract-atlas-personal-d624.vercel.app. Vercel authentication is limited to previews; production paid actions retain the app's demo-code gate. Browser source inspection, benchmark rendering and the native-learning result were checked against the public app.
