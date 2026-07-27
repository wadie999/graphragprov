import { requestJson } from "./client";
import type {
  ExperimentCaseListResponse,
  ExperimentCaseReference,
  ExperimentListResponse,
} from "../domain/experiment";

export function listExperiments(): Promise<ExperimentListResponse> {
  return requestJson<ExperimentListResponse>("/api/v1/experiments");
}

export function listExperimentCases(
  experimentId: string,
): Promise<ExperimentCaseListResponse> {
  return requestJson<ExperimentCaseListResponse>(
    `/api/v1/experiments/${encodeURIComponent(experimentId)}/cases`,
  );
}

export function loadCaseReference(
  experimentId: string,
  caseId: string,
): Promise<ExperimentCaseReference> {
  return requestJson<ExperimentCaseReference>(
    `/api/v1/experiments/${encodeURIComponent(experimentId)}/cases/${encodeURIComponent(caseId)}/reference`,
  );
}
