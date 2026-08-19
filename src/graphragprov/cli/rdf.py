"""Offline RDF artifact transformations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from rdflib import Literal, URIRef

from graphragprov.benchmarks.musique import (
    collect_musique_source_units,
    load_case,
)
from graphragprov.config import musique_dataset_path
from graphragprov.domain import SourceUnit
from graphragprov.extraction import ExtractionResult, parse_extraction_response
from graphragprov.rdf import (
    rdf_triple,
    serialize_extraction_trig_star,
    unit_graph_iri,
)


def configure_rdf_parser(parser: argparse.ArgumentParser) -> None:
    """Register RDF artifact transformation commands."""

    commands = parser.add_subparsers(dest="rdf_command", required=True)

    export_run = commands.add_parser(
        "export-run",
        help="Reconstruct the RDF-star graph of an existing run.",
    )
    export_run.add_argument(
        "run",
        type=Path,
        help="Path to a run directory or its result.json.",
    )
    export_run.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output TriG-star file. Defaults to <run>/graph.trig.",
    )
    export_run.set_defaults(handler=_export_run)


def _export_run(arguments: argparse.Namespace) -> int:
    input_path = cast(Path, arguments.run)
    requested_output = cast(Path | None, arguments.output)

    run_directory, result_path = _resolve_run(input_path)
    result = _load_json_object(result_path)

    outcome = result.get("outcome")

    if not isinstance(outcome, dict):
        raise ValueError("result.json does not contain an outcome object")

    documents, _ = _load_embedded_graph(
        cast(dict[str, Any], outcome)
    )

    trig_path = requested_output or (run_directory / "graph.trig")
    ttl_path = trig_path.with_suffix(".ttl")

    trig_content = "\n".join(documents)
    ttl_content = _flatten_trig_star_documents(documents)

    trig_path.parent.mkdir(parents=True, exist_ok=True)

    trig_path.write_text(trig_content, encoding="utf-8")
    ttl_path.write_text(ttl_content, encoding="utf-8")

    print(trig_path)
    print(ttl_path)

    return 0

def _flatten_trig_star_documents(documents: list[str]) -> str:
    """Flatten named TriG-star graphs into one Turtle-star visualization graph.

    Semantic triples and RDF-star occurrence annotations are preserved.
    Named-graph membership is intentionally removed.
    """

    prefixes: list[str] = []
    prefix_seen: set[str] = set()
    bodies: list[str] = []

    for document in documents:
        lines = document.splitlines()

        graph_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.startswith("GRAPH ")
            ),
            None,
        )

        if graph_index is None:
            raise ValueError(
                "serialized TriG-star document has no GRAPH declaration"
            )

        if not lines or lines[-1].strip() != "}":
            raise ValueError(
                "serialized TriG-star document has no closing graph brace"
            )

        for line in lines[:graph_index]:
            stripped = line.strip()

            if stripped.startswith("@prefix ") and stripped not in prefix_seen:
                prefix_seen.add(stripped)
                prefixes.append(stripped)

        body = "\n".join(
            line[4:] if line.startswith("    ") else line
            for line in lines[graph_index + 1 : -1]
        ).strip()

        if body:
            bodies.append(body)

    sections: list[str] = []

    if prefixes:
        sections.append("\n".join(prefixes))

    if bodies:
        sections.append("\n\n".join(bodies))

    return "\n\n".join(sections) + "\n"

def _resolve_run(path: Path) -> tuple[Path, Path]:
    if path.is_file():
        if path.name != "result.json":
            raise ValueError(
                "when passing a file, expected result.json"
            )
        return path.parent, path

    if not path.is_dir():
        raise FileNotFoundError(f"run path does not exist: {path}")

    result_path = path / "result.json"

    if result_path.is_file():
        return path, result_path

    support_result = path / "support" / "result.json"

    if support_result.is_file():
        return support_result.parent, support_result

    raise FileNotFoundError(
        f"could not find result.json under {path}"
    )


def _is_h0_multihop_run(
    result: dict[str, Any],
    run_directory: Path,
) -> bool:
    return (
        isinstance(result.get("case_id"), str)
        and (run_directory / "sources").is_dir()
    )


def _load_h0_multihop_graph(
    *,
    result: dict[str, Any],
    run_directory: Path,
) -> tuple[
    list[str],
    list[tuple[SourceUnit, ExtractionResult]],
]:
    case_id = result.get("case_id")

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("result.json has no valid case_id")

    raw_supports = result.get("supporting_paragraphs")

    if not isinstance(raw_supports, list):
        raise ValueError(
            "result.json has no supporting_paragraphs list"
        )

    support_indices: list[int] = []

    for value in raw_supports:
        if not isinstance(value, int):
            raise ValueError(
                "supporting_paragraphs must contain integers"
            )
        support_indices.append(value)

    case = load_case(musique_dataset_path(), case_id)

    sources = collect_musique_source_units((case,))
    source_by_unit_id = {
        source.unit_id: source
        for source in sources
    }

    paragraph_by_index = {
        paragraph.index: paragraph
        for paragraph in case.paragraphs
    }

    documents: list[str] = []
    accepted: list[tuple[SourceUnit, ExtractionResult]] = []

    for paragraph_index in support_indices:
        paragraph = paragraph_by_index.get(paragraph_index)

        if paragraph is None:
            raise ValueError(
                f"MuSiQue case has no paragraph {paragraph_index}"
            )

        source = source_by_unit_id.get(paragraph.unit_id)

        if source is None:
            raise ValueError(
                f"no source unit for paragraph {paragraph_index}"
            )

        extraction = _replay_accepted_extraction(
            source=source,
            paragraph_index=paragraph_index,
            run_directory=run_directory,
        )

        documents.append(
            serialize_extraction_trig_star(
                source,
                extraction,
            )
        )
        accepted.append((source, extraction))

    if not accepted:
        raise ValueError(
            "run contains no supporting graph extractions"
        )

    return documents, accepted


def _replay_accepted_extraction(
    *,
    source: SourceUnit,
    paragraph_index: int,
    run_directory: Path,
) -> ExtractionResult:
    paragraph_directory = (
        run_directory
        / "sources"
        / f"{paragraph_index:02d}"
    )

    if not paragraph_directory.is_dir():
        raise ValueError(
            "missing source artifact directory for "
            f"paragraph {paragraph_index}: "
            f"{paragraph_directory}"
        )

    attempts = sorted(
        path
        for path in paragraph_directory.iterdir()
        if path.is_dir()
    )

    if not attempts:
        raise ValueError(
            f"paragraph {paragraph_index} has no extraction attempts"
        )

    errors: list[str] = []

    for attempt in attempts:
        response_path = attempt / "response.txt"

        if not response_path.is_file():
            continue

        response = response_path.read_text(encoding="utf-8")

        try:
            extraction = parse_extraction_response(
                source,
                response,
            )
        except ValueError as error:
            errors.append(f"{attempt.name}: {error}")
            continue

        extraction.validate_against(source)
        return extraction

    details = "; ".join(errors)

    raise ValueError(
        "could not reconstruct an accepted extraction for "
        f"paragraph {paragraph_index}"
        + (f": {details}" if details else "")
    )


def _verify_against_graphdb_observation(
    *,
    extractions: list[tuple[SourceUnit, ExtractionResult]],
    observation_path: Path,
) -> None:
    observation = _load_json_object(observation_path)
    raw_triples = observation.get("triples")

    if not isinstance(raw_triples, list):
        raise ValueError(
            "graph_observation.json has no triples list"
        )

    observed = {
        _observation_tuple(
            cast(dict[str, Any], raw)
        )
        for raw in raw_triples
        if isinstance(raw, dict)
    }

    expected = set()

    for source, extraction in extractions:
        graph_iri = str(unit_graph_iri(source.unit_id))

        for statement in extraction.statements:
            subject, predicate, object_ = rdf_triple(statement)

            if isinstance(object_, URIRef):
                expected.add(
                    (
                        graph_iri,
                        str(subject),
                        str(predicate),
                        "uri",
                        str(object_),
                        None,
                        None,
                    )
                )
            elif isinstance(object_, Literal):
                expected.add(
                    (
                        graph_iri,
                        str(subject),
                        str(predicate),
                        "literal",
                        str(object_),
                        (
                            str(object_.datatype)
                            if object_.datatype is not None
                            else None
                        ),
                        object_.language,
                    )
                )
            else:
                raise TypeError(
                    f"unsupported RDF object: {type(object_).__name__}"
                )

    if expected == observed:
        return

    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)

    raise ValueError(
        "reconstructed semantic graph does not match "
        "graph_observation.json; "
        f"missing={missing!r}; unexpected={unexpected!r}"
    )


def _observation_tuple(
    raw: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    str | None,
    str | None,
]:
    graph_iri = _required_string(raw, "graph_iri")
    subject_iri = _required_string(raw, "subject_iri")
    predicate_iri = _required_string(raw, "predicate_iri")
    object_type = _required_string(raw, "object_type")
    object_value = _required_string(raw, "object_value")

    object_datatype = raw.get("object_datatype")
    object_language = raw.get("object_language")

    if object_datatype is not None and not isinstance(
        object_datatype,
        str,
    ):
        raise ValueError(
            "object_datatype must be a string or null"
        )

    if object_language is not None and not isinstance(
        object_language,
        str,
    ):
        raise ValueError(
            "object_language must be a string or null"
        )

    return (
        graph_iri,
        subject_iri,
        predicate_iri,
        object_type,
        object_value,
        object_datatype,
        object_language,
    )


def _load_embedded_graph(
    result: dict[str, Any],
) -> tuple[
    list[str],
    list[tuple[SourceUnit, ExtractionResult]],
]:
    graph_extractions = result.get("graph_extractions")

    if not isinstance(graph_extractions, dict):
        raise ValueError("graph_extractions must be an object")

    raw_items = graph_extractions.get("items")

    if not isinstance(raw_items, list):
        raise ValueError(
            "graph_extractions.items must be a list"
        )

    documents: list[str] = []
    accepted: list[tuple[SourceUnit, ExtractionResult]] = []

    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError(
                f"graph_extractions.items[{index}] "
                "must be an object"
            )

        raw_run = raw_item.get("run")

        if not isinstance(raw_run, dict):
            raise ValueError(
                f"graph_extractions.items[{index}].run "
                "must be an object"
            )

        raw_source = raw_run.get("source")
        raw_extraction = raw_run.get("extraction")

        if not isinstance(raw_source, dict):
            raise ValueError(
                f"graph_extractions.items[{index}].run.source "
                "must be an object"
            )

        if not isinstance(raw_extraction, dict):
            raise ValueError(
                f"graph_extractions.items[{index}].run.extraction "
                "must be an object"
            )

        source = SourceUnit(
            unit_id=_required_string(
                raw_source,
                "unit_id",
            ),
            title=_required_string(
                raw_source,
                "title",
            ),
            text=_required_string(
                raw_source,
                "text",
            ),
        )

        extraction = ExtractionResult.from_dict(
            cast(dict[str, Any], raw_extraction)
        )
        extraction.validate_against(source)

        documents.append(
            serialize_extraction_trig_star(
                source,
                extraction,
            )
        )
        accepted.append((source, extraction))

    return documents, accepted


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid JSON in {path}: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise ValueError(
            f"JSON artifact must contain an object: {path}"
        )

    return cast(dict[str, Any], payload)


def _required_string(
    payload: dict[str, Any],
    field: str,
) -> str:
    value = payload.get(field)

    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be a string"
        )

    return value