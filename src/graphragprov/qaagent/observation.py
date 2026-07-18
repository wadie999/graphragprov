"""Observation of validated semantic RDF stored in GraphDB."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol, cast

from rdflib import Literal as RDFLiteral
from rdflib import URIRef

from graphragprov.rdf.terms import unit_graph_iri

QAObservedObjectType = Literal[
    "uri",
    "literal",
]


class SPARQLQueryExecutor(Protocol):
    """Minimal GraphDB query contract required by the QA agent."""

    def query(
        self,
        sparql: str,
    ) -> dict[str, object]:
        """Execute a SPARQL query."""


@dataclass(frozen=True, slots=True)
class QAObservedTriple:
    """One semantic RDF triple observed in a named graph."""

    graph_iri: str
    subject_iri: str
    predicate_iri: str
    object_type: QAObservedObjectType
    object_value: str
    object_datatype: str | None = None
    object_language: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("graph IRI", self.graph_iri),
            ("subject IRI", self.subject_iri),
            ("predicate IRI", self.predicate_iri),
        ):
            if not value.strip():
                raise ValueError(f"observed {name} must not be empty")

        if self.object_type not in (
            "uri",
            "literal",
        ):
            raise ValueError("observed object type must be uri or literal")

        if self.object_type == "uri" and not self.object_value.strip():
            raise ValueError("observed object IRI must not be empty")

        if self.object_datatype is not None and not self.object_datatype.strip():
            raise ValueError("observed object datatype must not be empty")

        if self.object_language is not None and not self.object_language.strip():
            raise ValueError("observed object language must not be empty")

        if self.object_type == "uri" and (
            self.object_datatype is not None or self.object_language is not None
        ):
            raise ValueError("observed object IRI cannot have datatype or language")

        if self.object_datatype is not None and self.object_language is not None:
            raise ValueError("observed literal cannot have both datatype and language")

    def to_nquad(self) -> str:
        """Serialize the observed tuple as one deterministic N-Quad."""

        subject = URIRef(self.subject_iri).n3()

        predicate = URIRef(self.predicate_iri).n3()

        graph = URIRef(self.graph_iri).n3()

        if self.object_type == "uri":
            object_term = URIRef(self.object_value).n3()
        else:
            datatype = URIRef(self.object_datatype) if self.object_datatype is not None else None

            object_term = RDFLiteral(
                self.object_value,
                datatype=datatype,
                lang=self.object_language,
                normalize=False,
            ).n3()

        return f"{subject} {predicate} {object_term} {graph} ."

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable tuple."""

        return {
            "graph_iri": self.graph_iri,
            "subject_iri": self.subject_iri,
            "predicate_iri": self.predicate_iri,
            "object_type": self.object_type,
            "object_value": self.object_value,
            "object_datatype": self.object_datatype,
            "object_language": self.object_language,
        }


@dataclass(frozen=True, slots=True)
class QAAgentObservation:
    """Semantic graph context observed by a QA agent."""

    query: str
    triples: tuple[QAObservedTriple, ...]

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("observation query must not be empty")

    @property
    def graph_iris(self) -> tuple[str, ...]:
        """Return observed named graphs deterministically."""

        return tuple(sorted({triple.graph_iri for triple in self.triples}))

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable observation."""

        return {
            "query": self.query,
            "graph_iris": list(self.graph_iris),
            "triples": [triple.to_dict() for triple in self.triples],
        }


def build_semantic_triple_observation_query(
    *,
    source_unit_ids: Iterable[str] | None,
) -> str:
    """Build a query over semantic triples in allowed named graphs."""

    graph_iris: tuple[str, ...] | None

    if source_unit_ids is None:
        graph_iris = None
    else:
        graph_iris = tuple(sorted({str(unit_graph_iri(unit_id)) for unit_id in source_unit_ids}))

        if not graph_iris:
            raise ValueError("tuple observation requires at least one source unit")

    lines = [
        ("SELECT DISTINCT ?graph ?subject ?predicate ?object"),
        "WHERE {",
    ]

    if graph_iris is not None:
        lines.append("  VALUES ?graph {")

        lines.extend(f"    <{graph_iri}>" for graph_iri in graph_iris)

        lines.append("  }")

    lines.extend(
        [
            "  GRAPH ?graph {",
            "    ?subject ?predicate ?object .",
            "    FILTER(isIRI(?subject))",
            "  }",
            "}",
            ("ORDER BY ?graph ?subject ?predicate ?object"),
        ]
    )

    return "\n".join(lines)


def observe_semantic_triples(
    *,
    graphdb: SPARQLQueryExecutor,
    source_unit_ids: Iterable[str] | None,
) -> QAAgentObservation:
    """Read validated semantic RDF from GraphDB."""

    query = build_semantic_triple_observation_query(
        source_unit_ids=source_unit_ids,
    )

    result = graphdb.query(query)

    triples = {_parse_observed_triple(binding) for binding in _bindings(result)}

    ordered_triples = tuple(
        sorted(
            triples,
            key=_triple_sort_key,
        )
    )

    return QAAgentObservation(
        query=query,
        triples=ordered_triples,
    )


def _bindings(
    result: dict[str, object],
) -> tuple[dict[str, object], ...]:
    raw_results = result.get("results")

    if not isinstance(raw_results, dict):
        raise ValueError("observation result has no results object")

    raw_bindings = raw_results.get("bindings")

    if not isinstance(raw_bindings, list):
        raise ValueError("observation result has no bindings list")

    bindings: list[dict[str, object]] = []

    for index, binding in enumerate(raw_bindings):
        if not isinstance(binding, dict):
            raise ValueError(f"observation binding {index} must be an object")

        bindings.append(
            cast(
                dict[str, object],
                binding,
            )
        )

    return tuple(bindings)


def _parse_observed_triple(
    binding: dict[str, object],
) -> QAObservedTriple:
    graph_iri = _required_uri(
        binding,
        name="graph",
    )

    subject_iri = _required_uri(
        binding,
        name="subject",
    )

    predicate_iri = _required_uri(
        binding,
        name="predicate",
    )

    object_binding = _term_binding(
        binding,
        name="object",
    )

    raw_type = object_binding.get("type")

    object_value = object_binding.get("value")

    if not isinstance(object_value, str):
        raise ValueError("observation object value must be a string")

    if raw_type == "uri":
        return QAObservedTriple(
            graph_iri=graph_iri,
            subject_iri=subject_iri,
            predicate_iri=predicate_iri,
            object_type="uri",
            object_value=object_value,
        )

    if raw_type not in (
        "literal",
        "typed-literal",
    ):
        raise ValueError("observation object must be a URI or literal")

    datatype = object_binding.get("datatype")

    if datatype is not None and not isinstance(
        datatype,
        str,
    ):
        raise ValueError("observation object datatype must be a string")

    language = object_binding.get("xml:lang")

    if language is not None and not isinstance(
        language,
        str,
    ):
        raise ValueError("observation object language must be a string")

    return QAObservedTriple(
        graph_iri=graph_iri,
        subject_iri=subject_iri,
        predicate_iri=predicate_iri,
        object_type="literal",
        object_value=object_value,
        object_datatype=datatype,
        object_language=language,
    )


def _required_uri(
    binding: dict[str, object],
    *,
    name: str,
) -> str:
    term = _term_binding(
        binding,
        name=name,
    )

    if term.get("type") != "uri":
        raise ValueError(f"observation {name} must be a URI")

    value = term.get("value")

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"observation {name} URI must not be empty")

    return value


def _term_binding(
    binding: dict[str, object],
    *,
    name: str,
) -> dict[str, object]:
    raw_term = binding.get(name)

    if not isinstance(raw_term, dict):
        raise ValueError(f"observation binding has no {name} term")

    return cast(
        dict[str, object],
        raw_term,
    )


def _triple_sort_key(
    triple: QAObservedTriple,
) -> tuple[str, ...]:
    return (
        triple.graph_iri,
        triple.subject_iri,
        triple.predicate_iri,
        triple.object_type,
        triple.object_value,
        triple.object_datatype or "",
        triple.object_language or "",
    )
