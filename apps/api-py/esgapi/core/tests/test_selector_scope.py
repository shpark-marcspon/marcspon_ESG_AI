"""Selector 가 회사 범위 표를 읽는 문마다 회사 조건이 있는가, Service 는 읽지 않는가. 소스를 AST 로 읽는다(DB 없이).

규칙(esgapi/*/service/selectors/*.py):
  - 회사 칸 표(company_id — Site·User·DocumentRow·JobRow·LlmCallLogRow)는 `<표>.for_company(company_id)` 로만 연다
    (값은 이름 company_id 여야 한다). 뿌리 표(company)는 `<표>.by_subdomain(subdomain)`(이름 붙은 찾기 입구) 또는
    `<표>.for_company(company_id)` 로만. `<표>.objects` 는 0
    (기본 매니저는 조건 없는 조회를 던진다 — core/isolation/managers.py)
  - 회사 칸이 없는 표(전역 자료)를 읽는 파일에는 `# tenant-scope: global` 줄이 있고, 그 파일은 회사 표를 안 읽는다
  - 문 함수(_documents·_jobs)를 부르는 자리는 이름 company_id 하나만 넘긴다
  테넌트 바닥(tenant_id 칸의 표·for_tenant)은 K1u-b 가 지웠다: tenant_id 칸의 표는 0 이다.
규칙(Service): organization·user 의 Service 는 회사 칸 표를, core 의 Service(services/{documents,jobs}.py)는 core 의
  표를 `<표>.for_company(<company_id 또는 행.company_id>)` 로만 열고(`.objects` 는 0), 읽는 끝맺음(first·get·all·
  values…·select_for_update)이 하나도 없다. 읽기는 Selector 를 부른다.

★ 무효 조건: 글자의 꼴만 본다. `<이름>.objects`·`<이름>.for_company` 로 시작하지 않는 읽기(다른 이름에 담아 둔 매니저,
  getattr, 다른 모듈의 함수가 돌려준 QuerySet, 날 SQL)는 보지 못한다(unscoped·숨은 매니저·날 SQL 은
  core/tests/isolation/test_static_rules.py 가 제품 전체에서 본다 — selector 안의 `.unscoped`·숨은 매니저는 여기도
  본다, ISSUE-310). pk 조건이 빠진 것도 보지 않는다
  (그것은 회사의 일이 아니다). 조건이 실제로 남의 행을 거르는지는 업무 층(test_selectors_tenant.py)이,
  앱 역할 연결의 경계는 보안 층(tests/security)이 잰다(DB 에 RLS 는 없다).
"""

import ast
from pathlib import Path

import pytest
from django.apps import apps

ESGAPI = Path(__file__).resolve().parents[2]
GLOBAL_MARK = "# tenant-scope: global"
TENANT_TABLES: set[str] = set()  # 테넌트 바닥(tenant_id 칸)의 표는 K1u-b 가 회사 칸으로 옮겼다
PK_IS_TENANT: set[str] = set()  # 옛 tenants 표(pk 가 곧 테넌트)는 K1u-a 가 걷었다 — 뿌리는 COMPANY_ROOT
GLOBAL_TABLES = {"SourceRow", "FactorRecordRow", "FactorScope3CategoryRow", "MappingRow"}
# K1b-1: 자산/시설 코드 목록(FacilityCode)은 모든 고객사 공통 하나라 회사 칸이 없다(결정 MARC-ENT-469 3) — 격리 표에서
# 빠지는 까닭. 회사 데이터 0, 쓰기는 운영 관리자만(core/permissions.py), 쓰는 회사 행 셈은 자기 회사 것만(ce 덧붙임 ②).
GLOBAL_TABLES.add("FacilityCode")
# K1b-2a: 온실가스 인덱스 풀·시설별 배출계수 풀(표 넷)도 모든 고객사 공통 하나라 회사 칸이 없다(결정 MARC-ENT-469 3) —
# 회사 데이터 0, 쓰기는 운영 관리자만(core/permissions.py 의 inventory_admin_ghg_*). 회사 선택은 K1b-2b 가 판을 잡는다.
GLOBAL_TABLES.update({"GhgIndexNode", "GhgFactor", "GhgFactorVersion", "GhgFactorGas"})
# core·runs 의 회사 칸 표(K1u-b · AU1a 감사 기록 · X1b-1 실행 넷 — 이름은 그대로 CORE_TABLES)
CORE_TABLES = {
    "AuditEventRow",
    "DocumentRow",
    "JobRow",
    "LlmCallLogRow",
    "RunRow",
    "RunStepRow",
    "RunResultRow",
    "RunFileRow",
    "RunSegmentRow",  # RM1a 구획 기록(플랫폼-서버 7a 허락 2026-11-10)
}
CORE_TABLES.update({"DocumentArtifactRow", "DocumentArtifactUseRow"})  # RP2a ① 문서 산출물 둘(플랫폼-서버 e7 허락)
# G1b 검토 둘(백엔드 4d 허락 2026-10-19) · G2c2 AI 설정 판(백엔드 c1 허락 2026-10-19)
GREENWASH_TABLES = {"GreenwashReviewRow", "GreenwashReviewMarkRow", "GreenwashAiSettingRow"}
TRANSLATION_TABLES = {"TranslationAiSettingRow"}  # TR4 AI 설정 판(플랫폼-서버 d9 허락 2026-10-23)
COMPANY_TABLES = {"Site", "User"} | CORE_TABLES | GREENWASH_TABLES  # company_id 칸이 있는 표
COMPANY_TABLES.update(TRANSLATION_TABLES)  # TR4
DATAVERIFY_TABLES = {"DataverifyAiSettingRow"}  # DVA1 AI 설정 판(플랫폼-서버 e5 허락 2026-10-26)
COMPANY_TABLES.update(DATAVERIFY_TABLES)  # DVA1
MATERIALITY_TABLES = {"MaterialityAiSettingRow"}  # IR4 AI 설정 판(플랫폼-서버 e5 허락 2026-10-27)
COMPANY_TABLES.update(MATERIALITY_TABLES)  # IR4
# IRS3 ① 결과 고침 둘(고침 → 머리는 같은 회사 복합 FK — 플랫폼-서버 7a 허락 2026-11-03)
COMPANY_TABLES.update({"MaterialityResultEditHeadRow", "MaterialityResultEditRow"})
COMPANY_TABLES.add("SiteFacility")  # K1b-1 사업장별 자산/시설(사업장과 같은 회사 — 복합 FK)
# K1b-2b 인벤토리 해·고객사 인덱스 선택(선택 → 해는 같은 회사 복합 FK, 풀 잎·판은 공통 표 — e7 허락 10-29)
COMPANY_TABLES.update({"InventoryYear", "CompanyIndexSelection"})
# S12a Scope 1·2 입력 셋(행 → 선택·자산/시설, 값·히스토리 → 행은 같은 회사 복합 FK — e7 허락 10-29)
COMPANY_TABLES.update({"InventoryEntryRow", "InventoryEntryValue", "InventoryEntryHistory"})
# RP1 원고작성 표 넷(프로젝트 → 문서·목차 판 → 마디는 같은 회사 복합 FK — 보고서 감독 처분 · 1-3 알림 2026-10-29)
DRAFTING_TABLES = {"DraftingProject", "DraftingProjectDocument", "DraftingOutline", "DraftingOutlineNode"}
COMPANY_TABLES.update(DRAFTING_TABLES)  # RP1
# S12a-2 입력주기·직접입력 계수(주기 → 선택·사업장, 행·히스토리 → 직접입력은 같은 회사 복합 FK — e7 허락 10-29)
COMPANY_TABLES.update({"InventoryEntryPeriod", "InventoryCustomFactor"})
# S3K2a Scope 3 카테고리 잠금(회사 FK 하나 — 같은 회사 복합 FK 0, runs FK 0 · 플랫폼-서버 7a 허락)
COMPANY_TABLES.add("Scope3CategoryState")
# S3K2b-1 Scope 3 줄 편집 사건(회사 FK 하나 — run_id 는 FK 아님, MARC-ENT-210 · 플랫폼-서버 7a 허락)
COMPANY_TABLES.add("Scope3RowEdit")
COMPANY_TABLES.add("DraftingAiSettingRow")  # RPA1 원고작성 AI 설정 판(플랫폼-서버 7a 허락 2026-10-30)
COMPANY_ROOT = {"Company"}  # 뿌리(범위 칸이 자기 pk)
# 사용자에 딸린 표(K2a): 회사 칸이 없다(운영 관리자의 행은 회사가 없다). 이름 붙은 입구(by_jti 등)로만 열고 그 입구의
# 호출 자리는 core/tests/isolation/test_static_rules.py 의 USER_ENTRANCES 가 지킨다.
# `.objects` 로 읽으면 「모르는 이름」이다.
USER_OWNED = {"RefreshToken"}
OPENERS = {"objects", "for_company", "by_subdomain"}
# operator_rows(감사 기록의 회사 없는 줄 — AU1a)는 여기 없다 — 그 입구를 부르는 자리는 test_static_rules 의
# AUDIT_ENTRANCES 가 지킨다.
GATES = {"_documents", "_jobs", "_runs", "_steps"}  # core·runs 의 표를 여는 문 함수(X1b-1 +2: 실행·단계)
HIDDEN_MANAGERS = {"_default_manager", "_base_manager"}
# selector 안에서 `.unscoped`(회사 범위를 빼는 매니저 — core/isolation/managers.py)를 써도 되는 파일(ESGAPI 기준 경로).
# 지금 0 — 늘릴 때 까닭을 적는다(ISSUE-310).
SELECTOR_UNSCOPED_ALLOWED: frozenset[str] = frozenset()
READ_ENDS = {
    "first",
    "last",
    "get",
    "all",
    "values",
    "values_list",
    "exists",
    "count",
    "order_by",
    "iterator",
    "select_for_update",
}


def selector_files() -> list[Path]:
    return sorted(p for p in ESGAPI.glob("*/service/selectors/*.py") if p.name != "__init__.py")


def _is_name(node: ast.expr, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def reads(source: str) -> list[tuple[str, ast.Attribute, ast.AST | None, ast.AST | None]]:
    """`<이름>.objects`·`<이름>.for_company`·`<이름>.by_subdomain` 자리마다 (이름, 그 노드, 부모, 조부모)."""
    tree = ast.parse(source)
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    found: list[tuple[str, ast.Attribute, ast.AST | None, ast.AST | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in OPENERS:
            name = node.value.id if isinstance(node.value, ast.Name) else "<expr>"
            up = parent.get(node)
            found.append((name, node, up, parent.get(up) if up is not None else None))
    return found


def _filter_call(node: ast.Attribute, up: ast.AST | None, upup: ast.AST | None) -> ast.Call | None:
    if not (isinstance(up, ast.Attribute) and up.value is node and up.attr == "filter"):
        return None
    return upup if isinstance(upup, ast.Call) and upup.func is up else None


def _kw_is_tenant(call: ast.Call, key: str) -> bool:
    return any(kw.arg == key and _is_name(kw.value, "tenant_id") for kw in call.keywords)


def _opener_arg(node: ast.Attribute, up: ast.AST | None, opener: str = "for_company") -> ast.expr | None:
    """`<표>.<opener>(<인자 하나>)` 이면 그 인자(opener 의 기본은 for_company)."""
    if node.attr != opener or not (isinstance(up, ast.Call) and up.func is node):
        return None
    return up.args[0] if len(up.args) == 1 and not up.keywords else None


def _company_problem(name: str, node: ast.Attribute, up: ast.AST | None) -> str | None:
    """회사 바닥의 표를 여는 자리의 문제(없으면 None)."""
    if name in COMPANY_ROOT and node.attr == "by_subdomain":
        arg = _opener_arg(node, up, "by_subdomain")
        return None if arg is not None and _is_name(arg, "subdomain") else ".by_subdomain(subdomain) 로 열지 않는다"
    arg = _opener_arg(node, up, "for_company")
    return None if arg is not None and _is_name(arg, "company_id") else ".for_company(company_id) 로 열지 않는다"


def selector_problems(source: str) -> list[str]:
    marked = any(line.startswith(GLOBAL_MARK) for line in source.splitlines())
    problems: list[str] = []
    for name, node, up, upup in reads(source):
        where = f"{name}.{node.attr} (줄 {node.lineno})"
        call = _filter_call(node, up, upup)
        if name in COMPANY_TABLES | COMPANY_ROOT:
            problem = "전역 표시가 있는 파일이 회사 표를 읽는다" if marked else _company_problem(name, node, up)
            if problem is not None:
                problems.append(f"{where}: {problem}")
        elif node.attr in {"for_company", "by_subdomain"}:
            problems.append(f"{where}: 회사 표가 아닌데 {node.attr} 를 부른다")
        elif name in PK_IS_TENANT:
            if call is None or not _kw_is_tenant(call, "pk"):
                problems.append(f"{where}: .filter(pk=tenant_id) 로 시작하지 않는다")
        elif name in GLOBAL_TABLES:
            if not marked:
                problems.append(f"{where}: 전역 표인데 파일에 표시가 없다")
        else:
            problems.append(f"{where}: 모르는 이름이다")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in GATES:
            alone = len(node.args) == 1 and not node.keywords and _is_name(node.args[0], "company_id")
            if not alone:
                problems.append(f"{node.func.id}(…) (줄 {node.lineno}): 인자가 이름 company_id 하나가 아니다")
        if isinstance(node, ast.Attribute) and node.attr in HIDDEN_MANAGERS:
            problems.append(f".{node.attr} (줄 {node.lineno}): objects 를 거치지 않는 매니저다")
    return problems


def selector_unscoped_problems(rel: str, source: str) -> list[str]:
    """selector 파일(`rel` = ESGAPI 기준 경로)의 `.unscoped` 자리마다 한 줄. 허용 목록의 경로는 0."""
    if rel in SELECTOR_UNSCOPED_ALLOWED:
        return []
    return [
        f".unscoped (줄 {node.lineno}): 회사 범위를 빼는 매니저다"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and node.attr == "unscoped"
    ]


def service_problems(source: str) -> list[str]:
    """core 의 Service: core 의 표는 `<표>.for_company(company_id 또는 <행>.company_id)` 로만 열고 읽지 않는다."""
    tree = ast.parse(source)
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    problems: list[str] = []
    for name, node, up, _upup in reads(source):
        where = f"{name}.{node.attr} (줄 {node.lineno})"
        arg = _opener_arg(node, up)
        named = arg is not None and (
            _is_name(arg, "company_id") or (isinstance(arg, ast.Attribute) and arg.attr == "company_id")
        )
        if name not in CORE_TABLES or not named:
            problems.append(f"{where}: .for_company(company_id 또는 <행>.company_id) 로 열지 않는다")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in READ_ENDS | HIDDEN_MANAGERS:
            problems.append(f".{node.attr} (줄 {node.lineno}): Service 가 읽는다(읽기는 Selector 로)")
    return problems


def company_service_problems(source: str) -> list[str]:
    """organization·user 의 Service: 회사 칸 표는 `<표>.for_company(company_id 또는 <행>.company_id)` 로만 열고
    읽지 않는다."""
    tree = ast.parse(source)
    problems: list[str] = []
    for name, node, up, _upup in reads(source):
        where = f"{name}.{node.attr} (줄 {node.lineno})"
        arg = _opener_arg(node, up, "for_company")
        named = arg is not None and (
            _is_name(arg, "company_id") or (isinstance(arg, ast.Attribute) and arg.attr == "company_id")
        )
        if name not in COMPANY_TABLES - CORE_TABLES or not named:
            problems.append(f"{where}: .for_company(company_id 또는 <행>.company_id) 로 열지 않는다")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in READ_ENDS | HIDDEN_MANAGERS:
            problems.append(f".{node.attr} (줄 {node.lineno}): Service 가 읽는다(읽기는 Selector 로)")
    return problems


def test_company_services_only_write_and_name_the_company() -> None:
    opened: dict[str, int] = {}
    for name in (
        "organization/service/services/organization.py",
        "organization/service/services/branches.py",  # K1b-1
        "inventory/service/services/index_selection.py",  # K1b-2b
        "inventory/service/services/entries.py",  # S12a
        "user/service/services/user.py",
        "user/service/services/login.py",
    ):
        source = (ESGAPI / name).read_text()
        opened[name] = len(reads(source))
        assert company_service_problems(source) == [], name
    # 분모: 쓰는 문의 수(사업장 create 하나 · 사용자 update_or_create 하나와 고객사 사용자 create 하나(K2a) ·
    # login 은 0 — 사용자 행은 Selector 가 잠가 읽은 행을 save, refresh 행은 RefreshToken 의 입구)
    assert opened == {
        "organization/service/services/organization.py": 0,  # K1b-1: 사업장 create 는 services/branches.py 로
        "organization/service/services/branches.py": 7,  # K1b-1: 만들기·고침·토글·삭제 표시 둘·자산/시설·본사 세우기
        "inventory/service/services/index_selection.py": 5,  # K1b-2b: 해·선택·숨김·삭제 표시 · S12a: 자릿수
        # S12a: 행 둘·값 둘·히스토리·삭제 표시·메모·잠금 · S12a-2 +3: 주기·직접입력·행 계수
        "inventory/service/services/entries.py": 11,
        "user/service/services/user.py": 2,
        "user/service/services/login.py": 0,
    }
    assert company_service_problems("Site.for_company(company_id).filter(pk=x).first()")
    assert company_service_problems("Site.for_company(other).create(name=n)")
    assert company_service_problems("Site.objects.create(company_id=company_id)")
    assert company_service_problems("Site.for_company(company_id).create(name=n)") == []


def test_the_tenant_tables_are_the_ones_we_know() -> None:
    with_column: set[str] = set()
    with_company: set[str] = set()
    without: set[str] = set()
    for model in apps.get_models():
        if not model.__module__.startswith("esgapi."):
            continue
        names = {field.attname for field in model._meta.concrete_fields}
        (with_column if "tenant_id" in names else without).add(model.__name__)
        if "company_id" in names:
            with_company.add(model.__name__)
    assert with_column == TENANT_TABLES == set()  # 테넌트 바닥의 표 0
    assert with_company == COMPANY_TABLES and len(COMPANY_TABLES) == 36  # 분모(AU1a +1 · X1b-1 +4 · G1b +2 · G2c2 +1)
    # · RM1a +1: RunSegmentRow
    # · TR4 +1: TranslationAiSettingRow
    # · DVA1 +1: DataverifyAiSettingRow
    # · IR4 +1: MaterialityAiSettingRow
    # · K1b-1 +1: SiteFacility(감독 허락 10-28 — 발주서 「:238 0줄」을 고침)
    # · K1b-2b +2: InventoryYear·CompanyIndexSelection
    # · S12a +3: InventoryEntryRow·InventoryEntryValue·InventoryEntryHistory
    # · RP1 +4: 원고작성 표 넷
    # · RP2a +2: 문서 산출물 둘(DocumentArtifactRow·DocumentArtifactUseRow)
    # · S12a-2 +2: InventoryEntryPeriod·InventoryCustomFactor
    # · RPA1 +1: DraftingAiSettingRow
    # · S3K2a +1: Scope3CategoryState
    # · IRS3 +2: MaterialityResultEditHeadRow·MaterialityResultEditRow
    # · S3K2b-1 +1: Scope3RowEdit
    assert without == PK_IS_TENANT | GLOBAL_TABLES | COMPANY_TABLES | COMPANY_ROOT | USER_OWNED


def test_only_files_without_tenant_tables_are_marked_global() -> None:
    files = {str(path.relative_to(ESGAPI)): path.read_text() for path in selector_files()}
    assert sorted(files) == [  # 분모: Selector 파일 열(G1b +1). 늘면 여기가 빨개져 새 파일의 조회를 보게 한다
        "core/service/selectors/audit.py",
        "core/service/selectors/documents.py",
        "core/service/selectors/llm_logs.py",  # RX1a
        "core/service/selectors/llm_usage.py",
        "dataverify/service/selectors/ai_settings.py",  # DVA1
        "dataverify/service/selectors/run_extras.py",  # DVA1 ③
        "drafting/service/selectors/ai_settings.py",  # RPA1
        "drafting/service/selectors/projects.py",  # RP1
        "drafting/service/selectors/run_extras.py",  # RPA1 ②
        "greenwash/service/selectors/ai_settings.py",  # G2c2
        "greenwash/service/selectors/review.py",  # G1b(③ 에서 checks.py 하나 더)
        "greenwash/service/selectors/run_extras.py",  # AD4S
        "inventory/service/selectors/entries.py",  # S12a ②(회사 범위 — 표시 없음)
        "inventory/service/selectors/ghg_pool.py",  # K1b-2a ②(공통 풀 — 전역 표시)
        "inventory/service/selectors/index_selection.py",  # K1b-2b ②(회사 범위 — 표시 없음)
        "inventory/service/selectors/scope3_edits.py",  # S3K2b-1
        "inventory/service/selectors/scope3_state.py",  # S3K2a ①(회사 범위 — 표시 없음)
        "materiality/service/selectors/ai_settings.py",  # IR4
        "materiality/service/selectors/edits.py",  # IRS3 ①
        "materiality/service/selectors/run_extras.py",  # IR4 ③
        "organization/service/selectors/branches.py",  # K1b-1
        "organization/service/selectors/facility_codes.py",  # K1b-1 ②(공통 코드 목록 — 전역 표시)
        "organization/service/selectors/organization.py",
        "reference/service/selectors/reference.py",
        "runs/service/selectors/bundle.py",  # RX1a
        "runs/service/selectors/jobs.py",
        "runs/service/selectors/operator.py",
        "runs/service/selectors/runs.py",
        "translation/service/selectors/ai_settings.py",  # TR4
        "translation/service/selectors/run_extras.py",  # TR4 ③
        "user/service/selectors/user.py",
    ]
    marked = [
        name for name, source in files.items() if any(line.startswith(GLOBAL_MARK) for line in source.splitlines())
    ]
    assert marked == [
        "inventory/service/selectors/ghg_pool.py",  # K1b-2a: 회사 칸 없는 공통 풀 표 넷(MARC-ENT-469 3)
        "organization/service/selectors/facility_codes.py",  # K1b-1: 회사 칸 없는 공통 코드 목록(MARC-ENT-469 3)
        "reference/service/selectors/reference.py",
    ]
    for name in marked:
        scoped = TENANT_TABLES | PK_IS_TENANT | COMPANY_TABLES | COMPANY_ROOT
        assert [table for table, *_ in reads(files[name]) if table in scoped] == [], name


@pytest.mark.parametrize("path", selector_files(), ids=lambda p: str(p.relative_to(ESGAPI)))
def test_selectors_scope_every_read(path: Path) -> None:
    source = path.read_text()
    assert reads(source), "이 파일에서 .objects·.for_company·.by_subdomain 을 하나도 못 찾았다"
    assert selector_problems(source) == []
    assert selector_unscoped_problems(str(path.relative_to(ESGAPI)), source) == []


# RP2a ①(처분 ① 가): service/selectors 밖의 읽기 포트 — 문서 산출물(core/documents/selectors.py)도 같은 규칙으로 훑는다
DOCUMENT_ARTIFACT_SELECTORS = "core/documents/selectors.py"


def test_the_document_artifact_selectors_scope_every_read() -> None:
    source = (ESGAPI / DOCUMENT_ARTIFACT_SELECTORS).read_text()
    assert reads(source), "이 파일에서 .objects·.for_company·.by_subdomain 을 하나도 못 찾았다"
    assert selector_problems(source) == []
    assert selector_unscoped_problems(DOCUMENT_ARTIFACT_SELECTORS, source) == []


def test_the_unscoped_checker_catches_what_it_should() -> None:
    """ISSUE-310: `selector_problems` 는 여는 꼴(objects·for_company·by_subdomain)만 보아 `.unscoped` 를 지나친다."""
    rel = "runs/service/selectors/runs.py"
    assert selector_problems("RunRow.unscoped.filter(pk=x)") == []  # 그래서 따로 본다
    assert selector_unscoped_problems(rel, "RunRow.unscoped.filter(pk=x)") == [
        ".unscoped (줄 1): 회사 범위를 빼는 매니저다"
    ]
    assert selector_unscoped_problems(rel, "x = 1\nDocumentRow.unscoped.all()") == [
        ".unscoped (줄 2): 회사 범위를 빼는 매니저다"
    ]
    assert selector_unscoped_problems(rel, "RunRow.for_company(company_id).filter(pk=x)") == []


def test_the_unscoped_allow_list_is_by_path(monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = "runs/service/selectors/fake.py"
    monkeypatch.setattr(f"{__name__}.SELECTOR_UNSCOPED_ALLOWED", frozenset({allowed}))
    assert selector_unscoped_problems(allowed, "RunRow.unscoped.filter(pk=x)") == []
    assert selector_unscoped_problems("runs/service/selectors/runs.py", "RunRow.unscoped.filter(pk=x)")


def test_core_services_only_write_and_name_the_tenant() -> None:
    opened: dict[str, int] = {}
    for name, folder in (
        ("documents", "core/service/services"),
        ("jobs", "runs/service/services"),
        ("audit", "core/service/services"),
        ("runs", "runs/service/services"),
    ):
        source = (ESGAPI / folder / f"{name}.py").read_text()
        opened[name] = len(reads(source))
        assert service_problems(source) == [], name
    # 분모: 쓰는 문의 수(create 둘·update 넷 · AU1a 감사 create 하나 · X1b-1 실행기의 쓰는 문 여섯 — 잡기·울타리·단계·
    # 파일·끝내기·결과 · X1b-2a 문서 고치기(PATCH)의 update 하나 · RX1a 넣기 셋(import_document create·set_imported_etag
    # update·restore_document_times update) · RM1a 구획 쓰기 둘(segments_planned 의 create·_segment_guard 의 update) ·
    # RM1b ② 실행 쓰기 둘(_wake 의 update·segment_end Fatal 의 실행 failed update))
    assert opened == {"documents": 7, "jobs": 3, "audit": 1, "runs": 10}


def test_row_locks_live_in_selectors_only() -> None:
    hits: list[str] = []
    for path in ESGAPI.rglob("*.py"):
        if "/tests/" in str(path):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Attribute) and node.attr == "select_for_update":
                hits.append(str(path.relative_to(ESGAPI)))
    assert sorted(hits) == [
        "core/service/selectors/documents.py",
        "dataverify/service/selectors/ai_settings.py",  # DVA1: 회사의 판 행 잠금(lock_settings — 적용 바꾸기)
        "drafting/service/selectors/ai_settings.py",  # RPA1: 회사의 판 행 잠금(lock_settings — 적용 바꾸기)
        "drafting/service/selectors/projects.py",  # RP1: 프로젝트 행 잠금(lock_project — 목차 판 번호 매김)
        "greenwash/service/selectors/ai_settings.py",  # G2c2: 회사의 판 행 잠금(lock_settings — 적용 바꾸기)
        "greenwash/service/selectors/review.py",  # G1b: 검토 행의 잠금(lock_review — 규칙 7)
        "inventory/service/selectors/entries.py",  # S12a: 입력 행 잠금(lock_rows — 저장이 선택 잠금 뒤 그 사업장의 행)
        "inventory/service/selectors/ghg_pool.py",  # K1b-2a: 계수 정체 잠금(lock_factor — 고치기의 새 판 번호)
        "inventory/service/selectors/ghg_pool.py",  # K1b-2a: 노드 잠금(lock_nodes — 잎 기본·부모 아래 만들기·지우기)
        "inventory/service/selectors/index_selection.py",  # K1b-2b: 해 행 잠금(lock_year — 저장 둘을 줄 세움)
        "inventory/service/selectors/index_selection.py",  # S12a: 선택 행 잠금(lock_selection — 입력·지움·메모·잠금)
        "inventory/service/selectors/scope3_state.py",  # S3K2a: 카테고리 잠금 행(lock_row — 걸기·풀기를 줄 세움)
        "materiality/service/selectors/ai_settings.py",  # IR4: 회사의 판 행 잠금(lock_settings — 적용 바꾸기)
        "organization/service/selectors/branches.py",  # K1b-1: PUT 의 사업장 행 잠금(lock_branch)
        "organization/service/selectors/branches.py",  # S12a ④: 일괄 지움의 사업장 행 잠금(lock_branches — id 차례)
        "runs/service/selectors/jobs.py",
        "runs/service/selectors/runs.py",  # X1b-1: 실행 행의 잠금(lock_run — 감독 처분 sid:MARC-TICK-179)
        "translation/service/selectors/ai_settings.py",  # TR4: 회사의 판 행 잠금(lock_settings — 적용 바꾸기)
        # K2a: 사용자 행(고객사·운영 관리자 두 갈래)과 refresh 행의 잠금 — 한 파일에 세 자리
        "user/service/selectors/user.py",
        "user/service/selectors/user.py",
        "user/service/selectors/user.py",
    ]


def test_the_checker_catches_what_it_should() -> None:
    assert selector_problems("DocumentRow.objects.all()")
    assert selector_problems("DocumentRow.objects.filter(company_id=company_id)")
    assert selector_problems("DocumentRow.for_company(1)")
    assert selector_problems("DocumentRow.for_company(other)")
    assert selector_problems("# tenant-scope: global\nSite.for_company(company_id)")
    assert selector_problems("# tenant-scope: global\nDocumentRow.for_company(company_id)")
    assert selector_problems("Whatever.objects.filter(company_id=company_id)")
    assert selector_problems("Whatever.for_company(company_id)")
    assert selector_problems("_documents(1)")
    assert selector_problems("_jobs(other)")
    assert selector_problems("JobRow._default_manager.filter(company_id=company_id)")
    assert service_problems("JobRow.for_company(company_id).filter(pk=x).first()")
    assert service_problems("JobRow.objects.filter(pk=x, company_id=company_id).update(a=1)")
    assert service_problems("JobRow.for_company(other).filter(pk=x).update(a=1)")
    assert service_problems("Site.for_company(company_id).create(name=n)")  # core 의 Service 는 core 의 표만
    assert company_service_problems("JobRow.for_company(company_id).create(kind=k)")  # 거꾸로도
    assert selector_problems("Company.objects.filter(pk=company_id)")
    assert selector_problems("Company.for_company(1)")
    assert selector_problems("Company.by_subdomain(other)")
    assert selector_problems("DocumentRow.by_subdomain(subdomain)")
    assert selector_problems("# tenant-scope: global\nCompany.by_subdomain(subdomain)")
    assert selector_problems("Company.by_subdomain(subdomain)") == []
    assert selector_problems("Company.for_company(company_id)") == []
    assert selector_problems("DocumentRow.for_company(company_id)") == []
    assert selector_problems("_documents(company_id)") == []
    assert service_problems("JobRow.for_company(company_id).filter(pk=x).update(a=1)") == []
    assert service_problems("JobRow.for_company(locked.company_id).create(kind=k)") == []
