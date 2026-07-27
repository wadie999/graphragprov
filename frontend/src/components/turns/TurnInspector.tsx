import type { QaTurn } from "../../domain/qa";
import { CodeBlock } from "../common/CodeBlock";
import { JsonBlock } from "../common/JsonBlock";
import { ProvenanceInspector } from "../results/ProvenanceInspector";
import { ResultSelector } from "../results/ResultSelector";

interface TurnInspectorProps {
  turn: QaTurn | null;
  selectedAnswerIndex: number;
  selectedDerivationIndex: number;
  selectedOccurrenceIndex: number | null;
  onSelectAnswer: (index: number) => void;
  onSelectDerivation: (index: number) => void;
  onSelectOccurrence: (index: number | null) => void;
}

export function TurnInspector({
  turn,
  selectedAnswerIndex,
  selectedDerivationIndex,
  selectedOccurrenceIndex,
  onSelectAnswer,
  onSelectDerivation,
  onSelectOccurrence,
}: TurnInspectorProps) {
  if (turn === null) {
    return (
      <section className="turn-inspector">
        <h3>Live turn inspection</h3>
        <p>Start a run to inspect the agent execution.</p>
      </section>
    );
  }

  const answer =
    turn.answer_provenances[selectedAnswerIndex] ??
    turn.answer_provenances[0] ??
    null;

  return (
    <section className="turn-inspector">
      <div className="section-heading">
        <h3>
          Turn {turn.turn_index} — {turn.purpose ?? "pending"}
        </h3>
        <span>{turn.provenance_status ?? "pending"}</span>
      </div>

      {turn.decision ? (
        <section>
          <h4>Agent decision</h4>
          <p>{turn.decision.rationale}</p>
          {turn.decision.assumptions.length > 0 ? (
            <ul>
              {turn.decision.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <details open>
        <summary>Semantic SPARQL</summary>
        <CodeBlock value={turn.semantic_sparql} />
      </details>

      <details>
        <summary>Backend-scoped SPARQL</summary>
        <CodeBlock value={turn.scoped_sparql} />
      </details>

      <details>
        <summary>NPCS-rewritten SPARQL</summary>
        <CodeBlock value={turn.execution?.rewritten_query} />
      </details>

      <details>
        <summary>Original GraphDB result</summary>
        <JsonBlock value={turn.execution?.original_result} />
      </details>

      <details>
        <summary>Rewritten GraphDB result</summary>
        <JsonBlock value={turn.execution?.rewritten_result} />
      </details>

      {turn.error_message ? (
        <div className="error-message">
          <strong>{turn.error_type ?? "Turn error"}</strong>
          <p>{turn.error_message}</p>
        </div>
      ) : null}

      <section>
        <h4>Result bindings</h4>
        <ResultSelector
          answers={turn.answer_provenances}
          selectedIndex={selectedAnswerIndex}
          onSelect={onSelectAnswer}
        />

        <ProvenanceInspector
          answer={answer}
          selectedDerivationIndex={selectedDerivationIndex}
          selectedOccurrenceIndex={selectedOccurrenceIndex}
          onSelectDerivation={onSelectDerivation}
          onSelectOccurrence={onSelectOccurrence}
        />
      </section>
    </section>
  );
}
