import { useEffect, useState } from "react";
import {
  Hammer,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import type { CaseSnapshot } from "../api/snapshotTypes";
import type {
  GraphBuildMode,
  WorkspaceSourceInput,
} from "../api/types";

export function CaseAuthoring(props: {
  snapshot: CaseSnapshot;
  busy: "save" | "build" | null;

  onSave: (
    sources: WorkspaceSourceInput[],
  ) => Promise<void>;

  onBuild: (
    sources: WorkspaceSourceInput[],
    mode: GraphBuildMode,
    question?: string,
  ) => Promise<void>;

  onCancel?: () => void;
}) {
  const [sources, setSources] =
    useState<WorkspaceSourceInput[]>([]);

  const [mode, setMode] =
    useState<GraphBuildMode>(
      props.snapshot.build_mode
      ?? "source_only",
    );

  const [question, setQuestion] =
    useState(
      props.snapshot.build_question
      ?? "",
    );

  const [error, setError] =
    useState<string>();

  useEffect(() => {
    setSources(
      props.snapshot.sources.length
        ? props.snapshot.sources.map(
            (source) => ({
              title: source.title,
              text: source.text,
            }),
          )
        : [
            {
              title: "",
              text: "",
            },
          ],
    );

    setMode(
      props.snapshot.build_mode
      ?? "source_only",
    );

    setQuestion(
      props.snapshot.build_question
      ?? "",
    );

    setError(undefined);
  }, [props.snapshot.snapshot_id]);

  function update(
    index: number,
    field: keyof WorkspaceSourceInput,
    value: string,
  ) {
    setSources((items) =>
      items.map(
        (item, current) =>
          current === index
            ? {
                ...item,
                [field]: value,
              }
            : item,
      ),
    );
  }

  function validSources():
    | WorkspaceSourceInput[]
    | null {
    const normalized =
      sources.map((source) => ({
        title: source.title.trim(),
        text: source.text.trim(),
      }));

    if (
      !normalized.length
      || normalized.some(
        (source) =>
          !source.title
          || !source.text,
      )
    ) {
      setError(
        "Every paragraph needs both a title and paragraph text.",
      );

      return null;
    }

    if (
      mode === "question_conditioned"
      && !question.trim()
    ) {
      setError(
        "Question-conditioned construction requires a question.",
      );

      return null;
    }

    setError(undefined);

    return normalized;
  }

  async function save() {
    const normalized =
      validSources();

    if (!normalized) {
      return;
    }

    try {
      await props.onSave(
        normalized,
      );
    } catch (reason) {
      setError(
        message(reason),
      );
    }
  }

  async function build() {
    const normalized =
      validSources();

    if (!normalized) {
      return;
    }

    try {
      await props.onBuild(
        normalized,
        mode,
        mode === "question_conditioned"
          ? question.trim()
          : undefined,
      );
    } catch (reason) {
      setError(
        message(reason),
      );
    }
  }

  return (
    <section className="authoring-shell">
      <header className="authoring-header">
        <div>
          <div className="case-kicker">
            Workspace case ·{" "}
            {props.snapshot.case_id}
          </div>

          <h1>
            {props.snapshot.case_label}
          </h1>

          <p>
            Add source paragraphs, freeze a graph
            build, then inspect and query it in the
            same workbench as the benchmark cases.
          </p>
        </div>

        {props.onCancel && (
          <button
            className="secondary-button"
            onClick={props.onCancel}
          >
            Back to graph
          </button>
        )}
      </header>

      <div className="authoring-controls panel">
        <div className="construction-mode">
          <span>
            Graph construction
          </span>

          <label>
            <input
              type="radio"
              checked={
                mode === "source_only"
              }
              onChange={() =>
                setMode(
                  "source_only",
                )
              }
            />

            Source-only
          </label>

          <label>
            <input
              type="radio"
              checked={
                mode
                === "question_conditioned"
              }
              onChange={() =>
                setMode(
                  "question_conditioned",
                )
              }
            />

            Question-conditioned
          </label>
        </div>

        {mode
          === "question_conditioned" && (
          <input
            className="construction-question"
            value={question}
            onChange={(event) =>
              setQuestion(
                event.target.value,
              )
            }
            placeholder="Question used only as graph-construction context…"
          />
        )}
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <div className="paragraph-editor-list">
        {sources.map(
          (source, index) => (
            <article
              className="paragraph-editor panel"
              key={index}
            >
              <div className="paragraph-editor-title">
                <strong>
                  Paragraph {index + 1}
                </strong>

                {sources.length > 1 && (
                  <button
                    className="icon-button danger"
                    title="Remove paragraph"
                    onClick={() =>
                      setSources(
                        (items) =>
                          items.filter(
                            (
                              _,
                              current,
                            ) =>
                              current
                              !== index,
                          ),
                      )
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>

              <input
                value={source.title}
                onChange={(event) =>
                  update(
                    index,
                    "title",
                    event.target.value,
                  )
                }
                placeholder="Title"
              />

              <textarea
                value={source.text}
                onChange={(event) =>
                  update(
                    index,
                    "text",
                    event.target.value,
                  )
                }
                placeholder="Paragraph text"
              />
            </article>
          ),
        )}
      </div>

      <footer className="authoring-actions">
        <button
          className="secondary-button"
          onClick={() =>
            setSources(
              (items) => [
                ...items,
                {
                  title: "",
                  text: "",
                },
              ],
            )
          }
        >
          <Plus size={14} />
          Add paragraph
        </button>

        <div>
          <button
            className="secondary-button"
            onClick={() => void save()}
            disabled={
              props.busy !== null
            }
          >
            <Save size={14} />

            {props.busy === "save"
              ? "SAVING…"
              : "SAVE SOURCES"}
          </button>

          <button
            className="primary-button"
            onClick={() => void build()}
            disabled={
              props.busy !== null
            }
          >
            <Hammer size={14} />

            {props.busy === "build"
              ? "BUILDING GRAPH…"
              : "BUILD GRAPH"}
          </button>
        </div>
      </footer>
    </section>
  );
}

function message(reason: unknown): string {
  return reason instanceof Error
    ? reason.message
    : String(reason);
}