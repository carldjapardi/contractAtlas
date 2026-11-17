export type Mode = 'baseline' | 'cognee';
export type View = 'explore' | 'awards' | 'benchmark';
export type EntityType = 'agency' | 'award' | 'recipient' | 'parent' | 'topic';
export interface Award {
  id: string; award_id: string; description: string; agency: string;
  sub_agency: string | null; recipient_id: string; recipient_name: string;
  recipient_uei: string | null; parent_uei: string | null; parent_name: string | null;
  obligation: number; start_date: string | null; end_date: string | null; source_url: string;
}
export interface Dataset {
  name: string; status: 'live_snapshot' | 'empty'; retrieved_at: string | null;
  fiscal_year: number; agency: string; keywords: string[]; award_count: number;
  recipient_count: number; total_obligation: number; snapshot_id: string | null;
  truncated: boolean; notes: string[];
}
export interface GraphNode {
  id: string; type: EntityType; label: string; sublabel: string; award_ids: string[];
}
export interface GraphEdge {
  id: string; source: string; target: string; relationship: string;
  origin: 'reported' | 'inferred'; award_ids: string[];
}
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean }
export interface Evidence {
  id: string; title: string; description: string; source_url: string;
  obligation: number; agency: string; recipient_name: string;
}
export interface Answer {
  answer: string; evidence: Evidence[]; graph: Graph; mode: Mode;
  elapsed_ms: number; coverage_notes: string[]; matched_count: number;
}
export interface Health { status: string; cognee: { available: boolean; ready: boolean; reason: string } }
export interface AwardsResponse { awards: Award[]; total: number }
export interface EvaluationResult {
  mode: Mode; status: 'ok' | 'unavailable' | 'error'; elapsed_ms: number;
  evidence_ids?: string[]; citation_validity: number | null; recall: number | null;
  precision: number | null; matched_count: number; error?: string;
  answer?: string; abstention_check?: boolean | null;
}
export interface Evaluation {
  status: string; snapshot_id?: string; generated_at?: string; scope_note?: string;
  corpus_comparable?: boolean | null; reason?: string;
  cases?: { id: string; question: string; category: string; expected_ids: string[]; results: EvaluationResult[] }[];
  summary?: { mode: Mode; completed: number; total: number; mean_elapsed_ms: number; citation_validity: number | null; mean_recall: number | null }[];
}
