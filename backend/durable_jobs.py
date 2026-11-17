"""Supabase-backed admission and Vercel Workflow dispatch for hosted jobs."""
import json
from uuid import uuid4

from backend.team_jobs import TeamJobManager, TeamJobConflict, load_sources, now
from backend.run_store import SupabaseRunStore


class DurableTeamJobManager(TeamJobManager):
    def __init__(self, store=None):
        super().__init__()
        self.store = store or SupabaseRunStore()

    def save(self, run):
        self.store.save(run)

    def get(self, run_id):
        return self.store.get(run_id)

    def list(self):
        return self.store.list()

    @property
    def busy(self):
        return self.store.active()

    def recover_interrupted(self):
        # Function cold starts must never cancel durable work on another instance.
        pass

    async def shutdown(self):
        # The workflow owns execution, not the HTTP application's lifespan.
        pass

    async def _dispatch(self, run, action):
        try:
            from vercel import workflow
            from backend.workflows import execute_team_job
            await workflow.start(execute_team_job, run_id=run["id"], action=action)
        except Exception:
            # Only release a run that has not started. A worker may have won a
            # race with a lost submission response; never overwrite its progress.
            failed = self.store.claim(run["id"], ["queued"], "error")
            if failed:
                failed.update(stage="Workflow submission failed", error="The operation was not started. Refresh and inspect this run before retrying.")
                self.save(failed)
            raise TeamJobConflict("Workflow submission could not be confirmed. Refresh the run before starting another operation.") from None
        return json.loads(json.dumps(run))

    async def start(self, question, profile):
        run_id, created = uuid4().hex, now()
        brief = {"id": "brief:" + run_id, "title": "Team research brief (user supplied)",
                 "kind": "internal_brief", "url": None, "retrieved_at": created,
                 "text": "Company profile:\n" + profile + "\n\nResearch question:\n" + question,
                 "notes": ["Internal research brief; not an open government solicitation."]}
        run = {"id": run_id, "created_at": created, "updated_at": created,
               "status": "queued", "stage": "Research queued", "question": question, "profile": profile,
               "events": [], "sources": [*load_sources(), brief], "agents": [], "before_report": None,
               "after_report": None, "review": None, "improvement": None, "memory_graph": None,
               "memory_stats": None, "error": None}
        if not self.store.create(run):
            raise TeamJobConflict("Another team memory operation is running. Wait for it to finish.")
        return await self._dispatch(run, "research")

    async def improve(self, run_id, feedback):
        run = self.store.claim(run_id, ["awaiting_review"], "queued")
        if run is None:
            raise TeamJobConflict("This review was already submitted or another memory operation is running.")
        run.update(stage="Improvement queued", accepted_feedback=feedback)
        self.save(run)
        return await self._dispatch(run, "improve")
