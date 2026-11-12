"""회사 범위 표의 기본 매니저(받침 ②, core/isolation/managers.py)가 회사를 정하지 않은 조회와 다른 회사로의 쓰기를
거절하는가. 바닥은 하나다(회사 바닥 — company_id 숫자와 뿌리 company. 테넌트 바닥은 K1u-b 가 지웠다).

순수 몫(DB 없이): 던지는 것은 문이 나가기 전이다. pytest-django 가 이 층에서 DB 를 막으므로 문이 나가면 다른 오류로
빨개진다. 업무 몫(django_db, 주인 역할 연결): 범위가 사슬 끝까지 남고 SQL 에 조건이 있는가.

범위 모델은 등록부에서 읽는다(뿌리이거나 company_id 칸이 있는 모델. core 는 user·organization 을 import 하지 않는다 —
.importlinter 「가」).
★ 무효 조건: 이 파일은 매니저의 길만 잰다. _base_manager(정방향 외래 키·save·refresh)와 생성자 + save() 는 안 막힌다
  (managers.py 의 머리말) — 제품 코드에 그 길이 없는지는 test_static_rules.py 가,
  DB 의 같은 회사 외래 키는 보안 층이 잰다.
"""

import re
from typing import cast

import pytest
from django.apps import apps
from django.db import connection, models, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.isolation.managers import (
    CompanyRootManager,
    CompanyRootModel,
    CompanyScopedManager,
    CompanyScopedModel,
    CrossCompanyWriteError,
    UnscopedQueryError,
)
from esgapi.core.models import DocumentRow
from esgapi.runs.models import JobRow
from tests.support import tokens
from tests.support.http import login


def test_no_model_keeps_the_tenant_column() -> None:
    """테넌트 바닥(tenant_id 글자 칸)의 모델은 0 이다. 분모: 회사 칸(company_id)이 있는 모델은 열."""
    fields = [
        {f.attname for f in model._meta.concrete_fields}
        for model in apps.get_models()
        if model.__module__.startswith("esgapi.")
    ]
    assert [names for names in fields if "tenant_id" in names] == []
    # G2c2 +1: 그린워싱 AI 설정 판(GreenwashAiSettingRow)
    assert (
        len([names for names in fields if "company_id" in names]) == 36
    )  # 분모(AU1a +1: AuditEventRow · X1b-1 +4: 실행 넷 · G1b +2: 그린워싱 검토 둘 · TR4 +1 · DVA1 +1 · IR4 +1)
    # · S12a +3: Scope 1·2 입력 행·값·히스토리
    # · K1b-1 +1: SiteFacility
    # · RM1a +1: RunSegmentRow(구획 기록 — 플랫폼-서버 7a 허락 2026-11-10)
    # · K1b-2b +2: InventoryYear·CompanyIndexSelection(inventory 의 첫 회사 범위 표 — 플랫폼-서버 e7 허락 2026-10-29)
    # · RP1 +4: 원고작성 표 넷(DraftingProject·DraftingProjectDocument·DraftingOutline·DraftingOutlineNode)
    # · RP2a +2: 문서 산출물 둘(DocumentArtifactRow·DocumentArtifactUseRow — 플랫폼-서버 e7 허락 2026-10-29)
    # · S12a-2 +2: InventoryEntryPeriod·InventoryCustomFactor(입력주기·직접입력 계수 — 플랫폼-서버 e7 허락 2026-10-29)
    # · RPA1 +1: DraftingAiSettingRow(원고작성 AI 설정 판 — 플랫폼-서버 7a 허락 2026-10-30)
    # · S3K2a +1: Scope3CategoryState(Scope 3 카테고리 잠금 — 플랫폼-서버 7a 허락)
    # · IRS3 +2: MaterialityResultEditHeadRow·MaterialityResultEditRow(결과 고침 둘 — 플랫폼-서버 7a 허락 2026-11-03)
    # · S3K2b-1 +1: Scope3RowEdit(Scope 3 줄 편집 사건 — 플랫폼-서버 7a 허락 2026-11-04)


def test_a_reverse_relation_is_refused_too() -> None:
    reverse = "jobs"  # JobRow.document 의 related_name
    document = DocumentRow(pk=1, company_id=1)  # 관계 매니저는 pk 가 있는 행에서만 열린다(BigAuto 는 저장 때 매긴다)
    with pytest.raises(UnscopedQueryError):
        getattr(document, reverse).all()


def document(company_id: int, name: str) -> DocumentRow:
    return DocumentRow.for_company(company_id).create(
        uploaded_by="u-1", file_name=name, storage_key=f"{company_id}/{name}", size_bytes=1, status="uploaded"
    )


@pytest.mark.django_db
def test_for_company_fills_the_company_on_create(companies: tuple[int, int]) -> None:
    a, b = companies
    row = document(a, "a.pdf")
    assert row.company_id == a
    assert DocumentRow.unscoped.filter(company_id=a).count() == 1
    assert DocumentRow.unscoped.count() == 1  # 분모: B 에는 0
    assert DocumentRow.unscoped.filter(company_id=b).count() == 0


@pytest.mark.django_db
def test_the_scope_survives_filter_order_by_and_select_for_update(companies: tuple[int, int]) -> None:
    a, b = companies
    for company_id, name in ((a, "a.pdf"), (b, "b.pdf"), (b, "c.pdf")):
        mine = document(company_id, name)
        JobRow.for_company(company_id).create(document=mine, kind="parse", status="queued", attempts=0)
    assert JobRow.unscoped.count() == 3  # 분모
    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        rows = list(JobRow.for_company(a).filter(status="queued").order_by("id").select_for_update())
    assert [row.company_id for row in rows] == [a]
    selects = [q["sql"] for q in queries.captured_queries if q["sql"].startswith("SELECT")]
    assert len(selects) == 1
    assert re.search(rf'"run_jobs"\."company_id" = {a}\b', selects[0])  # \b: A 가 1 이면 10 은 아니다
    assert "FOR UPDATE" in selects[0]


@pytest.mark.django_db
def test_a_user_in_another_company_is_not_overwritten(client: Client, tenants: None) -> None:
    """B 회사에 같은 sub 의 사용자가 있을 때 A 의 토큰으로 교환: upsert_user 의 조회가 A 로 걸러져 못 찾고 A 에 새로
    만든다 → 200(처분 2 ㉡ — 같은 sub 라도 회사마다 별개 사용자. 옛 409 를 뒤집음). B 의 행은 그대로(주인 역할 연결).
    user 의 함수는 HTTP 로 부른다(core 는 user·organization 을 import 하지 않는다 — 표는 등록부에서 꺼낸다)."""
    login(Client(), sub="edk-user-1", tenant_id="tenant-b", name="나담당", role="viewer")
    users = apps.get_model("user", "User")._meta.managers_map["unscoped"]
    companies = apps.get_model("organization", "Company")._meta.managers_map["unscoped"]
    a = companies.get(subdomain="tenant-a").pk
    b = companies.get(subdomain="tenant-b").pk
    fields = ("company_id", "username", "name", "level")
    before = list(users.values_list(*fields))
    assert before == [(b, "edk-user-1", "나담당", 79)]  # 분모: 이 연결에는 모든 회사의 행이 보인다
    token = tokens.edk_token(sub="edk-user-1", tenant_id="tenant-a", name="가담당", role="admin")
    response = client.post("/api/auth/exchange", data={"token": token}, content_type="application/json")
    assert response.status_code == 200
    after = sorted(users.values_list(*fields))
    assert after == sorted([(a, "edk-user-1", "가담당", 99), *before])  # 회사마다 하나씩 둘, B 의 행은 그대로


# ── 회사 바닥(K1u-a. core 의 세 표는 K1u-b 가 더했다) ──────────────────
# 회사 범위 모델 = 뿌리(CompanyRootModel) 이거나 company_id 칸이 있는 모델. 등록부에서 읽는다
# (core 는 organization·user 를 import 하지 않는다).

CompanyModel = type[CompanyRootModel] | type[CompanyScopedModel]


def company_models() -> list[CompanyModel]:
    found: list[CompanyModel] = []
    for model in apps.get_models():
        if not model.__module__.startswith("esgapi."):
            continue
        if issubclass(model, CompanyRootModel):
            found.append(model)
        elif "company_id" in {f.attname for f in model._meta.concrete_fields}:
            assert issubclass(model, CompanyScopedModel), model.__name__
            found.append(model)
    return sorted(found, key=lambda m: m.__name__)


COMPANY_SCOPED = company_models()
# 범위로 받지 않는 값: 0·음수·bool(int 의 하위 타입)·숫자 글자·빈 글자·None
BAD_COMPANY_IDS: tuple[object, ...] = (0, -1, True, "1", "", None)
UNSCOPED_COMPANY_CALLS = ("all", "filter", "create", "count")


def test_the_company_models_are_the_ones_we_know() -> None:
    assert [m.__name__ for m in COMPANY_SCOPED] == [
        "AuditEventRow",  # AU1a(감독 처분 2026-10-19)
        "Company",
        "CompanyIndexSelection",  # K1b-2b 고객사 인덱스 선택·인벤토리 해(플랫폼-서버 e7 허락 2026-10-29)
        "DataverifyAiSettingRow",  # DVA1 AI 설정 판(플랫폼-서버 e5 허락 2026-10-26)
        "DocumentArtifactRow",  # RP2a ① 문서 산출물 둘(플랫폼-서버 e7 허락 2026-10-29)
        "DocumentArtifactUseRow",
        "DocumentRow",
        "DraftingAiSettingRow",  # RPA1 AI 설정 판(플랫폼-서버 7a 허락 2026-10-30)
        "DraftingOutline",  # RP1 원고작성 표 넷(보고서 감독 처분 · 1-3 알림 2026-10-29)
        "DraftingOutlineNode",
        "DraftingProject",
        "DraftingProjectDocument",
        "GreenwashAiSettingRow",  # G2c2 AI 설정 판(백엔드 c1 허락 2026-10-19)
        "GreenwashReviewMarkRow",  # G1b 검토 둘(백엔드 4d 허락 2026-10-19)
        "GreenwashReviewRow",
        "InventoryCustomFactor",  # S12a-2 직접입력 계수·입력주기(플랫폼-서버 e7 허락 2026-10-29)
        "InventoryEntryHistory",  # S12a Scope 1·2 입력 셋(플랫폼-서버 e7 허락 2026-10-29)
        "InventoryEntryPeriod",  # S12a-2
        "InventoryEntryRow",
        "InventoryEntryValue",
        "InventoryYear",
        "JobRow",
        "LlmCallLogRow",
        "MaterialityAiSettingRow",  # IR4 AI 설정 판(플랫폼-서버 e5 허락 2026-10-27)
        "MaterialityResultEditHeadRow",  # IRS3 결과 고침 둘(플랫폼-서버 7a 허락 2026-11-03)
        "MaterialityResultEditRow",
        "RunFileRow",  # X1b-1 실행 넷(감독 처분 2026-10-19)
        "RunResultRow",
        "RunRow",
        "RunSegmentRow",  # RM1a 구획 기록(플랫폼-서버 7a 허락 2026-11-10)
        "RunStepRow",
        "Scope3CategoryState",  # S3K2a Scope 3 카테고리 잠금(플랫폼-서버 7a 허락)
        "Scope3RowEdit",  # S3K2b-1 Scope 3 줄 편집 사건(플랫폼-서버 7a 허락)
        "Site",
        "SiteFacility",  # K1b-1 사업장별 자산/시설(플랫폼-서버 ce 허락 2026-10-28 — 코드 목록은 회사 칸이 없어 안 듦)
        "TranslationAiSettingRow",  # TR4 AI 설정 판(플랫폼-서버 e5 허락 2026-10-23)
        "User",
    ]


@pytest.mark.parametrize("model", COMPANY_SCOPED, ids=lambda m: m.__name__)
@pytest.mark.parametrize("call", UNSCOPED_COMPANY_CALLS)
def test_an_unscoped_company_query_is_refused_before_the_db(model: CompanyModel, call: str) -> None:
    with pytest.raises(UnscopedQueryError):
        match call:
            case "all":
                model.objects.all()
            case "filter":
                model.objects.filter(pk=1)
            case "create":
                model.objects.create()
            case _:
                model.objects.count()


@pytest.mark.parametrize("model", COMPANY_SCOPED, ids=lambda m: m.__name__)
@pytest.mark.parametrize("bad", BAD_COMPANY_IDS, ids=repr)
def test_a_bad_company_id_is_refused_before_the_db(model: CompanyModel, bad: object) -> None:
    with pytest.raises(UnscopedQueryError):
        model.for_company(cast("int", bad))  # 타입 검사기를 지나도 실행에서 거절한다


@pytest.mark.parametrize("model", COMPANY_SCOPED, ids=lambda m: m.__name__)
def test_the_company_default_manager_is_the_refusing_one(model: CompanyModel) -> None:
    assert model._default_manager is model.objects
    assert isinstance(model.objects, CompanyRootManager | CompanyScopedManager)
    assert type(model._meta.managers_map["unscoped"]) is models.Manager


# 회사 칸 모델(뿌리 Company 는 뺀다 — 범위 칸이 자기 id 라 「다른 회사로 쓰기」가 없다).
COMPANY_FIELD_MODELS = [m for m in COMPANY_SCOPED if issubclass(m, CompanyScopedModel)]


@pytest.mark.parametrize("model", COMPANY_FIELD_MODELS, ids=lambda m: m.__name__)
def test_a_write_for_another_company_is_refused_before_the_db(model: type[CompanyScopedModel]) -> None:
    scope = model.for_company(1)
    with pytest.raises(CrossCompanyWriteError):
        scope.create(company_id=2)
    with pytest.raises(CrossCompanyWriteError):
        scope.filter(pk=1).update(company_id=2)
    with pytest.raises(CrossCompanyWriteError):
        scope.bulk_create([model(company_id=2)])
    # company= 로는 같은 회사여도 받지 않는다(company_id= 로만)
    company = apps.get_model("organization", "Company")
    with pytest.raises(CrossCompanyWriteError):
        scope.create(company=company(pk=1))
