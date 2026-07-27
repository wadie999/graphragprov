import type { FormEvent } from "react";

import type { QueryScope } from "../../domain/qa";

interface RunControlsProps {
  question: string;
  maxTurns: number;
  queryScope: QueryScope;
  includeOracleTuples: boolean;
  running: boolean;
  disabled: boolean;
  onQuestionChange: (value: string) => void;
  onMaxTurnsChange: (value: number) => void;
  onQueryScopeChange: (value: QueryScope) => void;
  onIncludeOracleTuplesChange: (value: boolean) => void;
  onRun: () => void;
  onCancel: () => void;
}

export function RunControls({
  question,
  maxTurns,
  queryScope,
  includeOracleTuples,
  running,
  disabled,
  onQuestionChange,
  onMaxTurnsChange,
  onQueryScopeChange,
  onIncludeOracleTuplesChange,
  onRun,
  onCancel,
}: RunControlsProps) {
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onRun();
  }

  return (
    <form className="run-controls" onSubmit={submit}>
      <label className="field field-wide">
        <span>Question</span>
        <textarea
          rows={3}
          value={question}
          disabled={disabled}
          onChange={(event) => onQuestionChange(event.target.value)}
        />
      </label>

      <div className="control-grid">
        <label className="field">
          <span>Query scope</span>
          <select
            value={queryScope}
            disabled={disabled}
            onChange={(event) =>
              onQueryScopeChange(event.target.value as QueryScope)
            }
          >
            <option value="case_graphs">
              Selected case graphs
            </option>
            <option value="whole_repository">
              Whole repository
            </option>
          </select>
        </label>

        <label className="field">
          <span>Maximum turns</span>
          <input
            type="number"
            min={1}
            max={20}
            value={maxTurns}
            disabled={disabled}
            onChange={(event) =>
              onMaxTurnsChange(Number(event.target.value))
            }
          />
        </label>

        <label className="check-field">
          <input
            type="checkbox"
            checked={includeOracleTuples}
            disabled={disabled}
            onChange={(event) =>
              onIncludeOracleTuplesChange(event.target.checked)
            }
          />
          <span>
            Include oracle tuples from gold supporting paragraphs
          </span>
        </label>
      </div>

      <div className="button-row">
        <button
          type="submit"
          disabled={disabled || running || !question.trim()}
        >
          Run streamed QA
        </button>

        <button
          type="button"
          disabled={!running}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
