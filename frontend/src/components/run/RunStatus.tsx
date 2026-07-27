import type { QaRunState } from "../../domain/qa";
import { ErrorMessage } from "../common/ErrorMessage";

interface RunStatusProps {
  state: QaRunState;
}

export function RunStatus({ state }: RunStatusProps) {
  return (
    <section className="run-status">
      <div className="status-line">
        <strong>Status:</strong> {state.status}
      </div>

      {state.terminationReason ? (
        <div className="status-line">
          <strong>Termination:</strong> {state.terminationReason}
        </div>
      ) : null}

      {state.finalDecision ? (
        <div className="decision-summary">
          <strong>Final decision:</strong>{" "}
          {state.finalDecision.status}
          <p>{state.finalDecision.rationale}</p>
        </div>
      ) : null}

      <ErrorMessage message={state.error} />
    </section>
  );
}
