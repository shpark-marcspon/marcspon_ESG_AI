"""중대성평가 IRO의 표 셋.

- 회사별 AI 설정 판(MaterialityAiSettingRow, 표 materiality_ai_settings). 밴드 IR4 ② (결정 MARC-ENT-399·381·387).
  표·CHECK·앱 역할의 권한은 migrations/0001_ai_settings.py. 영문번역 판 표(translation/models.py 의
  TranslationAiSettingRow)의 판별 복사다(이름 접두만 다름 — 모듈끼리 import 하지 않는다).
- 결과 글 칸 고침 둘(밴드 IRS3, 결정 MARC-ENT-561): 실행마다의 머리(MaterialityResultEditHeadRow, 표
  materiality_result_edit_heads — revision)와 고침(MaterialityResultEditRow, 표 materiality_result_edits — 불변 행).
  표·CHECK·복합 외래 키·권한은 migrations/0002_result_edits.py. run_id 는 외래 키가 아니다(BigInt — MARC-ENT-210 (1)).
  같은 회사는 쓰는 길이 지킨다(actions 가 runs 의 find_run 으로 실행을 먼저 찾고 그 회사로 쓴다). 고침 → 머리는 같은
  회사 복합 외래 키 (company_id, run_id) 하나(greenwash marks → reviews 꼴).

★ 지우지 않는다(앱 역할에 DELETE 없음 — core/isolation/grants.py). 고쳐 쓰지도 않는다(칸 단위 UPDATE 는 applied,
  applied_at 둘뿐).
"""

from django.db import models
from django.db.models.functions import Cast, Length

from esgapi.core.contracts.ai_setting_shapes import (
    PROMPTS_MAX_OCTETS,
    VERSION_MEMO_MAX_CHARS,
    VERSION_NAME_MAX_CHARS,
    VERSION_NAME_PATTERN,
    VERSION_TITLE_MAX_CHARS,
)
from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel
from esgapi.core.models import BaseModel
from esgapi.materiality.contracts.edit_shapes import POINTER_MAX_CHARS, POINTER_PATTERN, VALUE_MAX_OCTETS

# 판 이름·제목·메모·프롬프트 상한은 core 판 상수(contracts/ai_setting_shapes.py). 받기(core check_prompts·본문 꼴)가
# 먼저 막으므로 CHECK 는 마지막 그물이다(500 0). 마이그레이션은 값을 문면에 굳힌다 — 상수가 바뀌면 새 마이그레이션.
# 모델 설정 상한은 어림(칸 둘 정규형 약 240 바이트 — 영문번역 AI_SETTING_MODEL_SETTINGS_MAX_OCTETS 와 같은 값).
AI_SETTING_MODEL_SETTINGS_MAX_OCTETS = 4096


def _octets_at_most(field: str, limit: int) -> models.Q:
    return models.Q(
        models.lookups.LessThanOrEqual(
            models.Func(
                Cast(field, output_field=models.TextField()),
                function="octet_length",
                output_field=models.IntegerField(),
            ),
            limit,
        )
    )


class MaterialityAiSettingRow(BaseModel, CompanyScopedModel):
    """회사 하나의 중대성평가 IRO AI 설정 판 하나(표 materiality_ai_settings). 밴드 IR4 — 결정 MARC-ENT-399·387.

    ★ 불변 행이다: 저장 = 새 행. 고쳐 쓰기·지우기 없음 — 앱 역할에게 SELECT·INSERT 와 칸 단위 UPDATE (applied,
      applied_at) 만 준다(마이그레이션 0001). 적용 바꾸기는 QuerySet.update(applied=…, applied_at=…) 하나다
      (service/services/ai_settings.py — save() 는 updated_at 도 쓰려다 권한 오류).
    ★ 기본 판(엔진 코드 글·모델 칸 기본값)은 행이 없다. 적용 판 행이 없으면 곧 기본 판.
    ★ 회사마다 적용 판은 많아야 하나(부분 unique (company_id) WHERE applied).
    ★ model_settings 는 받기(flows/prompt_model_155.accept_model)를 거친 정규형(ai.model-settings@1 — 칸 둘)이다. null
      없음(안 보내면 코드 값의 정규형). 실행은 만들 때 지금 설정으로 다시 받아 그 sha 를 versions 에 박는다.
    ★ prompts 는 받기(core check_prompts)를 거친 정규형(ai.prompts@1 — 묶음 여섯·칸 열넷, 글 바이트 그대로·메모 strip)
      이고 NULL 이면 코드 글이다. 기본 글과 같은 글을 보내도 NULL 로 접지 않는다. IRA3 앞에 저장한 행은 칸 열일곱 —
      읽는 자리가 accept_stored 로 셋을 뗀다.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    name = models.CharField(max_length=VERSION_NAME_MAX_CHARS)  # v1, v2, … (회사 안 1부터)
    title = models.CharField(max_length=VERSION_TITLE_MAX_CHARS)  # 판 이름 1~40자
    # ai.model-settings@1 의 정규형(받기를 거친 값). 불변: 모델 설정만 바꿔도 새 판
    model_settings: "models.JSONField[dict[str, object]]" = models.JSONField()
    # ai.prompts@1 의 정규형(받기를 거친 값). NULL = 코드 글. 불변: 글·메모만 바꿔도 새 판
    prompts: "models.JSONField[dict[str, object] | None]" = models.JSONField(null=True)
    memo = models.CharField(max_length=VERSION_MEMO_MAX_CHARS, default="")
    # 저장한 운영 관리자의 id(외래 키가 아니다 — 실행의 created_by_user_id 와 같은 뜻)
    created_by_user_id = models.BigIntegerField()
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True)  # 마지막으로 적용한 때. 한 번도 안 했으면 NULL

    objects = CompanyScopedManager["MaterialityAiSettingRow"]()
    unscoped = models.Manager["MaterialityAiSettingRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "materiality_ai_settings"
        constraints = (
            models.UniqueConstraint(fields=("company", "name"), name="materiality_ai_settings_company_name_uniq"),
            models.UniqueConstraint(
                fields=("company",), condition=models.Q(applied=True), name="materiality_ai_settings_one_applied_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=VERSION_NAME_PATTERN), name="materiality_ai_settings_name_check"
            ),
            models.CheckConstraint(
                condition=models.Q(applied=False) | models.Q(applied_at__isnull=False),
                name="materiality_ai_settings_applied_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("prompts", PROMPTS_MAX_OCTETS),
                name="materiality_ai_settings_prompts_size_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("model_settings", AI_SETTING_MODEL_SETTINGS_MAX_OCTETS),
                name="materiality_ai_settings_model_settings_size_check",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.GreaterThanOrEqual(Length("title"), 1),
                    models.lookups.LessThanOrEqual(Length("title"), VERSION_TITLE_MAX_CHARS),
                ),
                name="materiality_ai_settings_title_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class MaterialityResultEditHeadRow(BaseModel, CompanyScopedModel):
    """한 실행의 결과 고침 머리(표 materiality_result_edit_heads). 열쇠 (company_id, run_id). 처음 저장 때 revision
    0 으로 만들고(세이브포인트 INSERT) 저장마다 조건부 UPDATE 로 revision 을 하나 올린다(낙관 잠금 — FOR UPDATE 없음).

    ★ 지우지 않는다. 앱 역할에게 SELECT·INSERT 와 칸 단위 UPDATE (revision, updated_at) 만 준다(마이그레이션 0002).
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    run_id = models.BigIntegerField()  # 실행 id(외래 키가 아니다 — 머리말)
    revision = models.IntegerField()  # 저장 번호(0 = 아직 고침 없음)

    objects = CompanyScopedManager["MaterialityResultEditHeadRow"]()
    unscoped = models.Manager["MaterialityResultEditHeadRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "materiality_result_edit_heads"
        constraints = (
            models.UniqueConstraint(
                fields=("company", "run_id"), name="materiality_result_edit_heads_company_run_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=0), name="materiality_result_edit_heads_revision_check"
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class MaterialityResultEditRow(BaseModel, CompanyScopedModel):
    """칸 하나의 고침 한 번(표 materiality_result_edits). 열쇠 (company_id, run_id, revision, pointer).

    ★ 불변 행이다: 저장 = 새 행(그 저장의 revision). 칸의 지금 값 = 그 주소의 가장 큰 revision 행. 앱 역할에게
      SELECT·INSERT 만 준다(고쳐 쓰기·지우기 0 — 마이그레이션 0002). 이 행들이 고침의 이력이다(감사 줄은 없다).
    ★ pointer 는 바른 주소(outputs/edits.py — 맥락 항목은 퍼짐 묶음의 첫 자리)이고 value 는 정규 값(NULL = 빈 칸)이다.
      원문과 같은 값도 행으로 남는다(되돌림).
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    run_id = models.BigIntegerField()  # 같은 회사 복합 외래 키 (company_id, run_id) → 머리의 반쪽
    revision = models.IntegerField()  # 이 고침을 넣은 저장의 번호(1부터)
    pointer = models.CharField(max_length=POINTER_MAX_CHARS)
    value = models.TextField(null=True)  # noqa: DJ001  NULL = 빈 칸(화면 「–」)
    # 고친 사람의 id(외래 키가 아니다 — 실행의 created_by_user_id 와 같은 뜻)
    edited_by_user_id = models.BigIntegerField()

    objects = CompanyScopedManager["MaterialityResultEditRow"]()
    unscoped = models.Manager["MaterialityResultEditRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "materiality_result_edits"
        constraints = (
            models.UniqueConstraint(
                fields=("company", "run_id", "revision", "pointer"),
                name="materiality_result_edits_company_run_rev_uniq",
            ),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="materiality_result_edits_revision_check"),
            models.CheckConstraint(
                condition=models.Q(pointer__regex=POINTER_PATTERN), name="materiality_result_edits_pointer_check"
            ),
            models.CheckConstraint(
                condition=_octets_at_most("value", VALUE_MAX_OCTETS), name="materiality_result_edits_value_size_check"
            ),
        )

    def __str__(self) -> str:
        return str(self.id)
