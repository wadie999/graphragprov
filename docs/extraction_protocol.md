# Grounded RDF Extraction Protocol

Protocol version: `grounded-rdf-v1`

## Purpose

Convert one immutable source unit into zero or more RDF-like statements grounded in exact source fragments.

A source unit contains:

- a stable `unit_id`;
- an exact title;
- an exact paragraph text.

Each source unit is processed independently.

## Extraction input

The extractor receives only:

- `unit_id`;
- title;
- paragraph text;
- extraction instructions;
- required JSON structure.

It must not receive:

- benchmark questions or answers;
- answer aliases;
- decomposition hops;
- supporting-paragraph labels;
- other paragraphs;
- previous extraction results.

Graph construction is therefore question-blind and source-unit independent.

## Title and text

The title and paragraph jointly form the source unit, but remain separate source segments:

- `title`
- `text`

The title may support entity identification, pronoun resolution, abbreviated references, or an omitted subject.

Seeing the title does not make it evidence for every statement. A title fragment is recorded only when it contributes to the extracted component.

The title and text must never be trimmed, normalized, rewritten, or artificially concatenated for provenance.

## Extracted statements

The extractor returns zero or more statements:

```text
(subject, predicate, object)
```

Each component contains:

- a semantic `value`;
- one or more evidence references.

Semantic values may differ from their surface evidence. For example, the value `Albert Einstein` may be supported by the title fragment `Albert Einstein` and the text fragment `He`.

An empty statement list is valid when no fully grounded statement can be extracted.

## Model-facing evidence references

The language model does not calculate character offsets.

For each evidence fragment, it returns:

- `segment`: `title` or `text`;
- `quote`: an exact non-empty substring;
- `occurrence`: the one-based occurrence of that quote in the segment.

Occurrences are counted from left to right.

Example:

```json
{
  "unit_id": "u_<sha256>",
  "statements": [
    {
      "subject": {
        "value": "Albert Einstein",
        "evidence": [
          {
            "segment": "title",
            "quote": "Albert Einstein",
            "occurrence": 1
          },
          {
            "segment": "text",
            "quote": "He",
            "occurrence": 1
          }
        ]
      },
      "predicate": {
        "value": "bornIn",
        "evidence": [
          {
            "segment": "text",
            "quote": "born in",
            "occurrence": 1
          }
        ]
      },
      "object": {
        "value": "Ulm",
        "evidence": [
          {
            "segment": "text",
            "quote": "Ulm",
            "occurrence": 1
          }
        ]
      }
    }
  ]
}
```

## Deterministic localization

The system converts every evidence reference into an exact span:

```text
(segment, start, end, quote)
```

Where:

- `start` is inclusive;
- `end` is exclusive;
- offsets are relative to the selected original segment;
- `quote` must equal `segment[start:end]` exactly.

No approximate matching, case folding, whitespace normalization, or Unicode normalization is allowed.

## Validation

An extraction result is accepted only when:

- its `unit_id` matches the source unit;
- every subject, predicate, and object has evidence;
- every referenced quote and occurrence exists;
- every resolved span is inside its declared segment;
- every quote exactly matches the resolved source characters.

## Extraction boundaries

The extractor may perform locally supported interpretation such as:

- pronoun resolution;
- title-based subject recovery;
- list expansion;
- abbreviated-reference resolution.

The extraction stage must not automatically add:

- inverse statements;
- symmetric or transitive statements;
- ontology-derived statements;
- external knowledge;
- cross-source links;
- global entity canonicalization.

These operations, when needed, must be implemented as separate explicit stages.

## Interpretation

Exact grounding shows which source fragments support a generated statement.

It does not prove that:

- the statement is semantically correct;
- a coreference was resolved correctly;
- the selected predicate is the only valid formalization;
- the source text is factually true.

These questions must be evaluated separately.

## Reproducibility

Every extraction run must preserve:

- protocol and prompt versions;
- exact source unit;
- exact rendered prompt;
- model and provider configuration;
- unmodified model response;
- parsed result;
- localization and validation outcome.
