"""설정 읽기. 환경 변수에서만, 빠진 것은 뜨기 전에 전부 알린다. 순수 층."""

from pathlib import Path

import pytest

from esgapi.config.env import (
    BROKER_KEYS,
    SDK_ENV_NAMES,
    SDK_ENV_PREFIXES,
    STORAGE_KEYS,
    BrokerSettings,
    Config,
    ConfigError,
    DbTarget,
    JobSettings,
    LlmSettings,
    StorageSettings,
    load_config,
    parse_database_url,
    session_secret_warning,
)

ENV = {
    "DATABASE_URL_PY": "postgres://esg_app:pw@postgres:5432/esg_py",
    "EDK_JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----\\n",
    "EDK_JWT_AUDIENCE": "esg-api",
    "EDK_JWT_ISSUER": "https://edk.example",
    "SESSION_SECRET": "x" * 32,
    "SESSION_TTL_SECONDS": "3600",
}


def test_reads_everything_from_env() -> None:
    config = load_config(ENV)
    assert config.database == DbTarget(host="postgres", port=5432, name="esg_py", user="esg_app", password="pw")
    assert (
        config.edk_public_key_pem == "-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n"
    )  # \n 이 줄바꿈으로
    assert (config.edk_audience, config.edk_issuer, config.session_ttl_seconds) == (
        "esg-api",
        "https://edk.example",
        3600,
    )


@pytest.mark.parametrize(("env", "enabled"), [({}, False), ({"INVENTORY_SCOPE3_RUNS_ENABLED": ""}, False)])
def test_scope3_runs_are_off_when_the_switch_is_absent_or_empty(env: dict[str, str], enabled: bool) -> None:
    assert load_config({**ENV, **env}).inventory_scope3_runs_enabled is enabled


@pytest.mark.parametrize(("text", "enabled"), [("true", True), ("false", False)])
def test_scope3_runs_follow_the_switch(text: str, enabled: bool) -> None:
    config = load_config({**ENV, "INVENTORY_SCOPE3_RUNS_ENABLED": text})
    assert config.inventory_scope3_runs_enabled is enabled


@pytest.mark.parametrize("bad", ["1", "TRUE", "yes"])
def test_a_wrong_scope3_runs_switch_stops_startup(bad: str) -> None:
    with pytest.raises(ConfigError, match="INVENTORY_SCOPE3_RUNS_ENABLED 는 true 나 false 여야 한다"):
        load_config({**ENV, "INVENTORY_SCOPE3_RUNS_ENABLED": bad})


@pytest.mark.parametrize(("env", "enabled"), [({}, False), ({"GREENWASH_G1_RUNS_ENABLED": ""}, False)])
def test_greenwash_g1_runs_are_off_when_the_switch_is_absent_or_empty(env: dict[str, str], enabled: bool) -> None:
    assert load_config({**ENV, **env}).greenwash_g1_runs_enabled is enabled


@pytest.mark.parametrize(("text", "enabled"), [("true", True), ("false", False)])
def test_greenwash_g1_runs_follow_the_switch(text: str, enabled: bool) -> None:
    config = load_config({**ENV, "GREENWASH_G1_RUNS_ENABLED": text})
    assert config.greenwash_g1_runs_enabled is enabled


@pytest.mark.parametrize("bad", ["1", "TRUE", "yes"])
def test_a_wrong_greenwash_g1_runs_switch_stops_startup(bad: str) -> None:
    with pytest.raises(ConfigError, match="GREENWASH_G1_RUNS_ENABLED 는 true 나 false 여야 한다"):
        load_config({**ENV, "GREENWASH_G1_RUNS_ENABLED": bad})


def test_missing_keys_are_all_named_at_once() -> None:
    with pytest.raises(ConfigError) as caught:
        load_config({})
    for key in ENV:
        assert key in str(caught.value)


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("SESSION_SECRET", "short"),
        ("SESSION_TTL_SECONDS", "0"),
        ("SESSION_TTL_SECONDS", "ten"),
        ("DATABASE_URL_PY", "mysql://u:p@h/db"),
        ("DATABASE_URL_PY", "postgres://h"),
    ],
)
def test_bad_values_stop_startup(key: str, bad: str) -> None:
    with pytest.raises(ConfigError, match=key):
        load_config({**ENV, key: bad})


LOCAL_SECRET = "local-only-session-secret-0123456789abcdef"  # .env.example 의 값과 같은 꼴


def test_a_local_only_session_secret_starts_but_warns_loudly(capsys: pytest.CaptureFixture[str]) -> None:
    """밴드 CU2: 로컬 기본값은 조용히 뜨지 않는다. 뜨기는 한다(로컬 개발이 그대로 돈다)."""
    config = load_config({**ENV, "SESSION_SECRET": LOCAL_SECRET})
    assert config.session_secret == LOCAL_SECRET
    err = capsys.readouterr().err
    assert "SESSION_SECRET" in err
    assert "로컬 전용" in err
    assert err.count("★") >= 2


def test_the_warning_does_not_print_the_secret_value(capsys: pytest.CaptureFixture[str]) -> None:
    """경고는 값이 로컬 전용이라는 것만 말한다. 값 자체(머리 뒤의 글자)는 stderr 에도 경고 글에도 없다."""
    tail = "zq7-distinct-tail-0123456789abcdef"
    secret = f"local-only-{tail}"
    load_config({**ENV, "SESSION_SECRET": secret})
    err = capsys.readouterr().err
    assert err != ""
    assert secret not in err
    assert tail not in err
    warning = session_secret_warning(secret)
    assert warning is not None
    assert tail not in warning


def test_an_ordinary_session_secret_does_not_warn(capsys: pytest.CaptureFixture[str]) -> None:
    load_config(ENV)
    assert capsys.readouterr().err == ""
    assert session_secret_warning("x" * 32) is None
    assert session_secret_warning("my-local-only-secret-0123456789abcdef") is None  # 머리에 있을 때만
    assert session_secret_warning(LOCAL_SECRET) is not None


def test_a_short_local_only_secret_is_still_refused() -> None:
    """32바이트 검사는 그대로다: 경고가 거절을 덮지 않는다."""
    with pytest.raises(ConfigError, match="SESSION_SECRET 이 32바이트보다 짧다"):
        load_config({**ENV, "SESSION_SECRET": "local-only-short"})


def test_database_url_defaults_port_and_decodes_password() -> None:
    target = parse_database_url("postgresql://u:p%40ss@db.internal/name", key="K")
    assert (target.port, target.password) == (5432, "p@ss")


# ── LLM 호출 층의 설정 (LLM_*). 전부 선택이다 ──


def test_llm_settings_default_when_no_llm_key_is_given() -> None:
    assert load_config(ENV).llm == LlmSettings()
    assert LlmSettings() == LlmSettings(
        openai_api_key=None,
        anthropic_api_key=None,
        gemini_api_key=None,
        models_file=None,
        log_sink="memory",
        jsonl_path=None,
        rpm=None,
        translation_run_max_usd=5.0,
    )


def test_llm_empty_strings_mean_absent() -> None:
    """compose 가 `${LLM_X:-}` 로 빈 문자열을 넘긴다. 빈 값(빈칸뿐인 값 포함)은 없음(기본값)으로 읽는다."""
    blank = dict.fromkeys(LLM_KEYS, "")
    assert load_config({**ENV, **blank}).llm == LlmSettings()
    spaces = dict.fromkeys(LLM_KEYS, "  ")
    assert load_config({**ENV, **spaces}).llm == LlmSettings()


def test_llm_settings_are_read_from_env() -> None:
    env = {
        **ENV,
        "LLM_OPENAI_API_KEY": "sk-synthetic-openai-0000",
        "LLM_ANTHROPIC_API_KEY": "sk-ant-synthetic-0000",
        "LLM_GEMINI_API_KEY": "AIzaSyntheticSynthetic0000",
        "LLM_MODELS_FILE": "/etc/esg/models.json",
        "LLM_LOG_SINK": "jsonl",
        "LLM_JSONL_PATH": "/var/log/esg/llm.jsonl",
        "LLM_RPM": "12.5",
    }
    assert load_config(env).llm == LlmSettings(
        openai_api_key="sk-synthetic-openai-0000",
        anthropic_api_key="sk-ant-synthetic-0000",
        gemini_api_key="AIzaSyntheticSynthetic0000",
        models_file="/etc/esg/models.json",
        log_sink="jsonl",
        jsonl_path="/var/log/esg/llm.jsonl",
        rpm=12.5,
    )


def test_llm_keys_never_show_up_in_repr() -> None:
    env = {**ENV, "LLM_OPENAI_API_KEY": "sk-synthetic-openai-0000", "LLM_GEMINI_API_KEY": "AIzaSyntheticSynthetic0000"}
    config = load_config(env)
    for text in (repr(config), repr(config.llm), str(config.llm)):
        assert "sk-synthetic" not in text
        assert "AIzaSynthetic" not in text
        assert "api_key" not in text
    # 가린 것이 키뿐임을 보인다: 다른 칸은 repr 에 그대로 있다.
    assert "log_sink='memory'" in repr(config.llm)


@pytest.mark.parametrize(
    ("extra", "named"),
    [
        ({"LLM_LOG_SINK": "jsonl"}, "LLM_JSONL_PATH"),
        ({"LLM_LOG_SINK": "database"}, "LLM_LOG_SINK"),
        ({"LLM_RPM": "0"}, "LLM_RPM"),
        ({"LLM_RPM": "-3"}, "LLM_RPM"),
        ({"LLM_RPM": "fast"}, "LLM_RPM"),
        ({"LLM_RPM": "nan"}, "LLM_RPM"),
        ({"LLM_RPM": "inf"}, "LLM_RPM"),
    ],
)
def test_bad_llm_values_stop_startup(extra: dict[str, str], named: str) -> None:
    with pytest.raises(ConfigError, match=named):
        load_config({**ENV, **extra})


def test_translation_run_max_usd_defaults_to_five_and_is_read_from_env() -> None:
    """영문번역 한 실행의 금액 상한(TR2 — MARC-ENT-262 의 한 번 5 USD). 빈 값은 기본값."""
    assert load_config(ENV).llm.translation_run_max_usd == 5.0
    assert load_config({**ENV, "TRANSLATION_RUN_MAX_USD": "  "}).llm.translation_run_max_usd == 5.0
    assert load_config({**ENV, "TRANSLATION_RUN_MAX_USD": "12.5"}).llm.translation_run_max_usd == 12.5


@pytest.mark.parametrize("value", ["0", "-1", "free", "nan", "inf"])
def test_a_bad_translation_run_max_usd_stops_startup(value: str) -> None:
    with pytest.raises(ConfigError, match="TRANSLATION_RUN_MAX_USD"):
        load_config({**ENV, "TRANSLATION_RUN_MAX_USD": value})


def test_drafting_run_max_usd_defaults_to_five_and_is_read_from_env() -> None:
    """원고작성 한 실행의 금액 상한(RP1 — 영문번역과 같은 꼴). 빈 값은 기본값, 이름은 LLM_ 밖."""
    assert load_config(ENV).llm.drafting_run_max_usd == 5.0
    assert load_config({**ENV, "DRAFTING_RUN_MAX_USD": "  "}).llm.drafting_run_max_usd == 5.0
    assert load_config({**ENV, "DRAFTING_RUN_MAX_USD": "0.5"}).llm.drafting_run_max_usd == 0.5
    assert "DRAFTING_RUN_MAX_USD" not in ENV and all(not key.startswith("DRAFTING_") for key in LLM_KEYS)


@pytest.mark.parametrize("value", ["0", "-1", "free", "nan", "inf"])
def test_a_bad_drafting_run_max_usd_stops_startup(value: str) -> None:
    with pytest.raises(ConfigError, match="DRAFTING_RUN_MAX_USD"):
        load_config({**ENV, "DRAFTING_RUN_MAX_USD": value})


def test_translation_run_max_usd_is_not_an_llm_key() -> None:
    """이름이 LLM_ 로 시작하지 않는다 — LLM_* 일곱의 .env.example·compose 대조(아래)에 들지 않고 빠지면 기본값 5."""
    assert all(not key.startswith("TRANSLATION_") for key in LLM_KEYS)
    assert "TRANSLATION_RUN_MAX_USD" not in ENV


def test_db_sink_is_accepted_and_needs_no_jsonl_path() -> None:
    """LLM_LOG_SINK=db 는 받아들여지고(밴드 PY3b), 파일 경로를 요구하지 않는다(경로는 jsonl 일 때만 필수다)."""
    settings = load_config({**ENV, "LLM_LOG_SINK": "db"}).llm
    assert (settings.log_sink, settings.jsonl_path) == ("db", None)
    # 기본값은 그대로 memory 다(운영 기본을 db 로 바꾸지 않았다).
    assert load_config(ENV).llm.log_sink == "memory"


def test_jsonl_path_without_the_jsonl_sink_is_allowed() -> None:
    """경로만 있고 싱크가 memory 면 그대로 뜬다(경로는 쓰이지 않는다). 관리 명령의 --sink jsonl 이 그 경로를 쓴다."""
    settings = load_config({**ENV, "LLM_JSONL_PATH": "/var/log/esg/llm.jsonl"}).llm
    assert (settings.log_sink, settings.jsonl_path) == ("memory", "/var/log/esg/llm.jsonl")


LLM_KEYS = [
    "LLM_OPENAI_API_KEY",
    "LLM_ANTHROPIC_API_KEY",
    "LLM_GEMINI_API_KEY",
    "LLM_MODELS_FILE",
    "LLM_LOG_SINK",
    "LLM_JSONL_PATH",
    "LLM_RPM",
]


def test_env_example_and_compose_carry_the_same_llm_keys() -> None:
    """설정이 읽는 LLM_* 일곱이 .env.example 과 compose.yaml(api-py)에 같은 이름으로 있다. 키의 값은 빈 값이다."""
    root = Path(__file__).resolve().parents[5]
    example = (root / ".env.example").read_text(encoding="utf-8")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    for key in LLM_KEYS:
        assert f"\n{key}=" in example, key
        assert f"{key}: ${{{key}:-}}" in compose, key
    for key in LLM_KEYS[:3]:
        assert f"\n{key}=\n" in example, f"{key} 의 값이 비어 있지 않다"


# ── 원본 파일 저장소의 설정 (S3_* …). 전부 선택이다 ──

STORAGE_ENV = {
    "S3_BUCKET": "esg-documents",
    "S3_REGION": "ap-northeast-2",
    "S3_ENDPOINT": "http://storage:7070",
    "S3_PUBLIC_ENDPOINT": "http://localhost:19000",
    "S3_FORCE_PATH_STYLE": "true",
    "UPLOAD_URL_TTL_SECONDS": "120",
    "MAX_UPLOAD_BYTES": "1048576",
    "AWS_ACCESS_KEY_ID": "synthetic-access-key",
    "AWS_SECRET_ACCESS_KEY": "synthetic-secret-key",
}


def test_storage_is_none_when_no_storage_key_is_given_and_the_server_still_starts() -> None:
    assert load_config(ENV).storage is None
    # compose 가 빈 값을 넘겨도 「없음」이다. 버킷이 없으면 나머지(틀린 값이어도)를 보지 않는다.
    assert load_config({**ENV, **dict.fromkeys(STORAGE_KEYS, " ")}).storage is None
    assert load_config({**ENV, **STORAGE_ENV, "S3_BUCKET": "", "S3_ENDPOINT": "not-a-url"}).storage is None


def test_storage_settings_are_read_from_env() -> None:
    assert set(STORAGE_ENV) == set(STORAGE_KEYS)
    assert load_config({**ENV, **STORAGE_ENV}).storage == StorageSettings(
        bucket="esg-documents",
        region="ap-northeast-2",
        endpoint="http://storage:7070",
        public_endpoint="http://localhost:19000",
        force_path_style=True,
        upload_url_ttl_seconds=120,
        max_upload_bytes=1_048_576,
        access_key_id="synthetic-access-key",
        secret_access_key="synthetic-secret-key",
    )


def test_storage_defaults_match_the_ts_skeleton() -> None:
    """버킷과 리전만 있을 때(실제 S3 의 꼴): 주소 둘은 없고, 기본값은 TS 뼈대(packages/core/src/config.ts)와 같다."""
    assert load_config({**ENV, "S3_BUCKET": "b", "S3_REGION": "r"}).storage == StorageSettings(
        bucket="b",
        region="r",
        endpoint=None,
        public_endpoint=None,
        force_path_style=False,
        upload_url_ttl_seconds=300,
        max_upload_bytes=50 * 1024 * 1024,
        access_key_id=None,
        secret_access_key=None,
    )


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"S3_REGION": ""}, "S3_REGION"),
        ({"AWS_SECRET_ACCESS_KEY": ""}, "AWS_ACCESS_KEY_ID"),  # 접근 키가 하나뿐
        ({"AWS_ACCESS_KEY_ID": ""}, "AWS_SECRET_ACCESS_KEY"),
        ({"S3_ENDPOINT": "storage:7070"}, "S3_ENDPOINT"),
        ({"S3_PUBLIC_ENDPOINT": "ftp://localhost"}, "S3_PUBLIC_ENDPOINT"),
        ({"S3_FORCE_PATH_STYLE": "yes"}, "S3_FORCE_PATH_STYLE"),
        ({"UPLOAD_URL_TTL_SECONDS": "0"}, "UPLOAD_URL_TTL_SECONDS"),
        ({"UPLOAD_URL_TTL_SECONDS": "5m"}, "UPLOAD_URL_TTL_SECONDS"),
        ({"MAX_UPLOAD_BYTES": "-1"}, "MAX_UPLOAD_BYTES"),
        ({"MAX_UPLOAD_BYTES": "50MB"}, "MAX_UPLOAD_BYTES"),
    ],
)
def test_bad_storage_values_stop_startup(change: dict[str, str], named: str) -> None:
    with pytest.raises(ConfigError, match=named):
        load_config({**ENV, **STORAGE_ENV, **change})


def test_storage_problems_are_all_named_at_once() -> None:
    bad = {**ENV, **STORAGE_ENV, "S3_REGION": "", "MAX_UPLOAD_BYTES": "x", "S3_FORCE_PATH_STYLE": "1"}
    with pytest.raises(ConfigError) as caught:
        load_config(bad)
    for key in ("S3_REGION", "MAX_UPLOAD_BYTES", "S3_FORCE_PATH_STYLE"):
        assert key in str(caught.value)


def test_storage_access_keys_never_show_up_in_repr() -> None:
    config = load_config({**ENV, **STORAGE_ENV})
    for text in (repr(config), repr(config.storage), str(config.storage)):
        assert "synthetic-access-key" not in text
        assert "synthetic-secret-key" not in text
        assert "access_key" not in text
    # 가린 것이 키뿐임을 보인다: 다른 칸은 repr 에 그대로 있다.
    assert "bucket='esg-documents'" in repr(config.storage)


def _api_py_block(compose: str) -> str:
    """compose.yaml 에서 api-py 서비스의 덩어리(`  api-py:` 부터 다음 서비스 앞까지)."""
    start = compose.index("\n  api-py:\n")
    end = compose.index("\n  migrate-py:\n", start)
    return compose[start:end]


def test_compose_api_py_and_env_carry_the_same_storage_keys() -> None:
    """설정이 읽는 저장소 키 아홉이 compose.yaml 의 api-py 덩어리에 같은 이름으로 있다(더도 덜도 아니다).

    api-py 는 TS 쪽의 `x-server-env` 를 끌어 쓰지 않는다(그 묶음에는 DATABASE_URL·REDIS_URL 이 같이 있다).
    `.env.example` 에는 필수 키를 새로 만들지 않았다: 선택 키 둘은 빈 값으로 적혀 있고 compose 가 기본값을 넣는다.
    """
    root = Path(__file__).resolve().parents[5]
    block = _api_py_block((root / "compose.yaml").read_text(encoding="utf-8"))
    for key in STORAGE_KEYS:
        assert f"\n      {key}: " in block, key
    in_block = {line.strip().split(":")[0] for line in block.splitlines() if line.startswith("      ")}
    assert {key for key in in_block if key.startswith(("S3_", "AWS_", "UPLOAD_", "MAX_UPLOAD"))} == set(STORAGE_KEYS)
    assert "*server-env" not in block
    assert "storage: { condition: service_healthy }" in block
    example = (root / ".env.example").read_text(encoding="utf-8")
    for key in ("UPLOAD_URL_TTL_SECONDS", "MAX_UPLOAD_BYTES"):
        assert f"\n{key}=\n" in example, f"{key} 는 선택 키다(빈 값으로 적는다)"
    assert "개발 단계에 실제 고객 문서를 올리지 않는다" in example


# ── 작업 큐의 브로커와 일감의 수 (W1b) ────────────────────────────────

# 로컬 흉내(compose 의 queue)의 꼴. 브로커 주소에 호스트가 있다.
BROKER_ENV = {
    "CELERY_BROKER_URL": "sqs://queue:9324",
    "CELERY_BROKER_REGION": "ap-northeast-2",
    "CELERY_BROKER_SECURE": "false",
    "CELERY_QUEUE_NAME": "esg-jobs",
    "CELERY_QUEUE_URL": "http://queue:9324/000000000000/esg-jobs",
    "CELERY_VISIBILITY_TIMEOUT_SECONDS": "200",
    "CELERY_TASK_SOFT_TIME_LIMIT_SECONDS": "30",
    "CELERY_TASK_TIME_LIMIT_SECONDS": "40",
    "JOB_LEASE_SECONDS": "50",
    "JOB_MAX_ATTEMPTS": "4",
    "JOB_RETRY_DELAY_SECONDS": "2",
    "CELERY_WAIT_TIME_SECONDS": "3",
}
# 정식의 꼴: 호스트 없는 브로커 주소 + AWS 의 큐 주소 + TLS. ★ 이 꼴은 설정을 읽는 데만 쓴다(연결을 열지 않는다).
AWS_QUEUE_URL = "https://sqs.ap-northeast-2.amazonaws.com/123456789012/esg-jobs"


def test_broker_is_none_when_no_broker_key_is_given_and_the_server_still_starts() -> None:
    config = load_config(ENV)
    assert config.broker is None
    assert config.jobs == JobSettings(lease_s=330, max_attempts=3, retry_delay_s=5)
    # compose 가 빈 값을 넘겨도 「없음」이다.
    assert load_config({**ENV, **dict.fromkeys(BROKER_KEYS, " ")}).broker is None


def test_broker_and_job_settings_are_read_from_env() -> None:
    assert set(BROKER_ENV) == set(BROKER_KEYS)
    config = load_config({**ENV, **BROKER_ENV})
    assert config.broker == BrokerSettings(
        url="sqs://queue:9324",
        region="ap-northeast-2",
        queue_name="esg-jobs",
        queue_url="http://queue:9324/000000000000/esg-jobs",
        secure=False,
        visibility_timeout_s=200,
        task_soft_time_limit_s=30,
        task_time_limit_s=40,
        wait_time_seconds=3,
    )
    assert config.jobs == JobSettings(lease_s=50, max_attempts=4, retry_delay_s=2)


def test_broker_defaults_are_the_written_numbers() -> None:
    """수의 기본값. 순서: 소프트 240 < 하드 300 < 임대 330 < visibility 360(밴드 PX. 차례 전체는 아래 시험)."""
    env = {**ENV, **{key: BROKER_ENV[key] for key in ("CELERY_BROKER_URL", "CELERY_BROKER_REGION", "CELERY_QUEUE_URL")}}
    env["CELERY_BROKER_SECURE"] = "false"
    broker = load_config(env).broker
    assert broker is not None
    assert (broker.task_soft_time_limit_s, broker.task_time_limit_s, broker.visibility_timeout_s) == (240, 300, 360)
    assert broker.queue_name == "esg-jobs"
    assert broker.wait_time_seconds == 10  # 긴 폴링: Celery 문서의 기본값(짧게 하는 것은 테스트 몫)
    assert load_config(env).jobs == JobSettings(330, 3, 5)
    # CELERY_BROKER_SECURE 의 기본은 true 다(정식의 꼴에서 본다: 호스트 없는 주소는 false 와 같이 못 쓴다).
    aws = {
        **ENV,
        "CELERY_BROKER_URL": "sqs://",
        "CELERY_BROKER_REGION": "ap-northeast-2",
        "CELERY_QUEUE_URL": AWS_QUEUE_URL,
    }
    aws_broker = load_config(aws).broker
    assert aws_broker is not None and aws_broker.secure is True


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"CELERY_BROKER_URL": "amqp://guest:guest@rabbit:5672//"}, "CELERY_BROKER_URL 의 꼴이 틀렸다"),
        ({"CELERY_BROKER_URL": "redis://redis:6379/0"}, "CELERY_BROKER_URL 의 꼴이 틀렸다"),
        ({"CELERY_BROKER_REGION": ""}, "CELERY_BROKER_REGION 이 있어야 한다"),
        ({"CELERY_BROKER_SECURE": "yes"}, "CELERY_BROKER_SECURE 는 true 나 false 여야 한다"),
        ({"CELERY_QUEUE_URL": ""}, "CELERY_QUEUE_URL 이 있어야 한다"),
        ({"CELERY_QUEUE_URL": "queue:9324/esg-jobs"}, "CELERY_QUEUE_URL 의 꼴이 틀렸다"),
        ({"CELERY_VISIBILITY_TIMEOUT_SECONDS": "0"}, "CELERY_VISIBILITY_TIMEOUT_SECONDS 는 0보다 큰 정수여야 한다"),
        ({"CELERY_TASK_TIME_LIMIT_SECONDS": "1.5"}, "CELERY_TASK_TIME_LIMIT_SECONDS 는 0보다 큰 정수여야 한다"),
        ({"JOB_MAX_ATTEMPTS": "-1"}, "JOB_MAX_ATTEMPTS 는 0보다 큰 정수여야 한다"),
        ({"JOB_RETRY_DELAY_SECONDS": "곧"}, "JOB_RETRY_DELAY_SECONDS 는 0보다 큰 정수여야 한다"),
        # 긴 폴링: 1~20 만(0 = 짧은 폴링은 받지 않는다. SQS 의 WaitTimeSeconds 는 0~20)
        ({"CELERY_WAIT_TIME_SECONDS": "0"}, "CELERY_WAIT_TIME_SECONDS 는 0보다 큰 정수여야 한다"),
        ({"CELERY_WAIT_TIME_SECONDS": "-1"}, "CELERY_WAIT_TIME_SECONDS 는 0보다 큰 정수여야 한다"),
        ({"CELERY_WAIT_TIME_SECONDS": "곧"}, "CELERY_WAIT_TIME_SECONDS 는 0보다 큰 정수여야 한다"),
        ({"CELERY_WAIT_TIME_SECONDS": "1.5"}, "CELERY_WAIT_TIME_SECONDS 는 0보다 큰 정수여야 한다"),
        ({"CELERY_WAIT_TIME_SECONDS": "21"}, "CELERY_WAIT_TIME_SECONDS 는 20 이하여야 한다"),
        # 수의 짝: 소프트 < 하드 < 임대 < visibility
        ({"CELERY_TASK_SOFT_TIME_LIMIT_SECONDS": "40"}, "CELERY_TASK_SOFT_TIME_LIMIT_SECONDS 는"),
        ({"JOB_LEASE_SECONDS": "40"}, "JOB_LEASE_SECONDS 는 CELERY_TASK_TIME_LIMIT_SECONDS 보다 커야 한다"),
        ({"JOB_LEASE_SECONDS": "39"}, "JOB_LEASE_SECONDS 는 CELERY_TASK_TIME_LIMIT_SECONDS 보다 커야 한다"),
        ({"JOB_LEASE_SECONDS": "200"}, "JOB_LEASE_SECONDS 는 CELERY_VISIBILITY_TIMEOUT_SECONDS 보다 작아야 한다"),
        ({"JOB_LEASE_SECONDS": "201"}, "JOB_LEASE_SECONDS 는 CELERY_VISIBILITY_TIMEOUT_SECONDS 보다 작아야 한다"),
    ],
)
def test_bad_broker_values_stop_startup(change: dict[str, str], named: str) -> None:
    with pytest.raises(ConfigError, match=named):
        load_config({**ENV, **BROKER_ENV, **change})


def test_the_lease_must_sit_between_the_hard_limit_and_the_visibility_even_without_a_broker() -> None:
    """브로커가 없어도 수의 짝은 본다(기본값과 견준다: 하드 300 < 임대 < visibility 360)."""
    for lease in ("300", "360"):
        with pytest.raises(ConfigError, match="JOB_LEASE_SECONDS 는"):
            load_config({**ENV, "JOB_LEASE_SECONDS": lease})
    assert load_config({**ENV, "JOB_LEASE_SECONDS": "301"}).jobs.lease_s == 301
    assert load_config({**ENV, "JOB_LEASE_SECONDS": "359"}).jobs.lease_s == 359


def test_the_whole_time_order_parser_then_client_then_soft_then_hard_then_lease_then_visibility() -> None:
    """시간의 차례 전체(밴드 PX, 감독 처분 2026-10-16). 하나라도 어긋나면 같은 PDF 가 거듭 쌓이거나 일감이 둘로 돈다.

    파서 PARSE_TIMEOUT_SECONDS 180 < 파서 클라이언트 PARSER_TIMEOUT_MS 210초 < soft 240 < hard 300 < 임대 330
    < visibility 360. 파서의 값은 services/parser/app.py 의 기본값을, 클라이언트의 값은 설정과 compose 의 기본값을,
    visibility 는 docker/elasticmq.conf 를 읽는다(코드의 기본값과 따로 노는 자리를 함께 묶는다).
    """
    import re

    root = Path(__file__).resolve().parents[5]
    parser_app = (root / "services" / "parser" / "app.py").read_text(encoding="utf-8")
    found = re.search(r'\nPARSE_TIMEOUT_SECONDS = _positive\("PARSE_TIMEOUT_SECONDS", "(\d+)", float\)\n', parser_app)
    assert found is not None
    parser_s = int(found.group(1))
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    composed = re.search(r"\n      PARSER_TIMEOUT_MS: \$\{PARSER_TIMEOUT_MS:-(\d+)\}\n", compose)
    assert composed is not None and int(composed.group(1)) == Config.parser_timeout_ms
    assert load_config(ENV).parser_timeout_ms == Config.parser_timeout_ms
    conf = (root / "docker" / "elasticmq.conf").read_text(encoding="utf-8")
    queued = re.search(r"\n  esg-jobs \{\n(?:\s*#.*\n)*\s*defaultVisibilityTimeout = (\d+) seconds\n", conf)
    assert queued is not None
    order = [
        parser_s * 1000,
        Config.parser_timeout_ms,
        BrokerSettings.task_soft_time_limit_s * 1000,
        BrokerSettings.task_time_limit_s * 1000,
        JobSettings.lease_s * 1000,
        BrokerSettings.visibility_timeout_s * 1000,
        int(queued.group(1)) * 1000,
    ]
    assert order == [180_000, 210_000, 240_000, 300_000, 330_000, 360_000, 360_000]
    assert order == sorted(order) and len(set(order[:-1])) == len(order) - 1  # 끝 둘(설정·큐의 visibility)만 같다


@pytest.mark.parametrize(
    ("change", "named"),
    [
        # ① 큐 주소가 로컬인데 브로커 주소에 호스트가 없다 → kombu 는 진짜 AWS 를 부른다
        (
            {"CELERY_BROKER_URL": "sqs://", "CELERY_BROKER_SECURE": "true"},
            "AWS 의 주소가 아닌데 CELERY_BROKER_URL 에 호스트가 없다",
        ),
        # ② TLS 를 끄고(로컬 흉내의 표시) 브로커 주소에 호스트가 없다
        (
            {"CELERY_BROKER_URL": "sqs://", "CELERY_QUEUE_URL": AWS_QUEUE_URL},
            "CELERY_BROKER_SECURE 가 false 인데 CELERY_BROKER_URL 에 호스트가 없다",
        ),
        # 자격 증명은 있고 호스트는 없다(netloc 은 비지 않았다). 호스트가 없는 것이다
        (
            {"CELERY_BROKER_URL": "sqs://k:s@", "CELERY_BROKER_SECURE": "true"},
            "AWS 의 주소가 아닌데 CELERY_BROKER_URL 에 호스트가 없다",
        ),
        ({"CELERY_BROKER_URL": "sqs://k:s@"}, "CELERY_BROKER_SECURE 가 false 인데 CELERY_BROKER_URL 에 호스트가 없다"),
    ],
)
def test_a_hostless_broker_url_that_would_reach_real_aws_stops_startup(change: dict[str, str], named: str) -> None:
    """끝점은 브로커 주소의 호스트에서만 온다. 호스트가 없으면 큐 주소가 로컬이어도 진짜 AWS 로 간다(막는 꼴 둘)."""
    with pytest.raises(ConfigError, match=named):
        load_config({**ENV, **BROKER_ENV, **change})


def test_the_production_shape_passes_without_opening_a_connection() -> None:
    """정식의 꼴(호스트 없음 + amazonaws.com 의 큐 주소 + TLS)은 지난다. 읽기만 한다: 연결을 열지 않는다."""
    env = {
        **ENV,
        **BROKER_ENV,
        "CELERY_BROKER_URL": "sqs://",
        "CELERY_BROKER_SECURE": "true",
        "CELERY_QUEUE_URL": AWS_QUEUE_URL,
    }
    broker = load_config(env).broker
    assert broker is not None
    assert (broker.url, broker.secure, broker.queue_url) == ("sqs://", True, AWS_QUEUE_URL)


def test_broker_problems_are_all_named_at_once() -> None:
    with pytest.raises(ConfigError) as caught:
        load_config(
            {**ENV, "CELERY_BROKER_URL": "redis://redis:6379/0", "CELERY_BROKER_SECURE": "no", "JOB_MAX_ATTEMPTS": "0"}
        )
    message = str(caught.value)
    for named in (
        "CELERY_BROKER_URL 의 꼴",
        "CELERY_BROKER_REGION",
        "CELERY_BROKER_SECURE",
        "CELERY_QUEUE_URL",
        "JOB_MAX_ATTEMPTS",
    ):
        assert named in message, named


def test_broker_addresses_never_show_up_in_repr() -> None:
    """브로커 주소에는 키가, 큐 주소에는 계정 번호가 들 수 있다. 둘 다 repr 에 없다."""
    env = {**ENV, **BROKER_ENV, "CELERY_BROKER_URL": "sqs://synthetic-key:synthetic-secret@queue:9324"}
    config = load_config(env)
    for text in (repr(config), repr(config.broker)):
        assert "synthetic-secret" not in text
        assert "queue:9324" not in text
        assert "000000000000" not in text
    # 가린 것이 주소 둘뿐임을 보인다: 다른 칸은 repr 에 그대로 있다.
    assert "queue_name='esg-jobs'" in repr(config.broker)


def _service_block(compose: str, name: str) -> str:
    """compose.yaml 에서 서비스 하나의 덩어리(`  <이름>:` 부터 다음 서비스나 `volumes:` 앞까지)."""
    import re

    found = re.search(rf"\n  {re.escape(name)}:\n(.*?)(?=\n  [a-z-]+:\n|\nvolumes:)", compose, re.S)
    assert found is not None, name
    return found.group(1)


def test_compose_api_py_and_env_carry_the_same_broker_keys() -> None:
    """설정이 읽는 브로커·일감 키 열하나가 compose.yaml 의 api-py 덩어리에 같은 이름으로 있다(더도 덜도 아니다).

    ★ 브로커 주소는 `${…}` 가 아니라 **호스트를 가진 글자**다(.env 로 호스트를 지울 길이 없다).
    """
    from urllib.parse import urlsplit

    root = Path(__file__).resolve().parents[5]
    block = _api_py_block((root / "compose.yaml").read_text(encoding="utf-8"))
    in_block = {
        line.strip().split(":")[0]: line.strip().split(": ", 1)[1]
        for line in block.splitlines()
        if line.startswith("      ") and not line.strip().startswith("#") and ": " in line
    }
    assert {key for key in in_block if key.startswith(("CELERY_", "JOB_"))} == set(BROKER_KEYS)
    assert in_block["CELERY_BROKER_URL"] == "sqs://queue:9324"
    assert "$" not in in_block["CELERY_BROKER_URL"]
    assert urlsplit(in_block["CELERY_BROKER_URL"]).hostname == "queue"
    assert in_block["CELERY_QUEUE_URL"] == "http://queue:9324/000000000000/esg-jobs"
    assert in_block["CELERY_BROKER_SECURE"] == '"false"'
    assert in_block["CELERY_BROKER_REGION"] == "${S3_REGION}"
    assert in_block["CELERY_QUEUE_NAME"] == "esg-jobs"
    # 수 여섯은 빈 값이 기본이다(빈 값 = 설정의 기본값. 통합 테스트가 프로세스 환경으로 짧은 값을 준다).
    for key in BROKER_KEYS[5:]:
        assert in_block[key] == f"${{{key}:-}}", key
    assert "queue: { condition: service_healthy }" in block
    # compose 의 글자 값이 설정 검사를 지난다.
    local = {**ENV, "CELERY_BROKER_URL": "sqs://queue:9324", "CELERY_QUEUE_URL": in_block["CELERY_QUEUE_URL"]}
    assert (
        load_config({**local, "CELERY_BROKER_SECURE": "false", "CELERY_BROKER_REGION": "ap-northeast-2"}).broker
        is not None
    )
    example = (root / ".env.example").read_text(encoding="utf-8")
    for key in BROKER_KEYS[5:]:
        assert f"\n{key}=\n" in example, f"{key} 는 선택 키다(빈 값으로 적는다)"
    # 주소 셋은 .env 의 것이 아니다(compose 의 글자다).
    assert "\nCELERY_BROKER_URL=" not in example and "\nCELERY_QUEUE_URL=" not in example


def test_compose_worker_py_takes_the_api_py_environment_and_no_owner_address() -> None:
    """worker-py 는 api-py 의 환경을 앵커로 그대로 받는다. 주인 역할의 주소·호스트 포트가 없고 명령이 celery 다."""
    root = Path(__file__).resolve().parents[5]
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    assert "\n    environment: &api-py-env\n" in _api_py_block(compose)
    worker = _service_block(compose, "worker-py")
    assert "\n    environment:\n      <<: *api-py-env\n" in "\n" + worker
    assert "DATABASE_URL_PY_OWNER" not in worker
    assert "ports:" not in worker
    assert "healthcheck:" not in worker.replace("# healthcheck", "")
    assert '"celery", "-A", "esgapi.config.celery", "worker"' in worker
    assert '"-Q", "esg-jobs"' in worker
    assert "image: ${COMPOSE_PROJECT_NAME:-esg-app}/api-py:local" in worker
    # worker-py 의 environment 에는 앵커 한 줄뿐이다(따로 더한 키가 없다).
    lines = worker.split("    environment:\n", 1)[1].split("\n    depends_on:", 1)[0].splitlines()
    assert [line.strip() for line in lines if line.strip()] == ["<<: *api-py-env"]
    for needed in ("postgres", "storage", "parser", "queue"):
        assert f"{needed}: {{ condition: service_healthy }}" in worker, needed
    assert "migrate-py: { condition: service_completed_successfully }" in worker


def test_the_local_queue_is_made_with_the_visibility_the_app_believes() -> None:
    """미리 만든 큐에서는 큐의 속성이 재전달의 시각을 정한다. conf 의 초 수 = 설정의 기본값이고 임대의 기본보다 크다."""
    import re

    root = Path(__file__).resolve().parents[5]
    conf = (root / "docker" / "elasticmq.conf").read_text(encoding="utf-8")
    found = re.search(r"\n  esg-jobs \{\n(?:\s*#.*\n)*\s*defaultVisibilityTimeout = (\d+) seconds\n", conf)
    assert found is not None
    seconds = int(found.group(1))
    assert seconds == BrokerSettings.visibility_timeout_s == 360
    assert seconds > JobSettings.lease_s
    assert "host = queue" in conf and "port = 9324" in conf
    queue = _service_block((root / "compose.yaml").read_text(encoding="utf-8"), "queue")
    assert "image: softwaremill/elasticmq-native:1.7.1" in queue
    assert "./docker/elasticmq.conf:/opt/elasticmq.conf:ro" in queue
    assert "ports:" not in queue


def test_compose_gives_the_session_secret_no_default() -> None:
    """compose 는 SESSION_SECRET 에 기본값을 두지 않는다(.env 에 없으면 compose 가 시작 전에 멈춘다).

    MARC-ISSUE-66 의 2.
    """
    import re

    root = Path(__file__).resolve().parents[5]
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    assert re.search(r"\n      SESSION_SECRET: \$\{SESSION_SECRET:\?[^}\n]+\}\n", _api_py_block(compose))
    assert "local-only" not in compose


# ── 공급사 SDK 의 환경 변수(LH1 S6 — MARC-ISSUE-306 m3) ──

LIVE = {
    **ENV,
    "LLM_RUN_MODE": "live",
    "LLM_LOG_SINK": "db",
    "LLM_OPENAI_API_KEY": "sk-LH1-synthetic",
    "LLM_RUN_MAX_USD": "0.5",
}
SDK_VALUE = "https://value-not-shown.invalid/LH1-synthetic"  # 글에 실리면 안 되는 값
SDK_NAMES = sorted(SDK_ENV_NAMES) + [f"{prefix}BASE_URL" for prefix in SDK_ENV_PREFIXES]


@pytest.mark.parametrize("name", ["OPENAI_BASE_URL", *SDK_NAMES])
def test_live_with_an_sdk_variable_stops_startup_naming_it_without_the_value(name: str) -> None:
    with pytest.raises(ConfigError) as caught:
        load_config({**LIVE, name: SDK_VALUE})
    assert f"SDK 환경 변수를 두지 않는다: {name}" in str(caught.value)
    assert SDK_VALUE not in str(caught.value)


@pytest.mark.parametrize("name", ["OPENAI_BASE_URL", *SDK_NAMES])
def test_mock_with_an_sdk_variable_starts_and_warns_one_line_by_name(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    load_config({**ENV, name: SDK_VALUE})
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert name in err and SDK_VALUE not in err


def test_several_sdk_variables_are_named_together_in_order(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ConfigError, match="SDK 환경 변수를 두지 않는다: ANTHROPIC_BASE_URL,OPENAI_ORG_ID"):
        load_config({**LIVE, "OPENAI_ORG_ID": SDK_VALUE, "ANTHROPIC_BASE_URL": SDK_VALUE})
    load_config({**ENV, "OPENAI_ORG_ID": SDK_VALUE, "ANTHROPIC_BASE_URL": SDK_VALUE})
    assert "ANTHROPIC_BASE_URL,OPENAI_ORG_ID" in capsys.readouterr().err


def test_without_sdk_variables_there_is_no_warning(capsys: pytest.CaptureFixture[str]) -> None:
    load_config(ENV)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("name", ["AWS_REGION", "SSL_CERT_FILE", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"])
def test_ordinary_names_the_sdks_also_read_are_not_blocked(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    """운영 셸이 두는 일반 이름(M3) — live 도 뜨고, 경고 0(live 의 기동 알림 한 줄만)."""
    config = load_config({**LIVE, name: "ap-northeast-2"})
    assert config.llm.run_mode == "live"
    load_config({**ENV, name: "ap-northeast-2"})
    assert "SDK" not in capsys.readouterr().err
