import type {
  EvidenceRole,
} from "../api/graphTypes";

import type {
  ProvenanceDerivation,
  QueryRun,
} from "../api/runTypes";

import type {
  CaseSnapshot,
} from "../api/snapshotTypes";

export function ProvenancePanel(props: {
  snapshot: CaseSnapshot;

  run?: QueryRun | null;

  selectedOccurrenceIds: string[];

  answerIndex: number;

  onSelect: (
    ids: string[],
  ) => void;

  onHoverOccurrence: (
    id?: string,
    role?: EvidenceRole,
  ) => void;
}) {
  const answer =
    props.run?.provenance[
      props.answerIndex
    ];

  const occurrences =
    props.snapshot.graph
      ?.occurrences
    ?? [];

  if (!props.run) {
    return (
      <section className="result-card provenance-card">
        <span>
          Provenance polynomial
        </span>

        <strong>
          —
        </strong>
      </section>
    );
  }

  if (!answer) {
    return (
      <section className="result-card provenance-card">
        <span>
          Provenance
        </span>

        <strong className="status-text">
          {
            props.run
              .provenance_status
          }
        </strong>
      </section>
    );
  }

  return (
    <section className="result-card provenance-card">
      <span>
        Provenance polynomial
      </span>

      <div className="polynomial">
        {answer.derivations.map(
          (
            derivation,
            index,
          ) => (
            <span
              className="derivation-group"
              key={
                derivation.derivation_id
              }
            >
              {index > 0 && (
                <b className="plus">
                  +
                </b>
              )}

              <button
                className={
                  selected(
                    props.selectedOccurrenceIds,
                    derivation,
                  )
                    ? "selected"
                    : ""
                }
                onClick={() =>
                  props.onSelect(
                    ids(
                      derivation,
                    ),
                  )
                }
                title="Select this complete derivation"
              >
                {derivation.factors.map(
                  (
                    factor,
                    factorIndex,
                  ) => {
                    const occurrence =
                      occurrences.find(
                        (item) =>
                          item.occurrence_id
                          === factor.occurrence_id,
                      );

                    const tuple =
                      occurrenceTuple(
                        props.snapshot,
                        factor.occurrence_id,
                      );

                    return (
                      <span
                        className="factor-wrap"
                        key={
                          `${factor.token}-${factorIndex}`
                        }
                        onMouseEnter={() =>
                          props.onHoverOccurrence(
                            factor.occurrence_id
                            ?? undefined,
                          )
                        }
                        onMouseLeave={() =>
                          props.onHoverOccurrence()
                        }
                      >
                        {factorIndex
                          > 0 && (
                          <b>
                            ×
                          </b>
                        )}

                        <em
                          onClick={
                            (
                              event,
                            ) => {
                              event
                                .stopPropagation();

                              if (
                                factor.occurrence_id
                              ) {
                                props.onSelect(
                                  [
                                    factor.occurrence_id,
                                  ],
                                );
                              }
                            }
                          }
                        >
                          {label(
                            occurrences,
                            factor.occurrence_id,
                          )}
                        </em>

                        {occurrence
                          && tuple && (
                          <span
                            className="factor-popover"
                            onClick={
                              (
                                event,
                              ) =>
                                event
                                  .stopPropagation()
                            }
                          >
                            <small
                              title={
                                occurrence.token
                              }
                            >
                              {
                                occurrence.token
                              }
                            </small>

                            <RoleLine
                              role="subject"
                              label="Es"
                              value={
                                tuple.subject
                              }
                              occurrenceId={
                                occurrence.occurrence_id
                              }
                              onHover={
                                props.onHoverOccurrence
                              }
                            />

                            <RoleLine
                              role="predicate"
                              label="Ep"
                              value={
                                tuple.predicate
                              }
                              occurrenceId={
                                occurrence.occurrence_id
                              }
                              onHover={
                                props.onHoverOccurrence
                              }
                            />

                            <RoleLine
                              role="object"
                              label="Eo"
                              value={
                                tuple.object
                              }
                              occurrenceId={
                                occurrence.occurrence_id
                              }
                              onHover={
                                props.onHoverOccurrence
                              }
                            />
                          </span>
                        )}
                      </span>
                    );
                  },
                )}
              </button>
            </span>
          ),
        )}
      </div>

      <small
        title={
          answer.polynomial
        }
      >
        Hover eᵢ to trace one
        occurrence. Hover Es / Ep /
        Eo for component-level
        grounding.
      </small>
    </section>
  );
}

function RoleLine(props: {
  role: EvidenceRole;
  label: string;
  value: string;
  occurrenceId: string;

  onHover: (
    id?: string,
    role?: EvidenceRole,
  ) => void;
}) {
  return (
    <span
      className={
        `factor-role factor-role-${props.role}`
      }
      onMouseEnter={
        (event) => {
          event.stopPropagation();

          props.onHover(
            props.occurrenceId,
            props.role,
          );
        }
      }
      onMouseLeave={
        (event) => {
          event.stopPropagation();

          props.onHover(
            props.occurrenceId,
          );
        }
      }
    >
      <b>
        {props.label}
      </b>

      <span>
        {props.value}
      </span>
    </span>
  );
}

function ids(
  derivation: ProvenanceDerivation,
) {
  return derivation.factors.flatMap(
    (factor) =>
      factor.occurrence_id
        ? [
            factor.occurrence_id,
          ]
        : [],
  );
}

function selected(
  active: string[],
  derivation: ProvenanceDerivation,
) {
  const target =
    ids(
      derivation,
    );

  return (
    target.length > 0
    && target.every(
      (id) =>
        active.includes(id),
    )
    && active.length
    === target.length
  );
}

function label(
  occurrences:
    NonNullable<
      CaseSnapshot["graph"]
    >["occurrences"],
  id?: string | null,
) {
  const index =
    occurrences.findIndex(
      (item) =>
        item.occurrence_id
        === id,
    );

  return index >= 0
    ? `e${index + 1}`
    : "e?";
}

function occurrenceTuple(
  snapshot: CaseSnapshot,
  occurrenceId?:
    | string
    | null,
) {
  if (
    !occurrenceId
    || !snapshot.graph
  ) {
    return null;
  }

  const occurrence =
    snapshot.graph.occurrences.find(
      (item) =>
        item.occurrence_id
        === occurrenceId,
    );

  if (!occurrence) {
    return null;
  }

  const edge =
    snapshot.graph.edges.find(
      (item) =>
        item.edge_id
        === occurrence.semantic_edge_id,
    );

  if (!edge) {
    return null;
  }

  const subject =
    snapshot.graph.nodes.find(
      (item) =>
        item.node_id
        === edge.subject_node_id,
    );

  const object =
    snapshot.graph.nodes.find(
      (item) =>
        item.node_id
        === edge.object_node_id,
    );

  return {
    subject:
      subject?.label
      ?? edge.subject_node_id,

    predicate:
      edge.predicate_label,

    object:
      object?.label
      ?? edge.object_node_id,
  };
}