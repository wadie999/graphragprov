import pytest

from graphragprov.extraction import (
    GroundedStatement,
    GroundedValue,
    TextSegment,
    TextSpan,
)
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.provenance import (
    DecodedOccurrenceToken,
    EvidenceLocation,
    compact_unit_id,
    decode_occurrence_token,
    occurrence_token,
)

TITLE = "Albert Einstein"
TEXT = "He was born in Ulm."

UNIT_ID = source_unit_id(
    title=TITLE,
    text=TEXT,
)


def make_statement() -> GroundedStatement:
    return GroundedStatement(
        subject=GroundedValue(
            value="Albert Einstein",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=0,
                    end=2,
                    quote="He",
                ),
                TextSpan(
                    segment=TextSegment.TITLE,
                    start=0,
                    end=15,
                    quote="Albert Einstein",
                ),
            ),
        ),
        predicate=GroundedValue(
            value="bornIn",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=7,
                    end=14,
                    quote="born in",
                ),
            ),
        ),
        object=GroundedValue(
            value="Ulm",
            evidence=(
                TextSpan(
                    segment=TextSegment.TEXT,
                    start=15,
                    end=18,
                    quote="Ulm",
                ),
            ),
        ),
    )


def valid_token(
    *,
    subject: str = "tl:0-15+tx:0-2",
    predicate: str = "tx:7-14",
    object_: str = "tx:15-18",
    triple_hash: str = "1234abcd",
) -> str:
    return f"{compact_unit_id(UNIT_ID)}:s={subject}:p={predicate}:o={object_}:t={triple_hash}"


def test_decodes_generated_occurrence_token() -> None:
    token = occurrence_token(
        unit_id=UNIT_ID,
        statement=make_statement(),
    )

    decoded = decode_occurrence_token(token)

    assert decoded == DecodedOccurrenceToken(
        compact_unit_id=compact_unit_id(UNIT_ID),
        subject_evidence=(
            EvidenceLocation(
                segment=TextSegment.TITLE,
                start=0,
                end=15,
            ),
            EvidenceLocation(
                segment=TextSegment.TEXT,
                start=0,
                end=2,
            ),
        ),
        predicate_evidence=(
            EvidenceLocation(
                segment=TextSegment.TEXT,
                start=7,
                end=14,
            ),
        ),
        object_evidence=(
            EvidenceLocation(
                segment=TextSegment.TEXT,
                start=15,
                end=18,
            ),
        ),
        triple_hash=token.rsplit(":t=", maxsplit=1)[1],
    )


def test_decodes_multiple_evidence_locations() -> None:
    decoded = decode_occurrence_token(valid_token())

    assert decoded.subject_evidence == (
        EvidenceLocation(
            segment=TextSegment.TITLE,
            start=0,
            end=15,
        ),
        EvidenceLocation(
            segment=TextSegment.TEXT,
            start=0,
            end=2,
        ),
    )


def test_rejects_zero_length_evidence_location() -> None:
    with pytest.raises(
        ValueError,
        match="end must be greater than start",
    ):
        decode_occurrence_token(valid_token(subject="tl:0-0"))


def test_rejects_reversed_evidence_location() -> None:
    with pytest.raises(
        ValueError,
        match="end must be greater than start",
    ):
        decode_occurrence_token(valid_token(subject="tx:15-2"))


def test_rejects_noncanonical_evidence_order() -> None:
    with pytest.raises(
        ValueError,
        match="canonically ordered",
    ):
        decode_occurrence_token(
            valid_token(
                subject="tx:0-2+tl:0-15",
            )
        )


def test_rejects_duplicate_evidence_location() -> None:
    with pytest.raises(
        ValueError,
        match="unique",
    ):
        decode_occurrence_token(
            valid_token(
                subject="tl:0-15+tl:0-15",
            )
        )


def test_rejects_uppercase_triple_hash() -> None:
    with pytest.raises(
        ValueError,
        match="invalid grounded occurrence token",
    ):
        decode_occurrence_token(
            valid_token(
                triple_hash="1234ABCD",
            )
        )


@pytest.mark.parametrize(
    "compact_id",
    [
        "u_1234",
        "u_000000000000000",
        "u_00000000000000000",
        "u_000000000000000G",
        "0000000000000000",
    ],
)
def test_rejects_malformed_compact_unit_id(
    compact_id: str,
) -> None:
    token = f"{compact_id}:s=tl:0-15:p=tx:7-14:o=tx:15-18:t=1234abcd"

    with pytest.raises(
        ValueError,
        match="invalid grounded occurrence token",
    ):
        decode_occurrence_token(token)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-token",
        ("u_0000000000000000:s=:p=tx:7-14:o=tx:15-18:t=1234abcd"),
        ("u_0000000000000000:s=tl:0-15:p=tx:7-14:o=tx:15-18"),
        ("u_0000000000000000:s=tl:0-15:p=tx:7-14:o=tx:15-18:t=1234abc"),
        ("u_0000000000000000:s=tl:0-15:p=tx:7-14:o=tx:15-18:t=1234abcd:extra=value"),
    ],
)
def test_rejects_malformed_occurrence_token(
    token: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="invalid grounded occurrence token",
    ):
        decode_occurrence_token(token)
