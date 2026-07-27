import type { ExperimentCaseSummary } from "../../domain/experiment";

interface CaseSelectorProps {
  cases: ExperimentCaseSummary[];
  value: string;
  disabled: boolean;
  onChange: (caseId: string) => void;
}

export function CaseSelector({
  cases,
  value,
  disabled,
  onChange,
}: CaseSelectorProps) {
  return (
    <label className="field">
      <span>Benchmark case</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {cases.map((item) => (
          <option key={item.case_id} value={item.case_id}>
            {item.hop_count}-hop — {item.case_id}
          </option>
        ))}
      </select>
    </label>
  );
}
