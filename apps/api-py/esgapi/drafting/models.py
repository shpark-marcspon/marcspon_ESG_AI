"""원고작성의 표 넷 — 프로젝트·달린 문서·목차 판·목차 마디. 밴드 RP1 ① (결정 MARC-ENT-501). 표·CHECK·같은 회사 복합
외래 키·앱 역할의 권한은 migrations/0001_initial.py.

★ 불변 행이다: 문서 달기 = 새 행(지금 문서 = 가장 늦은 행), 목차 바꿈 = 새 판 + 마디 INSERT(지금 판 = 가장 큰
  revision). 앱 역할에게 SELECT·INSERT 만 주고, 프로젝트 표만 칸 단위 UPDATE (outline_revision, updated_at) 를 준다
  (감독 처분 10-29 — 목차 판 번호 매김을 프로젝트 행 FOR UPDATE 로 줄 세운다. FOR UPDATE 는 칸 하나의 UPDATE 권한으로
  된다). 지우지 않는다.
★ document_id 는 core 문서의 id 다(외래 키가 아니다 — 남의 도메인. 같은 회사·올림 확인은 actions 가 본다).
★ 실행은 판 id(outline_id)로 늘 같은 목차를 읽는다(만들 때 versions 에 박음).
"""

from django.db import models
from django.db.models.functions import Length

from esgapi.core.contracts.ai_setting_shapes import (
    PROMPTS_MAX_OCTETS,
    VERSION_MEMO_MAX_CHARS,
    VERSION_NAME_MAX_CHARS,
    VERSION_NAME_PATTERN,
    VERSION_TITLE_MAX_CHARS,
)
from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel
from esgapi.core.models import BaseModel
from esgapi.drafting.contracts.shapes import (
    DEPTH_MAX,
    KEY_MAX_CHARS,
    NODES_MAX,
    REQUIREMENT_MAX_CHARS,
    TITLE_MAX_CHARS,
)

PROJECT_NAME_MAX_CHARS = 80
YEAR_FIRST = 2000
YEAR_LAST = 2100
DOCUMENT_KINDS = ("prior_report",)  # 2차 갈래(자료 여럿 — RP2)는 새 마이그레이션


def _chars_between(field: str, low: int, high: int) -> models.Q:
    return models.Q(
        models.lookups.GreaterThanOrEqual(Length(field), low), models.lookups.LessThanOrEqual(Length(field), high)
    )


class DraftingProject(BaseModel, CompanyScopedModel):
    """원고작성 프로젝트 하나(연도·이름). outline_revision 은 마지막 목차 판 번호(0 = 목차 없음)."""

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    year = models.SmallIntegerField()
    name = models.CharField(max_length=PROJECT_NAME_MAX_CHARS)
    created_by_user_id = models.BigIntegerField()  # 만든 사용자의 id(외래 키가 아니다 — 실행의 created_by 와 같은 뜻)
    # 마지막 목차 판 번호. put_outline 이 이 행을 잠그고 +1 한다(앱 역할이 고칠 수 있는 칸은 이것과 updated_at 뿐)
    outline_revision = models.IntegerField(default=0)

    objects = CompanyScopedManager["DraftingProject"]()
    unscoped = models.Manager["DraftingProject"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "drafting_projects"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(year__gte=YEAR_FIRST, year__lte=YEAR_LAST), name="drafting_projects_year_range"
            ),
            models.CheckConstraint(
                condition=_chars_between("name", 1, PROJECT_NAME_MAX_CHARS), name="drafting_projects_name_length"
            ),
            models.CheckConstraint(
                condition=models.Q(outline_revision__gte=0), name="drafting_projects_outline_revision_range"
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class DraftingProjectDocument(BaseModel, CompanyScopedModel):
    """프로젝트에 단 문서 하나(불변 — 다시 달면 새 행, 지금 문서 = 가장 늦은 행)."""

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    project: "models.ForeignKey[DraftingProject]" = models.ForeignKey(
        DraftingProject, on_delete=models.PROTECT, related_name="+"
    )
    project_id: int
    document_id = models.BigIntegerField()  # core 문서 id(외래 키 아님)
    kind = models.CharField(max_length=32)
    attached_by_user_id = models.BigIntegerField()

    objects = CompanyScopedManager["DraftingProjectDocument"]()
    unscoped = models.Manager["DraftingProjectDocument"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "drafting_project_documents"
        constraints = (
            models.CheckConstraint(condition=models.Q(kind__in=DOCUMENT_KINDS), name="drafting_project_documents_kind"),
        )

    def __str__(self) -> str:
        return str(self.id)


class DraftingOutline(BaseModel, CompanyScopedModel):
    """목차 판 하나(불변). sha256 은 정규형(contracts/wire.outline_sha256)의 값."""

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    project: "models.ForeignKey[DraftingProject]" = models.ForeignKey(
        DraftingProject, on_delete=models.PROTECT, related_name="+"
    )
    project_id: int
    revision = models.IntegerField()
    sha256 = models.CharField(max_length=64)
    node_count = models.IntegerField()
    created_by_user_id = models.BigIntegerField()

    objects = CompanyScopedManager["DraftingOutline"]()
    unscoped = models.Manager["DraftingOutline"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "drafting_outlines"
        constraints = (
            models.UniqueConstraint(
                fields=("company", "project", "revision"), name="drafting_outlines_project_revision_unique"
            ),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="drafting_outlines_revision_range"),
            models.CheckConstraint(
                condition=models.Q(sha256__regex=r"^[0-9a-f]{64}$"), name="drafting_outlines_sha256"
            ),
            models.CheckConstraint(
                condition=models.Q(node_count__gte=1, node_count__lte=NODES_MAX), name="drafting_outlines_node_count"
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class DraftingOutlineNode(BaseModel, CompanyScopedModel):
    """목차 판의 마디 하나(불변). position 은 앞차례 나열의 자리(0부터)."""

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    outline: "models.ForeignKey[DraftingOutline]" = models.ForeignKey(
        DraftingOutline, on_delete=models.PROTECT, related_name="+"
    )
    outline_id: int
    key = models.CharField(max_length=KEY_MAX_CHARS)
    parent_key = models.CharField(max_length=KEY_MAX_CHARS, default="")  # 빈 글 = 첫 층(parentKey null)
    depth = models.SmallIntegerField()
    position = models.IntegerField()
    title = models.CharField(max_length=TITLE_MAX_CHARS)
    requirement = models.TextField(default="")

    objects = CompanyScopedManager["DraftingOutlineNode"]()
    unscoped = models.Manager["DraftingOutlineNode"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "drafting_outline_nodes"
        constraints = (
            models.UniqueConstraint(fields=("company", "outline", "key"), name="drafting_outline_nodes_key_unique"),
            models.UniqueConstraint(
                fields=("company", "outline", "position"), name="drafting_outline_nodes_position_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(depth__gte=1, depth__lte=DEPTH_MAX), name="drafting_outline_nodes_depth_range"
            ),
            models.CheckConstraint(condition=models.Q(position__gte=0), name="drafting_outline_nodes_position_range"),
            models.CheckConstraint(
                condition=_chars_between("title", 1, TITLE_MAX_CHARS), name="drafting_outline_nodes_title_length"
            ),
            models.CheckConstraint(
                condition=models.Q(models.lookups.LessThanOrEqual(Length("requirement"), REQUIREMENT_MAX_CHARS)),
                name="drafting_outline_nodes_requirement_length",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


# ── AI 설정 판(밴드 RPA1 ① — 결정 MARC-ENT-399·381·387) ──
# materiality/models.py 의 MaterialityAiSettingRow 판별 복사(이름 접두만 다름 — 모듈끼리 import 하지 않는다). 표·CHECK·
# 앱 역할의 권한은 migrations/0002_ai_settings.py. 판 이름·제목·메모·프롬프트 상한은 core 판 상수. 받기(core
# check_prompts·본문 꼴)가 먼저 막으므로 CHECK 는 마지막 그물이다(500 0). 모델 설정 상한은 어림(칸 둘 정규형).
AI_SETTING_MODEL_SETTINGS_MAX_OCTETS = 4096


def _octets_at_most(field: str, limit: int) -> models.Q:
    return models.Q(
        models.lookups.LessThanOrEqual(
            models.Func(
                models.functions.Cast(field, output_field=models.TextField()),
                function="octet_length",
                output_field=models.IntegerField(),
            ),
            limit,
        )
    )


class DraftingAiSettingRow(BaseModel, CompanyScopedModel):
    """회사 하나의 원고작성 AI 설정 판 하나(표 drafting_ai_settings). 밴드 RPA1 — 결정 MARC-ENT-399·387.

    ★ 불변 행이다: 저장 = 새 행. 고쳐 쓰기·지우기 없음 — 앱 역할에게 SELECT·INSERT 와 칸 단위 UPDATE (applied,
      applied_at) 만 준다(마이그레이션 0002). 적용 바꾸기는 QuerySet.update(applied=…, applied_at=…) 하나다
      (service/services/ai_settings.py — save() 는 updated_at 도 쓰려다 권한 오류).
    ★ 기본 판(엔진 코드 글·모델 칸 기본값)은 행이 없다. 적용 판 행이 없으면 곧 기본 판.
    ★ 회사마다 적용 판은 많아야 하나(부분 unique (company_id) WHERE applied).
    ★ model_settings 는 받기(flows/prompt_model_v2.accept_model)를 거친 정규형(ai.model-settings@1 — 칸 둘)이다. null
      없음(안 보내면 코드 값의 정규형). 실행은 만들 때 지금 설정으로 다시 받아 그 sha 를 versions 에 박는다.
    ★ prompts 는 받기(prompt_model_v2.accept_prompts)를 거친 정규형(ai.prompts@1 — 묶음 둘·칸 넷, 글 바이트 그대로·
      메모 strip)이고 NULL 이면 코드 글이다. 기본 글과 같은 글을 보내도 NULL 로 접지 않는다.
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

    objects = CompanyScopedManager["DraftingAiSettingRow"]()
    unscoped = models.Manager["DraftingAiSettingRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "drafting_ai_settings"
        constraints = (
            models.UniqueConstraint(fields=("company", "name"), name="drafting_ai_settings_company_name_uniq"),
            models.UniqueConstraint(
                fields=("company",), condition=models.Q(applied=True), name="drafting_ai_settings_one_applied_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=VERSION_NAME_PATTERN), name="drafting_ai_settings_name_check"
            ),
            models.CheckConstraint(
                condition=models.Q(applied=False) | models.Q(applied_at__isnull=False),
                name="drafting_ai_settings_applied_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("prompts", PROMPTS_MAX_OCTETS),
                name="drafting_ai_settings_prompts_size_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("model_settings", AI_SETTING_MODEL_SETTINGS_MAX_OCTETS),
                name="drafting_ai_settings_model_settings_size_check",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.GreaterThanOrEqual(Length("title"), 1),
                    models.lookups.LessThanOrEqual(Length("title"), VERSION_TITLE_MAX_CHARS),
                ),
                name="drafting_ai_settings_title_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)
