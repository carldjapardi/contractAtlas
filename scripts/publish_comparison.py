"""Validate anonymous checklist reviews and publish the observed comparison."""
from datetime import datetime, timezone
import json
from statistics import mean

from scripts.compare_expansion import BUNDLE, RUNTIME, METHODS, digest, save


def publish():
    rubric = json.loads((BUNDLE / "comparison_rubric.json").read_text())
    reviews = json.loads((RUNTIME / "blind_scores.json").read_text())["answers"]
    key = json.loads((RUNTIME / "blind_key.json").read_text())
    if len(reviews) != 16 or {row["label"] for row in reviews} != set(key):
        raise ValueError("All sixteen unique anonymous reviews are required.")
    originals = {}
    inventories = {}
    for phase in ("before", "after"):
        batch = json.loads((RUNTIME / f"{phase}.json").read_text())
        if not batch.get("inventory_unchanged"):
            raise ValueError("Inventory changed during a batch.")
        inventories[phase] = batch["inventory"]
        for row in batch["answers"]:
            originals[(phase, row["method"], row["case_id"])] = row
    if len(originals) != 16:
        raise ValueError("Expected sixteen original answers.")
    answers = []
    for review in reviews:
        identity = key[review["label"]]
        original = originals[(identity["phase"], identity["method"], identity["case_id"])]
        expected = {check["id"] for check in rubric["cases"][identity["case_id"]]}
        checks = review["checks"]
        if review["case_id"] != identity["case_id"] or len(checks) != 6 or {check["id"] for check in checks} != expected:
            raise ValueError("Review does not match the frozen rubric.")
        if any(type(check["pass"]) is not bool or not check.get("evidence") for check in checks):
            raise ValueError("Each binary decision needs a review explanation.")
        raw_path = RUNTIME / "raw" / f"{identity['phase']}-{identity['case_id']}-{identity['method']}.json"
        raw = json.loads(raw_path.read_text())
        observed_type = next(entry for entry in raw if entry.get("source") == "graph").get("search_type")
        if observed_type != METHODS[identity["method"]]:
            raise ValueError("Actual returned retrieval method differs from requested method.")
        answers.append({**{k: original[k] for k in ("question", "answer", "source_ids", "uncertainties", "elapsed_ms", "prompt_hash")},
                        **identity, "anonymous_label": review["label"], "observed_search_type": observed_type,
                        "passed": sum(check["pass"] for check in checks), "total": 6, "checks": checks,
                        "critical_errors": review["critical_errors"], "citation_review": review["citation_review"],
                        "review_notes": review["notes"] + [review["citation_review"]]})
    for case_id in rubric["cases"]:
        if len({row["prompt_hash"] for row in answers if row["case_id"] == case_id}) != 1:
            raise ValueError("Prompts differed between conditions.")
    answers.sort(key=lambda row: (row["phase"] != "before", row["method"], row["case_id"]))
    summary = []
    for phase in ("before", "after"):
        for method in METHODS:
            rows = [row for row in answers if row["phase"] == phase and row["method"] == method]
            summary.append({"phase": phase, "method": method, "passed": sum(row["passed"] for row in rows),
                            "total": 24, "critical_errors": sum(len(row["critical_errors"]) for row in rows),
                            "mean_elapsed_ms": round(mean(row["elapsed_ms"] for row in rows), 1)})
    intervention = json.loads((RUNTIME / "improvement.json").read_text())
    native = intervention["native_result"]
    if native.get("status") != "completed":
        raise ValueError("Native improvement did not complete.")
    for phase in ("before", "after"):
        if intervention[f"{phase}_inventory"]["fingerprint"] != inventories[phase]["fingerprint"]:
            raise ValueError("Measured document inventory differs from the intervention boundary.")
    lessons = json.loads((RUNTIME / "lesson_evidence.json").read_text())
    result = {"status": "complete", "generated_at": datetime.now(timezone.utc).isoformat(),
              "headline": "Memory persisted; checklist scores stayed flat." if all(summary[i]["passed"] == summary[i + 2]["passed"] for i in (0, 1)) else "Observed results from the frozen memory experiment",
              "source_count": inventories["before"]["count"], "question_count": 4,
              "review_type": "Assistant-reviewed checklist, anonymous method/phase labels; not independent human evaluation.",
              "summary": summary, "answers": answers,
              "inventory": {phase: {k: value[k] for k in ("count", "fingerprint")} for phase, value in inventories.items()},
              "protocol_sha256": digest((BUNDLE / "comparison_protocol.md").read_text()),
              "rubric_sha256": digest(rubric),
              "improvement": {"native_status": native["status"], "stages": [{"stage": s.get("stage", s.get("name")), "status": s["status"], "counts": s["counts"]} for s in native["stages"]],
                              "completed_stages": [stage.get("stage", stage.get("name")) for stage in native["stages"] if stage["status"] == "completed"],
                              "new_documents": inventories["after"]["count"] - inventories["before"]["count"],
                              "freshly_retrieved_lessons": len(lessons["lessons"]), "lesson_excerpts": lessons["lessons"]},
              "limitations": ["Four repeated questions, one run and assistant-reviewed checks; no statistical or general accuracy claim.",
                              "Both methods use the same Cloud tenant configuration and the same documents within each phase; model version and temperature are not exposed in these responses.",
                              "Requested topK=10 and prompts match; internal retrieval context and token budgets differ. Document fingerprints do not prove complete graph/index immutability.",
                              "After combines new accepted synthetic feedback and native improvement; it does not isolate consolidation from adding information.",
                              "Citation entailment is reviewed separately from checklist coverage. Missing evidence is not a false assertion."]}
    save(BUNDLE / "comparison_results.json", result)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    publish()
