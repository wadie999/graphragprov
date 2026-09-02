import {
  Maximize2,
  Network,
} from "lucide-react";

import type { EvidenceRole } from "../api/graphTypes";
import type { CaseSnapshot } from "../api/snapshotTypes";

import { EdgeInspector } from "./EdgeInspector";
import { GraphCanvas } from "./GraphCanvas";

export function GraphPanel(props: {
  snapshot: CaseSnapshot;

  activeOccurrenceIds: string[];

  activeRole?: EvidenceRole;

  onHoverOccurrences: (
    ids: string[],
  ) => void;

  onSelectOccurrences: (
    ids: string[],
  ) => void;
}) {
  const graph =
    props.snapshot.graph;

  if (!graph) {
    return (
      <section className="panel empty-panel">
        Frozen graph unavailable
      </section>
    );
  }

  return (
    <section className="panel graph-panel">
      <div className="panel-title">
        <span>
          <Network size={16} />
          Global RDF graph
        </span>

        <span className="graph-stats">
          {graph.nodes.length} nodes
          {" · "}
          {graph.edges.length} edges

          <Maximize2 size={14} />
        </span>
      </div>

      <GraphCanvas
        {...props}
      />

      <EdgeInspector
        snapshot={
          props.snapshot
        }
        activeOccurrenceIds={
          props.activeOccurrenceIds
        }
      />
    </section>
  );
}