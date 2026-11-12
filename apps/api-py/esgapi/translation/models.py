"""영문번역의 표 하나 — 회사별 AI 설정 판(TranslationAiSettingRow, 표 translation_ai_settings). 밴드 TR4 ② (결정
MARC-ENT-399·387). 표·CHECK·앱 역할의 권한은 migrations/0001_ai_settings.py. 그린워싱 판 표(greenwash/models.py 의
GreenwashAiSettingRow)의 판별 복사에서 기준표·대상 단어·판정 sha 칸을 뺐다.

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

# 판 이름·제목·메모·프롬프트 상한은 core 판 상수(contracts/ai_setting_shapes.py). 받기(core check_prompts·본문 꼴)가
# 먼저 막으므로 CHECK 는 마지막 그물이다(500 0). 마이그레이션은 값을 문면에 굳힌다 — 상수가 바뀌면 새 마이그레이션.
# 모델 설정 상한은 어림(칸 셋 정규형 약 330 바이트 — 그린워싱 AI_SETTING_MODEL_SETTINGS_MAX_OCTETS 와 같은 값).
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


class TranslationAiSettingRow(BaseModel, CompanyScopedModel):
    """회사 하나의 영문번역 AI 설정 판 하나(표 translation_ai_settings). 밴드 TR4 — 결정 MARC-ENT-399·387.

    ★ 불변 행이다: 저장 = 새 행. 고쳐 쓰기·지우기 없음 — 앱 역할에게 SELECT·INSERT 와 칸 단위 UPDATE (applied,
      applied_at) 만 준다(마이그레이션 0001). 적용 바꾸기는 QuerySet.update(applied=…, applied_at=…) 하나다
      (service/services/ai_settings.py — save() 는 updated_at 도 쓰려다 권한 오류).
    ★ 기본 판(엔진 코드 글·모델 칸 기본값)은 행이 없다. 적용 판 행이 없으면 곧 기본 판.
    ★ 회사마다 적용 판은 많아야 하나(부분 unique (company_id) WHERE applied).
    ★ model_settings 는 받기(flows/prompt_model_158.accept_model)를 거친 정규형(ai.model-settings@1 — 칸 셋)이다. null
      없음(안 보내면 코드 값의 정규형). 실행은 만들 때 지금 설정으로 다시 받아 그 sha 를 versions 에 박는다.
    ★ prompts 는 받기(core check_prompts)를 거친 정규형(ai.prompts@1 — 묶음 다섯·칸 열넷, 글 바이트 그대로·메모 strip)
      이고 NULL 이면 코드 글이다. 기본 글과 같은 글을 보내도 NULL 로 접지 않는다.
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

    objects = CompanyScopedManager["TranslationAiSettingRow"]()
    unscoped = models.Manager["TranslationAiSettingRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "translation_ai_settings"
        constraints = (
            models.UniqueConstraint(fields=("company", "name"), name="translation_ai_settings_company_name_uniq"),
            models.UniqueConstraint(
                fields=("company",), condition=models.Q(applied=True), name="translation_ai_settings_one_applied_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=VERSION_NAME_PATTERN), name="translation_ai_settings_name_check"
            ),
            models.CheckConstraint(
                condition=models.Q(applied=False) | models.Q(applied_at__isnull=False),
                name="translation_ai_settings_applied_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("prompts", PROMPTS_MAX_OCTETS),
                name="translation_ai_settings_prompts_size_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("model_settings", AI_SETTING_MODEL_SETTINGS_MAX_OCTETS),
                name="translation_ai_settings_model_settings_size_check",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.GreaterThanOrEqual(Length("title"), 1),
                    models.lookups.LessThanOrEqual(Length("title"), VERSION_TITLE_MAX_CHARS),
                ),
                name="translation_ai_settings_title_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)
