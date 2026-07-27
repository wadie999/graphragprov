import type { ExperimentCaseReference } from "../../domain/experiment";
import type {
  EvidenceOccurrence,
  ProvenanceDerivation,
} from "../../domain/provenance";
import {
  HighlightedText,
  type RoleSpan,
} from "./HighlightedText";

interface BenchmarkPanelProps {
  reference: ExperimentCaseReference | null;
  derivation: ProvenanceDerivation | null;
  selectedOccurrenceIndex: number | null;
}

export function BenchmarkPanel({
  reference,
  derivation,
  selectedOccurrenceIndex,
}: BenchmarkPanelProps) {
  if (reference === null) {
    return (
      <section className="benchmark-panel">
        <h2>Benchmark reference</h2>
        <p>Select a case to load its fixed reference.</p>
      </section>
    );
  }

  const occurrences = selectedOccurrences(
    derivation,
    selectedOccurrenceIndex,
  );
  const spansBySource = collectSpansBySource(occurrences);

  return (
    <section className="benchmark-panel">
      <div className="section-heading">
        <h2>Fixed benchmark reference</h2>
        <span>{reference.hop_count}-hop</span>
      </div>

      <dl className="reference-summary">
        <dt>Question</dt>
        <dd>{reference.question}</dd>

        <dt>Gold answer</dt>
        <dd>
          {reference.gold_answer}
          {reference.answer_aliases.length > 0
            ? ` (${reference.answer_aliases.join(", ")})`
            : ""}
        </dd>
      </dl>

      <h3>Gold decomposition</h3>
      <ol>
        {reference.decomposition.map((hop) => (
          <li key={hop.hop_id}>
            <strong>{hop.question}</strong>
            <div>Answer: {hop.answer}</div>
            <div>
              Paragraph:{" "}
              {hop.paragraph_support_index ?? "not annotated"}
            </div>
          </li>
        ))}
      </ol>

      <h3>Paragraphs</h3>
      <div className="paragraph-list">
        {reference.paragraphs.map((paragraph) => {
          const spans =
            spansBySource.get(paragraph.source_unit_id) ?? [];

          return (
            <article
              key={paragraph.paragraph_index}
              className={
                spans.length > 0
                  ? "benchmark-paragraph highlighted-source"
                  : "benchmark-paragraph"
              }
            >
              <header>
                <strong>
                  [{paragraph.paragraph_index}]{" "}
                  <HighlightedText
                    text={paragraph.title}
                    segment="title"
                    spans={spans}
                  />
                </strong>
                {paragraph.is_supporting ? (
                  <span>gold support</span>
                ) : null}
              </header>

              <p>
                <HighlightedText
                  text={paragraph.text}
                  segment="text"
                  spans={spans}
                />
              </p>

              <small>{paragraph.source_unit_id}</small>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function selectedOccurrences(
  derivation: ProvenanceDerivation | null,
  selectedOccurrenceIndex: number | null,
): EvidenceOccurrence[] {
  if (derivation === null) {
    return [];
  }

  if (selectedOccurrenceIndex === null) {
    return derivation.occurrences;
  }

  const occurrence =
    derivation.occurrences[selectedOccurrenceIndex];

  return occurrence ? [occurrence] : [];
}

function collectSpansBySource(
  occurrences: EvidenceOccurrence[],
): Map<string, RoleSpan[]> {
  const result = new Map<string, RoleSpan[]>();

  for (const occurrence of occurrences) {
    const sourceId = occurrence.source.unit_id;
    const current = result.get(sourceId) ?? [];

    current.push(
      ...occurrence.subject_evidence.map((span) => ({
        ...span,
        role: "subject" as const,
      })),
      ...occurrence.predicate_evidence.map((span) => ({
        ...span,
        role: "predicate" as const,
      })),
      ...occurrence.object_evidence.map((span) => ({
        ...span,
        role: "object" as const,
      })),
    );

    result.set(sourceId, current);
  }

  return result;
}
