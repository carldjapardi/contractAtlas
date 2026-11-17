"""Server-only Supabase persistence for durable research jobs and manifests.

The service-role key never crosses the API boundary. HTTP writes are attempted
once: a timeout can mean that a write committed, so callers must inspect state
before deciding whether to dispatch or repeat a workflow operation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from urllib.parse import urlsplit

import httpx

RUN_ID = re.compile(r"^[a-f0-9]{32}$")
MANIFEST_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_./-]{0,199}$")
STATUSES = frozenset({"queued", "running", "awaiting_review", "improving", "complete", "error"})
ACTIVE_STATUSES = frozenset({"queued", "running", "improving"})


class RunStoreUnavailable(RuntimeError):
    """A sanitized configuration, network or database failure."""


def is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL", "").strip() and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise KeyError("Unknown research run")


def _validate_manifest_key(key: str) -> None:
    if not isinstance(key, str) or not MANIFEST_KEY.fullmatch(key):
        raise ValueError("Invalid research memory manifest key")


class SupabaseRunStore:
    """Synchronous PostgREST adapter; inject an httpx client for isolated tests.

    SUPABASE_ALLOWED_HOST may pin the exact official project hostname. Hosted
    URLs must remain HTTPS project hosts under supabase.co; alternate/self-hosted
    endpoints are intentionally unsupported by this deployment adapter.
    """

    def __init__(self, url: str | None = None, service_role_key: str | None = None,
                 *, client: httpx.Client | None = None, allowed_host: str | None = None):
        url = (url if url is not None else os.getenv("SUPABASE_URL", "")).strip()
        key = (service_role_key if service_role_key is not None else os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
        pin = (allowed_host if allowed_host is not None else os.getenv("SUPABASE_ALLOWED_HOST", "")).strip().lower()
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme == "https" and parsed.hostname is not None
                     and re.fullmatch(r"[a-z0-9-]+\.supabase\.co", parsed.hostname) is not None
                     and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
                     and parsed.path in ("", "/") and not parsed.query and not parsed.fragment)
            valid = valid and (not pin or parsed.hostname == pin)
        except ValueError:
            valid = False
        if not valid or not key or key.startswith("sb_publishable_") or "\n" in key or "\r" in key:
            raise RunStoreUnavailable("Configure the official HTTPS Supabase project URL and a server-only service-role key.")
        self._url = url.rstrip("/") + "/rest/v1"
        self._headers = {"apikey": key, "Accept": "application/json", "Content-Type": "application/json"}
        # New sb_secret keys are API keys, not JWTs. Legacy service_role JWTs
        # also need their Authorization header; neither is sent to the browser.
        if not key.startswith("sb_secret_"):
            self._headers["Authorization"] = "Bearer " + key
        self._client = client

    def _request(self, method: str, path: str, *, params: dict | None = None,
                 payload: dict | None = None, prefer: str | None = None):
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            # Validate JSON locally rather than letting NaN or unserializable
            # objects create ambiguous provider-side persistence failures.
            body = None if payload is None else json.dumps(payload, allow_nan=False)
            if self._client is None:
                with httpx.Client(timeout=20, follow_redirects=False) as client:
                    response = client.request(method, self._url + path, params=params,
                                              headers=headers, content=body, follow_redirects=False)
            else:
                response = self._client.request(method, self._url + path, params=params,
                                                headers=headers, content=body, follow_redirects=False)
        except (httpx.HTTPError, ValueError, TypeError):
            raise RunStoreUnavailable("Research storage is unavailable. Check configuration and inspect saved state before retrying a write.") from None
        if response.status_code >= 300:
            # Provider bodies/URLs can contain submitted research or credentials.
            raise RunStoreUnavailable("Research storage could not complete this operation. Check server configuration and database migration.") from None
        if not response.content:
            return None
        try:
            return response.json()
        except (ValueError, UnicodeError):
            raise RunStoreUnavailable("Research storage returned an invalid response. Inspect saved state before retrying a write.") from None

    @staticmethod
    def _document(value, *, run_id: str | None = None) -> dict:
        if not isinstance(value, dict) or not RUN_ID.fullmatch(str(value.get("id", ""))) or value.get("status") not in STATUSES:
            raise RunStoreUnavailable("Research storage returned an invalid run document.")
        if run_id is not None and value["id"] != run_id:
            raise RunStoreUnavailable("Research storage returned a mismatched run document.")
        return value

    def save(self, run: dict) -> None:
        _validate_id(run.get("id"))
        if run.get("status") not in STATUSES:
            raise ValueError("Invalid research run status")
        timestamp = _now()
        document = dict(run)
        document["updated_at"] = timestamp
        document.setdefault("created_at", timestamp)
        self._request("POST", "/atlas_runs", params={"on_conflict": "id"},
                      payload={"id": document["id"], "status": document["status"],
                               "created_at": document["created_at"], "updated_at": timestamp, "document": document},
                      prefer="resolution=merge-duplicates,return=minimal")
        run["updated_at"] = timestamp
        run.setdefault("created_at", document["created_at"])

    def create(self, run: dict) -> bool:
        """Admit a queued run only when no shared-memory operation is active.

        Database transaction locking coordinates independent serverless workers;
        active() followed by save() is not a safe admission sequence.
        """
        _validate_id(run.get("id"))
        if run.get("status") != "queued":
            raise ValueError("New research runs must be queued")
        document = dict(run)
        timestamp = _now()
        document["updated_at"] = timestamp
        document.setdefault("created_at", timestamp)
        admitted = self._request("POST", "/rpc/atlas_create_run", payload={"p_document": document})
        if not isinstance(admitted, bool):
            raise RunStoreUnavailable("Research storage did not confirm run admission. Inspect saved state before retrying.")
        if admitted:
            run["updated_at"] = timestamp
            run.setdefault("created_at", document["created_at"])
        return admitted

    def get(self, run_id: str) -> dict:
        _validate_id(run_id)
        rows = self._request("GET", "/atlas_runs", params={"id": "eq." + run_id, "select": "document", "limit": 1})
        if not isinstance(rows, list):
            raise RunStoreUnavailable("Research storage returned an invalid run response.")
        if not rows:
            raise KeyError("Unknown research run")
        if not isinstance(rows[0], dict):
            raise RunStoreUnavailable("Research storage returned an invalid run response.")
        return self._document(rows[0].get("document"), run_id=run_id)

    def list(self) -> list[dict]:
        rows = self._request("GET", "/atlas_runs", params={"select": "document", "order": "created_at.desc,id.desc", "limit": 10})
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RunStoreUnavailable("Research storage returned an invalid run list.")
        return [self._document(row.get("document")) for row in rows[:10]]

    def claim(self, run_id: str, expected_statuses, next_status: str) -> dict | None:
        """Atomically change status; None means absent or another worker won.

        A network failure is ambiguous and raises rather than blindly dispatching
        a second workflow. Call get() to inspect the saved state before retrying.
        """
        _validate_id(run_id)
        if isinstance(expected_statuses, str):
            raise ValueError("Expected statuses must be a nonempty collection")
        expected = sorted(set(expected_statuses))
        if not expected or any(status not in STATUSES for status in expected) or next_status not in STATUSES:
            raise ValueError("Invalid research run transition")
        if next_status in expected:
            raise ValueError("A claim must change status to prevent duplicate dispatch")
        document = self._request("POST", "/rpc/atlas_claim_run", payload={
            "p_run_id": run_id, "p_expected_statuses": expected, "p_next_status": next_status})
        if document is None:
            return None
        result = self._document(document, run_id=run_id)
        if result["status"] != next_status:
            raise RunStoreUnavailable("Research storage did not confirm the requested run transition.")
        return result

    def active(self) -> bool:
        rows = self._request("GET", "/atlas_runs", params={"select": "id", "status": "in.(improving,queued,running)", "limit": 1})
        if not isinstance(rows, list):
            raise RunStoreUnavailable("Research storage returned an invalid activity response.")
        return bool(rows)

    def get_manifest(self, key: str) -> dict | None:
        _validate_manifest_key(key)
        rows = self._request("GET", "/atlas_manifests", params={"key": "eq." + key, "select": "document", "limit": 1})
        if not isinstance(rows, list):
            raise RunStoreUnavailable("Research storage returned an invalid memory manifest response.")
        if not rows:
            return None
        if not isinstance(rows[0], dict) or not isinstance(rows[0].get("document"), dict):
            raise RunStoreUnavailable("Research storage returned an invalid memory manifest document.")
        return rows[0]["document"]

    def save_manifest(self, key: str, payload: dict) -> None:
        _validate_manifest_key(key)
        if not isinstance(payload, dict):
            raise ValueError("Memory manifest must be a JSON object")
        self._request("POST", "/atlas_manifests", params={"on_conflict": "key"},
                      payload={"key": key, "document": payload, "updated_at": _now()},
                      prefer="resolution=merge-duplicates,return=minimal")
