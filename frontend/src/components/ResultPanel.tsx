import {
  useEffect,
  useState,
} from "react";

import {
  CheckCircle2,
  CircleAlert,
} from "lucide-react";

import type {
  EvidenceRole,
} from "../api/graphTypes";

import type {
  ProvenanceAnswer,
  QueryRun,
} from "../api/runTypes";

import type {
  CaseSnapshot,
} from "../api/snapshotTypes";

import {
  answerValues,
} from "../utils/results";

import {
  ProvenancePanel,
} from "./ProvenancePanel";

export function ResultPanel(props: {
  snapshot: CaseSnapshot;

  run?: QueryRun | null;

  selectedOccurrenceIds: string[];

  onSelect: (
    ids: string[],
  ) => void;

  onHoverOccurrence: (
    id?: string,
    role?: EvidenceRole,
  ) => void;
}) {
  const values =
    answerValues(
      props.run,
    );

  const [
    answerIndex,
    setAnswerIndex,
  ] =
    useState(0);

  useEffect(() => {
    setAnswerIndex(0);
  }, [
    props.run?.run_id,
  ]);

  function selectAnswer(
    index: number,
  ) {
    setAnswerIndex(index);

    props.onSelect(
      provenanceOccurrences(
        props.run?.provenance[
          index
        ],
      ),
    );
  }

  return (
    <div className="result-stack">
      <section className="result-card answer-card">
        <span>
          Answer
        </span>

        {props.run?.error
          ? (
            <strong className="error-answer">
              <CircleAlert
                size={19}
              />

              Query failed
            </strong>
          )
          : values.length
            ? (
              <div className="answer-values">
                {values.map(
                  (
                    value,
                    index,
                  ) => {
                    const occurrenceIds =
                      provenanceOccurrences(
                        props.run
                          ?.provenance[
                            index
                          ],
                      );

                    return (
                      <button
                        key={
                          `${value}-${index}`
                        }
                        className={
                          index
                          === answerIndex
                            ? "answer-value active"
                            : "answer-value"
                        }
                        onClick={() =>
                          selectAnswer(
                            index,
                          )
                        }
                        disabled={
                          !occurrenceIds.length
                        }
                        title={
                          occurrenceIds.length
                            ? "Highlight the graph and source occurrences supporting this answer"
                            : "No decoded provenance is available for this answer"
                        }
                      >
                        {value}

                        {index
                          === answerIndex
                          && occurrenceIds.length
                          ? (
                            <CheckCircle2
                              size={18}
                            />
                          )
                          : null}
                      </button>
                    );
                  },
                )}
              </div>
            )
            : (
              <strong>
                —
              </strong>
            )}

        {props.run?.answer_correct
          != null && (
          <small>
            Benchmark match:{" "}
            {props.run.answer_correct
              ? "yes"
              : "no"}
          </small>
        )}

        {props.run && (
          <small>
            Provenance:{" "}
            {props.run.provenance_status.replaceAll(
              "_",
              " ",
            )}
          </small>
        )}

        {props.run?.attempts.length
          ? (
            <small>
              Interactive trace:{" "}
              {
                props.run
                  .attempts.length
              }{" "}
              SPARQL attempt
              {props.run.attempts.length
                === 1
                ? ""
                : "s"}
            </small>
          )
          : null}

        {props.run
          ?.provenance_error && (
          <small
            title={
              props.run
                .provenance_error
                .message
            }
          >
            NPCS:{" "}
            {
              props.run
                .provenance_error
                .error_type
            }
          </small>
        )}
      </section>

      <ProvenancePanel
        {...props}
        answerIndex={
          answerIndex
        }
      />
    </div>
  );
}

function provenanceOccurrences(
  answer?: ProvenanceAnswer,
): string[] {
  if (!answer) {
    return [];
  }

  return Array.from(
    new Set(
      answer.derivations.flatMap(
        (derivation) =>
          derivation.factors.flatMap(
            (factor) =>
              factor.occurrence_id
                ? [
                    factor.occurrence_id,
                  ]
                : [],
          ),
      ),
    ),
  );
}