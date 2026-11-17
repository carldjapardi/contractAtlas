"""Hosted job control tests with in-memory persistence and zero provider calls."""

import asyncio
import json

import pytest
from vercel import workflow

from backend import durable_jobs, run_store, workflows
from backend.team_jobs import TeamJobConflict

RUN_ID = "a" * 32


def detached(value):
    return json.loads(json.dumps(value))


def run_document(status="queued"):
    return {"id": RUN_ID, "status": status, "stage": "Research queued",
            "created_at": "2026-11-17T00:00:00Z", "updated_at": "2026-11-17T00:00:00Z",
            "question": "Find source-grounded teaming leads", "profile": "Fictional small identity firm",
            "events": [], "sources": [], "agents": [], "before_report": "Original checkpoint",
            "after_report": None, "review": None, "improvement": None,
            "memory_graph": None, "memory_stats": None, "error": None}


class FakeStore:
    """Model the REST store's detached documents and database admission contract."""

    def __init__(self, runs=()):
        self.runs = {r["id"]: detached(r) for r in runs}
        self.claims = []
        self.saves = []

    def active(self):
        return any(run["status"] in {"queued", "running", "improving"} for run in self.runs.values())

    def create(self, run):
        if self.active() or run["id"] in self.runs:
            return False
        self.runs[run["id"]] = detached(run)
        return True

    def save(self, run):
        self.saves.append(detached(run))
        self.runs[run["id"]] = detached(run)

    def get(self, run_id):
        return detached(self.runs[run_id])

    def list(self):
        return detached(list(self.runs.values()))[:10]

    def claim(self, run_id, expected_statuses, next_status):
        self.claims.append((run_id, tuple(expected_statuses), next_status))
        run = self.runs.get(run_id)
        if not run or run["status"] not in expected_statuses:
            return None
        if next_status in {"queued", "running", "improving"} and any(
            other["id"] != run_id and other["status"] in {"queued", "running", "improving"}
            for other in self.runs.values()
        ):
            return None
        run["status"] = next_status
        return detached(run)


class FakeMemory:
    class TeamMemoryUnavailable(RuntimeError):
        pass

    def __init__(self):
        self.research_calls = 0
        self.improve_calls = 0

    def get_status(self):
        return {"ready": True}

    async def seed_memory(self, **kwargs):
        raise AssertionError("No ingestion/provider call should be needed")

    async def research(self, question, profile, run_id, emit):
        self.research_calls += 1
        await emit({"kind": "agent", "title": "Researching", "detail": "Mock source evidence"})
        return {"agents": [], "before_report": "Actual mock research checkpoint",
                "review": {"findings": [], "suggested_learning": "Keep source identities separate."}}

    async def improve_research(self, run, feedback, emit):
        self.improve_calls += 1
        assert feedback == "Keep source identities separate."
        return {"before_report": "A provider must not replace the original checkpoint",
                "after_report": "Fresh mock research", "improvement": {"status": "complete", "lesson_count": 0}}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(durable_jobs, "load_sources", lambda: [])

    def build(runs=()):
        store = FakeStore(runs)
        memory = FakeMemory()
        manager = durable_jobs.DurableTeamJobManager(store)
        manager._memory = memory
        # Workflow step obtains the same persisted state through a fresh manager
        # constructor; no SDK dispatch, service key, or remote HTTP is required.
        monkeypatch.setattr(durable_jobs, "DurableTeamJobManager", lambda: manager)
        return manager, store, memory
    return build


def test_cold_start_recovery_and_http_shutdown_do_not_cancel_durable_work(setup):
    manager, store, _ = setup([run_document("running")])

    class TaskSentinel:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    task = TaskSentinel()
    manager.tasks[RUN_ID] = task
    original = store.get(RUN_ID)
    manager.recover_interrupted()
    asyncio.run(manager.shutdown())
    assert store.get(RUN_ID) == original
    assert not task.cancelled
    assert store.claims == [] and store.saves == []


def test_rejected_global_admission_never_dispatches_workflow(setup, monkeypatch):
    manager, store, _ = setup([run_document("running")])
    calls = []

    async def dispatch(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(workflow, "start", dispatch)
    with pytest.raises(TeamJobConflict):
        asyncio.run(manager.start("A valid research question", "A company profile"))
    assert calls == []
    assert len(store.runs) == 1


def test_queued_http_snapshot_is_preserved_when_worker_finishes_during_dispatch(setup, monkeypatch):
    manager, store, memory = setup()

    async def immediate_worker(fn, *, run_id, action):
        assert fn is workflows.execute_team_job
        await workflows.execute_job_step.func(run_id=run_id, action=action)
        return {"workflow_id": "mock-dispatch"}

    monkeypatch.setattr(workflow, "start", immediate_worker)
    response = asyncio.run(manager.start("Find teaming leads", "A company profile"))
    assert response["status"] == "queued"
    assert response["before_report"] is None
    stored = store.get(response["id"])
    assert stored["status"] == "awaiting_review"
    assert stored["before_report"] == "Actual mock research checkpoint"
    assert memory.research_calls == 1


def test_duplicate_improvement_admission_never_dispatches_twice_and_keeps_before(setup, monkeypatch):
    manager, store, memory = setup([run_document("awaiting_review")])
    dispatches = []

    async def deferred_worker(fn, *, run_id, action):
        dispatches.append((run_id, action))

    monkeypatch.setattr(workflow, "start", deferred_worker)
    response = asyncio.run(manager.improve(RUN_ID, "Keep source identities separate."))
    assert response["status"] == "queued"
    assert response["before_report"] == "Original checkpoint"
    with pytest.raises(TeamJobConflict):
        asyncio.run(manager.improve(RUN_ID, "Keep source identities separate."))
    assert dispatches == [(RUN_ID, "improve")]
    result = asyncio.run(workflows.execute_job_step.func(run_id=RUN_ID, action="improve"))
    assert result["status"] == "complete"
    assert memory.improve_calls == 1
    assert store.get(RUN_ID)["before_report"] == "Original checkpoint"
    assert store.get(RUN_ID)["after_report"] == "Fresh mock research"


@pytest.mark.parametrize("action", ["research", "improve"])
def test_duplicate_step_delivery_does_not_repeat_paid_operation(setup, action):
    run = run_document()
    if action == "improve":
        run["accepted_feedback"] = "Keep source identities separate."
    manager, store, memory = setup([run])
    first = asyncio.run(workflows.execute_job_step.func(run_id=RUN_ID, action=action))
    again = asyncio.run(workflows.execute_job_step.func(run_id=RUN_ID, action=action))
    assert again == {"status": first["status"], "duplicate_delivery": True}
    assert (memory.research_calls, memory.improve_calls) == ((1, 0) if action == "research" else (0, 1))


def test_paid_step_disables_automatic_retries_and_sdk_cancellation():
    assert workflows.execute_job_step.max_retries == 0
    assert workflows.execute_job_step.cancellable is False


def test_lost_dispatch_response_does_not_overwrite_started_worker(setup, monkeypatch):
    manager, store, memory = setup()

    async def started_but_response_lost(fn, *, run_id, action):
        await workflows.execute_job_step.func(run_id=run_id, action=action)
        raise RuntimeError("private provider diagnostic should never escape")

    monkeypatch.setattr(workflow, "start", started_but_response_lost)
    with pytest.raises(TeamJobConflict) as error:
        asyncio.run(manager.start("Find teaming leads", "A company profile"))
    assert "private provider diagnostic" not in str(error.value)
    assert len(store.runs) == 1
    saved = next(iter(store.runs.values()))
    assert saved["status"] == "awaiting_review"
    assert saved["before_report"] == "Actual mock research checkpoint"
    assert memory.research_calls == 1


def test_unstarted_dispatch_failure_releases_queued_run_without_paid_calls(setup, monkeypatch):
    manager, store, memory = setup()

    async def no_dispatch(*args, **kwargs):
        raise RuntimeError("private SDK diagnostic")

    monkeypatch.setattr(workflow, "start", no_dispatch)
    with pytest.raises(TeamJobConflict):
        asyncio.run(manager.start("Find teaming leads", "A company profile"))
    assert next(iter(store.runs.values()))["status"] == "error"
    assert (memory.research_calls, memory.improve_calls) == (0, 0)


def test_failure_step_can_release_own_run_while_another_run_is_active(setup, monkeypatch):
    original = run_document("running")
    peer = {**run_document("improving"), "id": "b" * 32}
    _, store, _ = setup([original, peer])
    monkeypatch.setattr(run_store, "SupabaseRunStore", lambda: store)
    asyncio.run(workflows.fail_job_step.func(run_id=RUN_ID))
    assert store.get(RUN_ID)["status"] == "error"
    assert store.get(RUN_ID)["before_report"] == "Original checkpoint"
    assert store.get(peer["id"])["status"] == "improving"


def test_unknown_action_never_claims_or_calls_provider(setup):
    _, store, memory = setup([run_document()])
    with pytest.raises(ValueError, match="Unknown research operation"):
        asyncio.run(workflows.execute_job_step.func(run_id=RUN_ID, action="not-an-action"))
    assert store.claims == []
    assert (memory.research_calls, memory.improve_calls) == (0, 0)
