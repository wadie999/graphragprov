import type { AnswerProvenance } from "./provenance";

export type QueryScope = "case_graphs" | "whole_repository";
export type QueryPurpose = "inspection" | "candidate" | "final";
export type RunStatus = "idle" | "running" | "completed" | "failed" | "cancelled";

export interface QaRunConfig {
  question: string;
  max_turns: number;
  query_scope: QueryScope;
  include_oracle_tuples: boolean;
}

export interface QaAgentDecision {
  status: "query" | "ambiguous" | "unanswerable";
  purpose: QueryPurpose | null;
  sparql: string | null;
  rationale: string;
  assumptions: string[];
}

export interface QueryExecution {
  original_query?: string;
  original_result?: Record<string, unknown>;
  rewritten_query?: string;
  rewritten_result?: Record<string, unknown>;
}

export interface QaTurn {
  turn_index: number;
  purpose?: QueryPurpose;
  decision?: QaAgentDecision;
  raw_response?: string;
  semantic_sparql?: string;
  scoped_sparql?: string;
  execution?: QueryExecution;
  answer_provenances: AnswerProvenance[];
  provenance_status?: string;
  error_type?: string | null;
  error_message?: string | null;
}

export interface QaStreamEvent {
  type: string;
  experiment_id?: string;
  case_id?: string;
  [key: string]: unknown;
}

export interface QaRunState {
  status: RunStatus;
  config: QaRunConfig | null;
  events: QaStreamEvent[];
  turns: QaTurn[];
  finalDecision: QaAgentDecision | null;
  terminationReason: string | null;
  error: string | null;
}
