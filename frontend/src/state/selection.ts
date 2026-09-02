import type { EvidenceRole } from "../api/graphTypes";

export type EvidenceSelection = {
  selectedOccurrenceIds: string[];
  hoveredOccurrenceIds: string[];
  hoveredRole?: EvidenceRole;
};

export const emptySelection: EvidenceSelection = {
  selectedOccurrenceIds: [],
  hoveredOccurrenceIds: [],
  hoveredRole: undefined,
};

export function activeOccurrences(
  selection: EvidenceSelection,
): string[] {
  return selection.hoveredOccurrenceIds.length
    ? selection.hoveredOccurrenceIds
    : selection.selectedOccurrenceIds;
}

export function activeRole(
  selection: EvidenceSelection,
): EvidenceRole | undefined {
  return selection.hoveredOccurrenceIds.length
    ? selection.hoveredRole
    : undefined;
}