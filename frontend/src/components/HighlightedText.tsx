import type {
  ReactNode,
} from "react";

import type {
  EvidenceRole,
  EvidenceSpan,
} from "../api/graphTypes";

type Segment = {
  start: number;
  end: number;
  role: EvidenceRole;
};

const ROLE_PRIORITY:
  EvidenceRole[] = [
    "subject",
    "predicate",
    "object",
  ];

export function HighlightedText(
  props: {
    text: string;

    spans: EvidenceSpan[][];

    segment?:
      | "title"
      | "text";
  },
) {
  const segments =
    partition(
      props.text.length,
      props.spans,
      props.segment
      ?? "text",
    );

  if (!segments.length) {
    return (
      <>
        {props.text}
      </>
    );
  }

  const parts:
    ReactNode[] = [];

  let cursor = 0;

  for (
    const item
    of segments
  ) {
    if (
      item.start > cursor
    ) {
      parts.push(
        props.text.slice(
          cursor,
          item.start,
        ),
      );
    }

    parts.push(
      <mark
        className={
          `evidence-highlight evidence-role-${item.role}`
        }
        key={
          `${item.start}-${item.end}-${item.role}`
        }
      >
        {props.text.slice(
          item.start,
          item.end,
        )}
      </mark>,
    );

    cursor =
      item.end;
  }

  if (
    cursor
    < props.text.length
  ) {
    parts.push(
      props.text.slice(
        cursor,
      ),
    );
  }

  return (
    <>
      {parts}
    </>
  );
}

function partition(
  length: number,
  groups: EvidenceSpan[][],
  segment:
    | "title"
    | "text",
): Segment[] {
  const spans =
    groups
      .flat()
      .filter(
        (item) =>
          item.segment
            === segment
          && item.end
            > item.start,
      )
      .map(
        (item) => ({
          start:
            Math.max(
              0,
              item.start,
            ),

          end:
            Math.min(
              length,
              item.end,
            ),

          role:
            item.role,
        }),
      )
      .filter(
        (item) =>
          item.end
          > item.start,
      );

  if (!spans.length) {
    return [];
  }

  const boundaries =
    Array.from(
      new Set(
        spans.flatMap(
          (item) => [
            item.start,
            item.end,
          ],
        ),
      ),
    ).sort(
      (a, b) =>
        a - b,
    );

  const result:
    Segment[] = [];

  for (
    let index = 0;
    index
      < boundaries.length - 1;
    index += 1
  ) {
    const start =
      boundaries[index];

    const end =
      boundaries[
        index + 1
      ];

    const covering =
      spans.filter(
        (span) =>
          span.start <= start
          && span.end >= end,
      );

    if (
      !covering.length
    ) {
      continue;
    }

    const role =
      ROLE_PRIORITY.find(
        (candidate) =>
          covering.some(
            (span) =>
              span.role
              === candidate,
          ),
      )
      ?? covering[0].role;

    const previous =
      result.at(-1);

    if (
      previous
      && previous.end
        === start
      && previous.role
        === role
    ) {
      previous.end = end;
    } else {
      result.push({
        start,
        end,
        role,
      });
    }
  }

  return result;
}