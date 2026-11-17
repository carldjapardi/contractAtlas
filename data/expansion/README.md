# Approved source expansion: items 1-7

Collected November 16, 2026, Pacific time. This bundle extends the contractor research scenario without replacing `data/team_sources.json`, its Cloud manifest, or the successful original run. No repository or solicitation was added.

| Approved item | Delivered material | Evidence status |
| --- | --- | --- |
| 1. Candidate partners | `candidate_partners.csv`: 12 exact recipient identities, selected descriptions, award IDs and original URLs | Real, derived from the frozen USAspending snapshot |
| 2. Company capabilities | Existing Leidos and GuidePoint excerpts plus new Accenture Federal Services and Deloitte excerpts | Four companies' self-reported public claims |
| 3. Our capability statement | `synthetic/company_profile.md` | Fictional Atlas Identity Lab scenario |
| 4. Relationships/outreach | `synthetic/relationships.csv`: six dated records, two fictional candidates, owners and next actions | Synthetic, linked to meeting IDs |
| 5. Meeting transcripts | Discovery, delivery qualification, capacity update | Three synthetic transcripts with fictional people and organizations |
| 6. Research review | `synthetic/review_meeting.md` | Synthetic review input, excluded from initial ingestion |
| 7. Focused agency guidance | CISA Zero Trust Maturity Model v2, section 5.1 and selected Table 2 cells, pages 13-15 | Real official guidance; maturity-stage labels preserved |

## Read the data

The candidate CSV is a research list, not a qualified-partner list. It preserves exact recipient IDs/UEIs and never merges same-name recipients or transfers capabilities between related legal entities. The 12 entries include monitoring, assessments, training, credential equipment, and research organizations. Their lanes explain why they may be worth investigating; enterprise IAM suitability remains a separate question. Missing contacts, availability, coverage, interest and eligibility are explicitly `unknown`.

List-valued CSV fields are JSON arrays. Award descriptions are verbatim. Selected award counts describe only the listed evidence, not all awards or fiscal-year spending. The original snapshot and source timestamps remain authoritative.

Harbor Signal, Cedar Response, Atlas Identity Lab and every named participant in their records are fictional. They have `demo:` IDs, no UEIs, and no identity links to real contractors. Conversations are attributed fictional claims, not verified operational evidence. The November 16 Harbor update supersedes its earlier capacity statement, while its weekday-only coverage remains unchanged. Cedar's promised roster and escalation matrix are pending.

`team_sources.expanded.json` contains 68 documents: all 28 original documents, additional supporting award records, two new capability excerpts, focused guidance, the profile/three transcripts, and source documents rendered from the CSV rows. Curated rows use the existing `internal_brief` schema with explicit real-derived or synthetic provenance in their titles, text and notes. The two CSVs and JSON source documents are built from the same records.

Raw public captures, extracted text, source URLs, retrieval timestamps and SHA-256 hashes are retained under `public/` and `manifest.json`. Vendor excerpts contain at most 185 words. Deloitte's page is brand-level evidence, not proof that every service belongs to the exact award recipient. The CISA selection preserves optimal-maturity column labels and is not a procurement mandate.

## Rebuild and verify

From the project root, using a Python environment with `pypdf`:

```sh
python -m scripts.build_source_expansion
python -m scripts.build_source_expansion --refresh-public
.venv/bin/python -m pytest -q tests/test_source_expansion.py
```

The first command rebuilds from retained public captures and the frozen snapshot. The second explicitly refreshes public captures and requires network access. CISA cells are checked against extracted source text; changed content fails rather than being silently fabricated. Pages 13-15 were rendered and visually inspected during collection.

## Use in the existing research workflow

This is a staged source bundle, not an already executed new learning experiment. The active app and original verified Cloud dataset remain unchanged.

The isolated seed command below uses the existing Cloud implementation, expanded source path, and a separate manifest under ignored `runtime/`. The dataset name is derived from the expanded source fingerprint. It does not change `.env` or the active app's source/manifest paths:

```sh
.venv/bin/python -m scripts.seed_source_expansion
```

The role sequence stays opportunity analyst, partner researcher, evidence reviewer, accepted feedback, native improvement, and fresh-session retrieval. Follow `evaluation_cases.json` to evaluate the new material without answer leakage. Do not add the synthetic review meeting or evaluation rubric to the initial source collection. The review is an explicit later feedback turn. Synthetic inputs are disclosed; stages, counts, reports and retrieval must remain actual observed outputs. No new improvement result is asserted by this bundle.

## Collection status

All approved material is present and validated. Activation in the app and an expanded-corpus Cloud research/improvement run have not been performed. The separate seed tool is provided so integration can use the existing agent workflow without overwriting the preserved checkpoint.
