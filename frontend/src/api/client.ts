import type {
  QueryPlan,
  QueryRun,
} from "./runTypes";

import type {
  CaseSnapshot,
} from "./snapshotTypes";

import type {
  CaseSummary,
  Experiment,
  GraphBuildMode,
  WorkspaceSourceInput,
} from "./types";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = await response.text();

    let message = payload;

    try {
      const decoded = JSON.parse(
        payload,
      ) as {
        detail?: string;
      };

      message =
        decoded.detail
        ?? payload;
    } catch {
      // Keep the raw response when the server
      // does not return JSON.
    }

    throw new Error(
      message
      || `${response.status} ${response.statusText}`,
    );
  }

  return (
    await response.json()
  ) as T;
}

export const api = {
  experiments: async () =>
    (
      await request<{
        items: Experiment[];
      }>("/api/v1/experiments")
    ).items,

  cases: async (
    experimentId: string,
  ) =>
    (
      await request<{
        items: CaseSummary[];
      }>(
        `/api/v1/experiments/${experimentId}/cases`,
      )
    ).items,

  snapshot: (
    snapshotId: string,
  ) =>
    request<CaseSnapshot>(
      `/api/v1/snapshots/${snapshotId}`,
    ),

  plan: (
    snapshotId: string,
    question: string,
  ) =>
    request<QueryPlan>(
      `/api/v1/snapshots/${snapshotId}/query-plans`,
      {
        method: "POST",
        body: JSON.stringify({
          question,
        }),
      },
    ),

  run: (
    snapshotId: string,
    sparql: string,
    question: string,
    planId?: string,
  ) =>
    request<QueryRun>(
      `/api/v1/snapshots/${snapshotId}/query-runs`,
      {
        method: "POST",
        body: JSON.stringify({
          sparql,
          question,
          plan_id:
            planId ?? null,
          origin:
            planId
              ? "natural_language"
              : "manual",
        }),
      },
    ),

  interactive: (
    snapshotId: string,
    question: string,
    maxTurns = 5,
  ) =>
    request<QueryRun>(
      `/api/v1/snapshots/${snapshotId}/interactive-runs`,
      {
        method: "POST",
        body: JSON.stringify({
          question,
          max_turns: maxTurns,
        }),
      },
    ),

  createExperiment: (
    name: string,
  ) =>
    request<Experiment>(
      "/api/v1/workspace/experiments",
      {
        method: "POST",
        body: JSON.stringify({
          name,
        }),
      },
    ),

  createCase: (
    experimentId: string,
    name: string,
  ) =>
    request<CaseSummary>(
      `/api/v1/workspace/experiments/${experimentId}/cases`,
      {
        method: "POST",
        body: JSON.stringify({
          name,
        }),
      },
    ),

  updateSources: (
    experimentId: string,
    caseId: string,
    sources: WorkspaceSourceInput[],
  ) =>
    request<CaseSnapshot>(
      `/api/v1/workspace/experiments/${experimentId}/cases/${caseId}/sources`,
      {
        method: "PUT",
        body: JSON.stringify({
          sources,
        }),
      },
    ),

  buildGraph: (
    experimentId: string,
    caseId: string,
    mode: GraphBuildMode,
    question?: string,
  ) =>
    request<CaseSnapshot>(
      `/api/v1/workspace/experiments/${experimentId}/cases/${caseId}/builds`,
      {
        method: "POST",
        body: JSON.stringify({
          mode,
          question:
            question?.trim()
            || null,
        }),
      },
    ),
};