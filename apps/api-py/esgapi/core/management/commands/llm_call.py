"""호출 층을 끝까지 한 번 돌려 본다:  python manage.py llm_call --prompt core/hello@1 --var name=김 --route mock …

    --dry-run            공급사를 부르지 않고 조립된 요청과 어림 토큰·비용만 낸다(키가 필요 없다)
    --route mock         모의 공급사를 부른다(키가 필요 없다). --mock-text 로 답을 심는다. 안 심으면 provider_error 다
    --route <실제 경로>   실제 공급사를 부른다. ★ 돈이 든다. --limit-usd 와 그 공급사의 키(LLM_*_API_KEY)가 있어야 한다.
                         SDK 가 스스로 읽는 환경 변수(OPENAI_BASE_URL 등 — env.py 의 sdk_env_names)가 있으면 2(LH2)

표준 출력에 JSON 하나를 낸다(dry-run 은 보고, 아니면 결과). 종료 코드: 성공 0, 성공이 아닌 결과 1, 쓰는 법이 틀렸으면 2.
기록이 가는 곳은 환경 변수(LLM_LOG_SINK, LLM_JSONL_PATH)를 따르고 --sink 로 바꿀 수 있다.

기록이 DB 로 갈 때(--sink db 또는 LLM_LOG_SINK=db):
    --tenant 를 명시해야 한다(없으면 2). 기본 꼬리표 cli 로 DB 에 쓰지 않는다. 명령은 트랜잭션을 열지 않는다: 싱크가
    줄마다 스스로 짧은 트랜잭션을 열어 커밋한다(LLM 호출은 트랜잭션 밖에서 한다 — 연결을 쥔 채 기다리지 않는다).
    행의 회사는 꼬리표(= --tenant, 회사 id 의 십진 숫자 글자)의 것이다(core/llm/sink_db.py).
    꼴이 틀리면 갈래 no_tenant 로 1. 결과가 성공이 아니어도 기록 줄은 남는다.
    --store-bodies 와 같이 쓰지 못한다(2). 본문은 DB 에 두지 않는다.
    기록이 쓰이지 않았으면(갈래가 written 이 아니면) stderr 에 갈래 이름을 한 줄 내고 1 로 끝난다.
    --dry-run 은 기록을 쓰지 않으므로 --tenant 가 없어도 된다.
    ★ 무효 조건: --tenant 에 없는 회사 id 를 줘도 행이 남는다(표의 company_id 는 외래 키가 아니다).
esg-lab CLI 의 `call` 만 옮겼다(`probe` 는 옮기지 않았다).
"""

import dataclasses
import json
import os
import sys
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from esgapi.config.env import sdk_env_names
from esgapi.core.conf import app_config
from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import DEFAULT_TIMEOUT_MS, CallRequest, LlmClient
from esgapi.core.llm.config import load_config, resolve_route
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, PromptError
from esgapi.core.llm.log import CallLogSink
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.redact import redact_keys
from esgapi.core.llm.setup import build_client, config_sources, make_sink
from esgapi.core.llm.types import Scope, Success, Tags, result_json
from esgapi.core.resources.llm import MOCK_PROVIDERS

USAGE_ERROR = 2


def parse_vars(pairs: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep or not name:
            raise CommandError(f"--var 는 이름=값 꼴이어야 한다: {pair}", returncode=USAGE_ERROR)
        values[name] = value
    return values


def require_limit_usd(raw: str | None) -> float:
    """실제 호출의 누적 비용 상한. 실제 공급사를 부르는 실행은 상한 없이 시작하지 않는다."""
    if raw is None:
        raise LiveSetupError("실제 공급사 호출에는 --limit-usd <상한 USD> 가 필요하다")
    try:
        limit = float(raw)
    except ValueError:
        limit = 0.0
    if not limit > 0 or limit == float("inf"):
        raise LiveSetupError(f"--limit-usd 는 양수여야 한다: {raw}")
    return limit


class Command(BaseCommand):
    help = "LLM 호출 층을 한 번 돌린다(모의 공급사·dry-run 은 키 없이). 실제 경로는 돈이 든다"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--prompt", required=True, help="모듈/이름@판  예: core/hello@1")
        parser.add_argument("--route", required=True, help="모델 설정의 경로 이름  예: mock, light")
        parser.add_argument(
            "--var", action="append", default=[], metavar="이름=값", help="템플릿 변수. 여러 번 줄 수 있다"
        )
        parser.add_argument(
            "--tenant", help="기록의 꼬리표(회사 id). 기본 cli. 기록이 DB 로 가면 필수이고 그 회사의 행으로 쓰인다"
        )
        parser.add_argument("--module", default="cli", help="기록의 꼬리표(모듈). 기본 cli")
        parser.add_argument("--dry-run", action="store_true", help="공급사를 부르지 않는다")
        parser.add_argument("--mock-text", help="모의 공급사가 돌려줄 답")
        parser.add_argument(
            "--sink", choices=["memory", "jsonl", "db"], help="기록이 가는 곳. 주지 않으면 LLM_LOG_SINK"
        )
        parser.add_argument("--limit-usd", help="누적 비용 상한(USD). 실제 공급사를 부를 때 필수")
        parser.add_argument("--store-bodies", action="store_true", help="기록에 요청 본문과 응답 글자를 그대로 남긴다")
        parser.add_argument("--max-output-tokens", type=int)
        parser.add_argument("--timeout-ms", type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            code = self.run(options)
        except (LiveSetupError, LlmConfigError, PromptError) as error:
            # 쓰는 법·설정의 잘못. 공급사는 부르지 않았다.
            raise CommandError(f"{type(error).__name__}: {redact_keys(str(error))}", returncode=USAGE_ERROR) from error
        if code != 0:
            sys.exit(code)

    def run(self, options: dict[str, Any]) -> int:
        settings = app_config().llm
        sink: str | None = options["sink"]
        if sink is not None:
            settings = dataclasses.replace(settings, log_sink=sink)
        route: str = options["route"]
        dry_run: bool = options["dry_run"]

        # 경로의 모델이 전부 모의 공급사의 것인가. 아니면 실제 공급사가 끼어 있다.
        models = resolve_route(load_config(config_sources(settings, mock=True)), route)
        live = not dry_run and any(model.provider not in MOCK_PROVIDERS for model in models)
        # 실공급사를 부를 때 SDK 가 스스로 읽는 환경 변수(주소·머리)가 있으면 키가 그쪽으로 갈 수 있다 — 막는다(LH2 Q2).
        # 키 파일을 source 한 셸도 여기서 멈춘다. 이름만 낸다(값 0). dry-run·모의 경로는 그대로.
        sdk_names = sdk_env_names(os.environ) if live else []
        if sdk_names:
            raise CommandError(
                f"실공급사 경로를 부를 때 SDK 환경 변수를 두지 않는다: {', '.join(sdk_names)} "
                f"— env -u <이름> 으로 지운다",
                returncode=USAGE_ERROR,
            )
        limits = [BudgetLimit(scope=Scope(), limit_usd=require_limit_usd(options["limit_usd"]))] if live else []

        tenant: str | None = options["tenant"]
        to_db = settings.log_sink == "db" and not dry_run
        if to_db and tenant is None:
            raise CommandError(
                "기록이 DB 로 갈 때는 --tenant <회사 id> 를 명시해야 한다(기본 꼬리표 cli 로 DB 에 쓰지 않는다)",
                returncode=USAGE_ERROR,
            )

        log: CallLogSink = make_sink(settings)
        client: LlmClient = build_client(
            settings,
            limits=limits,
            mock=True,
            assemble_only=dry_run,
            sink=log,
            store_bodies=options["store_bodies"],
        )
        request = CallRequest(
            prompt=options["prompt"],
            vars=parse_vars(options["var"]),
            route=route,
            tags=Tags(tenant=tenant or "cli", module=options["module"]),
            max_output_tokens=options["max_output_tokens"],
            timeout_ms=DEFAULT_TIMEOUT_MS if options["timeout_ms"] is None else options["timeout_ms"],
        )
        if dry_run:
            self.emit(client.dry_run(request).to_json())
            return 0
        mock_text: str | None = options["mock_text"]
        if mock_text is not None:
            mock = client.provider("mock")
            if isinstance(mock, MockProvider):
                mock.enqueue_text(mock_text)
        # 트랜잭션 밖에서 부른다. DB 싱크는 줄마다 스스로 커밋한다(core/llm/sink_db.py).
        result = client.call(request)
        self.emit(result_json(result, result.data if isinstance(result, Success) else None))
        code = 0 if isinstance(result, Success) else 1
        # DB 싱크만 갈래를 쥔다(outcomes). 쓰이지 않은 줄을 조용히 지나가지 않는다.
        for outcome in getattr(log, "outcomes", ()):
            if outcome.kind != "written":
                self.stderr.write(f"호출 기록이 DB 에 온전히 남지 않았다: {outcome.kind}")
                code = 1
        return code

    def emit(self, value: dict[str, object]) -> None:
        self.stdout.write(json.dumps(value, ensure_ascii=False, indent=2))
