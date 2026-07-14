import json

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.hashing import source_unit_id
from graphragprov.provenance import (
    SourceRegistry,
    decode_provenance_polynomial,
)
from graphragprov.rdf.provenance import compact_unit_id

TITLE = "Albert Einstein"
TEXT = "He was born in Ulm."

SOURCE = SourceUnit(
    unit_id=source_unit_id(
        title=TITLE,
        text=TEXT,
    ),
    title=TITLE,
    text=TEXT,
)

COMPACT_ID = compact_unit_id(SOURCE.unit_id)

TOKEN = f"{COMPACT_ID}:s=tl:0-15+tx:0-2:p=tx:7-14:o=tx:15-18:t=1234abcd"


def test_decodes_token_into_exact_source_quotes() -> None:
    decoded = decode_provenance_polynomial(
        f"⊕((⊗{TOKEN},))",
        registry=SourceRegistry((SOURCE,)),
    )

    occurrence = decoded.derivations[0].occurrences[0]

    assert occurrence.token == TOKEN
    assert occurrence.compact_unit_id == COMPACT_ID
    assert occurrence.source == SOURCE
    assert occurrence.triple_hash == "1234abcd"

    assert [span.quote for span in occurrence.subject_evidence] == [
        "Albert Einstein",
        "He",
    ]

    assert [span.quote for span in occurrence.predicate_evidence] == [
        "born in",
    ]

    assert [span.quote for span in occurrence.object_evidence] == [
        "Ulm",
    ]


def test_preserves_duplicate_occurrences() -> None:
    decoded = decode_provenance_polynomial(
        f"⊕((⊗{TOKEN},{TOKEN},))",
        registry=SourceRegistry((SOURCE,)),
    )

    occurrences = decoded.derivations[0].occurrences

    assert len(occurrences) == 2
    assert occurrences[0] == occurrences[1]


def test_preserves_alternative_derivations() -> None:
    second_token = f"{COMPACT_ID}:s=tl:0-15:p=tx:7-14:o=tx:15-18:t=ffffffff"

    decoded = decode_provenance_polynomial(
        (f"⊕((⊗{TOKEN},) (⊗{second_token},))"),
        registry=SourceRegistry((SOURCE,)),
    )

    assert len(decoded.derivations) == 2
    assert all(len(derivation.occurrences) == 1 for derivation in decoded.derivations)


def test_rejects_unknown_source_unit() -> None:
    unknown_token = "u_ffffffffffffffff:s=tl:0-15:p=tx:7-14:o=tx:15-18:t=1234abcd"

    with pytest.raises(
        ValueError,
        match="unknown source unit",
    ):
        decode_provenance_polynomial(
            f"⊕((⊗{unknown_token},))",
            registry=SourceRegistry(),
        )


def test_rejects_out_of_bounds_source_span() -> None:
    invalid_token = f"{COMPACT_ID}:s=tl:0-15:p=tx:7-14:o=tx:15-999:t=1234abcd"

    with pytest.raises(
        ValueError,
        match="object evidence.*exceeds",
    ):
        decode_provenance_polynomial(
            f"⊕((⊗{invalid_token},))",
            registry=SourceRegistry((SOURCE,)),
        )


def test_decoded_output_is_json_serializable() -> None:
    decoded = decode_provenance_polynomial(
        f"⊕((⊗{TOKEN},))",
        registry=SourceRegistry((SOURCE,)),
    )

    serialized = json.dumps(
        decoded.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
    )
    restored = json.loads(serialized)

    occurrence = restored["derivations"][0]["occurrences"][0]

    assert occurrence["source"] == {
        "unit_id": SOURCE.unit_id,
        "title": TITLE,
        "text": TEXT,
    }
    assert occurrence["subject_evidence"] == [
        {
            "segment": "title",
            "start": 0,
            "end": 15,
            "quote": "Albert Einstein",
        },
        {
            "segment": "text",
            "start": 0,
            "end": 2,
            "quote": "He",
        },
    ]


BROWARD_TITLE = "Broward Correctional Institution"

BROWARD_TEXT = (
    "The Broward Correctional Institution (BCI) was a correctional "
    "facility located in the former Country Estates CDP and in "
    "Southwest Ranches, Florida, operated by the Florida Department "
    "of Corrections. The Region IV Correctional Facility Office is "
    "located on the grounds of Broward Correctional Institution in "
    "the former Country Estates CDP. The prison was in proximity to "
    "Pembroke Pines. It was located along Sheridan Street, near "
    "U.S. Route 27."
)

BROWARD_SOURCE = SourceUnit(
    unit_id=source_unit_id(
        title=BROWARD_TITLE,
        text=BROWARD_TEXT,
    ),
    title=BROWARD_TITLE,
    text=BROWARD_TEXT,
)

BROWARD_OPERATOR = "u_38162077dce1d7d1:s=tx:4-36:p=tx:148-159:o=tx:164-197:t=4b79dc23"

BROWARD_OFFICE = "u_38162077dce1d7d1:s=tx:203-241:p=tx:242-270:o=tx:271-303:t=5dae8a89"

BROWARD_SOUTHWEST = "u_38162077dce1d7d1:s=tx:4-36:p=tx:113-119:o=tx:120-146:t=2605283e"

BROWARD_COUNTRY_ESTATES = "u_38162077dce1d7d1:s=tx:4-36:p=tx:71-81:o=tx:86-112:t=4d7e942b"


def test_decodes_real_npcs_graphdb_polynomial() -> None:
    assert BROWARD_SOURCE.unit_id == (
        "u_38162077dce1d7d133ddfe5380cadaa2f53ccc39014260184b42e13ad14cea1c"
    )

    polynomial = (
        "⊕("
        f"(⊗{BROWARD_OPERATOR},"
        f"{BROWARD_OFFICE},"
        f"{BROWARD_SOUTHWEST},) "
        f"(⊗{BROWARD_OPERATOR},"
        f"{BROWARD_OFFICE},"
        f"{BROWARD_COUNTRY_ESTATES},)"
        ")"
    )

    decoded = decode_provenance_polynomial(
        polynomial,
        registry=SourceRegistry((BROWARD_SOURCE,)),
    )

    assert len(decoded.derivations) == 2
    assert {len(derivation.occurrences) for derivation in decoded.derivations} == {
        3,
    }

    occurrences_by_hash = {
        occurrence.triple_hash: occurrence
        for derivation in decoded.derivations
        for occurrence in derivation.occurrences
    }

    assert occurrences_by_hash["4b79dc23"].predicate_evidence[0].quote == "operated by"
    assert (
        occurrences_by_hash["4b79dc23"].object_evidence[0].quote
        == "Florida Department of Corrections"
    )

    assert (
        occurrences_by_hash["5dae8a89"].subject_evidence[0].quote
        == "Region IV Correctional Facility Office"
    )
    assert (
        occurrences_by_hash["5dae8a89"].predicate_evidence[0].quote
        == "is located on the grounds of"
    )

    assert occurrences_by_hash["2605283e"].object_evidence[0].quote == "Southwest Ranches, Florida"

    assert occurrences_by_hash["4d7e942b"].object_evidence[0].quote == "former Country Estates CDP"
