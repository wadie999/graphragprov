import { useMemo, useState } from "react";

import {
  Beaker,
  Check,
  Circle,
  Database,
  FilePlus2,
  FolderPlus,
  Plus,
  Search,
  X,
} from "lucide-react";

import type {
  CaseSummary,
  Experiment,
} from "../api/types";

export function ExperimentSidebar(props: {
  experiments: Experiment[];
  cases: CaseSummary[];
  experimentId?: string;
  snapshotId?: string;

  onExperiment: (id: string) => void;
  onCase: (id: string) => void;

  onCreateExperiment: (
    name: string,
  ) => Promise<void>;

  onCreateCase: (
    name: string,
  ) => Promise<void>;
}) {
  const [filter, setFilter] =
    useState("");

  const [
    newExperiment,
    setNewExperiment,
  ] =
    useState(false);

  const [
    newCase,
    setNewCase,
  ] =
    useState(false);

  const [
    experimentName,
    setExperimentName,
  ] =
    useState("");

  const [
    caseName,
    setCaseName,
  ] =
    useState("");

  const [
    busy,
    setBusy,
  ] =
    useState<
      "experiment"
      | "case"
      | null
    >(null);

  const [
    error,
    setError,
  ] =
    useState<string>();

  const selectedExperiment =
    props.experiments.find(
      (item) =>
        item.experiment_id
        === props.experimentId,
    );

  const cases =
    useMemo(
      () =>
        props.cases.filter(
          (item) =>
            `${item.label} ${item.case_id}`
              .toLowerCase()
              .includes(
                filter.toLowerCase(),
              ),
        ),
      [
        filter,
        props.cases,
      ],
    );

  async function createExperiment() {
    if (
      !experimentName.trim()
    ) {
      return;
    }

    setBusy(
      "experiment",
    );

    setError(
      undefined,
    );

    try {
      await props.onCreateExperiment(
        experimentName.trim(),
      );

      setExperimentName(
        "",
      );

      setNewExperiment(
        false,
      );
    } catch (reason) {
      setError(
        message(reason),
      );
    } finally {
      setBusy(
        null,
      );
    }
  }

  async function createCase() {
    if (
      !caseName.trim()
    ) {
      return;
    }

    setBusy(
      "case",
    );

    setError(
      undefined,
    );

    try {
      await props.onCreateCase(
        caseName.trim(),
      );

      setCaseName(
        "",
      );

      setNewCase(
        false,
      );
    } catch (reason) {
      setError(
        message(reason),
      );
    } finally {
      setBusy(
        null,
      );
    }
  }

  return (
    <aside className="sidebar">
      <section>
        <div className="sidebar-heading">
          <h3>
            Experiments
          </h3>

          <button
            className="icon-button"
            title="Create experiment"
            onClick={() =>
              setNewExperiment(
                (value) =>
                  !value,
              )
            }
          >
            <Plus size={15} />
          </button>
        </div>

        {newExperiment && (
          <div className="inline-create">
            <input
              autoFocus
              value={
                experimentName
              }
              placeholder="Experiment name"
              onChange={
                (event) =>
                  setExperimentName(
                    event.target
                      .value,
                  )
              }
              onKeyDown={
                (event) => {
                  if (
                    event.key
                    === "Enter"
                  ) {
                    void createExperiment();
                  }
                }
              }
            />

            <button
              onClick={() =>
                void createExperiment()
              }
              disabled={
                busy
                === "experiment"
              }
            >
              <FolderPlus
                size={14}
              />
            </button>
          </div>
        )}

        {props.experiments.map(
          (item) => (
            <button
              className={
                `nav-card ${
                  item.experiment_id
                  === props.experimentId
                    ? "active"
                    : ""
                }`
              }
              key={
                item.experiment_id
              }
              onClick={() =>
                props.onExperiment(
                  item.experiment_id,
                )
              }
            >
              {item.origin
                === "workspace"
                ? (
                  <FilePlus2
                    size={17}
                  />
                )
                : item.benchmark
                  === "twowiki"
                  ? (
                    <Beaker
                      size={17}
                    />
                  )
                  : (
                    <Database
                      size={17}
                    />
                  )}

              <span>
                <strong>
                  {item.label}
                </strong>

                <small>
                  {item.case_count} cases
                  {" · "}
                  {item.origin
                    === "workspace"
                    ? "workspace"
                    : "frozen"}
                </small>
              </span>
            </button>
          ),
        )}
      </section>

      <section className="case-section">
        <div className="sidebar-heading">
          <h3>
            Cases
          </h3>

          {selectedExperiment
            ?.origin
            === "workspace" && (
            <button
              className="icon-button"
              title="Create case"
              onClick={() =>
                setNewCase(
                  (value) =>
                    !value,
                )
              }
            >
              <Plus size={15} />
            </button>
          )}
        </div>

        {newCase
          && selectedExperiment
            ?.origin
            === "workspace"
          && (
            <div className="inline-create">
              <input
                autoFocus
                value={
                  caseName
                }
                placeholder="Case name"
                onChange={
                  (event) =>
                    setCaseName(
                      event.target
                        .value,
                    )
                }
                onKeyDown={
                  (event) => {
                    if (
                      event.key
                      === "Enter"
                    ) {
                      void createCase();
                    }
                  }
                }
              />

              <button
                onClick={() =>
                  void createCase()
                }
                disabled={
                  busy
                  === "case"
                }
              >
                <FilePlus2
                  size={14}
                />
              </button>
            </div>
          )}

        <label className="search-box">
          <Search size={15} />

          <input
            value={
              filter
            }
            onChange={
              (event) =>
                setFilter(
                  event.target
                    .value,
                )
            }
            placeholder="Filter cases…"
          />
        </label>

        {error && (
          <div className="sidebar-error">
            {error}
          </div>
        )}

        <div className="case-list">
          {cases.map(
            (item) => {
              const status =
                caseStatus(
                  item,
                );

              return (
                <button
                  key={
                    item.case_id
                  }
                  className={
                    item.snapshot_id
                    === props.snapshotId
                      ? "active"
                      : ""
                  }
                  onClick={() =>
                    props.onCase(
                      item.snapshot_id,
                    )
                  }
                >
                  <span className="case-list-main">
                    <CaseStatusIcon
                      status={
                        status
                      }
                    />

                    <span className="case-list-id">
                      {item.label}
                    </span>
                  </span>

                  <small>
                    {item.origin
                      === "workspace"
                      ? item.graph_available
                        ? "built"
                        : "draft"
                      : `${item.hop_count ?? 0} hop`}
                  </small>
                </button>
              );
            },
          )}
        </div>
      </section>
    </aside>
  );
}

type CaseStatus =
  | {
      kind: "success";
      title: string;
    }
  | {
      kind: "failure";
      title: string;
    }
  | {
      kind: "draft";
      title: string;
    };

function caseStatus(
  item: CaseSummary,
): CaseStatus {
  if (
    item.origin
    === "workspace"
  ) {
    if (
      item.graph_available
    ) {
      return {
        kind: "success",
        title:
          "Graph build complete",
      };
    }

    return {
      kind: "draft",
      title:
        "Draft — graph not built yet",
    };
  }

  if (
    item.artifact_status
      === "complete"
    && item.graph_available
    && item.provenance_available
  ) {
    return {
      kind: "success",
      title:
        "Reference execution complete with provenance",
    };
  }

  return {
    kind: "failure",
    title:
      failureTitle(
        item,
      ),
  };
}

function failureTitle(
  item: CaseSummary,
): string {
  if (
    item.artifact_status
      === "missing"
  ) {
    return "Reference artifact unavailable";
  }

  if (
    item.artifact_status
  ) {
    return (
      "Reference execution did not complete: "
      + item.artifact_status
    );
  }

  return (
    "Reference execution did not complete"
  );
}

function CaseStatusIcon({
  status,
}: {
  status: CaseStatus;
}) {
  if (
    status.kind
    === "success"
  ) {
    return (
      <span
        className="case-status case-status-success"
        title={
          status.title
        }
        aria-label={
          status.title
        }
      >
        <Check
          size={11}
          strokeWidth={3}
        />
      </span>
    );
  }

  if (
    status.kind
    === "failure"
  ) {
    return (
      <span
        className="case-status case-status-failure"
        title={
          status.title
        }
        aria-label={
          status.title
        }
      >
        <X
          size={11}
          strokeWidth={3}
        />
      </span>
    );
  }

  return (
    <span
      className="case-status case-status-draft"
      title={
        status.title
      }
      aria-label={
        status.title
      }
    >
      <Circle
        size={8}
        strokeWidth={2.5}
      />
    </span>
  );
}

function message(
  reason: unknown,
): string {
  return reason instanceof Error
    ? reason.message
    : String(reason);
}