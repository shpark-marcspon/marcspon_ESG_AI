"""runs 의 모델: 문서에 걸린 일감(JobRow, 표 run_jobs)과 흐름의 실행 넷(X1b-1) — 실행(RunRow, run_runs)·단계
(RunStepRow, run_steps)·결과(RunResultRow, run_results)·출력 파일(RunFileRow, run_files). JobRow 는 X1a 때 core 의
models.py 에서 옮겼다 — 칸은 그대로, 표·제약·색인 이름은 run_ 접두로 바꿨다. 표·크기 CHECK·같은 회사 외래 키·앱 역할의
권한은 migrations/0001_initial.py.

★ 실행 넷은 지우지 않는다(MARC-ENT-208 — 성공한 실행의 단계 산출도). 앱 역할에게 DELETE·TRUNCATE 가 없고, 결과·파일은
  UPDATE 도 없다(한 번 쓰고 끝 — MARC-ENT-210 (1)). 하위 셋(단계·결과·파일)은 실행과, 실행은 문서와 같은 회사다
  (복합 FK).
★ 흐름마다 표를 만들지 않는다: 결과·단계 산출은 JSON 본문(큰 것은 저장소의 파일)으로만 둔다.
★ 다른 앱은 runs 로 FK·마이그레이션 의존을 두지 않는다(MARC-ENT-210 (1)).
★ core 의 문서 쪽 두 파일(core/service/selectors/documents.py·services/documents.py)이 JobRow 를 직접 읽고 쓴다 —
  .importlinter 계약 가 의 이름 붙인 예외 두 줄이다(옛 분해 일감 길 — 데이터 검증 서버 밴드가 걷는다,
  sid:MARC-ISSUE-233).
"""

import json
from typing import TYPE_CHECKING, Any, cast

from django.db import models

from esgapi.core.flows.binding import DOCUMENTLESS_OPTIONS_MAX_OCTETS
from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel
from esgapi.core.models import BaseModel, DocumentRow

# 상태의 값. esgapi/core/calc/documents.py 의 JOB_STATUSES 와 같아야 한다(테스트가 견준다. 여기서 그 튜플을
# import 하지 않는 까닭: 마이그레이션이 값을 문면에 굳히므로, 상태가 늘면 새 마이그레이션을 같이 내야 한다).
JOB_ROW_STATUSES = ("queued", "processing", "done", "failed")

# 실행·단계·목적의 값. runs/service/schemas/runs.py 의 RunStatus·RunStepStatus 와 같아야 한다(테스트가 견준다 —
# import 하지 않는 까닭은 위와 같다).
RUN_ROW_STATUSES = ("queued", "processing", "done", "failed")
RUN_STEP_STATUSES = ("pending", "running", "done", "failed")
# 구획의 값(RM1a — run_segments). 전이: pending→running · running→running(새 시도) · running→done|failed. 끝난 구획
# (done·failed)은 다시 쓰지 않는다(그 실행 안에서 끝 — 다시 부름은 RM1c 의 새 실행).
RUN_SEGMENT_STATUSES = ("pending", "running", "done", "failed")
# service = 고객사의 실행, test = 테스트 비교(AD-03·AD-04 「테스트」 — 지금 쓰는 길 0, 칸만)
RUN_PURPOSES = ("service", "test")
# 크기 상한(바이트 — PostgreSQL 이 jsonb 를 다시 적은 글자의 octet_length). ★ 전부 어림이다(잰 값이 아니다).
# 결과 8MiB: 그린워싱 목데이터 69,152바이트/문장 22 에서 문장 534건이면 약 1.7MB(추정)의 다섯 배 안팎.
RUN_OPTIONS_MAX_OCTETS = 16 * 1024  # 어림. 옵션 앱 상한의 기본값(= core/flows/binding.py 의 DEFAULT) — 흐름별 등록
# options 의 DB 상한(migrations/0002 의 OPTIONS_CEILING_OCTETS 와 같다 — 테스트가 견준다). 흐름의 앱 상한(많아야
# 256KiB)을 감싼 꼴(OrderedJSONField)로 적으면 안쪽 따옴표·역빗금마다 역빗금이 붙어 최악 두 배가 되고, 껍데기
# {"ordered@1": ""} 가 17바이트다(+64 는 그 몫의 넉넉함). 앱 상한은 raw JSON 으로 재고 이 값은 그 위의 잠금이다.
RUN_OPTIONS_CEILING_OCTETS = 2 * DOCUMENTLESS_OPTIONS_MAX_OCTETS + 64
RUN_VERSIONS_MAX_OCTETS = 16 * 1024  # 어림
RUN_STEP_DATA_MAX_OCTETS = 16 * 1024 * 1024  # 어림(data·partial 각각)
RUN_RESULT_BODY_MAX_OCTETS = 8 * 1024 * 1024  # 어림
# 구획 산출 data 의 DB 상한(migrations/0005 의 SEGMENT_DATA_MAX_OCTETS 와 같다 — 테스트가 견준다). core 의 앱 상한
# SEGMENT_DATA_MAX_OCTETS(core/flows/types.py)가 이것의 절반이다(감싼 꼴은 최악 두 배). 어림
RUN_SEGMENT_DATA_MAX_OCTETS = 1024 * 1024
# 출력 파일 이름의 꼴(저장소 키의 한 마디가 된다 — runs/calc/keys.py)
RUN_FILE_NAME = r"^[A-Za-z0-9._-]{1,100}$"


ORDERED_JSON_TAG = "ordered@1"

if TYPE_CHECKING:
    _JSONBase = models.JSONField[dict[str, object] | None]
else:
    _JSONBase = models.JSONField


class OrderedJSONField(_JSONBase):
    """쓴 열쇠 차례를 그대로 돌려주는 JSON 칸(X1b-2b ㉔). jsonb 는 열쇠를 길이·글자 차례로 다시 늘어세운다.

    dict 는 {"ordered@1": "<json 글자>"} 로 감싸 jsonb 에 넣고, 읽을 때 푼다(감싸지 않은 옛 값은 그대로). 스키마는
    맨 JSONField 와 같다(deconstruct 가 그 이름 — 마이그레이션 0).
    ★ `data__…` 같은 열쇠 조회·날 SQL 의 jsonb 읽기는 감싼 꼴을 본다. 제품에 그런 읽기를 두지 않는다.
      예외 둘: runs/service/selectors/runs.py 의 run_keys(options 의 batchId·part 투영, MARC-TICK-251)와
      run_page_brief(데이터 검증 목록의 경로 투영 — 안쪽 글자에 \\u0000 이 든 줄은 풀지 않는다, MARC-ISSUE-347).
    """

    def deconstruct(self) -> Any:
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.JSONField", args, kwargs

    def get_prep_value(self, value: Any) -> Any:
        value = super().get_prep_value(value)
        if isinstance(value, dict):
            # allow_nan=False: NaN·Infinity 는 jsonb 가 받지 않는다 — 감싼 글자 안에 숨어 지나가지 않게 쓰기에서 거절
            return {ORDERED_JSON_TAG: json.dumps(value, ensure_ascii=False, allow_nan=False)}
        return value

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        found: object = super().from_db_value(value, expression, connection)
        if not isinstance(found, dict):
            return found
        items = cast("dict[str, object]", found)
        wrapped = items.get(ORDERED_JSON_TAG) if len(items) == 1 else None
        return json.loads(wrapped) if isinstance(wrapped, str) else items


class JobRow(BaseModel, CompanyScopedModel):
    """문서 하나에 걸린 일감 한 건(표 run_jobs). 요청 밖에서 도는 일의 상태를 적는 자리다.

    ★ 넣지 않는 것: 일의 결과 본문. `summary` 는 「작은 요약」이고 DB 가 크기를 막는다
      (migrations/0001 의 CHECK: 글자로 4096바이트 이하. 4096 은 어림이다).
    ★ 행은 `queued` 로 만들어진다(W1a 때). attempts·error_*·summary·lease_expires_at·finished_at 을 쓰는
      코드는 워커(W1b)의 것이다. `kind` 에는 CHECK 가 없다(값은 core/calc/documents.py 의 JOB_KINDS 로 서비스가 거른다).
    """

    id = models.BigAutoField(primary_key=True)
    # 문서 행의 회사와 같은 값이다(서비스가 문서 행에서 읽어 적는다). 같은 회사 외래 키
    # (company_id, document_id) → core_documents (company_id, id) 의 반쪽이다(migrations/0001, 받침 ⑤).
    # 문서의 회사와 다르면 DB 가 거절한다. 글자 참조인 까닭은 DocumentRow.company 와 같다.
    # 따옴표 주석은 타입 검사기에게만 하는 말이다(글자 참조라 django-types 가 대상 모델을 모른다).
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    # PROTECT: 일감이 있는 문서는 지워지지 않는다(앱 역할에는 DELETE 권한도 없다).
    document = models.ForeignKey(DocumentRow, on_delete=models.PROTECT, related_name="jobs")
    document_id: int  # Django 가 외래 키마다 만들어 주는 칸. 타입 검사기가 알도록 적어 둔다
    kind = models.CharField(max_length=32)
    status = models.CharField(max_length=32)
    attempts = models.IntegerField(default=0)
    error_code = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 실패하지 않았다
    error_message = models.CharField(max_length=500, null=True)  # noqa: DJ001  위와 같다
    summary: "models.JSONField[dict[str, object]]" = models.JSONField(default=dict)
    lease_expires_at = models.DateTimeField(null=True)  # 워커가 이 일을 쥐고 있는 기한. NULL = 아무도 안 쥐었다
    finished_at = models.DateTimeField(null=True)

    objects = CompanyScopedManager["JobRow"]()
    unscoped = models.Manager["JobRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "run_jobs"
        constraints = (
            models.CheckConstraint(condition=models.Q(status__in=JOB_ROW_STATUSES), name="run_jobs_status_check"),
            models.CheckConstraint(condition=models.Q(attempts__gte=0), name="run_jobs_attempts_check"),
        )
        indexes = (models.Index(fields=["document", "created_at"], name="run_jobs_document_created"),)

    def __str__(self) -> str:
        return str(self.id)


# ── 흐름의 실행(X1b-1) ───────────────────────────────────────────────


class RunRow(BaseModel, CompanyScopedModel):
    """흐름의 실행 한 건(표 run_runs): 문서 하나(문서 없는 흐름이면 옵션만)를 등록된 흐름 하나로 돌린다. 실행은 늘
    새로 만든다.

    칸의 뜻(AU1b 가 믿는다 — 발주서 §2-6, 커밋 ① 뒤 바꾸지 않는다):
      module·flow_id      만들 때 고른 모듈 id·흐름 id@판(이후 안 바뀜)
      document            실행한 문서. NULL = 문서 없는 흐름의 실행(ND1 — 입력은 options, 쓴 차례로 읽힌다)
      created_by_user_id  실행을 만든 사용자 id(외래 키가 아니다 — runs 는 user 를 모른다.
                          DocumentRow.uploaded_by 의 뜻)
      status              queued → processing → done|failed. processing → queued 는 다시 넣기(협조 마감·소프트 제한·
                          잠깐 오류)뿐, 끝난 뒤 안 바뀜
      started_at          **첫** 잡기 때 한 번(다시 넣어도 안 바뀜). NULL = 한 번도 안 돌았다
      finished_at         done·failed 로 끝날 때 한 번
      failed_step         단계에서 실패했을 때만. 실행기의 실패(result_too_large 등)는 NULL
      attempts            잡은 횟수(진행 있는 시도 포함 — 시도 상한의 셈과 다르다)
      versions            만들 때 한 번: {"flow": <id@판>, …끼움 몫}. 그린워싱 aiSetting·evalPromptSha256·aiSettingId
      purpose             service(늘 — 이 밴드에서 test 를 쓰는 길 0)
      idempotency_key     만들 때 한 번: 요청 머리 Idempotency-Key(소문자 UUID — IK1). 이후 안 바뀜. NULL = 열쇠 없이
                          만든 실행. (회사, 만든 사람, 열쇠)가 유일하다(run_runs_idempotency_uniq — 만료 없음)
      idempotency_sha256  만들 때 한 번: 그 요청 본문의 정규화 sha256(runs/calc/idempotency.py). 이후 안 바뀜. 열쇠와
                          짝이다 — 둘 다 NULL 이거나 둘 다 값(run_runs_idempotency_pair_check)
      launch_key          만들 때 한 번: 본문 launchKey(소문자 UUID — LK1). 같이 시작한 실행(사람 동작 한 번)의 묶음
                          열쇠라 유일이 아니다. 이후 안 바뀜. NULL = 묶음 없이 만든 실행. 묶음의 첫 id·차례·수는
                          저장하지 않고 읽을 때 센다(runs/service/selectors/operator.py 의 _launches — (회사, 만든
                          사람, 열쇠))
    ★ AU1b 가 믿지 않는 칸: stalled_attempts(진행 없이 끝난 시도 수 — 시도 상한은 이 칸으로)·progress_attempt
      (마지막으로 진행을 남긴 시도 번호. 진행 = 단계의 done 이 저장된 값보다 커진 체크포인트 또는 단계 끝남).
      실행기 안쪽의 셈이라 뜻을 X1b-2 가 바꿀 수 있다.
    """

    id = models.BigAutoField(primary_key=True)
    # 문서 행의 회사와 같은 값이다(같은 회사 외래 키 (company_id, document_id) → core_documents 의 반쪽 —
    # JobRow 와 같다).
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    # PROTECT: 실행이 있는 문서는 지워지지 않는다. NULL = 문서 없는 흐름의 실행(ND1) — 같은 회사 외래 키는 MATCH
    # SIMPLE 이라 NULL 이면 비껴간다(회사는 company 칸이 지킨다).
    document = models.ForeignKey(DocumentRow, on_delete=models.PROTECT, related_name="runs", null=True)
    document_id: int | None
    module = models.CharField(max_length=64)
    flow_id = models.CharField(max_length=100)
    # 쓴 열쇠 차례 그대로(ND1 — 흐름이 옵션을 입력 차례로 읽는다). 스키마는 맨 JSONField 와 같다
    options: "models.JSONField[dict[str, object]]" = OrderedJSONField(default=dict)  # pyright: ignore[reportAssignmentType] — default=dict 라 None 이 아니다
    versions: "models.JSONField[dict[str, object]]" = models.JSONField(default=dict)
    purpose = models.CharField(max_length=16, default="service")
    status = models.CharField(max_length=32)
    attempts = models.IntegerField(default=0)
    stalled_attempts = models.SmallIntegerField(default=0)
    progress_attempt = models.IntegerField(null=True)  # NULL = 진행을 남긴 시도가 아직 없다
    lease_expires_at = models.DateTimeField(null=True)  # 워커가 이 실행을 쥐고 있는 기한. NULL = 아무도 안 쥐었다
    created_by_user_id = models.BigIntegerField()
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    failed_step = models.CharField(max_length=100, null=True)  # noqa: DJ001  NULL = 단계에서 실패하지 않았다
    error_code = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 실패하지 않았다
    # 사람에게 보일 고정 글(예외 원문은 로그에만).
    error_message = models.CharField(max_length=500, null=True)  # noqa: DJ001  위와 같다
    # 앞 실행의 id(외래 키가 아니다 — X1b-2 가 채운다). NULL = 처음부터 돈 실행
    resumed_from_run_id = models.BigIntegerField(null=True)
    idempotency_key = models.CharField(max_length=36, null=True)  # noqa: DJ001  NULL = 열쇠 없이 만든 실행(IK1)
    idempotency_sha256 = models.CharField(max_length=64, null=True)  # noqa: DJ001  위와 같다(열쇠와 짝)
    launch_key = models.CharField(max_length=36, null=True)  # noqa: DJ001  NULL = 묶음 없이 만든 실행(LK1)
    # 펼침 단계의 구획을 쪽지에 맡기고 지휘 시도가 주차한 시각(RM1b — 0006). NULL = 주차 아님(장벽 흐름·직렬은 늘 NULL).
    # 주차 중 status 는 processing 그대로이고 실행 임대는 구획 잡기가 당긴다. 깨우기·잡기 Take·끝내기가 비운다.
    parked_at = models.DateTimeField(null=True)

    objects = CompanyScopedManager["RunRow"]()
    unscoped = models.Manager["RunRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "run_runs"
        constraints = (
            models.CheckConstraint(condition=models.Q(status__in=RUN_ROW_STATUSES), name="run_runs_status_check"),
            models.CheckConstraint(condition=models.Q(purpose__in=RUN_PURPOSES), name="run_runs_purpose_check"),
            models.CheckConstraint(condition=models.Q(attempts__gte=0), name="run_runs_attempts_check"),
            models.CheckConstraint(condition=models.Q(stalled_attempts__gte=0), name="run_runs_stalled_attempts_check"),
            models.CheckConstraint(
                condition=models.Q(progress_attempt__isnull=True) | models.Q(progress_attempt__gte=1),
                name="run_runs_progress_attempt_check",
            ),
            # IK1: 같은 사람의 같은 열쇠는 실행 하나(만료 없음). 동시 두 요청의 뒤의 것은 여기서 23505 → 앞 실행을 읽음
            models.UniqueConstraint(
                fields=["company", "created_by_user_id", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="run_runs_idempotency_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(idempotency_key__isnull=True, idempotency_sha256__isnull=True)
                | models.Q(idempotency_key__isnull=False, idempotency_sha256__isnull=False),
                name="run_runs_idempotency_pair_check",
            ),
        )
        indexes = (
            models.Index(fields=["company", "created_at"], name="run_runs_company_created"),
            models.Index(fields=["company", "document", "created_at"], name="run_runs_company_doc_created"),
            models.Index(fields=["created_at"], name="run_runs_created"),  # 운영 관리자의 모든 회사(AU1b)
            # LK1: 묶음 셈의 launch_key IN 읽기. 유일 아님(묶음 = 실행 여럿), 옛 행(NULL)은 밖
            models.Index(
                fields=["company", "launch_key"],
                condition=models.Q(launch_key__isnull=False),
                name="run_runs_launch_key",
            ),
        )

    def __str__(self) -> str:
        return str(self.id)


class RunStepRow(BaseModel, CompanyScopedModel):
    """실행의 단계 하나(표 run_steps). 실행을 만들 때 흐름이 선언한 단계 전부를 선언 차례로 pending 으로 만든다.

    data    끝난 단계의 산출(StepOutput.data — 체크포인트. 이어 가기의 carried)
    partial 단계 안의 부분 산출(StepContext.checkpoint — 이어 가기의 resume). 저장 자리는 실행기의 step_progress 하나
    단계 산출 파일은 run_files(step = 이 이름)에 있다.
    data·partial 은 쓴 열쇠 차례로 읽힌다(OrderedJSONField — DB 안은 감싼 글자, 스키마는 맨 jsonb).
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    # 실행의 회사와 같은 값이다(같은 회사 외래 키 (company_id, run_id) → run_runs).
    run = models.ForeignKey(RunRow, on_delete=models.PROTECT, related_name="steps")
    run_id: int
    name = models.CharField(max_length=100)
    position = models.IntegerField()  # 선언 차례(0부터)
    status = models.CharField(max_length=16)
    done = models.IntegerField(null=True)
    total = models.IntegerField(null=True)
    data: "models.JSONField[dict[str, object] | None]" = OrderedJSONField(null=True)
    partial: "models.JSONField[dict[str, object] | None]" = OrderedJSONField(null=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)

    objects = CompanyScopedManager["RunStepRow"]()
    unscoped = models.Manager["RunStepRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "run_steps"
        constraints = (
            models.CheckConstraint(condition=models.Q(status__in=RUN_STEP_STATUSES), name="run_steps_status_check"),
            models.CheckConstraint(condition=models.Q(position__gte=0), name="run_steps_position_check"),
            models.UniqueConstraint(fields=["run", "name"], name="run_steps_run_name_uniq"),
            models.UniqueConstraint(fields=["run", "position"], name="run_steps_run_position_uniq"),
        )

    def __str__(self) -> str:
        return f"{self.run_id}:{self.name}"


class RunSegmentRow(BaseModel, CompanyScopedModel):
    """펼침 단계의 구획 하나(표 run_segments — RM1a, MARC-ENT-618). 첫 시도의 segments_planned 가 계획의 구획 전부를
    계획 차례로 pending 으로 만든다. 다음 시도는 같은 계획이면 행을 더하지 않는다(다르면 segments_mismatch).

    step        펼침 단계 이름(run_steps.name 과 같은 상한)
    position    계획 차례(0부터)
    kind·key    구획 열쇠(key = 정규화 칸 {kind, span, documentSha256, parserVersion}). span 은 위치 표지만 — 문서 글 0
    key_sha256  열쇠의 sha256(core/flows/types.segment_key_sha256). 호출 기록의 segment 칸이 이 값이다
    status      pending → running → done|failed. running → running 은 새 시도(앞 시도가 죽었거나 잠깐 오류)
    attempts    그 구획을 시작한 횟수(segment_started 마다 +1)
    data        done 일 때만: 구획 산출(SegmentOutput.data — 쓴 열쇠 차례)
    error_code  failed 일 때만: 실행기가 지은 code(runs/calc/errors.py 의 step_error_code)
    ★ 지우지 않는다(실행 표와 같다 — MARC-ENT-208). 앱 역할에 DELETE 가 없다.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    # 실행의 회사와 같은 값이다(같은 회사 외래 키 (company_id, run_id) → run_runs).
    run = models.ForeignKey(RunRow, on_delete=models.PROTECT, related_name="segments")
    run_id: int
    step = models.CharField(max_length=100)
    position = models.IntegerField()
    kind = models.CharField(max_length=32)
    key: "models.JSONField[dict[str, object]]" = models.JSONField()
    key_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=16)
    attempts = models.IntegerField(default=0)
    data: "models.JSONField[dict[str, object] | None]" = OrderedJSONField(null=True)
    error_code = models.CharField(max_length=64, null=True)  # noqa: DJ001  NULL = 실패하지 않았다
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    # 구획 쪽지가 이 구획을 쥐고 있는 기한(RM1b — 0006). running 일 때만 값. NULL 인 running = 아무도 안 쥠(놓음·직렬)
    lease_expires_at = models.DateTimeField(null=True)
    # done 일 때만(병렬 끝냄이 적는다 — 직렬은 NULL): data 를 json 기본 구분자로 적은 바이트. 단계 합 검사(635-2)
    data_octets = models.IntegerField(null=True)

    objects = CompanyScopedManager["RunSegmentRow"]()
    unscoped = models.Manager["RunSegmentRow"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "run_segments"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(status__in=RUN_SEGMENT_STATUSES), name="run_segments_status_check"
            ),
            models.CheckConstraint(condition=models.Q(position__gte=0), name="run_segments_position_check"),
            models.CheckConstraint(condition=models.Q(attempts__gte=0), name="run_segments_attempts_check"),
            models.CheckConstraint(
                condition=models.Q(key_sha256__regex=r"^[0-9a-f]{64}$"), name="run_segments_key_sha256_check"
            ),
            # 상태와 칸의 짝: done 만 data, failed 만 error_code
            models.CheckConstraint(
                condition=models.Q(status="done", data__isnull=False, error_code__isnull=True)
                | models.Q(status="failed", data__isnull=True, error_code__isnull=False)
                | models.Q(status__in=("pending", "running"), data__isnull=True, error_code__isnull=True),
                name="run_segments_status_fields_check",
            ),
            # RM1b 0006: 임대는 running 만(한 방향 — running·임대 NULL 은 됨) · data_octets 는 done 만·0 이상(한 방향)
            models.CheckConstraint(
                condition=models.Q(lease_expires_at__isnull=True) | models.Q(status="running"),
                name="run_segments_lease_running_check",
            ),
            models.CheckConstraint(
                condition=models.Q(data_octets__isnull=True) | models.Q(status="done", data_octets__gte=0),
                name="run_segments_data_octets_check",
            ),
            models.UniqueConstraint(fields=["run", "step", "key_sha256"], name="run_segments_run_step_sha_uniq"),
            models.UniqueConstraint(fields=["run", "step", "position"], name="run_segments_run_step_position_uniq"),
        )
        indexes = (models.Index(fields=["company", "run"], name="run_segments_company_run"),)

    def __str__(self) -> str:
        return f"{self.run_id}:{self.step}#{self.position}"


class RunResultRow(CompanyScopedModel):
    """실행의 결과 하나(표 run_results): 결과 꼴 이름@판(schema_version)과 JSON 본문. 한 번 쓰고 끝(UPDATE 권한 없음).

    BaseModel 을 잇지 않는다: updated_at 이 뜻이 없다(LlmCallLogRow 와 같은 꼴).
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    run = models.ForeignKey(RunRow, on_delete=models.PROTECT, related_name="results")
    run_id: int
    position = models.IntegerField()  # 흐름이 낸 차례(0부터)
    schema_version = models.CharField(max_length=100)  # 결과의 첫 키 — greenwash.result@1 꼴
    body: "models.JSONField[object]" = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager["RunResultRow"]()
    unscoped = models.Manager["RunResultRow"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "run_results"
        constraints = (
            models.CheckConstraint(condition=models.Q(position__gte=0), name="run_results_position_check"),
            models.UniqueConstraint(fields=["run", "position"], name="run_results_run_position_uniq"),
        )

    def __str__(self) -> str:
        return f"{self.run_id}#{self.position}"


class RunFileRow(CompanyScopedModel):
    """실행의 파일 하나(표 run_files): 바이트는 저장소(storage_key)에, 여기에는 자리와 꼴. 한 번 쓰고 끝.

    step NULL = 흐름의 출력 파일(GET /runs/{runId}/files/{name} 이 내는 것), 글자 = 그 단계의 산출 파일.
    """

    id = models.BigAutoField(primary_key=True)
    company: "models.ForeignKey[models.Model]" = models.ForeignKey("organization.Company", on_delete=models.PROTECT)
    company_id: int
    run = models.ForeignKey(RunRow, on_delete=models.PROTECT, related_name="files")
    run_id: int
    step = models.CharField(max_length=100, null=True)  # noqa: DJ001  NULL = 흐름의 출력 파일
    name = models.CharField(max_length=100)
    media_type = models.CharField(max_length=100)
    storage_key = models.CharField(max_length=255, unique=True)  # 서버가 짓는다(runs/calc/keys.py)
    size_bytes = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager["RunFileRow"]()
    unscoped = models.Manager["RunFileRow"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "run_files"
        constraints = (
            models.CheckConstraint(condition=models.Q(name__regex=RUN_FILE_NAME), name="run_files_name_check"),
            models.CheckConstraint(condition=models.Q(size_bytes__gte=0), name="run_files_size_bytes_check"),
            # 출력 파일(step NULL)도 이름이 겹치지 않는다: NULL 을 같은 값으로 친다(PostgreSQL 15+).
            models.UniqueConstraint(
                fields=["run", "step", "name"], name="run_files_run_step_name_uniq", nulls_distinct=False
            ),
        )

    def __str__(self) -> str:
        return f"{self.run_id}:{self.step or '-'}:{self.name}"
