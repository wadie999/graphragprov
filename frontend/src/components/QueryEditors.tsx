import {
  History,
  RotateCw,
} from "lucide-react";

import type {
  QueryRun,
} from "../api/runTypes";

import {
  SparqlEditor,
} from "./SparqlEditor";

export function QueryEditors(props: {
  sparql: string;
  rewritten: string;

  run?: QueryRun | null;

  onSparql: (
    value: string,
  ) => void;

  onRun: () => void;

  onLoadReference?: () => void;

  runBusy: boolean;
  disabled?: boolean;
}) {
  return (
    <section className="query-section">
      <div className="query-toolbar">
        <span>
          Executable computation
        </span>

        <div>
          {props.onLoadReference && (
            <button
              className="secondary-button"
              onClick={
                props.onLoadReference
              }
            >
              <History size={13} />
              Reference
            </button>
          )}

          <button
            className="secondary-button"
            onClick={props.onRun}
            disabled={
              props.runBusy
              || !props.sparql
              || props.disabled
            }
          >
            <RotateCw size={14} />

            {props.runBusy
              ? "RUNNING…"
              : "RUN SPARQL"}
          </button>
        </div>
      </div>

      {props.run?.attempts.length
        ? (
          <div className="attempt-strip">
            {props.run.attempts.map(
              (attempt) => (
                <span
                  key={
                    attempt.turn_index
                  }
                  className={
                    `attempt-chip attempt-${attempt.purpose}`
                  }
                  title={
                    attempt.error?.message
                  }
                >
                  {attempt.turn_index}
                  {" · "}
                  {attempt.purpose}
                  {" · "}
                  {attempt.provenance_status.replaceAll(
                    "_",
                    " ",
                  )}
                </span>
              ),
            )}
          </div>
        )
        : null}

      <div className="query-stack">
        <SparqlEditor
          title="Semantic SPARQL"
          value={props.sparql}
          onChange={
            props.onSparql
          }
          placeholder="Waiting for natural-language planning or manual SPARQL…"
        />

        <SparqlEditor
          title="NPCS rewritten query"
          value={
            props.rewritten
          }
          readOnly
          placeholder="Waiting for provenance rewriting…"
        />
      </div>
    </section>
  );
}