# Provenance Token Design

## Goal

NPCS returns provenance polynomials whose variables identify the graph statements used to produce an answer.

Our system must decode every variable into:

1. the exact RDF statement used;
2. the source unit from which it was extracted;
3. the exact title or text spans supporting its subject, predicate, and object.

The important object is therefore not only an RDF triple. It is a **grounded statement occurrence**.

---

## Grounded statement occurrence

We define an occurrence as:

\[
g = (u, t, E_s, E_p, E_o)
\]

where:

- \(u\) is the source-unit identifier;
- \(t = (s,p,o)\) is the RDF triple;
- \(E_s\) is the evidence supporting the subject;
- \(E_p\) is the evidence supporting the predicate;
- \(E_o\) is the evidence supporting the object.

A source unit contains two immutable segments:

    tl = title
    tx = paragraph text

A span is represented as:

\[
(\text{segment}, \text{start}, \text{end})
\]

using zero-based, half-open character offsets.

For example:

    tx:25-41

means:

    source.text[25:41]

Evidence may contain several spans. Before generating the token, spans are deduplicated and sorted canonically so that the order emitted by the LLM does not affect statement identity.

---

## Why spans alone are insufficient

Consider two statements extracted from the same phrase:

    (A, commonlyKnownAs, B)
    (A, aliasOf, B)

They may use exactly the same subject, predicate, and object spans.

A token containing only the source unit and offsets would assign both statements the same provenance variable. That variable could no longer be decoded into one unique graph record.

NPCS would still correctly compute a polynomial for the graph it received, but information would already have been lost during graph encoding.

Therefore:

> Text spans identify evidence, while provenance tokens identify grounded statement occurrences.

The semantic RDF triple must contribute to the token identity.

---

## Token structure

The proposed token format is:

    po1:<unit>:s=<subject-evidence>:p=<predicate-evidence>:o=<object-evidence>:t=<triple-hash>

Example:

    po1:u_0a5e4e80:s=tx:0-23:p=tx:25-41:o=tx:42-54:t=16e1f63eec7e79c9

Interpretation:

    po1                 token format version
    u_0a5e4e80          source unit
    s=tx:0-23           subject evidence
    p=tx:25-41          predicate evidence
    o=tx:42-54          object evidence
    t=...               hash of the canonical RDF triple

Multiple spans are joined with `+`:

    s=tl:0-15+tx:0-2

The triple hash is computed from a deterministic serialization of the RDF subject, predicate, and object.

Typed-literal lexical forms and datatype IRIs are part of this serialization.

Conceptually:

\[
\tau(g)
=

\operatorname{encode}(u,E_s,E_p,E_o)
\;\Vert\;
H(\operatorname{canonical}(s,p,o))
\]

where \(H\) is SHA-256.

---

## Identity rules

### Same spans, different RDF triples

These statements:

    (A, commonlyKnownAs, B)
    (A, aliasOf, B)

receive different tokens because their triple hashes differ.

### Same RDF triple, different evidence

Different evidence spans produce different tokens.

They represent two independent textual derivations of the same semantic triple.

### Same triple and evidence, different source units

Different source-unit identifiers produce different tokens.

### Exact duplicate extraction

The same unit, RDF triple, and evidence produce the same token.

Exact duplicates are intentionally merged. An extraction-run identifier is not part of statement identity. Run information may be stored separately as metadata.

---

## Required properties

Let:

\[
\tau : G \rightarrow X
\]

map grounded statement occurrences to NPCS provenance variables.

The mapping must be deterministic:

\[
g_1 = g_2
\Rightarrow
\tau(g_1)=\tau(g_2)
\]

Reprocessing the same occurrence must generate the same identifier.

The mapping must also be injective on the materialized dataset:

\[
\tau(g_1)=\tau(g_2)
\Rightarrow
g_1=g_2
\]

Different loaded occurrences must not share one variable.

Surjectivity over all possible token values is unnecessary. The mapping only needs to be a bijection between the materialized occurrences and the tokens actually generated for them.

Absolute mathematical injectivity cannot be obtained from a finite cryptographic hash over an unlimited domain. In practice, we use SHA-256 and verify during ingestion that an existing token never maps to a different canonical occurrence.

Injectivity over the published dataset is therefore an implementation invariant, not only a probabilistic assumption.

---

## Why injectivity matters for NPCS

Let \(S\) be the set of grounded statement occurrences and let:

\[
\rho : S \rightarrow X
\]

assign provenance variables to them.

If two different occurrences receive the same variable:

\[
g_1 \neq g_2
\quad\text{but}\quad
\rho(g_1)=\rho(g_2)=x
\]

NPCS can still return a polynomial that is correct relative to the encoded graph. However, the encoded graph has already merged two distinct records.

For alternative derivations, two records may appear as:

\[
x \oplus x = 2x
\]

The multiplicity may remain visible, but the identity of the two records is lost.

For a joint derivation, using both records may produce:

\[
x \otimes x = x^2
\]

This is indistinguishable from one record being used twice in a self-join.

Most importantly, the inverse mapping:

\[
\tau^{-1}
\]

would no longer be a function. One polynomial variable could refer to several RDF statements or several textual groundings.

This would directly invalidate our claim that each returned variable decodes to one exact statement occurrence and its exact textual evidence.

---

## RDF representation

Each source unit is stored in its own named graph.

Example TriG-star representation:

    GRAPH <https://kg.example/unit/u_0a5e4e80> {
        <https://kg.example/id/A>
            <https://kg.example/id/commonlyKnownAs>
            <https://kg.example/id/B> .

        <<
            <https://kg.example/id/A>
            <https://kg.example/id/commonlyKnownAs>
            <https://kg.example/id/B>
        >>
            <https://prov.example/occurrenceOf>
            "po1:u_0a5e4e80:s=tx:0-23:p=tx:25-41:o=tx:42-54:t=16e1f63eec7e79c9" .
    }

The semantic triple remains directly queryable.

The RDF-star annotation connects the triple to the grounded occurrence identifier used by NPCS.

Several independent occurrences of the same semantic triple are represented using several distinct `occurrenceOf` tokens.

For example:

    << :A :bornIn :B >>
        prov:occurrenceOf "token-from-source-1" .

    << :A :bornIn :B >>
        prov:occurrenceOf "token-from-source-2" .

The underlying semantic triple is the same, but the two grounded occurrences remain distinguishable.

---

## Canonicalization rules

To keep token generation deterministic:

1. the complete source-unit identifier is used;
2. title spans use `tl`;
3. paragraph-text spans use `tx`;
4. offsets are zero-based and end-exclusive;
5. duplicate evidence spans are removed;
6. spans are sorted canonically;
7. RDF terms are serialized deterministically;
8. typed literals preserve their lexical form and datatype;
9. blank nodes are excluded or deterministically skolemized;
10. the same token format version is always included.

The full SHA-256 hash should be used internally.

A shortened prefix may be displayed for debugging, but it should not be treated as the canonical identity unless ingestion verifies that no collision exists.

---

## Ingestion invariant

During serialization, the implementation maintains a mapping:

    provenance token -> canonical grounded occurrence

When a token is generated:

- if it is new, the occurrence is registered;
- if it already exists for the same occurrence, the duplicate is ignored;
- if it already exists for a different occurrence, ingestion fails.

This check guarantees injectivity on the materialized dataset.

---

## Scope of the guarantee

The token identifies which materialized graph occurrence participated in query execution and which exact source spans were attached to it.

It does not prove that:

- the extracted RDF statement is semantically correct;
- the chosen predicate is the best abstraction;
- the SPARQL query is correct;
- the source text is true;
- entity resolution is correct;
- the answer is factually correct.

The guarantee is deliberately narrower:

> Every provenance variable returned by NPCS decodes to one unique materialized RDF statement occurrence and its exact textual evidence.
