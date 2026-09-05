import { Play } from "lucide-react";

import type { QueryMode } from "../api/types";

export function QuestionBar(props: {
  question: string;
  onQuestion: (value: string) => void;

  onAsk: () => void;
  askBusy: boolean;

  queryMode: QueryMode;
  onQueryMode: (mode: QueryMode) => void;

  disabled?: boolean;
}) {
  return (
    <div className="question-bar">
      <label htmlFor="workbench-question">
        
        Question
      </label>

      <input id="workbench-question"
        value={props.question}
        onChange={(event) =>
          props.onQuestion(
            event.target.value,
          )
        }
        placeholder="Ask a question over the frozen graph…"
      />

      <div
        className="query-mode-switch"
        aria-label="Query synthesis mode"
      >
        <button
          className={
            props.queryMode === "whole_graph"
              ? "active"
              : ""
          }
          onClick={() =>
            props.onQueryMode(
              "whole_graph",
            )
          }
          title="Give the LLM the frozen graph tuples once"
        >
          Whole graph
        </button>

        <button
          className={
            props.queryMode === "interactive"
              ? "active"
              : ""
          }
          onClick={() =>
            props.onQueryMode(
              "interactive",
            )
          }
          title="Let the LLM discover the graph through iterative SPARQL execution feedback"
        >
          Interactive
        </button>
      </div>

      <button
        className="primary-button"
        onClick={props.onAsk}
        disabled={
          props.askBusy
          || props.disabled
          || !props.question.trim()
        }
      >
        <Play size={15} />

        {props.askBusy
          ? "ASKING…"
          : "ASK"}
      </button>
    </div>
  );
}