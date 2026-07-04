from graphragprov.hashing import source_unit_id


def test_source_unit_id_is_deterministic() -> None:
    unit_id = source_unit_id(
        title="Alice",
        text="Alice works at Airbus.",
    )

    assert unit_id == source_unit_id(
        title="Alice",
        text="Alice works at Airbus.",
    )
    assert unit_id.startswith("u_")
    assert len(unit_id) == 66


def test_title_is_part_of_source_unit_identity() -> None:
    text = "He was born in Ulm."

    assert source_unit_id(
        title="Albert Einstein",
        text=text,
    ) != source_unit_id(
        title="Someone else",
        text=text,
    )


def test_text_is_part_of_source_unit_identity() -> None:
    title = "Albert Einstein"

    assert source_unit_id(
        title=title,
        text="He was born in Ulm.",
    ) != source_unit_id(
        title=title,
        text="He was born in Berlin.",
    )


def test_source_unit_identity_preserves_exact_content() -> None:
    original = source_unit_id(
        title="Alice",
        text="Alice works at Airbus.",
    )

    assert original != source_unit_id(
        title=" Alice",
        text="Alice works at Airbus.",
    )
    assert original != source_unit_id(
        title="Alice",
        text=" Alice works at Airbus.",
    )
    assert original != source_unit_id(
        title="Alice",
        text="Alice works at Airbus.\n",
    )
