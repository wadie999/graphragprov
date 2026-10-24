import { useRef } from "react";
import { Maximize2, Network } from "lucide-react";

import type { EvidenceRole } from "../api/graphTypes";
import type { CaseSnapshot } from "../api/snapshotTypes";

import { EdgeInspector } from "./EdgeInspector";
import { GraphCanvas } from "./GraphCanvas";

export function GraphPanel(props: {
  snapshot: CaseSnapshot;
  activeOccurrenceIds: string[];
  activeRole?: EvidenceRole;
  onHoverOccurrences: (ids: string[]) => void;
  onSelectOccurrences: (ids: string[]) => void;
}) {
  const panelRef = useRef<HTMLElement>(null);
  const graph = props.snapshot.graph;

  async function toggleFullscreen() {
    const panel = panelRef.current;
    if (!panel) return;

    try {
      if (document.fullscreenElement === panel) {
        await document.exitFullscreen();
      } else {
        await panel.requestFullscreen();
      }
    } catch (error) {
      console.error(
        "Unable to toggle graph fullscreen:",
        error,
      );
    }
  }

  if (!graph) {
    return (
      <section className="panel empty-panel">
        Frozen graph unavailable
      </section>
    );
  }

  return (
    <section
      ref={panelRef}
      className="panel graph-panel"
    >
      <div className="panel-title">
        <span>
          <Network size={16} />
          Global RDF graph
        </span>

        <span className="graph-stats">
          {graph.nodes.length} nodes
          {" · "}
          {graph.edges.length} edges

          <button
            type="button"
            className="graph-expand-button"
            onClick={() => void toggleFullscreen()}
            aria-label="Toggle full-screen graph"
            title="Expand graph · Esc to exit"
          >
            <Maximize2 size={16} />
          </button>
        </span>
      </div>

      <GraphCanvas {...props} />

      <EdgeInspector
        snapshot={props.snapshot}
        activeOccurrenceIds={props.activeOccurrenceIds}
      />
    </section>
  );
}