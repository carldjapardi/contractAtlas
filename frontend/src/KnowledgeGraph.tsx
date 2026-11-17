import { memo, useMemo } from 'react';
import {
  ReactFlow, Background, Controls, Handle, Position, MarkerType,
  type NodeProps, type Node, type Edge,
} from '@xyflow/react';
import { Building2, FileText, Landmark, Layers3, Network, Sparkles } from 'lucide-react';
import type { EntityType, Graph, GraphNode } from './types';

const icons = { agency: Landmark, recipient: Building2, award: FileText, parent: Layers3, topic: Sparkles };
const typeNames = { agency: 'Agency', recipient: 'Recipient', award: 'Contract award', parent: 'Ultimate parent', topic: 'Inferred topic' };
type EntityNode = Node<{ entity: GraphNode }, 'entity'>;

const EntityCard = memo(function EntityCard({ data, selected }: NodeProps<EntityNode>) {
  const entity = data.entity;
  const Icon = icons[entity.type] ?? Building2;
  return <div className={`entity-node entity-${entity.type} ${selected ? 'is-selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <div className="entity-kind"><Icon size={13} strokeWidth={1.8} /><span>{typeNames[entity.type]}</span></div>
    <div className="entity-name" title={entity.label}>{entity.label}</div>
    {entity.sublabel && <div className="entity-subtitle" title={entity.sublabel}>{entity.sublabel}</div>}
    <Handle type="source" position={Position.Right} />
  </div>;
});
const nodeTypes = { entity: EntityCard };

function positionNodes(graph: Graph, selectedId?: string): EntityNode[] {
  const kinds: EntityType[] = ['agency', 'award', 'recipient', 'parent', 'topic'];
  const columns = kinds.filter(kind => graph.nodes.some(node => node.type === kind));
  const recipients = graph.nodes.filter(node => node.type === 'recipient');
  const awards = graph.nodes.filter(node => node.type === 'award').sort((a, b) => {
    const group = (node: GraphNode) => recipients.findIndex(r => r.award_ids.some(id => node.award_ids.includes(id)));
    return group(a) - group(b) || a.label.localeCompare(b.label);
  });
  const count = Math.max(awards.length, recipients.length, 1);
  const height = (count - 1) * 136;
  const ys = new Map(awards.map((node, index) => [node.id, index * 136]));
  const positions = new Map<string, number>();
  for (const node of recipients) {
    const related = awards.filter(a => a.award_ids.some(id => node.award_ids.includes(id)));
    positions.set(node.id, related.length ? related.reduce((sum, a) => sum + (ys.get(a.id) ?? 0), 0) / related.length : recipients.indexOf(node) * 136);
  }
  return graph.nodes.map(node => {
    const peers = graph.nodes.filter(peer => peer.type === node.type);
    let y = peers.length === 1 ? height / 2 : (peers.indexOf(node) / (peers.length - 1)) * height;
    if (node.type === 'award') y = ys.get(node.id) ?? y;
    if (node.type === 'recipient') y = positions.get(node.id) ?? y;
    if (node.type === 'parent') {
      const related = recipients.filter(r => r.award_ids.some(id => node.award_ids.includes(id)));
      if (related.length) y = related.reduce((sum, r) => sum + (positions.get(r.id) ?? 0), 0) / related.length;
    }
    return { id: node.id, type: 'entity', data: { entity: node }, position: { x: columns.indexOf(node.type) * 250, y }, selected: node.id === selectedId };
  });
}

export default function KnowledgeGraph({ graph, selectedId, onSelect, loading }: {
  graph: Graph; selectedId?: string; onSelect: (node: GraphNode | null) => void; loading: boolean;
}) {
  const nodes = useMemo(() => positionNodes(graph, selectedId), [graph, selectedId]);
  const edges = useMemo<Edge[]>(() => graph.edges.map(edge => {
    const highlighted = edge.source === selectedId || edge.target === selectedId;
    return {
      id: edge.id, source: edge.source, target: edge.target,
      type: 'smoothstep', label: highlighted ? edge.relationship.replaceAll('_', ' ') : undefined,
      style: { stroke: highlighted ? '#247968' : '#b7c8c2', strokeWidth: highlighted ? 2 : 1.3, strokeDasharray: edge.origin === 'inferred' ? '5 5' : undefined },
      markerEnd: { type: MarkerType.ArrowClosed, color: highlighted ? '#247968' : '#b7c8c2', width: 14, height: 14 },
      labelStyle: { fill: '#42645a', fontSize: 10 }, labelBgStyle: { fill: '#f7f9f6', fillOpacity: .95 },
    };
  }), [graph.edges, selectedId]);
  if (!nodes.length) return <div className="graph-empty"><div className="empty-icon"><Network size={27} /></div>
    <h3>{loading ? 'Mapping the connections…' : 'A graph starts with evidence.'}</h3>
    <p>{loading ? 'Loading the frozen USAspending snapshot.' : 'Load a dataset or try another question to explore its relationships.'}</p>
  </div>;
  return <ReactFlow
    key={graph.nodes.map(n => n.id).join('|')}
    nodes={nodes} edges={edges} nodeTypes={nodeTypes}
    onNodeClick={(_, node) => onSelect(node.data.entity)}
    onPaneClick={() => onSelect(null)}
    fitView fitViewOptions={{ padding: .17 }} minZoom={.25} maxZoom={1.5}
    nodesConnectable={false} nodesDraggable panOnScroll selectionOnDrag={false}
    aria-label="Federal contract relationship graph"
  ><Background gap={20} size={1} color="#dce4df" /><Controls showInteractive={false} /></ReactFlow>;
}
