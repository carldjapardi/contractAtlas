"""HTTP-boundary tests; SQL locking/RLS still require deployed database checks."""

import json

import httpx
import pytest

from backend.run_store import RunStoreUnavailable, SupabaseRunStore, is_configured

RUN_ID = "a" * 32
OTHER_ID = "b" * 32
KEY = "server-test-key-not-a-real-credential"


def run_document(status="queued", run_id=RUN_ID):
    return {"id": run_id, "status": status, "created_at": "2026-11-17T00:00:00+00:00",
            "updated_at": "2026-11-17T00:00:00+00:00", "question": "A public research question", "events": []}


def store_with(handler, key=KEY):
    return SupabaseRunStore("https://project-test.supabase.co", key,
                            client=httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("url", ["http://project.supabase.co", "https://supabase.co.evil.test",
                                  "https://project.supabase.co.evil.test", "https://localhost",
                                  "https://user:pass@project.supabase.co", "https://project.supabase.co/rest/v1",
                                  "https://project.supabase.co?key=something", "https://project.supabase.co#fragment",
                                  "https://project.supabase.co:8443", "https://nested.project.supabase.co"])
def test_credentials_cannot_be_sent_to_nonofficial_or_ambiguous_urls(url):
    with pytest.raises(RunStoreUnavailable):
        SupabaseRunStore(url, KEY)


def test_exact_host_pin_is_enforced():
    with pytest.raises(RunStoreUnavailable):
        SupabaseRunStore("https://different.supabase.co", KEY, allowed_host="expected.supabase.co")
    SupabaseRunStore("https://expected.supabase.co/", KEY, allowed_host="expected.supabase.co")


def test_publishable_key_is_rejected_and_configuration_is_server_only(monkeypatch):
    with pytest.raises(RunStoreUnavailable):
        SupabaseRunStore("https://project.supabase.co", "sb_publishable_not_privileged")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert not is_configured()
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    assert not is_configured()
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", KEY)
    assert is_configured()


def test_save_round_trip_preserves_document_and_updates_timestamp():
    requests = []
    saved = {}

    def handler(request):
        requests.append(request)
        assert request.headers["apikey"] == KEY
        assert request.headers["authorization"] == "Bearer " + KEY
        if request.method == "POST":
            payload = json.loads(request.content)
            saved.update(payload["document"])
            assert payload["status"] == saved["status"]
            assert payload["id"] == saved["id"]
            assert payload["updated_at"] == saved["updated_at"]
            assert request.url.params["on_conflict"] == "id"
            return httpx.Response(201)
        return httpx.Response(200, json=[{"document": saved}])

    store = store_with(handler)
    run = run_document()
    original = run["updated_at"]
    store.save(run)
    assert run["updated_at"] != original
    assert store.get(RUN_ID) == run
    assert len(requests) == 2


def test_new_secret_key_is_only_an_apikey_not_a_jwt():
    def handler(request):
        assert request.headers["apikey"] == "sb_secret_server_only"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=[])
    assert store_with(handler, key="sb_secret_server_only").active() is False


def test_missing_run_and_invalid_identifiers_are_distinct_from_provider_errors():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[])

    store = store_with(handler)
    with pytest.raises(KeyError):
        store.get("bad-id?or=(id.eq.other)")
    assert not calls
    with pytest.raises(KeyError):
        store.get(RUN_ID)
    assert len(calls) == 1


def test_list_requests_only_ten_latest_runs_and_active_checks_all_persisted_statuses():
    def handler(request):
        assert request.url.params["limit"] in ("10", "1")
        if request.url.params.get("select") == "id":
            assert request.url.params["status"] == "in.(improving,queued,running)"
            return httpx.Response(200, json=[{"id": OTHER_ID}])
        assert request.url.params["order"] == "created_at.desc,id.desc"
        return httpx.Response(200, json=[{"document": run_document(run_id=f"{i:032x}")} for i in range(12)])
    store = store_with(handler)
    assert len(store.list()) == 10
    assert store.active() is True


def test_atomic_create_uses_one_rpc_and_conflict_is_not_replayed():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/rest/v1/rpc/atlas_create_run"
        payload = json.loads(request.content)
        assert payload["p_document"]["id"] == RUN_ID
        assert payload["p_document"]["status"] == "queued"
        return httpx.Response(200, json=False)

    run = run_document()
    previous = dict(run)
    assert store_with(handler).create(run) is False
    assert run == previous
    assert len(calls) == 1


def test_successful_atomic_create_confirms_admission():
    store = store_with(lambda request: httpx.Response(200, json=True))
    run = run_document()
    assert store.create(run) is True
    assert run["updated_at"] != "2026-11-17T00:00:00+00:00"


def test_claim_only_dispatches_when_database_confirms_compare_and_set():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/rest/v1/rpc/atlas_claim_run"
        assert json.loads(request.content) == {"p_run_id": RUN_ID,
            "p_expected_statuses": ["awaiting_review"], "p_next_status": "improving"}
        if len(calls) == 1:
            return httpx.Response(200, json=run_document(status="improving"))
        return httpx.Response(200, content="null")

    store = store_with(handler)
    assert store.claim(RUN_ID, ["awaiting_review"], "improving")["status"] == "improving"
    assert store.claim(RUN_ID, ["awaiting_review"], "improving") is None
    assert len(calls) == 2


def test_claim_rejects_noop_or_malformed_transitions_without_network():
    def handler(request):
        raise AssertionError("No request should be sent")
    store = store_with(handler)
    for expected, following in [(["improving"], "improving"), ([], "improving"),
                                 (["awaiting_review"], "unknown"), ("awaiting_review", "improving")]:
        with pytest.raises(ValueError):
            store.claim(RUN_ID, expected, following)


def test_timeout_on_write_is_sanitized_and_never_retried():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("sensitive provider detail " + KEY, request=request)

    with pytest.raises(RunStoreUnavailable) as error:
        store_with(handler).create(run_document())
    assert KEY not in str(error.value)
    assert len(calls) == 1
    assert "inspect saved state" in str(error.value)


def test_provider_error_body_and_redirect_location_are_not_exposed_or_followed():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://evil.test/?secret=" + KEY},
                              text="sensitive provider detail " + KEY)

    with pytest.raises(RunStoreUnavailable) as error:
        store_with(handler).save(run_document())
    assert KEY not in str(error.value)
    assert "evil.test" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{"id": OTHER_ID, "status": "queued"}, {"id": RUN_ID, "status": "unknown"}, "not-an-object"])
def test_corrupt_or_mismatched_run_documents_fail_closed(payload):
    with pytest.raises(RunStoreUnavailable):
        store_with(lambda request: httpx.Response(200, json=[{"document": payload}])).get(RUN_ID)


def test_manifest_round_trip_is_separate_from_run_documents():
    saved = {}

    def handler(request):
        assert request.url.path == "/rest/v1/atlas_manifests"
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["key"] == "cloud:team-sources"
            saved.update(payload["document"])
            return httpx.Response(201)
        assert request.url.params["key"] == "eq.cloud:team-sources"
        return httpx.Response(200, json=[{"document": saved}] if saved else [])

    store = store_with(handler)
    assert store.get_manifest("cloud:team-sources") is None
    manifest = {"dataset_name": "shared-memory", "state": "ready", "source_count": 28}
    store.save_manifest("cloud:team-sources", manifest)
    assert store.get_manifest("cloud:team-sources") == manifest


def test_nonfinite_json_is_rejected_before_any_http_write():
    def handler(request):
        raise AssertionError("No request should be sent")
    with pytest.raises(RunStoreUnavailable):
        store_with(handler).save_manifest("cloud", {"invalid": float("nan")})
