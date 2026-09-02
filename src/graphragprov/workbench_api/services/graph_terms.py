"""Stable RDF term identities and display projections for the workbench."""

from hashlib import sha256
from urllib.parse import unquote

from rdflib import Literal, URIRef

from graphragprov.rdf.terms import ENTITY_NAMESPACE, PREDICATE_NAMESPACE
from graphragprov.workbench_api.models.graph import GraphNode


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode()).hexdigest()[:20]}"


def signature(
    subject: URIRef, predicate: URIRef, object_value: URIRef | Literal
) -> tuple[str, ...]:
    if isinstance(object_value, URIRef):
        return (str(subject), str(predicate), "uri", str(object_value), "", "")
    return (
        str(subject),
        str(predicate),
        "literal",
        str(object_value),
        str(object_value.datatype or ""),
        str(object_value.language or ""),
    )


def iri_node(value: str) -> GraphNode:
    return GraphNode(
        node_id=stable_id("n", value),
        kind="iri",
        value=value,
        label=display_label(value, ENTITY_NAMESPACE),
    )


def object_node(kind: str, value: str, datatype: str | None, language: str | None) -> GraphNode:
    if kind == "uri":
        return iri_node(value)
    key = f"{kind}\0{value}\0{datatype or ''}\0{language or ''}"
    return GraphNode(
        node_id=stable_id("n", key),
        kind=kind,
        value=value,
        label=value,
        datatype=datatype,
        language=language,
    )


def predicate_label(value: str) -> str:
    return display_label(value, PREDICATE_NAMESPACE)


def ntriple(
    subject: str, predicate: str, kind: str, value: str, datatype: str | None, language: str | None
) -> str:
    obj = (
        URIRef(value)
        if kind == "uri"
        else Literal(value, datatype=URIRef(datatype) if datatype else None, lang=language)
    )
    return f"{URIRef(subject).n3()} {URIRef(predicate).n3()} {obj.n3()} ."


def display_label(value: str, namespace: str) -> str:
    return unquote(value[len(namespace) :]) if value.startswith(namespace) else unquote(value)
