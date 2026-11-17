import type { Graph } from './types';

export interface TeamSource {
  id: string; title: string; kind: 'award' | 'agency_guidance' | 'company_capability' | 'internal_brief';
  url: string | null; retrieved_at: string; text: string; notes: string[];
}
export interface TeamStatus { available: boolean; ready: boolean; reason: string; source_count: number; dataset_name: string | null; runtime_mode?: 'local'|'cloud'; busy?: boolean }
export type AgentRole = 'opportunity' | 'partner' | 'reviewer';
export interface ResearchAgent {
  role: AgentRole; name: string; session_id: string; status: 'complete' | 'error';
  report: string; source_ids: string[]; memory_excerpt: string; trace_recorded: boolean;
}
export interface TeamEvent {
  id: string; at: string; kind: string; title: string; detail: string;
  agent_role?: AgentRole; metrics?: Record<string, unknown>;
}
export interface Improvement {
  status: string; stages: { name: string; status: string; counts: Record<string, unknown>; reason?: string }[];
  lesson_count: number; lessons: { id: string; text: string }[];
  learning_verified: boolean; durable_recall_excerpt: string; notes: string[];
}
export interface TeamRun {
  id: string; created_at: string; updated_at: string;
  status: 'queued' | 'running' | 'awaiting_review' | 'improving' | 'complete' | 'error';
  stage: string; question: string; profile: string; events: TeamEvent[]; sources: TeamSource[];
  agents: ResearchAgent[]; before_report: string | null; after_report: string | null;
  review: { findings: string[]; suggested_learning: string } | null;
  improvement: Improvement | null; memory_graph: Graph | null;
  memory_stats: { nodes?: number; edges?: number; source_count: number; dataset_name: string } | null;
  error: string | null; fresh_session_id?: string;
}
