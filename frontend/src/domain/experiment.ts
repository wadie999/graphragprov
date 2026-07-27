export interface ExperimentSummary {
  experiment_id: string;
  benchmark: "musique";
  status: "complete" | "partial";
  created_at: string;
  case_count: number;
  hop_counts: number[];
  prompt_version: string;
  extraction_model: string;
  requested_source_count: number;
  successful_extraction_count: number;
  failed_extraction_count: number;
  materialized_source_count: number;
  statement_count: number;
}

export interface ExperimentListResponse {
  items: ExperimentSummary[];
  total: number;
}

export interface ExperimentCaseSummary {
  experiment_id: string;
  case_id: string;
  question: string;
  hop_count: number;
  answerable: boolean;
  paragraph_count: number;
}

export interface ExperimentCaseListResponse {
  experiment_id: string;
  items: ExperimentCaseSummary[];
  total: number;
}

export interface BenchmarkParagraph {
  paragraph_index: number;
  source_unit_id: string;
  title: string;
  text: string;
  is_supporting: boolean;
}

export interface BenchmarkHop {
  hop_id: number;
  question: string;
  answer: string;
  paragraph_support_index: number | null;
}

export interface ExperimentCaseReference {
  experiment_id: string;
  case_id: string;
  question: string;
  gold_answer: string;
  answer_aliases: string[];
  hop_count: number;
  answerable: boolean;
  gold_support_indices: number[];
  decomposition: BenchmarkHop[];
  paragraphs: BenchmarkParagraph[];
}
