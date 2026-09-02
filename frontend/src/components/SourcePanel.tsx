import {
  useState,
} from "react";

import type {
  EvidenceRole,
  Occurrence,
} from "../api/graphTypes";

import type {
  CaseSnapshot,
} from "../api/snapshotTypes";

import {
  HighlightedText,
} from "./HighlightedText";

export function SourcePanel(props: {
  snapshot: CaseSnapshot;

  activeOccurrenceIds: string[];

  activeRole?: EvidenceRole;

  onHoverOccurrence: (
    id?: string,
    role?: EvidenceRole,
  ) => void;
}) {
  const [
    openTrace,
    setOpenTrace,
  ] =
    useState<string>();

  const active =
    new Set(
      props.activeOccurrenceIds,
    );

  const occurrences =
    props.snapshot.graph
      ?.occurrences
    ?? [];

  return (
    <section className="panel source-panel">
      <div className="panel-title">
        <span>
          Source paragraphs
        </span>

        <small>
          {
            props.snapshot
              .sources.length
          }{" "}
          sources
        </small>
      </div>

      <div className="source-scroll">
        {props.snapshot.sources.map(
          (source) => {
            const sourceOccurrences =
              occurrences.filter(
                (item) =>
                  item.source_id
                  === source.source_id,
              );

            const highlighted =
              sourceOccurrences.filter(
                (item) =>
                  active.has(
                    item.occurrence_id,
                  ),
              );

            const groups =
              highlighted.map(
                (item) =>
                  spansFor(
                    item,
                    props.activeRole,
                  ),
              );

            const traceOpen =
              openTrace
              === source.source_id;

            return (
              <article
                className={
                  highlighted.length
                    ? "source-card source-card-active"
                    : "source-card"
                }
                key={
                  source.source_id
                }
              >
                <header>
                  <span>
                    #
                    {
                      source.paragraph_index
                      ?? source.ordinal
                    }
                    {" · "}

                    <HighlightedText
                      text={
                        source.title
                      }
                      spans={
                        groups
                      }
                      segment="title"
                    />
                  </span>

                  <small>
                    {
                      source.statement_count
                    }{" "}
                    facts
                  </small>
                </header>

                <p>
                  <HighlightedText
                    text={
                      source.text
                    }
                    spans={
                      groups
                    }
                  />
                </p>

                <div className="source-card-footer">
                  <div className="occurrence-chips">
                    {sourceOccurrences.map(
                      (
                        item,
                        index,
                      ) => (
                        <button
                          key={
                            item.occurrence_id
                          }
                          className={
                            active.has(
                              item.occurrence_id,
                            )
                              ? "active"
                              : ""
                          }
                          title={
                            item.token
                          }
                          onMouseEnter={() =>
                            props.onHoverOccurrence(
                              item.occurrence_id,
                            )
                          }
                          onMouseLeave={() =>
                            props.onHoverOccurrence()
                          }
                        >
                          e
                          {occurrenceNumber(
                            occurrences,
                            item,
                            index,
                          )}
                        </button>
                      ),
                    )}
                  </div>

                  {source.extraction_prompt && (
                    <button
                      className="trace-toggle"
                      onClick={() =>
                        setOpenTrace(
                          traceOpen
                            ? undefined
                            : source.source_id,
                        )
                      }
                    >
                      {traceOpen
                        ? "Hide extraction"
                        : "Inspect extraction"}
                    </button>
                  )}
                </div>

                {traceOpen
                  && source.extraction_prompt && (
                  <div className="extraction-trace">
                    <div>
                      <strong>
                        Exact prompt
                      </strong>

                      <pre>
                        {
                          source.extraction_prompt
                        }
                      </pre>
                    </div>

                    <div>
                      <strong>
                        Raw model response
                      </strong>

                      <pre>
                        {
                          source.extraction_response
                          ?? "—"
                        }
                      </pre>
                    </div>
                  </div>
                )}
              </article>
            );
          },
        )}
      </div>
    </section>
  );
}

function spansFor(
  item: Occurrence,
  role?: EvidenceRole,
) {
  if (
    role === "subject"
  ) {
    return (
      item.subject_evidence
    );
  }

  if (
    role === "predicate"
  ) {
    return (
      item.predicate_evidence
    );
  }

  if (
    role === "object"
  ) {
    return (
      item.object_evidence
    );
  }

  return [
    ...item.subject_evidence,
    ...item.predicate_evidence,
    ...item.object_evidence,
  ];
}

function occurrenceNumber(
  all: Occurrence[],
  item: Occurrence,
  fallback: number,
) {
  const index =
    all.findIndex(
      (candidate) =>
        candidate.occurrence_id
        === item.occurrence_id,
    );

  return index >= 0
    ? index + 1
    : fallback + 1;
}