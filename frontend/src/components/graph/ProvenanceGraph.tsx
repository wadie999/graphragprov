import cytoscape, {
  type Core,
  type ElementDefinition,
} from "cytoscape";
import { useEffect, useMemo, useRef } from "react";

import type {
  EvidenceOccurrence,
  ProvenanceDerivation,
} from "../../domain/provenance";

interface ProvenanceGraphProps {
  derivation: ProvenanceDerivation | null;
  selectedOccurrenceIndex: number | null;
  onSelectOccurrence: (occurrenceIndex: number) => void;
}

export function ProvenanceGraph({
  derivation,
  selectedOccurrenceIndex,
  onSelectOccurrence,
}: ProvenanceGraphProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cytoscapeRef = useRef<Core | null>(null);

  const elements = useMemo(
    () => buildElements(derivation),
    [derivation],
  );

  useEffect(() => {
    if (containerRef.current === null) {
      return;
    }

    const instance = cytoscape({
      container: containerRef.current,
      elements,
      layout: {
        name: "breadthfirst",
        directed: true,
        padding: 20,
        spacingFactor: 1.2,
      },
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "#ffffff",
            "border-color": "#333333",
            "border-width": 1,
            color: "#111111",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": "130px",
            width: 34,
            height: 34,
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            width: 1,
            "line-color": "#555555",
            "target-arrow-color": "#555555",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "font-size": 10,
            "text-background-color": "#ffffff",
            "text-background-opacity": 1,
            "text-background-padding": "2px",
          },
        },
        {
          selector: ".selected-occurrence",
          style: {
            "border-width": 3,
            width: 3,
            "line-color": "#000000",
            "target-arrow-color": "#000000",
          },
        },
      ],
    });

    instance.on("tap", "edge", (event) => {
      const index = event.target.data("occurrenceIndex");

      if (typeof index === "number") {
        onSelectOccurrence(index);
      }
    });

    instance.on("tap", "node", (event) => {
      const indexes = event.target.data("occurrenceIndexes");

      if (Array.isArray(indexes) && typeof indexes[0] === "number") {
        onSelectOccurrence(indexes[0]);
      }
    });

    cytoscapeRef.current = instance;

    return () => {
      instance.destroy();
      cytoscapeRef.current = null;
    };
  }, [elements, onSelectOccurrence]);

  useEffect(() => {
    const instance = cytoscapeRef.current;

    if (instance === null) {
      return;
    }

    instance.elements().removeClass("selected-occurrence");

    if (selectedOccurrenceIndex === null) {
      return;
    }

    instance
      .edges(`[occurrenceIndex = ${selectedOccurrenceIndex}]`)
      .addClass("selected-occurrence");

    instance
      .nodes()
      .filter((node) => {
        const indexes = node.data("occurrenceIndexes");
        return (
          Array.isArray(indexes) &&
          indexes.includes(selectedOccurrenceIndex)
        );
      })
      .addClass("selected-occurrence");
  }, [selectedOccurrenceIndex]);

  if (derivation === null || derivation.occurrences.length === 0) {
    return <p>No derivation graph is available.</p>;
  }

  return (
    <div
      ref={containerRef}
      className="provenance-graph"
      aria-label="Selected provenance derivation graph"
    />
  );
}

function buildElements(
  derivation: ProvenanceDerivation | null,
): ElementDefinition[] {
  if (derivation === null) {
    return [];
  }

  const elements: ElementDefinition[] = [];
  const nodeIndexes = new Map<string, number[]>();

  derivation.occurrences.forEach((occurrence, index) => {
    const subject = evidenceLabel(
      occurrence,
      "subject_evidence",
      "subject",
    );
    const predicate = evidenceLabel(
      occurrence,
      "predicate_evidence",
      "predicate",
    );
    const object = evidenceLabel(
      occurrence,
      "object_evidence",
      "object",
    );
    const subjectId = nodeId(subject);
    const objectId = nodeId(object);

    addNodeIndex(nodeIndexes, subjectId, index);
    addNodeIndex(nodeIndexes, objectId, index);

    elements.push({
      data: {
        id: `edge-${index}-${occurrence.triple_hash || occurrence.token}`,
        source: subjectId,
        target: objectId,
        label: predicate,
        occurrenceIndex: index,
      },
    });
  });

  for (const [id, indexes] of nodeIndexes.entries()) {
    elements.push({
      data: {
        id,
        label: id.slice("node:".length),
        occurrenceIndexes: indexes,
      },
    });
  }

  return elements;
}

function evidenceLabel(
  occurrence: EvidenceOccurrence,
  key:
    | "subject_evidence"
    | "predicate_evidence"
    | "object_evidence",
  fallback: string,
): string {
  const label = occurrence[key]
    .map((span) => span.quote.trim())
    .filter(Boolean)
    .join(" / ");

  return label || fallback;
}

function nodeId(label: string): string {
  return `node:${label.trim().toLowerCase()}`;
}

function addNodeIndex(
  map: Map<string, number[]>,
  node: string,
  index: number,
): void {
  const current = map.get(node) ?? [];

  if (!current.includes(index)) {
    current.push(index);
  }

  map.set(node, current);
}
