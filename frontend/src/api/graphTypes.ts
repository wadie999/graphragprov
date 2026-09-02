export type EvidenceRole =
  | "subject"
  | "predicate"
  | "object";

export type EvidenceSpan = {
  segment: "title" | "text";
  start: number;
  end: number;
  quote: string;
  role: EvidenceRole;
};

export type SourceUnit = {
  source_id: string;
  ordinal: number;
  paragraph_index?: number | null;
  title: string;
  text: string;
  statement_count: number;
  extraction_prompt?: string | null;
  extraction_response?: string | null;
};

export type GraphNode = {
  node_id: string;
  kind: string;
  value: string;
  label: string;
  datatype?: string | null;
  language?: string | null;
};

export type GraphEdge = {
  edge_id: string;
  subject_node_id: string;
  predicate_iri: string;
  predicate_label: string;
  object_node_id: string;
  occurrence_ids: string[];
};

export type Occurrence = {
  occurrence_id: string;
  token: string;
  semantic_edge_id: string;
  source_id: string;
  subject_evidence: EvidenceSpan[];
  predicate_evidence: EvidenceSpan[];
  object_evidence: EvidenceSpan[];
};