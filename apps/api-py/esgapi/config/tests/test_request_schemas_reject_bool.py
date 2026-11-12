"""요청 본문의 정수 칸은 불리언을 받지 않는다. `api` 에 걸린 경로의 본문 스키마를 전부(중첩까지) 훑어 잰다.

파이썬에서는 `True == 1` 이라 느슨한 `int` 칸과 정수 `Literal` 칸이 `true` 를 1 로 받는다(pydantic 2.13.5 로 잰 것:
엄격한 `int` 는 거절, 엄격한 `Literal[1, 2]` 는 1 로 받음, 느슨한 것은 둘 다 받음). 막는 장치는 둘이다:
`core.schemas.StrictIn`(strict=True)·`StrictInt`, 그리고 정수 Literal 에 붙이는 `core.schemas.NotBool`.
새 스키마가 그것을 빠뜨리면 여기서 걸린다(칸의 이름을 낸다).

재는 법: 모델마다 그 칸 하나에만 `true` 를 넣어 검증하고, 그 칸의 자리에 오류가 났는지 본다
(다른 칸의 「없음」 오류는 무관).
못 보는 것: 쿼리 인자(문자열로 온다), `dict` 의 키, 판별 유니온의 판별 칸, `Any`·`object` 로 적은 칸.
중첩 TypedDict 는 훑는다(MARC-ISSUE-92, 밴드 E2) — StrictIn 의 strict 가 거기 내려가지 않으므로 그 꼴 하나로 잰다.

순수 층: DB 에 닿지 않는다. core 의 테스트가 아니라 여기 있는 까닭: core 는 업무 모듈을 import 하지 않는다(계약 가).
"""

import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints, is_typeddict

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from esgapi.config.api import api

# 훑은 수(분모). 본문을 받는 경로나 그 스키마의 정수 칸이 늘면 이 수를 고친다(늘어난 칸이 걸러지는지 본 뒤에).
BODY_OPERATIONS = 58  # K2a +4: 로그인·refresh·revoke·비밀번호 바꾸기 · K2c +2: 사용자 만들기·초기화 · UA1 +1: 수정
# · S3K2b-1 +2: Scope 3 제외·복구
# · S3K2b-2 +1: Scope 3 계수 수정
# · X1b-2a +1: 문서 고치기(PATCH /documents/{id}) — 감독 c1 허락
# · G2c2 +2: AI 설정 판 저장·적용(POST /ai-settings/greenwash · PUT /ai-settings/greenwash/applied) — 감독 c1 허락
# · TR4 +2: 영문번역 AI 설정 판 저장·적용(POST /ai-settings/translation · PUT …/applied) — 플랫폼-서버 d9 허락
# · DVA1 +2: 데이터 검증 AI 설정 판 저장·적용(POST /ai-settings/dataverify · PUT …/applied) — 플랫폼-서버 e5 허락
# · IR4 +2: 중대성평가 IRO AI 설정 판 저장·적용(POST /ai-settings/materiality · PUT …/applied) — 플랫폼-서버 e5 허락
# · K1b-1 +7: 사업장 만들기·저장·토글·삭제 · 코드 만들기·고침·삭제 — 플랫폼-서버 ce 허락 (다)
# · K1b-2a +8: 노드 만들기·이름·지우기 · 잎 만들기·저장 · 계수 만들기·고침·지우기 — 플랫폼-서버 dc 허락 H6
# · K1b-2b +1: 인덱스 선택 저장(PUT /inventory/scope12/index-selections/{year}) — 플랫폼-서버 e7 허락 H6
# · S12a +4: 행 저장·행 지움·메모·자릿수(PUT …/sites/{site_id}/rows · POST …/rows/delete · PUT …/memo ·
#   PUT …/decimals) — 플랫폼-서버 e7 허락 H6
# · RP1 +3: 원고작성 프로젝트 만들기·문서 달기·목차 넣기(POST /drafting/projects · PUT …/document · PUT …/outline)
# · S12a-2 +3: 입력주기·행 계수 바꿈·복구(PUT …/sites/{site_id}/period · PUT …/rows/{row_id}/factor ·
#   POST …/history/{history_id}/restore) — 플랫폼-서버 e7 허락 H6
# · RPA1 +2: 원고작성 AI 설정 판 저장·적용(POST /ai-settings/drafting · PUT …/applied) — 플랫폼-서버 7a 허락
# · IRS3 +1: 결과 고침 저장(POST /materiality/runs/{run_id}/result/edits) — 7a 허락
# G2c2 +5: GreenwashAiSettingCreate·GreenwashAiSettingApply + 처음 본문에 오는 GreenwashCriteria·GreenwashCriterionRow·
#   GreenwashCriterionGuideline · 정수 칸 +2: GreenwashAiSettingApply.id·GreenwashCriterionRow.order
# K2a +3: LoginIn·RefreshIn(둘이 같이 씀)·PasswordChangeIn · K2c +2: UserCreateIn·PasswordResetIn
# E2 +1: 중첩 TypedDict GreenwashReviewMark(ISSUE-92) · UA1 +1: UserUpdateIn · X1b-2a +1: DocumentPatchIn(감독 c1 허락)
# AS2b +2: 중첩 TypedDict AiModelSettingsIn·AiModelStepIn(GreenwashAiSettingCreate.modelSettings — 감독 f6 허락)
# G1b-3 +1: 중첩 TypedDict GreenwashReviewEditIn(GreenwashReviewUpdate.edits — 감독 dd·4f 허락) · 정수 칸 +1: itemIndex
REQUEST_MODELS = 83  # AS3a-2 +3: 중첩 AiPromptsIn·AiPromptStepIn·AiPromptIn(…Create.prompts) · G2d +1: GreenwashTermIn
# GRJ1 +2: GreenwashReviewEvidenceIn·GreenwashEvidenceAdded(검토 PUT 본문 evidence)
# · RM1c ③ +1: RunRetrySegmentsIn(RunIn.retrySegments) · 정수 칸 +1: fromRunId(7a 허락)
# · S3K2b-1 +1: Scope3RowEditIn
# · S3K2b-2 +2: Scope3RowEditFactorIn·Scope3RowEditCustomIn
# TR4 +2: TranslationAiSettingCreate·TranslationAiSettingApply · 정수 칸 +1: TranslationAiSettingApply.id
# DVA1 +2: DataverifyAiSettingCreate·DataverifyAiSettingApply · 정수 칸 +1: DataverifyAiSettingApply.id
# IR4 +2: MaterialityAiSettingCreate·MaterialityAiSettingApply · 정수 칸 +1: MaterialityAiSettingApply.id
# K1b-1 +6: BranchCreateIn·BranchSaveIn·BranchFacilityIn·BranchInventoryIn·BranchIdsIn·FacilityCodeNameIn
#   · 정수 칸 +4: BranchFacilityIn.id·facilityCodeId · BranchInventoryIn.ids·BranchIdsIn.ids(목록의 정수)
# K1b-2a +8: GhgNodeCreateIn·GhgNodeRenameIn·GhgIdsIn·GhgFacilityCreateIn·GhgFacilitySaveIn·GhgUnitIn
#   ·GhgFactorIn·GhgGasIn
#   · 정수 칸 +8: GhgNodeCreateIn.parentId · GhgIdsIn.ids · GhgFacilityCreateIn.parentId·facilityCodeId
#   · GhgFacilitySaveIn.facilityCodeId·defaultFactorId · GhgFactorIn.baseYear·tier
# K1b-2b +1: IndexSelectionSaveIn · 정수 칸 +1: IndexSelectionSaveIn.facilityNodeIds(목록의 정수)
# S12a +6: EntrySaveIn·EntryRowIn·EntrySlotIn·EntryIdsIn·EntryMemoIn·EntryDecimalsIn
#   · 정수 칸 +4: EntryRowIn.rowId·siteFacilityId · EntryIdsIn.ids(목록의 정수) · EntryDecimalsIn.decimals
# RP1 +4: DraftingProjectCreateIn·DraftingDocumentPutIn·DraftingOutlinePutIn + 중첩 TypedDict DraftingOutlineNode
#   · 정수 칸 +3: DraftingProjectCreateIn.year · DraftingDocumentPutIn.documentId · DraftingOutlineNode.depth
# S12a-2 +3: EntryPeriodIn·EntryRowFactorIn·EntryRestoreIn(custom 은 이미 센 GhgFactorIn·GhgGasIn·GhgUnitIn)
#   · 정수 칸 +1: EntryRowFactorIn.factorId
# RPA1 +2: DraftingAiSettingCreate·DraftingAiSettingApply · 정수 칸 +1: DraftingAiSettingApply.id
# IRS3 +2: MaterialityResultEditsIn + 중첩 TypedDict MaterialityResultEditChange · 정수 칸 +1:
#   MaterialityResultEditsIn.baseRevision(7a 허락)
INTEGER_FIELDS = (
    57  # K2c +2: 두 companyId(int | None — StrictIn 이 true 를 거절) · E2 +1: GreenwashReviewMark.item_index
    # UA1 +1: UserUpdateIn.companyId · X1b-2a +2: DocumentPatchIn.reportYear·previousDocumentId(감독 c1 허락)
    # AS2b +1: AiModelStepIn.maxOutputTokens(감독 f6 허락)
    # S3K2b-2 +1: Scope3RowEditFactorIn.rank
    + 3  # GRJ1 +3: GreenwashReviewEvidenceIn.itemIndex·removed · GreenwashEvidenceAdded.page(감독 80 경유 7a 허락)
    + 1  # RM1c ③ +1: RunRetrySegmentsIn.fromRunId(7a 허락)
)


# 정수가 아닌데 느슨한 칸이 정수로 받는 것 셋(MARC-ISSUE-92 가 말한 셋): 불리언, 소수점이 0 인 실수, 수 글자.
NOT_INTEGERS: tuple[object, ...] = (True, 1.0, "1")


def _body_models() -> list[type[BaseModel]]:
    """본문을 받는 경로의 본문 모델. ninja 가 경로마다 만들어 둔 것에서 꺼낸다.

    ★ 문서를 먼저 만든다: 라우터 안에 건 라우터(user 의 하위 라우터)는 api 가 urls·문서를 만들 때에야 api._routers 에
    펴진다. 그 전에 읽으면 파일 하나로 돌릴 때 16 이 아니라 10 이 보였다(밴드 E2, CA 검증 지적 3).
    """
    api.get_openapi_schema(path_prefix="")
    found: list[type[BaseModel]] = []
    for _prefix, router in api._routers:  # pyright: ignore[reportPrivateUsage]
        for view in router.path_operations.values():
            for operation in view.operations:
                params_models: list[type[BaseModel]] = list(operation.models)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                for params in params_models:
                    if getattr(params, "__ninja_param_source__", None) != "body":
                        continue
                    for field in params.model_fields.values():
                        assert isinstance(field.annotation, type)
                        assert issubclass(field.annotation, BaseModel)
                        found.append(field.annotation)
    return found


def _probes(annotation: Any, nested: list[Any]) -> list[object]:
    """이 타입의 정수 자리에 `true` 를 넣은 값들. 중첩된 모델·TypedDict 는 `nested` 에 모은다(따로 훑는다).

    TypedDict 를 따로 훑는 까닭(MARC-ISSUE-92): StrictIn 의 strict 는 중첩 TypedDict 에 내려가지 않는다. 그 꼴이 자기
    설정(with_config strict)이나 칸마다의 거름을 갖췄는지 그 꼴 하나로 잰다 — 바깥 모델 안에서 재는 것과 같은 결과다."""
    origin = get_origin(annotation)
    if annotation is int:
        return list(NOT_INTEGERS)
    if origin is Literal:
        members = get_args(annotation)
        return list(NOT_INTEGERS) if any(type(member) is int for member in members) else []
    if origin is Annotated:
        return _probes(get_args(annotation)[0], nested)
    if origin is Union or origin is types.UnionType:
        return [probe for arg in get_args(annotation) for probe in _probes(arg, nested)]
    if origin in (list, set, frozenset, tuple):
        return [[probe] for arg in get_args(annotation) if arg is not Ellipsis for probe in _probes(arg, nested)]
    if origin is dict:
        return [{"k": probe} for probe in _probes(get_args(annotation)[1], nested)]
    if is_typeddict(annotation) or (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
        nested.append(annotation)
    return []


def _fields(model: Any) -> dict[str, tuple[str, Any]]:
    """칸 이름 → (본문의 키, 타입). 모델이면 model_fields, TypedDict 면 타입 힌트."""
    if is_typeddict(model):
        return {name: (name, hint) for name, hint in get_type_hints(model, include_extras=True).items()}
    return {name: (field.alias or name, field.annotation) for name, field in model.model_fields.items()}


def _all_request_models() -> dict[str, Any]:
    todo: list[Any] = list(_body_models())
    seen: dict[str, Any] = {}
    while todo:
        model = todo.pop()
        if model.__name__ in seen:
            continue
        seen[model.__name__] = model
        for _key, annotation in _fields(model).values():
            _probes(annotation, todo)
    return seen


def _rejects(model: Any, key: str, value: object) -> bool:
    try:
        if is_typeddict(model):
            TypeAdapter(model).validate_python({key: value})
        else:
            model.model_validate({key: value})
    except ValidationError as error:
        return any(detail["loc"][:1] == (key,) for detail in error.errors())
    return False


def test_every_integer_field_of_every_request_body_rejects_true() -> None:
    assert len(_body_models()) == BODY_OPERATIONS
    models = _all_request_models()
    probed: list[str] = []
    accepted: list[str] = []
    for name in sorted(models):
        model = models[name]
        for field_name, (key, annotation) in _fields(model).items():
            probes = _probes(annotation, [])
            if not probes:
                continue
            probed.append(f"{name}.{field_name}")
            if not all(_rejects(model, key, probe) for probe in probes):
                accepted.append(f"{name}.{field_name}")
    assert accepted == [], (
        f"true 를 정수로 받는 칸: {accepted} (StrictInt 나 Annotated[Literal[...], NotBool] 로 적는다)"
    )
    assert (len(models), len(probed)) == (REQUEST_MODELS, INTEGER_FIELDS), (sorted(models), probed)


def test_the_probe_itself_catches_a_field_that_takes_true() -> None:
    """이 검사가 눈이 멀지 않았는지: 거름이 없는 모델에서는 `true` 가 통과한다는 것을 같은 함수로 본다."""

    class Loose(BaseModel):
        tier: Literal[1, 2, 3, 4]
        count: int
        counts: list[int]

    for field_name in ("tier", "count"):
        assert _probes(Loose.model_fields[field_name].annotation, []) == list(NOT_INTEGERS)
        assert not _rejects(Loose, field_name, True)
        assert not _rejects(Loose, field_name, 1.0)  # 느슨한 int·정수 Literal 은 1.0 도 받는다 — 그래서 넣어 본다
    assert not _rejects(Loose, "count", "1")
    assert _probes(Loose.model_fields["counts"].annotation, []) == [[p] for p in NOT_INTEGERS]
    assert not _rejects(Loose, "counts", [True])


def test_the_probe_reaches_a_nested_typed_dict_that_takes_true() -> None:
    """MARC-ISSUE-92: 중첩 TypedDict 의 정수 칸도 훑는다. strict 를 내리지 않은 TypedDict 는 걸린다."""
    from typing import TypedDict

    from pydantic import ConfigDict, with_config

    from esgapi.core.schemas import StrictIn

    class LooseMark(TypedDict):
        index: int

    @with_config(ConfigDict(strict=True))
    class StrictMark(TypedDict):
        index: int

    class Body(StrictIn):
        loose: list[LooseMark]
        strict: list[StrictMark]

    nested: list[Any] = []
    _probes(Body.model_fields["loose"].annotation, nested)
    _probes(Body.model_fields["strict"].annotation, nested)
    assert nested == [LooseMark, StrictMark]
    assert not _rejects(LooseMark, "index", True)  # 바깥이 StrictIn 이어도 안 내려간다 — 그래서 따로 잰다
    assert _rejects(StrictMark, "index", True)


# ── 정수 Literal 칸 다섯 × (1.0 거절, "1" 거절, 1 받음) — IntOnly(밴드 E2 검증 뒤 고침, MARC-ISSUE-92) ──


def _tiers(**one: object) -> dict[str, object]:
    return {"calorific": 1, "co2": 1, "nonCo2": 1, "oxidation": 1, **one}


@pytest.mark.parametrize("field", ["calorific", "co2", "nonCo2", "oxidation"])
def test_each_tier_takes_1_and_refuses_1_point_0_and_the_text_1(field: str) -> None:
    from esgapi.inventory.service.schemas.inventory import CalcTiersIn

    assert getattr(CalcTiersIn.model_validate(_tiers(**{field: 1})), field) == 1
    for bad in (1.0, "1"):
        with pytest.raises(ValidationError) as caught:
            CalcTiersIn.model_validate(_tiers(**{field: bad}))
        assert [e["loc"][:1] for e in caught.value.errors()] == [(field,)], bad


def test_the_scope3_category_takes_1_and_refuses_1_point_0_and_the_text_1() -> None:
    from esgapi.inventory.service.schemas.inventory import Scope3CategoryIn

    adapter: TypeAdapter[Any] = TypeAdapter(Scope3CategoryIn)
    assert adapter.validate_python(1) == 1
    for bad in (1.0, "1", True):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_the_llm_output_category_still_takes_1_point_0_and_other() -> None:
    """IntOnly 는 요청 꼴에만 붙였다. LLM 출력 꼴(CategoryOut)은 지금처럼 1.0·"other" 를 받는다.

    (보고에 적음 — 이슈 후보)"""
    from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import CategoryOut

    adapter: TypeAdapter[Any] = TypeAdapter(CategoryOut)
    assert adapter.validate_python(1.0) == 1
    assert adapter.validate_python("other") == "other"
    with pytest.raises(ValidationError):
        adapter.validate_python(True)
