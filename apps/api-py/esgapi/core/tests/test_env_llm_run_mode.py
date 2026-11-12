"""실행기의 실제 공급사 켜기(LV1) — LLM_RUN_MODE·LLM_RUN_MAX_USD 를 읽는 규칙과 live 의 기동 조건. 순수 층.

  빈 값·없음 = mock · 모르는 값(오타 포함) = 기동 실패(메시지에 허용 값, 받은 값은 0 — 테스트 73 조건 (가))
  live 의 기동 조건 셋: LLM_LOG_SINK=db · 키 하나 이상 · LLM_RUN_MAX_USD 명시(LV1 Q3·critic M1)
  LLM_RUN_MAX_USD 는 0보다 큰 유한한 수(빈 값·0·음수·nan·inf·글자 → 기동 실패 — 73 조건 (다))
  기동 줄(run_mode_notice)은 live 에서만, 공급사 이름만(키의 값·길이·앞머리 0)
  compose.yaml(api-py — worker 는 앵커로 같은 환경)·.env.example 이 두 이름을 빈 기본값으로 싣는다
키는 전부 지어낸 글자다(LV1SENTINEL).
"""

from pathlib import Path

import pytest

from esgapi.config.env import ConfigError, LlmSettings, load_config, run_mode_notice

ENV = {
    "DATABASE_URL_PY": "postgres://esg_app:pw@postgres:5432/esg_py",
    "EDK_JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----\\n",
    "EDK_JWT_AUDIENCE": "esg-api",
    "EDK_JWT_ISSUER": "https://edk.example",
    "SESSION_SECRET": "x" * 32,
    "SESSION_TTL_SECONDS": "3600",
}
SK = "sk-proj-LV1SENTINEL" + "q" * 24  # 가림(redact_keys)의 꼴 안
PLAIN = "LV1PLAINSENTINEL"  # 가림의 꼴 밖 — 가림에 기대지 않는 자리
LIVE = {**ENV, "LLM_RUN_MODE": "live", "LLM_LOG_SINK": "db", "LLM_OPENAI_API_KEY": SK, "LLM_RUN_MAX_USD": "0.30"}


def problem(env: dict[str, str]) -> str:
    with pytest.raises(ConfigError) as caught:
        load_config(env)
    return str(caught.value)


@pytest.mark.parametrize("value", [None, "", "   ", "mock", " mock "])
def test_absent_blank_and_mock_are_mock(value: str | None) -> None:
    env = dict(ENV) if value is None else {**ENV, "LLM_RUN_MODE": value}
    assert load_config(env).llm.run_mode == "mock"


def test_the_default_of_the_settings_is_mock() -> None:
    """설정 객체의 기본도 mock 이다(환경을 읽지 않고 지은 LlmSettings — 시험·관리 명령)."""
    assert (LlmSettings().run_mode, LlmSettings().run_max_usd) == ("mock", 5.0)


def test_mock_with_keys_starts_and_keeps_the_keys_for_the_other_paths() -> None:
    """mock 은 기동 조건이 없다(키가 있어도, 싱크가 memory 여도). 키는 설정에 남는다 — 실행기가 비운다(runs/context)."""
    llm = load_config({**ENV, "LLM_OPENAI_API_KEY": SK}).llm
    assert (llm.run_mode, llm.log_sink, llm.openai_api_key is not None) == ("mock", "memory", True)


def test_live_with_the_three_conditions_starts() -> None:
    llm = load_config(LIVE).llm
    assert (llm.run_mode, llm.log_sink, llm.run_max_usd) == ("live", "db", 0.30)


@pytest.mark.parametrize("value", ["LIVE", "openai", "1", "real", "true", PLAIN, SK])
def test_an_unknown_mode_stops_startup_and_names_the_allowed_values_only(value: str) -> None:
    """모르는 값은 mock 으로 삼키지 않고 기동 실패다. 메시지에 허용 값만 있고 받은 값은 없다(키일 수 있다)."""
    text = problem({**LIVE, "LLM_RUN_MODE": value})
    assert "LLM_RUN_MODE 는 mock, live 가운데 하나여야 한다" in text
    if len(value) > 4:  # 짧은 값(1·true)은 다른 낱말에 섞여 있을 수 있어 「없음」을 재지 않는다
        assert value not in text


@pytest.mark.parametrize("sink", [None, "memory", "jsonl"])
def test_live_needs_the_db_sink(sink: str | None) -> None:
    env = {k: v for k, v in LIVE.items() if k != "LLM_LOG_SINK"}
    if sink is not None:
        env |= {"LLM_LOG_SINK": sink, "LLM_JSONL_PATH": "/var/log/esg/llm.jsonl"}
    assert "LLM_RUN_MODE 가 live 면 LLM_LOG_SINK 가 db 여야 한다" in problem(env)


def test_live_needs_a_key() -> None:
    env = {k: v for k, v in LIVE.items() if k != "LLM_OPENAI_API_KEY"} | {"LLM_GEMINI_API_KEY": "  "}
    assert "LLM_RUN_MODE 가 live 면 공급사 키" in problem(env)


@pytest.mark.parametrize("key", ["LLM_OPENAI_API_KEY", "LLM_ANTHROPIC_API_KEY", "LLM_GEMINI_API_KEY"])
def test_any_one_key_is_enough_for_live(key: str) -> None:
    env = {k: v for k, v in LIVE.items() if k != "LLM_OPENAI_API_KEY"} | {key: PLAIN}
    assert load_config(env).llm.run_mode == "live"


@pytest.mark.parametrize("value", [None, "", "  "])
def test_live_needs_an_explicit_run_max_usd(value: str | None) -> None:
    """live 면 상한을 사람이 정해야 한다 — 기본값 5.0 은 mock 에서만(critic M1)."""
    env = {k: v for k, v in LIVE.items() if k != "LLM_RUN_MAX_USD"}
    if value is not None:
        env["LLM_RUN_MAX_USD"] = value
    assert "LLM_RUN_MODE 가 live 면 LLM_RUN_MAX_USD 가 있어야 한다" in problem(env)


@pytest.mark.parametrize("mode", ["live", "mock"])
@pytest.mark.parametrize("value", ["0", "-1", "-0.01", "nan", "inf", "-inf", "free", PLAIN])
def test_a_bad_run_max_usd_stops_startup(mode: str, value: str) -> None:
    """닫힌 쪽(73 조건 (다)): 상한이 수가 아니거나 0 이하·무한이면 어느 모드에서도 뜨지 않는다. 받은 값은 싣지 않음."""
    text = problem({**LIVE, "LLM_RUN_MODE": mode, "LLM_RUN_MAX_USD": value})
    assert "LLM_RUN_MAX_USD 는 0보다 큰 수여야 한다" in text
    assert PLAIN not in text


def test_problems_are_collected_at_once() -> None:
    """live 의 조건 셋이 모두 빠지면 한 번에 셋 다 알린다(빠진 것을 전부 모아 — env.py 머리말)."""
    text = problem({**ENV, "LLM_RUN_MODE": "live"})
    assert all(part in text for part in ("LLM_LOG_SINK 가 db 여야", "공급사 키", "LLM_RUN_MAX_USD 가 있어야"))


def test_the_startup_notice_names_the_providers_only() -> None:
    env = {**LIVE, "LLM_GEMINI_API_KEY": PLAIN}
    notice = run_mode_notice(load_config(env).llm)
    assert notice == "llm_run_mode mode=live providers=openai,gemini max_usd=0.3 sink=db"
    assert run_mode_notice(load_config({**ENV, "LLM_OPENAI_API_KEY": SK}).llm) is None  # mock 은 줄 없음


def test_load_config_prints_the_notice_in_live_only(capsys: pytest.CaptureFixture[str]) -> None:
    load_config({**ENV, "LLM_OPENAI_API_KEY": SK})
    assert "llm_run_mode" not in capsys.readouterr().err
    load_config(LIVE)
    err = capsys.readouterr().err
    assert "llm_run_mode mode=live providers=openai" in err
    assert "LV1SENTINEL" not in err


RUN_KEYS = ["LLM_RUN_MODE", "LLM_RUN_MAX_USD"]


def test_env_example_and_compose_carry_the_run_keys_empty() -> None:
    """compose.yaml 의 api-py 환경(worker-py 는 앵커로 같은 것)과 .env.example 이 두 이름을 빈 기본값으로 싣는다."""
    root = Path(__file__).resolve().parents[5]
    example = (root / ".env.example").read_text(encoding="utf-8")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    for key in RUN_KEYS:
        assert f"\n{key}=\n" in example, key
        assert f"{key}: ${{{key}:-}}" in compose, key
    assert "<<: *api-py-env" in compose  # worker 가 api-py 의 환경을 그대로 받는다
