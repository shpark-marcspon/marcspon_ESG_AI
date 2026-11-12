"""쓰기. 회사별 AI 설정 판(표 greenwash_ai_settings — 밴드 G2c2). 읽기는 selectors/ai_settings.py, 감사·권한·이름
풀기는 부르는 쪽(actions/ai_settings.py)이다.

    create_setting(company_id, created_by_user_id, title, memo, criteria, model_settings, prompts, terms, models)
                                                                     받기 → 새 판 하나(이름 v<n>) — 블록 하나
    apply_setting(company_id, setting_id | None, now, models)        회사의 적용 판을 바꾼다(None = 기본 판) — 블록 하나
    next_name(names)                                                 이름 매김(순수) — core next_version_name 의 별칭
    import_setting(company_id, row, user_id)                         실행 묶음(RX1b)의 판 행 → 새 판(다음 v<n>,
                                                                     적용 안 함) — 받기를 다시 거치지 않는다(칸
                                                                     바이트 그대로, criteria.version 만 새 이름 —
                                                                     MARC-ENT-442)

★ 저장 = 새 행이다(고쳐 쓰기·지우기 없음 — 앱 역할에게 기준표 칸 UPDATE·DELETE 권한이 없다, 마이그레이션 0002).
  받은 기준표는 criteria_e0.accept_criteria 를 거치고, version 은 서버가 매긴 이름으로 덮는다(Q5). sha 는 그 값으로
  colab_e0.run_versions 가 지은 판정 프롬프트의 sha256 — 기록용이다(실행은 만들 때 다시 짓는다, R1).
★ 모델 설정(밴드 AS2b, MARC-ENT-353): 빠지면 코드 값(defaults(설정, STEPS)), 있으면 prompt_model_e0.accept_model 로
  받는다 — 거절이면 ModelRefused(행 0). 저장은 늘 그 정규형(to_input)이다(null 0). 차례: 기준표 → 모델(쓰기 앞).
  모델 설정만 바꿔도 새 판이다. 받기의 원천은 models(기본 selectors.RunModelSource — 실행기와 같은 원천, ★E).
★ 한 번 저장 = 판 하나(밴드 AS3a-2, 결정 MARC-ENT-384·387): 판 이름(title)·기준표(빠지면 기본 기준표 — 373)·모델·
  프롬프트 글·메모가 한 본문이다. 프롬프트만 따로 저장하는 길은 없다. 받기 차례는 기준표 → 모델 → 프롬프트(쓰기 앞 —
  하나라도 거절이면 행 0). 프롬프트 글은 prompt_model_e0.accept_prompts(core check_prompts) — 거절이면
  PromptsRefused(code·문장·칸 경로). 저장 칸은 받은 정규형(글 바이트 그대로·메모 strip) 또는 None(코드 글 — 코드 글과
  같은 글을 보내도 접지 않는다, J12). eval_prompt_sha256 은 실제로 쓸 EVAL 의 sha — 저장 글이 있으면 그 EVAL 글.
★ 대상 단어(밴드 G2d, MARC-ENT-394): 받기 차례의 끝(기준표 → 모델 → 프롬프트 → 단어, 쓰기 앞). flows/terms_e0.
  accept_terms — 거절이면 TermsRefused(code·문장·칸 경로, 행 0). 저장 칸은 받은 정규형(받은 차례·text strip) 또는
  None(코드 기본 목록 — 기본 목록과 같은 목록을 보내도 접지 않는다). 단어만 바꿔도 새 판이다.
★ 이름 경합: 같은 회사에 두 저장이 겹치면 둘이 같은 v<n> 을 셀 수 있다. INSERT 는 세이브포인트 안이고 unique
  (company_id, name) 위반만 다시 센다(NAME_RETRIES 번까지). 다른 제약 위반은 그대로 올라간다.
★ 적용 바꾸기: 그 회사의 판 행을 id 차례로 FOR UPDATE 로 잡고(selectors.lock_settings) 옛 판을 false 로 내린 뒤 새 판을
  true 로 올린다(부분 unique (company_id) WHERE applied 가 그 차례를 요구한다). 이미 그 판이면 쓰지 않는다(Unchanged).
  적용은 QuerySet.update(applied, applied_at) 하나다 — 앱 역할의 칸 단위 UPDATE 권한이 그 두 칸뿐이다(save() 는
  updated_at 도 쓰려다 권한 오류).
★ 못 받는 판(밴드 G2c3): 받기 규칙이 좁아져 지금 accept_criteria 에 맞지 않게 된 저장 판은 적용하지 않는다
  (SettingUnusable — 쓰기 0). 잠근 뒤 그 한 행의 기준표·모델 설정(AS2b)·프롬프트 글(AS3a-2)·대상 단어(G2d)를 그
  차례로 받기에 넣는다. 이미 적용된 그 판을 다시 보내도 같다(Unchanged 보다 앞). 기본 판(None)으로 되돌리기는 늘
  된다(막힌 회사의 출구).
생성자 <Row>(…) 는 쓰지 않는다(core/tests/isolation/test_static_rules.py 받침 ④).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

from django.db import IntegrityError, transaction

from esgapi.core.calc.ai_settings import ModelSettingRefused, PromptRefused, defaults, prompts_input, to_input
from esgapi.core.calc.ai_settings import next_version_name as next_name
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.log import sha256_text
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.flows import colab_e0, prompt_model_e0, terms_e0
from esgapi.greenwash.flows.binding_e0 import ModelSettingsSource
from esgapi.greenwash.flows.criteria_e0 import CriteriaRejected, accept_criteria, default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.selectors import ai_settings as selectors

NAME_UNIQUE: Final = "greenwash_ai_settings_company_name_uniq"
NAME_RETRIES: Final = 5
RUN_MODELS: Final = selectors.RunModelSource()
"""모델 설정 받기의 기본 원천(실행기와 같은 RunModelSource — 시험 이음매는 그 클래스의 config·steps)."""


@dataclass(frozen=True, slots=True)
class Created:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class CriteriaRefused:
    """받기의 거절. code 는 CriteriaRejected.code(CRITERIA_*), message 는 화면에 보일 한 문장."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ModelRefused:
    """모델 설정 받기의 거절. code 는 ModelSettingRefused.code(소문자 ai_model_* — 나갈 때 대문자), message 는 화면에
    보일 한 문장."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PromptsRefused:
    """프롬프트 글 받기의 거절. code 는 PromptRefused.code(소문자 ai_prompt_* — 나갈 때 대문자), message 는 화면에 보일
    한 문장, field 는 어긴 칸의 점 경로(prompts.steps.<i>.prompts.<j>.text|memo — 422 의 fields 와 같은 규칙)."""

    code: str
    message: str
    field: str


@dataclass(frozen=True, slots=True)
class TermsRefused:
    """대상 단어 받기의 거절(G2d). code 는 terms_e0.TermsRefused.code(TERMS_*), message 는 화면에 보일 한 문장, field 는
    어긴 칸의 점 경로(terms.<i>.text 또는 terms)."""

    code: str
    message: str
    field: str


@dataclass(frozen=True, slots=True)
class NameConflict:
    """겹친 저장이 NAME_RETRIES 번 내리 같은 이름을 먼저 썼다(쓰지 않았다 — 다시 보내면 된다)."""


@dataclass(frozen=True, slots=True)
class Applied:
    before_id: int | None  # 바꾸기 전 적용 판(None = 기본 판)
    after_id: int | None
    after_name: str | None


@dataclass(frozen=True, slots=True)
class SettingUnusable:
    """그 판의 기준표나 모델 설정·프롬프트 글·대상 단어가 지금 받기 규칙에 맞지 않는다(쓰지 않았다). code 는
    CriteriaRejected.code 나 ModelSettingRefused.code(ai_model_*)·PromptRefused.code(ai_prompt_*)·terms_e0 의 TERMS_*,
    name 은 판 이름."""

    code: str
    name: str


@dataclass(frozen=True, slots=True)
class Unchanged:
    """이미 그 판이 적용돼 있다(쓰지 않았다)."""


def _constraint(error: IntegrityError) -> str | None:
    """Django 의 IntegrityError 가 품은 psycopg 예외의 제약 이름."""
    diag = getattr(error.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def _criteria_named(accepted: GreenwashCriteria, name: str) -> GreenwashCriteria:
    return cast("GreenwashCriteria", {**accepted, "version": name})


@transaction.atomic
def create_setting(
    *,
    company_id: int,
    created_by_user_id: int,
    title: str,
    memo: str,
    criteria: object = None,
    model_settings: AiModelSettingsIn | None = None,
    prompts: AiPromptsIn | None = None,
    terms: object = None,
    models: ModelSettingsSource = RUN_MODELS,
) -> Created | CriteriaRefused | ModelRefused | PromptsRefused | TermsRefused | NameConflict:
    """받은 이름·기준표(None 이면 기본 기준표)·모델 설정·프롬프트 글·대상 단어(None 이면 코드 기본 목록)로 새 판 하나.
    받기 거절이면 쓰지 않는다(행 0 — 차례 기준표 → 모델 → 프롬프트 → 단어). 이름 경합이 다시 시도를 다 쓰면
    NameConflict. title 은 본문 꼴을 지난 값(strip 뒤 1~40자)이다."""
    try:
        accepted = accept_criteria(default_criteria() if criteria is None else criteria)
    except CriteriaRejected as refused:
        return CriteriaRefused(refused.code, str(refused))
    config = models.config()
    if model_settings is None:
        model = defaults(config, models.steps())
    else:
        found = prompt_model_e0.accept_model(config, model_settings, steps=models.steps())
        if isinstance(found, ModelSettingRefused):
            return ModelRefused(found.code, found.message)
        model = found
    texts = None if prompts is None else prompt_model_e0.accept_prompts(prompts)
    if isinstance(texts, PromptRefused):
        return PromptsRefused(texts.code, texts.message, texts.field)
    words = None if terms is None else terms_e0.accept_terms(terms)
    if isinstance(words, terms_e0.TermsRefused):
        return TermsRefused(words.code, words.message, words.field)
    stored = to_input(model)
    stored_prompts = None if texts is None else prompts_input(texts)
    for _ in range(NAME_RETRIES):
        name = next_name(selectors.setting_names(company_id))
        named = _criteria_named(accepted, name)
        sha = (
            str(colab_e0.run_versions(named)["evalPromptSha256"])
            if texts is None
            else sha256_text(colab_e0.pack_from(texts).eval_system_prompt)
        )
        try:
            with transaction.atomic():
                row = GreenwashAiSettingRow.for_company(company_id).create(
                    company_id=company_id,
                    name=name,
                    criteria=named,
                    model_settings=stored,
                    prompts=stored_prompts,
                    terms=None if words is None else terms_e0.terms_input(words),
                    title=title,
                    eval_prompt_sha256=sha,
                    memo=memo,
                    created_by_user_id=created_by_user_id,
                )
        except IntegrityError as error:
            if _constraint(error) != NAME_UNIQUE:
                raise
            continue  # 겹친 저장이 같은 이름을 먼저 썼다(머리말)
        return Created(row.id, row.name)
    return NameConflict()


@transaction.atomic
def import_setting(company_id: int, *, row: Mapping[str, object], user_id: int) -> tuple[int, str] | NameConflict:
    """묶음이 실은 판 칸(name·title·eval_prompt_sha256·memo·criteria·model_settings·prompts·terms)을 받기를 거치지 않고
    그대로 새 판 하나로. 이름은 받는 회사의 다음 v<n>, criteria.version 은 그 이름(_criteria_named — 고치는 자리는 여기
    하나), eval_prompt_sha256 은 그대로(판정 sha 는 이름에 닿지 않는다 — criteria_e0). 적용 판·기본 판은 건드리지 않는다
    (applied=False). 이름 경합이 다시 시도를 다 쓰면 NameConflict(부르는 쪽이 거절)."""
    criteria = cast("GreenwashCriteria", row["criteria"])
    for _ in range(NAME_RETRIES):
        name = next_name(selectors.setting_names(company_id))
        try:
            with transaction.atomic():
                made = GreenwashAiSettingRow.for_company(company_id).create(
                    company_id=company_id,
                    name=name,
                    criteria=_criteria_named(criteria, name),
                    model_settings=row["model_settings"],
                    prompts=row["prompts"],
                    terms=row["terms"],
                    title=row["title"],
                    eval_prompt_sha256=row["eval_prompt_sha256"],
                    memo=row["memo"],
                    created_by_user_id=user_id,
                )
        except IntegrityError as error:
            if _constraint(error) != NAME_UNIQUE:
                raise
            continue
        return (made.id, made.name)
    return NameConflict()


@transaction.atomic
def apply_setting(
    *, company_id: int, setting_id: int | None, now: datetime, models: ModelSettingsSource = RUN_MODELS
) -> Applied | Unchanged | SettingUnusable | selectors.SettingMissing:
    """그 회사의 적용 판을 setting_id 로(None 이면 기본 판). 없거나 남의 회사의 id 면 SettingMissing, 지금 받기에
    안 맞는 판이면 SettingUnusable(둘 다 쓰지 않는다)."""
    settings = selectors.lock_settings(company_id)
    if setting_id is not None and setting_id not in settings:
        return selectors.SettingMissing()
    if setting_id is not None:
        found = selectors.ai_setting_detail(company_id=company_id, setting_id=setting_id)
        if isinstance(found, selectors.SettingMissing):  # 잠근 행이다(지우는 길이 없다 — 일어나지 않는다)
            return found
        try:
            accept_criteria(found.criteria)
        except CriteriaRejected as refused:
            return SettingUnusable(refused.code, found.name)
        model = prompt_model_e0.accept_model(models.config(), found.model_settings, steps=models.steps())
        if isinstance(model, ModelSettingRefused):
            return SettingUnusable(model.code, found.name)
        texts = None if found.prompts is None else prompt_model_e0.accept_prompts(found.prompts)
        if isinstance(texts, PromptRefused):
            return SettingUnusable(texts.code, found.name)
        words = None if found.terms is None else terms_e0.accept_terms(found.terms)
        if isinstance(words, terms_e0.TermsRefused):
            return SettingUnusable(words.code, found.name)
    before = next((s.id for s in settings.values() if s.applied), None)
    if before == setting_id:
        return Unchanged()
    if before is not None:
        GreenwashAiSettingRow.for_company(company_id).filter(id=before).update(applied=False)
    if setting_id is None:
        return Applied(before_id=before, after_id=None, after_name=None)
    GreenwashAiSettingRow.for_company(company_id).filter(id=setting_id).update(applied=True, applied_at=now)
    return Applied(before_id=before, after_id=setting_id, after_name=settings[setting_id].name)
