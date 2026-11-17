import json

import pytest

from scripts import compare_expansion as comparison


def test_inventory_fingerprint_tracks_content_and_ignores_api_order(monkeypatch):
    rows = [{"id": "b", "name": "B", "contentHash": "one"}, {"id": "a", "name": "A", "contentHash": "two"}]

    async def request(*args, **kwargs):
        return rows

    monkeypatch.setattr(comparison.cloud, "request", request)
    import asyncio
    first = asyncio.run(comparison.inventory({"dataset_id": "test"}))
    rows.reverse()
    assert asyncio.run(comparison.inventory({"dataset_id": "test"})) == first
    rows[0]["contentHash"] = "changed"
    assert asyncio.run(comparison.inventory({"dataset_id": "test"}))["fingerprint"] != first["fingerprint"]


def test_blinded_review_excludes_method_phase_and_session(monkeypatch, tmp_path):
    monkeypatch.setattr(comparison, "RUNTIME", tmp_path)
    for phase in ("before", "after"):
        comparison.save(tmp_path / f"{phase}.json", {"inventory_unchanged": True, "answers": [
            {"method": "rag", "phase": phase, "case_id": "case", "question": "Question", "answer": "Answer", "source_ids": [], "status": "ok", "session_id": "private-session"}
        ]})
    comparison.blind()
    public = json.loads((tmp_path / "blind_answers.json").read_text())
    assert all(not ({"method", "phase", "session_id"} & row.keys()) for row in public)
    assert len(json.loads((tmp_path / "blind_key.json").read_text())) == 2


def test_resume_refuses_changed_inventory(monkeypatch, tmp_path):
    monkeypatch.setattr(comparison, "RUNTIME", tmp_path)
    comparison.save(tmp_path / "before.json", {"inventory": {"fingerprint": "original"}, "answers": []})

    async def inventory(*args):
        return {"fingerprint": "changed"}

    monkeypatch.setattr(comparison, "inventory", inventory)
    import asyncio
    with pytest.raises(RuntimeError, match="inventory changed"):
        asyncio.run(comparison.measure("before", {}))
