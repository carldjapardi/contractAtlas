# Sponsor checkpoint: shared and improving research memory

Confirmed user: a cybersecurity contractor's business-development team.

Problem: opportunity requirements, public award history, vendor capability pages, and the team's research conclusions live in separate places. Each research session repeats work and loses corrections.

Demo: give a small contractor a clearly labeled research brief, let opportunity/partner/reviewer agents share Cognee memory, accept a real review lesson, call `cognee.improve()`, then show a new agent session retrieving and applying the durable lesson.

The target brief is market/teaming research, not a fabricated live solicitation. Public guidance describes agency needs; USAspending describes historical awards; vendor pages describe self-reported capabilities. Keep those distinctions visible.

## Must demonstrate

1. At least three different source types ingested into Cognee: award data, agency guidance, and company capability text. The internal/demo brief is separately labeled.
2. Actual LLM research agents with distinct roles/session IDs reading the same dataset. Preserve outputs and SDK memory/trace events.
3. An unchanged before checkpoint and an explicit review/learning step.
4. A real `improve(dataset=..., session_ids=[...])` result, including stages and document counts. A completed stage with zero new lessons is not proof of learning.
5. A fresh agent session retrieving shared permanent memory without the accepted correction copied into its prompt.
6. Evidence of what changed, plus a source-linked graph or memory view.
7. No forced errors, scripted answer swapping, invented benefits, or guaranteed performance claims.

## Preserve

The award explorer, data integrity checks, and initial retrieval comparison remain available as supporting views. The initial comparison is committed; a new narrative does not erase its results.

## Build boundaries

- Data builder owns multi-source collection `data/team_sources.json`, `scripts/collect_team_sources.py`, source tests only.
- Cognee builder owns `backend/team_memory.py`, `scripts/seed_team_memory.py`, memory/provider tests only.
- Frontend builder owns `frontend/**`, with a new Research team view.
- Lead owns HTTP routes/models, orchestration HTTP/background job manager, integration, tests, documentation, and commits.

The working local SDK remains the default while Cognee Cloud account setup happens independently. Do not switch runtime or spend cloud credits until credential configuration and API compatibility are verified.
