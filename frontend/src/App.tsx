import { useEffect, useMemo, useState } from "react";

import { BenchmarkPanel } from "./components/benchmark/BenchmarkPanel";
import { CaseSelector } from "./components/cases/CaseSelector";
import { ErrorMessage } from "./components/common/ErrorMessage";
import { ExperimentSelector } from "./components/experiments/ExperimentSelector";
import { AppHeader } from "./components/layout/AppHeader";
import { RunControls } from "./components/run/RunControls";
import { RunStatus } from "./components/run/RunStatus";
import { TurnInspector } from "./components/turns/TurnInspector";
import { TurnNavigator } from "./components/turns/TurnNavigator";
import type { QueryScope } from "./domain/qa";
import { useExperimentBrowser } from "./state/useExperimentBrowser";
import { useQaRun } from "./state/useQaRun";
import { useQaSelection } from "./state/useQaSelection";
import { downloadJson } from "./utils/download";

export function App() {
  const browser = useExperimentBrowser();
  const qaRun = useQaRun();
  const selection = useQaSelection(qaRun.state.turns);

  const [questionDraft, setQuestionDraft] = useState("");
  const [maxTurns, setMaxTurns] = useState(5);
  const [queryScope, setQueryScope] =
    useState<QueryScope>("case_graphs");
  const [includeOracleTuples, setIncludeOracleTuples] =
    useState(false);

  useEffect(() => {
    if (browser.reference !== null) {
      setQuestionDraft(browser.reference.question);
      qaRun.reset();
    }
  }, [browser.reference?.case_id]);

  const selectedAnswer =
    selection.selectedTurn?.answer_provenances[
      selection.selectedAnswerIndex
    ] ?? null;

  const selectedDerivation = useMemo(
    () =>
      selectedAnswer?.decoded.derivations[
        selection.selectedDerivationIndex
      ] ??
      selectedAnswer?.decoded.derivations[0] ??
      null,
    [selectedAnswer, selection.selectedDerivationIndex],
  );

  const canRun =
    Boolean(
      browser.selectedExperimentId &&
        browser.selectedCaseId &&
        browser.reference,
    ) && !browser.loading;

  function startRun(): void {
    if (!canRun) {
      return;
    }

    void qaRun.start(
      browser.selectedExperimentId,
      browser.selectedCaseId,
      {
        question: questionDraft.trim(),
        max_turns: maxTurns,
        query_scope: queryScope,
        include_oracle_tuples: includeOracleTuples,
      },
    );
  }

  function exportRun(): void {
    if (browser.reference === null) {
      return;
    }

    const filename =
      `graphragprov-${browser.reference.case_id}-` +
      `${new Date().toISOString().replaceAll(":", "-")}.json`;

    downloadJson(filename, {
      format: "graphragprov-browser-run-v1",
      exported_at: new Date().toISOString(),
      benchmark_reference: browser.reference,
      edited_question: questionDraft,
      configuration: {
        max_turns: maxTurns,
        query_scope: queryScope,
        include_oracle_tuples: includeOracleTuples,
      },
      stream_events: qaRun.state.events,
      reduced_run: qaRun.state,
    });
  }

  return (
    <div className="app-shell">
      <AppHeader
        canExport={
          browser.reference !== null &&
          qaRun.state.events.length > 0
        }
        onExport={exportRun}
      />

      <section className="selection-bar">
        <ExperimentSelector
          experiments={browser.experiments}
          value={browser.selectedExperimentId}
          disabled={browser.loading || qaRun.state.status === "running"}
          onChange={browser.selectExperiment}
        />

        <CaseSelector
          cases={browser.cases}
          value={browser.selectedCaseId}
          disabled={browser.loading || qaRun.state.status === "running"}
          onChange={browser.selectCase}
        />

        <span>
          {browser.loading ? "Loading…" : "Reference loaded"}
        </span>
      </section>

      <ErrorMessage
        message={browser.error}
        onRetry={browser.reloadReference}
      />

      <section className="runtime-panel">
        <h2>Live QA execution</h2>

        <RunControls
          question={questionDraft}
          maxTurns={maxTurns}
          queryScope={queryScope}
          includeOracleTuples={includeOracleTuples}
          running={qaRun.state.status === "running"}
          disabled={!canRun}
          onQuestionChange={setQuestionDraft}
          onMaxTurnsChange={setMaxTurns}
          onQueryScopeChange={setQueryScope}
          onIncludeOracleTuplesChange={setIncludeOracleTuples}
          onRun={startRun}
          onCancel={qaRun.cancel}
        />

        <RunStatus state={qaRun.state} />

        <div className="turn-workspace">
          <TurnNavigator
            turns={qaRun.state.turns}
            selectedTurnIndex={selection.selectedTurnIndex}
            onSelect={selection.selectTurn}
          />

          <TurnInspector
            turn={selection.selectedTurn}
            selectedAnswerIndex={selection.selectedAnswerIndex}
            selectedDerivationIndex={
              selection.selectedDerivationIndex
            }
            selectedOccurrenceIndex={
              selection.selectedOccurrenceIndex
            }
            onSelectAnswer={selection.selectAnswer}
            onSelectDerivation={selection.selectDerivation}
            onSelectOccurrence={selection.selectOccurrence}
          />
        </div>
      </section>

      <BenchmarkPanel
        reference={browser.reference}
        derivation={selectedDerivation}
        selectedOccurrenceIndex={selection.selectedOccurrenceIndex}
      />
    </div>
  );
}
