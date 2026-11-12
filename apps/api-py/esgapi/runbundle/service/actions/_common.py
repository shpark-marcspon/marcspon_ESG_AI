"""넣기·내보내기가 같이 쓰는 조각(DB 0 — 모델 칸·마이그레이션 그래프는 앱 등록부·디스크에서, 회사 있음은 selector 로).

    DEFAULT_MAX_BYTES      묶음의 풀린 크기 합 상한 하나 — 넣기 기본(import_runs --max-bytes)이자 내보내기의 합 상한
                           (HD1 R1 — 내보내기가 넣기 기본으로 못 넣는 묶음을 짓지 않게. 새 숫자 0: 옛 import_.py 상수)
    model_columns()        묶음 표 → 이 코드의 모델 칸 → 필수인가
    migration_graph()      디스크의 마이그레이션 그래프(앱별 잎, 마디 전부)
    require_company(id)    그 회사가 있어야 한다(없으면 Refused)
    carrier_of(reg, m)     그 모듈의 carrier(없으면 Refused — 닫힌 기본)

HD1 R5 가 export.py 에서 옮겼다(본문 바이트 그대로) — 넣기가 내보내기 파일을 import 하지 않게.
"""

from django.apps import apps
from django.db.migrations.loader import MigrationLoader
from django.db.models import Field

from esgapi.core.flows.carriers import CarrierRegistry, RunCarrier
from esgapi.organization.service.selectors.organization import find_company_by_id
from esgapi.runbundle.calc.bundle import TABLES, Refused
from esgapi.runbundle.calc.gate import check_carriers

DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 풀린 크기 합의 상한(어림 — 문서 50MiB 상한 × 수십)


def _required(field: "Field[object, object]") -> bool:
    automatic = getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    return not (field.null or field.has_default() or field.primary_key or automatic)


def model_columns() -> dict[str, dict[str, bool]]:
    """묶음 표 → 이 코드의 모델 칸(attname) → 필수인가. 앱 등록부의 메타만 읽는다(DB 0, 모델 import 0)."""
    found: dict[str, dict[str, bool]] = {}
    for model in apps.get_models():
        table = model._meta.db_table
        if table in TABLES:
            found[table] = {field.attname: _required(field) for field in model._meta.concrete_fields}
    return found


def migration_graph() -> tuple[dict[str, list[str]], frozenset[tuple[str, str]]]:
    """디스크의 마이그레이션 그래프(연결 None — DB 를 읽지 않는다): (앱별 잎, 마디 전부)."""
    graph = MigrationLoader(None, ignore_no_migrations=True).graph
    leaves: dict[str, list[str]] = {}
    for app, name in sorted(graph.leaf_nodes()):
        leaves.setdefault(app, []).append(name)
    return leaves, frozenset(graph.nodes)


def require_company(company_id: int) -> None:
    """그 회사가 있어야 한다(활성이든 아니든 — 운영자 명령). 없으면 Refused. 넣기(import_)도 이 함수를 부른다."""
    if find_company_by_id(company_id) is None:
        raise Refused("그런 회사가 없다")


def carrier_of(carriers: CarrierRegistry, module: str) -> RunCarrier:
    """그 모듈의 carrier. 없으면 Refused(닫힌 기본 — 그 모듈의 실행은 싣지도 넣지도 못한다)."""
    check_carriers([module], carriers)
    carrier = carriers.get(module)
    if carrier is None:
        raise Refused(f"모듈 {module} 에 carrier 가 없다")
    return carrier
