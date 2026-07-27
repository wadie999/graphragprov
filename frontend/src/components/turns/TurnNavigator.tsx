import type { QaTurn } from "../../domain/qa";

interface TurnNavigatorProps {
  turns: QaTurn[];
  selectedTurnIndex: number | null;
  onSelect: (turnIndex: number) => void;
}

export function TurnNavigator({
  turns,
  selectedTurnIndex,
  onSelect,
}: TurnNavigatorProps) {
  if (turns.length === 0) {
    return (
      <aside className="turn-navigator">
        <h3>Turns</h3>
        <p>No agent turn yet.</p>
      </aside>
    );
  }

  return (
    <aside className="turn-navigator">
      <h3>Turns</h3>

      <div className="turn-list">
        {turns.map((turn) => (
          <button
            type="button"
            key={turn.turn_index}
            className={
              turn.turn_index === selectedTurnIndex
                ? "turn-button selected"
                : "turn-button"
            }
            onClick={() => onSelect(turn.turn_index)}
          >
            <strong>Turn {turn.turn_index}</strong>
            <span>{turn.purpose ?? "waiting"}</span>
            <span>
              {turn.answer_provenances.length} result
              {turn.answer_provenances.length === 1 ? "" : "s"}
            </span>
            <span>{turn.provenance_status ?? "pending"}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}
