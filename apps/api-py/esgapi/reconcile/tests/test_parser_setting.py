"""설정 키 PARSER_URL · PARSER_TIMEOUT_MS (`config/env.py` 에 더한 것). 순수 층. `config/tests` 는 건드리지 않았다."""

import pytest

from esgapi.config.env import Config, ConfigError, DbTarget, load_config, load_parser_settings

BASE = {
    "DATABASE_URL_PY": "postgres://esg_app:pw@postgres:5432/esg_py",
    "EDK_JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\\nAAAA\\n-----END PUBLIC KEY-----\\n",
    "EDK_JWT_AUDIENCE": "esg-api",
    "EDK_JWT_ISSUER": "https://edk.local.invalid",
    "SESSION_SECRET": "local-only-session-secret-0123456789abcdef",
    "SESSION_TTL_SECONDS": "3600",
}


def read(env: dict[str, str]) -> tuple[str | None, int, list[str]]:
    problems: list[str] = []
    url, timeout_ms = load_parser_settings(env, problems)
    return url, timeout_ms, problems


def test_absent_or_blank_is_none_and_the_server_still_starts() -> None:
    assert read({}) == (None, 210_000, [])
    assert read({"PARSER_URL": ""}) == (None, 210_000, [])
    assert read({"PARSER_URL": "   ", "PARSER_TIMEOUT_MS": " "}) == (None, 210_000, [])
    config = load_config(BASE)  # PARSER_URL 없이도 설정이 선다
    assert (config.parser_url, config.parser_timeout_ms) == (None, 210_000)


def test_a_valid_address_and_timeout_come_through() -> None:
    assert read({"PARSER_URL": "http://parser:8000", "PARSER_TIMEOUT_MS": "45000"}) == (
        "http://parser:8000",
        45_000,
        [],
    )
    assert read({"PARSER_URL": " https://parser.example.invalid/base "}) == (
        "https://parser.example.invalid/base",
        210_000,
        [],
    )
    config = load_config({**BASE, "PARSER_URL": "http://parser:8000", "PARSER_TIMEOUT_MS": "1500"})
    assert (config.parser_url, config.parser_timeout_ms) == ("http://parser:8000", 1500)


@pytest.mark.parametrize(
    "url", ["parser:8000", "ftp://parser:8000", "file:///etc/passwd", "http://", "//parser:8000", "postgres://h/db"]
)
def test_a_wrong_address_is_a_listed_problem_not_accepted(url: str) -> None:
    """틀린 꼴을 그대로 받지 않는다. (심은 파손 17)"""
    found, _, problems = read({"PARSER_URL": url})
    assert found is None
    assert problems == ["PARSER_URL 의 꼴이 틀렸다. http://호스트:포트 나 https://호스트 여야 한다"]
    with pytest.raises(ConfigError, match="PARSER_URL 의 꼴이 틀렸다"):
        load_config({**BASE, "PARSER_URL": url})


@pytest.mark.parametrize("text", ["0", "-5", "1.5", "abc", "30s", "٣٠", "１２"])
def test_a_wrong_timeout_is_a_listed_problem(text: str) -> None:
    assert read({"PARSER_TIMEOUT_MS": text}) == (None, 210_000, ["PARSER_TIMEOUT_MS 는 0보다 큰 정수여야 한다"])


def test_existing_callers_of_config_are_not_broken_by_the_new_fields() -> None:
    """칸에 기본값이 있어, 두 칸을 모르는 호출(기존 테스트의 Config(...))이 그대로 선다."""
    config = Config(
        database=DbTarget("h", 5432, "n", "u", "p"),
        edk_public_key_pem="",
        edk_audience="",
        edk_issuer="",
        session_secret="",
        session_ttl_seconds=1,
    )
    assert (config.parser_url, config.parser_timeout_ms) == (None, 210_000)
