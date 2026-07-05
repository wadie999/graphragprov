# Grounded RDF Extraction Protocol

Protocol version: `grounded-rdf-v1`

## Purpose

This protocol converts one immutable source unit into zero or more RDF-like statements grounded in exact character spans from that source.

A source unit contains:

- a stable source-unit identifier;
- an exact title;
- an exact paragraph text.

The extractor processes each source unit independently.

## Extractor input

The extractor receives only:

- the source-unit identifier;
- the complete title;
- the complete paragraph text;
- the required output structure;
- the extraction and grounding rules.

The title and paragraph text are supplied exactly as stored. They are not trimmed, lowercased, normalized, rewritten, or concatenated into a new source string.

## Information excluded from extraction

The extractor must not receive:

- the benchmark question;
- the benchmark answer;
- answer aliases;
- question-decomposition hops;
- gold supporting-paragraph labels;
- other paragraphs from the same benchmark case;
- results produced by other source units.

This makes graph construction question-blind and paragraph-independent.

## Role of the title

The title is part of the extraction source.

It may provide information that is required to understand the paragraph, such as:

- the identity of an entity omitted from the paragraph body;
- the referent of a pronoun;
- the expansion of an abbreviated reference;
- the topic represented by the paragraph.

Seeing the title does not make it evidence for every extracted statement.

A title span is attached to a statement component only when that title fragment contributes textual evidence for the component.

## Extracted statements

The extractor returns zero or more RDF-like statements:

```text
(subject, predicate, object)
```

Every subject, predicate, and object contains:

- a normalized output value;
- one or more evidence spans.

An empty statement list is valid when no fully grounded statement can be extracted.

## Evidence spans

Each evidence span identifies:

- `segment`: either `title` or `text`;
- `start`: inclusive character offset;
- `end`: exclusive character offset;
- `quote`: the exact selected substring.

Offsets are relative to the original selected segment.

Offsets are never calculated over prompt labels, separators, JSON formatting, or an artificial concatenation of the title and paragraph text.

A statement component may use several evidence spans when its interpretation depends on several source fragments.

## Validation

An extraction result is accepted only when:

- its source-unit identifier matches the processed source unit;
- every statement component contains evidence;
- every span is inside its declared segment;
- every span satisfies `0 <= start < end`;
- every quote exactly equals `segment[start:end]`.

No approximate matching or normalization is used during validation.

## Interpretation of grounding

A valid evidence span proves that the extracted component is connected to the declared source characters.

It does not by itself prove that:

- the extracted RDF statement is semantically correct;
- a pronoun was resolved correctly;
- the chosen predicate is ontologically appropriate;
- the source text is factually true.

The protocol exposes the textual basis of extraction so these decisions can be inspected and evaluated separately.

## Reproducibility

Every extraction run must preserve:

- the protocol version;
- the prompt version;
- the exact source unit;
- the exact rendered prompt;
- the model and provider configuration;
- the unmodified model response;
- the parsed extraction result;
- the validation outcome.

Provider integration and run persistence are defined in later components.
