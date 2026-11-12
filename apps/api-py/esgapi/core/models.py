"""core 의 모델: 공통 바닥(BaseModel, 추상)과 LLM 호출 감사 기록(LlmCallLogRow, 표 core_llm_call_logs)과
올린 문서(DocumentRow, 표 core_documents)와 감사 기록(AuditEventRow, 표 core_audit_events — AU1a).
문서에 걸린 일감(JobRow)은 runs 의 models.py 에 있다."""

from django.db import models
from django.db.models.functions import Cast

from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel


class BaseModel(models.Model):
    """언제 만들어졌고 언제 마지막으로 고쳐졌는가. 새 모델은 이것을 이어받는다.

    이어받는 모델이 Meta 를 적을 때는  class Meta(BaseModel.Meta):  로 적는다(그냥 class Meta: 면 pyright 가
    「부모의 Meta 와 맞지 않는다」고 한다). abstract 는 물려받지 않는다: Django 가 자식에서 False 로 되돌린다.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# 호출 결과의 갈래. esgapi/core/llm/types.py 의 LlmResultKind 와 같아야 한다(테스트가 견준다. 여기서 그 타입을
# import 하지 않는 까닭: 마이그레이션이 이 값을 문면에 굳히므로, 갈래가 늘면 새 마이그레이션을 같이 내야 한다).
LLM_RESULT_KINDS = (
    "success",
    "schema_mismatch",
    "refusal",
    "truncated",
    "provider_error",
    "timeout",
    "budget_exceeded",
)


class LlmCallLogRow(CompanyScopedModel):
    """LLM 호출 감사 기록 한 줄(표 core_llm_call_logs). 공급사를 한 번 부를 때마다(재시도·대체 호출 포함) 한 줄.

    칸은 esgapi/core/llm/log.py 의 CallRecord 와 하나씩 맞는다(본문 body 만 없다: 공시 전 고객 데이터라 DB 에 두지
    않는다). 쓰는 곳은 esgapi/core/llm/sink_db.py 하나다. 권한은 migrations/0001_initial.py.

    BaseModel 을 잇지 않는다: 덧붙이기만 하는 표라 updated_at 이 뜻이 없다(앱 역할에는 UPDATE 권한도 없다).
    """

    # 기본 키는 숫자(BigAuto — DB 의 식별 열. 앱 역할의 INSERT 권한으로 쓰인다).
    id = models.BigAutoField(primary_key=True)
    # ★ 외래 키가 아니다. 값은 꼬리표(Tags.tenant)에 적힌 회사 id 다(sink_db.py 가 십진 숫자 글자만 받는다.
    #   꼬리표는 세션의 company_id·--tenant 에서 온다). 까닭: 회사가 지워져도 감사 기록은 남는다.
    #   무효 조건: 없는 회사 id 로도 행이 남는다(오타를 DB 가 잡지 못한다).
    company_id = models.BigIntegerField()
    module = models.CharField(max_length=100)

    ts = models.DateTimeField()  # 기록이 만들어진 때(CallRecord.ts. 밀리초까지)
    call_id = models.CharField(max_length=64)
    attempt = models.IntegerField()
    provider = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 공급사를 부르기 전에 막힌 줄(상한)
    model = models.CharField(max_length=100, null=True)  # noqa: DJ001  위와 같다
    api_model_id = models.CharField(max_length=200, null=True)  # noqa: DJ001  위와 같다
    response_model_id = models.CharField(max_length=200, null=True)  # noqa: DJ001  NULL = 응답에 모델 ID 가 없었다
    prompt_id = models.CharField(max_length=200)
    prompt_version = models.IntegerField()
    template_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64)
    input_tokens = models.IntegerField(null=True)
    output_tokens = models.IntegerField(null=True)
    cache_read_tokens = models.IntegerField(null=True)
    cache_write_tokens = models.IntegerField(null=True)
    thinking_tokens = models.IntegerField(null=True)
    # 소수 8자리: 비용의 반올림 자리(cost.round_usd 의 1e-8)와 같다. float 칸이 아니라 합계가 정확하다.
    cost_usd = models.DecimalField(max_digits=18, decimal_places=8, null=True)
    duration_ms = models.FloatField()
    result_kind = models.CharField(max_length=32)
    # 경고 코드의 목록(글자). 없으면 []. 따옴표 주석은 타입 검사기에게만 하는 말이다(reference/models 와 같은 꼴).
    warnings: "models.JSONField[list[str]]" = models.JSONField(default=list)
    retry_after_ms = models.IntegerField(null=True)
    provider_retry = models.IntegerField(null=True)
    retry_wait_ms = models.FloatField(null=True)
    # 「칸 없음」(MISSING)과 None 은 뜻이 다르다(log.py 의 머리말). 표지 칸이 False 면 칸 없음이고,
    # True 인데 값이 NULL 이면 「상태 코드 없이 실패했다」다.
    has_error_status = models.BooleanField(default=False)
    error_status = models.IntegerField(null=True)
    has_previous_error_status = models.BooleanField(default=False)
    previous_error_status = models.IntegerField(null=True)
    # 실행 id(X1b-1): 실행기가 지은 클라이언트의 호출이면 그 실행(runs 의 run_runs.id), 그 밖(동기 계산·관리 명령)은
    # NULL. ★ 외래 키가 아니다(MARC-ENT-210 (1) — runs 로 향하는 다른 앱의 FK 0, 실행이 없어져도 기록은 남는다).
    #   무효 조건: 없는 실행 id 로도 행이 남는다(오타를 DB 가 잡지 못한다).
    run_id = models.BigIntegerField(null=True)
    # 단계 이름(AD4D): 실행기가 지은 클라이언트의 호출이면 그 호출이 일어난 단계(runs 의 run_steps.name 과 같은 상한).
    step = models.CharField(max_length=100, null=True)  # noqa: DJ001  NULL = 단계 밖·사이 호출이거나 AD4D 앞의 줄
    # 구획 열쇠의 sha256(RM1a): 펼침 단계의 구획 안 호출이면 그 구획(runs 의 run_segments.key_sha256 과 같은 값).
    segment = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 장벽 단계·구획 밖이거나 RM1a 앞의 줄
    created_at = models.DateTimeField(auto_now_add=True)  # DB 에 들어간 때

    objects = CompanyScopedManager["LlmCallLogRow"]()
    unscoped = models.Manager["LlmCallLogRow"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "core_llm_call_logs"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(result_kind__in=LLM_RESULT_KINDS), name="core_llm_call_logs_result_kind_check"
            ),
            models.CheckConstraint(condition=models.Q(attempt__gte=0), name="core_llm_call_logs_attempt_check"),
        )
        indexes = (
            models.Index(fields=["company_id", "module"], name="core_llm_logs_company_module"),
            models.Index(fields=["call_id"], name="core_llm_logs_call_id"),
            models.Index(fields=["company_id", "run_id"], name="core_llm_logs_company_run"),  # 실행마다의 합(AU1b)
        )

    def __str__(self) -> str:
        return f"{self.call_id}#{self.attempt}"


# ── 올린 문서 ───────────────────────────────────────────────────────
# 상태의 값. esgapi/core/calc/documents.py 의 DOCUMENT_STATUSES 와 같아야 한다(테스트가 견준다.
# 여기서 그 튜플을 import 하지 않는 까닭은 위 LLM_RESULT_KINDS 와 같다: 마이그레이션이 값을 문면에 굳힌다).
# 문서에 걸린 일감(JobRow)은 실행 층 runs 의 models.py 에 있다(X1a 때 옮김).
DOCUMENT_ROW_STATUSES = ("awaiting_upload", "uploaded")


class DocumentRow(BaseModel, CompanyScopedModel):
    """올린(올릴) 원본 문서 한 건(표 core_documents). 파일 바이트는 저장소에 있고 여기에는 그 자리와 상태만 있다.

    ★ 넣지 않는 것: 분해 결과의 본문(문서 모델·글자 자리·쪽의 글), 모듈 고유의 칸, 서명된 주소, EDK 토큰.
      칸의 집합은 esgapi/core/tests/test_documents_models.py 가 글자로 못 박는다(더해도 빠져도 빨개진다).
    쓰는 곳은 esgapi/core/service/services/documents.py 다. 같은 회사 외래 키의 자리와 권한은
    migrations/0001_initial.py.
    """

    id = models.BigAutoField(primary_key=True)
    # 회사(organization 의 company). 글자 참조다: core 는 organization 을 import 하지 않는다(.importlinter 계약 가).
    # PROTECT: 문서가 있는 회사는 지워지지 않는다.
    # 따옴표 주석은 타입 검사기에게만 하는 말이다(글자 참조라 django-types 가 대상 모델을 모른다).
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int  # Django 가 외래 키마다 만들어 주는 칸. 타입 검사기가 알도록 적어 둔다
    # 만든 사람: 세션의 사용자 id 글자. 외래 키가 아니다(FK 로 할지는 X1 의 판단).
    uploaded_by = models.CharField(max_length=64)
    file_name = models.CharField(max_length=255)  # 표시용. 저장소 키에는 들어가지 않는다
    storage_key = models.CharField(max_length=255, unique=True)  # 서버가 짓는다(core/calc/documents.py)
    # 만들 때 클라이언트가 말한 크기. 서명 조건이 되고, 올림 확인이 저장소의 크기와 같은지 본다.
    size_bytes = models.BigIntegerField()
    # 저장소가 준 글자 그대로(따옴표째). NULL = 아직 안 올라왔다.
    # 길이 255 는 어림이다: 로컬(Versity)은 34자, 멀티파트의 ETag 는 더 길다.
    etag = models.CharField(max_length=255, null=True)  # noqa: DJ001  NULL = 아직 안 올라왔다
    # ★ 지금은 쓰는 코드가 없다. 워커(W1b)가 파서의 답에서 채울 자리다.
    sha256 = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 아직 모른다
    status = models.CharField(max_length=32)
    uploaded_at = models.DateTimeField(null=True)
    # ── 판 사슬과 쪽 재기(X1b-1 이 칸을 세움, X1b-2a 가 씀 — 쓰는 곳 esgapi/core/service/services/documents.py) ──
    # 보고서의 해(사용자가 말한 값 — 만들기·PATCH). NULL = 모른다. 범위 CHECK(1900~2100)는 어림이다.
    report_year = models.SmallIntegerField(null=True)
    # 같은 보고서의 앞 판(수정본 사슬). 같은 회사 외래 키 (company_id, previous_document_id) → core_documents 의 짝을
    # migrations/0001 이 단다(받침 ⑤). PROTECT: 뒤 판이 가리키는 문서는 지워지지 않는다. NULL = 첫 판.
    # 갈래 금지(한 문서의 뒤 판은 하나): 부분 UNIQUE core_documents_previous_uniq.
    # 쓰는 길은 PATCH 하나(만들기는 받지 않음)
    previous_document = models.ForeignKey("self", on_delete=models.PROTECT, null=True, related_name="+")
    previous_document_id: int | None
    page_count = models.IntegerField(null=True)  # 쪽 수(≥1). NULL = 모른다(올림 확인이 못 쟀다)
    # NULL = 모른다(못 열었거나 재지 않음). 앞 TEXT_PROBE_PAGES 쪽 기준 — X1b-2
    has_text = models.BooleanField(null=True)

    objects = CompanyScopedManager["DocumentRow"]()
    unscoped = models.Manager["DocumentRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "core_documents"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(status__in=DOCUMENT_ROW_STATUSES), name="core_documents_status_check"
            ),
            models.CheckConstraint(condition=models.Q(size_bytes__gte=1), name="core_documents_size_bytes_check"),
            models.CheckConstraint(
                condition=models.Q(report_year__isnull=True) | models.Q(report_year__gte=1900, report_year__lte=2100),
                name="core_documents_report_year_check",
            ),
            models.CheckConstraint(
                condition=models.Q(page_count__isnull=True) | models.Q(page_count__gte=1),
                name="core_documents_page_count_check",
            ),
            models.UniqueConstraint(
                fields=("company", "previous_document"),
                condition=models.Q(previous_document__isnull=False),
                name="core_documents_previous_uniq",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


# ── 문서 산출물(RP2a ① — MARC-ENT-514, 계약 core/documents/contract.py 의 core.doc-artifact@1) ───────────
# 값의 갈래. core/documents/contract.py 의 STATUSES·LAYOUTS 와 같아야 한다(core/tests/documents/test_tables.py 가
# 견준다. import 하지 않는 까닭은 위 LLM_RESULT_KINDS 와 같다 — 마이그레이션이 값을 굳힌다).
DOCUMENT_ARTIFACT_STATUSES = ("ready", "too_large")
DOCUMENT_ARTIFACT_LAYOUTS = (1, 2)


class DocumentArtifactRow(CompanyScopedModel):
    """파서 출력 한 벌(표 core_document_artifacts) — 회사·원본 sha256·분해 판·EPOCH 마다 한 행. 불변 행이다.

    ★ 앱 역할은 SELECT·INSERT 만(migrations/0003). 판이 오르면 새 행, 옛 행은 그대로. 지우는 길 0.
    ★ 읽는 길은 core/documents/selectors.py 하나이고 늘 uses ⋈ core_documents(같은 회사)를 지난다 — 문서 행이 안 보이면
      산출물도 없다. 본문 칸 둘(jsonb)은 목록·찾기에 싣지 않는다(.defer — 글자 자리는 상자를 그릴 때만).
    status `ready` ⇔ 본문 둘 NOT NULL, `too_large` ⇔ 둘 NULL(본문이 ARTIFACT_MAX_BYTES 를 넘음 — 다시 분해하지 않는다).
    셋째 칸 `chart_labels`(도표 라벨, 밴드 CHL1 — migrations/0005)는 판 2 에서 파서가 냈을 때만 차고, too_large 면 NULL.
    쓰는 곳은 core/documents/services.py 의 ensure_artifact 하나다.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    contract = models.CharField(max_length=40)  # core.doc-artifact@1
    epoch = models.SmallIntegerField()
    source_sha256 = models.CharField(max_length=64)
    layout = models.SmallIntegerField()
    parser_name = models.CharField(max_length=40)  # 보이기용(열쇠 아님)
    parser_version = models.CharField(max_length=40)  # 보이기용(열쇠 아님 — contract.py 의 EPOCH 규칙)
    status = models.CharField(max_length=16)
    page_count = models.IntegerField()
    body_bytes = models.BigIntegerField()
    # 따옴표 주석은 타입 검사기에게만 하는 말이다. NULL = too_large
    document: "models.JSONField[dict[str, object] | None]" = models.JSONField(null=True)
    char_places: "models.JSONField[dict[str, object] | None]" = models.JSONField(null=True)
    # NULL = 칸 없음(EPOCH 1 행·판 1·파서가 내지 않음·too_large). 비었어도 찾은 것이면 객체다(CHL1)
    chart_labels: "models.JSONField[dict[str, object] | None]" = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager["DocumentArtifactRow"]()
    unscoped = models.Manager["DocumentArtifactRow"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "core_document_artifacts"
        constraints = (
            models.UniqueConstraint(
                fields=("company", "contract", "source_sha256", "layout", "epoch"),
                name="core_document_artifacts_key_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=DOCUMENT_ARTIFACT_STATUSES), name="core_document_artifacts_status_check"
            ),
            models.CheckConstraint(
                condition=models.Q(layout__in=DOCUMENT_ARTIFACT_LAYOUTS), name="core_document_artifacts_layout_check"
            ),
            models.CheckConstraint(condition=models.Q(epoch__gte=1), name="core_document_artifacts_epoch_check"),
            models.CheckConstraint(
                condition=models.Q(source_sha256__regex=r"^[0-9a-f]{64}$"), name="core_document_artifacts_sha256_check"
            ),
            models.CheckConstraint(
                condition=models.Q(page_count__gte=1, body_bytes__gte=0), name="core_document_artifacts_sizes_check"
            ),
            models.CheckConstraint(
                condition=models.Q(status="ready", document__isnull=False, char_places__isnull=False)
                | models.Q(
                    status="too_large", document__isnull=True, char_places__isnull=True, chart_labels__isnull=True
                ),
                name="core_document_artifacts_body_check",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class DocumentArtifactUseRow(CompanyScopedModel):
    """문서(그 etag 의 바이트) ↔ 산출물 이음(표 core_document_artifact_uses). 불변 행이다.

    같은 PDF 의 다른 문서 행(같은 회사)은 산출물 하나를 같이 쓴다. 다시 생성은 이 행으로 저장소·파서 0.
    문서·산출물은 같은 회사 외래 키(migrations/0003, PROTECT). 앱 역할은 SELECT·INSERT 만.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    document = models.ForeignKey(DocumentRow, on_delete=models.PROTECT, related_name="+")
    document_id: int
    document_etag = models.CharField(max_length=255)  # core_documents.etag 과 같은 상한
    artifact = models.ForeignKey(DocumentArtifactRow, on_delete=models.PROTECT, related_name="+")
    artifact_id: int
    contract = models.CharField(max_length=40)
    layout = models.SmallIntegerField()
    epoch = models.SmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager["DocumentArtifactUseRow"]()
    unscoped = models.Manager["DocumentArtifactUseRow"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "core_document_artifact_uses"
        constraints = (
            models.UniqueConstraint(
                fields=("company", "document", "document_etag", "contract", "layout", "epoch"),
                name="core_document_artifact_uses_key_uniq",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


# ── 감사 기록(AU1a — MARC-ENT-291) ───────────────────────────────────
# 값의 갈래. esgapi/core/calc/audit.py 의 AUDIT_ACTIONS·AUDIT_RESULTS·ACTOR_KINDS·DETAIL_MAX_OCTETS 와 같아야 한다
# (core/tests/test_models.py 가 견준다. import 하지 않는 까닭은 위 LLM_RESULT_KINDS 와 같다 — 마이그레이션이 값을
# 굳힌다).
AUDIT_EVENT_ACTIONS = (
    "login",
    "logout",
    "upload",
    "run",
    "download",
    "setting_change",
    "adopt",
    "exclude",
    "confirm",
)
AUDIT_EVENT_RESULTS = ("success", "failure")
AUDIT_ACTOR_KINDS = ("admin", "service", "command", "anonymous")
AUDIT_DETAIL_MAX_OCTETS = 1024  # 어림(근거 없는 수)


class AuditEventRow(CompanyScopedModel):
    """감사 기록 한 줄(표 core_audit_events): 누가·언제·무엇을 했는가. 덧붙이기만 하는 표다.

    ★ 지울 수 없음은 **앱 역할에게만**이다: 앱 역할(esg_app)의 권한은 SELECT·INSERT 뿐이라(migrations/0001_initial.py)
      요청·워커가 고치거나 지우지 못한다. 주인 역할(마이그레이션·psql)은 고치고 지울 수 있다(2차 보존 정리의 자리).
    BaseModel 을 잇지 않는다: updated_at 이 뜻이 없다(LlmCallLogRow 와 같은 꼴). 쓰는 곳은
    esgapi/core/service/services/audit.py 의 record_event 하나, 읽는 곳은 esgapi/core/service/selectors/audit.py 하나다.

    회사 칸이 NULL 인 줄 = 운영 관리자 쪽 사건(운영 관리자의 로그인·명령, 회사를 못 찾은 모르는 아이디의 로그인).
    그 줄을 여는 길은 이름 붙은 입구 operator_rows() 하나다. 부르는 자리는 core/tests/isolation/test_static_rules.py 의
    AUDIT_ENTRANCES 가 허용 목록으로 지킨다(core/service/selectors/audit.py·core/service/services/audit.py).
    사람 이름은 싣지 않는다(core 의 기록 지점은 이름을 모른다 — 읽을 때 user 가 푼다). 비밀번호·토큰·본문·로그인에 넣은
    아이디 글자는 어느 칸에도 없다(부르는 자리의 시험이 지킨다 — target_label·detail 은 부른 쪽이 준 글자 그대로다).
    """

    id = models.BigAutoField(primary_key=True)
    # ★ 외래 키가 아니다(회사가 지워져도 감사 기록은 남는다). NULL = 운영 관리자 쪽 사건.
    #   무효 조건: 없는 회사 id 로도 행이 남는다(오타를 DB 가 잡지 못한다).
    company_id = models.BigIntegerField(null=True)
    at = models.DateTimeField()  # 사건 때(부른 쪽의 now)
    actor_kind = models.CharField(max_length=16)
    actor_user_id = models.BigIntegerField(null=True)  # 외래 키가 아니다. NULL = 명령·누구인지 모름
    action = models.CharField(max_length=32)  # 화면 배지(AUDIT_EVENT_ACTIONS)
    event = models.CharField(max_length=40)  # 가는 이름(로그의 사건 이름과 같다 — login_failed 등)
    result = models.CharField(max_length=16)
    reason = models.CharField(max_length=40, null=True)  # noqa: DJ001  NULL = 실패 아님(실패 까닭의 코드)
    target_kind = models.CharField(max_length=40, null=True)  # noqa: DJ001  NULL = 대상 없음
    target_id = models.BigIntegerField(null=True)  # 외래 키가 아니다
    target_label = models.CharField(max_length=255, null=True)  # noqa: DJ001  그때의 이름(아이디·파일 이름)
    # 이름 있는 칸만(changed_fields — 바뀐 칸의 이름, 값 0 · module — 모듈 id, AD4S).
    # 따옴표 주석은 타입 검사기에게만 하는 말이다.
    detail: "models.JSONField[dict[str, list[str] | str]]" = models.JSONField(default=dict)
    request_id = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 요청 밖(명령)

    objects = CompanyScopedManager["AuditEventRow"]()
    unscoped = models.Manager["AuditEventRow"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "core_audit_events"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(action__in=AUDIT_EVENT_ACTIONS), name="core_audit_events_action_check"
            ),
            models.CheckConstraint(
                condition=models.Q(result__in=AUDIT_EVENT_RESULTS), name="core_audit_events_result_check"
            ),
            models.CheckConstraint(
                condition=models.Q(actor_kind__in=AUDIT_ACTOR_KINDS), name="core_audit_events_actor_kind_check"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.lookups.LessThanOrEqual(
                        models.Func(
                            Cast("detail", output_field=models.TextField()),
                            function="octet_length",
                            output_field=models.IntegerField(),
                        ),
                        AUDIT_DETAIL_MAX_OCTETS,
                    )
                ),
                name="core_audit_events_detail_size_check",
            ),
            # 고객사 사람의 줄은 회사가 있다: 회사 없음 칸(어느 회사를 골라도 보이는 칸)으로 새는 쓰기 실수를 막는다.
            models.CheckConstraint(
                condition=~models.Q(actor_kind="service", company_id__isnull=True),
                name="core_audit_events_service_company_check",
            ),
        )
        indexes = (
            models.Index(fields=["company_id", "at"], name="core_audit_company_at"),
            models.Index(fields=["at"], name="core_audit_at"),
            models.Index(fields=["action", "at"], name="core_audit_action_at"),
        )

    def __str__(self) -> str:
        return f"{self.event}#{self.id}"

    @classmethod
    def operator_rows(cls) -> models.QuerySet["AuditEventRow"]:
        """회사 칸이 NULL 인 줄(운영 관리자 쪽)을 여는 이름 붙은 입구. 회사 바닥(for_company) 밖으로 여는 유일한 길이다.
        몸의 조건은 company_id IS NULL 하나다(남의 회사 줄은 여기로 열리지 않는다 — test_static_rules 의
        audit_entrance_problems 가 몸을 읽는다). 부르는 자리는 AUDIT_ENTRANCES 둘(User._admins() 와 같은 꼴)."""
        return models.QuerySet["AuditEventRow"](model=cls).filter(company_id__isnull=True)
