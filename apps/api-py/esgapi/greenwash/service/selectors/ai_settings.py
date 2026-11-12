"""읽기. 회사별 AI 설정 판(표 greenwash_ai_settings — 밴드 G2c2). 쓰지 않는다.

    ai_setting_page(company_id, limit, offset)               그 회사의 판 한 쪽(새 것 먼저 — id 내림)과 전체 수·적용 판
                                                              (머리 꼴 — 기준표 칸을 읽지 않는다)
    ai_setting_detail(company_id, setting_id)                 판 하나(기준표째). 없거나 남의 회사면 SettingMissing
    lock_settings(company_id)                                 그 회사의 판 행 전부를 id 차례로 FOR UPDATE(적용 바꾸기 —
                                                              변경 트랜잭션 안에서만. id·이름·적용만 읽는다)
    setting_names(company_id)                                 그 회사의 판 이름 전부(이름 매김 — 잠그지 않는다)
    status_of(applied, applied_at)                            응답의 상태 셈(순수) — core version_status 의 별칭
    model_config()                                            모델 설정 받기·보기의 설정(AS2a) — 실제 파일만, 모의
                                                              경로 0(표를 읽지 않는다. 한 번 읽어 캐시)
    RunModelSource()                                          모델 설정 받기·sha 의 원천(AS2b — flows/binding_e0.
                                                              ModelSettingsSource 구현): config()·steps()

    RunSettingStore()                                         실행기의 판 읽기(flows/binding_e0.AiSettingStore 구현) —
                                                              applied(company_id)·get(company_id, id)

실행기(워커)가 판을 읽는 길은 권한 없는 따로의 입구 RunSettingStore 다(주체가 없다 — 밴드 G2c2 ③). 경로의 읽기는
actions(첫 문장이 권한)를 거친다.
★ 조회마다 회사 조건을 적는다(<표>.for_company(company_id) — core/tests/test_selector_scope.py). 남의 회사의 판 id 는
  「없음」과 같다(SettingMissing 하나 — 응답도 같은 404).
★ 목록·잠금은 기준표 칸(criteria — jsonb)을 싣지 않는다(.only — 밴드 G2c3, MARC-ISSUE-229). 기준표는 한 판 읽기와
  실행기의 읽기만 싣는다. 모델 설정 칸(model_settings — AS2b)·프롬프트 글 칸(prompts — AS3a-2)·대상 단어 칸(terms —
  G2d)도 같다. 판 이름
  (title)은 목록 줄이 싣는다.
★ 모델 설정의 받기·sha 는 만들 때(services·actions)와 워커(끼움)가 같은 원천 RunModelSource 를 본다(AS2b ★E). 원천의
  설정은 실행 클라이언트가 보는 파일과 같은 셈이다: LLM_MODELS_FILE 이 있으면 그 파일, 없으면 패키지 models.json
  (core/llm/setup.py 의 비모의 갈래). 한 번 읽어 프로세스 끝까지 쥔다 — 설정 파일을 바꾸면 웹·워커 둘 다 재시작.
★ 목록 한 쪽은 문 하나다(셈은 창 함수, 적용 판은 부분 쿼리). 무효 조건: 문을 나누면 한 응답 안에서 total·applied 와
  items 의 상태가 어긋날 수 있다(READ COMMITTED 는 문마다 스냅숏 — transaction.atomic 으로 감싸도 같다). 쪽이 비면
  (offset ≥ 전체) 셈 한 문을 더 낸다.
"""

import functools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, cast

from django.db.models import Count, Max, Q, Subquery, Window

from esgapi.core.calc.ai_settings import AiStepSpec, version_status
from esgapi.core.conf import app_config
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.contracts.terms_shapes import GreenwashTerm
from esgapi.greenwash.flows import prompt_model_e0
from esgapi.greenwash.flows.binding_e0 import DefaultSetting, SavedSetting, SettingNotFound
from esgapi.greenwash.models import GreenwashAiSettingRow

status_of: Final = version_status
"""응답의 상태 셈 — core version_status 의 별칭(밴드 AP1b Q3 — actions 가 부른다)."""


@dataclass(frozen=True, slots=True)
class AiSettingHead:
    """판의 머리(기준표 없음) — 목록의 줄."""

    id: int
    name: str
    title: str | None  # 판 이름(0005 앞의 행은 None — AS3a-2)
    eval_prompt_sha256: str
    memo: str
    created_by_user_id: int
    created_at: datetime
    applied: bool
    applied_at: datetime | None


@dataclass(frozen=True, slots=True)
class AiSetting(AiSettingHead):
    """판 하나(머리 + 기준표 + 모델 설정 + 프롬프트 글 + 대상 단어)."""

    criteria: GreenwashCriteria
    model_settings: AiModelSettingsIn
    prompts: AiPromptsIn | None  # 저장 글 정규형. None = 코드 글(AS3a-2)
    terms: list[GreenwashTerm] | None  # 대상 단어 정규형(받은 차례). None = 코드 기본 목록(G2d)


@dataclass(frozen=True, slots=True)
class SettingLock:
    """잠근 판 행에서 적용 바꾸기가 쓰는 칸."""

    id: int
    name: str
    applied: bool


@dataclass(frozen=True, slots=True)
class AiSettingPage:
    total: int  # 그 회사의 판 전부의 수
    applied_id: int | None  # 지금 적용 판의 id. None = 기본 판
    items: tuple[AiSettingHead, ...]


@dataclass(frozen=True, slots=True)
class SettingMissing:
    """그런 판이 없다(남의 회사의 판도 이 갈래)."""


HEAD_FIELDS: Final = (
    "id",
    "name",
    "title",
    "eval_prompt_sha256",
    "memo",
    "created_by_user_id",
    "created_at",
    "applied",
    "applied_at",
)


def head_of(row: GreenwashAiSettingRow) -> AiSettingHead:
    return AiSettingHead(
        id=row.id,
        name=row.name,
        title=row.title,
        eval_prompt_sha256=row.eval_prompt_sha256,
        memo=row.memo,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        applied=row.applied,
        applied_at=row.applied_at,
    )


def setting_of(row: GreenwashAiSettingRow) -> AiSetting:
    return AiSetting(
        id=row.id,
        name=row.name,
        title=row.title,
        eval_prompt_sha256=row.eval_prompt_sha256,
        memo=row.memo,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        applied=row.applied,
        applied_at=row.applied_at,
        criteria=cast("GreenwashCriteria", row.criteria),  # 저장할 때 받기(accept_criteria)를 거친 값이다
        model_settings=cast("AiModelSettingsIn", row.model_settings),  # 저장할 때 받기(accept_model)를 거친 정규형
        prompts=cast("AiPromptsIn | None", row.prompts),  # 저장할 때 받기(accept_prompts)를 거친 정규형
        terms=cast("list[GreenwashTerm] | None", row.terms),  # 저장할 때 받기(terms_e0.accept_terms)를 거친 정규형
    )


def ai_setting_page(*, company_id: int, limit: int, offset: int) -> AiSettingPage:
    """그 회사의 판을 새 것 먼저 한 쪽으로. 쿼리 = 한 문(셈·적용 판을 줄마다 실음). 쪽이 비면 + 셈 한 문(머리말)."""
    rows = GreenwashAiSettingRow.for_company(company_id)
    applied = GreenwashAiSettingRow.for_company(company_id).filter(applied=True).values("id")[:1]
    page = list(
        rows.only(*HEAD_FIELDS)
        .annotate(total=Window(Count("id")), applied_id=Subquery(applied))
        .order_by("-id")[offset : offset + limit]
    )
    if page:
        first = page[0]
        total = int(first.total)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType] — annotate 한 칸
        applied_id = cast("int | None", first.applied_id)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType] — annotate 한 칸
        return AiSettingPage(total=total, applied_id=applied_id, items=tuple(head_of(row) for row in page))
    counted = rows.aggregate(total=Count("id"), applied_id=Max("id", filter=Q(applied=True)))
    return AiSettingPage(total=counted["total"], applied_id=counted["applied_id"], items=())


def ai_setting_detail(*, company_id: int, setting_id: int) -> AiSetting | SettingMissing:
    """판 하나."""
    row = GreenwashAiSettingRow.for_company(company_id).filter(id=setting_id).first()
    return SettingMissing() if row is None else setting_of(row)


def lock_settings(company_id: int) -> Mapping[int, SettingLock]:
    """그 회사의 판 행 전부를 id 차례로 FOR UPDATE 로 읽는다(적용 바꾸기의 차례 — 겹친 두 적용은 여기서 줄을 선다).
    트랜잭션 밖이면 Django 가 던진다."""
    rows = (
        GreenwashAiSettingRow.for_company(company_id).only("id", "name", "applied").select_for_update().order_by("id")
    )
    return {row.id: SettingLock(id=row.id, name=row.name, applied=row.applied) for row in rows}


def setting_names(company_id: int) -> tuple[str, ...]:
    return tuple(GreenwashAiSettingRow.for_company(company_id).values_list("name", flat=True))


@functools.cache
def model_config() -> LlmConfig:
    """실제 모델 설정(가상 파일 0). LLM_MODELS_FILE 이 있으면 그 파일, 없으면 패키지 models.json — 실행 클라이언트
    (core/llm/setup.py 비모의 갈래)와 같은 셈(AS2b N1). prompt-model 의 경로 능력·모델 설정 받기·sha 가 본다."""
    models_file = app_config().llm.models_file
    if models_file is not None:
        return load_config((Path(models_file),))
    return load_config(default_config_sources(synthetic=False))


class RunModelSource:
    """모델 설정 받기·sha 의 원천(flows/binding_e0.ModelSettingsSource 구현 — AS2b ★E). 판 저장·적용·prompt-model 과
    실행기의 끼움이 같은 이것을 본다. 시험 이음매는 이 클래스의 config·steps 하나다."""

    def config(self) -> LlmConfig:
        return model_config()

    def steps(self) -> Sequence[AiStepSpec]:
        return prompt_model_e0.STEPS


class RunSettingStore:
    """실행기가 끼움(GreenwashBinding)에 꽂는 판 읽기. 권한 검사 없음(실행기에 주체가 없다) — 회사 조건은 늘 적는다."""

    def applied(self, company_id: int) -> SavedSetting | DefaultSetting:
        row = GreenwashAiSettingRow.for_company(company_id).filter(applied=True).first()
        if row is None:
            return DefaultSetting()
        return SavedSetting(
            id=row.id,
            name=row.name,
            criteria=cast("GreenwashCriteria", row.criteria),
            model_settings=cast("AiModelSettingsIn", row.model_settings),
            prompts=cast("AiPromptsIn | None", row.prompts),
            terms=cast("list[GreenwashTerm] | None", row.terms),
        )

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound:
        row = GreenwashAiSettingRow.for_company(company_id).filter(id=setting_id).first()
        if row is None:
            return SettingNotFound(setting_id)
        return SavedSetting(
            id=row.id,
            name=row.name,
            criteria=cast("GreenwashCriteria", row.criteria),
            model_settings=cast("AiModelSettingsIn", row.model_settings),
            prompts=cast("AiPromptsIn | None", row.prompts),
            terms=cast("list[GreenwashTerm] | None", row.terms),
        )
