"""Run reproducible exploratory retrieval checks against a frozen local snapshot."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from backend import baseline, cognee_adapter, data
from backend.models import Answer

ROOT = Path(__file__).resolve().parents[1]


async def run(modes: list[str], limit: int | None = None) -> dict:
    snapshot = data.load_snapshot()
    metadata = snapshot["metadata"]
    records = snapshot["awards"]
    if not records:
        raise ValueError("Load a real snapshot before evaluating.")
    case_file = json.loads((ROOT / "data/evaluation_cases.json").read_text())
    cases = case_file["cases"][:limit]
    by_award_id = {a["award_id"]: a["id"] for a in records}
    known_ids = {a["id"] for a in records}
    manifest = None
    try:
        manifest = json.loads(cognee_adapter.INDEX_PATH.read_text())
    except (OSError, ValueError):
        pass
    comparable_cognee = bool(
        manifest and manifest.get("snapshot_id") == metadata["snapshot_id"]
        and set(manifest.get("award_ids", [])) == known_ids
        and manifest.get("state") == "ready"
    )
    outputs = []
    for case in cases:
        expected = [by_award_id[i] for i in case["expected_award_ids"] if i in by_award_id]
        missing = [i for i in case["expected_award_ids"] if i not in by_award_id]
        results = []
        for mode in modes:
            started = time.perf_counter()
            if mode == "cognee" and not comparable_cognee:
                results.append({"mode": mode, "status": "unavailable", "error": "A ready Cognee index covering the exact full snapshot is required for comparison.", "elapsed_ms": 0})
                continue
            if missing:
                results.append({"mode": mode, "status": "skipped", "error": "Expected anchor absent from this snapshot.", "elapsed_ms": 0})
                continue
            try:
                if mode == "baseline":
                    raw = baseline.query(case["question"])
                else:
                    raw = await asyncio.wait_for(cognee_adapter.query(case["question"]), timeout=90)
                answer = Answer.model_validate(raw)
                ids = [e.id for e in answer.evidence]
                unique_ids = set(ids)
                valid = sum(i in known_ids for i in ids) / len(ids) if ids else None
                recall = len(unique_ids & set(expected)) / len(expected) if expected else None
                results.append({
                    "mode": mode, "status": "ok", "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    "evidence_ids": ids, "citation_validity": valid, "recall": recall, "precision": None,
                    "matched_count": answer.matched_count, "answer": answer.answer,
                    "abstention_check": len(ids) == 0 if case.get("expect_abstention") else None,
                })
            except cognee_adapter.CogneeUnavailable:
                results.append({"mode": mode, "status": "unavailable", "error": "Cognee is not ready for this snapshot.", "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)})
            except Exception:
                results.append({"mode": mode, "status": "error", "error": "Retrieval failed; inspect configuration or rerun individually.", "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)})
        outputs.append({**case, "expected_ids": expected, "results": results})
    summary = []
    for mode in modes:
        rows = [r for c in outputs for r in c["results"] if r["mode"] == mode and r["status"] == "ok"]
        recalls = [r["recall"] for r in rows if r["recall"] is not None]
        validities = [r["citation_validity"] for r in rows if r["citation_validity"] is not None]
        summary.append({
            "mode": mode, "completed": len(rows), "total": len(cases),
            "mean_elapsed_ms": round(sum(r["elapsed_ms"] for r in rows) / len(rows), 1) if rows else None,
            "citation_validity": sum(validities) / len(validities) if validities else None,
            "mean_recall": sum(recalls) / len(recalls) if recalls else None,
        })
    return {
        "status": "complete", "snapshot_id": metadata["snapshot_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(), "scope_note": case_file["description"],
        "corpus_comparable": comparable_cognee if "cognee" in modes else None,
        "cases": outputs, "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["baseline", "cognee", "both"], default="baseline")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    modes = ["baseline", "cognee"] if args.mode == "both" else [args.mode]
    result = asyncio.run(run(modes, args.limit))
    path = ROOT / "data/evaluation.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(path)
    print(json.dumps({"path": str(path), "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
