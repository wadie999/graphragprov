export type EvidenceSegment = "title" | "text";
export type EvidenceRole = "subject" | "predicate" | "object";

export interface EvidenceSpan {
  segment: EvidenceSegment;
  start: number;
  end: number;
  quote: string;
}

export interface EvidenceSource {
  unit_id: string;
  title: string;
  text: string;
}

export interface EvidenceOccurrence {
  token: string;
  compact_unit_id: string;
  source: EvidenceSource;
  subject_evidence: EvidenceSpan[];
  predicate_evidence: EvidenceSpan[];
  object_evidence: EvidenceSpan[];
  triple_hash: string;
}

export interface ProvenanceDerivation {
  occurrences: EvidenceOccurrence[];
}

export interface DecodedProvenance {
  derivations: ProvenanceDerivation[];
}

export interface AnswerProvenance {
  binding: Record<string, unknown>;
  polynomial: string;
  decoded: DecodedProvenance;
}
