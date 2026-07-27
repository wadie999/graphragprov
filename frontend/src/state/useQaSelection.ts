import { useEffect, useMemo, useRef, useState } from "react";

import type { QaTurn } from "../domain/qa";

export interface QaSelection {
  selectedTurn: QaTurn | null;
  selectedTurnIndex: number | null;
  selectedAnswerIndex: number;
  selectedDerivationIndex: number;
  selectedOccurrenceIndex: number | null;
  selectTurn: (turnIndex: number) => void;
  selectAnswer: (answerIndex: number) => void;
  selectDerivation: (derivationIndex: number) => void;
  selectOccurrence: (occurrenceIndex: number | null) => void;
}

export function useQaSelection(turns: QaTurn[]): QaSelection {
  const [selectedTurnIndex, setSelectedTurnIndex] =
    useState<number | null>(null);
  const [selectedAnswerIndex, setSelectedAnswerIndex] = useState(0);
  const [selectedDerivationIndex, setSelectedDerivationIndex] =
    useState(0);
  const [selectedOccurrenceIndex, setSelectedOccurrenceIndex] =
    useState<number | null>(null);
  const latestSeenRef = useRef<number | null>(null);

  const latestTurnIndex = turns.at(-1)?.turn_index ?? null;

  useEffect(() => {
    if (
      latestTurnIndex !== null &&
      latestTurnIndex !== latestSeenRef.current
    ) {
      latestSeenRef.current = latestTurnIndex;
      setSelectedTurnIndex(latestTurnIndex);
      setSelectedAnswerIndex(0);
      setSelectedDerivationIndex(0);
      setSelectedOccurrenceIndex(null);
    }
  }, [latestTurnIndex]);

  const selectedTurn = useMemo(
    () =>
      turns.find((turn) => turn.turn_index === selectedTurnIndex) ??
      null,
    [selectedTurnIndex, turns],
  );

  useEffect(() => {
    const answerCount = selectedTurn?.answer_provenances.length ?? 0;

    if (answerCount === 0) {
      setSelectedAnswerIndex(0);
      setSelectedDerivationIndex(0);
      setSelectedOccurrenceIndex(null);
      return;
    }

    if (selectedAnswerIndex >= answerCount) {
      setSelectedAnswerIndex(0);
    }
  }, [selectedAnswerIndex, selectedTurn]);

  return {
    selectedTurn,
    selectedTurnIndex,
    selectedAnswerIndex,
    selectedDerivationIndex,
    selectedOccurrenceIndex,
    selectTurn: (turnIndex) => {
      setSelectedTurnIndex(turnIndex);
      setSelectedAnswerIndex(0);
      setSelectedDerivationIndex(0);
      setSelectedOccurrenceIndex(null);
    },
    selectAnswer: (answerIndex) => {
      setSelectedAnswerIndex(answerIndex);
      setSelectedDerivationIndex(0);
      setSelectedOccurrenceIndex(null);
    },
    selectDerivation: (derivationIndex) => {
      setSelectedDerivationIndex(derivationIndex);
      setSelectedOccurrenceIndex(null);
    },
    selectOccurrence: setSelectedOccurrenceIndex,
  };
}
