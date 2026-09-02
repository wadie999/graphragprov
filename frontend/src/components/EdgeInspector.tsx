import type { CaseSnapshot } from "../api/snapshotTypes";

export function EdgeInspector(props: { snapshot: CaseSnapshot; activeOccurrenceIds: string[] }) {
  const graph = props.snapshot.graph;
  const occurrence = graph?.occurrences.find((item) => props.activeOccurrenceIds.includes(item.occurrence_id));
  if (!graph || !occurrence) return null;
  const edge = graph.edges.find((item) => item.edge_id === occurrence.semantic_edge_id);
  if (!edge) return null;
  const subject = graph.nodes.find((item) => item.node_id === edge.subject_node_id)?.label ?? "?";
  const object = graph.nodes.find((item) => item.node_id === edge.object_node_id)?.label ?? "?";
  const source = props.snapshot.sources.find((item) => item.source_id === occurrence.source_id);
  return (
    <aside className="edge-inspector">
      <strong>Grounded statement occurrence</strong>
      <dl>
        <dt>Subject</dt><dd>{subject}</dd>
        <dt>Predicate</dt><dd>{edge.predicate_label}</dd>
        <dt>Object</dt><dd>{object}</dd>
        <dt>Source</dt><dd>{source?.title ?? occurrence.source_id}</dd>
        <dt>Token</dt><dd title={occurrence.token}>{occurrence.token}</dd>
      </dl>
    </aside>
  );
}
