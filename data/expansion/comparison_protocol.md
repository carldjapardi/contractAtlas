# Frozen comparison protocol

This protocol is fixed before generating comparison answers. The original four-question file and the 68-source corpus are unchanged.

## Design

Two retrieval methods × two memory states, four questions each: 16 answers.

- **Document RAG:** Cognee Cloud `RAG_COMPLETION`, using document/vector retrieval.
- **Cognee hybrid:** the same tenant's `HYBRID_COMPLETION`, using document, entity and fact retrieval.
- **Before:** the isolated expanded dataset with 68 source documents, no accepted review in graph memory.
- **After:** that same dataset after the accepted synthetic review guidance has entered a real session and native `improve()` has run. BOTH methods access the identical post-improvement inventory, including any persisted feedback and learned documents.

Both methods use the same Cloud model configuration, company profile, question, generic answer schema, system instruction, requested topK=10, graph scope and dataset filters. The held-out readiness question is a repeated evaluation probe when measured before and after; its evaluation sessions are excluded from improvement. No expected answers, checks, earlier evaluation outputs or review rubric enter generation prompts or the initial corpus.

Method order alternates by question. Each answer uses a new session. Answering can record session Q&A, but only the explicit review session is consolidated into graph memory. Document inventories are fingerprinted before and after each measurement batch. Cases and prompts are not tuned after observing results.

The retrieval strategies construct different contexts internally. This is a package-level comparison with matched requested topK, not a token-budget-matched isolation of graph traversal. The before/after change combines new accepted feedback and native memory consolidation; it does not isolate improve() from adding information.

The same tenant configuration is used throughout; the Cloud responses do not expose a pinned model version or temperature. Inventory fingerprints establish listed-document stability, not complete graph/index immutability. Returned search types are checked against the requested methods when publishing results.

## Review

Freeze 24 binary checks: six per question in `comparison_rubric.json`. Assess semantic correctness against source documents; equivalent wording passes. An omitted answer fails that check. A contradiction also receives a separate critical-error flag where applicable.

Report checklist coverage, supporting citations, critical errors and latency separately. Valid source IDs are not proof of entailment. Outputs are reviewed under anonymous labels, with method/phase mappings stored separately. These are assistant-reviewed exploratory results, not an independent human or statistically validated benchmark.

## Bounds and outcomes

One initial run, four questions, no forced mistakes. Retain errors and original outputs. The review document remains explicitly synthetic. Keep public companies and fictional partners separate. If both methods answer correctly, report parity. If Cognee performs worse, report it. Native lesson creation and fresh-session reuse are separate outcomes from answer quality.
