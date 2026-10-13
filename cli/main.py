"""Command line interface (cache-cli) for testing the caching service programmatically."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.payload import PayloadCreateRequest


class CliSettings(BaseSettings):
    """Sanitized CLI settings validated via Pydantic Settings."""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_CLI_",
        extra="ignore",
    )

    host: str = Field(
        default="http://localhost:8000",
        description="Target server host URL",
    )
    repeat: int = Field(
        default=1,
        ge=1,
        description="Number of request iterations",
    )
    input: str | None = Field(
        default=None,
        description="Input JSON file path or '-' for stdin",
    )
    json_data: str | None = Field(
        default=None,
        description="Input argument in JSON format string",
    )
    output: str = Field(
        default="-",
        description="Output destination file path or '-' for stdout",
    )

    @field_validator("host")
    @classmethod
    def clean_host_url(cls, v: str) -> str:
        """Strip trailing slash and ensure HTTP protocol."""
        cleaned = v.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            cleaned = f"http://{cleaned}"
        return cleaned

    @model_validator(mode="after")
    def validate_input_source(self) -> "CliSettings":
        """Ensure an input source (inline JSON, file, or stdin) is available."""
        if not self.json_data and not self.input:
            # Default to stdin if nothing is specified
            self.input = "-"
        return self


def parse_cli_args(args: list[str] | None = None) -> CliSettings:
    """Parse and sanitize command-line arguments using argparse and Pydantic Settings."""
    parser = argparse.ArgumentParser(
        prog="cache-cli",
        description="CLI tool to test the caching service programmatically.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        dest="host",
        default=None,
        help="Points to the server URL (e.g. http://localhost:8000)",
    )
    parser.add_argument(
        "-r",
        "--repeat",
        dest="repeat",
        type=int,
        default=None,
        help="Number of iterations to execute",
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input",
        default=None,
        help="Input file ('-' for stdin)",
    )
    parser.add_argument(
        "-j",
        "--json",
        dest="json_data",
        default=None,
        help="Input argument in JSON format",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        default=None,
        help="Output file ('-' for stdout)",
    )

    parsed = parser.parse_args(args)
    cli_kwargs = {k: v for k, v in vars(parsed).items() if v is not None}
    return CliSettings(**cli_kwargs)


def load_payload_data(settings: CliSettings) -> dict[str, Any]:
    """Read and validate the payload structure from JSON argument, file, or stdin."""
    raw_content: str

    if settings.json_data:
        raw_content = settings.json_data.strip()
    elif settings.input == "-":
        if sys.stdin.isatty():
            raise ValueError(
                "No input provided via stdin. Pipe data in or use --json / --input <file>."
            )
        raw_content = sys.stdin.read().strip()
    elif settings.input:
        input_path = Path(settings.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {settings.input}")
        raw_content = input_path.read_text(encoding="utf-8").strip()
    else:
        raise ValueError("No input source specified.")

    if not raw_content:
        raise ValueError("Input data is empty.")

    try:
        parsed_json = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON format: {exc}") from exc

    # Validate against PayloadCreateRequest schema to ensure list_1 and list_2 format and equal lengths
    validated_model = PayloadCreateRequest.model_validate(parsed_json)
    return validated_model.model_dump()


async def execute_requests(
    settings: CliSettings, payload_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Execute the configured number of POST and GET requests against the caching service."""
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=settings.host, timeout=30.0) as client:
        for iteration in range(1, settings.repeat + 1):
            # 1. POST /payload
            post_response = await client.post("/payload", json=payload_data)
            post_response.raise_for_status()
            post_data = post_response.json()
            payload_id = post_data["id"]

            # 2. GET /payload/{id}
            get_response = await client.get(f"/payload/{payload_id}")
            get_response.raise_for_status()
            get_data = get_response.json()

            results.append(
                {
                    "iteration": iteration,
                    "payload_id": payload_id,
                    "status": "success",
                    "output": get_data.get("output"),
                    "created_at": get_data.get("created_at"),
                }
            )

    return results


def write_output(settings: CliSettings, results: list[dict[str, Any]]) -> None:
    """Write formatted execution results to stdout or destination file."""
    output_obj: Any = results[0] if len(results) == 1 else results
    formatted_output = json.dumps(output_obj, indent=2)

    if settings.output == "-":
        print(formatted_output)
    else:
        output_path = Path(settings.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted_output + "\n", encoding="utf-8")


async def async_main(args: list[str] | None = None) -> int:
    """Async coordinator for CLI execution."""
    try:
        settings = parse_cli_args(args)
        payload_data = load_payload_data(settings)
        results = await execute_requests(settings, payload_data)
        write_output(settings, results)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main(args: list[str] | None = None) -> None:
    """CLI synchronous entry point invoked by script runner."""
    exit_code = asyncio.run(async_main(args))
    if exit_code != 0 and args is not None:
        raise SystemExit(exit_code)
    elif exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
