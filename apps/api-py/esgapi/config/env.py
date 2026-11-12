"""설정을 환경 변수에서만 읽는다. 값이 코드에 없다.

틀에 묶이지 않은 순수한 함수다(표준 라이브러리만. Django 를 import 하지 않는다).
Django 설정(config/settings/base.py)이 이것을 불러 쓴다.
빠진 키가 있으면 서버가 뜨기 전에, 빠진 것을 전부 모아 한 번에 알린다.
"""

import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal
from urllib.parse import unquote, urlsplit


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class DbTarget:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass(frozen=True)
class LlmSettings:
    """LLM 호출 층(esgapi/core/llm)의 설정. 전부 선택이다: 하나도 없어도 서버는 뜬다.

    키 셋은 repr 에 내지 않는다(Config 를 찍어도 값이 기록에 남지 않게). 없으면 None 이고, 그 공급사를 부를 때
    이름 있는 오류(LiveSetupError)가 난다. 키는 여기서만 읽어 어댑터에 명시로 넘긴다(SDK 가 환경에서 스스로 읽지 않게).
    """

    openai_api_key: str | None = field(default=None, repr=False)
    anthropic_api_key: str | None = field(default=None, repr=False)
    gemini_api_key: str | None = field(default=None, repr=False)
    models_file: str | None = None  # 모델 설정 파일의 경로. None 이면 패키지에 실린 자료(core/llm/data/models.json)
    log_sink: Literal["memory", "jsonl", "db"] = "memory"  # 호출 기록이 가는 곳(db = 표 core_llm_call_logs)
    jsonl_path: str | None = None  # log_sink 가 jsonl 일 때의 파일 경로(그때는 필수)
    rpm: float | None = None  # 실제 공급사 호출의 분당 요청 수 상한. None 이면 간격을 두지 않는다
    # 영문번역 실행 하나의 호출 비용 위끝 상한(USD — dry-run 어림). 넘으면 공급사 전에 over_budget(MARC-ENT-262 의
    # 「한 번 5 USD」, MARC-ENT-334). 환경 TRANSLATION_RUN_MAX_USD
    translation_run_max_usd: float = 5.0
    # 원고작성 실행 하나의 호출 비용 위끝 상한(USD — dry-run 어림, 밴드 RP1). 넘으면 공급사 전에 over_budget(영문번역과
    # 같은 꼴·같은 기본값). 환경 DRAFTING_RUN_MAX_USD
    drafting_run_max_usd: float = 5.0
    # 실행기(runs/context.py)가 실제 공급사의 키를 싣는가(LV1). mock(기본·빈 값) = 싣지 않는다(모의 공급사만),
    # live = 싣는다. 환경 LLM_RUN_MODE. 그 밖의 값은 기동 실패다(모르는 값을 mock 으로 삼키지 않는다 — 테스트 73 조건)
    run_mode: Literal["mock", "live"] = "mock"
    # live 실행 하나의 호출 비용 상한(USD — 그 실행의 앞 시도 DB 합 + 이 시도의 기록). 넘으면 공급사 전에 막힌다
    # (MARC-ENT-262 의 「한 번 5 USD」). 환경 LLM_RUN_MAX_USD. live 면 명시해야 한다(기본값은 mock 에서만 — critic M1)
    run_max_usd: float = 5.0


@dataclass(frozen=True)
class StorageSettings:
    """원본 파일 저장소(S3·S3 호환)의 설정. S3_BUCKET 이 있을 때만 생긴다(없으면 Config.storage 가 None).

    접근 키 둘은 repr 에 내지 않는다. 둘 다 없으면 None 이고 boto3 의 기본 순서(ECS 의 태스크 역할)가 찾는다.
    이름·단위·기본값은 TS 뼈대(packages/core/src/config.ts)와 같다.
    """

    bucket: str
    region: str
    endpoint: str | None = None  # 서버가 저장소에 닿는 주소. None 이면 AWS 의 주소
    public_endpoint: str | None = None  # 클라이언트가 저장소에 닿는 주소(서명에 들어간다). None 이면 endpoint
    force_path_style: bool = False
    upload_url_ttl_seconds: int = 300  # 서명한 올리기 주소의 수명(초)
    max_upload_bytes: int = 50 * 1024 * 1024  # 올릴 수 있는 파일의 상한. 파서의 MAX_SOURCE_BYTES 기본값과 같다
    access_key_id: str | None = field(default=None, repr=False)
    secret_access_key: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class JobSettings:
    """일감(표 run_jobs)을 잡고 다시 해 보는 수. 전부 선택이고 브로커가 없어도 있다(태스크의 함수는 브로커 없이 돈다).

    ★ 값은 재서 정한 것이 아니다(어림). max_attempts 만 TS 뼈대의 QUEUE_ATTEMPTS 기본값과 같게 두었다.
    """

    # 임대: 워커가 일감을 쥐고 있다고 표에 적는 시간. 하드 시간 제한 < 임대 < 큐의 visibility. 시도마다 새로 잡는다.
    # 시간의 차례(밴드 PX, 감독 처분 2026-10-16): 파서 180 < 파서 클라이언트 210 < soft 240 < hard 300 < 임대 330
    # < visibility 360. config/tests/test_env.py 가 이 차례 전체를 본다.
    lease_s: int = 330
    max_attempts: int = 3  # 한 일감을 몇 번까지 잡는가(첫 시도 포함)
    retry_delay_s: int = 5  # 잠깐의 실패 뒤 다시 해 보기까지(어림)


@dataclass(frozen=True)
class BrokerSettings:
    """작업 큐의 브로커(SQS·SQS 흉내)와 워커의 시간 제한. CELERY_BROKER_URL 이 있을 때만 생긴다(없으면 None).

    주소 둘은 repr 에 내지 않는다(브로커 주소에는 키가, 큐 주소에는 계정 번호가 들 수 있다).
    ★ 끝점(요청이 가는 곳)은 **브로커 주소의 호스트**에서만 온다(kombu 5.6.2 transport/SQS.py 의 endpoint_url).
      호스트가 없으면 큐 주소가 로컬이어도 kombu 는 진짜 AWS(sqs.<region>.amazonaws.com)를 부른다.
      load_broker_settings 가 그 꼴 둘을 문제 목록으로 막는다.
    """

    url: str = field(repr=False)  # 로컬 `sqs://queue:9324`(호스트 = 끝점), 정식 `sqs://`(태스크 역할)
    region: str
    queue_name: str
    queue_url: str = field(repr=False)  # 그 큐의 주소. 늘 predefined_queues 로 넘긴다(Celery 가 큐를 만들지 않는다)
    secure: bool = True  # TLS. 로컬 흉내만 false
    # 아래 셋은 어림이다(재서 정한 값이 아니다).
    # ★ 미리 만든 큐에서는 Celery 가 visibility 를 쓰지 않는다: 큐의 속성이 재전달의 시각을 정한다
    #   (로컬은 docker/elasticmq.conf 의 defaultVisibilityTimeout). 이 값은 「큐가 그렇게 만들어져 있다」는 앱의 앎이다.
    visibility_timeout_s: int = 360
    # 저장소 get 최악 14초 + 파서 클라이언트 210초 + 여유. 파서 210초는 실제 173쪽 보고서가 컨테이너에서 69초 걸린
    # 기록(services/parser/README.md)에서 넉넉히 잡은 것이다(밴드 PX, 감독 처분).
    task_soft_time_limit_s: int = 240
    task_time_limit_s: int = 300
    # 긴 폴링(초. SQS 의 WaitTimeSeconds, 1~20). Celery 문서(「Using Amazon SQS」, 5.6.3)의 기본값.
    # 짧게 하는 것은 테스트 몫이다.
    wait_time_seconds: int = 10


@dataclass(frozen=True)
class Config:
    database: DbTarget  # 앱 역할(esg_app)의 주소. 주인 역할의 주소는 여기에 오지 않는다(config/settings/migrate.py)
    edk_public_key_pem: str
    edk_audience: str
    edk_issuer: str
    session_secret: str
    session_ttl_seconds: int
    llm: LlmSettings = LlmSettings()
    # 문서 파서(services/parser)의 주소와 기다리는 최대 시간(ms). 주소는 선택이다: 없어도 서버는 뜬다(None).
    parser_url: str | None = None
    # 환경 변수 PARSER_TIMEOUT_MS(ms. 이름·단위는 걷힌 TS worker 의 것을 이어받았다).
    # 파서 자신의 상한(180초)보다 길게 두어 파서가 먼저 422 parse_timeout 으로 끊게 한다(밴드 PX).
    parser_timeout_ms: int = 210_000
    # 원본 파일 저장소. 선택이다: S3_BUCKET 이 없으면 None 이고 서버는 뜬다
    # (문서를 만들고 올림을 확인하는 경로가 503 storage_unconfigured 를 낸다).
    storage: StorageSettings | None = None
    # 작업 큐의 브로커. 선택이다: CELERY_BROKER_URL 이 없으면 None 이고 서버는 뜬다
    # (큐에 넣는 갈고리가 기록 한 줄만 남기고 일감은 `queued` 에 머문다).
    broker: BrokerSettings | None = None
    jobs: JobSettings = JobSettings()
    # Scope 3 코랩 실행(POST /runs inventory.scope3)을 받는가. 기본은 끔: 시간 상한에 걸리면 처음부터 다시 돌아 공급사
    # 비용이 몇 배가 된다(sid:MARC-ISSUE-499, 가지 리뷰 F2). 실제 키가 있는 배포본에서 켜는 일은 사용자 몫이다.
    inventory_scope3_runs_enabled: bool = False
    # 그린워싱 2차 엔진 실행(POST /runs greenwash, flowId greenwash.engine@G1)을 받는가. 기본은 끔(GE1b D4): 여는 것은
    # 사용자 결정 뒤다. 꺼짐이면 G1 끼움의 check_options 가 거절한다(400 INVALID_OPTIONS, 행 0) — 읽는 자리는 그것뿐.
    greenwash_g1_runs_enabled: bool = False


def parse_database_url(url: str, *, key: str) -> DbTarget:
    """postgres://사용자:비밀번호@호스트:포트/DB이름 을 나눈다(TS 뼈대의 DATABASE_URL 과 같은 꼴)."""
    parts = urlsplit(url)
    name = parts.path.removeprefix("/")
    if parts.scheme not in ("postgres", "postgresql") or not parts.hostname or not parts.username or not name:
        raise ConfigError(f"{key} 의 꼴이 틀렸다. postgres://사용자:비밀번호@호스트:포트/DB이름 이어야 한다")
    return DbTarget(
        host=parts.hostname,
        port=parts.port or 5432,
        name=name,
        user=unquote(parts.username),
        password=unquote(parts.password or ""),
    )


# 공급사 SDK 가 스스로 읽는 환경 변수(키 말고도 주소·머리·자격 증명 — 키가 다른 주소로 갈 길). 앱은 키를 LLM_*_API_KEY
# 로만 받아 명시로 넘기므로 이 이름들은 쓸 일이 없다(LH1 Q3, MARC-ISSUE-306 m3). live 면 기동을 멈추고, mock 이면
# stderr 경고 한 줄(이름만). 이름은 설치된 SDK 를 2026-10-28 에 grep 하고 생성자를 손으로 대조해 모았다(openai 3.26.0
# _client.py, anthropic 1.11.0 _client.py, google-genai 2.28.0 _api_client.py — 밴드 보고 band-reports/LH1.md ★h).
# 접두는 SDK 자기 접두다(그 SDK 가 새 이름을 더해도 걸린다).
# 막지 않는 일반 이름(SDK 가 읽어도): AWS_REGION·AWS_DEFAULT_REGION(운영 셸이 둔다 — infra/README.md), SSL_CERT_FILE·
# SSL_CERT_DIR, APPDATA, DEFER_PYDANTIC_BUILD, PYTEST_CURRENT_TEST, GITHUB_ACTIONS, UNITTEST_ON_FORGE,
# GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION(둘은 Vertex 갈래에서만 읽힌다 —
# create_gemini_client 가 vertexai=False 로 고정). HTTP(S)_PROXY 같은 전송 층 이름도 여기서 보지 않는다(LH2 Q13 —
# 프록시는 CONNECT 터널이라 신뢰 루트를 같이 바꾸지 않으면 키를 읽지 못한다. 저장소 쓰임 0).
SDK_ENV_PREFIXES: Final = ("OPENAI_", "AZURE_OPENAI_", "ANTHROPIC_", "GOOGLE_GENAI_")
SDK_ENV_NAMES: Final = frozenset(
    {
        "GOOGLE_GEMINI_BASE_URL",
        "GOOGLE_VERTEX_BASE_URL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_BEDROCK_BASE_URL",
        "CLOUD_ML_REGION",
    }
)


def sdk_env_names(env: Mapping[str, str]) -> list[str]:
    """env 에 있는 SDK 환경 변수의 이름(정렬). 빈 값도 센다(SDK 가 빈 글자를 그대로 쓰는 이름이 있다)."""
    return sorted(name for name in env if name in SDK_ENV_NAMES or name.startswith(SDK_ENV_PREFIXES))


def sdk_env_warning(env: Mapping[str, str]) -> str | None:
    """mock 기동 때 낼 경고 한 줄(이름만 — 값 0). SDK 환경 변수가 없으면 None. live 는 load_llm_settings 가 멈춘다."""
    names = sdk_env_names(env)
    if not names:
        return None
    return "경고: 공급사 SDK 가 읽는 환경 변수가 있다(LLM_RUN_MODE=live 면 기동이 멈춘다): " + ",".join(names)


def load_llm_settings(env: Mapping[str, str], problems: list[str]) -> LlmSettings:
    """LLM_* 를 읽는다. compose 가 `${LLM_X:-}` 로 빈 문자열을 넘기므로 빈 값(빈칸뿐인 값 포함)은 「없음」으로
    읽는다.
    """

    def optional(key: str) -> str | None:
        value = env.get(key, "").strip()
        return value or None

    sink = optional("LLM_LOG_SINK") or "memory"
    jsonl_path = optional("LLM_JSONL_PATH")
    if sink not in ("memory", "jsonl", "db"):
        problems.append("LLM_LOG_SINK 는 memory, jsonl, db 가운데 하나여야 한다")
        sink = "memory"
    elif sink == "jsonl" and jsonl_path is None:
        problems.append("LLM_LOG_SINK 가 jsonl 이면 LLM_JSONL_PATH 가 있어야 한다")

    rpm: float | None = None
    rpm_text = optional("LLM_RPM")
    if rpm_text is not None:
        try:
            rpm = float(rpm_text)
        except ValueError:
            rpm = None
        # `not rpm > 0` 꼴이라 nan 도 걸린다. inf 는 따로 막는다.
        if rpm is None or not rpm > 0 or rpm == float("inf"):
            problems.append("LLM_RPM 은 0보다 큰 수여야 한다")
            rpm = None

    translation_run_max_usd = 5.0
    max_usd_text = optional("TRANSLATION_RUN_MAX_USD")
    if max_usd_text is not None:
        try:
            translation_run_max_usd = float(max_usd_text)
        except ValueError:
            translation_run_max_usd = float("nan")
        # `not x > 0` 꼴이라 nan 도 걸린다. inf 는 따로 막는다(LLM_RPM 과 같은 꼴).
        if not translation_run_max_usd > 0 or translation_run_max_usd == float("inf"):
            problems.append("TRANSLATION_RUN_MAX_USD 는 0보다 큰 수여야 한다")
            translation_run_max_usd = 5.0

    drafting_run_max_usd = 5.0  # RP1 — 위와 같은 검사 꼴
    drafting_max_text = optional("DRAFTING_RUN_MAX_USD")
    if drafting_max_text is not None:
        try:
            drafting_run_max_usd = float(drafting_max_text)
        except ValueError:
            drafting_run_max_usd = float("nan")
        if not drafting_run_max_usd > 0 or drafting_run_max_usd == float("inf"):
            problems.append("DRAFTING_RUN_MAX_USD 는 0보다 큰 수여야 한다")
            drafting_run_max_usd = 5.0

    run_mode = optional("LLM_RUN_MODE") or "mock"
    if run_mode not in ("mock", "live"):
        # 받은 값은 싣지 않는다(키를 잘못 넣은 자리일 수 있다).
        problems.append("LLM_RUN_MODE 는 mock, live 가운데 하나여야 한다(빈 값은 mock)")
        run_mode = "mock"

    run_max_usd = 5.0
    run_max_text = optional("LLM_RUN_MAX_USD")
    if run_max_text is not None:
        try:
            run_max_usd = float(run_max_text)
        except ValueError:
            run_max_usd = float("nan")
        # `not x > 0` 꼴이라 nan 도 걸린다. inf 는 따로 막는다(LLM_RPM 과 같은 꼴).
        if not run_max_usd > 0 or run_max_usd == float("inf"):
            problems.append("LLM_RUN_MAX_USD 는 0보다 큰 수여야 한다")
            run_max_usd = 5.0

    keys = (optional("LLM_OPENAI_API_KEY"), optional("LLM_ANTHROPIC_API_KEY"), optional("LLM_GEMINI_API_KEY"))
    if run_mode == "live":
        # live 의 기동 조건 셋(LV1 Q3·critic M1): 실비가 장부(core_llm_call_logs)에 남고, 키가 있고, 상한이 명시됐다.
        if sink != "db":
            problems.append("LLM_RUN_MODE 가 live 면 LLM_LOG_SINK 가 db 여야 한다")
        if all(key is None for key in keys):
            problems.append("LLM_RUN_MODE 가 live 면 공급사 키(LLM_OPENAI_API_KEY 등 셋) 가운데 하나가 있어야 한다")
        if run_max_text is None:
            problems.append("LLM_RUN_MODE 가 live 면 LLM_RUN_MAX_USD 가 있어야 한다")
        sdk_names = sdk_env_names(env)
        if sdk_names:
            # 이름만 싣는다(값은 키일 수 있다).
            problems.append("LLM_RUN_MODE 가 live 면 SDK 환경 변수를 두지 않는다: " + ",".join(sdk_names))

    return LlmSettings(
        openai_api_key=keys[0],
        anthropic_api_key=keys[1],
        gemini_api_key=keys[2],
        models_file=optional("LLM_MODELS_FILE"),
        log_sink="jsonl" if sink == "jsonl" else "db" if sink == "db" else "memory",
        jsonl_path=jsonl_path,
        rpm=rpm,
        translation_run_max_usd=translation_run_max_usd,
        drafting_run_max_usd=drafting_run_max_usd,
        run_mode="live" if run_mode == "live" else "mock",
        run_max_usd=run_max_usd,
    )


def load_parser_settings(env: Mapping[str, str], problems: list[str]) -> tuple[str | None, int]:
    """PARSER_URL 과 PARSER_TIMEOUT_MS 를 읽는다. 둘 다 선택이다. 빈 값(빈칸뿐인 값 포함)은 「없음」으로 읽는다.

    주소가 있는데 http://·https:// 주소가 아니면 문제 목록에 한 줄. 어댑터는 환경을 읽지 않는다: 여기서 읽어 명시로
    넘긴다.
    """
    url: str | None = env.get("PARSER_URL", "").strip() or None
    if url is not None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            problems.append("PARSER_URL 의 꼴이 틀렸다. http://호스트:포트 나 https://호스트 여야 한다")
            url = None
    timeout_ms = Config.parser_timeout_ms
    timeout_text = env.get("PARSER_TIMEOUT_MS", "").strip()
    if timeout_text:
        if timeout_text.isascii() and timeout_text.isdecimal() and int(timeout_text) > 0:
            timeout_ms = int(timeout_text)
        else:
            problems.append("PARSER_TIMEOUT_MS 는 0보다 큰 정수여야 한다")
    return url, timeout_ms


# 저장소 설정이 읽는 키 아홉. compose.yaml 의 api-py 가 같은 이름으로 넘긴다(config/tests/test_env.py 가 견준다).
STORAGE_KEYS: tuple[str, ...] = (
    "S3_BUCKET",
    "S3_REGION",
    "S3_ENDPOINT",
    "S3_PUBLIC_ENDPOINT",
    "S3_FORCE_PATH_STYLE",
    "UPLOAD_URL_TTL_SECONDS",
    "MAX_UPLOAD_BYTES",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)


def load_storage_settings(env: Mapping[str, str], problems: list[str]) -> StorageSettings | None:
    """S3_* 와 올리기의 상한 둘, 접근 키 둘을 읽는다. 전부 선택이다. 빈 값(빈칸뿐인 값 포함)은 「없음」으로 읽는다.

    S3_BUCKET 이 없으면 나머지를 보지 않고 None 이다(저장소 없이 뜬다). 있으면 S3_REGION 이 있어야 한다.
    틀린 값은 문제 목록에 모은다. 어댑터는 환경을 읽지 않는다: 여기서 읽어 부르는 쪽이 명시로 넘긴다.
    """

    def optional(key: str) -> str | None:
        return env.get(key, "").strip() or None

    def address(key: str) -> str | None:
        value = optional(key)
        if value is not None:
            parts = urlsplit(value)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                problems.append(f"{key} 의 꼴이 틀렸다. http://호스트:포트 나 https://호스트 여야 한다")
                return None
        return value

    def positive(key: str, default: int) -> int:
        text = optional(key)
        if text is None:
            return default
        if text.isascii() and text.isdecimal() and int(text) > 0:
            return int(text)
        problems.append(f"{key} 는 0보다 큰 정수여야 한다")
        return default

    bucket = optional("S3_BUCKET")
    if bucket is None:
        return None
    region = optional("S3_REGION")
    if region is None:
        problems.append("S3_BUCKET 이 있으면 S3_REGION 이 있어야 한다")
    path_style_text = optional("S3_FORCE_PATH_STYLE") or "false"
    if path_style_text not in ("true", "false"):
        problems.append("S3_FORCE_PATH_STYLE 은 true 나 false 여야 한다")
    access_key_id = optional("AWS_ACCESS_KEY_ID")
    secret_access_key = optional("AWS_SECRET_ACCESS_KEY")
    if (access_key_id is None) != (secret_access_key is None):
        problems.append("AWS_ACCESS_KEY_ID 와 AWS_SECRET_ACCESS_KEY 는 둘 다 있거나 둘 다 없어야 한다")
    return StorageSettings(
        bucket=bucket,
        region=region or "",
        endpoint=address("S3_ENDPOINT"),
        public_endpoint=address("S3_PUBLIC_ENDPOINT"),
        force_path_style=path_style_text == "true",
        upload_url_ttl_seconds=positive("UPLOAD_URL_TTL_SECONDS", 300),
        max_upload_bytes=positive("MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )


# 브로커·일감 설정이 읽는 키 열둘. compose.yaml 의 api-py 가 같은 이름으로 넘긴다(config/tests/test_env.py 가 견준다).
# 자격 증명은 여기 없다: boto3 의 기본 순서가 찾는다(로컬은 저장소와 같은 AWS_ACCESS_KEY_ID 둘, 정식은 태스크 역할).
BROKER_KEYS: tuple[str, ...] = (
    "CELERY_BROKER_URL",
    "CELERY_BROKER_REGION",
    "CELERY_BROKER_SECURE",
    "CELERY_QUEUE_NAME",
    "CELERY_QUEUE_URL",
    "CELERY_VISIBILITY_TIMEOUT_SECONDS",
    "CELERY_TASK_SOFT_TIME_LIMIT_SECONDS",
    "CELERY_TASK_TIME_LIMIT_SECONDS",
    "JOB_LEASE_SECONDS",
    "JOB_MAX_ATTEMPTS",
    "JOB_RETRY_DELAY_SECONDS",
    "CELERY_WAIT_TIME_SECONDS",
)


def _positive(env: Mapping[str, str], problems: list[str], key: str, default: int) -> int:
    text = env.get(key, "").strip()
    if not text:
        return default
    if text.isascii() and text.isdecimal() and int(text) > 0:
        return int(text)
    problems.append(f"{key} 는 0보다 큰 정수여야 한다")
    return default


def load_job_settings(env: Mapping[str, str], problems: list[str]) -> JobSettings:
    """JOB_* 셋을 읽는다. 전부 선택이다. 빈 값(빈칸뿐인 값 포함)은 「없음」으로 읽는다."""
    return JobSettings(
        lease_s=_positive(env, problems, "JOB_LEASE_SECONDS", JobSettings.lease_s),
        max_attempts=_positive(env, problems, "JOB_MAX_ATTEMPTS", JobSettings.max_attempts),
        retry_delay_s=_positive(env, problems, "JOB_RETRY_DELAY_SECONDS", JobSettings.retry_delay_s),
    )


def load_broker_settings(env: Mapping[str, str], problems: list[str], *, lease_s: int) -> BrokerSettings | None:
    """CELERY_* 아홉을 읽는다. 전부 선택이다. 빈 값은 「없음」. CELERY_BROKER_URL 이 없으면 None 이다(브로커 없이 뜬다).

    긴 폴링(CELERY_WAIT_TIME_SECONDS)은 1~20 만 받는다(SQS 의 WaitTimeSeconds 는 0~20. 0 = 짧은 폴링은 받지 않는다).
    수 셋(visibility·시간 제한 둘)과 임대의 짝은 브로커가 없어도 본다:
        소프트 제한 < 하드 제한 < 임대(JOB_LEASE_SECONDS) < visibility
      (하드 제한에 걸려 죽은 태스크의 임대가 아직 살아 있지 않게, 큐의 재전달이 임대가 끝난 뒤에 오게.)
    브로커가 있으면: 주소는 `sqs://` 만 받는다. CELERY_BROKER_REGION 과 CELERY_QUEUE_URL 이 있어야 한다
      (큐 주소 없이는 Celery 가 큐를 스스로 만든다. 그 길을 두지 않는다).
    ★ 진짜 AWS 로 새는 꼴 둘을 막는다. 「호스트가 없다」는 urlsplit(주소).hostname is None 이다
      (`sqs://키:비밀@` 도 호스트가 없다. netloc 으로 보면 지나간다):
        ① 큐 주소의 호스트가 `.amazonaws.com` 으로 끝나지 않는데 브로커 주소에 호스트가 없다
        ② CELERY_BROKER_SECURE=false 인데 브로커 주소에 호스트가 없다
    """

    def optional(key: str) -> str | None:
        return env.get(key, "").strip() or None

    visibility_s = _positive(env, problems, "CELERY_VISIBILITY_TIMEOUT_SECONDS", BrokerSettings.visibility_timeout_s)
    soft_s = _positive(env, problems, "CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", BrokerSettings.task_soft_time_limit_s)
    hard_s = _positive(env, problems, "CELERY_TASK_TIME_LIMIT_SECONDS", BrokerSettings.task_time_limit_s)
    wait_s = _positive(env, problems, "CELERY_WAIT_TIME_SECONDS", BrokerSettings.wait_time_seconds)
    if wait_s > 20:
        problems.append("CELERY_WAIT_TIME_SECONDS 는 20 이하여야 한다(SQS 의 WaitTimeSeconds 는 0~20)")
    if soft_s >= hard_s:
        problems.append("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS 는 CELERY_TASK_TIME_LIMIT_SECONDS 보다 작아야 한다")
    if lease_s <= hard_s:
        problems.append("JOB_LEASE_SECONDS 는 CELERY_TASK_TIME_LIMIT_SECONDS 보다 커야 한다")
    if lease_s >= visibility_s:
        problems.append("JOB_LEASE_SECONDS 는 CELERY_VISIBILITY_TIMEOUT_SECONDS 보다 작아야 한다")

    url = optional("CELERY_BROKER_URL")
    if url is None:
        return None
    broker = urlsplit(url)
    if broker.scheme != "sqs":
        problems.append("CELERY_BROKER_URL 의 꼴이 틀렸다. sqs://호스트:포트 (로컬 흉내) 나 sqs:// 여야 한다")
    region = optional("CELERY_BROKER_REGION")
    if region is None:
        problems.append("CELERY_BROKER_URL 이 있으면 CELERY_BROKER_REGION 이 있어야 한다")
    secure_text = optional("CELERY_BROKER_SECURE") or "true"
    if secure_text not in ("true", "false"):
        problems.append("CELERY_BROKER_SECURE 는 true 나 false 여야 한다")
    queue_url = optional("CELERY_QUEUE_URL")
    queue_host: str | None = None
    if queue_url is None:
        problems.append("CELERY_BROKER_URL 이 있으면 CELERY_QUEUE_URL 이 있어야 한다")
    else:
        queue = urlsplit(queue_url)
        queue_host = queue.hostname
        if queue.scheme not in ("http", "https") or not queue_host:
            problems.append("CELERY_QUEUE_URL 의 꼴이 틀렸다. http(s)://호스트[:포트]/계정/큐 여야 한다")
            queue_host = None
    if broker.scheme == "sqs" and broker.hostname is None:
        if queue_host is not None and not queue_host.endswith(".amazonaws.com"):
            problems.append(
                "CELERY_QUEUE_URL 이 AWS 의 주소가 아닌데 CELERY_BROKER_URL 에 호스트가 없다"
                "(끝점은 브로커 주소의 호스트에서 온다. 호스트가 없으면 진짜 AWS 를 부른다)"
            )
        if secure_text == "false":
            problems.append(
                "CELERY_BROKER_SECURE 가 false 인데 CELERY_BROKER_URL 에 호스트가 없다"
                "(로컬 흉내라면 sqs://호스트:포트 로 적는다)"
            )
    return BrokerSettings(
        url=url,
        region=region or "",
        queue_name=optional("CELERY_QUEUE_NAME") or "esg-jobs",
        queue_url=queue_url or "",
        secure=secure_text != "false",
        visibility_timeout_s=visibility_s,
        task_soft_time_limit_s=soft_s,
        task_time_limit_s=hard_s,
        wait_time_seconds=wait_s,
    )


# 로컬에서만 쓰는 SESSION_SECRET 의 머리. .env.example 의 값이 이것으로 시작한다(compose.yaml 에는 기본값이 없다).
LOCAL_ONLY_PREFIX: Final = "local-only-"


def run_mode_notice(llm: LlmSettings) -> str | None:
    """live 면 기동 로그 한 줄(모드·키가 있는 공급사 이름·상한·싱크 — 키의 값·길이·앞머리 0). mock 이면 None."""
    if llm.run_mode != "live":
        return None
    keyed = (("openai", llm.openai_api_key), ("anthropic", llm.anthropic_api_key), ("gemini", llm.gemini_api_key))
    providers = ",".join(name for name, key in keyed if key is not None)
    return f"llm_run_mode mode=live providers={providers} max_usd={llm.run_max_usd} sink={llm.log_sink}"


def session_secret_warning(secret: str) -> str | None:
    """SESSION_SECRET 이 로컬 전용 값(누구나 아는 글자)이면 기동 때 낼 경고. 아니면 None.

    거절하지 않고 경고만 한다: 「로컬 밖」을 가르는 신호(배포 환경이 넣는 환경 변수 등)가 아직 없다
    (밴드 CU2 가 2026-10-16 에 찾음 — infra/terraform 은 SESSION_SECRET 을 넣지 않는다). 신호가 생기면 그때 거절로.
    """
    if not secret.startswith(LOCAL_ONLY_PREFIX):
        return None
    return (
        "★★★ 경고: SESSION_SECRET 이 로컬 전용 값(local-only-…)이다. "
        "저장소에 적힌 글자라 누구나 세션을 위조할 수 있다. "
        "로컬 밖에서는 무작위 32바이트 이상의 값을 넣는다. ★★★"
    )


def load_config(env: Mapping[str, str]) -> Config:
    problems: list[str] = []

    def required(key: str) -> str:
        value = env.get(key, "")
        if not value:
            problems.append(f"{key} 가 없다")
        return value

    database_url = required("DATABASE_URL_PY")
    # 환경 변수는 한 줄이라, PEM 의 줄바꿈을 글자 둘(\n)로 적어 넣는다. 여기서 진짜 줄바꿈으로 되돌린다.
    public_key = required("EDK_JWT_PUBLIC_KEY").replace("\\n", "\n")
    audience = required("EDK_JWT_AUDIENCE")
    issuer = required("EDK_JWT_ISSUER")
    session_secret = required("SESSION_SECRET")
    ttl_text = required("SESSION_TTL_SECONDS")

    if session_secret and len(session_secret.encode()) < 32:
        problems.append("SESSION_SECRET 이 32바이트보다 짧다(HS256 서명의 비밀은 32바이트 이상이어야 한다)")
    ttl = int(ttl_text) if ttl_text.isdecimal() else 0
    if ttl_text and ttl <= 0:
        problems.append("SESSION_TTL_SECONDS 는 0보다 큰 정수여야 한다")

    llm = load_llm_settings(env, problems)
    parser_url, parser_timeout_ms = load_parser_settings(env, problems)
    storage = load_storage_settings(env, problems)
    jobs = load_job_settings(env, problems)
    broker = load_broker_settings(env, problems, lease_s=jobs.lease_s)
    scope3_runs_text = env.get("INVENTORY_SCOPE3_RUNS_ENABLED", "").strip() or "false"
    if scope3_runs_text not in ("true", "false"):
        problems.append("INVENTORY_SCOPE3_RUNS_ENABLED 는 true 나 false 여야 한다")
    g1_runs_text = env.get("GREENWASH_G1_RUNS_ENABLED", "").strip() or "false"
    if g1_runs_text not in ("true", "false"):
        problems.append("GREENWASH_G1_RUNS_ENABLED 는 true 나 false 여야 한다")

    database: DbTarget | None = None
    if database_url:
        try:
            database = parse_database_url(database_url, key="DATABASE_URL_PY")
        except ConfigError as err:
            problems.append(str(err))

    if problems or database is None:
        raise ConfigError("설정이 모자라다: " + " / ".join(problems))
    warning = session_secret_warning(session_secret)
    if warning is not None:
        print(warning, file=sys.stderr)  # 로그 설정 전에 불리는 자리라(settings/base.py) stderr 에 바로 쓴다
    notice = run_mode_notice(llm)
    if notice is not None:
        print(notice, file=sys.stderr)  # 위와 같은 까닭으로 stderr. 실호출이 켜졌다는 것을 기동 기록에 남긴다(LV1)
    sdk_warning = sdk_env_warning(env) if llm.run_mode == "mock" else None
    if sdk_warning is not None:
        print(sdk_warning, file=sys.stderr)  # 위와 같은 까닭으로 stderr(LH1 Q3 — mock 은 멈추지 않고 알리기만)
    return Config(
        database=database,
        edk_public_key_pem=public_key,
        edk_audience=audience,
        edk_issuer=issuer,
        session_secret=session_secret,
        session_ttl_seconds=ttl,
        llm=llm,
        parser_url=parser_url,
        parser_timeout_ms=parser_timeout_ms,
        storage=storage,
        broker=broker,
        jobs=jobs,
        inventory_scope3_runs_enabled=scope3_runs_text == "true",
        greenwash_g1_runs_enabled=g1_runs_text == "true",
    )
