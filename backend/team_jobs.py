"""Persistent local job control for the research → review → improve workflow."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STATUSES = {"queued", "running", "improving"}
RUN_ID = re.compile(r"^[a-f0-9]{32}$")


class TeamJobConflict(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sources() -> list[dict]:
    path = ROOT / "data/team_sources.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return payload.get("sources", [])


class TeamJobManager:
    def __init__(self, directory: Path | None = None, memory: Any = None):
        self.directory = directory or ROOT / "data/team/runs"
        self._memory = memory
        self.tasks: dict[str, asyncio.Task] = {}

    @property
    def memory(self):
        if self._memory is None:
            from backend import team_memory
            self._memory = team_memory
        return self._memory

    def _path(self, run_id: str) -> Path:
        if not RUN_ID.fullmatch(run_id):
            raise KeyError("Unknown research run")
        return self.directory / f"{run_id}.json"

    def save(self, run: dict):
        self.directory.mkdir(parents=True, exist_ok=True)
        run["updated_at"] = now()
        path = self._path(run["id"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(run, indent=2, allow_nan=False) + "\n")
        temporary.replace(path)

    def get(self, run_id: str) -> dict:
        try:
            return json.loads(self._path(run_id).read_text())
        except (OSError, ValueError):
            raise KeyError("Unknown research run") from None

    def list(self) -> list[dict]:
        runs = []
        for path in self.directory.glob("*.json"):
            try:
                run = json.loads(path.read_text())
                if RUN_ID.fullmatch(run.get("id", "")):
                    runs.append(run)
            except (OSError, ValueError):
                continue
        return sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)[:10]

    def recover_interrupted(self):
        # Called only at service startup, never by ordinary read/status requests.
        for run in self.list():
            if run["status"] in ACTIVE_STATUSES:
                run["status"] = "error"
                run["stage"] = "interrupted"
                run["error"] = "The service restarted before this run finished. Start a new research run."
                self.save(run)

    @property
    def busy(self) -> bool:
        return any(not task.done() for task in self.tasks.values())

    def _schedule(self, run_id: str, coroutine):
        task = asyncio.create_task(coroutine, name=f"team-research-{run_id}")
        self.tasks[run_id] = task

        def release(finished):
            if self.tasks.get(run_id) is finished:
                self.tasks.pop(run_id, None)

        task.add_done_callback(release)

    async def _emit(self, run: dict, event: dict):
        agent = event.get("agent_result")
        if isinstance(agent, dict) and agent.get("session_id"):
            run["agents"] = [a for a in run["agents"] if a["session_id"] != agent["session_id"]] + [agent]
            if agent.get("role") == "partner" and not run.get("before_report"):
                run["before_report"] = agent.get("report")
        # Only whitelisted event fields cross the HTTP boundary.
        safe = {key: event[key] for key in ("kind", "title", "detail", "agent_role", "metrics") if key in event}
        safe.update({"id": uuid4().hex, "at": now()})
        run["events"].append(safe)
        run["stage"] = event.get("title") or run["stage"]
        self.save(run)

    def start(self, question: str, profile: str) -> dict:
        if self.busy:
            raise TeamJobConflict("Another team research operation is running. Wait for it to finish.")
        run_id = uuid4().hex
        created = now()
        brief = {"id": "brief:" + run_id, "title": "Team research brief (user supplied)",
                 "kind": "internal_brief", "url": None, "retrieved_at": created,
                 "text": "Company profile:\n" + profile + "\n\nResearch question:\n" + question,
                 "notes": ["Internal research brief; not an open government solicitation."]}
        run = {"id": run_id, "created_at": created, "updated_at": created,
               "status": "queued", "stage": "Research queued", "question": question, "profile": profile,
               "events": [], "sources": [*load_sources(), brief], "agents": [],
               "before_report": None, "after_report": None, "review": None, "improvement": None,
               "memory_graph": None, "memory_stats": None, "error": None}
        self.save(run)
        # Return a detached snapshot of the queued state before background mutation.
        response = json.loads(json.dumps(run))
        self._schedule(run_id, self._research(run))
        return response

    async def _research(self, run: dict):
        emit = lambda event: self._emit(run, event)
        try:
            run["status"] = "running"
            self.save(run)
            if not self.memory.get_status().get("ready"):
                await emit({"kind": "memory", "title": "Preparing shared source memory", "detail": "Connecting the source collection in Cognee before the agents begin."})
                await self.memory.seed_memory(emit=emit)
            result = await self.memory.research(run["question"], run["profile"], run["id"], emit)
            for key in ("agents", "before_report", "review", "memory_graph", "memory_stats"):
                if key in result:
                    run[key] = result[key]
            run["status"] = "awaiting_review"
            await emit({"kind": "review", "title": "Research ready for review", "detail": "Inspect the findings, then accept or edit a lesson to improve shared team memory."})
        except asyncio.CancelledError:
            run["status"] = "error"
            run["stage"] = "interrupted"
            run["error"] = "The research operation was interrupted. Start a new run."
            raise
        except Exception as exc:
            run["status"] = "error"
            run["stage"] = "Research could not finish"
            run["error"] = str(exc) if isinstance(exc, self.memory.TeamMemoryUnavailable) else "Team research failed. Check provider connectivity and retry."
        finally:
            self.save(run)

    def improve(self, run_id: str, feedback: str) -> dict:
        if self.busy:
            raise TeamJobConflict("Another team research operation is running. Wait for it to finish.")
        run = self.get(run_id)
        if run["status"] != "awaiting_review":
            raise TeamJobConflict("Only a completed research run awaiting review can be improved.")
        run["status"] = "improving"
        run["stage"] = "Improvement queued"
        run["accepted_feedback"] = feedback
        self.save(run)
        response = json.loads(json.dumps(run))
        self._schedule(run_id, self._improve(run, feedback))
        return response

    async def _improve(self, run: dict, feedback: str):
        emit = lambda event: self._emit(run, event)
        before = run["before_report"]
        try:
            result = await self.memory.improve_research(run, feedback, emit)
            for key in ("agents", "after_report", "fresh_session_id", "improvement", "memory_graph", "memory_stats"):
                if key in result:
                    run[key] = list({agent["session_id"]: agent for agent in result[key]}.values()) if key == "agents" else result[key]
            run["status"] = "complete"
            await emit({"kind": "complete", "title": "Memory improvement inspected", "detail": "Compare the original research with the fresh agent session and inspect the actual learning results."})
        except asyncio.CancelledError:
            run["status"] = "error"
            run["stage"] = "interrupted"
            run["error"] = "Memory improvement was interrupted. The original research is preserved."
            raise
        except Exception as exc:
            run["status"] = "error"
            run["stage"] = "Improvement could not finish"
            run["error"] = str(exc) if isinstance(exc, self.memory.TeamMemoryUnavailable) else "Memory improvement failed. The original research is preserved."
        finally:
            run["before_report"] = before
            self.save(run)

    async def shutdown(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


manager = TeamJobManager()
