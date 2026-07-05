from unittest.mock import Mock, patch

import pytest

from graphragprov.providers.deepseek import (
    DEEPSEEK_BASE_URL,
    deepseek_generator,
)


def fake_client_response(
    *,
    content: str | None,
    finish_reason: str = "stop",
) -> Mock:
    response = Mock()
    choice = Mock()

    choice.message.content = content
    choice.finish_reason = finish_reason
    response.choices = [choice]

    return response


def test_generates_json_response_without_thinking() -> None:
    raw_response = '{\n  "statements": []\n}\n'

    client = Mock()
    client.chat.completions.create.return_value = fake_client_response(content=raw_response)

    with patch(
        "graphragprov.providers.deepseek.OpenAI",
        return_value=client,
    ) as openai_constructor:
        generate_response = deepseek_generator(
            api_key="secret",
            model="deepseek-v4-flash",
            max_tokens=8_000,
        )

        result = generate_response("EXTRACTION PROMPT")

    assert result == raw_response

    openai_constructor.assert_called_once_with(
        api_key="secret",
        base_url=DEEPSEEK_BASE_URL,
    )

    client.chat.completions.create.assert_called_once_with(
        model="deepseek-v4-flash",
        messages=[
            {
                "role": "user",
                "content": "EXTRACTION PROMPT",
            }
        ],
        temperature=0.0,
        max_tokens=8_000,
        response_format={"type": "json_object"},
        extra_body={
            "thinking": {
                "type": "disabled",
            }
        },
    )


def test_rejects_empty_response() -> None:
    client = Mock()
    client.chat.completions.create.return_value = fake_client_response(content="")

    with patch(
        "graphragprov.providers.deepseek.OpenAI",
        return_value=client,
    ):
        generate_response = deepseek_generator(api_key="secret")

        with pytest.raises(ValueError, match="content is empty"):
            generate_response("PROMPT")


def test_rejects_truncated_response() -> None:
    client = Mock()
    client.chat.completions.create.return_value = fake_client_response(
        content='{"statements": [',
        finish_reason="length",
    )

    with patch(
        "graphragprov.providers.deepseek.OpenAI",
        return_value=client,
    ):
        generate_response = deepseek_generator(api_key="secret")

        with pytest.raises(ValueError, match="truncated"):
            generate_response("PROMPT")


def test_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        deepseek_generator(api_key=" ")


def test_rejects_empty_model_name() -> None:
    with pytest.raises(ValueError, match="model"):
        deepseek_generator(
            api_key="secret",
            model=" ",
        )


def test_rejects_invalid_token_limit() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        deepseek_generator(
            api_key="secret",
            max_tokens=0,
        )
