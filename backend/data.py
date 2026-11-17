"""Read-only access to the frozen USAspending snapshot and its reported graph."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "snapshot.json"


def load_snapshot() -> dict:
    path = Path(os.environ.get("ATLAS_SNAPSHOT_PATH", SNAPSHOT_PATH))
    if not path.exists():
        return {"metadata": {"name": "DHS FY2025 cyber keyword slice", "status": "empty",
                "retrieved_at": None, "fiscal_year": 2025,
                "agency": "Department of Homeland Security", "keywords": ["cyber"],
                "award_count": 0, "recipient_count": 0, "total_obligation": 0,
                "snapshot_id": "empty", "truncated": False,
                "notes": ["No snapshot loaded. Run python -m scripts.ingest."]}, "awards": []}
    return json.loads(path.read_text())


def get_metadata() -> dict:
    return load_snapshot()["metadata"]


def get_awards(search: str = "", recipient_id: str | None = None, limit: int = 50) -> dict:
    awards = load_snapshot()["awards"]
    if recipient_id:
        awards = [a for a in awards if a["recipient_id"] == recipient_id]
    if search.strip():
        terms = search.casefold().split()
        awards = [a for a in awards if all(term in " ".join(str(a.get(k) or "") for k in
                   ("description", "recipient_name", "recipient_uei", "award_id", "parent_name", "sub_agency")).casefold()
                   for term in terms)]
    awards = sorted(awards, key=lambda a: (-a["obligation"], a["id"]))
    return {"awards": awards[:max(0, min(limit, 500))], "total": len(awards)}


def build_graph(awards: list[dict], limit: int = 12) -> dict:
    """Limit awards, not entities; the reported edge evidence is always retained."""
    unique = {a["id"]: a for a in awards}
    selected = sorted(unique.values(), key=lambda a: (-a["obligation"], a["id"]))[:max(0, min(limit, 100))]
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    selected_recipients = {a["recipient_uei"]: a for a in selected if a.get("recipient_uei")}
    canonical_recipient_ids = {uei: "recipient:" + a["recipient_id"] for uei, a in selected_recipients.items()}

    def node(node_id: str, kind: str, label: str, sublabel: str, award_id: str):
        item = nodes.setdefault(node_id, {"id": node_id, "type": kind, "label": label,
                                          "sublabel": sublabel, "award_ids": []})
        if award_id not in item["award_ids"]:
            item["award_ids"].append(award_id)

    def edge(source: str, target: str, relation: str, award_id: str):
        key = (source, target, relation)
        item = edges.setdefault(key, {"id": "edge:" + hashlib.sha256("|".join(key).encode()).hexdigest()[:16],
            "source": source, "target": target, "relationship": relation,
            "origin": "reported", "award_ids": []})
        if award_id not in item["award_ids"]:
            item["award_ids"].append(award_id)

    for a in selected:
        aid = a["id"]
        agency_id = "agency:" + hashlib.sha256(a["agency"].encode()).hexdigest()[:12]
        recipient_id = canonical_recipient_ids.get(a.get("recipient_uei"), "recipient:" + a["recipient_id"])
        node(agency_id, "agency", a["agency"], "Awarding agency", aid)
        node(aid, "award", a["award_id"], a.get("description", "")[:100], aid)
        node(recipient_id, "recipient", a["recipient_name"], a.get("recipient_uei") or "UEI unavailable", aid)
        edge(agency_id, aid, "awarded", aid)
        edge(aid, recipient_id, "awarded to", aid)
        # Names alone never establish a shared corporate parent.
        if a.get("parent_uei") and a["parent_uei"] != a.get("recipient_uei"):
            parent_recipient = selected_recipients.get(a["parent_uei"])
            pid = canonical_recipient_ids.get(a["parent_uei"], "parent:" + a["parent_uei"])
            if parent_recipient:
                node(pid, "recipient", parent_recipient["recipient_name"], a["parent_uei"], aid)
                nodes[pid]["sublabel"] = a["parent_uei"] + " · Also a reported ultimate parent"
            else:
                node(pid, "parent", a.get("parent_name") or a["parent_uei"], "Reported ultimate parent", aid)
            edge(pid, recipient_id, "reported parent of", aid)
    return {"nodes": list(nodes.values()), "edges": list(edges.values()), "truncated": len(unique) > len(selected)}


def to_evidence(award: dict) -> dict:
    return {"id": award["id"], "title": f"{award['recipient_name']} · {award['award_id']}",
            **{key: award[key] for key in ("description", "source_url", "obligation", "agency", "recipient_name")}}
