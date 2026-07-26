"""Run one real grounded extraction on one MuSiQue paragraph."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from graphragprov.extraction.musique import load_musique_source_unit
from graphragprov.extraction.parser import parse_extraction_response
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.providers.deepseek import DEFAULT_DEEPSEEK_MODEL, deepseek_generator


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract one MuSiQue paragraph with DeepSeek.")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--hops", required=True, type=int, choices=(2, 3, 4))
    parser.add_argument("--paragraph", required=True, type=int)
    parser.add_argument("--model", default=DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--max-tokens", type=int, default=16_384)

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")

    source = load_musique_source_unit(
        case_id=arguments.case_id, paragraph_index=arguments.paragraph, expected_hops=arguments.hops
    )

    prompt = build_extraction_prompt(source)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_directory = Path("runs") / f"single_musique_{timestamp}"
    run_directory.mkdir(parents=True)

    source_path = run_directory / "source.json"
    prompt_path = run_directory / "prompt.txt"
    response_path = run_directory / "response.txt"
    extraction_path = run_directory / "extraction.json"
    error_path = run_directory / "error.txt"

    source_path.write_text(
        json.dumps(
            {"unit_id": source.unit_id, "title": source.title, "text": source.text},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    prompt_path.write_text(prompt, encoding="utf-8")

    generate_response = deepseek_generator(
        api_key=api_key, model=arguments.model, max_tokens=arguments.max_tokens
    )

    try:
        response = generate_response(prompt)
    except Exception as error:
        error_path.write_text(f"provider: {type(error).__name__}: {error}\n", encoding="utf-8")
        raise

    response_path.write_text(response, encoding="utf-8")

    try:
        extraction = parse_extraction_response(source, response)
    except Exception as error:
        error_path.write_text(f"parsing: {type(error).__name__}: {error}\n", encoding="utf-8")
        raise

    extraction_path.write_text(extraction.to_json(), encoding="utf-8")

    print(f"Run:        {run_directory}")
    print(f"Statements: {len(extraction.statements)}")
    print(f"Source:     {source_path}")
    print(f"Prompt:     {prompt_path}")
    print(f"Response:   {response_path}")
    print(f"Extraction: {extraction_path}")


if __name__ == "__main__":
    main()
