import type { AnswerProvenance } from "../../domain/provenance";

interface ResultSelectorProps {
  answers: AnswerProvenance[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

export function ResultSelector({
  answers,
  selectedIndex,
  onSelect,
}: ResultSelectorProps) {
  if (answers.length === 0) {
    return <p>No provenance-decoded result for this turn.</p>;
  }

  return (
    <div className="result-selector">
      {answers.map((answer, index) => (
        <button
          type="button"
          key={`${index}-${answer.polynomial}`}
          className={index === selectedIndex ? "selected" : ""}
          onClick={() => onSelect(index)}
        >
          Result {index + 1}
        </button>
      ))}
    </div>
  );
}
