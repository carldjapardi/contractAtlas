# Multi-source memory comparison — observed results

**Cognee saved and retrieved a durable lesson. This experiment did not show a checklist-score gain or an advantage over document RAG.**

| Method | Before review | After review + native improvement | Critical errors before → after | Mean query seconds before → after |
| --- | --- | --- | --- | --- |
| Document RAG (`RAG_COMPLETION`) | 22/24 | 22/24 | 1 → 0 | 10.7 → 9.4 |
| Cognee hybrid (`HYBRID_COMPLETION`) | 20/24 | 20/24 | 0 → 0 | 9.9 → 9.9 |

These are binary checklist totals across four questions, not general accuracy percentages. One run and small timing differences do not establish a speed advantage.

## What we tested

The separate expansion contained 68 documents: historical awards, curated exact-entity candidate records, four company capability excerpts, official CISA guidance, and explicitly fictional company/meeting/relationship inputs. Neither the synthetic review nor expected answers were in initial memory.

We froze four questions and 24 checks before generation, then ran both methods before and after the same accepted synthetic reviewer guidance and native `improve()`. Both conditions had identical documents within each phase, the same question/profile/system instruction/schema and requested topK=10, and fresh sessions. Method order alternated. All 16 answers completed. Listed-document fingerprints stayed stable during each batch; returned search types matched the requested types. Evaluation sessions were excluded from improvement.

Another implementation agent reviewed anonymous answers without the method/phase key. The integrator independently checked the public-candidate and readiness judgments before unmasking, including the stale-capacity critical flag. This is assistant review, not independent human evaluation. Exact award-source citations plus correct SOC scope counted as identifying the award; all eight candidate/readiness-field assessments were required for the complete-readiness check.

## What the answers showed

- Both document-RAG answers identified Leidos and Deloitte & Touche LLP as historical SOC contractors. Both hybrid answers identified Leidos but omitted Deloitte. One hybrid answer additionally asserted that no other listed candidate had SOC evidence, which the Deloitte award contradicts.
- All four capacity answers used the newer Harbor update, rejected December availability, preserved provisional January capacity, and named the follow-up owner.
- All four readiness answers preserved Cedar's pending documents and unknown eligibility, but none separately assessed Cedar's technical fit apart from its staffed-coverage claim. The complete four-fields-for-both-candidates check therefore failed in every condition.
- All four guidance answers passed the six CISA checks and avoided presenting maturity guidance as a supplied procurement mandate.
- The before document-RAG public-candidate answer introduced Harbor's withdrawn December capacity as currently provisional. Its after answer omitted that stale claim. This is one observed error change; it does not isolate a causal improvement effect.
- All public-candidate answers omitted an explicit brand-versus-legal-entity capability boundary. Several otherwise supported answers used human-resolvable record/marker aliases rather than exact source IDs. Citation details are recorded separately from semantic checklist scores.

## What native improvement actually did

Native status was `completed`: one session Q&A persisted, one session-learning document distilled, no session failures, and the global context index completed. Trace persistence reported no new trace steps; agent-context extraction returned zero lessons; preference updates applied zero turns. Feedback weights, truth subspace and conflict review were skipped. We do not claim those features improved this run.

The listed inventory grew from 68 to 70 documents. A separate retrieval returned the actual new lesson: assess technical fit, staffed coverage, dated capacity and eligibility separately; retain source/date attribution and superseded history; keep promised evidence pending; name an owner and evidence needed for each gap. This proves durable memory creation and retrieval. It did not increase the checklist scores in these fresh-session answers.

The original three-role demo independently proved peer-trace retrieval and four fresh-session lesson excerpts; see [DEMO_RESULTS.md](DEMO_RESULTS.md). It remains unchanged.

## Limits and next decision

Both methods run through the same Cloud tenant configuration, whose exact model version and temperature are not exposed in the responses. Their internal context construction and token budgets differ. Inventory fingerprints do not prove complete graph/index immutability. The after condition combines adding accepted feedback and memory consolidation. The four questions are repeated probes, not an unseen test set.

For the hackathon, demonstrate **shared research memory and an inspectable review-to-memory loop**. Do not claim improved research accuracy. A useful follow-up would inspect why hybrid missed the Deloitte record and test retrieval changes on new, separately frozen questions; preserve these results rather than tuning this evaluation into a win.

## Inspect and reproduce

- [Full answers, checks, citation reviews, latency and improvement stages](data/expansion/comparison_results.json)
- [Frozen protocol](data/expansion/comparison_protocol.md) and [rubric](data/expansion/comparison_rubric.json)
- UI: **Benchmark → Multi-source memory experiment**

The original raw responses, anonymous review key, inventories and intervention remain locally under ignored `data/expansion/runtime/comparison/`. With a newly seeded isolated dataset, run `python -m scripts.compare_expansion before`, then `improve`, `after`, and `blind`. Complete a new anonymous review before `python -m scripts.publish_comparison`. Paid improvement attempts are recorded and cannot be silently repeated.
