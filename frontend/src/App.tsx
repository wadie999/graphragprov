import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { EvidenceRole } from "./api/graphTypes";
import type { QueryRun } from "./api/runTypes";
import type {
  GraphBuildMode,
  QueryMode,
  WorkspaceSourceInput,
} from "./api/types";
import { Brand } from "./components/Brand";
import { CaseAuthoring } from "./components/CaseAuthoring";
import { CaseHeader } from "./components/CaseHeader";
import { ExperimentSidebar } from "./components/ExperimentSidebar";
import { GraphPanel } from "./components/GraphPanel";
import { MetricsStrip } from "./components/MetricsStrip";
import { QueryEditors } from "./components/QueryEditors";
import { QuestionBar } from "./components/QuestionBar";
import { ResultPanel } from "./components/ResultPanel";
import { SourcePanel } from "./components/SourcePanel";
import { useWorkbench } from "./hooks/useWorkbench";
import {
  activeOccurrences,
  activeRole,
  emptySelection,
  type EvidenceSelection,
} from "./state/selection";

export default function App() {
  const workbench = useWorkbench();
  const snapshot = workbench.snapshot.data;

  const [question, setQuestion] = useState("");
  const [sparql, setSparql] = useState("");
  const [planId, setPlanId] = useState<string>();
  const [run, setRun] = useState<QueryRun | null>(null);

  const [queryMode, setQueryMode] =
    useState<QueryMode>("whole_graph");

  const [busy, setBusy] = useState<
    "ask" | "run" | "save" | "build" | null
  >(null);

  const [error, setError] = useState<string>();

  const [selection, setSelection] =
    useState<EvidenceSelection>(emptySelection);

  const [editingWorkspace, setEditingWorkspace] =
    useState(false);

  useEffect(() => {
    if (!snapshot) {
      return;
    }

    setQuestion(
      snapshot.benchmark?.question
        ?? snapshot.build_question
        ?? "",
    );

    setSparql("");
    setPlanId(undefined);
    setRun(null);
    setError(undefined);
    setSelection(emptySelection);

    setEditingWorkspace(
      snapshot.origin === "workspace"
      && !snapshot.graph,
    );
  }, [snapshot?.snapshot_id]);

  async function ask() {
    if (
      !snapshot
      || !question.trim()
    ) {
      return;
    }

    setBusy("ask");
    setError(undefined);
    setSelection(emptySelection);

    try {
      if (
        queryMode === "interactive"
      ) {
        const interactiveRun =
          await api.interactive(
            snapshot.snapshot_id,
            question.trim(),
            5,
          );

        setPlanId(undefined);
        setRun(interactiveRun);
        setSparql(
          interactiveRun.semantic_sparql,
        );

        return;
      }

      const plan =
        await api.plan(
          snapshot.snapshot_id,
          question.trim(),
        );

      setPlanId(
        plan.plan_id,
      );

      if (
        plan.status !== "query"
        || !plan.sparql
      ) {
        setRun(null);
        setSparql("");

        setError(
          `${plan.status}: ${plan.rationale}`,
        );

        return;
      }

      setSparql(
        plan.sparql,
      );

      setRun(
        await api.run(
          snapshot.snapshot_id,
          plan.sparql,
          question.trim(),
          plan.plan_id,
        ),
      );
    } catch (reason) {
      setError(
        message(reason),
      );
    } finally {
      setBusy(null);
    }
  }

  async function runSparql() {
    if (
      !snapshot
      || !sparql.trim()
    ) {
      return;
    }

    setBusy("run");
    setError(undefined);
    setSelection(emptySelection);

    try {
      setRun(
        await api.run(
          snapshot.snapshot_id,
          sparql,
          question.trim(),
          planId,
        ),
      );
    } catch (reason) {
      setError(
        message(reason),
      );
    } finally {
      setBusy(null);
    }
  }

  function loadReference() {
    if (
      !snapshot?.reference_run
    ) {
      return;
    }

    setRun(
      snapshot.reference_run,
    );

    setSparql(
      snapshot.reference_run
        .semantic_sparql,
    );

    setPlanId(undefined);
    setSelection(emptySelection);
    setError(undefined);
  }

  async function createExperiment(
    name: string,
  ) {
    const experiment =
      await api.createExperiment(
        name,
      );

    await workbench
      .refreshExperiments();

    workbench.setExperimentId(
      experiment.experiment_id,
    );

    workbench.setSnapshotId(
      undefined,
    );
  }

  async function createCase(
    name: string,
  ) {
    if (
      !workbench.experimentId
    ) {
      throw new Error(
        "Select a workspace experiment first.",
      );
    }

    const created =
      await api.createCase(
        workbench.experimentId,
        name,
      );

    await workbench.refreshCases(
      workbench.experimentId,
    );

    workbench.setSnapshotId(
      created.snapshot_id,
    );
  }

  async function saveWorkspaceSources(
    sources: WorkspaceSourceInput[],
  ) {
    if (
      !snapshot
      || snapshot.origin !== "workspace"
    ) {
      return;
    }

    setBusy("save");
    setError(undefined);

    try {
      const draft =
        await api.updateSources(
          snapshot.experiment_id,
          snapshot.case_id,
          sources,
        );

      await workbench.refreshCases(
        snapshot.experiment_id,
      );

      workbench.selectSnapshot(
        draft,
      );
    } catch (reason) {
      setError(
        message(reason),
      );

      throw reason;
    } finally {
      setBusy(null);
    }
  }

  async function buildWorkspaceGraph(
    sources: WorkspaceSourceInput[],
    mode: GraphBuildMode,
    buildQuestion?: string,
  ) {
    if (
      !snapshot
      || snapshot.origin !== "workspace"
    ) {
      return;
    }

    setBusy("build");
    setError(undefined);

    try {
      await api.updateSources(
        snapshot.experiment_id,
        snapshot.case_id,
        sources,
      );

      const built =
        await api.buildGraph(
          snapshot.experiment_id,
          snapshot.case_id,
          mode,
          buildQuestion,
        );

      await workbench.refreshCases(
        snapshot.experiment_id,
      );

      workbench.selectSnapshot(
        built,
      );

      setEditingWorkspace(
        false,
      );
    } catch (reason) {
      setError(
        message(reason),
      );

      throw reason;
    } finally {
      setBusy(null);
    }
  }

  function hoverOccurrence(
    id?: string,
    role?: EvidenceRole,
  ) {
    setSelection(
      (value) => ({
        ...value,

        hoveredOccurrenceIds:
          id
            ? [id]
            : [],

        hoveredRole:
          id
            ? role
            : undefined,
      }),
    );
  }

  if (
    workbench.experiments
      .isLoading
  ) {
    return (
      <div className="loading-screen">
        Loading workbench…
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="left-rail">
        <Brand />

        <ExperimentSidebar
          experiments={
            workbench.experiments
              .data
            ?? []
          }
          cases={
            workbench.cases
              .data
            ?? []
          }
          experimentId={
            workbench.experimentId
          }
          snapshotId={
            workbench.snapshotId
          }
          onExperiment={
            (id) => {
              workbench
                .setExperimentId(
                  id,
                );

              workbench
                .setSnapshotId(
                  undefined,
                );
            }
          }
          onCase={
            workbench.setSnapshotId
          }
          onCreateExperiment={
            createExperiment
          }
          onCreateCase={
            createCase
          }
        />
      </div>

      <main className="workspace">
        {snapshot
          ? (
            editingWorkspace
            && snapshot.origin
              === "workspace"
              ? (
                <CaseAuthoring
                  snapshot={
                    snapshot
                  }
                  busy={
                    busy === "save"
                    || busy === "build"
                      ? busy
                      : null
                  }
                  onSave={
                    saveWorkspaceSources
                  }
                  onBuild={
                    buildWorkspaceGraph
                  }
                  onCancel={
                    snapshot.graph
                      ? () =>
                          setEditingWorkspace(
                            false,
                          )
                      : undefined
                  }
                />
              )
              : (
                <>
                  <div className="workspace-header">
                    <CaseHeader
                      snapshot={
                        snapshot
                      }
                      onEditSources={
                        snapshot.origin
                          === "workspace"
                          ? () =>
                              setEditingWorkspace(
                                true,
                              )
                          : undefined
                      }
                    />

                    <MetricsStrip
                      metrics={
                        snapshot.metrics
                          .items
                      }
                    />

                    {error && (
                      <div className="error-banner">
                        {error}
                      </div>
                    )}
                  </div>

                  <div className="inspection-grid">
                    <GraphPanel
                      snapshot={
                        snapshot
                      }
                      activeOccurrenceIds={
                        activeOccurrences(
                          selection,
                        )
                      }
                      activeRole={
                        activeRole(
                          selection,
                        )
                      }
                      onHoverOccurrences={
                        (ids) =>
                          setSelection(
                            (value) => ({
                              ...value,

                              hoveredOccurrenceIds:
                                ids,

                              hoveredRole:
                                undefined,
                            }),
                          )
                      }
                      onSelectOccurrences={
                        (ids) =>
                          setSelection(
                            (value) => ({
                              ...value,

                              selectedOccurrenceIds:
                                ids,
                            }),
                          )
                      }
                    />

                    <SourcePanel
                      snapshot={
                        snapshot
                      }
                      activeOccurrenceIds={
                        activeOccurrences(
                          selection,
                        )
                      }
                      activeRole={
                        activeRole(
                          selection,
                        )
                      }
                      onHoverOccurrence={
                        hoverOccurrence
                      }
                    />
                  </div>

                  <section className="execution-dock">
                    <QuestionBar
                      question={
                        question
                      }
                      onQuestion={
                        setQuestion
                      }
                      onAsk={
                        ask
                      }
                      askBusy={
                        busy === "ask"
                      }
                      queryMode={
                        queryMode
                      }
                      onQueryMode={
                        setQueryMode
                      }
                      disabled={
                        !snapshot.graph
                      }
                    />

                    <div className="execution-body">
                      <QueryEditors
                        sparql={
                          sparql
                        }
                        rewritten={
                          run?.rewritten_sparql
                          ?? ""
                        }
                        run={
                          run
                        }
                        onSparql={
                          (value) => {
                            setSparql(
                              value,
                            );

                            setPlanId(
                              undefined,
                            );
                          }
                        }
                        onRun={
                          runSparql
                        }
                        runBusy={
                          busy === "run"
                        }
                        disabled={
                          !snapshot.graph
                        }
                        onLoadReference={
                          snapshot.reference_run
                            ? loadReference
                            : undefined
                        }
                      />

                      <ResultPanel
                        snapshot={
                          snapshot
                        }
                        run={
                          run
                        }
                        selectedOccurrenceIds={
                          selection
                            .selectedOccurrenceIds
                        }
                        onSelect={
                          (ids) =>
                            setSelection(
                              (value) => ({
                                ...value,

                                selectedOccurrenceIds:
                                  ids,
                              }),
                            )
                        }
                        onHoverOccurrence={
                          hoverOccurrence
                        }
                      />
                    </div>
                  </section>
                </>
              )
          )
          : (
            <div className="empty-workspace">
              <strong>
                No case selected
              </strong>

              <span>
                {workbench.experimentId
                  ? "Use + beside Cases to create a workspace case, or select an existing case."
                  : "Create or select an experiment."}
              </span>
            </div>
          )}
      </main>
    </div>
  );
}

function message(
  reason: unknown,
) {
  return reason instanceof Error
    ? reason.message
    : String(reason);
}