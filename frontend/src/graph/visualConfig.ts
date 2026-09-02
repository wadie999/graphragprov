export const GRAPH_VISUAL = {
  nodes: {
    entitySize: 5.8,
    literalSize: 3.3,

    entityColor: "#475569",
    literalColor: "#94a3b8",

    selectedSize: 7.1,
    selectedColor: "#0057ff",

    subjectColor: "#2563eb",
    objectColor: "#16a34a",
  },

  edges: {
    size: 1.9,
    color: "#8492a6",

    selectedSize: 3.2,
    selectedColor: "#0057ff",

    hoveredSize: 3.0,
    hoveredColor: "#f97316",

    predicateColor: "#d97706",
  },

  labels: {
    forceNodeLabelsBelow: 48,
    forceEdgeLabelsBelow: 40,

    nodeSize: 11,
    edgeSize: 9,

    nodeColor: "#1f2937",
    edgeColor: "#5f6b7c",

    density: 1,
    gridCellSize: 44,

    renderedSizeThreshold: 0,
  },

  layout: {
    smallGraphIterations: 130,
    largeGraphIterations: 190,
    largeGraphThreshold: 80,

    gravity: 0.7,
    scalingRatio: 9,
  },

  stage: {
    padding: 38,
  },
} as const;