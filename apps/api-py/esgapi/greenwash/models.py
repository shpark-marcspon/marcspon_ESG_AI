"""그린워싱의 표 셋 — 한 실행의 검토(GreenwashReviewRow, 표 greenwash_reviews)와 문장마다의 표시
(GreenwashReviewMarkRow, 표 greenwash_review_marks). 밴드 G1b ②. 표·CHECK·복합 외래 키·앱 역할의 권한은
migrations/0001_initial.py. 회사별 AI 설정 판(GreenwashAiSettingRow, 표 greenwash_ai_settings)은 밴드 G2c2 ① —
migrations/0002_ai_settings.py(모델 설정 0003, 프롬프트 글·판 이름 0005, 대상 단어 0006).

★ run_id 는 외래 키가 아니다(BigInt — MARC-ENT-210 (1): 다른 앱은 runs 로 FK·마이그레이션 의존을 두지 않는다).
  같은 회사는 쓰는 길이 지킨다: actions 가 runs 의 selector(find_run, 세션의 회사)로 실행을 먼저 찾고 그 회사로 쓴다.
  표시 → 검토는 같은 회사 복합 외래 키 (company_id, run_id) → greenwash_reviews (company_id, run_id) 하나(마이그레이션).
★ 지우지 않는다(앱 역할에 DELETE 없음 — core/isolation/grants.py). 「표시 지우기」는 decision·exclude_reason 을 NULL 로
  UPDATE 한다. decision NULL = 미검토. 응답·목록 셈·감사는 decision 이 있는 행만 본다.
★ 열쇠는 (run_id, item_index) 다(contracts/review_shapes.py 머리말). 회사를 앞에 둔 unique 다.
"""

from django.db import models
from django.db.models.functions import Cast, Length

from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel
from esgapi.core.models import BaseModel

# 상태·표시의 값. contracts/review_shapes.py 의 GreenwashReviewStateName·GreenwashReviewMark.decision 과 같아야 한다
# (테스트가 견준다 — import 하지 않는 까닭: 마이그레이션이 값을 문면에 굳힌다. 값이 늘면 새 마이그레이션).
REVIEW_STATES = ("pending", "in_review", "confirmed")
MARK_DECISIONS = ("adopted", "excluded")
EXCLUDE_REASON_MAX_CHARS = 500
# 검토 고침(G1b-3). 등급 값은 contracts/shapes.py 의 Level 과 같아야 한다(테스트가 견준다 — import 하지 않는 까닭은
# 위와 같다). 상한은 어림(발주서 G1b-3 처분 Q4): AI 출력은 사유 셋 줄까지(엔진 _as_str_list(…, 3))·실측 줄 46자·수정
# 방향 185자 — 그보다 넓게 잡았다.
EDIT_LEVELS = ("High", "Mid", "Low")
EDIT_LEVEL_MAX_CHARS = 8
EDIT_REASONS_MAX_LINES = 10
EDIT_REASON_MAX_CHARS = 500
EDIT_FIX_MAX_CHARS = 2000
# strip 전 상한(GRV1, MARC-ISSUE-282) — 본문 상한 말고 서비스 그물. 위 상한의 5배(항목 수)·2배(글자 수): 붙여넣은 빈 줄·
# 들여쓰기 여유. 공백만 큰 값이 strip 뒤 통과하지 않게 한다.
EDIT_REASONS_RAW_MAX_LINES = EDIT_REASONS_MAX_LINES * 5
EDIT_REASON_RAW_MAX_CHARS = EDIT_REASON_MAX_CHARS * 2
EDIT_FIX_RAW_MAX_CHARS = EDIT_FIX_MAX_CHARS * 2
# AI 설정 판(G2c2). 이름은 서버가 회사 안에서 v1, v2, … 로 매긴다(발주서 G2c2 Q5). 메모는 0~200자.
# 기준표 jsonb 의 글자 바이트 상한은 어림이다(받기 최대 약 29,160 바이트 — MARC-ISSUE-208 의 5).
AI_SETTING_NAME_PATTERN = r"^v[1-9][0-9]{0,14}$"
AI_SETTING_NAME_MAX_CHARS = 16
AI_SETTING_MEMO_MAX_CHARS = 200
AI_SETTING_CRITERIA_MAX_OCTETS = 32768
# 프롬프트 글·판 이름(AS3a-2). 받기(core check_prompts·본문 꼴)가 먼저 막으므로 CHECK 는 마지막 그물이다(500 0 — 발주서
# M3). 프롬프트 상한은 core contracts/ai_setting_shapes.PROMPTS_MAX_OCTETS, 이름은 contracts TITLE_MAX_CHARS 와 같아야
# 한다(테스트가 견준다). 모델 설정 상한은 어림(한 단계 정규형 약 110 바이트 — MARC-ISSUE-257 4번).
AI_SETTING_PROMPTS_MAX_OCTETS = 131072
AI_SETTING_MODEL_SETTINGS_MAX_OCTETS = 4096
AI_SETTING_TITLE_MAX_CHARS = 40
# 판 대상 단어(G2d). 받기(flows/terms_e0.accept_terms — 100개·글 30자·제어 글자 0)가 먼저 막는다 — CHECK 는 마지막
# 그물(최악 약 15,200 바이트, 발주서 K6).
AI_SETTING_TERMS_MAX_OCTETS = 16384
# 근거 고침·재판단(GRJ1, MARC-ENT-617). 더한 조각은 문장마다 10개·한 조각 1~1000자(코드 포인트, strip 뒤 — strip 전 그물
# ×2). CHECK 는 마지막 그물이다(받기가 먼저 막는다): 더한 조각 jsonb 최악 약 10 × (2000자 × 4바이트 + 30) ≈ 80,300
# 바이트 → 131,072. 재판단 실행 id 목록은 어림(id 20자리 × 약 3,000번 — 사람 손으로 닿지 않는 수).
EVIDENCE_ADDED_MAX_ITEMS = 10
EVIDENCE_TEXT_MAX_CHARS = 1000
EVIDENCE_TEXT_RAW_MAX_CHARS = EVIDENCE_TEXT_MAX_CHARS * 2
EVIDENCE_ADDED_MAX_OCTETS = 131072
REJUDGE_RUN_IDS_MAX_OCTETS = 65536


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


class GreenwashReviewRow(BaseModel, CompanyScopedModel):
    """한 실행의 검토 한 건(표 greenwash_reviews). 표시를 처음 저장할 때 만든다(없으면 읽기는 pending).

    confirmed 면 confirmed_at·confirmed_by_user_id 둘 다 값이고 잠긴다(그 밖에는 둘 다 NULL — CHECK).
    """

    id = models.BigAutoField(primary_key=True)
    # 회사(organization 의 company). 글자 참조다(DocumentRow.company 와 같은 까닭). 따옴표 주석은 타입 검사기에게만.
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int  # Django 가 외래 키마다 만들어 주는 칸. 타입 검사기가 알도록 적어 둔다
    run_id = models.BigIntegerField()  # 실행 id(외래 키가 아니다 — 머리말)
    state = models.CharField(max_length=16)
    confirmed_at = models.DateTimeField(null=True)
    # 확정한 사용자 id(외래 키가 아니다 — 실행의 created_by_user_id 와 같은 뜻)
    confirmed_by_user_id = models.BigIntegerField(null=True)

    objects = CompanyScopedManager["GreenwashReviewRow"]()
    unscoped = models.Manager["GreenwashReviewRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "greenwash_reviews"
        constraints = (
            models.UniqueConstraint(fields=("company", "run_id"), name="greenwash_reviews_company_run_uniq"),
            models.CheckConstraint(condition=models.Q(state__in=REVIEW_STATES), name="greenwash_reviews_state_check"),
            models.CheckConstraint(
                condition=(
                    models.Q(state="confirmed", confirmed_at__isnull=False, confirmed_by_user_id__isnull=False)
                    | (
                        ~models.Q(state="confirmed")
                        & models.Q(confirmed_at__isnull=True, confirmed_by_user_id__isnull=True)
                    )
                ),
                name="greenwash_reviews_confirmed_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


# 고침 칸 셋: (CHECK 이름 조각, 값 칸, 때 칸, 사람 칸)
EDIT_COLUMNS = (
    ("level", "edited_level", "level_edited_at", "level_edited_by_user_id"),
    ("reasons", "edited_reason_bullets", "reasons_edited_at", "reasons_edited_by_user_id"),
    ("fix", "edited_fix_paragraph", "fix_edited_at", "fix_edited_by_user_id"),
)


class GreenwashReviewMarkRow(BaseModel, CompanyScopedModel):
    """문장 하나의 표시와 고침(표 greenwash_review_marks). 열쇠 (company_id, run_id, item_index).

    decision NULL = 미검토(지운 표시). excluded ⇔ exclude_reason 이 값(adopted·NULL 이면 사유도 NULL — CHECK).
    고침 칸 셋(등급·판정 사유·수정 방향 — G1b-3, 마이그레이션 0004)은 칸마다 값·때·사람이 다 NULL(고침 없음 = AI 그대로)
    이거나 다 값이다(CHECK). 고침만 있고 decision NULL 인 행이 있을 수 있다(미검토 문장의 고침). AI 원본은 결과
    (run_results)에 있다 — 이 행은 고친 값만 싣는다.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    run_id = models.BigIntegerField()  # 같은 회사 복합 외래 키 (company_id, run_id) → greenwash_reviews 의 반쪽
    item_index = models.IntegerField()  # 결과 items 의 차례(0부터)
    decision = models.CharField(max_length=16, null=True)  # noqa: DJ001  NULL = 미검토
    exclude_reason = models.CharField(max_length=EXCLUDE_REASON_MAX_CHARS, null=True)  # noqa: DJ001  excluded 일 때만
    # 고침 칸 셋 × (값·때·사람). 사람 id 는 외래 키가 아니다(confirmed_by_user_id 와 같은 뜻)
    edited_level = models.CharField(max_length=EDIT_LEVEL_MAX_CHARS, null=True)  # noqa: DJ001  NULL = AI 등급
    level_edited_at = models.DateTimeField(null=True)
    level_edited_by_user_id = models.BigIntegerField(null=True)
    edited_reason_bullets: "models.JSONField[list[str] | None]" = models.JSONField(null=True)  # NULL = AI 사유
    reasons_edited_at = models.DateTimeField(null=True)
    reasons_edited_by_user_id = models.BigIntegerField(null=True)
    edited_fix_paragraph = models.CharField(max_length=EDIT_FIX_MAX_CHARS, null=True)  # noqa: DJ001  NULL = AI 수정 방향
    fix_edited_at = models.DateTimeField(null=True)
    fix_edited_by_user_id = models.BigIntegerField(null=True)
    # 근거 고침(GRJ1 — 마이그레이션 0007). removed = 기준 판단(evidence_basis_run_id 의 판단, NULL 이면 첫 판단)의
    # confirmedInEvidence 차례 중 지운 것(오름·겹침 없음), added = 더한 조각 [{text, page|null}](받은 차례). 넷은 다
    # NULL(고침 없음) 이거나 다 값이다(CHECK). 기준 판단이 바뀌면(재판단 성공) removed 는 읽을 때 [] 로 본다(R3 안 C)
    evidence_removed: "models.JSONField[list[int] | None]" = models.JSONField(null=True)
    evidence_added: "models.JSONField[list[dict[str, object]] | None]" = models.JSONField(null=True)
    evidence_edited_at = models.DateTimeField(null=True)
    evidence_edited_by_user_id = models.BigIntegerField(null=True)
    evidence_basis_run_id = models.BigIntegerField(null=True)  # 외래 키 아님(run_id 와 같은 뜻). NULL = 첫 판단
    # 이 문장의 재판단 실행 id(만든 차례, 붙이기만). NULL = 재판단 없음. 기준 판단 = 이 가운데 가장 늦은 done 실행
    rejudge_run_ids: "models.JSONField[list[int] | None]" = models.JSONField(null=True)

    objects = CompanyScopedManager["GreenwashReviewMarkRow"]()
    unscoped = models.Manager["GreenwashReviewMarkRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "greenwash_review_marks"
        constraints = (
            models.UniqueConstraint(
                fields=("company", "run_id", "item_index"), name="greenwash_review_marks_company_run_item_uniq"
            ),
            models.CheckConstraint(condition=models.Q(item_index__gte=0), name="greenwash_review_marks_item_check"),
            models.CheckConstraint(
                condition=(
                    # 갈래마다 decision IS [NOT] NULL 을 같이 적는다: decision 이 NULL 이면 decision = '…' 가 NULL(3값
                    # 논리)이라 CHECK 가 지나 버린다(검증 2 B1 — NULL decision + 사유 값이 들어갔다)
                    models.Q(decision__isnull=True, exclude_reason__isnull=True)
                    | models.Q(decision__isnull=False, decision="adopted", exclude_reason__isnull=True)
                    | models.Q(decision__isnull=False, decision="excluded", exclude_reason__isnull=False)
                ),
                name="greenwash_review_marks_decision_check",
            ),
            # 고침 칸마다 값·때·사람이 다 NULL 이거나 다 값(갈래마다 IS [NOT] NULL — 위 3값 함정)
            *(
                models.CheckConstraint(
                    condition=(
                        models.Q(**{f"{value}__isnull": True, f"{at}__isnull": True, f"{by}__isnull": True})
                        | models.Q(**{f"{value}__isnull": False, f"{at}__isnull": False, f"{by}__isnull": False})
                    ),
                    name=f"greenwash_review_marks_{name}_edit_check",
                )
                for name, value, at, by in EDIT_COLUMNS
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(edited_level__isnull=True)
                    | models.Q(edited_level__isnull=False, edited_level__in=EDIT_LEVELS)
                ),
                name="greenwash_review_marks_edit_level_check",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        evidence_removed__isnull=True,
                        evidence_added__isnull=True,
                        evidence_edited_at__isnull=True,
                        evidence_edited_by_user_id__isnull=True,
                    )
                    | models.Q(
                        evidence_removed__isnull=False,
                        evidence_added__isnull=False,
                        evidence_edited_at__isnull=False,
                        evidence_edited_by_user_id__isnull=False,
                    )
                ),
                name="greenwash_review_marks_evidence_edit_check",
            ),
            models.CheckConstraint(
                condition=models.Q(evidence_basis_run_id__isnull=True) | models.Q(evidence_removed__isnull=False),
                name="greenwash_review_marks_evidence_basis_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("evidence_added", EVIDENCE_ADDED_MAX_OCTETS),
                name="greenwash_review_marks_evidence_size_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("rejudge_run_ids", REJUDGE_RUN_IDS_MAX_OCTETS),
                name="greenwash_review_marks_rejudge_size_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class GreenwashAiSettingRow(BaseModel, CompanyScopedModel):
    """회사 하나의 그린워싱 AI 설정 판 하나(표 greenwash_ai_settings). 밴드 G2c2 — 결정 MARC-ENT-341·244·312.

    ★ 불변 행이다: 저장 = 새 행. 고쳐 쓰기·지우기 없음 — 앱 역할에게 SELECT·INSERT 와 칸 단위 UPDATE (applied,
      applied_at) 만 준다(마이그레이션 0002). 그래서 이 행은 save() 로 고치지 않는다(updated_at 칸도 UPDATE 권한 밖이다)
      — 적용 바꾸기는 QuerySet.update(applied=…, applied_at=…) 하나다(service/services/ai_settings.py).
    ★ 기본 판(criteria_e0.default_criteria(), 이름 colab-2026-01-15-v1)은 행이 없다. 적용 판 행이 없으면 곧 기본 판.
    ★ 회사마다 적용 판은 많아야 하나(부분 unique (company_id) WHERE applied).
    ★ eval_prompt_sha256 은 저장할 때 지은 값의 기록이다. 실행은 만들 때 다시 지은 값을 versions 에 박는다(발주서 R1).
    ★ model_settings 는 받기를 거친 정규형이다(밴드 AS2b, MARC-ENT-353). 실행은 만들 때 지금 설정으로 다시 받아 그
      sha 를 versions.modelSettingsSha256 에 박는다(flows/binding_e0.py).
    ★ prompts 는 받기(core check_prompts)를 거친 정규형(ai.prompts@1 — 글 바이트 그대로·메모 strip)이고 NULL 이면 코드
      글이다(밴드 AS3a-2). title 은 판 이름(1~40자) — 0005 앞의 행은 NULL(채우지 않는다, MARC-ENT-387 노트).
    ★ terms 는 판의 대상 단어 {text, enabled} 목록(받기 flows/terms_e0.accept_terms 를 거친 정규형 — 받은 차례)이고 NULL
      이면 코드 기본 목록(GREEN_TERMS)이다(밴드 G2d, MARC-ENT-394). 빈도 목록만 바꾼다 — 환경 신호에 닿지 않는다.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    name = models.CharField(max_length=AI_SETTING_NAME_MAX_CHARS)  # v1, v2, … (회사 안 1부터)
    criteria: "models.JSONField[dict[str, object]]" = (
        models.JSONField()
    )  # greenwash.criteria@1(받기를 거친 값, version = name)
    # ai.model-settings@1 의 정규형(받기를 거친 값 — to_input(check_model_settings(…)), 밴드 AS2b). 불변: 모델 설정만
    # 바꿔도 새 판이다. null 없음 — null(코드 값)은 행이 없는 기본 판뿐. 이행(0003) 전 행은 그때의 코드 값
    model_settings: "models.JSONField[dict[str, object]]" = models.JSONField()
    # ai.prompts@1 의 정규형(받기를 거친 값 — prompts_input(check_prompts(…)), 밴드 AS3a-2). NULL = 코드 글(옛 행·
    # prompts 없는 저장). 불변: 글·메모만 바꿔도 새 판
    prompts: "models.JSONField[dict[str, object] | None]" = models.JSONField(null=True)
    title = models.CharField(max_length=AI_SETTING_TITLE_MAX_CHARS, null=True)  # noqa: DJ001  판 이름. 0005 앞 NULL
    # {text, enabled} 목록의 정규형(받기를 거친 값 — 밴드 G2d). NULL = 코드 기본 목록(옛 행·terms 없는 저장). 같은
    # 목록을 보내도 NULL 로 접지 않는다. 불변: 단어만 바꿔도 새 판
    terms: "models.JSONField[list[dict[str, object]] | None]" = models.JSONField(null=True)
    eval_prompt_sha256 = models.CharField(max_length=64)
    memo = models.CharField(max_length=AI_SETTING_MEMO_MAX_CHARS, default="")
    # 저장한 운영 관리자의 id(외래 키가 아니다 — 실행의 created_by_user_id 와 같은 뜻)
    created_by_user_id = models.BigIntegerField()
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True)  # 마지막으로 적용한 때. 한 번도 안 했으면 NULL

    objects = CompanyScopedManager["GreenwashAiSettingRow"]()
    unscoped = models.Manager["GreenwashAiSettingRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "greenwash_ai_settings"
        constraints = (
            models.UniqueConstraint(fields=("company", "name"), name="greenwash_ai_settings_company_name_uniq"),
            models.UniqueConstraint(
                fields=("company",), condition=models.Q(applied=True), name="greenwash_ai_settings_one_applied_uniq"
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=AI_SETTING_NAME_PATTERN), name="greenwash_ai_settings_name_check"
            ),
            models.CheckConstraint(
                condition=models.Q(applied=False) | models.Q(applied_at__isnull=False),
                name="greenwash_ai_settings_applied_check",
            ),
            models.CheckConstraint(
                condition=models.Q(eval_prompt_sha256__regex=r"^[0-9a-f]{64}$"),
                name="greenwash_ai_settings_sha_check",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.LessThanOrEqual(
                        models.Func(
                            Cast("criteria", output_field=models.TextField()),
                            function="octet_length",
                            output_field=models.IntegerField(),
                        ),
                        AI_SETTING_CRITERIA_MAX_OCTETS,
                    )
                ),
                name="greenwash_ai_settings_criteria_size_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("prompts", AI_SETTING_PROMPTS_MAX_OCTETS),
                name="greenwash_ai_settings_prompts_size_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("model_settings", AI_SETTING_MODEL_SETTINGS_MAX_OCTETS),
                name="greenwash_ai_settings_model_settings_size_check",
            ),
            models.CheckConstraint(
                condition=models.Q(title__isnull=True)
                | models.Q(
                    models.lookups.GreaterThanOrEqual(Length("title"), 1),
                    models.lookups.LessThanOrEqual(Length("title"), AI_SETTING_TITLE_MAX_CHARS),
                ),
                name="greenwash_ai_settings_title_check",
            ),
            models.CheckConstraint(
                condition=_octets_at_most("terms", AI_SETTING_TERMS_MAX_OCTETS),
                name="greenwash_ai_settings_terms_size_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)
