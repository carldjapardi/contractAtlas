"""Fetch a capped, reproducible DHS contract snapshot from the public USAspending API."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.usaspending.gov/api/v2"
FIELDS = ["Award ID", "Recipient Name", "recipient_id", "Recipient UEI", "Description",
          "Award Amount", "Awarding Agency", "Awarding Sub Agency", "Start Date", "End Date", "generated_internal_id"]


def request_json(client: httpx.Client, method: str, url: str, **kwargs) -> dict:
    for attempt in range(4):
        try:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError):
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def normalize(row: dict, detail: dict | None = None) -> dict:
    stable_id = row.get("generated_internal_id")
    if not stable_id:
        raise ValueError("Missing generated_internal_id; refusing ambiguous award identity")
    uei = row.get("Recipient UEI")
    recipient_id = uei or row.get("recipient_id")
    if not recipient_id:
        # Preserve unknown entities separately rather than merging by company name.
        recipient_id = "unknown:" + stable_id
    recipient = (detail or {}).get("recipient") or {}
    return {"id": stable_id, "award_id": row["Award ID"],
            "description": row.get("Description") or "", "agency": row.get("Awarding Agency") or "Unknown agency",
            "sub_agency": row.get("Awarding Sub Agency"), "recipient_id": recipient_id,
            "recipient_name": row.get("Recipient Name") or "Unknown recipient", "recipient_uei": uei,
            "parent_uei": recipient.get("parent_recipient_uei"), "parent_name": recipient.get("parent_recipient_name"),
            "obligation": float(Decimal(str(row.get("Award Amount") or 0))),
            "start_date": row.get("Start Date"), "end_date": row.get("End Date"),
            "source_url": "https://www.usaspending.gov/award/" + quote(stable_id, safe="_-")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--fiscal-year", type=int, default=2025)
    parser.add_argument("--keyword", default="cyber")
    parser.add_argument("--skip-details", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 500:
        parser.error("--limit must be between 1 and 500")
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    filters = {"award_type_codes": ["A", "B", "C", "D"],
               "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Homeland Security"}],
               "time_period": [{"start_date": f"{args.fiscal_year - 1}-10-01", "end_date": f"{args.fiscal_year}-09-30"}],
               "keywords": [args.keyword]}
    rows: dict[str, dict] = {}
    requests = []
    page, has_next = 1, True
    page_size = min(100, args.limit)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        while has_next and len(rows) < args.limit:
            # Page size must remain constant: changing it changes page offsets.
            payload = {"filters": filters, "fields": FIELDS, "limit": page_size,
                       "page": page, "sort": "Award Amount", "order": "desc"}
            result = request_json(client, "POST", API + "/search/spending_by_award/", json=payload)
            requests.append(payload)
            (raw_dir / f"search-page-{page}.json").write_text(json.dumps(result, indent=2))
            before = len(rows)
            for row in result.get("results", []):
                rows[row["generated_internal_id"]] = row
            has_next = result.get("page_metadata", {}).get("hasNext", False)
            if len(rows) > args.limit:
                rows = dict(list(rows.items())[:args.limit])
                has_next = True
            if len(rows) == before:
                break
            page += 1
        details, detail_errors = {}, []
        if not args.skip_details:
            def fetch_detail(stable_id):
                path = raw_dir / ("detail-" + hashlib.sha256(stable_id.encode()).hexdigest()[:20] + ".json")
                result = request_json(client, "GET", API + "/awards/" + quote(stable_id, safe="_-") + "/")
                path.write_text(json.dumps(result, indent=2))
                return stable_id, result
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(fetch_detail, aid): aid for aid in rows}
                for future in as_completed(futures):
                    try:
                        aid, detail = future.result()
                        details[aid] = detail
                    except Exception:
                        detail_errors.append(futures[future])
    awards = [normalize(row, details.get(aid)) for aid, row in rows.items()]
    awards.sort(key=lambda a: (-a["obligation"], a["id"]))
    digest = hashlib.sha256(json.dumps(awards, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    metadata = {"name": f"DHS FY{args.fiscal_year} {args.keyword} keyword slice", "status": "live_snapshot" if awards else "empty",
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "fiscal_year": args.fiscal_year,
        "agency": "Department of Homeland Security", "keywords": [args.keyword], "award_count": len(awards),
        "recipient_count": len({a["recipient_id"] for a in awards}),
        "total_obligation": float(sum((Decimal(str(a["obligation"])) for a in awards), Decimal("0"))),
        "snapshot_id": digest, "truncated": has_next,
        "notes": [f"Keyword search '{args.keyword}' over DHS contracts with activity in FY{args.fiscal_year}; matches may occur in descriptions, recipients or agency fields. This is not a cybersecurity classification or comprehensive cybersecurity dataset.",
                  "Amounts are award-summary lifetime obligations, not fiscal-year-only spending, cash paid, or contract ceilings.",
                  f"Source search capped at {args.limit} awards; sorted by Award Amount descending.",
                  f"Reported parent fields retrieved from {len(details)} award detail records; {len(detail_errors)} detail requests failed.",
                  "Missing parent information is unknown. No parent relationships are inferred from names.",
                  "No transaction history or subaward records are included."],
        "source_api": API + "/search/spending_by_award/", "filters": filters,
        "detail_failure_ids": detail_errors}
    snapshot = {"metadata": metadata, "awards": awards}
    path = ROOT / "data" / "snapshot.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2))
    temporary.replace(path)
    (raw_dir / "requests.json").write_text(json.dumps(requests, indent=2))
    print(json.dumps({"awards": len(awards), "recipients": metadata["recipient_count"],
                      "detail_records": len(details), "truncated": has_next, "snapshot_id": digest}))


if __name__ == "__main__":
    main()
