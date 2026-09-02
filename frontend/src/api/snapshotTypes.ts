import type {
  GraphEdge,
  GraphNode,
  Occurrence,
  SourceUnit,
} from "./graphTypes";

import type {
  QueryRun,
} from "./runTypes";

import type {
  ReasoningStep,
} from "./types";

export type Metric = {
  key: string;
  label: string;
  scope: string;
  value: number | string | boolean;
  unit?: string | null;
  target_id?: string | null;
};

export type BenchmarkRecord = {
  case_id: string;
  benchmark: string;
  question: string;
  expected_answers: string[];
  hop_count: number;
  answerable?: boolean | null;
  reasoning_steps: ReasoningStep[];
  support_source_ids: string[];
  metadata: Record<string, unknown>;
};

export type CaseSnapshot = {
  snapshot_id: string;
  experiment_id: string;
  case_id: string;
  case_label: string;
  origin: "curated" | "workspace";

  artifact_status: string;

  failure_stage?: string | null;
  failure_message?: string | null;

  build_id?: string | null;
  build_mode?:
    | "source_only"
    | "question_conditioned"
    | null;
  build_question?: string | null;

  benchmark?: BenchmarkRecord | null;

  sources: SourceUnit[];

  graph?: {
    graph_id: string;
    nodes: GraphNode[];
    edges: GraphEdge[];
    occurrences: Occurrence[];
    ntriples: string;
  } | null;

  metrics: {
    items: Metric[];
  };

  reference_run?: QueryRun | null;
};