import { MultiGraph } from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";

import type { CaseSnapshot } from "../api/snapshotTypes";
import { GRAPH_VISUAL } from "./visualConfig";

export type RenderGraph = MultiGraph;

export function buildRenderGraph(
  snapshot: CaseSnapshot,
): RenderGraph {
  const graph = new MultiGraph();

  const nodes = snapshot.graph?.nodes ?? [];
  const edges = snapshot.graph?.edges ?? [];

  for (const node of nodes) {
    const angle = seed(node.node_id) * Math.PI * 2;
    const radius = 1 + seed(`${node.node_id}:r`) * 3;

    graph.addNode(node.node_id, {
      label: node.label,
      kind: node.kind,

      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,

      size:
        node.kind === "literal"
          ? GRAPH_VISUAL.nodes.literalSize
          : GRAPH_VISUAL.nodes.entitySize,

      color:
        node.kind === "literal"
          ? GRAPH_VISUAL.nodes.literalColor
          : GRAPH_VISUAL.nodes.entityColor,

      forceLabel:
        node.kind !== "literal" &&
        nodes.length <
          GRAPH_VISUAL.labels.forceNodeLabelsBelow,
    });
  }

  for (const edge of edges) {
    if (
      !graph.hasNode(edge.subject_node_id) ||
      !graph.hasNode(edge.object_node_id)
    ) {
      continue;
    }

    graph.addDirectedEdgeWithKey(
      edge.edge_id,
      edge.subject_node_id,
      edge.object_node_id,
      {
        type: "arrow",
        label: edge.predicate_label,

        size: GRAPH_VISUAL.edges.size,
        color: GRAPH_VISUAL.edges.color,

        occurrenceIds: edge.occurrence_ids,

        forceLabel:
          edges.length <
          GRAPH_VISUAL.labels.forceEdgeLabelsBelow,
      },
    );
  }

  separateParallelEdges(graph);
  layoutGraph(graph);

  return graph;
}

function separateParallelEdges(graph: RenderGraph): void {
  const groups = new Map<string, string[]>();

  // Group edges by unordered endpoints, including edges
  // pointing in opposite directions.
  graph.forEachEdge((edge) => {
    const source = graph.source(edge);
    const target = graph.target(edge);

    const endpoints =
      source < target
        ? [source, target]
        : [target, source];

    const key = JSON.stringify(endpoints);
    const group = groups.get(key);

    if (group) {
      group.push(edge);
    } else {
      groups.set(key, [edge]);
    }
  });

  for (const group of groups.values()) {
    if (group.length < 2) continue;

    // Stable ordering keeps each edge on the same side
    // when the graph is rebuilt.
    group.sort();

    const middle = (group.length - 1) / 2;

    group.forEach((edge, index) => {
      const source = graph.source(edge);
      const target = graph.target(edge);

      // Self-loops require a dedicated loop renderer.
      if (source === target) return;

      const offset = index - middle;

      // With an odd number of parallel edges, keep
      // the middle edge straight.
      if (offset === 0) {
        graph.mergeEdgeAttributes(edge, {
          type: "arrow",
          curvature: 0,
        });
        return;
      }

      // Reverse the sign for reverse-direction edges
      // so every edge occupies a distinct physical path.
      const direction = source < target ? 1 : -1;

      graph.mergeEdgeAttributes(edge, {
        type: "curved",
        curvature: direction * offset * 0.35,
      });
    });
  }
}

function layoutGraph(graph: RenderGraph): void {
  if (graph.order < 2) return;

  const inferred = forceAtlas2.inferSettings(graph);

  const iterations =
    graph.order > GRAPH_VISUAL.layout.largeGraphThreshold
      ? GRAPH_VISUAL.layout.largeGraphIterations
      : GRAPH_VISUAL.layout.smallGraphIterations;

  forceAtlas2.assign(graph, {
    iterations,
    settings: {
      ...inferred,
      gravity: GRAPH_VISUAL.layout.gravity,
      scalingRatio: GRAPH_VISUAL.layout.scalingRatio,
    },
  });
}

function seed(value: string): number {
  let hash = 2166136261;

  for (let index = 0; index < value.length; index += 1) {
    hash = Math.imul(
      hash ^ value.charCodeAt(index),
      16777619,
    );
  }

  return ((hash >>> 0) % 10000) / 10000;
}