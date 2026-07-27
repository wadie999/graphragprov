import type { AnswerProvenance, DecodedProvenance } from "../domain/provenance";
import type {
  QaAgentDecision,
  QaRunConfig,
  QaRunState,
  QaStreamEvent,
  QaTurn,
  QueryExecution,
  QueryPurpose,
} from "../domain/qa";
import { asArray, asNumber, asRecord, asString } from "../utils/guards";

export const initialQaRunState: QaRunState = {
  status: "idle",
  config: null,
  events: [],
  turns: [],
  finalDecision: null,
  terminationReason: null,
  error: null,
};

export type QaRunAction =
  | { type: "START"; config: QaRunConfig }
  | { type: "EVENT"; event: QaStreamEvent }
  | { type: "STREAM_ENDED" }
  | { type: "CANCELLED" }
  | { type: "RESET" };

export function qaRunReducer(
  state: QaRunState,
  action: QaRunAction,
): QaRunState {
  switch (action.type) {
    case "START":
      return {
        ...initialQaRunState,
        status: "running",
        config: action.config,
      };

    case "EVENT":
      return reduceEvent(state, action.event);

    case "STREAM_ENDED":
      return state.status === "running"
        ? { ...state, status: "completed" }
        : state;

    case "CANCELLED":
      return {
        ...state,
        status: "cancelled",
        error: null,
      };

    case "RESET":
      return initialQaRunState;
  }
}

function reduceEvent(
  state: QaRunState,
  event: QaStreamEvent,
): QaRunState {
  const next: QaRunState = {
    ...state,
    events: [...state.events, event],
  };

  if (event.type === "run.requested" || event.type === "run.started") {
    return {
      ...next,
      status: "running",
      error: null,
    };
  }

  if (event.type === "run.failed") {
    return {
      ...next,
      status: "failed",
      error: extractError(event),
    };
  }

  if (event.type === "run.completed") {
    return reduceRunCompleted(next, event);
  }

  if (event.type.startsWith("turn.")) {
    const turn = normalizeTurnEvent(event);

    if (turn !== null) {
      return {
        ...next,
        turns: upsertTurn(next.turns, turn),
      };
    }
  }

  return next;
}

function reduceRunCompleted(
  state: QaRunState,
  event: QaStreamEvent,
): QaRunState {
  const result = asRecord(event.result) ?? event;
  const attempts = asArray(result.query_attempts)
    .map((value) => asRecord(value))
    .filter((value): value is Record<string, unknown> => value !== null)
    .map(normalizeAttempt);

  const decision = normalizeDecision(result.decision);
  const terminationReason =
    asString(result.termination_reason) ??
    asString(event.termination_reason) ??
    null;

  return {
    ...state,
    status: "completed",
    turns: attempts.length > 0 ? attempts : state.turns,
    finalDecision: decision ?? state.finalDecision,
    terminationReason,
    error: null,
  };
}

function normalizeTurnEvent(event: QaStreamEvent): QaTurn | null {
  if (event.type === "turn.completed") {
    const attempt = asRecord(event.attempt) ?? asRecord(event.turn) ?? event;
    return normalizeAttempt(attempt);
  }

  const turnIndex = asNumber(event.turn_index);

  if (turnIndex === undefined) {
    return null;
  }

  const turn: QaTurn = {
    turn_index: turnIndex,
    answer_provenances: [],
  };

  const purpose = asQueryPurpose(event.purpose);

  if (purpose !== undefined) {
    turn.purpose = purpose;
  }

  if (event.type === "turn.response_received") {
    turn.raw_response = asString(event.raw_response);
  }

  if (event.type === "turn.decision_received") {
    turn.decision = normalizeDecision(event.decision) ?? undefined;
  }

  if (event.type === "turn.query_generated") {
    turn.semantic_sparql = asString(event.semantic_sparql);
  }

  if (event.type === "turn.query_scoped") {
    turn.semantic_sparql = asString(event.semantic_sparql);
    turn.scoped_sparql = asString(event.scoped_sparql);
  }

  if (event.type === "turn.query.original_completed") {
    turn.execution = {
      original_query: asString(event.original_query),
      original_result: asRecord(event.original_result) ?? undefined,
    };
  }

  if (event.type === "turn.query.rewritten") {
    turn.execution = {
      rewritten_query: asString(event.rewritten_query),
    };
  }

  if (event.type === "turn.query.rewritten_completed") {
    turn.execution = {
      rewritten_query: asString(event.rewritten_query),
      rewritten_result: asRecord(event.rewritten_result) ?? undefined,
    };
  }

  return turn;
}

function normalizeAttempt(record: Record<string, unknown>): QaTurn {
  const executionRecord = asRecord(record.execution);
  const purpose = asQueryPurpose(record.purpose);

  return {
    turn_index: asNumber(record.turn_index) ?? 0,
    purpose,
    decision: normalizeDecision(record.decision) ?? undefined,
    raw_response: asString(record.raw_response),
    semantic_sparql: asString(record.semantic_sparql),
    scoped_sparql: asString(record.scoped_sparql),
    execution: executionRecord
      ? normalizeExecution(executionRecord)
      : undefined,
    answer_provenances: normalizeAnswerProvenances(
      record.answer_provenances ?? record.answers,
    ),
    provenance_status: asString(record.provenance_status),
    error_type:
      typeof record.error_type === "string" || record.error_type === null
        ? record.error_type
        : undefined,
    error_message:
      typeof record.error_message === "string" || record.error_message === null
        ? record.error_message
        : undefined,
  };
}

function normalizeExecution(
  record: Record<string, unknown>,
): QueryExecution {
  return {
    original_query: asString(record.original_query),
    original_result: asRecord(record.original_result) ?? undefined,
    rewritten_query: asString(record.rewritten_query),
    rewritten_result: asRecord(record.rewritten_result) ?? undefined,
  };
}

function normalizeAnswerProvenances(value: unknown): AnswerProvenance[] {
  return asArray(value)
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => {
      const decoded = asRecord(item.decoded);
      const directDerivations = asArray(item.derivations);
      const decodedValue: DecodedProvenance = {
        derivations: (
          decoded ? asArray(decoded.derivations) : directDerivations
        ) as DecodedProvenance["derivations"],
      };

      return {
        binding: asRecord(item.binding) ?? {},
        polynomial: asString(item.polynomial) ?? "",
        decoded: decodedValue,
      };
    });
}

function normalizeDecision(value: unknown): QaAgentDecision | null {
  const record = asRecord(value);

  if (record === null) {
    return null;
  }

  const status = asString(record.status);

  if (
    status !== "query" &&
    status !== "ambiguous" &&
    status !== "unanswerable"
  ) {
    return null;
  }

  return {
    status,
    purpose: asQueryPurpose(record.purpose) ?? null,
    sparql:
      typeof record.sparql === "string" || record.sparql === null
        ? record.sparql
        : null,
    rationale: asString(record.rationale) ?? "",
    assumptions: asArray(record.assumptions).filter(
      (item): item is string => typeof item === "string",
    ),
  };
}

function asQueryPurpose(value: unknown): QueryPurpose | undefined {
  return value === "inspection" ||
    value === "candidate" ||
    value === "final"
    ? value
    : undefined;
}

function upsertTurn(turns: QaTurn[], incoming: QaTurn): QaTurn[] {
  const existing = turns.find(
    (turn) => turn.turn_index === incoming.turn_index,
  );

  if (existing === undefined) {
    return [...turns, incoming].sort(
      (left, right) => left.turn_index - right.turn_index,
    );
  }

  const mergedExecution =
    existing.execution || incoming.execution
      ? {
          ...existing.execution,
          ...incoming.execution,
        }
      : undefined;

  const merged: QaTurn = {
    ...existing,
    ...incoming,
    execution: mergedExecution,
    answer_provenances:
      incoming.answer_provenances.length > 0
        ? incoming.answer_provenances
        : existing.answer_provenances,
  };

  return turns.map((turn) =>
    turn.turn_index === incoming.turn_index ? merged : turn,
  );
}

function extractError(event: QaStreamEvent): string {
  const error = asRecord(event.error);

  if (error !== null) {
    return (
      asString(error.message) ??
      asString(error.error_message) ??
      "The QA run failed."
    );
  }

  return (
    asString(event.error_message) ??
    asString(event.message) ??
    "The QA run failed."
  );
}
