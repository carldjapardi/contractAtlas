"""Build a Cognee index over the frozen snapshot, optionally smoke-test it.

Run: uv run --extra cognee python -m scripts.index_cognee --limit 3 --smoke
Then index the full snapshot without --limit for fair baseline comparisons.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.cognee_adapter import CogneeUnavailable, index_snapshot, query


async def run(limit: int | None, smoke: bool) -> None:
    manifest = await index_snapshot(limit)
    print(json.dumps({
        "status": "indexed",
        "snapshot_id": manifest["snapshot_id"],
        "award_count": len(manifest["award_ids"]),
        "ingestion_ms": manifest["ingestion_ms"],
    }, indent=2))
    if smoke:
        result = await query("Which recipients have cybersecurity-related contract awards?")
        print(json.dumps({
            "status": "smoke_complete",
            "source_verified_records": result["matched_count"],
            "query_ms": result["elapsed_ms"],
            "coverage_notes": result["coverage_notes"],
        }, indent=2))
        if not result["evidence"]:
            raise CogneeUnavailable("Indexing completed, but retrieval returned no verifiable evidence. Inspect source mapping before treating the integration as validated.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Index only N awards for a clearly marked smoke-test subset")
    parser.add_argument("--smoke", action="store_true", help="Run one real retrieval and verify source mapping")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.limit, args.smoke))
    except CogneeUnavailable as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
