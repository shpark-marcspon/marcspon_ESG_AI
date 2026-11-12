"""격리의 받침 ④: 제품 코드가 회사 범위 표를 for_company 로만 열고, 그 밖의 길(unscoped·숨은 매니저·날 SQL·생성자·
연결에 테넌트 싣기)을 쓰지 않는가. 소스를 AST 와 글자로 읽는다(DB 없이).

제품 = esgapi/**/*.py 가운데 경로에 tests·migrations 마디가 없는 것. 범위 모델은 등록부에서 읽는다(esgapi. 모듈이고
concrete_fields 에 attname company_id 가 있거나 뿌리인 모델. core 는 organization·user 를 import 하지
않는다 — .importlinter 「가」). 테넌트 바닥(tenant_id 칸의 모델·for_tenant)은 K1u-b 가 지웠다 — 0 을 단언한다.
selectors·services 의 조건 꼴(인자가 이름 company_id 인가)은 core/tests/test_selector_scope.py 가 보고 여기서는 두 번
적지 않는다. 경로 표기는 esgapi/ 아래의 상대 경로.
날 SQL 의 허용 목록에 core/isolation/foreign_keys.py·core/isolation/grants.py 가 있다:
RunSQL 조각을 만드는 함수만 있고 마이그레이션만 import 한다
(실행 중의 요청·워커는 안 부른다). .execute( 무늬가 무는 자리는 지금 config/api.py 의 cursor.execute 하나뿐이다.

★ 무효 조건: 글자의 꼴만 본다. `<범위 모델 이름>.` 으로 시작하지 않는 길(다른 이름에 담은 모델, getattr, type(row),
  관계 매니저 document.jobs)은 이름으로는 못 본다 — 기본 매니저가 던지는 것(test_managers.py)이 받친다.
  날 SQL 은 무늬(.raw·.extra·.cursor·.execute·.executemany·RawSQL·RunSQL·psycopg.connect·connections[…])로만
  본다: 다른 이름으로 들여온 드라이버나 문자열로 부른 함수는 지나간다. 생성자는 `<Row>(…)` 꼴만 — 이름을 바꿔 담은
  클래스의 생성자는 지나간다(DB 의 같은 회사 외래 키가 받침 ⑤). 연결에 테넌트를 싣는 글자는 원문 전체(주석·
  docstring 포함)에서 세므로 그 낱말을 설명하는 글도 빨개진다(뺀 파일 0 — 옛 RLS 조각은 K1u-b 가 지웠다).
"""

import ast
from collections.abc import Collection
from pathlib import Path
from typing import TypeGuard

from django.apps import apps
from django.db import models

from esgapi.core.isolation.managers import (
    CompanyRootManager,
    CompanyRootModel,
    CompanyScopedManager,
)

ESGAPI = Path(__file__).resolve().parents[3]
UNSCOPED_ALLOWED: frozenset[str] = frozenset()
# config/api.py: readyz 의 SELECT 1. core/isolation/foreign_keys.py·core/isolation/grants.py: 마이그레이션만 import
# 하는 RunSQL 조각(요청·워커에서는 안 돈다)
# runbundle/service/actions/_pg.py: 묶음 넣기의 advisory 잠금·내보내기의 REPEATABLE READ 스냅숏 두 문장
# (RX1a, 매개 바인딩)
RAW_SQL_ALLOWED: frozenset[str] = frozenset(
    {
        "config/api.py",
        "core/isolation/foreign_keys.py",
        "core/isolation/grants.py",
        "runbundle/service/actions/_pg.py",
    }
)
# 위 허용 가운데 마이그레이션 조각 파일: 제품 코드(요청·워커·명령)가 import 하지 않고 마이그레이션만 import 한다.
MIGRATION_PIECES: dict[str, str] = {
    "core/isolation/foreign_keys.py": "esgapi.core.isolation.foreign_keys",
    "core/isolation/grants.py": "esgapi.core.isolation.grants",
}
# 회사 뿌리의 매니저를 꺼내는 길(<모델>.root_manager())을 부를 수 있는 자리. 그 뒤의 register·_entrance·by_subdomain 은
# 입구 허용 목록을 비껴가므로, 꺼내는 자리 자체를 뿌리 모델의 정의(입구의 몸)와 바닥으로 묶는다.
ROOT_MANAGER_ALLOWED: frozenset[str] = frozenset({"organization/models.py", "core/isolation/managers.py"})
# 회사 뿌리의 이름 붙은 입구와 그것을 부를 수 있는 자리(K1u-a). 찾기 하나·만들기 하나 + 「하나뿐인 회사」 하나(K2c —
# 회사 표의 앞 두 행까지만 읽는다. 운영 관리자의 회사 고르기 find_sole_company 의 자리).
ENTRANCES: dict[str, frozenset[str]] = {
    "by_subdomain": frozenset({"organization/service/selectors/organization.py"}),
    "register": frozenset({"organization/management/commands/seed_company.py"}),
    "sole_candidates": frozenset({"organization/service/selectors/organization.py"}),
}
# 운영 관리자의 회사 고르기 포트 둘(K2c): organization selectors 의 함수를 꽂는 자리는 user 의 apis 하나다.
COMPANY_CHOOSERS: dict[str, frozenset[str]] = {
    # RX1a: 운영자 명령(export_runs·import_runs)의 회사 있음 — 발주서 §1-1, runbundle 의 require_company 한 자리
    "find_company_by_id": frozenset({"user/service/apis/users.py", "runbundle/service/actions/_common.py"}),
    "find_sole_company": frozenset(
        {"user/service/apis/users.py", "user/service/apis/user.py"}
    ),  # UA1: 회사 칸 없는 로그인
}
# 사용자 표의 이름 붙은 입구(K2a)와 그것을 부를 수 있는 자리. 운영 관리자(kind admin, 회사 없음)를 여는 셋과
# refresh 행(RefreshToken)을 여는 넷. 입구의 몸(user/models.py)은 뺀다(by_subdomain 의 organization/models.py 꼴).
USER_ENTRANCES: dict[tuple[str, str], frozenset[str]] = {
    ("User", "admin_by_username"): frozenset({"user/service/selectors/user.py"}),
    ("User", "admin_by_id"): frozenset({"user/service/selectors/user.py"}),
    ("User", "register_admin"): frozenset({"user/service/services/user.py"}),
    ("RefreshToken", "by_jti"): frozenset({"user/service/selectors/user.py"}),
    ("RefreshToken", "of_family"): frozenset({"user/service/services/login.py"}),
    ("RefreshToken", "of_user"): frozenset({"user/service/actions/password.py", "user/service/actions/account.py"}),
    ("RefreshToken", "issue"): frozenset({"user/service/services/login.py"}),
}
USER_MODELS = "user/models.py"
# 감사 기록의 이름 붙은 입구(AU1a, 처분 ⑪): 회사 칸이 NULL 인 줄(운영 관리자 쪽)을 여는 operator_rows 와 그것을 부를 수
# 있는 자리 — 읽기(selectors)와 쓰기(services) 하나씩. 입구의 몸(core/models.py)은 뺀다.
AUDIT_ENTRANCES: dict[tuple[str, str], frozenset[str]] = {
    ("AuditEventRow", "operator_rows"): frozenset(
        {"core/service/selectors/audit.py", "core/service/services/audit.py"}
    ),
}
AUDIT_MODELS = "core/models.py"
# 모델의 이름 붙은 입구(모듈 공용 표 — K1b-2b ④, 결정 MARC-ENT-487 · 플랫폼-서버 dc·e7 허락 2026-10-29):
# (모델, 입구 이름) → 부를 수 있는 파일 집합. 몸은 그 모델 파일(MODEL_ENTRANCE_FILES)에 있고 거기는 셈에서 뺀다.
# 첫 줄 inventory: 회사 넘는 사용 중 읽기 둘(풀 id 집합만 — 회사 id·행 0)은 인덱스 선택의 selectors 하나에서만.
MODEL_ENTRANCES: dict[tuple[str, str], frozenset[str]] = {
    ("CompanyIndexSelection", "used_node_ids"): frozenset({"inventory/service/selectors/index_selection.py"}),
    ("CompanyIndexSelection", "used_factor_ids"): frozenset({"inventory/service/selectors/index_selection.py"}),
    # S12a-2(H14 — e7 허락): 입력 행이 덮어쓴 풀 계수(행 칸 하나 — 히스토리는 막지 않는다, 감독 27 길 i)
    ("InventoryEntryRow", "used_factor_ids"): frozenset({"inventory/service/selectors/index_selection.py"}),
    # S12S1 Q9 — 7a 허락(S12S1 Q9 +1): 옛 씨앗 코드 지우기의 사업장 쓰임(코드 id 만)
    ("SiteFacility", "used_code_ids"): frozenset({"organization/service/selectors/facility_codes.py"}),
}
MODEL_ENTRANCE_FILES: dict[str, str] = {
    "CompanyIndexSelection": "inventory/models.py",
    "InventoryEntryRow": "inventory/models.py",
    "SiteFacility": "organization/models.py",  # S12S1 Q9 — 7a 허락(S12S1 Q9 +1)
}
# 입구가 내도 되는 칸(공통 풀 id) — 회사 칸·행 칸 0.
POOL_ID_COLUMNS: frozenset[str] = frozenset(
    {"facility_node_id", "factor_version__factor_id", "facility_code_id"}  # S12S1 Q9 — 7a 허락(S12S1 Q9 +1)
)
CONSTRUCTOR_ALLOWED: frozenset[str] = frozenset(
    {
        "core/llm/sink_db.py",  # row_from_record
        "inventory/service/services/scope3_edits.py",  # S3K2b-1: Scope3RowEdit 묶어 넣기 — 7a 허락
        "runs/service/services/runs.py",  # RM1b 635-2 — 7a 허락(segments_planned 의 RunSegmentRow 묶어 넣기)
        "runs/service/actions/runs.py",  # RM1c — 7a 허락(create_run 의 옮긴 구획 RunSegmentRow 묶어 넣기)
    }
)
CONSTRUCTOR_HITS: dict[str, int] = {
    "core/llm/sink_db.py": 1,
    "inventory/service/services/scope3_edits.py": 1,  # S3K2b-2: 계수 사건도 같은 자리 — 561 L2
    "runs/service/services/runs.py": 1,  # RM1b 635-2 — 7a 허락
    "runs/service/actions/runs.py": 1,  # RM1c — 7a 허락
}
TENANT_LOADING_EXEMPT: frozenset[str] = frozenset()  # 옛 마이그레이션의 문면(rls.py)은 K1u-b 가 지웠다
TENANT_LOADING_WORDS = ("set_config", "current_setting", "app.tenant_id")
RAW_SQL_CALLS = {"raw", "extra", "cursor", "execute", "executemany"}
RAW_SQL_NAMES = {"RawSQL", "RunSQL"}
HIDDEN_MANAGERS = {"_default_manager", "_base_manager"}


def scoped_models() -> list[type[models.Model]]:
    """테넌트 바닥의 모델(tenant_id 칸). K1u-b 뒤 0 이어야 한다."""
    found = [
        model
        for model in apps.get_models()
        if model.__module__.startswith("esgapi.")
        and "tenant_id" in {field.attname for field in model._meta.concrete_fields}
    ]
    return sorted(found, key=lambda model: model.__name__)


def company_models() -> list[type[models.Model]]:
    """회사 바닥의 모델: 뿌리(CompanyRootModel) 이거나 company_id 칸이 있는 모델."""
    found = [
        model
        for model in apps.get_models()
        if model.__module__.startswith("esgapi.")
        and (
            issubclass(model, CompanyRootModel)
            or "company_id" in {field.attname for field in model._meta.concrete_fields}
        )
    ]
    return sorted(found, key=lambda model: model.__name__)


COMPANY_NAMES = frozenset(model.__name__ for model in company_models())
SCOPED_NAMES = COMPANY_NAMES


def product_files() -> dict[str, ast.Module]:
    files: dict[str, ast.Module] = {}
    for path in sorted(ESGAPI.rglob("*.py")):
        relative = path.relative_to(ESGAPI)
        if {"tests", "migrations"} & set(relative.parts[:-1]):
            continue
        files[str(relative)] = ast.parse(path.read_text(), filename=str(relative))
    return files


PRODUCT = product_files()


def _scoped_attribute(node: ast.AST, attr: str) -> TypeGuard[ast.Attribute]:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr
        and isinstance(node.value, ast.Name)
        and node.value.id in SCOPED_NAMES
    )


def raw_sql_hits(tree: ast.Module) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in RAW_SQL_CALLS:
            hits.append(f".{node.func.attr}( (줄 {node.lineno})")
        elif isinstance(node, ast.Name) and node.id in RAW_SQL_NAMES:
            hits.append(f"{node.id} (줄 {node.lineno})")
        elif isinstance(node, ast.Attribute) and node.attr in RAW_SQL_NAMES:
            hits.append(f".{node.attr} (줄 {node.lineno})")
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "connect"
            and isinstance(node.value, ast.Name)
            and node.value.id == "psycopg"
        ):
            hits.append(f"psycopg.connect (줄 {node.lineno})")
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "connections":
            hits.append(f"connections[…] (줄 {node.lineno})")
    return hits


def imported_modules(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def constructor_hits(tree: ast.Module) -> list[str]:
    return [
        f"{node.func.id}(…) (줄 {node.lineno})"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SCOPED_NAMES
    ]


def test_every_scoped_model_defaults_to_the_refusing_manager() -> None:
    """테넌트 범위 모델(tenant_id 칸)은 0 이다. 범위 모델은 전부 회사 바닥이다(분모: 열하나)."""
    assert [model.__name__ for model in scoped_models()] == []
    assert len(company_models()) == 37  # 분모(AU1a +1: AuditEventRow · X1b-1 +4: 실행 넷 · G1b +2: 검토 둘 · G2c2 +1)
    # · RM1a +1: RunSegmentRow(구획 기록 — 플랫폼-서버 7a 허락 2026-11-10)
    # · TR4 +1: TranslationAiSettingRow
    # · DVA1 +1: DataverifyAiSettingRow
    # · IR4 +1: MaterialityAiSettingRow
    # · K1b-1 +1: SiteFacility(FacilityCode 는 회사 칸이 없어 안 듦)
    # · K1b-2b +2: InventoryYear·CompanyIndexSelection(inventory 의 첫 회사 범위 표)
    # · S12a +3: InventoryEntryRow·InventoryEntryValue·InventoryEntryHistory(입구 0 — MODEL_ENTRANCES 그대로)
    # · RP1 +4: 원고작성 표 넷
    # · RP2a +2: 문서 산출물 둘(DocumentArtifactRow·DocumentArtifactUseRow)
    # · S12a-2 +2: InventoryEntryPeriod·InventoryCustomFactor(입구는 ② 의 InventoryEntryRow.used_factor_ids 하나)
    # · RPA1 +1: DraftingAiSettingRow
    # · S3K2a +1: Scope3CategoryState(입구 0 — MODEL_ENTRANCES·허락 목록 그대로)
    # · IRS3 +2: MaterialityResultEditHeadRow·MaterialityResultEditRow
    # · S3K2b-1 +1: Scope3RowEdit(입구 0 — MODEL_ENTRANCES·허락 목록 그대로)


def test_product_code_has_no_objects_and_no_tenant_opener() -> None:
    """<범위 모델>.objects 0, 그리고 테넌트 바닥의 여는 길(어느 이름 뒤의 .for_tenant 든) 0."""
    problems: list[str] = []
    for name, tree in PRODUCT.items():
        for node in ast.walk(tree):
            if _scoped_attribute(node, "objects"):
                problems.append(f"{name}: .objects (줄 {node.lineno})")
            if isinstance(node, ast.Attribute) and node.attr == "for_tenant":
                problems.append(f"{name}: .for_tenant (줄 {node.lineno})")
    assert problems == []
    assert len(PRODUCT) > 0  # 분모
    # 자기 시험: 지어낸 소스의 두 꼴을 잡는다
    planted = ast.parse("DocumentRow.objects.all()\nopener = JobRow.for_tenant")
    assert sum(_scoped_attribute(node, "objects") for node in ast.walk(planted)) == 1
    assert sum(isinstance(node, ast.Attribute) and node.attr == "for_tenant" for node in ast.walk(planted)) == 1


def test_every_company_model_defaults_to_the_refusing_manager() -> None:
    models_found = company_models()
    assert [model.__name__ for model in models_found] == [
        "AuditEventRow",
        "Company",
        "CompanyIndexSelection",  # K1b-2b 고객사 인덱스 선택
        "DataverifyAiSettingRow",  # DVA1 AI 설정 판
        "DocumentArtifactRow",  # RP2a ① 문서 산출물 둘
        "DocumentArtifactUseRow",
        "DocumentRow",
        "DraftingAiSettingRow",  # RPA1 AI 설정 판
        "DraftingOutline",  # RP1 원고작성 표 넷
        "DraftingOutlineNode",
        "DraftingProject",
        "DraftingProjectDocument",
        "GreenwashAiSettingRow",  # G2c2 AI 설정 판
        "GreenwashReviewMarkRow",  # G1b 검토 둘
        "GreenwashReviewRow",
        "InventoryCustomFactor",  # S12a-2 직접입력 계수·입력주기
        "InventoryEntryHistory",  # S12a Scope 1·2 입력 셋
        "InventoryEntryPeriod",  # S12a-2
        "InventoryEntryRow",
        "InventoryEntryValue",
        "InventoryYear",  # K1b-2b 인벤토리 해
        "JobRow",
        "LlmCallLogRow",
        "MaterialityAiSettingRow",  # IR4 AI 설정 판
        "MaterialityResultEditHeadRow",  # IRS3 결과 고침 둘
        "MaterialityResultEditRow",
        "RunFileRow",
        "RunResultRow",
        "RunRow",
        "RunSegmentRow",  # RM1a 구획 기록
        "RunStepRow",
        "Scope3CategoryState",  # S3K2a Scope 3 카테고리 잠금
        "Scope3RowEdit",  # S3K2b-1 Scope 3 줄 편집 사건
        "Site",
        "SiteFacility",  # K1b-1 사업장별 자산/시설
        "TranslationAiSettingRow",  # TR4 AI 설정 판
        "User",
    ]  # 분모
    for model in models_found:
        assert isinstance(model._default_manager, CompanyRootManager | CompanyScopedManager), model.__name__
        assert "unscoped" in model._meta.managers_map, model.__name__


def test_product_code_opens_company_tables_only_through_for_company() -> None:
    problems: list[str] = []
    opened = 0
    for name, tree in PRODUCT.items():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "for_company"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in COMPANY_NAMES
            ):
                opened += 1
                if len(node.args) != 1 or node.keywords or isinstance(node.args[0], ast.Constant):
                    problems.append(f"{name}: for_company 의 인자가 상수 아닌 하나가 아니다 (줄 {node.lineno})")
    assert problems == []
    # 분모: 지금 제품의 <회사 모델>.for_company( 수. 늘거나 줄면 사람이 본다. organization selectors·services 하나씩,
    # user services 둘(upsert_user·create_customer_user), user selectors 셋(find_customer·account·lock_account — K2a),
    # core 의 10(K1u-b), K2c +2(organization selectors 의 find_company_by_id · user selectors 의 list_customer_users),
    # AU1a +2: core 의 감사 쓰기·읽기(services/audit.py 의 record_event · selectors/audit.py 의 list_audit_events),
    # AU1a ③ +1: user selectors 의 names_of,
    # X1b-1 +12: runs 의 selectors/runs.py 여섯(문 _runs·_steps, 파일·결과 표를 여는 넷) · services/runs.py 여섯,
    # X1b-1 ③ +2: runs 의 actions/runs.py 둘(create_run 의 실행 행·단계 행 — run_page 는 문 _runs 위라 0),
    # AU1b-2 +2: runs 의 selectors/operator.py 의 문 _runs · core 의 selectors/llm_usage.py 의 usage_by_run
    # G1b +8(검토 표 둘의 selector·service) · G1b ③ +2(목록 줄의 묶음 읽기 둘)
    # X1b-2a +1: core 의 services/documents.py 의 update_document(목록·사슬의 읽기는 문 _documents 위라 0)
    # G2c2 +8: AI 설정 판 — selectors/ai_settings.py 다섯(목록 셈·적용 판·한 판·잠금·이름) · services 셋(만들기·적용 둘)
    # G2c2 ③ +2: 실행기의 판 읽기 RunSettingStore 의 applied·get
    # X1b-2b +1: runs 의 actions/runs.py 의 create_run 이 이어 돌기의 파일 행을 쓴다(앞 실행 읽기는 selector 위라 0)
    # G1b-2b +1: runs 의 selectors/runs.py 의 results_of(결과 표는 문 함수가 없다 — 다른 묶음 읽기 둘은 문 위라 0)
    # AD4S +1: 그린워싱 run_extras 의 run_ids_in
    # AD4D +1: core 의 selectors/llm_usage.py 의 usage_by_step(단계 머리 step_heads 는 문 _steps 위라 0)
    # TR4 +8: 영문번역 AI 설정 판 — selectors/ai_settings.py 다섯(목록 셈·적용 판·한 판·잠금·이름) · services 셋
    # TR4 ③ +3: RunSettingStore 의 applied·get · run_extras 의 run_ids_in(G2c2 ③·AD4S 와 같은 꼴)
    # DVA1 +8: 데이터 검증 AI 설정 판 — selectors/ai_settings.py 다섯(목록 셈·적용 판·한 판·잠금·이름) · services 셋
    # DVA1 ③ +3: RunSettingStore 의 applied·get · run_extras 의 run_ids_in(TR4 ③ 과 같은 꼴)
    # RX1a ① +15: core 의 llm_logs selector·service 하나씩 · services/documents.py 셋(import_document·set_imported_etag·
    # restore_document_times — raw_documents 는 문 _documents 위라 0) · runs 의 selectors/bundle.py 넷 ·
    # services/bundle.py 여섯
    # IR4 +8: 중대성평가 IRO AI 설정 판 — selectors/ai_settings.py 다섯(목록 셈·적용 판·한 판·잠금·이름) · services 셋
    # IR4 ③ +3: RunSettingStore 의 applied·get · run_extras 의 run_ids_in(DVA1 ③ 과 같은 꼴)
    # RX1b +11: greenwash selectors/review.py 의 bundle_review_rows 둘 · services/review.py 의 import_review 셋
    # (있음·넣기·시각)·import_marks 둘(넣기·시각) · 네 모듈 services/ai_settings.py 의 import_setting 하나씩
    # K1b-1 ① +3: organization selectors/branches.py 둘(headquarters_of·alive_site_named) · services/branches.py 의
    # ensure_headquarters 하나
    # K1b-1 ② +3: selectors/branches.py 는 _alive·facilities_of 둘(① 의 둘이 _alive 위로 — 0) · services/branches.py
    # 다섯 더
    # (만들기·고침·토글·삭제 표시·자산/시설) · 옛 /sites 의 selectors/organization.py all_sites·services insert_site
    # 각 −1(같은 안쪽 함수로)
    # K1b-1 ② 고침 +1: services/branches.py 의 mark_facilities_of_sites_deleted(지운 사업장의 자산/시설 — R5)
    # K1b-2b ② +7: inventory 의 selectors/index_selection.py 셋(year_of·lock_year·selections_of) · services 넷
    # (create_year·insert_selections·set_hidden·mark_selections_deleted)
    # S12a ② +25: inventory 의 selectors/entries.py 열둘(행·값 읽기 둘·잠금·있나·히스토리·해 합·추정·해 목록 둘·
    # 자릿수·사용 중 둘) · selectors/index_selection.py 넷(selections_with_data 몸·selection_of·selection_states·
    # lock_selection) · services/entries.py 여덟(행 둘·값 둘·히스토리·삭제 표시·메모·잠금) ·
    # services/index_selection.py 의 set_decimals 하나
    # RP1 ① +11: drafting 의 selectors/projects.py 여섯(project_head·lock_project·current_document·current_outline·
    # outline_at 둘) · services/projects.py 다섯(create_project·attach_document·_bump_revision·_insert_outline·
    # _insert_nodes)
    # RP2a ① +8: core 의 documents/selectors.py 여섯(_visible_uses 둘·find_artifact·find_by_source·source_of·
    # artifact_view) · documents/services.py 둘(산출물·uses 넣기)
    # RP2d +2: drafting 의 selectors/projects.py project_page 둘(프로젝트·EXISTS 의 문서)
    # S12a-2 ② +8: inventory 의 selectors/entries.py 다섯(row_of·history_line·top_line_id·periods_of·custom_of —
    # estimated_lines 는 estimated_nodes 자리라 0) · services/entries.py 셋(upsert_period·insert_custom·set_row_factor)
    # RPA1 +9: drafting 의 selectors/ai_settings.py 다섯(목록 셈·적용 판·한 판·잠금·이름) · services/ai_settings.py
    # 넷(만들기 둘 — 번호 다시 시도·적용 내림·올림)
    # RPA1 ② +3: drafting 의 selectors/ai_settings.py RunSettingStore 둘(applied·get) · selectors/run_extras.py 하나
    # RPS1 +2: drafting 의 selectors/projects.py current_documents 하나 · project_page 의 지금 목차 판 서브쿼리 하나
    # S3K2a ① +5: inventory 의 selectors/scope3_state.py 둘(locks_of·lock_row) · services/scope3_state.py 셋
    # (ensure_row·set_lock·clear_lock)
    # IRS3 ① +5: materiality 의 selectors/edits.py 둘(head_revision·current_edits) · services/edits.py 셋(create_head·
    # bump_head·insert_edits)
    # S3K2b-1 ① +3: inventory 의 selectors/scope3_edits.py 둘(events_of·history_page) · services/scope3_edits.py 하나
    # (add_events)
    # RM1a ② +5: core 의 selectors/llm_usage.py usage_by_segment 하나 · runs 의 selectors/runs.py 둘(segment_rows·
    # ended_segments) · services/runs.py 둘(segments_planned 의 create·_segment_guard)
    # RM1b ② +9: runs 의 selectors/runs.py 일곱(segment_plan·segment_counts·running_segments·first_pending·
    # segment_head·alive_segments·done_octets) · services/runs.py 둘(_wake·segment_end 의 Fatal 실행 failed)
    # (segments_planned 의 create → bulk_create 는 같은 자리 하나)
    # RM1c ① +4: runs 의 actions/runs.py 하나(create_run 의 옮긴 구획 bulk_create) · selectors/runs.py 셋
    # (segments_to_carry·segment_refs·segment_outputs)
    # RM1c ② +2: runs 의 selectors/bundle.py bundle_rows 의 구획 하나 · services/bundle.py insert_segments 하나
    # RM1c ③′ +1: runs 의 selectors/runs.py earliest_lease(미룬 쪽지의 임대 끝)
    # RM1c ③ +1: runs 의 selectors/runs.py segment_page(구획 목록 GET /runs/{run_id}/segments)
    assert opened == 241


def test_the_company_entrances_are_called_only_from_their_place() -> None:
    """Company.by_subdomain 은 organization 의 selectors 하나, Company.register 는 seed_company 하나에서만 부른다."""
    calls: dict[str, set[str]] = {entrance: set() for entrance in ENTRANCES}
    for name, tree in PRODUCT.items():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            entrance = node.func.attr
            if entrance == "by_subdomain" and name not in {"core/isolation/managers.py", "organization/models.py"}:
                calls[entrance].add(name)
            if entrance == "register" and isinstance(node.func.value, ast.Name) and node.func.value.id in COMPANY_NAMES:
                calls[entrance].add(name)
            if entrance == "sole_candidates" and name != "organization/models.py":
                calls[entrance].add(name)
    assert calls == ENTRANCES  # 분모: 허용 자리마다 실제로 부른다(죽은 목록이 아니다)


def test_the_company_choosers_are_wired_only_in_the_user_admin_routes() -> None:
    """운영 관리자의 회사 고르기 둘(K2c)을 부르거나 가리키는 자리는 user 의 apis/users.py 하나다(정의 자리 밖)."""
    places: dict[str, set[str]] = {chooser: set() for chooser in COMPANY_CHOOSERS}
    for name, tree in PRODUCT.items():
        if name == "organization/service/selectors/organization.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in COMPANY_CHOOSERS:
                places[node.id].add(name)
    assert places == COMPANY_CHOOSERS


def root_manager_hits(tree: ast.Module) -> list[str]:
    """`<무엇>.root_manager(…)` 를 부르는 자리(그 뒤에 무엇을 잇든)."""
    return [
        f"root_manager() (줄 {node.lineno})"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "root_manager"
    ]


def test_the_root_manager_is_taken_out_only_in_its_place() -> None:
    """뿌리 매니저를 꺼내 register·_entrance 를 부르는 길이 허용 자리 밖에 없다(입구 허용 목록을 비껴가는 길)."""
    outside = [
        f"{name}: {hit}"
        for name, tree in PRODUCT.items()
        if name not in ROOT_MANAGER_ALLOWED
        for hit in root_manager_hits(tree)
    ]
    assert outside == []
    for name in ROOT_MANAGER_ALLOWED:  # 분모: 허용 목록이 죽은 목록이 아니다
        assert root_manager_hits(PRODUCT[name]), name
    # 자기 시험: services 에 심은 꼴(검증자의 지어낸 소스)을 잡는다
    assert root_manager_hits(ast.parse('Company.root_manager().register(name="n")'))
    assert root_manager_hits(ast.parse("Company.root_manager()._entrance().all()"))


# QuerySet 을 모델과 함께 새로 짓는 자리(`models.QuerySet[...](model=…)`): 기본 매니저의 거절을 비껴가는 길이라
# 입구 함수 일곱의 몸에만 둔다(K2a 검증 권고 2 · QC1 — 파일째가 아니라 함수 자리로, MARC-ISSUE-455) — 회사 바닥
# (managers.py 의 for_company·_entrance)과 운영 관리자·refresh 행의 입구(user/models.py)와
# 회사 없는 감사 행의 입구(core/models.py 의 operator_rows — AU1a)와
# 회사 넘는 사용 중 읽기의 입구(inventory/models.py 의 used_node_ids·used_factor_ids — K1b-2b ④, MODEL_ENTRANCES 의
# 열쇠와 같아야 한다). 파일 → 「클래스.함수」.
QUERYSET_CONSTRUCTOR_ALLOWED: dict[str, frozenset[str]] = {
    "core/isolation/managers.py": frozenset({"CompanyScopedManager.for_company", "CompanyRootManager._entrance"}),
    "user/models.py": frozenset({"CompanyScopedUserManager._admins", "RefreshToken._rows"}),
    "core/models.py": frozenset({"AuditEventRow.operator_rows"}),
    "inventory/models.py": frozenset(
        {
            "CompanyIndexSelection.used_node_ids",
            "CompanyIndexSelection.used_factor_ids",
            "InventoryEntryRow.used_factor_ids",  # S12a-2(H14)
        }
    ),
    "organization/models.py": frozenset({"SiteFacility.used_code_ids"}),  # S12S1 Q9 — 7a 허락(S12S1 Q9 +1)
}


def _queryset_name(node: ast.AST, subclasses: frozenset[str] = frozenset()) -> str | None:
    """`QuerySet`·`CompanyScopedQuerySet`·`models.QuerySet[...]` 처럼 이름이 QuerySet 으로 끝나는 이름·속성의 이름,
    또는 QuerySet 의 하위 클래스 이름(subclasses — queryset_subclasses)."""
    target = node.value if isinstance(node, ast.Subscript) else node
    name = target.attr if isinstance(target, ast.Attribute) else target.id if isinstance(target, ast.Name) else None
    return name if name is not None and (name.endswith("QuerySet") or name in subclasses) else None


def queryset_subclasses(trees: Collection[ast.Module]) -> frozenset[str]:
    """바탕 클래스 사슬이 `…QuerySet` 에 닿는 클래스의 이름(QC4 — `class _Rows(models.QuerySet)` 의 `_Rows(model=X)`).
    파일을 가르지 않고 이름으로 모은다: 같은 파일의 사슬과 다른 파일에서 들여온 이름(별칭 import 의 새 이름 포함)을
    사슬이 끝날 때까지 되풀이한다(고정점)."""
    found: set[str] = set()
    while True:
        known = frozenset(found)
        for tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and any(_queryset_name(base, known) for base in node.bases):
                    found.add(node.name)
                elif isinstance(node, ast.Import | ast.ImportFrom):
                    found.update(
                        alias.asname
                        for alias in node.names
                        if alias.asname and _queryset_name(ast.Name(alias.name.rsplit(".", 1)[-1]), known)
                    )
        if len(found) == len(known):
            return known


def _is_type_checking(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def queryset_sites(tree: ast.Module, subclasses: frozenset[str] | None = None) -> list[tuple[str, str, int]]:
    """QuerySet 을 짓는 자리와 짓는 이름을 빼돌리는 자리: (클래스.함수 — 모듈 수준은 "", 꼴, 줄).
    꼴 = 생성자(`…QuerySet(…)`·`…QuerySet[…](…)`) · 별칭 import(`import … QuerySet as X`) ·
    담기(이름을 부르지 않고 집음 — `x = models.QuerySet`, 인자로 넘김) · getattr(`getattr(m, "…QuerySet")`).
    QuerySet 의 하위 클래스 이름(subclasses — 주지 않으면 이 파일 하나에서 모은다)도 `…QuerySet` 이름과 똑같이 센다.
    타입 주석(인자·반환·변수 주석, `if TYPE_CHECKING:` 몸, type 별칭)과 클래스 바탕은 세지 않는다."""
    found: list[tuple[str, str, int]] = []
    named = queryset_subclasses([tree]) if subclasses is None else subclasses

    def visit(node: ast.AST, site: str) -> None:
        if isinstance(node, ast.ClassDef):
            inner = f"{site}.{node.name}" if site else node.name
            for child in [*node.decorator_list, *node.body]:  # 바탕(bases·keywords)은 건너뛴다
                visit(child, inner)
            return
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            inner = f"{site}.{node.name}" if site else node.name
            defaults = [*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)]
            for child in [*node.decorator_list, *defaults, *node.body]:  # 인자 주석·반환 주석은 건너뛴다
                visit(child, inner)
            return
        if isinstance(node, ast.AnnAssign):
            if node.value is not None:
                visit(node.value, site)
            return
        if isinstance(node, ast.If) and _is_type_checking(node):
            for child in node.orelse:
                visit(child, site)
            return
        if isinstance(node, ast.TypeAlias | ast.arg):
            return
        if isinstance(node, ast.Import | ast.ImportFrom):
            for alias in node.names:
                last = alias.name.rsplit(".", 1)[-1]
                if _queryset_name(ast.Name(last), named) and alias.asname not in {None, last}:
                    found.append((site, "별칭 import", node.lineno))
            return
        if isinstance(node, ast.Call):
            if _queryset_name(node.func, named):
                found.append((site, "생성자", node.lineno))
                callee = node.func.value if isinstance(node.func, ast.Subscript) else node.func
                if isinstance(callee, ast.Attribute):
                    visit(callee.value, site)
                for child in [*node.args, *(k.value for k in node.keywords)]:
                    visit(child, site)
                return
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and _queryset_name(ast.Name(node.args[1].value), named)
            ):
                found.append((site, "getattr", node.lineno))
        if (
            isinstance(node, ast.Name | ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and _queryset_name(node, named)
        ):
            found.append((site, "담기", node.lineno))
            return
        for child in ast.iter_child_nodes(node):
            visit(child, site)

    for statement in tree.body:
        visit(statement, "")
    return found


def queryset_constructor_hits(tree: ast.Module) -> list[str]:
    """queryset_sites 의 글: `<꼴> <자리> (줄 n)`."""
    return [f"{kind} {site or '<모듈>'} (줄 {line})" for site, kind, line in queryset_sites(tree)]


def queryset_problems(trees: dict[str, ast.Module], allowed: dict[str, frozenset[str]]) -> list[str]:
    """① 허락 파일 밖의 모든 꼴 ② 허락 파일 안이라도 표의 함수 자리 밖의 꼴 ③ 표의 자리마다 생성자가 하나 이상.
    QuerySet 의 하위 클래스는 trees 전체에서 모은다(다른 파일에서 지은 클래스를 들여와 짓는 꼴)."""
    problems: list[str] = []
    subclasses = queryset_subclasses(trees.values())
    for name, tree in trees.items():
        sites = allowed.get(name, frozenset())
        found = queryset_sites(tree, subclasses)
        problems += [
            f"{name}: {kind} {site or '<모듈>'} (줄 {line})" for site, kind, line in found if site not in sites
        ]
        built = {site for site, kind, _line in found if kind == "생성자"}
        problems += [f"{name}: {site} 에 생성자가 없다(죽은 줄)" for site in sorted(sites - built)]
    problems += [f"{name}: 제품 파일이 아니다" for name in allowed if name not in trees]
    return problems


def test_querysets_are_built_only_in_the_entrances() -> None:
    assert queryset_problems(PRODUCT, QUERYSET_CONSTRUCTOR_ALLOWED) == []
    assert sum(len(sites) for sites in QUERYSET_CONSTRUCTOR_ALLOWED.values()) == 9  # 분모: 함수 자리 아홉(S12S1 Q9 +1)
    # 자기 시험: selector 에 심은 꼴(검증자의 지어낸 소스) — 생성자 넷 · 별칭 import 둘 · 담기 둘 · getattr 하나
    assert queryset_constructor_hits(ast.parse('models.QuerySet["User"](model=User).filter(kind="service")'))
    assert queryset_constructor_hits(ast.parse("QuerySet(model=User)"))
    assert queryset_constructor_hits(ast.parse("models.QuerySet(User)"))
    assert queryset_constructor_hits(ast.parse("CompanyScopedQuerySet[_M](model=User, hints={})"))
    assert queryset_constructor_hits(ast.parse("from django.db.models import QuerySet as QS"))
    assert queryset_constructor_hits(ast.parse("import django.db.models.query.QuerySet as QS"))
    assert queryset_constructor_hits(ast.parse("def f():\n    build = models.QuerySet\n    return build(model=X)"))
    assert queryset_constructor_hits(ast.parse("rows = make(models.QuerySet[X], model=X)"))
    assert queryset_constructor_hits(ast.parse('getattr(models, "QuerySet")(model=X)'))
    assert not queryset_constructor_hits(ast.parse("User.for_company(c).filter(kind='service')"))
    # 자기 시험(QC4 R2): QuerySet 의 하위 클래스로 짓는 꼴 — 바로 · 사슬 · 별칭 import · getattr
    subclass = "class _Rows(models.QuerySet):\n    pass\n"
    assert queryset_constructor_hits(ast.parse(subclass + "rows = _Rows(model=X)"))
    assert queryset_constructor_hits(ast.parse(subclass + "class _Deep(_Rows):\n    pass\n_Deep[X](model=X)"))
    assert queryset_constructor_hits(ast.parse(subclass + 'getattr(here, "_Rows")(model=X)'))
    assert queryset_constructor_hits(ast.parse("from a import _Rows as R\nclass _Rows(QuerySet[X]):\n    pass\n"))
    # 안 잡히는 꼴: 하위 클래스 아닌 클래스의 같은 꼴 · 클래스 정의만
    assert not queryset_constructor_hits(ast.parse("class _Rows(Base):\n    pass\nrows = _Rows(model=X)"))
    assert not queryset_constructor_hits(ast.parse(subclass + "class _Deep(_Rows):\n    pass\n"))
    # 다른 파일에서 지은 하위 클래스를 들여와 짓는 꼴(queryset_problems 는 trees 전체에서 모은다)
    split = {
        "core/rows.py": ast.parse("class _Rows(models.QuerySet):\n    pass\n"),
        "inventory/service/actions/ghg_pool.py": ast.parse("from esgapi.core.rows import _Rows\n_Rows(model=X)"),
    }
    assert queryset_problems(split, {}) == ["inventory/service/actions/ghg_pool.py: 생성자 <모듈> (줄 2)"]
    # 자기 시험: 허락 파일 안이라도 표의 함수 밖이면 잡고, 표의 함수에 생성자가 없으면 죽은 줄
    planted = {
        "inventory/models.py": ast.parse(
            "class CompanyIndexSelection:\n"
            "    @classmethod\n    def used_node_ids(cls):\n        return models.QuerySet(model=cls)\n"
            "class InventoryYear:\n"
            '    @classmethod\n    def all_years(cls):\n        return models.QuerySet["InventoryYear"](model=cls)\n'
        )
    }
    assert queryset_problems(planted, {"inventory/models.py": frozenset({"CompanyIndexSelection.used_node_ids"})}) == [
        "inventory/models.py: 생성자 InventoryYear.all_years (줄 8)"
    ]
    assert queryset_problems(
        planted,
        {"inventory/models.py": frozenset({"CompanyIndexSelection.used_node_ids", "InventoryYear.all_years", "X.y"})},
    ) == ["inventory/models.py: X.y 에 생성자가 없다(죽은 줄)"]


def test_the_queryset_finder_skips_annotations_and_bases() -> None:
    """타입 주석·클래스 바탕·TYPE_CHECKING 몸·별칭 없는 import 는 세지 않는다(제품에서 오탐 0 의 근거)."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "from django.db.models import Q, QuerySet\n"
        "if TYPE_CHECKING:\n    from django.db.models.query import ValuesQuerySet as VQ\n"
        "class CompanyScopedQuerySet(models.QuerySet[_M]):\n    pass\n"
        "rows: QuerySet[Site] | None = None\n"
        "type Rows = QuerySet[Site]\n"
        "def _alive(company_id: int, rows: 'QuerySet[Site]' = None) -> models.QuerySet[Site]:\n"
        "    kept: CompanyScopedQuerySet[Site] = Site.for_company(company_id)\n"
        "    return kept.filter(deleted_at__isnull=True)\n"
    )
    assert queryset_sites(ast.parse(source)) == []


def model_entrance_sites() -> set[tuple[str, str]]:
    """MODEL_ENTRANCES 의 열쇠를 (몸의 파일, 클래스.함수) 로."""
    return {(MODEL_ENTRANCE_FILES[cls], f"{cls}.{name}") for cls, name in MODEL_ENTRANCES}


def test_the_queryset_table_matches_the_model_entrances() -> None:
    """MODEL_ENTRANCES 의 모델이 생성자를 둘 수 있는 자리 = MODEL_ENTRANCES 의 입구(두 표가 따로 놀지 않는다)."""
    allowed = {
        (name, site)
        for name, sites in QUERYSET_CONSTRUCTOR_ALLOWED.items()
        for site in sites
        if name in set(MODEL_ENTRANCE_FILES.values())
    }
    assert allowed == model_entrance_sites()
    assert len(allowed) == 4  # 분모 · S12a-2 +1: InventoryEntryRow.used_factor_ids · S12S1 Q9 +1: SiteFacility


def test_product_code_does_not_use_unscoped() -> None:
    hits = [
        f"{name}: .unscoped (줄 {node.lineno})"
        for name, tree in PRODUCT.items()
        if name not in UNSCOPED_ALLOWED
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "unscoped"
    ]
    assert hits == []


def test_product_code_does_not_reach_hidden_managers() -> None:
    hits = [
        f"{name}: .{node.attr} (줄 {node.lineno})"
        for name, tree in PRODUCT.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in HIDDEN_MANAGERS
    ]
    assert hits == []


def test_product_code_has_no_raw_sql_outside_the_list() -> None:
    outside = [
        f"{name}: {hit}" for name, tree in PRODUCT.items() if name not in RAW_SQL_ALLOWED for hit in raw_sql_hits(tree)
    ]
    assert outside == []
    for name in RAW_SQL_ALLOWED:  # 분모: 허용 목록이 죽은 목록이 아니다
        assert raw_sql_hits(PRODUCT[name]), name
    migrations = [ast.parse(path.read_text()) for path in sorted(ESGAPI.glob("*/migrations/*.py"))]
    for name, module in MIGRATION_PIECES.items():
        assert name in RAW_SQL_ALLOWED
        assert [other for other, tree in PRODUCT.items() if module in imported_modules(tree)] == [], name
        assert any(module in imported_modules(tree) for tree in migrations), name  # 분모: 마이그레이션이 쓴다


def test_product_code_builds_scoped_rows_only_in_the_list() -> None:
    outside = [
        f"{name}: {hit}"
        for name, tree in PRODUCT.items()
        if name not in CONSTRUCTOR_ALLOWED
        for hit in constructor_hits(tree)
    ]
    assert outside == []
    for name in CONSTRUCTOR_ALLOWED:  # 분모: 허용 목록이 죽은 목록이 아니다
        assert constructor_hits(PRODUCT[name]), name
    # 561 L2: 파일 단위 허락이 그 파일 안에 생성자를 늘리는 길이 되지 않게 — 파일마다 자리 수를 못 박는다
    assert {name: len(constructor_hits(PRODUCT[name])) for name in CONSTRUCTOR_ALLOWED} == CONSTRUCTOR_HITS


def test_no_one_loads_a_tenant_into_the_connection() -> None:
    names = [name for name in PRODUCT if name not in TENANT_LOADING_EXEMPT]
    hits = [f"{name}: {word}" for name in names for word in TENANT_LOADING_WORDS if word in (ESGAPI / name).read_text()]
    assert hits == []
    assert len(names) > 0  # 분모


# ── 사용자 표의 입구(K2a) ──────────────────────────────────────────────


def user_entrance_calls(trees: dict[str, ast.Module]) -> dict[tuple[str, str], set[str]]:
    calls: dict[tuple[str, str], set[str]] = {key: set() for key in USER_ENTRANCES}
    for name, tree in trees.items():
        if name == USER_MODELS:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and (node.func.value.id, node.func.attr) in USER_ENTRANCES
            ):
                calls[(node.func.value.id, node.func.attr)].add(name)
    return calls


def test_the_user_entrances_are_called_only_from_their_place() -> None:
    """운영 관리자 입구 셋과 refresh 행 입구 넷은 정해진 자리에서만 부른다(HTTP 경로·명령에서 직접 0)."""
    assert user_entrance_calls(PRODUCT) == {key: set(places) for key, places in USER_ENTRANCES.items()}
    # 자기 시험: 다른 자리에서 부르면 그 자리가 잡힌다
    planted = {"user/service/apis/user.py": ast.parse("User.admin_by_username(x).first()")}
    assert user_entrance_calls(planted)[("User", "admin_by_username")] == {"user/service/apis/user.py"}


def _function(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef:
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(function: ast.FunctionDef, attr: str) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr
        for n in ast.walk(function)
    )


def admin_filter_problems(tree: ast.Module) -> list[str]:
    """운영 관리자 입구의 몸에 kind="admin"·회사 NULL 조건이 있는가(P20).
    셋은 _admins() 를 거치고, _admins 가 조건을 쓴다."""
    problems: list[str] = []
    admins = _function(tree, "CompanyScopedUserManager", "_admins")
    keywords = {
        (k.arg, k.value.value)
        for n in ast.walk(admins)
        if isinstance(n, ast.Call)
        for k in n.keywords
        if isinstance(k.value, ast.Constant)
    }
    if not {("kind", "admin"), ("company__isnull", True)} <= keywords:
        problems.append("_admins: kind=admin·company__isnull=True 조건이 없다")
    for name in ("admin_by_username", "admin_by_id", "register_admin"):
        if not _calls(_function(tree, "CompanyScopedUserManager", name), "_admins"):
            problems.append(f"{name}: _admins() 를 거치지 않는다")
    return problems


def test_the_operator_entrances_carry_the_admin_condition() -> None:
    assert admin_filter_problems(PRODUCT[USER_MODELS]) == []
    # 자기 시험: 조건 없이 찾는 꼴(P20)을 잡는다
    planted = ast.parse(
        "class CompanyScopedUserManager:\n"
        "    def _admins(self):\n        return Q(model=self.model).filter(company__isnull=True)\n"
        "    def admin_by_username(self, u):\n        return Q(model=self.model).filter(username=u)\n"
        "    def admin_by_id(self, i):\n        return self._admins().filter(pk=i)\n"
        "    def register_admin(self, **f):\n        return self._admins().create(**f)\n"
    )
    assert len(admin_filter_problems(planted)) == 2


# ── 감사 기록의 입구(AU1a) ─────────────────────────────────────────────


def audit_entrance_calls(trees: dict[str, ast.Module]) -> dict[tuple[str, str], set[str]]:
    calls: dict[tuple[str, str], set[str]] = {key: set() for key in AUDIT_ENTRANCES}
    for name, tree in trees.items():
        if name == AUDIT_MODELS:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and (node.func.value.id, node.func.attr) in AUDIT_ENTRANCES
            ):
                calls[(node.func.value.id, node.func.attr)].add(name)
    return calls


def test_the_audit_entrance_is_called_only_from_its_places() -> None:
    """회사 없는 감사 행의 입구는 감사의 selectors·services 둘에서만 부른다(분모: 둘 다 실제로 부른다)."""
    assert audit_entrance_calls(PRODUCT) == {key: set(places) for key, places in AUDIT_ENTRANCES.items()}
    # 자기 시험: 다른 자리에서 부르면 그 자리가 잡힌다
    planted = {"core/service/services/documents.py": ast.parse("AuditEventRow.operator_rows().filter(pk=1)")}
    assert audit_entrance_calls(planted)[("AuditEventRow", "operator_rows")] == {"core/service/services/documents.py"}


def audit_entrance_problems(tree: ast.Module) -> list[str]:
    """회사 없는 감사 행 입구의 몸에 company_id__isnull=True 조건이 있는가(P3 의 순수 짝)."""
    entrance = _function(tree, "AuditEventRow", "operator_rows")
    keywords = {
        (k.arg, k.value.value)
        for n in ast.walk(entrance)
        if isinstance(n, ast.Call)
        for k in n.keywords
        if isinstance(k.value, ast.Constant)
    }
    return [] if ("company_id__isnull", True) in keywords else ["operator_rows: company_id__isnull=True 조건이 없다"]


def test_the_audit_entrance_carries_the_no_company_condition() -> None:
    assert audit_entrance_problems(PRODUCT[AUDIT_MODELS]) == []
    # 자기 시험: 조건 없이 모든 행을 여는 꼴(P3)을 잡는다
    planted = ast.parse(
        "class AuditEventRow:\n"
        "    @classmethod\n"
        "    def operator_rows(cls):\n        return Q(model=cls).filter(action='login')\n"
    )
    assert len(audit_entrance_problems(planted)) == 1


def imported_names(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def refresh_user_hits(tree: ast.Module) -> list[str]:
    """refresh 행에서 user FK 를 따라가는 글자(`.user` 속성, select_related("user"))."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "user"
            and not (isinstance(node.value, ast.Name) and node.value.id in {"self", "request"})
        ):
            hits.append(f".user (줄 {node.lineno})")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"select_related", "prefetch_related"}
            and any(isinstance(a, ast.Constant) and a.value == "user" for a in node.args)
        ):
            hits.append(f'{node.func.attr}("user") (줄 {node.lineno})')
    return hits


def test_no_one_follows_the_refresh_rows_user() -> None:
    """사용자는 refresh 주장의 회사 조건으로 따로 읽는다(K-B3) — RefreshToken.user 를 따라가지 않는다."""
    # refresh 행을 다루는 파일(RefreshToken 을 import 한 제품 파일 — 입구의 몸 밖)
    names = [name for name, tree in PRODUCT.items() if name != USER_MODELS and "RefreshToken" in imported_names(tree)]
    assert [f"{name}: {hit}" for name in names for hit in refresh_user_hits(PRODUCT[name])] == []
    assert sorted(names) == [  # 분모
        "user/service/actions/account.py",
        "user/service/actions/password.py",
        "user/service/selectors/user.py",
        "user/service/services/login.py",
    ]
    assert refresh_user_hits(ast.parse("row.user.is_active"))
    assert refresh_user_hits(ast.parse('RefreshToken.by_jti(j).select_related("user")'))


def test_the_refresh_rows_are_opened_only_through_their_entrances() -> None:
    hits = [
        f"{name}: RefreshToken.objects (줄 {node.lineno})"
        for name, tree in PRODUCT.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"objects", "unscoped"}
        and isinstance(node.value, ast.Name)
        and node.value.id == "RefreshToken"
    ]
    assert hits == []


# 명령이 받은 비밀번호의 이름(secret·typed — user/management/commands/create_user.py)도 든다(심은 파손 P15).
SECRET_NAMES = frozenset(
    {"password", "current_password", "new_password", "token", "refresh", "access", "current", "new", "secret", "typed"}
)
LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical", "write"})


def secret_log_hits(tree: ast.Module) -> list[str]:
    """기록·출력 호출(log.*·logger.*·print·self.stdout/stderr.write)의 인자에 비밀 이름이 든 자리."""
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_print = isinstance(func, ast.Name) and func.id == "print"
        is_log = isinstance(func, ast.Attribute) and func.attr in LOG_METHODS
        if not (is_print or is_log):
            continue
        for argument in [*node.args, *(k.value for k in node.keywords)]:
            for inner in ast.walk(argument):
                named = (
                    inner.id
                    if isinstance(inner, ast.Name)
                    else inner.attr
                    if isinstance(inner, ast.Attribute)
                    else None
                )
                if named in SECRET_NAMES:
                    hits.append(f"{named} (줄 {node.lineno})")
    return hits


def test_no_password_or_token_reaches_a_log() -> None:
    """비밀번호·토큰을 기록·표준 출력에 싣지 않는다(K2a). 분모: 그 이름들이 제품 코드에 다섯 자리 이상 있다."""
    assert [f"{name}: {hit}" for name, tree in PRODUCT.items() for hit in secret_log_hits(tree)] == []
    seen = sum(
        1
        for tree in PRODUCT.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in SECRET_NAMES
    )
    assert seen >= 5
    assert secret_log_hits(ast.parse('self.stdout.write(f"{password}")'))
    assert secret_log_hits(ast.parse('self.stdout.write(f"{result.user_id} {secret}")'))
    assert secret_log_hits(ast.parse("log.info('x', extra={'t': pair.access})"))


def test_the_operator_is_created_only_by_the_command() -> None:
    """운영 관리자를 만드는 service(create_operator)는 부트스트랩 명령 하나가 부른다(HTTP 0 — 사용자 결정 14:46)."""
    callers = {
        name
        for name, tree in PRODUCT.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "create_operator")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "create_operator")
        )
    }
    assert callers == {"user/management/commands/create_user.py"}


# ── 모델의 이름 붙은 입구(K1b-2b ④ — MODEL_ENTRANCES) ──────────────────


def model_aliases(tree: ast.Module) -> dict[str, set[str]]:
    """MODEL_ENTRANCES 의 모델을 가리키는 이름 → 모델 집합.
    제 이름 · import 별칭(`… import M as X`) · 대입(`X = M`, `X: type = M` — 모듈 수준이든 함수·메서드 몸 안이든,
    별칭의 별칭까지 고정점). 이름의 범위는 가르지 않는다: 파일 안 어디서든 모델을 받은 이름은 그 파일 전체에서
    별칭이다(QC4). 다시 대입한 이름(`S = A; S = B`)은 받은 모델을 다 든다(먼저 받은 것으로 못 박지 않는다)."""
    aliases = {cls: {cls} for cls in MODEL_ENTRANCE_FILES}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.asname and a.name in MODEL_ENTRANCE_FILES:
                    aliases.setdefault(a.asname, set()).add(a.name)
    assigns = [
        ([*node.targets] if isinstance(node, ast.Assign) else [node.target], node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign | ast.AnnAssign) and isinstance(node.value, ast.Name)
    ]
    while True:
        before = sum(map(len, aliases.values()))
        for targets, value in assigns:
            for target in targets:
                if isinstance(target, ast.Name) and value.id in aliases:
                    aliases.setdefault(target.id, set()).update(aliases[value.id])
        if sum(map(len, aliases.values())) == before:
            return aliases


def _entrance_owners(node: ast.AST, aliases: dict[str, set[str]]) -> set[str]:
    """입구 앞 마디가 가리키는 모델들: 이름이면 별칭으로, 속성 사슬(`m.M`·`esgapi.inventory.models.M`)이면 끝 마디로."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id, set())
    if isinstance(node, ast.Attribute) and node.attr in MODEL_ENTRANCE_FILES:
        return {node.attr}
    return set()


def model_entrance_calls(trees: dict[str, ast.Module]) -> dict[tuple[str, str], set[str]]:
    """MODEL_ENTRANCES 의 입구마다 그것을 부르거나 집는 파일(입구 몸의 모델 파일은 뺀다). `<모델>.<입구>` 는 부르든
    집든(`fn = M.used_node_ids`, 인자로 넘김) 세고, `getattr(<모델>, "<입구>")` 와 모델의 별칭(model_aliases)도 센다.
    속성 사슬은 끝 두 마디로 본다(`m.M.used_node_ids` — 모듈을 붙여 부른 꼴, QC4)."""
    calls: dict[tuple[str, str], set[str]] = {key: set() for key in MODEL_ENTRANCES}
    for name, tree in trees.items():
        aliases = model_aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                owners, entrance = _entrance_owners(node.value, aliases), node.attr
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                owners, entrance = _entrance_owners(node.args[0], aliases), node.args[1].value
            else:
                continue
            for owner in owners:
                key = (owner, entrance)
                if key in MODEL_ENTRANCES and name != MODEL_ENTRANCE_FILES[owner]:
                    calls[key].add(name)
    return calls


def test_the_model_entrances_are_called_only_from_their_places() -> None:
    """회사 넘는 사용 중 읽기 둘은 인덱스 선택의 selectors 하나에서만 부른다(분모: 둘 다 실제로 부른다)."""
    assert model_entrance_calls(PRODUCT) == {key: set(places) for key, places in MODEL_ENTRANCES.items()}
    # 자기 시험: 표 밖(actions)에서 부르거나 집으면 그 자리가 잡힌다
    place = "inventory/service/actions/ghg_pool.py"
    for source, entrance in [
        ("CompanyIndexSelection.used_node_ids([1])", "used_node_ids"),
        ("fn = CompanyIndexSelection.used_node_ids", "used_node_ids"),
        ("run(CompanyIndexSelection.used_factor_ids)", "used_factor_ids"),
        ('getattr(CompanyIndexSelection, "used_factor_ids")([1])', "used_factor_ids"),
        ("from esgapi.inventory.models import CompanyIndexSelection as Sel\nSel.used_node_ids([1])", "used_node_ids"),
        ("Sel = CompanyIndexSelection\ndef f():\n    return Sel.used_factor_ids([1])", "used_factor_ids"),
        # QC4 R3-a: 모듈을 붙여 부른 입구 · getattr 의 첫 인자가 속성 사슬
        ("import esgapi.inventory.models as m\nm.CompanyIndexSelection.used_node_ids([1])", "used_node_ids"),
        ("esgapi.inventory.models.CompanyIndexSelection.used_factor_ids([1])", "used_factor_ids"),
        ('getattr(m.CompanyIndexSelection, "used_node_ids")([1])', "used_node_ids"),
        # QC4 R3-b: 함수·메서드 몸 안의 별칭 · 별칭의 별칭 · 다시 대입한 별칭(QC4 검증 B1)
        ("S = InventoryEntryRow\nS = CompanyIndexSelection\nS.used_node_ids([1])", "used_node_ids"),
        ("def f():\n    s = CompanyIndexSelection\n    return s.used_factor_ids([1])", "used_factor_ids"),
        (
            "class A:\n    def f(self):\n        a = CompanyIndexSelection\n        b = a\n"
            "        return b.used_node_ids()",
            "used_node_ids",
        ),
    ]:
        assert model_entrance_calls({place: ast.parse(source)})[("CompanyIndexSelection", entrance)] == {place}, source
    # 안 잡히는 꼴: 다른 모델의 같은 이름 · 회사 범위의 보통 읽기 · 몸의 모델 파일
    for source in [
        "Other.used_node_ids([1])",
        "CompanyIndexSelection.for_company(c).filter(pk=1)",
        "m.Other.used_node_ids([1])",
        "def f():\n    s = Other\n    return s.used_factor_ids([1])",
    ]:
        assert model_entrance_calls({place: ast.parse(source)}) == {key: set() for key in MODEL_ENTRANCES}, source
    body = {"inventory/models.py": ast.parse("CompanyIndexSelection.used_node_ids([1])")}
    assert model_entrance_calls(body) == {key: set() for key in MODEL_ENTRANCES}


def model_entrance_problems(tree: ast.Module, cls: str, name: str) -> list[str]:
    """입구 몸: QuerySet(model=cls) 로 짓고 · deleted_at__isnull=True 로 거르고 · 풀 id 칸 하나만 values_list(flat=True)
    로 낸다. 회사 칸(이름에 company)·.unscoped·다른 칸을 내면 문제."""
    entrance = _function(tree, cls, name)
    problems: list[str] = []
    built = [
        n
        for n in ast.walk(entrance)
        if isinstance(n, ast.Call)
        and _queryset_name(n.func)
        and any(k.arg == "model" and isinstance(k.value, ast.Name) and k.value.id == "cls" for k in n.keywords)
    ]
    if not built:
        problems.append(f"{name}: QuerySet(model=cls) 로 짓지 않는다")
    keywords = {
        (k.arg, k.value.value)
        for n in ast.walk(entrance)
        if isinstance(n, ast.Call)
        for k in n.keywords
        if isinstance(k.value, ast.Constant)
    }
    if ("deleted_at__isnull", True) not in keywords:
        problems.append(f"{name}: deleted_at__isnull=True 조건이 없다")
    outs = [
        n
        for n in ast.walk(entrance)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "values_list"
    ]
    for out in outs:
        columns = [a.value for a in out.args if isinstance(a, ast.Constant)]
        flat = any(
            k.arg == "flat" and isinstance(k.value, ast.Constant) and k.value.value is True for k in out.keywords
        )
        if len(out.args) != 1 or len(columns) != 1 or columns[0] not in POOL_ID_COLUMNS or not flat:
            problems.append(f"{name}: 풀 id 칸 하나만 flat 으로 내지 않는다 {columns}")
    if len(outs) != 1:
        problems.append(f"{name}: values_list 가 하나가 아니다({len(outs)})")
    texts = [n.value for n in ast.walk(entrance) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    if any("company" in text for text in texts):
        problems.append(f"{name}: 회사 칸을 이름으로 부른다")
    if any(isinstance(n, ast.Attribute) and n.attr == "unscoped" for n in ast.walk(entrance)):
        problems.append(f"{name}: .unscoped")
    return problems


def test_the_model_entrances_answer_only_pool_ids() -> None:
    for (cls, name), _places in MODEL_ENTRANCES.items():
        assert model_entrance_problems(PRODUCT[MODEL_ENTRANCE_FILES[cls]], cls, name) == [], name

    # 자기 시험: 회사 칸도 내는 꼴 · 삭제 표시도 세는 꼴을 잡는다
    def body(text: str) -> ast.Module:
        return ast.parse(
            "class CompanyIndexSelection:\n    @classmethod\n    def used_node_ids(cls, ids):\n        return " + text
        )

    good = 'models.QuerySet(model=cls).filter(deleted_at__isnull=True).values_list("facility_node_id", flat=True)'
    assert model_entrance_problems(body(good), "CompanyIndexSelection", "used_node_ids") == []
    company = 'models.QuerySet(model=cls).filter(deleted_at__isnull=True).values_list("company_id", flat=True)'
    assert model_entrance_problems(body(company), "CompanyIndexSelection", "used_node_ids")
    alive = 'models.QuerySet(model=cls).filter(facility_node_id__in=ids).values_list("facility_node_id", flat=True)'
    assert model_entrance_problems(body(alive), "CompanyIndexSelection", "used_node_ids")
