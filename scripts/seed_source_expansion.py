"""Explicitly seed the approved expansion in Cloud without replacing the active dataset.

Uses the configured account and credits; does not execute research or improve().
"""
import asyncio
import json

from backend import team_cloud, team_memory


async def main():
    bundle = team_memory.ROOT / "data/expansion"
    source_path = bundle / "team_sources.expanded.json"
    if not source_path.exists():
        raise SystemExit("Build the source expansion first.")
    # Overrides are process-local, not persistent application configuration.
    team_memory.SOURCE_PATH = source_path
    team_cloud.MANIFEST = bundle / "runtime/cloud_index.json"

    async def emit(event):
        print(json.dumps(event), flush=True)

    result = await team_cloud.seed_memory(emit)
    print(json.dumps({k: result[k] for k in ("state", "runtime_mode", "dataset_name", "source_count")}), flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except team_memory.TeamMemoryUnavailable as exc:
        raise SystemExit(str(exc)) from None
