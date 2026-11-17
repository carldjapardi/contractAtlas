import json
from pathlib import Path
import subprocess

import pytest

from scripts import collect_team_sources as collector

ROOT = Path(__file__).resolve().parents[1]


def test_live_corpus_has_three_source_types_and_traceable_award_fields():
    corpus = json.loads((ROOT / "data/team_sources.json").read_text())
    snapshot = json.loads((ROOT / "data/snapshot.json").read_text())
    collector.validate_sources(corpus["sources"])
    assert corpus["version"] == 1
    assert len(corpus["sources"]) == 28
    records = {a["source_url"]: a for a in snapshot["awards"]}
    for source in corpus["sources"]:
        if source["kind"] == "award":
            award = records[source["url"]]
            assert source["text"].endswith(award["description"])
            assert award["id"] in source["text"]
            assert source["retrieved_at"] == snapshot["metadata"]["retrieved_at"]
            assert "not an open solicitation" in " ".join(source["notes"])
        elif source["kind"] == "company_capability":
            assert "Self-reported" in " ".join(source["notes"])
            assert len(source["text"].split()) <= 185
        elif source["kind"] == "agency_guidance":
            assert source["url"].startswith("https://www.cisa.gov/")
            assert "not a live solicitation" in " ".join(source["notes"])


def test_main_extraction_ignores_navigation_and_scripts_and_preserves_source_words():
    paragraph = "Actual source content & least-privilege access. " * 8
    html = f"<html><nav>Unrelated nav</nav><div role='main'><h1>Source heading</h1><p>{paragraph}</p><script>fake text</script><img src='x'><p>Final paragraph.</p></div><footer>Footer text</footer></html>"
    result = collector.extract_main_text(html)
    assert "Actual source content & least-privilege access." in result
    assert "Final paragraph." in result
    assert not any(word in result for word in ("Unrelated", "fake text", "Footer text"))


def test_publisher_article_region_is_supported():
    text = "Actual capability source words. " * 12
    result = collector.extract_main_text(f"<article data-swiftype-index='true'>{text}</article>")
    assert result == text.strip()


def test_challenge_or_changed_source_fails_closed():
    with pytest.raises(ValueError):
        collector.extract_main_text("<html><h1>Access denied</h1></html>")
    with pytest.raises(ValueError):
        collector.bounded_excerpt("Different page content", "Expected heading", None, 185)


def test_vendor_excerpt_is_exact_bounded_source_text():
    text = "Navigation\nCapability heading\n" + " ".join(f"word{i}" for i in range(300))
    excerpt = collector.bounded_excerpt(text, "Capability heading", None, 185)
    assert len(excerpt.split()) == 185
    assert excerpt == " ".join(text[text.index("Capability heading"):].split()[:185])


def test_award_selection_uses_description_not_company_name():
    rows = [{"id": "real", "description": "Security operations center support", "recipient_name": "Ordinary Name", "obligation": 1},
            {"id": "unrelated", "description": "Office furniture", "recipient_name": "CYBER SOC IDENTITY COMPANY", "obligation": 100}]
    assert [a["id"] for a in collector.select_awards(rows)] == ["real"]


def test_source_id_is_stable_across_collection_dates():
    award = json.loads((ROOT / "data/snapshot.json").read_text())["awards"][0]
    assert collector.award_source(award, "2026-01-01T00:00:00Z")["id"] == collector.award_source(award, "2027-01-01T00:00:00Z")["id"]


def test_failed_public_fetch_preserves_existing_corpus(tmp_path, monkeypatch):
    snapshot = json.loads((ROOT / "data/snapshot.json").read_text())
    (tmp_path / "data").mkdir()
    (tmp_path / "data/snapshot.json").write_text(json.dumps(snapshot))
    output = tmp_path / "data/team_sources.json"
    output.write_text("existing verified corpus")
    monkeypatch.setattr(collector, "ROOT", tmp_path)

    def fail_fetch(*args, **kwargs):
        raise subprocess.CalledProcessError(22, "curl")

    monkeypatch.setattr(collector.subprocess, "run", fail_fetch)
    with pytest.raises(subprocess.CalledProcessError):
        collector.main()
    assert output.read_text() == "existing verified corpus"
