import type {
  AnswerProvenance,
  EvidenceOccurrence,
  ProvenanceDerivation,
} from "../../domain/provenance";
import { JsonBlock } from "../common/JsonBlock";
import { ProvenanceGraph } from "../graph/ProvenanceGraph";

interface ProvenanceInspectorProps {
  answer: AnswerProvenance | null;
  selectedDerivationIndex: number;
  selectedOccurrenceIndex: number | null;
  onSelectDerivation: (index: number) => void;
  onSelectOccurrence: (index: number | null) => void;
}

export function ProvenanceInspector({
  answer,
  selectedDerivationIndex,
  selectedOccurrenceIndex,
  onSelectDerivation,
  onSelectOccurrence,
}: ProvenanceInspectorProps) {
  if (answer === null) {
    return null;
  }

  const derivations = answer.decoded.derivations;
  const derivation =
    derivations[selectedDerivationIndex] ??
    derivations[0] ??
    null;
  const occurrence =
    derivation !== null && selectedOccurrenceIndex !== null
      ? (derivation.occurrences[selectedOccurrenceIndex] ?? null)
      : null;

  return (
    <section className="provenance-inspector">
      <h4>Binding</h4>
      <JsonBlock value={answer.binding} />

      <h4>Polynomial</h4>
      <pre className="polynomial">
        <code>{answer.polynomial || "No polynomial."}</code>
      </pre>

      <h4>Alternative derivations</h4>
      <div className="button-row">
        {derivations.map((_, index) => (
          <button
            type="button"
            key={index}
            className={
              index === selectedDerivationIndex ? "selected" : ""
            }
            onClick={() => onSelectDerivation(index)}
          >
            Derivation {index + 1}
          </button>
        ))}
      </div>

      {derivation ? (
        <>
          <h4>Tuple occurrences</h4>
          <OccurrenceButtons
            derivation={derivation}
            selectedOccurrenceIndex={selectedOccurrenceIndex}
            onSelectOccurrence={onSelectOccurrence}
          />

          <div className="provenance-grid">
            <div>
              <h4>Subgraph</h4>
              <ProvenanceGraph
                derivation={derivation}
                selectedOccurrenceIndex={selectedOccurrenceIndex}
                onSelectOccurrence={(index) =>
                  onSelectOccurrence(index)
                }
              />
            </div>

            <div>
              <h4>Selected occurrence</h4>
              <OccurrenceDetails occurrence={occurrence} />
            </div>
          </div>
        </>
      ) : (
        <p>No decoded derivation is available.</p>
      )}
    </section>
  );
}

function OccurrenceButtons({
  derivation,
  selectedOccurrenceIndex,
  onSelectOccurrence,
}: {
  derivation: ProvenanceDerivation;
  selectedOccurrenceIndex: number | null;
  onSelectOccurrence: (index: number | null) => void;
}) {
  return (
    <div className="button-row">
      <button
        type="button"
        className={selectedOccurrenceIndex === null ? "selected" : ""}
        onClick={() => onSelectOccurrence(null)}
      >
        Entire derivation
      </button>

      {derivation.occurrences.map((occurrence, index) => (
        <button
          type="button"
          key={`${occurrence.token}-${index}`}
          className={
            selectedOccurrenceIndex === index ? "selected" : ""
          }
          onClick={() => onSelectOccurrence(index)}
        >
          Tuple {index + 1}
        </button>
      ))}
    </div>
  );
}

function OccurrenceDetails({
  occurrence,
}: {
  occurrence: EvidenceOccurrence | null;
}) {
  if (occurrence === null) {
    return (
      <p>
        Select one tuple or graph edge to inspect its exact evidence.
      </p>
    );
  }

  return (
    <dl className="occurrence-details">
      <dt>Token</dt>
      <dd>{occurrence.token}</dd>

      <dt>Source</dt>
      <dd>
        {occurrence.source.title} ({occurrence.source.unit_id})
      </dd>

      <dt>Subject evidence</dt>
      <dd>{quotes(occurrence.subject_evidence)}</dd>

      <dt>Predicate evidence</dt>
      <dd>{quotes(occurrence.predicate_evidence)}</dd>

      <dt>Object evidence</dt>
      <dd>{quotes(occurrence.object_evidence)}</dd>
    </dl>
  );
}

function quotes(
  spans: Array<{ quote: string }>,
): string {
  return spans.map((span) => span.quote).join(" | ") || "None";
}
