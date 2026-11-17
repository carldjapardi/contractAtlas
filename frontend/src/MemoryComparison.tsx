import { useEffect, useState } from 'react';
import { api } from './api';

type Score = { phase: string; method: string; passed: number; total: number; critical_errors: number; mean_elapsed_ms: number };
type ReviewedAnswer = { case_id: string; question: string; phase: string; method: string; answer: string; source_ids: string[]; passed: number; total: number; review_notes: string[] };
type Comparison = { status: string; headline: string; source_count: number; question_count: number; summary: Score[]; answers: ReviewedAnswer[]; limitations: string[]; improvement: { new_documents: number; freshly_retrieved_lessons: number; completed_stages: string[] } };
const name = (method: string) => method === 'rag' ? 'Document RAG' : 'Cognee hybrid';

export default function MemoryComparison() {
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { api<Comparison>('/comparison').then(setResult).catch(() => setError(true)); }, []);
  if (error) return <p className="evaluation-notice">The multi-source comparison could not be loaded.</p>;
  if (!result || result.status !== 'complete') return <div className="evaluation-notice">Multi-source memory comparison is in progress. No quality improvement is claimed until its results are reviewed.</div>;
  return <section aria-label="Multi-source memory comparison">
    <div className="benchmark-results-heading"><div><span className="eyebrow">MULTI-SOURCE MEMORY EXPERIMENT</span><h3>{result.headline}</h3><p>{result.source_count} starting sources · {result.question_count} repeated questions · 16 fresh-session answers · assistant-reviewed checklist</p></div></div>
    <div className="table-scroll"><table className="case-results"><thead><tr><th>Memory state</th><th>Approach</th><th>Checks passed</th><th>Critical errors</th><th>Mean query time</th></tr></thead><tbody>{result.summary.map(row => <tr key={`${row.phase}-${row.method}`}><td>{row.phase === 'before' ? 'Before review' : 'After review + improve'}</td><td>{name(row.method)}</td><td>{row.passed}/{row.total}</td><td>{row.critical_errors}</td><td>{(row.mean_elapsed_ms / 1000).toFixed(1)} s</td></tr>)}</tbody></table></div>
    <div className="evaluation-notice"><p>Native improvement added {result.improvement.new_documents} documents; a fresh retrieval found {result.improvement.freshly_retrieved_lessons} distilled lesson. Memory creation and answer quality are measured separately.</p></div>
    <details className="case-details"><summary>Read the answers and review notes</summary>{result.answers.map(row => <div key={`${row.phase}-${row.method}-${row.case_id}`}><strong>{row.question} · {name(row.method)} · {row.phase} · {row.passed}/{row.total}</strong><p>{row.answer}</p><p>Sources: {row.source_ids.join(', ') || 'None cited'}</p><p>{row.review_notes.join(' ')}</p></div>)}</details>
    <div className="evaluation-notice"><p>{result.limitations.join(' ')}</p></div>
  </section>;
}
