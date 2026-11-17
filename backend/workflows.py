"""Durable orchestration; paid operations are never automatically replayed."""
from vercel import workflow

wf = workflow.Workflows()


@wf.step(max_retries=0)
async def execute_job_step(*, run_id: str, action: str):
    from backend.durable_jobs import DurableTeamJobManager
    manager = DurableTeamJobManager()
    target = "running" if action == "research" else "improving"
    if action not in {"research", "improve"}:
        raise ValueError("Unknown research operation")
    run = manager.store.claim(run_id, ["queued"], target)
    if run is None:
        # Duplicate delivery cannot replay an ingestion or paid improvement call.
        return {"status": manager.get(run_id)["status"], "duplicate_delivery": True}
    if action == "research":
        await manager._research(run)
    else:
        await manager._improve(run, run["accepted_feedback"])
    return {"status": manager.get(run_id)["status"]}


@wf.step(max_retries=3)
async def fail_job_step(*, run_id: str):
    from backend.run_store import SupabaseRunStore
    store = SupabaseRunStore()
    run = store.claim(run_id, ["queued", "running", "improving"], "error")
    if run:
        run.update(stage="Hosted operation interrupted", error="The hosted operation could not finish. The saved evidence is preserved; inspect the run before retrying.")
        store.save(run)


@wf.workflow
async def execute_team_job(*, run_id: str, action: str):
    try:
        return await execute_job_step(run_id=run_id, action=action)
    except Exception:
        await fail_job_step(run_id=run_id)
        return {"status": "error"}
