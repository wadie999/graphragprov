from graphragprov.hashing import source_unit_id


def test_source_unit_id_is_deterministic() -> None:
    text = "Alice works at Airbus."

    assert source_unit_id(text) == source_unit_id(text)
    assert source_unit_id(text).startswith("u_")
    assert len(source_unit_id(text)) == 66


def test_source_unit_id_preserves_exact_text() -> None:
    assert source_unit_id("Alice") != source_unit_id(" Alice")
    assert source_unit_id("Alice") != source_unit_id("alice")
    assert source_unit_id("Alice") != source_unit_id("Alice\n")
