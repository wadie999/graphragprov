import { useEffect, useMemo, useRef } from "react";
import Sigma from "sigma";

import type { EvidenceRole } from "../api/graphTypes";
import type { CaseSnapshot } from "../api/snapshotTypes";
import {
  buildRenderGraph,
  type RenderGraph,
} from "../graph/buildGraph";
import { GRAPH_VISUAL } from "../graph/visualConfig";

export function GraphCanvas(props: {
  snapshot: CaseSnapshot;
  activeOccurrenceIds: string[];
  activeRole?: EvidenceRole;
  onHoverOccurrences: (ids: string[]) => void;
  onSelectOccurrences: (ids: string[]) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const renderer = useRef<Sigma | null>(null);

  const active = useRef<string[]>(
    props.activeOccurrenceIds,
  );

  const activeRole = useRef<
    EvidenceRole | undefined
  >(props.activeRole);

  const hoveredEdge = useRef<
    string | null
  >(null);

  const callbacks = useRef({
    hover: props.onHoverOccurrences,
    select: props.onSelectOccurrences,
  });

  const graph = useMemo(
    () =>
      buildRenderGraph(
        props.snapshot,
      ),
    [props.snapshot],
  );

  useEffect(() => {
    callbacks.current = {
      hover:
        props.onHoverOccurrences,
      select:
        props.onSelectOccurrences,
    };
  }, [
    props.onHoverOccurrences,
    props.onSelectOccurrences,
  ]);

  useEffect(() => {
    active.current =
      props.activeOccurrenceIds;

    activeRole.current =
      props.activeRole;

    stableRefresh(
      renderer.current,
    );
  }, [
    props.activeOccurrenceIds,
    props.activeRole,
  ]);

  useEffect(() => {
    if (!container.current) {
      return;
    }

    const sigma = new Sigma(
      graph,
      container.current,
      {
        enableEdgeEvents: true,

        renderEdgeLabels: true,

        hideEdgesOnMove: false,
        hideLabelsOnMove: false,

        labelDensity:
          GRAPH_VISUAL.labels
            .density,

        labelGridCellSize:
          GRAPH_VISUAL.labels
            .gridCellSize,

        labelRenderedSizeThreshold:
          GRAPH_VISUAL.labels
            .renderedSizeThreshold,

        labelSize:
          GRAPH_VISUAL.labels
            .nodeSize,

        labelWeight: "500",

        labelColor: {
          color:
            GRAPH_VISUAL.labels
              .nodeColor,
        },

        edgeLabelSize:
          GRAPH_VISUAL.labels
            .edgeSize,

        edgeLabelWeight: "600",

        edgeLabelColor: {
          color:
            GRAPH_VISUAL.labels
              .edgeColor,
        },

        stagePadding:
          GRAPH_VISUAL.stage
            .padding,

        zIndex: true,

        nodeReducer: (
          node,
          data,
        ) =>
          nodeDisplay(
            props.snapshot,
            graph,
            node,
            data,
            active.current,
            activeRole.current,
          ),

        edgeReducer: (
          edge,
          data,
        ) =>
          edgeDisplay(
            props.snapshot,
            graph,
            edge,
            data,
            active.current,
            activeRole.current,
            hoveredEdge.current,
          ),
      },
    );

    renderer.current = sigma;

    const camera = sigma.getCamera();
    const syncLabelSizes = () => {
      const scale = Math.min(
        2.5,
        Math.max(0.8, 1 / Math.sqrt(camera.getState().ratio)),
      );
      sigma.setSettings({
        labelSize: GRAPH_VISUAL.labels.nodeSize * scale,
        edgeLabelSize: GRAPH_VISUAL.labels.edgeSize * scale,
      });
    };

    camera.on("updated", syncLabelSizes);
    syncLabelSizes();

    sigma.on(
      "enterEdge",
      ({ edge }) => {
        hoveredEdge.current =
          edge;

        callbacks.current.hover(
          edgeOccurrences(
            graph,
            edge,
          ),
        );

        stableRefresh(
          sigma,
        );
      },
    );

    sigma.on(
      "leaveEdge",
      () => {
        hoveredEdge.current =
          null;

        callbacks.current.hover(
          [],
        );

        stableRefresh(
          sigma,
        );
      },
    );

    sigma.on(
      "clickEdge",
      ({ edge }) =>
        callbacks.current.select(
          edgeOccurrences(
            graph,
            edge,
          ),
        ),
    );

    sigma.on(
      "clickStage",
      () =>
        callbacks.current.select(
          [],
        ),
    );

    return () => {
      camera.off("updated", syncLabelSizes);
      sigma.kill();

      renderer.current = null;
    };
  }, [
    graph,
    props.snapshot,
  ]);

  return (
    <div
      className="graph-canvas"
      ref={container}
    />
  );
}

function nodeDisplay(
  snapshot: CaseSnapshot,
  graph: RenderGraph,
  node: string,
  data: Record<
    string,
    unknown
  >,
  activeIds: string[],
  role?: EvidenceRole,
) {
  if (!activeIds.length) {
    return data;
  }

  const occurrence =
    singleActiveOccurrence(
      snapshot,
      activeIds,
    );

  if (occurrence) {
    const edge =
      snapshot.graph?.edges.find(
        (candidate) =>
          candidate.edge_id
          === occurrence.semantic_edge_id,
      );

    if (!edge) {
      return data;
    }

    const showSubject =
      role === undefined
      || role === "subject";

    const showObject =
      role === undefined
      || role === "object";

    if (
      showSubject
      && node
        === edge.subject_node_id
    ) {
      return {
        ...data,

        color:
          GRAPH_VISUAL.nodes
            .subjectColor,

        size:
          GRAPH_VISUAL.nodes
            .selectedSize,

        forceLabel: true,
        zIndex: 30,
      };
    }

    if (
      showObject
      && node
        === edge.object_node_id
    ) {
      return {
        ...data,

        color:
          GRAPH_VISUAL.nodes
            .objectColor,

        size:
          GRAPH_VISUAL.nodes
            .selectedSize,

        forceLabel: true,
        zIndex: 30,
      };
    }

    return data;
  }

  const selected =
    graph
      .edges(node)
      .some(
        (edge) =>
          edgeIsActive(
            graph,
            edge,
            activeIds,
          ),
      );

  if (!selected) {
    return data;
  }

  return {
    ...data,

    color:
      GRAPH_VISUAL.nodes
        .selectedColor,

    size:
      Math.max(
        Number(
          data.size ?? 0,
        ),
        GRAPH_VISUAL.nodes
          .selectedSize,
      ),

    forceLabel: true,
    zIndex: 20,
  };
}

function edgeDisplay(
  snapshot: CaseSnapshot,
  graph: RenderGraph,
  edge: string,
  data: Record<
    string,
    unknown
  >,
  activeIds: string[],
  role:
    | EvidenceRole
    | undefined,
  hovered:
    | string
    | null,
) {
  const occurrence =
    singleActiveOccurrence(
      snapshot,
      activeIds,
    );

  if (occurrence) {
    const showPredicate =
      role === undefined
      || role === "predicate";

    if (
      showPredicate
      && edge
        === occurrence.semantic_edge_id
    ) {
      return {
        ...data,

        color:
          GRAPH_VISUAL.edges
            .predicateColor,

        size:
          GRAPH_VISUAL.edges
            .selectedSize,

        forceLabel: true,
        zIndex: 30,
      };
    }

    return data;
  }

  if (
    hovered === edge
  ) {
    return {
      ...data,

      color:
        GRAPH_VISUAL.edges
          .hoveredColor,

      size:
        GRAPH_VISUAL.edges
          .hoveredSize,

      forceLabel: true,
      zIndex: 20,
    };
  }

  if (
    edgeIsActive(
      graph,
      edge,
      activeIds,
    )
  ) {
    return {
      ...data,

      color:
        GRAPH_VISUAL.edges
          .selectedColor,

      size:
        GRAPH_VISUAL.edges
          .selectedSize,

      forceLabel: true,
      zIndex: 30,
    };
  }

  return data;
}

function singleActiveOccurrence(
  snapshot: CaseSnapshot,
  activeIds: string[],
) {
  if (
    activeIds.length !== 1
  ) {
    return undefined;
  }

  return (
    snapshot.graph
      ?.occurrences
      .find(
        (item) =>
          item.occurrence_id
          === activeIds[0],
      )
  );
}

function edgeOccurrences(
  graph: RenderGraph,
  edge: string,
): string[] {
  return (
    graph.getEdgeAttribute(
      edge,
      "occurrenceIds",
    ) as
      | string[]
      | undefined
  ) ?? [];
}

function edgeIsActive(
  graph: RenderGraph,
  edge: string,
  activeIds: string[],
) {
  const occurrences =
    edgeOccurrences(
      graph,
      edge,
    );

  return activeIds.some(
    (id) =>
      occurrences.includes(id),
  );
}

function stableRefresh(
  sigma: Sigma | null,
) {
  if (!sigma) {
    return;
  }

  const camera =
    sigma.getCamera();

  const state =
    camera.getState();

  sigma.refresh();

  camera.setState(
    state,
  );
}