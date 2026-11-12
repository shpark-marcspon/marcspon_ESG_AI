"""옛 씨앗(연료 = 잎 코드)의 노드를 세고, 셈이 전부 0 일 때만 지운다(밴드 S12S1 — 결정 MARC-ENT-644·676).

    python manage.py retire_ghg_seed [--apply] [--plan <json>]

  (기본)      셈만 — 쓰기 0. 끝 줄 RETIRE=nothing(지울 것 없음)|ready(지울 수 있음)|blocked(셈이 있음)
              · 거절(계획에 retired 없음·권한·없는 노드)은 RETIRE=refused <타입>
  --apply     같은 트랜잭션에서 잠그고 다시 센 뒤 전부 0 이면 삭제 표시로 지운다 → RETIRE=done.
              blocked 면 지움 0 으로 멈춘다(CommandError). 두 번째 --apply 는 RETIRE=nothing
  --plan      씨앗 파일. 기본 패키지의 inventory/data/ghg-pool-seed.json — 그 retired 칸(옛 씨앗 노드 열쇠)만 읽는다

셈은 수만 찍는다(회사 이름·id 0): 회사 선택이 고른 옛 잎 · 판을 잡았거나 입력 행이 덮어쓴 옛 계수 · 옛 노드 아래 씨앗 밖
자식 · 옛 잎의 씨앗 아닌 계수 · 고친 씨앗 계수 · 사업장 자산/시설이 쓰는 지울 옛 코드. 하나라도 1 이상이면 blocked —
지움 0, 그 수를 들고 사용자에게 간다(MARC-ENT-676).
지울 옛 코드 = 옛 잎(삭제 표시 포함)의 살아 있는 시설 코드 가운데 다른 살아 있는 잎(새 씨앗·관리자가 만든 잎)이 안 쓰는
것. 다른 잎이 쓰는 코드는 남기고(「다른 잎이 씀 n」) 상태는 바꾸지 않는다 — 그 코드는 지우지 않으니 사업장 행이 고를
잎을 잃지 않는다. 그래서 사업장 셈은 지울 옛 코드에 대해서만 한다(S12S1 덧 2 · 감독 판단).
지우기는 있는 길(actions.delete_nodes·organization 의 delete_codes — 삭제 표시)뿐이다. 새 씨앗(seed_ghg_pool)은 이
명령 뒤에 돌린다. 일은 actions.retire_seed 하나가 하고, 사업장 판정(codes_on_site_facilities — 코드 id 만)은 이 명령이
organization 에서 넘긴다.
"""

import json
from argparse import ArgumentParser
from importlib import resources
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.utils.ghg_pool import HasChildren, InUse
from esgapi.organization.service.selectors.facility_codes import codes_on_site_facilities
from esgapi.organization.service.services.branches import InUse as CodesInUse

PACKAGED_PLAN = "ghg-pool-seed.json"
USED = (InUse, HasChildren, CodesInUse)  # 쓰임이 막은 거절 — RETIRE=blocked
WHY = (
    ("leaves_in_use", "회사 선택이 고른 옛 잎(숨김 포함)"),
    ("factors_in_use", "회사가 판을 잡았거나 입력 행이 덮어쓴 옛 계수"),
    ("foreign_children", "옛 노드 아래 씨앗 밖 자식"),
    ("foreign_factors", "옛 잎의 씨앗 아닌 계수"),
    ("edited_factors", "고친 씨앗 계수(판 2 이상)"),
    ("codes_on_sites", "사업장 자산/시설이 쓰는 지울 옛 코드"),
)


class Command(BaseCommand):
    help = "옛 씨앗 노드를 센다. --apply 면 셈이 전부 0 일 때만 삭제 표시로 지운다"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--apply", action="store_true", help="셈이 전부 0 이면 지운다(기본은 셈만)")
        parser.add_argument("--plan", help="씨앗 파일(json)의 경로. 생략하면 패키지의 사본")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["plan"]:
            text = Path(options["plan"]).read_text(encoding="utf-8")
        else:
            text = resources.files("esgapi.inventory").joinpath("data", PACKAGED_PLAN).read_text(encoding="utf-8")
        plan: dict[str, Any] = json.loads(text)
        report = actions.retire_seed(
            actor_kind="admin", plan=plan, apply=options["apply"], codes_on_sites=codes_on_site_facilities
        )
        if not isinstance(report, actions.RetireReport):
            # 지우는 중 쓰임이 새로 걸림(경합 — 409 꼴)만 blocked, 그 밖의 거절(계획·권한·없음)은 refused <타입>
            used = isinstance(report, USED)
            self.stdout.write("RETIRE=blocked" if used else f"RETIRE=refused {type(report).__name__}")
            raise CommandError(f"지우지 못했다(지움 0 — 되돌림): {type(report).__name__}")
        self.stdout.write(
            f"옛 씨앗 노드 살아 있음 {report.alive}·지움/없음 {report.gone} · 쓰이는 잎 {report.leaves_in_use} · "
            f"잡힌 계수 {report.factors_in_use} · 씨앗 밖 자식 {report.foreign_children} · "
            f"씨앗 아닌 계수 {report.foreign_factors} · 고친 씨앗 계수 {report.edited_factors} · "
            f"사업장이 쓰는 옛 코드 {report.codes_on_sites} · "
            f"옛 코드 지울 {report.codes}·다른 잎이 씀 {report.codes_on_leaves}"
        )
        for name, why in WHY:
            if getattr(report, name):
                self.stdout.write(f"  막음 {why} {getattr(report, name)}")
        if report.state == "done":
            self.stdout.write(f"  지움 노드 {report.deleted_nodes} · 코드 {report.deleted_codes}")
        self.stdout.write(f"RETIRE={report.state}")
        if options["apply"] and report.state == "blocked":
            raise CommandError("셈이 있어 지우지 않았다(지움 0) — 수를 들고 사용자에게(MARC-ENT-676)")
