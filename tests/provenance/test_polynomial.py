import json

import pytest

from graphragprov.provenance import ProvenancePolynomial, parse_provenance_polynomial

TOKEN_A = "u_0000000000000001:s=tl:0-1:p=tx:1-2:o=tx:2-3:t=00000001"

TOKEN_B = "u_0000000000000002:s=tl:0-1:p=tx:1-2:o=tx:2-3:t=00000002"

TOKEN_C = "u_0000000000000003:s=tl:0-1:p=tx:1-2:o=tx:2-3:t=00000003"


def test_parses_one_product_with_one_token() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_A},))")

    assert polynomial == ProvenancePolynomial(derivations=((TOKEN_A,),))


def test_parses_observed_npcs_sum_of_products_shape() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_A},{TOKEN_B},) (⊗{TOKEN_A},{TOKEN_C},))")

    assert polynomial.derivations == ((TOKEN_A, TOKEN_B), (TOKEN_A, TOKEN_C))


def test_accepts_one_or_more_whitespace_between_products() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_A},) \n\t (⊗{TOKEN_B},))")

    assert polynomial.derivations == ((TOKEN_A,), (TOKEN_B,))


def test_canonicalizes_token_order_within_product() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_C},{TOKEN_A},{TOKEN_B},))")

    assert polynomial.derivations == ((TOKEN_A, TOKEN_B, TOKEN_C),)


def test_canonicalizes_product_order() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_C},) (⊗{TOKEN_A},{TOKEN_B},))")

    assert polynomial.derivations == ((TOKEN_A, TOKEN_B), (TOKEN_C,))


def test_preserves_duplicate_tokens() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_A},{TOKEN_A},))")

    assert polynomial.derivations == ((TOKEN_A, TOKEN_A),)


def test_preserves_duplicate_derivations() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_A},) (⊗{TOKEN_A},))")

    assert polynomial.derivations == ((TOKEN_A,), (TOKEN_A,))


def test_result_is_json_serializable() -> None:
    polynomial = parse_provenance_polynomial(f"⊕((⊗{TOKEN_A},{TOKEN_B},))")

    serialized = json.dumps(polynomial.to_dict(), ensure_ascii=False, sort_keys=True)

    assert json.loads(serialized) == {"derivations": [{"tokens": [TOKEN_A, TOKEN_B]}]}


def test_constructor_rejects_noncanonical_token_order() -> None:
    with pytest.raises(ValueError, match="tokens.*canonically ordered"):
        ProvenancePolynomial(derivations=((TOKEN_B, TOKEN_A),))


def test_constructor_rejects_noncanonical_product_order() -> None:
    with pytest.raises(ValueError, match="derivations.*canonically ordered"):
        ProvenancePolynomial(derivations=((TOKEN_B,), (TOKEN_A,)))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "must not be empty"),
        ("⊕(", "missing its body"),
        ("⊕()", "at least one product"),
        (f" (⊕((⊗{TOKEN_A},)))", "expected '⊕\\('"),
        (f"⊕((⊗{TOKEN_A},)) ", "unexpected trailing content"),
        (f"⊕((⊗{TOKEN_A}))", "missing a token separator"),
        ("⊕((⊗,))", "empty token"),
        (f"⊕((⊗{TOKEN_A},)(⊗{TOKEN_B},))", "expected whitespace"),
        (f"⊕((⊗{TOKEN_A},) )", "expected provenance product"),
        (f"⊕((⊗{TOKEN_A},)", "missing its closing"),
        (f"⊕((⊗{TOKEN_A},))trailing", "unexpected trailing content"),
        (("⊕((⊗u_invalid:s=tl:0-1:p=tx:1-2:o=tx:2-3:t=00000001,))"), "invalid provenance token"),
    ],
)
def test_rejects_malformed_polynomial(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_provenance_polynomial(value)
