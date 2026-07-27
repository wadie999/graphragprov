import { streamNdjson } from "./ndjson";
import type { QaRunConfig, QaStreamEvent } from "../domain/qa";

export async function* runQaStream(
  experimentId: string,
  caseId: string,
  config: QaRunConfig,
  signal: AbortSignal,
): AsyncGenerator<QaStreamEvent> {
  const path =
    `/api/v1/experiments/${encodeURIComponent(experimentId)}` +
    `/cases/${encodeURIComponent(caseId)}/qa-stream`;

  yield* streamNdjson<QaStreamEvent>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
    signal,
  });
}
