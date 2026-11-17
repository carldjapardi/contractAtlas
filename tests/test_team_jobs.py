import asyncio
import json

import pytest

from backend.team_jobs import TeamJobConflict, TeamJobManager


class Unavailable(RuntimeError):
    pass


class FakeMemory:
    TeamMemoryUnavailable = Unavailable

    def get_status(self):
        return {"ready": True, "available": True}

    async def research(self, question, profile, run_id, emit):
        await emit({"kind": "agent", "title": "Partner researcher", "detail": "Checked source records.", "agent_role": "partner"})
        return {"agents": [], "before_report": "Original research preserved", "review": {"findings": [], "suggested_learning": "Keep source identities separate."}}

    async def improve_research(self, run, feedback, emit):
        return {"before_report": "Must not replace original", "after_report": "Fresh session result", "improvement": {"status": "complete", "lesson_count": 0, "learning_verified": False}}


async def finish(manager):
    await asyncio.gather(*list(manager.tasks.values()))
    await asyncio.sleep(0)


def test_research_and_improve_preserve_before_checkpoint(tmp_path):
    async def scenario():
        manager = TeamJobManager(tmp_path, FakeMemory())
        queued = manager.start("Find teaming partners", "A small cybersecurity firm")
        assert queued["status"] == "queued"
        await finish(manager)
        run = manager.get(queued["id"])
        assert run["status"] == "awaiting_review"
        assert run["before_report"] == "Original research preserved"
        assert run["events"][0]["agent_role"] == "partner"
        manager.improve(run["id"], "Preserve exact source identities in all findings.")
        await finish(manager)
        improved = manager.get(run["id"])
        assert improved["status"] == "complete"
        assert improved["before_report"] == run["before_report"]
        assert improved["after_report"] == "Fresh session result"
        # Completed processing does not become a claim of learning.
        assert improved["improvement"]["learning_verified"] is False
        assert improved["improvement"]["lesson_count"] == 0
    asyncio.run(scenario())


def test_one_active_operation_and_no_repeated_improvement(tmp_path):
    async def scenario():
        manager = TeamJobManager(tmp_path, FakeMemory())
        run = manager.start("Find teaming partners", "A small cybersecurity firm")
        with pytest.raises(TeamJobConflict):
            manager.start("Another research question", "A different firm")
        with pytest.raises(TeamJobConflict):
            manager.improve(run["id"], "A useful lesson for all agents")
        await finish(manager)
        manager.improve(run["id"], "A useful lesson for all agents")
        await finish(manager)
        with pytest.raises(TeamJobConflict):
            manager.improve(run["id"], "A useful lesson for all agents")
    asyncio.run(scenario())


def test_unknown_run_and_path_traversal_are_rejected(tmp_path):
    manager = TeamJobManager(tmp_path, FakeMemory())
    for value in ("../anything", "../../.env", "x" * 32, ""):
        with pytest.raises(KeyError):
            manager.get(value)


def test_provider_exception_is_not_written_into_artifact(tmp_path):
    class Broken(FakeMemory):
        async def research(self, *args):
            raise RuntimeError("private-provider-secret")

    async def scenario():
        manager = TeamJobManager(tmp_path, Broken())
        queued = manager.start("Find teaming partners", "A small cybersecurity firm")
        await finish(manager)
        run = manager.get(queued["id"])
        assert run["status"] == "error"
        assert "private-provider-secret" not in json.dumps(run)
    asyncio.run(scenario())


def test_service_restart_marks_active_run_interrupted(tmp_path):
    manager = TeamJobManager(tmp_path, FakeMemory())
    run = {"id": "a" * 32, "status": "running", "created_at": "2026-11-16T00:00:00Z"}
    manager.save(run)
    manager.recover_interrupted()
    recovered = manager.get(run["id"])
    assert recovered["status"] == "error"
    assert recovered["stage"] == "interrupted"


def test_shutdown_cancels_operation_and_preserves_failure_state(tmp_path):
    class Slow(FakeMemory):
        async def research(self, *args):
            await asyncio.Event().wait()

    async def scenario():
        manager = TeamJobManager(tmp_path, Slow())
        run = manager.start("Find teaming partners", "A small cybersecurity firm")
        await asyncio.sleep(0)
        await manager.shutdown()
        assert manager.get(run["id"])["status"] == "error"
    asyncio.run(scenario())
