import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen,
  Check, ChevronDown, ChevronRight, CircleHelp, Clock3,
  Database, ExternalLink, FileText, FlaskConical, GitBranch, Globe2,
  Landmark, LoaderCircle, Network, RefreshCw, Search, ShieldCheck,
  SlidersHorizontal, Sparkles, Users, X,
} from 'lucide-react';
import { api } from './api';
import KnowledgeGraph from './KnowledgeGraph';
import TeamResearch from './TeamResearch';
import MemoryComparison from './MemoryComparison';
import DemoAccess from './DemoAccess';
import type { Answer, Award, AwardsResponse, Dataset, Evaluation, Evidence, Graph, GraphNode, Health, Mode, View } from './types';

const emptyGraph: Graph = { nodes: [], edges: [], truncated: false };
const prompts = ['Who receives cybersecurity contracts?', 'Find identity and access management awards', 'Which recipients share a parent?'];
const money = (amount: number, compact = true) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: compact ? 'compact' : 'standard', maximumFractionDigits: compact ? 1 : 0 }).format(amount);
const count = (value: number) => new Intl.NumberFormat('en-US').format(value);
const date = (value: string | null | undefined) => value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: value.includes('T') ? 'America/Los_Angeles' : 'UTC' }) : 'Not available';
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const sourceUrl = (value: string) => { try { const url = new URL(value); return url.protocol === 'https:' && (url.hostname === 'www.usaspending.gov' || url.hostname === 'api.usaspending.gov') ? url.href : undefined; } catch { return undefined; } };
const asEvidence = (award: Award): Evidence => ({ id: award.id, title: `${award.recipient_name} · ${award.award_id}`, description: award.description, source_url: award.source_url, obligation: award.obligation, agency: award.agency, recipient_name: award.recipient_name });

function downloadJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

function SourceCard({ evidence, index, expanded = false, recipientUei }: { evidence: Evidence; index: number; expanded?: boolean; recipientUei?: string | null }) {
  const [open, setOpen] = useState(expanded);
  const href = sourceUrl(evidence.source_url);
  return <article className={`source-card ${open ? 'source-open' : ''}`}>
    <button className="source-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span className="source-number">{String(index + 1).padStart(2, '0')}</span>
      <span className="source-heading"><strong>{evidence.recipient_name}</strong><span>{money(evidence.obligation)} <span className="source-amount-label">award obligations</span></span></span>
      <ChevronDown size={15} className={open ? 'rotate' : ''} />
    </button>
    {open && <div className="source-details"><p>{evidence.description || 'No award description was reported.'}</p>
      <div className="record-id">{evidence.title}</div>
      {recipientUei && <div className="record-id">Recipient UEI · {recipientUei}</div>}
      {href && <a href={href} target="_blank" rel="noreferrer">View source record <ArrowUpRight size={13} /></a>}
    </div>}
  </article>;
}

function AnswerText({ text }: { text: string }) {
  const paragraphs = text.split(/\n\s*\n/);
  return <><div className="answer-text">{paragraphs[0]}</div>{paragraphs.length > 1 && <details className="answer-excerpts"><summary>Read source excerpts <ChevronDown size={12} /></summary><div className="answer-text">{paragraphs.slice(1).join('\n\n')}</div></details>}</>;
}

function AwardsView({ onExplore }: { onExplore: (award: Award) => void }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [result, setResult] = useState<AwardsResponse>({ awards: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let current = true;
    const timer = setTimeout(() => {
      setLoading(true); setError('');
      api<AwardsResponse>(`/awards?limit=500&search=${encodeURIComponent(search)}`).then(data => { if (current) { setResult(data); setPage(0); } }).catch(error => { if (current) setError(messageOf(error)); }).finally(() => { if (current) setLoading(false); });
    }, 250);
    return () => { current = false; clearTimeout(timer); };
  }, [search]);
  const pageCount = Math.max(1, Math.ceil(result.awards.length / 25));
  const pageAwards = result.awards.slice(page * 25, (page + 1) * 25);
  return <section className="records-view">
    <div className="section-title"><div><span className="eyebrow">THE SOURCE OF TRUTH</span><h2>Awards, in detail.</h2><p>Inspect the reported records behind the relationships.</p></div>
      <button className="button-secondary" onClick={() => downloadJson(result.awards, 'contract-atlas-awards.json')} disabled={!result.awards.length}><ArrowDownToLine size={15} /> Export records</button></div>
    <div className="records-card"><div className="records-toolbar"><label className="record-search"><Search size={17} /><input aria-label="Search award records" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search recipients, descriptions, or award IDs…" />{search && <button className="icon-button" aria-label="Clear search" onClick={() => setSearch('')}><X size={14} /></button>}</label><span>{loading ? 'Searching…' : `${count(result.total)} matching ${result.total === 1 ? 'award' : 'awards'}`}</span></div>
    {error && <div className="inline-error" role="alert">{error}</div>}
    <div className="table-scroll"><table><thead><tr><th>Recipient / award</th><th>Description</th><th>Award obligations</th><th>Start date</th><th><span className="sr-only">Explore</span></th></tr></thead>
      <tbody>{pageAwards.map(award => <tr key={award.id}><td><strong>{award.recipient_name}</strong><span className="table-id">{award.award_id}</span></td><td><p className="table-description">{award.description || 'No description reported'}</p></td><td className="amount-cell">{money(award.obligation, false)}</td><td className="date-cell">{date(award.start_date)}</td><td><button className="icon-button" aria-label={`Explore ${award.recipient_name}`} onClick={() => onExplore(award)}><ArrowUpRight size={17} /></button></td></tr>)}</tbody>
    </table></div>
    {!loading && !result.awards.length && <div className="table-empty"><Search size={24} /><h3>No matching awards</h3><p>Try a different recipient name or a broader search term.</p></div>}
    <div className="table-footer"><span>Showing {result.awards.length ? page * 25 + 1 : 0}–{Math.min((page + 1) * 25, result.awards.length)} of {count(result.total)} records</span><div className="pagination"><button className="button-secondary" onClick={() => setPage(value => Math.max(0, value - 1))} disabled={page === 0 || loading} aria-label="Previous page">Previous</button><span>{page + 1} / {pageCount}</span><button className="button-secondary" onClick={() => setPage(value => Math.min(pageCount - 1, value + 1))} disabled={page >= pageCount - 1 || loading} aria-label="Next page">Next</button></div><span>Amounts are award-level obligations, not cash paid.</span></div></div>
  </section>;
}

function BenchmarkView({ dataset }: { dataset: Dataset | null }) {
  const [result, setResult] = useState<Evaluation | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { api<Evaluation>('/evaluation').then(setResult).catch(error => setError(messageOf(error))); }, []);
  const cases = result?.cases ?? [];
  const summaries = result?.summary ?? [];
  const hasResults = cases.length > 0;
  const bothModes = summaries.some(item => item.mode === 'baseline' && item.completed > 0) && summaries.some(item => item.mode === 'cognee' && item.completed > 0);
  const percent = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value * 100)}%`;
  const snapshotMatches = Boolean(dataset?.snapshot_id && result?.snapshot_id === dataset.snapshot_id);
  return <section className="benchmark-view"><div className="section-title"><div><span className="eyebrow">SHOW YOUR WORK</span><h2>Better is a measurable claim.</h2><p>Compare retrieval approaches against the same frozen dataset.</p></div></div>
    <MemoryComparison />
    <div className="comparison-grid"><div className="comparison-card"><span className="method-icon"><GitBranch size={22} /></span><span className="eyebrow">ORIGINAL AWARD BASELINE</span><h3>Structured + lexical</h3><p>Explicit source relationships and description search over the original award snapshot.</p></div><div className="comparison-card"><span className="method-icon"><Sparkles size={22} /></span><span className="eyebrow">ORIGINAL AWARD COGNEE INDEX</span><h3>Graph-powered retrieval</h3><p>Earlier exploratory retrieval checks, preserved separately from the multi-source memory experiment.</p></div></div>
    {hasResults ? <div className="benchmark-results-heading"><div><span className="eyebrow">EXPLORATORY RETRIEVAL CHECKS</span><h3>{bothModes ? 'Two approaches. The same questions.' : 'Baseline checked. Comparison pending.'}</h3><p>{cases.length} questions · Generated {date(result?.generated_at)}</p></div><button className="button-secondary" onClick={() => downloadJson(result, 'contract-atlas-evaluation.json')}><ArrowDownToLine size={14} /> Export results</button></div> : <div className="benchmark-status"><div className="empty-icon"><FlaskConical size={27} /></div><h3>The benchmark is not complete yet.</h3><p>No improvement claims until both approaches are tested. The evaluation will report retrieval of selected relevant records, source ID validity, and latency.</p>
      {error && <p className="muted">Evaluation status unavailable: {error}</p>}
      {result && <button className="button-secondary" onClick={() => downloadJson(result, 'contract-atlas-evaluation.json')}><ArrowDownToLine size={15} /> Download evaluation artifact</button>}
    </div>}
    {hasResults && <><div className="evaluation-summaries">{(['baseline', 'cognee'] as const).map(method => {
      const summary = summaries.find(item => item.mode === method);
      return <div className="evaluation-summary" key={method}><div><strong>{method === 'baseline' ? 'Structured + lexical' : 'Cognee retrieval'}</strong><span className={`evaluation-state ${summary?.completed ? 'state-ready' : ''}`}>{summary?.completed ? `${summary.completed}/${summary.total} completed` : 'Not evaluated'}</span></div><div className="summary-metrics"><span><strong>{summary?.completed ? `${summary.mean_elapsed_ms.toFixed(1)} ms` : '—'}</strong><small>Mean query time</small></span><span><strong>{percent(summary?.mean_recall)}</strong><small>Anchor recall</small></span><span><strong>{percent(summary?.citation_validity)}</strong><small>Valid source IDs</small></span></div></div>;
    })}</div><div className="evaluation-notice"><CircleHelp size={15} /><p>Anchor recall checks whether selected relevant records were retrieved; it is not overall answer accuracy. Valid source IDs confirm records exist, not that every claim is supported.{!snapshotMatches && ' These results do not match the currently loaded dataset.'}{bothModes && result?.corpus_comparable === false && ' The indexed corpora differ; these results are not a like-for-like comparison.'}</p></div>
      <div className="evaluation-case-list">{cases.map((item, index) => <article className="evaluation-case" key={item.id}><div className="case-heading"><span className="source-number">{String(index + 1).padStart(2, '0')}</span><h4>{item.question}</h4><span className="case-category">{item.category}</span></div><div className="table-scroll"><table className="case-results"><thead><tr><th>Approach</th><th>Status</th><th>Query time</th><th>Anchor recall</th><th>Source IDs</th><th>Abstention check</th></tr></thead><tbody>{(['baseline', 'cognee'] as const).map(method => {
        const value = item.results.find(row => row.mode === method);
        return <tr key={method}><td>{method === 'baseline' ? 'Baseline' : 'Cognee'}</td><td><span className={`evaluation-state ${value?.status === 'ok' ? 'state-ready' : ''}`}>{value?.status === 'ok' ? 'Completed' : value?.status === 'error' ? 'Error' : 'Unavailable'}</span></td><td>{value?.status === 'ok' ? `${value.elapsed_ms.toFixed(1)} ms` : '—'}</td><td>{percent(value?.recall)}</td><td>{percent(value?.citation_validity)}</td><td>{value?.abstention_check == null ? '—' : value.abstention_check ? <span className="abstention-pass"><Check size={11} /> Passed</span> : 'Failed'}</td></tr>;
      })}</tbody></table></div><details className="case-details"><summary>Inspect returned answers <ChevronDown size={12} /></summary>{item.results.map(value => <div key={value.mode}><strong>{value.mode === 'baseline' ? 'Baseline' : 'Cognee'}</strong><p>{value.answer || value.error || 'No answer returned.'}</p><span>{value.evidence_ids?.length ?? 0} source records returned</span></div>)}</details></article>)}</div></>}
    <div className="benchmark-footnote"><ShieldCheck size={18} /><p>{result?.scope_note || 'These are exploratory retrieval checks, not a held-out research benchmark.'} Snapshot <code>{result?.snapshot_id?.slice(0, 12) || 'not loaded'}</code>. This prototype’s baseline does not isolate graph reasoning from embeddings.</p></div>
  </section>;
}

export default function App() {
  const [view, setView] = useState<View>('research');
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [graph, setGraph] = useState<Graph>(emptyGraph);
  const [baseGraph, setBaseGraph] = useState<Graph>(emptyGraph);
  const [allAwards, setAllAwards] = useState<Award[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<Mode>('baseline');
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [selectedRecords, setSelectedRecords] = useState<Evidence[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scopeOpen, setScopeOpen] = useState(false);
  const [limit, setLimit] = useState(4);
  const questionRef = useRef<HTMLInputElement>(null);
  const selectionGeneration = useRef(0);

  const refresh = useCallback(async () => {
    setLoading(true); setError('');
    const results = await Promise.allSettled([api<Dataset>('/dataset'), api<Health>('/health'), api<Graph>(`/graph?limit=${limit}`), api<AwardsResponse>('/awards?limit=500')]);
    if (results[0].status === 'fulfilled') setDataset(results[0].value);
    else setError('Cannot connect to the data service. Start the backend, then refresh this workspace.');
    if (results[1].status === 'fulfilled') setHealth(results[1].value);
    if (results[2].status === 'fulfilled') { setGraph(results[2].value); setBaseGraph(results[2].value); }
    if (results[3].status === 'fulfilled') setAllAwards(results[3].value.awards);
    setAnswer(null); setSelected(null); setLoading(false);
  }, [limit]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const timer = setInterval(() => { api<Health>('/health').then(setHealth).catch(() => {}); }, 15000);
    return () => clearInterval(timer);
  }, []);

  const selectNode = useCallback((node: GraphNode | null) => {
    setSelected(node); setSelectedRecords([]);
    const generation = ++selectionGeneration.current;
    if (!node) return;
    const local = allAwards.filter(award => node.award_ids.includes(award.id));
    setSelectedRecords(local.map(asEvidence));
    if (local.length < node.award_ids.length) {
      const search = node.type === 'recipient' ? `recipient_id=${encodeURIComponent(node.id.replace(/^recipient:/, ''))}` : `search=${encodeURIComponent(node.type === 'award' ? node.sublabel || node.label : '')}`;
      api<AwardsResponse>(`/awards?limit=500&${search}`).then(result => {
        if (generation === selectionGeneration.current) setSelectedRecords(result.awards.filter(award => node.award_ids.includes(award.id)).map(asEvidence));
      }).catch(() => {});
    }
  }, [allAwards]);

  async function submitQuery(text = question) {
    if (!text.trim() || busy || loading) return;
    setQuestion(text); setBusy(true); setError(''); setSelected(null);
    try {
      const result = await api<Answer>('/query', { method: 'POST', body: JSON.stringify({ question: text.trim(), mode }) });
      setAnswer(result); setGraph(result.graph);
    } catch (error) { setError(messageOf(error)); }
    finally { setBusy(false); }
  }

  const cogneeReady = Boolean(health?.cognee.ready);
  const evidence = selected ? selectedRecords : answer?.evidence ?? [];
  const hasData = Boolean(dataset?.award_count);
  const viewTitle = view === 'research' ? 'Research team' : view === 'explore' ? 'Explore' : view === 'awards' ? 'Award records' : 'Benchmark';

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to workspace</a>
    <aside className="sidebar"><a href="/" className="brand" aria-label="Contract Atlas home"><span className="brand-mark"><Landmark size={23} strokeWidth={1.7} /></span><span>contract<span className="brand-light">atlas</span><small>FOLLOW THE FUNDING</small></span></a>
      <div className="nav-label">WORKSPACE</div><nav aria-label="Workspace navigation">{([{ id: 'research', label: 'Research team', icon: Users }, { id: 'explore', label: 'Explore graph', icon: Network }, { id: 'awards', label: 'Award records', icon: FileText }, { id: 'benchmark', label: 'Benchmark', icon: FlaskConical }] as const).map(item => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} onClick={() => setView(item.id)} aria-label={item.label} aria-current={view === item.id ? 'page' : undefined}><item.icon size={18} /><span>{item.label}</span>{view === item.id && <span className="nav-active-dot" />}</button>)}</nav>
      <div className="sidebar-divider" /><div className="nav-label">DATA COLLECTION</div><div className="collection"><span className="collection-symbol"><ShieldCheck size={16} /></span><span>Federal contracts<small>{dataset?.agency === 'Department of Homeland Security' ? 'DHS' : dataset?.agency || 'DHS'} · FY {dataset?.fiscal_year || 2025}</small></span></div>
      <div className="sidebar-bottom"><div className="source-badge"><span className={`status-dot ${hasData ? '' : 'offline'}`} /><span>{hasData ? 'Real data. Traceable sources.' : 'Waiting for source data.'}</span></div><p>Built on public USAspending records. Every connection has a starting point.</p><a href="https://www.usaspending.gov" target="_blank" rel="noreferrer">About the source <ArrowUpRight size={13} /></a><div className="prototype-tag">HACKATHON PROTOTYPE <span>v0.1</span></div></div>
    </aside>
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>{viewTitle}</strong></div><div className="topbar-right"><span className="snapshot-label"><Database size={13} /> {view === 'research' ? 'Shared research memory' : 'Frozen snapshot'}</span><span className="avatar" title="Local workspace">CA</span></div></header>
      <main id="main-content">
        <DemoAccess />
        {view === 'research' && <TeamResearch />}
        {view === 'explore' && <>
          <div className="workspace-heading"><div><span className="eyebrow">CONNECTED RECORDS. CLEARER ANSWERS.</span><h1>Follow the funding<span>.</span></h1><p>Explore who gets funded, how they connect, and the evidence behind it.</p></div><button className="button-secondary refresh-button" onClick={() => void refresh()} disabled={loading || busy}><RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh data</button></div>
          <section className="query-card" aria-label="Ask about federal contracts"><div className="query-topline"><span><Sparkles size={15} /> ASK YOUR DATA</span><div className="mode-switch" aria-label="Retrieval mode"><button className={mode === 'baseline' ? 'selected' : ''} onClick={() => setMode('baseline')} aria-pressed={mode === 'baseline'}><GitBranch size={13} /> Baseline</button><button className={mode === 'cognee' ? 'selected' : ''} onClick={() => setMode('cognee')} aria-pressed={mode === 'cognee'} title={health?.cognee.reason || 'Cognee status is loading'}><Sparkles size={13} /> Cognee {!cogneeReady && <span className="mode-pending-dot" />}</button></div></div>
            <form onSubmit={event => { event.preventDefault(); void submitQuery(); }}><Search size={22} className="query-search-icon" /><input ref={questionRef} value={question} onChange={event => setQuestion(event.target.value)} placeholder="What would you like to uncover?" aria-label="Ask a question about the contract dataset" maxLength={2000} /><button className="query-submit" disabled={!question.trim() || busy || loading || !hasData || (mode === 'cognee' && !cogneeReady)}>{busy ? <LoaderCircle size={16} className="spin" /> : <>Explore <ArrowRight size={16} /></>}</button></form>
            <div className="example-prompts"><span>Try asking</span>{prompts.map(prompt => <button key={prompt} onClick={() => { setQuestion(prompt); questionRef.current?.focus(); if (mode === 'baseline' || cogneeReady) void submitQuery(prompt); }} disabled={busy}>{prompt}<ArrowUpRight size={11} /></button>)}</div>
            {mode === 'cognee' && !cogneeReady && <div className="provider-notice"><CircleHelp size={14} /><span>{health?.cognee.reason || 'Checking Cognee availability…'} Baseline exploration is available without a model provider.</span></div>}
          </section>
          {error && <div className="inline-error workspace-error" role="alert"><CircleHelp size={17} /><span>{error}</span><button className="icon-button" onClick={() => setError('')} aria-label="Dismiss error"><X size={15} /></button></div>}
          <div className="scope-stats"><div className="scope-filters"><span className="scope-icon"><SlidersHorizontal size={15} /></span><button className="scope-chip" onClick={() => setScopeOpen(!scopeOpen)} aria-expanded={scopeOpen}><Landmark size={13} /> {dataset?.agency === 'Department of Homeland Security' ? 'DHS' : dataset?.agency || 'DHS'}<ChevronDown size={12} /></button><span className="scope-chip static-chip">FY {dataset?.fiscal_year || 2025}</span><span className="scope-chip topic-chip">Cyber keyword <span className="tiny-dot" /></span><span className="scope-type">Contracts</span></div><div className="quick-stats"><span><strong>{dataset ? count(dataset.award_count) : '—'}</strong> awards</span><span><strong>{dataset ? count(dataset.recipient_count) : '—'}</strong> recipients</span><span title="Sum of award-level obligations for the snapshot; not FY-only spending"><strong>{dataset ? money(dataset.total_obligation) : '—'}</strong> award obligations</span></div></div>
          {scopeOpen && <div className="scope-details"><div><strong>Snapshot scope</strong><span>Fixed collection · refresh reloads the local snapshot</span></div><p>{dataset?.name || 'Dataset not loaded'}. Keywords: {dataset?.keywords?.join(', ') || 'not available'}. Retrieved {date(dataset?.retrieved_at)}.</p>{dataset?.truncated && <p>This is a capped sample, not a complete inventory.</p>}{dataset?.notes?.map((note, index) => <p key={index}>{note}</p>)}</div>}
          <section className="investigation"><div className="graph-panel"><div className="panel-heading"><div><Network size={17} /><h2>Relationship map</h2><span className="count-badge">{graph.nodes.length} nodes</span></div><div className="graph-actions">{answer && <button className="text-button" onClick={() => { setAnswer(null); setGraph(baseGraph); setSelected(null); }}>Reset view</button>}<button className="icon-button" onClick={() => downloadJson(graph, 'contract-atlas-graph.json')} title="Export graph" aria-label="Export graph" disabled={!graph.nodes.length}><ArrowDownToLine size={16} /></button></div></div><div className={`graph-canvas ${busy ? 'graph-busy' : ''}`}><KnowledgeGraph graph={graph} selectedId={selected?.id} onSelect={selectNode} loading={loading} />{busy && <div className="graph-loading"><LoaderCircle size={17} className="spin" /> Finding supporting records…</div>}{graph.nodes.length > 0 && <div className="graph-hint"><span className="hint-dot" /> Click a node to inspect its evidence</div>}</div><div className="graph-footer"><div className="legend"><span><i className="legend-agency" />Agency</span><span><i className="legend-recipient" />Recipient</span><span><i className="legend-award" />Award</span><span className="legend-inferred"><i />Inferred link</span></div>{graph.truncated && !answer && <button className="text-button" onClick={() => setLimit(value => Math.min(value + 6, 30))} disabled={limit >= 30}>Show more <ArrowRight size={12} /></button>}{graph.truncated && answer && <span className="graph-truncation">Focused result</span>}</div></div>
          <aside className="evidence-panel" aria-label="Answer and supporting evidence"><div className="panel-heading"><div><BookOpen size={16} /><h2>{selected ? 'Selected connection' : answer ? 'Findings & evidence' : 'The evidence trail'}</h2></div>{selected && <button className="icon-button" aria-label="Clear node selection" onClick={() => selectNode(null)}><X size={15} /></button>}</div><div className="evidence-content">
            {selected ? <><span className="eyebrow">{selected.type.replace('_', ' ')}</span><h3 className="selected-title">{selected.label}</h3><p className="selected-subtitle">{selected.sublabel}</p><div className="evidence-divider" /><div className="evidence-label">SUPPORTING AWARDS <span>{evidence.length}</span></div>{evidence.map((record, index) => <SourceCard key={record.id} evidence={record} index={index} expanded={index === 0} recipientUei={allAwards.find(award => award.id === record.id)?.recipient_uei} />)}{!evidence.length && <p className="muted">No supporting award details are available in the loaded records.</p>}</> : answer ? <><div className="answer-meta"><span><span className="status-dot" /> {answer.mode === 'cognee' ? 'Cognee retrieval' : 'Structured + lexical'}</span><span><Clock3 size={11} /> {(answer.elapsed_ms / 1000).toFixed(2)}s</span></div><AnswerText text={answer.answer} /><div className="evidence-divider" /><div className="evidence-label">SOURCE RECORDS <span>{answer.matched_count} matched</span></div>{evidence.map((record, index) => <SourceCard key={record.id} evidence={record} index={index} expanded={index === 0} recipientUei={allAwards.find(award => award.id === record.id)?.recipient_uei} />)}{answer.coverage_notes?.length > 0 && <details className="coverage-notes"><summary>Coverage & limitations <ChevronDown size={12} /></summary>{answer.coverage_notes.map((note, i) => <p key={i}>{note}</p>)}</details>}<button className="export-answer" onClick={() => downloadJson(answer, 'contract-atlas-findings.json')}><ArrowDownToLine size={14} /> Export findings</button></> : <div className="evidence-welcome"><div className="evidence-illustration"><span className="illustration-file"><FileText size={25} strokeWidth={1.4} /><span /><span /></span><span className="illustration-check"><Check size={13} /></span><span className="illustration-orbit" /></div><h3>Every connection<br />has a source.</h3><p>Ask a question or select a node to see the records behind the relationships.</p><div className="welcome-points"><span><ShieldCheck size={14} /> Reported links stay traceable</span><span><Sparkles size={14} /> Inferred links stay distinguishable</span><span><ExternalLink size={14} /> Original awards are one click away</span></div></div>}
          </div><div className="evidence-footer"><ShieldCheck size={12} /><span>Grounded in source records</span></div></aside></section>
          <div className="workspace-footer"><span><Globe2 size={12} /> Public records. Focused exploration.</span><span>{dataset?.retrieved_at ? `Snapshot retrieved ${date(dataset.retrieved_at)}` : 'Waiting for dataset'}<span className="footer-dot">·</span>Award obligations ≠ cash paid</span></div>
        </>}
        {view === 'awards' && <AwardsView onExplore={award => { setView('explore'); setQuestion(`What awards connect ${award.recipient_name} to DHS?`); selectNode({ id: award.id, type: 'award', label: award.recipient_name, sublabel: award.award_id, award_ids: [award.id] }); }} />}
        {view === 'benchmark' && <BenchmarkView dataset={dataset} />}
      </main>
    </div>
  </div>;
}
