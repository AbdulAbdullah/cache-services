"""Unit and integration tests for the cache-cli utility."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from cli.main import (
    CliSettings,
    async_main,
    execute_requests,
    load_payload_data,
    main,
    parse_cli_args,
    write_output,
)


def test_parse_cli_args_defaults():
    """Verify default CLI arguments."""
    settings = parse_cli_args([])
    assert settings.host == "http://localhost:8000"
    assert settings.repeat == 1
    assert settings.input == "-"
    assert settings.json_data is None
    assert settings.output == "-"


def test_parse_cli_args_custom():
    """Verify custom CLI flag overrides."""
    args = [
        "--host",
        "http://api.example.com:8080/",
        "-r",
        "5",
        "-j",
        '{"list_1": ["a"], "list_2": ["b"]}',
        "-o",
        "out.json",
    ]
    settings = parse_cli_args(args)
    assert settings.host == "http://api.example.com:8080"
    assert settings.repeat == 5
    assert settings.json_data == '{"list_1": ["a"], "list_2": ["b"]}'
    assert settings.output == "out.json"


def test_load_payload_data_from_json_string():
    """Verify loading and validating payload from inline JSON."""
    settings = parse_cli_args(["-j", '{"list_1": ["hello"], "list_2": ["world"]}'])
    payload = load_payload_data(settings)
    assert payload["list_1"] == ["hello"]
    assert payload["list_2"] == ["world"]


def test_load_payload_data_from_file(tmp_path: Path):
    """Verify loading and validating payload from an input file."""
    input_file = tmp_path / "payload.json"
    input_file.write_text(
        json.dumps({"list_1": ["first", "third"], "list_2": ["second", "fourth"]}),
        encoding="utf-8",
    )
    settings = parse_cli_args(["-i", str(input_file)])
    payload = load_payload_data(settings)
    assert payload["list_1"] == ["first", "third"]
    assert payload["list_2"] == ["second", "fourth"]


def test_load_payload_data_from_stdin(monkeypatch: pytest.MonkeyPatch):
    """Verify loading payload when piped through stdin."""
    import io

    settings = parse_cli_args(["-i", "-"])
    sample_json = json.dumps({"list_1": ["item1"], "list_2": ["item2"]})

    monkeypatch.setattr("sys.stdin", io.StringIO(sample_json))
    payload = load_payload_data(settings)
    assert payload["list_1"] == ["item1"]
    assert payload["list_2"] == ["item2"]


def test_load_payload_data_invalid_json():
    """Verify exception raised when JSON is malformed."""
    settings = parse_cli_args(["-j", "{not valid json"])
    with pytest.raises(ValueError, match="Invalid JSON format"):
        load_payload_data(settings)


def test_load_payload_data_unequal_lengths():
    """Verify exception raised when list_1 and list_2 lengths differ."""
    settings = parse_cli_args(
        ["-j", '{"list_1": ["a", "b"], "list_2": ["c"]}']
    )
    with pytest.raises(ValueError, match="must have equal length"):
        load_payload_data(settings)


def test_load_payload_data_missing_file():
    """Verify exception raised when input file does not exist."""
    settings = parse_cli_args(["-i", "nonexistent_file_path.json"])
    with pytest.raises(FileNotFoundError):
        load_payload_data(settings)


@pytest.mark.asyncio
async def test_execute_requests_flow():
    """Verify execute_requests performs both POST and GET per iteration."""
    settings = parse_cli_args(["--repeat", "2", "-j", '{"list_1": ["a"], "list_2": ["b"]}'])
    payload_data = {"list_1": ["a"], "list_2": ["b"]}

    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"id": 42}

    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {
        "id": 42,
        "list_1": ["a"],
        "list_2": ["b"],
        "output": "A B",
        "created_at": "2026-10-13T20:00:00",
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = post_resp
    mock_client.get.return_value = get_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        results = await execute_requests(settings, payload_data)

    assert len(results) == 2
    assert results[0]["payload_id"] == 42
    assert results[0]["output"] == "A B"
    assert results[1]["iteration"] == 2
    assert mock_client.post.call_count == 2
    assert mock_client.get.call_count == 2


def test_write_output_stdout(capsys: pytest.CaptureFixture):
    """Verify write_output prints JSON to stdout."""
    settings = parse_cli_args(["-o", "-"])
    sample_results = [{"iteration": 1, "payload_id": 1, "output": "TEST"}]
    write_output(settings, sample_results)
    captured = capsys.readouterr()
    assert '"payload_id": 1' in captured.out
    assert '"output": "TEST"' in captured.out


def test_write_output_file(tmp_path: Path):
    """Verify write_output saves formatted JSON to target file."""
    out_file = tmp_path / "subdir" / "output.json"
    settings = parse_cli_args(["-o", str(out_file)])
    sample_results = [{"iteration": 1, "payload_id": 1, "output": "FILE OUTPUT"}]
    write_output(settings, sample_results)
    assert out_file.exists()
    content = json.loads(out_file.read_text(encoding="utf-8"))
    assert content["payload_id"] == 1
    assert content["output"] == "FILE OUTPUT"


@pytest.mark.asyncio
async def test_async_main_success(capsys: pytest.CaptureFixture):
    """Verify async_main successfully executes with inline json."""
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = {"id": 10}

    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.json.return_value = {
        "id": 10,
        "output": "HELLO WORLD",
        "created_at": "2026-10-13T20:00:00",
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = post_resp
    mock_client.get.return_value = get_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        exit_code = await async_main(["-j", '{"list_1": ["hello"], "list_2": ["world"]}'])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"payload_id": 10' in captured.out
    assert '"output": "HELLO WORLD"' in captured.out


@pytest.mark.asyncio
async def test_async_main_error_handling(capsys: pytest.CaptureFixture):
    """Verify async_main returns code 1 and writes error to stderr on failure."""
    exit_code = await async_main(["-j", "{invalid json}"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error:" in captured.err


def test_main_cli_execution():
    """Verify main entry point runs cleanly."""
    with patch("cli.main.async_main", return_value=0) as mock_async_main:
        main(["-j", '{"list_1": ["a"], "list_2": ["b"]}'])
        mock_async_main.assert_called_once()
