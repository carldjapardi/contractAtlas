"""Transparent structured traversal + lexical retrieval, with no model calls."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from decimal import Decimal

from backend.data import build_graph, load_snapshot, to_evidence

STOP_WORDS = set("a an all the this that these those which what who whom whose where when how why is are was were be been being do does did can could would should will has have had it its their they them we our i me my you your and or of to for from in on at by with as across between through about related relate relating provide providers providing services service work working received receive receiving awarded award awards contract contracts company companies contractor contractors recipients recipient dataset snapshot dhs department homeland security federal government show list find tell explain please much total amount money funding obligations obligation similar using different terminology describe describes descriptions description".split())
UNSUPPORTED = re.compile(r"\b(fraud|fraudulent|corrupt|corruption|waste|wasteful|successful|success|effectiveness|effective|prevent\w*|reduce\w*|outcomes?|impact|cash|payments?|outlays?|profit|profits|employees|political|donations?|lobbying|beneficial owners?|shareholders?)\b", re.I)
LEGAL_SUFFIXES = set("inc incorporated llc corporation corp co company limited ltd lp llp".split())


def _terms(question: str) -> list[str]:
    terms = {t for t in re.findall(r"[a-z0-9]+", question.casefold()) if t not in STOP_WORDS and len(t) > 1}
    # Generic contract words swamp useful topic terms; retain them for single-word searches.
    specific = terms - {"management", "support", "systems", "technology", "technologies", "engineering", "technical"}
    return sorted(specific or terms)


def _entity_matches(question: str, awards: list[dict]) -> list[dict]:
    """Prefer explicit source identifiers or recognizable recipient-name tokens."""
    q = question.casefold()
    identifiers = [a for a in awards if any(value and re.search(r"(?<!\w)" + re.escape(value.casefold()) + r"(?!\w)", q)
                   for value in (a["award_id"], a.get("recipient_uei"), a["id"]))]
    if identifiers:
        return identifiers
    normalized_question = " " + " ".join(re.findall(r"[a-z0-9]+", q)) + " "
    recipient_ids = set()
    for a in awards:
        words = re.findall(r"[a-z0-9]+", a["recipient_name"].casefold())
        while words and words[-1] in LEGAL_SUFFIXES:
            words.pop()
        # Require the complete normalized name, not a rare topic word appearing
        # somewhere in a company name. Legal suffixes may be omitted by users.
        name = " ".join(words)
        if name and f" {name} " in normalized_question:
            recipient_ids.add(a["recipient_id"])
    return [a for a in awards if a["recipient_id"] in recipient_ids]


def retrieve(question: str, awards: list[dict]) -> list[dict]:
    """Deterministic token overlap; no semantic or synonym expansion."""
    explicit = _entity_matches(question, awards)
    if explicit:
        return sorted(explicit, key=lambda a: (-a["obligation"], a["id"]))
    terms = _terms(question)
    if not terms:
        return sorted(awards, key=lambda a: (-a["obligation"], a["id"]))
    ranked = []
    for a in awards:
        identity = " ".join(str(a.get(k) or "") for k in ("recipient_name", "recipient_uei", "award_id", "parent_name")).casefold()
        text = " ".join(str(a.get(k) or "") for k in ("description", "sub_agency")).casefold()
        identity_tokens = set(re.findall(r"[a-z0-9]+", identity))
        description_tokens = set(re.findall(r"[a-z0-9]+", text))
        score = sum(4 * (t in identity_tokens) + (t in description_tokens) for t in terms)
        if score:
            ranked.append((score, a))
    return [a for _, a in sorted(ranked, key=lambda item: (-item[0], -item[1]["obligation"], item[1]["id"]))]


def query(question: str) -> dict:
    started = time.perf_counter()
    snapshot = load_snapshot()
    awards = snapshot["awards"]
    metadata = snapshot["metadata"]
    notes = ["Baseline uses reported relationships and lexical token matching; it performs no semantic inference.",
             "Amounts are award-summary obligations over each award's lifetime, not FY2025-only spending or cash payments.",
             "Results describe this sampled snapshot, not all federal cybersecurity contracting."]
    if metadata.get("truncated"):
        notes.append("The source search was capped; some matching awards are outside this snapshot.")
    selected: list[dict] = []
    q = question.casefold()
    answer = ""
    if not awards:
        answer = "No real award snapshot is loaded yet. Run the ingestion command before querying."
    elif UNSUPPORTED.search(question):
        answer = "These award records cannot establish that. This snapshot contains contract descriptions, reported recipients and award-summary obligations; it does not establish payments, wrongdoing, ownership beyond reported parents, or project outcomes."
    elif any(term in q for term in ("multiple agencies", "across agencies", "cross-agency", "other agencies", "all agencies")):
        answer = "This snapshot covers only Department of Homeland Security awards, so it cannot establish cross-agency vendor relationships or government-wide totals. Explore a recipient's DHS awards or expand the source dataset first."
    elif any(term in q for term in ("cannot", "limitations", "missing", "not establish")):
        answer = "This snapshot cannot establish project outcomes, cash payments, wrongdoing, a complete ownership structure, or market-wide coverage. It contains a capped DHS keyword search and reported award relationships. Missing parent fields mean unknown, not no parent."
    elif "parent" in q or "subsidiar" in q or "corporate famil" in q:
        entity_awards = _entity_matches(question, awards)
        wants_siblings = any(term in q for term in ("share", "sibling", "subsidiar", "corporate famil"))
        parent_scope = {a["parent_uei"] for a in entity_awards if a.get("parent_uei")}
        if entity_awards and not wants_siblings:
            representatives = {(a["recipient_id"], a.get("parent_uei")): a for a in entity_awards}
            selected = list(representatives.values())
            lines = [f"[{i}] {a['recipient_name']} (UEI {a.get('recipient_uei') or 'unavailable'}): " + (f"reported ultimate parent {a.get('parent_name') or a['parent_uei']} (UEI {a['parent_uei']})." if a.get('parent_uei') else "no reported parent available; the relationship is unknown.") for i, a in enumerate(selected, 1)]
            answer = "\n\n".join(lines)
        elif entity_awards and not parent_scope:
            answer = "The selected recipient has no reported parent identifier in this snapshot, so shared-parent relationships cannot be established."
        groups: dict[str, list[dict]] = defaultdict(list)
        for a in awards:
            if a.get("parent_uei") and (not entity_awards or a["parent_uei"] in parent_scope):
                groups[a["parent_uei"]].append(a)
        shared = [(uei, rows) for uei, rows in groups.items() if len({a["recipient_id"] for a in rows}) > 1]
        shared.sort(key=lambda item: (-len({a["recipient_id"] for a in item[1]}), item[0]))
        if not answer and shared:
            lines = []
            for uei, rows in shared[:4]:
                names = sorted({f"{a['recipient_name']} (UEI {a.get('recipient_uei') or 'unavailable'})" for a in rows})
                first = len(selected) + 1
                # Keep evidence from each distinct recipient, not only biggest awards.
                representatives = {a["recipient_id"]: a for a in sorted(rows, key=lambda a: a["obligation"])}
                selected.extend(representatives.values())
                refs = ", ".join(f"[{i}]" for i in range(first, len(selected) + 1))
                lines.append(f"{rows[0].get('parent_name') or uei}: {'; '.join(names)} ({refs}).")
            answer = "Reported ultimate-parent links connect distinct recipients in this snapshot:\n\n" + "\n\n".join(lines)
            notes.append("Ultimate-parent reporting is not a complete or independently verified corporate ownership tree.")
        elif not answer:
            answer = "No shared reported parent across distinct recipients was found in this snapshot. That does not establish that no such relationship exists."
    else:
        matches = retrieve(question, awards)
        selected = matches[:8]
        if not matches:
            answer = "No lexical matches were found in this snapshot. Try a specific recipient, award ID, or wording from an award description. This does not establish that relevant contracts do not exist."
        else:
            count = len(matches)
            recipients = len({a["recipient_id"] for a in matches})
            amount = sum((Decimal(str(a["obligation"])) for a in matches), Decimal("0"))
            answer = f"Found {count} matching award{'s' if count != 1 else ''} across {recipients} reported recipient{'s' if recipients != 1 else ''} in this snapshot. Their combined award-summary obligations are ${amount:,.2f} over the awards' lifetimes."
            lines = [f"[{i}] {a['recipient_name']} — {a['award_id']}: {a['description'] or 'No description reported.'}" for i, a in enumerate(selected, 1)]
            answer += "\n\n" + "\n\n".join(lines)
            if len(matches) > len(selected):
                notes.append(f"Showing evidence for the first {len(selected)} of {len(matches)} lexical matches.")
    return {"answer": answer, "evidence": [to_evidence(a) for a in selected],
            "graph": build_graph(selected, limit=max(12, len(selected))), "mode": "baseline",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "coverage_notes": notes, "matched_count": len(matches) if 'matches' in locals() else len(selected)}
