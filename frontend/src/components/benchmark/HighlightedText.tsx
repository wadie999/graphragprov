import type {
  EvidenceRole,
  EvidenceSpan,
  EvidenceSegment,
} from "../../domain/provenance";

export interface RoleSpan extends EvidenceSpan {
  role: EvidenceRole;
}

interface HighlightedTextProps {
  text: string;
  segment: EvidenceSegment;
  spans: RoleSpan[];
}

export function HighlightedText({
  text,
  segment,
  spans,
}: HighlightedTextProps) {
  const relevant = spans
    .filter((span) => span.segment === segment)
    .map((span) => ({
      ...span,
      start: clamp(span.start, 0, text.length),
      end: clamp(span.end, 0, text.length),
    }))
    .filter((span) => span.end > span.start);

  if (relevant.length === 0) {
    return <>{text}</>;
  }

  const boundaries = Array.from(
    new Set([
      0,
      text.length,
      ...relevant.flatMap((span) => [span.start, span.end]),
    ]),
  ).sort((left, right) => left - right);

  return (
    <>
      {boundaries.slice(0, -1).map((start, index) => {
        const end = boundaries[index + 1] ?? start;
        const value = text.slice(start, end);
        const activeRoles = relevant
          .filter((span) => span.start <= start && span.end >= end)
          .map((span) => span.role);

        return activeRoles.length > 0 ? (
          <mark
            key={`${start}-${end}`}
            title={`Evidence: ${Array.from(new Set(activeRoles)).join(", ")}`}
          >
            {value}
          </mark>
        ) : (
          <span key={`${start}-${end}`}>{value}</span>
        );
      })}
    </>
  );
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}
