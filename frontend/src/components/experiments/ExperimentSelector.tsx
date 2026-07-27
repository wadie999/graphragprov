import type { ExperimentSummary } from "../../domain/experiment";

interface ExperimentSelectorProps {
  experiments: ExperimentSummary[];
  value: string;
  disabled: boolean;
  onChange: (experimentId: string) => void;
}

export function ExperimentSelector({
  experiments,
  value,
  disabled,
  onChange,
}: ExperimentSelectorProps) {
  return (
    <label className="field">
      <span>Experiment</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {experiments.map((experiment) => (
          <option
            key={experiment.experiment_id}
            value={experiment.experiment_id}
          >
            {experiment.experiment_id} ({experiment.case_count} cases)
          </option>
        ))}
      </select>
    </label>
  );
}
