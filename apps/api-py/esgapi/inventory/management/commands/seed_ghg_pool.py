"""온실가스 인덱스 풀·시설별 배출계수 풀을 씨앗 파일로 채운다(밴드 K1b-2a ④ — 결정 MARC-ENT-463·469 3, 감독 판단 2).

    python manage.py seed_ghg_pool [--gwp-set <id>] [--dry-run] [--plan <json>]

  --gwp-set   GWP 세트(inventory/data/gwp-sets.json 의 id). 기본 kr-ets-decree-annex2 [추정 — 근거 법 체계가 계수 원천과
              같음, 확인 안 됨. 감독 판단 2]. 행마다 관리자가 고칠 수 있다
  --dry-run   한 트랜잭션을 되돌린다(셈만 찍는다)
  --plan      씨앗 파일. 기본 패키지의 inventory/data/ghg-pool-seed.json

범위는 engine_1 이 셈하는 것(Scope 1 고정연소 · Scope 2 구매 전력 — 감독 판단 2). 나머지는 관리자 입력.
나무는 연료 = 배출활동, 그 아래 설비 종류 잎(결정 MARC-ENT-676 — S12S1). 옛 씨앗(연료 = 잎 코드)은 지우지 않는다 —
먼저 retire_ghg_seed 로 세고 지운 뒤 이 명령을 돌린다(씨앗 파일의 retired 칸은 이 명령이 읽지 않는다).
**멱등**: 씨앗 열쇠가 있는 노드·계수는 건드리지 않는다(관리자가 고친 것을 덮지 않는다). 값은 reference 낱줄의
value_raw 와 gwp-sets.json 에서만(수치를 지어내지 않는다 — 운영 규칙 4). reference 는 읽기만 한다 — 먼저
import_factors 로 적재본이 있어야 한다(없는 낱줄은 그 묶음을 건너뛰고 끝에 까닭을 찍는다). 회사 데이터 0.
일은 actions.seed_pool 하나가 한다.
"""

import json
from argparse import ArgumentParser
from importlib import resources
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.utils.ghg_pool import Forbidden, Invalid

DEFAULT_GWP_SET = "kr-ets-decree-annex2"
PACKAGED_PLAN = "ghg-pool-seed.json"


class Command(BaseCommand):
    help = "온실가스 풀(공통)을 씨앗 파일로 채운다. 멱등 — 이미 있는 씨앗 행은 건드리지 않는다"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--gwp-set", default=DEFAULT_GWP_SET, help=f"GWP 세트 id(기본 {DEFAULT_GWP_SET})")
        parser.add_argument("--dry-run", action="store_true", help="한 트랜잭션을 되돌린다")
        parser.add_argument("--plan", help="씨앗 파일(json)의 경로. 생략하면 패키지의 사본")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["plan"]:
            text = Path(options["plan"]).read_text(encoding="utf-8")
        else:
            text = resources.files("esgapi.inventory").joinpath("data", PACKAGED_PLAN).read_text(encoding="utf-8")
        plan: dict[str, Any] = json.loads(text)
        report = actions.seed_pool(
            actor_kind="admin", plan=plan, gwp_set_id=options["gwp_set"], dry_run=options["dry_run"]
        )
        if isinstance(report, Invalid | Forbidden):
            raise CommandError(f"씨앗을 넣지 못했다: {report!r}")
        made, existing = report.made, report.existing
        self.stdout.write(
            f"{'(dry-run — 되돌림) ' if options['dry_run'] else ''}GWP 세트 {options['gwp_set']} · "
            f"노드 만듦 {made['node']}·있음 {existing['node']} · "
            f"잎 만듦 {made['facility']}·있음 {existing['facility']} · "
            f"계수 만듦 {made['factor']}·있음 {existing['factor']} · 시설 코드 만듦 {made['code']} · "
            f"건너뜀 {len(report.skipped)}"
        )
        for key, reason in report.skipped:
            self.stdout.write(f"  건너뜀 {key}: {reason}")
