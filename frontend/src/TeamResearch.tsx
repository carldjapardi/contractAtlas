import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight, ArrowUpRight, BookOpen, Building2, Check, ChevronDown, CircleHelp,
  Database, FileText, GitBranch, History, Layers3, Lightbulb, LoaderCircle,
  MessageSquareText, Network, Play, RefreshCw, Search, ShieldCheck, Sparkles, Users, X,
} from 'lucide-react';
import { api } from './api';
import KnowledgeGraph from './KnowledgeGraph';
import type { GraphNode } from './types';
import type { AgentRole, ResearchAgent, TeamRun, TeamSource, TeamStatus } from './teamTypes';
import './team.css';

const demoQuestion = 'Find potential teaming partners for a small cybersecurity contractor researching DHS identity and access management work. Connect historical awards, agency guidance, and company capabilities. Identify evidence gaps before recommending a next step.';
const demoProfile = 'Hypothetical small cybersecurity contractor offering identity and access management implementation, cloud security, and compliance support. Certifications, past performance, and contract vehicles have not been verified.';
const roleInfo: { role: AgentRole; name: string; description: string; icon: typeof Search }[] = [
  { role: 'opportunity', name: 'Market researcher', description: 'Agency priorities and historical buying patterns.', icon: Search },
  { role: 'partner', name: 'Partner analyst', description: 'Capability fit and possible teaming connections.', icon: Users },
  { role: 'reviewer', name: 'Evidence reviewer', description: 'Unsupported claims, gaps, and reusable lessons.', icon: ShieldCheck },
];
const sourceKinds = {
  award: { label: 'Historical award', short: 'Award history', icon: FileText, note: 'Reported historical award, not an open solicitation.' },
  agency_guidance: { label: 'Official guidance', short: 'Agency guidance', icon: BookOpen, note: 'Official guidance describes priorities; it is not a solicitation.' },
  company_capability: { label: 'Self-reported capability', short: 'Company capabilities', icon: Building2, note: 'Company statements are self-reported, not independently verified.' },
  internal_brief: { label: 'Internal / demo brief', short: 'Internal brief', icon: MessageSquareText, note: 'Team research context, not a published government opportunity.' },
};
const activeStatus = (run: TeamRun | null | undefined) => Boolean(run && ['queued', 'running', 'improving'].includes(run.status));
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'The request could not be completed. Please try again.';
const timeLabel = (value: string) => new Date(value).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit', timeZone: 'America/Los_Angeles' });
const dateLabel = (value: string) => new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Los_Angeles' });
const runLabel = (status: TeamRun['status']) => ({ queued: 'Queued', running: 'Researching', awaiting_review: 'Ready for review', improving: 'Improving memory', complete: 'Complete', error: 'Needs attention' })[status];
function safeSourceUrl(value: string | null) { try { if (!value) return undefined; const parsed = new URL(value); return parsed.protocol === 'https:' ? parsed.href : undefined; } catch { return undefined; } }

function SourceDetail({ source, onClose }: { source: TeamSource; onClose: () => void }) {
  const meta = sourceKinds[source.kind];
  const href = safeSourceUrl(source.url);
  return <section className="team-source-detail" aria-label="Selected source"><div className="team-section-heading"><div><span className={`team-kind kind-${source.kind}`}>{meta.label}</span><h3>{source.title}</h3></div><button className="icon-button" aria-label="Close source" onClick={onClose}><X size={17} /></button></div><p className="team-source-caution">{meta.note}</p><details open><summary>Read collected source text <ChevronDown size={14} /></summary><pre>{source.text || 'Source text is not available.'}</pre></details>{source.notes?.map((note, index) => <p className="team-source-note" key={index}>{note}</p>)}<div className="team-source-meta"><span>Source ID · {source.id}</span>{href && <a href={href} target="_blank" rel="noreferrer">Open original source <ArrowUpRight size={14} /></a>}</div></section>;
}

function AgentReport({ agent, sources, onSource }: { agent: ResearchAgent; sources: TeamSource[]; onSource: (source: TeamSource) => void }) {
  return <div className="team-agent-report"><div className="team-report-meta"><span><span className={`status-dot ${agent.status === 'error' ? 'offline' : ''}`} />{agent.status === 'complete' ? 'Research complete' : 'Agent error'}</span><span>{agent.trace_recorded ? 'Session recorded' : 'Trace not confirmed'}</span></div><p className="team-report-text">{agent.report}</p>{Boolean(agent.source_ids?.length) && <div className="team-source-references"><span>Linked sources</span>{agent.source_ids.map(id => { const source = sources.find(item => item.id === id); return source ? <button key={id} onClick={() => onSource(source)}><FileText size={12} />{source.title}<ArrowUpRight size={11} /></button> : <span key={id} className="team-unresolved-source">{id.startsWith('learning:') ? 'Learned team guidance · see retrieved memory' : `Source outside this collection: ${id}`}</span>; })}</div>}<details className="team-memory-excerpt"><summary><Database size={14} /> Retrieved shared memory <ChevronDown size={14} /></summary><pre>{agent.memory_excerpt || 'No memory excerpt was recorded for this agent.'}</pre></details><div className="team-session-id">Session · {agent.session_id}</div></div>;
}

export default function TeamResearch() {
  const [status, setStatus] = useState<TeamStatus | null>(null);
  const [sources, setSources] = useState<TeamSource[]>([]);
  const [runs, setRuns] = useState<TeamRun[]>([]);
  const [run, setRun] = useState<TeamRun | null>(null);
  const [question, setQuestion] = useState(demoQuestion);
  const [profile, setProfile] = useState(demoProfile);
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [agentRole, setAgentRole] = useState<AgentRole>('opportunity');
  const [selectedSource, setSelectedSource] = useState<TeamSource | null>(null);
  const [graphSelection, setGraphSelection] = useState<GraphNode | null>(null);
  const [allSourcesOpen, setAllSourcesOpen] = useState(false);
  const [showInputs, setShowInputs] = useState(true);
  const [fullGraph, setFullGraph] = useState(false);
  const [loadGeneration, setLoadGeneration] = useState(0);
  const initializedFeedbackFor = useRef('');
  const sourceDetailRef = useRef<HTMLDivElement>(null);
  const busy = submitting || activeStatus(run) || Boolean(status?.busy) || runs.some(item => activeStatus(item) && item.id !== run?.id);
  const collection = run?.sources?.length ? run.sources : sources;
  const displayedGraph = useMemo(() => {
    const graph = run?.memory_graph;
    if (!graph || fullGraph || graph.nodes.length <= 16) return graph;
    const semantic = graph.nodes.filter(node => !/NodeSet|EntityType|TextSummary|DocumentChunk|TextDocument/.test(node.sublabel));
    const selected = semantic.slice(0, 16);
    const ids = new Set(selected.map(node => node.id));
    return {nodes: selected, edges: graph.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)), truncated: true};
  }, [run?.memory_graph, fullGraph]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    Promise.allSettled([api<TeamStatus>('/team/status'), api<TeamSource[] | { sources: TeamSource[] }>('/team/sources'), api<{ runs: TeamRun[] }>('/team/runs')]).then(results => {
      if (cancelled) return;
      if (results[0].status === 'fulfilled') setStatus(results[0].value);
      else setError('The research team service is unavailable. Refresh when the service is ready.');
      if (results[1].status === 'fulfilled') setSources(Array.isArray(results[1].value) ? results[1].value : results[1].value.sources);
      if (results[2].status === 'fulfilled') {
        const items = results[2].value.runs; setRuns(items);
        const latest = items.find(item => activeStatus(item)) ?? items[0] ?? null;
        setRun(latest);
        if (latest) { setQuestion(latest.question); setProfile(latest.profile); setShowInputs(false); }
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [loadGeneration]);

  useEffect(() => {
    let cancelled = false;
    const timer = setInterval(() => { api<TeamStatus>('/team/status').then(value => { if (!cancelled) setStatus(value); }).catch(() => {}); }, 10000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!run || !activeStatus(run)) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await api<TeamRun>(`/team/runs/${encodeURIComponent(run!.id)}`);
        if (cancelled) return;
        setRun(value); setPollError('');
        setRuns(items => [value, ...items.filter(item => item.id !== value.id)].slice(0, 10));
        if (activeStatus(value)) timer = setTimeout(poll, 2000);
        else api<TeamStatus>('/team/status').then(setStatus).catch(() => {});
      } catch {
        if (!cancelled) { setPollError('Progress updates paused. We’ll retry automatically; the research job may still be running.'); timer = setTimeout(poll, 4000); }
      }
    }
    timer = setTimeout(poll, 1500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [run?.id, run?.status]);

  useEffect(() => {
    if (run?.review && initializedFeedbackFor.current !== run.id) {
      setFeedback(run.review.suggested_learning || ''); initializedFeedbackFor.current = run.id;
    }
  }, [run?.id, run?.review]);

  function chooseSource(source: TeamSource) {
    setSelectedSource(source);
    setTimeout(() => sourceDetailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 80);
  }

  async function startResearch() {
    if (busy || question.trim().length < 10 || profile.trim().length < 10) return;
    setSubmitting(true); setError(''); setSelectedSource(null); setGraphSelection(null);
    try {
      const created = await api<TeamRun>('/team/runs', { method: 'POST', body: JSON.stringify({ question: question.trim(), profile: profile.trim() }) });
      setRun(created); setRuns(items => [created, ...items.filter(item => item.id !== created.id)].slice(0, 10));
      setFeedback(''); initializedFeedbackFor.current = ''; setShowInputs(false); setAgentRole('opportunity');
    } catch (error) { setError(errorMessage(error)); }
    finally { setSubmitting(false); }
  }

  async function improveMemory() {
    if (!run || busy || feedback.trim().length < 10 || run.status !== 'awaiting_review') return;
    setSubmitting(true); setError('');
    try {
      const updated = await api<TeamRun>(`/team/runs/${encodeURIComponent(run.id)}/improve`, { method: 'POST', body: JSON.stringify({ feedback: feedback.trim() }) });
      setRun(updated); setRuns(items => [updated, ...items.filter(item => item.id !== updated.id)].slice(0, 10));
    } catch (error) { setError(errorMessage(error)); }
    finally { setSubmitting(false); }
  }

  async function selectRun(id: string) {
    if (busy) return;
    setError('');
    try {
      const value = await api<TeamRun>(`/team/runs/${encodeURIComponent(id)}`);
      setRun(value); setQuestion(value.question); setProfile(value.profile); setSelectedSource(null); setGraphSelection(null); setShowInputs(false);
      initializedFeedbackFor.current = ''; setFeedback(value.review?.suggested_learning || '');
    } catch (error) { setError(errorMessage(error)); }
  }

  const selectedAgent = run?.agents?.find(agent => agent.role === agentRole);
  const improvement = run?.improvement;
  const sourceGroups = Object.entries(sourceKinds).map(([kind, meta]) => ({ kind, ...meta, items: collection.filter(source => source.kind === kind) })).filter(group => group.items.length);
  return <div className="team-workspace">
    <div className="team-hero"><div><span className="eyebrow">BUSINESS DEVELOPMENT · SHARED RESEARCH MEMORY</span><h1>A research team that remembers<span>.</span></h1><p>Connect agency needs, award history, and company capabilities.<br className="team-desktop-break" /> Review the findings. Carry what you learn into the next session.</p></div><div className="team-readiness"><span className={`status-dot ${status?.ready ? '' : 'offline'}`} /><span>{loading ? 'Connecting…' : status?.ready ? `${status.runtime_mode === 'cloud' ? 'Cognee Cloud' : 'Local'} memory ready` : 'Memory setup pending'}</span><button className="icon-button" aria-label="Refresh research workspace" onClick={() => setLoadGeneration(value => value + 1)} disabled={busy || loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /></button></div></div>
    {error && <div className="inline-error team-error" role="alert"><CircleHelp size={17} /><span>{error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={15} /></button></div>}
    {!loading && !status?.ready && <div className="team-setup-notice"><Database size={17} /><div><strong>{status?.available ? 'The shared source collection is being prepared.' : 'Research memory is not available yet.'}</strong><p>{status?.reason || 'The research team service must be ready before starting a run.'}</p></div></div>}
    <section className="team-brief-card"><div className="team-section-heading"><div><span className="team-section-icon"><MessageSquareText size={17} /></span><h2>Your research brief</h2><span className="team-demo-label">{run ? 'Run inputs' : 'Editable demo defaults'}</span></div><button className="text-button" aria-expanded={showInputs} onClick={() => setShowInputs(!showInputs)}>{showInputs ? 'Collapse' : 'View / edit'}<ChevronDown size={13} className={showInputs ? 'rotate' : ''} /></button></div>
      {showInputs && <div className="team-brief-inputs"><label><span>What should the team investigate?</span><textarea value={question} onChange={event => setQuestion(event.target.value)} maxLength={4000} disabled={busy} rows={4} /><small>Market and teaming research. This is not a live solicitation.</small></label><label><span>Your company profile</span><textarea value={profile} onChange={event => setProfile(event.target.value)} maxLength={4000} disabled={busy} rows={4} /><small>Hypothetical profile. Replace it with verified company information.</small></label></div>}
      {!showInputs && <p className="team-brief-preview">{question}</p>}
      <div className="team-brief-footer"><span><Layers3 size={14} /> Three roles · one shared source collection</span><button className="team-primary" onClick={() => void startResearch()} disabled={busy || loading || !status?.ready || question.trim().length < 10 || profile.trim().length < 10}>{submitting || activeStatus(run) ? <LoaderCircle className="spin" size={15} /> : <Play size={14} />}{busy ? run?.status === 'improving' ? 'Improving memory…' : 'Research in progress…' : run ? 'Start a new research run' : 'Start team research'}{!busy && <ArrowRight size={15} />}</button></div>
    </section>
    <section className="team-source-collection"><div className="team-section-heading"><div><Database size={17} /><h2>Shared source collection</h2><span className="count-badge">{collection.length} sources</span></div><button className="text-button" onClick={() => setAllSourcesOpen(!allSourcesOpen)} aria-expanded={allSourcesOpen}>{allSourcesOpen ? 'Hide sources' : 'Inspect sources'}<ChevronDown size={13} className={allSourcesOpen ? 'rotate' : ''} /></button></div><div className="team-source-groups">{sourceGroups.map(group => <button key={group.kind} className={`team-source-group kind-${group.kind}`} onClick={() => { setAllSourcesOpen(true); chooseSource(group.items[0]); }}><span className="team-source-group-icon"><group.icon size={18} /></span><span><strong>{group.short}</strong><small>{group.items.length} {group.items.length === 1 ? 'document' : 'documents'}</small></span><ArrowUpRight size={14} /></button>)}{!sourceGroups.length && <p className="team-empty-inline">No source documents are loaded yet. Real source text will appear here once the collection is ready.</p>}</div>
      {allSourcesOpen && <div className="team-source-list">{collection.map(source => <button key={source.id} onClick={() => chooseSource(source)} className={selectedSource?.id === source.id ? 'selected' : ''}><span className={`team-kind kind-${source.kind}`}>{sourceKinds[source.kind].label}</span><span>{source.title}</span><ChevronDown size={13} /></button>)}</div>}
    </section>
    <div ref={sourceDetailRef}>{selectedSource && <SourceDetail source={selectedSource} onClose={() => setSelectedSource(null)} />}</div>
    <section className="team-run-workspace"><div className="team-run-heading"><div><span className="eyebrow">THE TEAM AT WORK</span><h2>Different perspectives. Shared context.</h2></div>{runs.length > 0 && <label className="team-run-selector"><History size={15} /><span className="sr-only">Select research run</span><select value={run?.id || ''} onChange={event => void selectRun(event.target.value)} disabled={busy}>{runs.map(item => <option key={item.id} value={item.id}>{dateLabel(item.created_at)} · {runLabel(item.status)}</option>)}</select></label>}</div>
      <div className="team-agent-grid">{roleInfo.map(item => {
        const agent = run?.agents?.find(agent => agent.role === item.role);
        const roleWorking = activeStatus(run) && run?.events?.some(event => event.agent_role === item.role) && !agent;
        return <button key={item.role} className={`team-agent-card ${agentRole === item.role && agent ? 'selected' : ''}`} onClick={() => setAgentRole(item.role)} disabled={!agent} aria-pressed={agentRole === item.role && Boolean(agent)}><div className="team-agent-top"><span className={`team-role-icon role-${item.role}`}><item.icon size={20} /></span><span className={`team-agent-state ${agent?.status === 'complete' ? 'complete' : ''}`}>{agent ? agent.status === 'complete' ? <><Check size={11} /> Complete</> : 'Error' : roleWorking ? <><LoaderCircle size={11} className="spin" /> Working</> : run ? 'Waiting' : 'Ready to research'}</span></div><h3>{agent?.name || item.name}</h3><p>{item.description}</p><span className="team-agent-bottom">{agent ? 'Inspect report & memory' : 'Findings appear after a real agent run'}<ArrowRight size={13} /></span></button>;
      })}</div>
      {run && <div className="team-active-status"><span className={`team-run-status ${activeStatus(run) ? 'is-active' : ''}`}>{activeStatus(run) ? <LoaderCircle size={13} className="spin" /> : run.status === 'error' ? <CircleHelp size={13} /> : <Check size={13} />}{runLabel(run.status)}</span><span>{run.stage}</span><small>Run {run.id.slice(0, 12)}</small></div>}
      {pollError && <p className="team-poll-error" role="status">{pollError}</p>}
      {run?.error && <div className="inline-error team-run-error" role="alert">{run.error}</div>}
      {!run && <div className="team-first-run"><span className="team-first-run-icon"><Network size={27} strokeWidth={1.4} /></span><div><h3>The next session shouldn’t start from zero.</h3><p>Start a research run to see actual agent reports, shared-memory retrieval, and an evidence review. Nothing is generated until you start.</p></div></div>}
      {run && <div className="team-research-columns"><div className="team-report-panel"><div className="team-section-heading"><div><BookOpen size={17} /><h3>{selectedAgent?.name || roleInfo.find(item => item.role === agentRole)?.name}</h3></div><span className="team-panel-subtitle">Agent report</span></div>{selectedAgent ? <AgentReport key={selectedAgent.session_id} agent={selectedAgent} sources={collection} onSource={chooseSource} /> : <div className="team-report-pending"><LoaderCircle size={23} className={activeStatus(run) ? 'spin' : ''} /><h3>{activeStatus(run) ? 'Gathering evidence and shared context…' : 'No report recorded for this role.'}</h3><p>Reports appear as each research agent completes its work.</p></div>}</div><aside className="team-timeline-panel"><div className="team-section-heading"><div><GitBranch size={16} /><h3>Live activity</h3></div><span className="count-badge">{run.events?.length ?? 0}</span></div><div className="team-timeline" role="log" aria-live="polite" aria-label="Research progress">{run.events?.length ? [...run.events].reverse().map(event => <article className={`team-event event-${event.kind}`} key={event.id}><span className="team-event-dot" /><div><div className="team-event-meta"><span>{event.agent_role ? roleInfo.find(item => item.role === event.agent_role)?.name : 'Shared memory'}</span><time>{timeLabel(event.at)}</time></div><h4>{event.title}</h4><p>{event.detail}</p>{event.metrics && Object.keys(event.metrics).length > 0 && <details><summary>Recorded metrics <ChevronDown size={12} /></summary><pre>{JSON.stringify(event.metrics, null, 2)}</pre></details>}</div></article>) : <p className="team-empty-inline">Waiting for the first recorded event…</p>}</div></aside></div>}
    </section>
    {run?.review && <section className="team-review-section"><div className="team-section-heading"><div><span className="team-section-icon"><ShieldCheck size={18} /></span><h2>Review once. Remember next time.</h2></div><span className="team-step-label">HUMAN REVIEW</span></div><div className="team-review-grid"><div className="team-review-findings"><span className="eyebrow">WHAT THE REVIEWER FOUND</span>{run.review.findings?.length ? <ul>{run.review.findings.map((finding, index) => <li key={index}>{finding}</li>)}</ul> : <p>No reviewer findings were recorded.</p>}<details className="team-before-checkpoint"><summary><History size={14} /> Original research checkpoint <ChevronDown size={14} /></summary><p>{run.before_report || 'No before checkpoint was recorded.'}</p></details></div><div className="team-learning-input"><label htmlFor="team-review-feedback">Accepted team lesson</label><p>Edit the reviewer’s suggestion before adding it to shared memory.</p><textarea id="team-review-feedback" value={feedback} onChange={event => setFeedback(event.target.value)} rows={6} maxLength={4000} disabled={busy || run.status !== 'awaiting_review'} placeholder="State a specific, evidence-grounded correction or reusable research lesson…" /><button className="team-primary" onClick={() => void improveMemory()} disabled={busy || run.status !== 'awaiting_review' || feedback.trim().length < 10}>{run.status === 'improving' ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}{run.status === 'improving' ? 'Improving team memory…' : 'Improve team memory'}<ArrowRight size={15} /></button><small>The original report stays unchanged. A fresh session will test what the team retained.</small></div></div></section>}
    {improvement && <section className="team-improvement-section"><div className="team-section-heading"><div><span className="team-section-icon"><Lightbulb size={18} /></span><h2>What the team actually learned</h2></div><span className={`team-learning-status ${improvement.learning_verified ? 'verified' : ''}`}>{improvement.learning_verified ? <ShieldCheck size={13} /> : <CircleHelp size={13} />}{improvement.learning_verified ? 'Durable learning verified' : 'Learning not verified'}</span></div><div className="team-improvement-stats"><div><strong>{improvement.lesson_count ?? 0}</strong><span>New lessons recorded</span></div><div><strong>{improvement.stages?.filter(stage => stage.status === 'completed' || stage.status === 'complete' || stage.status === 'success').length ?? 0}<small> / {improvement.stages?.length ?? 0}</small></strong><span>Improvement stages completed</span></div><div><strong>{run.fresh_session_id ? 'New session' : 'Not recorded'}</strong><span>Independent memory recall</span></div></div><div className="team-stage-table"><table><thead><tr><th>Improvement stage</th><th>Status</th><th>Recorded counts</th></tr></thead><tbody>{improvement.stages?.map((stage, index) => <tr key={`${stage.name}-${index}`}><td><strong>{stage.name.replaceAll('_', ' ')}</strong>{stage.reason && <p>{stage.reason}</p>}</td><td><span className="team-stage-status">{stage.status}</span></td><td>{Object.entries(stage.counts || {}).length ? <div className="team-stage-counts">{Object.entries(stage.counts).map(([key, value]) => <span key={key}>{key.replaceAll('_', ' ')} <strong>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</strong></span>)}</div> : 'No counts reported'}</td></tr>)}</tbody></table></div>
      {improvement.lessons?.length > 0 && <div className="team-learned-lessons"><span className="eyebrow">RECORDED LESSONS</span>{improvement.lessons.map(lesson => <article key={lesson.id}><Lightbulb size={17} /><div><p>{lesson.text}</p><span>{lesson.id}</span></div></article>)}</div>}
      {improvement.lesson_count === 0 && <div className="team-zero-lessons"><CircleHelp size={17} /><p>No new lessons were recorded. Completed processing stages alone do not establish that the system learned.</p></div>}
      <div className="team-before-after"><article><div><History size={16} /><h3>Before review</h3><span>Preserved checkpoint</span></div><p>{run.before_report || 'No original checkpoint was recorded.'}</p></article><article><div><Sparkles size={16} /><h3>Fresh-session research</h3><span>After improvement</span></div><p>{run.after_report || 'No fresh-session report has been recorded yet.'}</p></article></div><div className="team-durable-proof"><div className="team-section-heading"><div><Database size={17} /><h3>Shared memory, retrieved in a fresh session</h3></div></div><p>The original research brief and company profile are reused. The accepted correction is not copied into the fresh agent’s prompt.</p><pre>{improvement.durable_recall_excerpt || 'No durable-memory recall excerpt was captured.'}</pre>{run.fresh_session_id && <span className="team-session-id">Fresh session · {run.fresh_session_id}</span>}</div>{improvement.notes?.map((note, index) => <p className="team-improvement-note" key={index}>{note}</p>)}</section>}
    {run?.memory_graph && <section className="team-memory-graph"><div className="team-section-heading"><div><Network size={17} /><h2>The shared memory map</h2><span className="count-badge">{displayedGraph?.nodes.length} of {run.memory_graph.nodes.length} nodes</span></div><button className="text-button" onClick={() => setFullGraph(value => !value)}>{fullGraph ? 'Focus on concepts' : 'Show full graph'}</button></div><div className="team-graph-canvas"><KnowledgeGraph graph={displayedGraph || run.memory_graph} selectedId={graphSelection?.id} onSelect={node => { setGraphSelection(node); const source = collection.find(item => node?.award_ids.includes(item.id)); if (source) chooseSource(source); }} loading={false} /></div>{graphSelection && <div className="team-graph-selection"><strong>{graphSelection.label}</strong><span>{graphSelection.sublabel}</span><div>{graphSelection.award_ids.map(id => { const source = collection.find(item => item.id === id); return source ? <button key={id} onClick={() => chooseSource(source)}>{source.title}<ArrowUpRight size={12} /></button> : <span key={id}>{id}</span>; })}</div></div>}<div className="team-graph-note">Showing part of Cognee’s memory graph. Use the reports’ source links to check the collected evidence.</div></section>}
    <footer className="team-footer"><span><ShieldCheck size={13} /> Interpretations remain separate from reported facts.</span><span>Historical awards · official guidance · self-reported capabilities</span></footer>
  </div>;
}
