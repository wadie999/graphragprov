export type ProvenanceFactor = {
  token: string;
  occurrence_id?: string | null;
};

export type ProvenanceDerivation = {
  derivation_id: string;
  factors: ProvenanceFactor[];
};

export type ProvenanceAnswer = {
  binding: Record<string, unknown>;
  polynomial: string;
  derivations: ProvenanceDerivation[];
};

export type QueryAttempt = {
  turn_index: number;

  purpose:
    | "inspection"
    | "candidate"
    | "final";

  semantic_sparql: string;
  execution_sparql: string;

  result?: Record<string, unknown> | null;

  rewritten_sparql?: string | null;
  rewritten_result?: Record<string, unknown> | null;

  provenance_status: string;

  error?: {
    error_type: string;
    message: string;
  } | null;
};

export type QueryRun = {
  run_id: string;
  snapshot_id: string;

  origin:
    | "reference"
    | "manual"
    | "natural_language"
    | "interactive";

  question?: string | null;

  semantic_sparql: string;
  execution_sparql?: string | null;

  rewritten_sparql?: string | null;

  result?: Record<string, unknown> | null;
  rewritten_result?: Record<string, unknown> | null;

  provenance_status: string;

  provenance: ProvenanceAnswer[];

  attempts: QueryAttempt[];

  answer_correct?: boolean | null;
  gold_support_covered?: boolean | null;

  error?: {
    error_type: string;
    message: string;
  } | null;

  provenance_error?: {
    error_type: string;
    message: string;
  } | null;
};

export type QueryPlan = {
  plan_id: string;
  snapshot_id: string;
  question: string;

  status:
    | "query"
    | "ambiguous"
    | "unanswerable";

  sparql?: string | null;

  rationale: string;
  assumptions: string[];

  model: string;
};