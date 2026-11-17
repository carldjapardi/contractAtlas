"""Seed isolated local shared memory: uv run --extra cognee python -m scripts.seed_team_memory."""
import asyncio
import json
import sys

from backend.team_memory import TeamMemoryUnavailable, seed_memory


async def main():
    async def emit(event):
        print(json.dumps(event), flush=True)
    result = await seed_memory(emit)
    print(json.dumps({key: result[key] for key in ("state", "runtime_mode", "dataset_name", "source_count")}), flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TeamMemoryUnavailable as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
