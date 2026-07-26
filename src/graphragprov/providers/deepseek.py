"""DeepSeek adapter for one grounded extraction call."""

from openai import OpenAI

from graphragprov.extraction.run import GenerateResponse

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


def deepseek_generator(
    *, api_key: str, model: str = DEFAULT_DEEPSEEK_MODEL, max_tokens: int = 16_384
) -> GenerateResponse:
    """Create a deterministic DeepSeek JSON-response generator."""

    if not api_key.strip():
        raise ValueError("DeepSeek API key must not be empty")

    if not model.strip():
        raise ValueError("DeepSeek model must not be empty")

    if max_tokens < 1:
        raise ValueError("max_tokens must be greater than zero")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    def generate_response(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )

        if not response.choices:
            raise ValueError("DeepSeek response contains no choices")

        choice = response.choices[0]

        if choice.finish_reason == "length":
            raise ValueError("DeepSeek response was truncated by the token limit")

        content = choice.message.content

        if content is None or not content.strip():
            raise ValueError("DeepSeek response content is empty")

        # Preserve the exact provider response. Parsing happens elsewhere.
        return content

    return generate_response
