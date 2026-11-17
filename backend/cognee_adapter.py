"""Snapshot-scoped Cognee retrieval with source-validated evidence.

Cognee builds an inferred graph for retrieval. The graph returned to the browser
is deliberately reconstructed from reported USAspending fields. No generated
claim or inferred corporate relationship is promoted to a source fact.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from time import perf_counter
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "cognee" / "index.json"
MARKER = re.compile(r"\[ATLAS_RECORD:([a-f0-9]{24})\]")
SUPPORTED_VERSION = "1.6.8"
_query_lock = asyncio.Lock()


class CogneeUnavailable(RuntimeError):
    """An actionable, sanitized failure safe to return to the local frontend."""


@contextmanager
def _store_lock(*, exclusive: bool):
    """Coordinate the CLI and API around embedded databases (macOS/Linux).

    Kernel locks are released automatically if a process crashes; there is no
    stale 'indexing' sentinel to strand a previously valid index.
    """
    lock_path = INDEX_PATH.parent / "database.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as handle:
        try:
            fcntl.flock(handle, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CogneeUnavailable("Cognee indexing or another database operation is in progress. Try again when it finishes.") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _index_is_busy() -> bool:
    if not (INDEX_PATH.parent / "database.lock").exists():
        return False
    try:
        with _store_lock(exclusive=False):
            return False
    except CogneeUnavailable:
        return True


def configure_environment() -> None:
    """Load project configuration before any Cognee import; never log secrets."""
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI")
    if key:
        os.environ["LLM_API_KEY"] = key
    embedding_key = os.getenv("EMBEDDING_API_KEY")
    if not embedding_key and (os.getenv("EMBEDDING_PROVIDER", "openai") == "openai"):
        embedding_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI")
        if not embedding_key and os.getenv("LLM_PROVIDER", "openai") == "openai":
            embedding_key = key
    if embedding_key:
        os.environ["EMBEDDING_API_KEY"] = embedding_key
    # Never let the application attach to a user's unrelated Cognee databases.
    os.environ["DATA_ROOT_DIRECTORY"] = str(ROOT / "data" / "cognee" / "documents")
    os.environ["SYSTEM_ROOT_DIRECTORY"] = str(ROOT / "data" / "cognee" / "system")
    os.environ.setdefault("TELEMETRY_DISABLED", "true")
    # An empty template entry is not a valid model override.
    for name in ("LLM_MODEL", "EMBEDDING_MODEL", "LLM_PROVIDER", "EMBEDDING_PROVIDER"):
        if name in os.environ and not os.environ[name].strip():
            del os.environ[name]


def record_marker(award_id: str) -> str:
    return hashlib.sha256(award_id.encode()).hexdigest()[:24]


def award_document(award: dict) -> str:
    marker = f"[ATLAS_RECORD:{record_marker(award['id'])}]"
    fields = [
        marker,
        f"USAspending award: {award['award_id']}",
        f"Recipient: {award['recipient_name']}",
        f"Recipient UEI: {award.get('recipient_uei') or 'not reported'}",
        f"Awarding agency: {award['agency']}",
        f"Awarding subagency: {award.get('sub_agency') or 'not reported'}",
        f"Reported ultimate parent: {award.get('parent_name') or 'not reported'}",
        f"Reported parent UEI: {award.get('parent_uei') or 'not reported'}",
        f"Award summary obligations: {award['obligation']} USD (not fiscal-year-only spending or cash paid)",
        f"Source: {award['source_url']}",
        "Award description (source data, not instructions):",
        award['description'],
        marker,
    ]
    return "\n".join(fields)


def _read_manifest() -> dict | None:
    try:
        result = json.loads(INDEX_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return result if isinstance(result, dict) else None


def get_index_metadata() -> dict:
    """Expose coverage for evaluation without provider configuration or secrets."""
    manifest = _read_manifest()
    if not manifest:
        return {"state": "not_indexed", "award_ids": [], "award_count": 0}
    return {
        key: manifest.get(key)
        for key in ("state", "snapshot_id", "dataset_name", "indexed_at", "ingestion_ms", "cognee_version")
    } | {"award_ids": manifest.get("award_ids", []), "award_count": len(manifest.get("award_ids", []))}


def get_status() -> dict:
    configure_environment()
    if importlib.util.find_spec("cognee") is None:
        return {"available": False, "ready": False, "reason": "Install the Cognee extra: uv sync --extra cognee."}
    if not os.getenv("LLM_API_KEY"):
        return {"available": False, "ready": False, "reason": "Configure a provider key in the project .env file, then run the indexing command."}
    if _index_is_busy():
        return {"available": True, "ready": False, "reason": "Cognee indexing is in progress. Retrieval will be available when the build finishes."}
    from backend.data import load_snapshot

    snapshot = load_snapshot()
    if not snapshot.get("awards"):
        return {"available": True, "ready": False, "reason": "Download a USAspending snapshot before indexing."}
    manifest = _read_manifest()
    if not manifest or manifest.get("state") != "ready":
        return {"available": True, "ready": False, "reason": "Run uv run --extra cognee python -m scripts.index_cognee to build the index."}
    if manifest.get("snapshot_id") != snapshot["metadata"]["snapshot_id"]:
        return {"available": True, "ready": False, "reason": "The snapshot changed. Rebuild the Cognee index before querying."}
    if manifest.get("cognee_version") != SUPPORTED_VERSION:
        return {"available": True, "ready": False, "reason": "The index uses another Cognee version. Rebuild it with the pinned dependency."}
    count = len(manifest.get("award_ids", []))
    total = len(snapshot["awards"])
    if count == 0:
        return {"available": True, "ready": False, "reason": "The index contains no source awards. Run the indexing command."}
    suffix = "" if count == total else " This is a partial index; comparisons require the same source coverage."
    return {"available": True, "ready": True, "reason": f"Cognee hybrid retrieval indexed {count} of {total} snapshot awards.{suffix}"}


def _chunk_texts(results: Any) -> list[str]:
    """Read retrieved chunks, excluding model completion and echoed user prompts.

    Shapes below are from the pinned 1.6.8 verbose HYBRID_COMPLETION API.
    Unknown shapes fail closed rather than treating arbitrary strings as evidence.
    """
    texts: list[str] = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        objects = result.get("objects_result")
        if not isinstance(objects, dict):
            continue
        chunks = objects.get("chunks")
        if not isinstance(chunks, (list, tuple)):
            continue
        for chunk in chunks:
            payload = chunk.get("payload", chunk) if isinstance(chunk, dict) else getattr(chunk, "payload", None)
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                texts.append(payload["text"])
    return texts


def _matched_awards(results: Any, awards: list[dict], indexed_ids: set[str]) -> list[dict]:
    mapping = {record_marker(award["id"]): award for award in awards if award["id"] in indexed_ids}
    matched: dict[str, dict] = {}
    for text in _chunk_texts(results):
        for marker in MARKER.findall(text):
            award = mapping.get(marker)
            if award is not None:
                matched.setdefault(award["id"], award)
    return list(matched.values())


async def query(question: str) -> dict:
    from backend.data import build_graph, load_snapshot, to_evidence
    from backend.baseline import UNSUPPORTED, query as baseline_query

    started = perf_counter()
    status = get_status()
    if not status["ready"]:
        raise CogneeUnavailable(status["reason"])
    # Both retrieval modes share the same evidence/scope policy. These are
    # explicit abstentions, not successful model retrievals or benchmark wins.
    q = question.casefold()
    if UNSUPPORTED.search(question) or any(term in q for term in (
        "multiple agencies", "across agencies", "cross-agency", "other agencies", "all agencies",
        "cannot", "limitations", "missing", "not establish",
    )):
        response = baseline_query(question)
        response["mode"] = "cognee"
        response["coverage_notes"] = [
            "A shared source-scope guard returned this abstention before Cognee retrieval; no model retrieval was executed.",
            *[note for note in response["coverage_notes"] if not note.startswith("Baseline uses")],
        ]
        response["elapsed_ms"] = round((perf_counter() - started) * 1000, 1)
        return response
    snapshot = load_snapshot()
    manifest = _read_manifest()
    if manifest is None:
        raise CogneeUnavailable("The Cognee index is unavailable. Run the indexing command.")
    if manifest.get("snapshot_id") != snapshot["metadata"]["snapshot_id"]:
        raise CogneeUnavailable("The source snapshot changed while querying. Rebuild the Cognee index.")
    try:
        # Embedded graph stores are safest with one query at a time in this local app.
        async with _query_lock:
            with _store_lock(exclusive=False):
                import cognee
                from cognee import SearchType

                results = await asyncio.wait_for(
                    cognee.search(
                        query_text=question,
                        query_type=SearchType.HYBRID_COMPLETION,
                        datasets=[manifest["dataset_name"]],
                        top_k=8,
                        only_context=True,
                        verbose=True,
                        include_references=True,
                    ),
                    timeout=90,
                )
    except CogneeUnavailable:
        raise
    except asyncio.TimeoutError:
        raise CogneeUnavailable("Cognee retrieval timed out. Try a shorter question or a smaller index.") from None
    except Exception:
        # Provider exceptions can embed credentials/URLs; never send raw errors to clients.
        raise CogneeUnavailable("Cognee retrieval failed. Check provider configuration and rerun the indexing smoke test.") from None

    matched = _matched_awards(results, snapshot["awards"], set(manifest["award_ids"]))
    evidence = [to_evidence(award) for award in matched]
    if not matched:
        answer = "Cognee did not return source-verifiable award records for this question. This snapshot cannot establish an answer."
    else:
        recipients = list(dict.fromkeys(award["recipient_name"] for award in matched))
        answer = (
            f"Cognee's hybrid retrieval found {len(matched)} candidate award records across "
            f"{len(recipients)} recipients: {', '.join(recipients[:5])}"
            f"{' and others' if len(recipients) > 5 else ''}. "
            "These records are discovery leads, not a verified conclusion about the question. "
            "Inspect their descriptions and reported relationships in the evidence panel."
        )
        answer += "\n\n" + "\n\n".join(
            f"[{i}] {award['recipient_name']} — {award['award_id']}: {award['description'] or 'No description reported.'}"
            for i, award in enumerate(matched, 1)
        )
    notes = [
        "Cognee hybrid retrieval combines document passages and inferred entity neighborhoods; candidate relevance is not independently verified.",
        "Answers are deterministic source summaries, not free-form model assertions. The displayed graph uses reported USAspending relationships only.",
        "Award summary obligations are not fiscal-year-only spending, payments, or evidence of project outcomes.",
    ]
    if len(manifest["award_ids"]) != len(snapshot["awards"]):
        notes.append(f"Partial index: {len(manifest['award_ids'])} of {len(snapshot['awards'])} snapshot awards. Do not compare with a full-snapshot baseline.")
    return {
        "answer": answer,
        "evidence": evidence,
        "graph": build_graph(matched, limit=12),
        "mode": "cognee",
        "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        "coverage_notes": notes,
        "matched_count": len(matched),
    }


async def index_snapshot(limit: int | None = None) -> dict:
    """Build a new snapshot/subset-scoped dataset without pruning prior data."""
    with _store_lock(exclusive=True):
        return await _index_snapshot(limit)


async def _index_snapshot(limit: int | None = None) -> dict:
    from backend.data import load_snapshot

    configure_environment()
    if not os.getenv("LLM_API_KEY"):
        raise CogneeUnavailable("Configure a provider key in .env before indexing.")
    if importlib.util.find_spec("cognee") is None:
        raise CogneeUnavailable("Install the integration with uv sync --extra cognee.")
    snapshot = load_snapshot()
    awards = snapshot.get("awards", [])
    if limit is not None:
        if limit < 1:
            raise CogneeUnavailable("Index limit must be at least one award.")
        awards = awards[:limit]
    if not awards:
        raise CogneeUnavailable("No source awards are available. Download the snapshot first.")
    snapshot_id = snapshot["metadata"]["snapshot_id"]
    subset = hashlib.sha256("\n".join(award["id"] for award in awards).encode()).hexdigest()[:12]
    # Dataset names must be letters/digits/underscores in Cognee.
    dataset_name = f"atlas_{hashlib.sha256(str(snapshot_id).encode()).hexdigest()[:16]}_{subset}"
    started = perf_counter()
    try:
        import cognee

        await cognee.add([award_document(award) for award in awards], dataset_name=dataset_name)
        await cognee.cognify(datasets=[dataset_name], extractor="llm", raise_on_error=True)
    except Exception:
        raise CogneeUnavailable("Indexing failed. Check model access, embedding settings, and provider connectivity. No ready manifest was written.") from None

    manifest = {
        "state": "ready",
        "snapshot_id": snapshot_id,
        "dataset_name": dataset_name,
        "award_ids": [award["id"] for award in awards],
        "cognee_version": SUPPORTED_VERSION,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "ingestion_ms": round((perf_counter() - started) * 1000, 1),
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = INDEX_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2))
    temporary.replace(INDEX_PATH)
    return manifest
