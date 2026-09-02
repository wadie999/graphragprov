export type Experiment = {
  experiment_id: string;
  label: string;
  benchmark: "musique" | "twowiki" | "custom";
  origin: "curated" | "workspace";
  case_count: number;
  available_case_count: number;
};

export type CaseSummary = {
  experiment_id: string;
  case_id: string;
  label: string;
  snapshot_id: string;
  origin: "curated" | "workspace";
  question: string;
  expected_answer: string;
  hop_count?: number | null;
  artifact_status: string;
  graph_available: boolean;
  provenance_available: boolean;
};

export type ReasoningStep = {
  step_id: string;
  question?: string | null;
  answer?: string | null;
  subject?: string | null;
  relation?: string | null;
  object?: string | null;
  source_index?: number | null;
};

export type WorkspaceSourceInput = {
  title: string;
  text: string;
};

export type GraphBuildMode =
  | "source_only"
  | "question_conditioned";

export type QueryMode =
  | "whole_graph"
  | "interactive";