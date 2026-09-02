import { Pencil } from "lucide-react";

import type { CaseSnapshot } from "../api/snapshotTypes";

export function CaseHeader(props: {
  snapshot: CaseSnapshot;
  onEditSources?: () => void;
}) {
  const benchmark =
    props.snapshot.benchmark;

  if (!benchmark) {
    const graph =
      props.snapshot.graph;

    return (
      <header className="case-header workspace-case-header">
        <div className="case-heading-row">
          <div>
            <div className="case-kicker">
              Workspace case ·{" "}
              {props.snapshot.case_id}
            </div>

            <h1>
              {props.snapshot.case_label}
            </h1>
          </div>

          {props.onEditSources && (
            <button
              className="secondary-button"
              onClick={
                props.onEditSources
              }
            >
              <Pencil size={13} />
              Edit sources
            </button>
          )}
        </div>

        <div className="case-facts workspace-facts">
          <Fact
            label="Case"
            value={
              props.snapshot.case_label
            }
          />

          <Fact
            label="Build mode"
            value={
              props.snapshot.build_mode
                === "question_conditioned"
                ? "Question-conditioned"
                : "Source-only"
            }
          />

          <Fact
            label="Sources"
            value={String(
              props.snapshot.sources.length,
            )}
          />

          <Fact
            label="Statements"
            value={String(
              graph?.occurrences.length
              ?? 0,
            )}
          />

          <div className="evidence-chain">
            <span>
              {props.snapshot.build_question
                ? "Construction question"
                : "Ground truth"}
            </span>

            <div className="no-ground-truth">
              {props.snapshot.build_question
                ?? "None — this is a user-authored graph build."}
            </div>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="case-header">
      <div className="case-kicker">
        Benchmark case ·{" "}
        {props.snapshot.case_id}
      </div>

      <h1>
        {benchmark.question}
      </h1>

      <div className="case-facts">
        <Fact
          label="Benchmark"
          value={
            benchmark.benchmark
              === "twowiki"
              ? "2WikiMultiHopQA"
              : "MuSiQue"
          }
        />

        <Fact
          label="Hops"
          value={String(
            benchmark.hop_count,
          )}
        />

        <Fact
          label="Expected answer"
          value={
            benchmark.expected_answers[0]
            ?? "—"
          }
        />

        <Fact
          label="Answerable"
          value={
            benchmark.answerable == null
              ? "Unknown"
              : benchmark.answerable
                ? "Yes"
                : "No"
          }
        />

        <div className="evidence-chain">
          <span>
            Evidence chain
          </span>

          <div>
            {benchmark.reasoning_steps.length
              ? benchmark.reasoning_steps.map(
                  (
                    step,
                    index,
                  ) =>
                    renderStep(
                      step,
                      index,
                    ),
                )
              : "Supporting sources only"}
          </div>
        </div>
      </div>
    </header>
  );
}

function Fact({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function renderStep(
  step:
    NonNullable<
      CaseSnapshot["benchmark"]
    >["reasoning_steps"][number],
  index: number,
) {
  const text =
    step.subject
      ? `${step.subject} → ${step.relation} → ${step.object}`
      : `${step.question} → ${step.answer}`;

  return (
    <span
      className="reasoning-step"
      key={step.step_id}
    >
      {index + 1}. {text}
    </span>
  );
}