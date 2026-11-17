"""Copy verified Cognee manifest and completed demo to server-only Supabase storage."""
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    from backend.run_store import SupabaseRunStore
    from backend.team_memory import _source_fingerprint, _sources
    manifest = json.loads((ROOT / "data/team/cloud_index.json").read_text())
    if manifest.get("state") != "ready" or manifest.get("source_fingerprint") != _source_fingerprint(_sources()):
        raise SystemExit("The verified Cloud manifest does not match the app's source collection.")
    store = SupabaseRunStore()
    if store.active():
        raise SystemExit("A hosted operation is active; do not replace its state.")
    store.save_manifest("cognee_cloud", manifest)
    demo = json.loads((ROOT / "data/team/runs/06b99bc85757443783635c11f3f81265.json").read_text())
    if demo.get("status") != "complete" or not demo.get("improvement", {}).get("learning_verified"):
        raise SystemExit("The selected demo is not a verified completed checkpoint.")
    try:
        existing = store.get(demo["id"])
    except KeyError:
        existing = None
    if existing is None:
        store.save(demo)
    print("Hosted manifest ready; verified completed demo available. No Cognee ingestion or improvement was repeated.")


if __name__ == "__main__":
    main()
