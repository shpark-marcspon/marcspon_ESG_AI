#!/usr/bin/env bash
# 밴드 X1b-1 의 심은 파손(발주서 band-handoffs/X1b-order.md §3-2, 개정 5). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로
# 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-X1b-1.sh [--commit 1|2|3] [--with-containers] [--only P1,P4]
#
# (-q 를 품은 층 명령에 -vv 를 더해 PASSED 줄이 찍히게 한다 — -v 하나면 -q 와 맞비겨 초록 노드를 못 본다.)
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 그 층의 pytest 가 0 아닌 종료이고, 빨개져야 할
# 시험 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 「초록이어야 함」 노드가 있으면 그것이 통과로
# 찍혀야 한다(P21 — 같은 파일의 다른 검사가 이 파손을 못 본다는 것).
# 커밋 n 에는 커밋 n 까지의 P 만 심는다. 업무·보안·통합 층(컨테이너가 필요)은 --with-containers 일 때만 — 아니면
# 「안 돌림」으로 찍고 잡은 수·심은 수에 넣지 않는다(조용한 초록 0).
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지
# 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 보안 층은 부를 때마다 테스트 DB 를 새로 만들어 마이그레이션한다(심은 마이그레이션이 그대로 들어간다).
# 산출물: X1B1_OUT(기본: 워크트리 곁의 X1b-1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${X1B1_OUT:-$(cd "$ROOT/.." && pwd)/X1b-1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
COMMIT = 3
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2", "3"):
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def cut(pattern: str) -> Callable[[str], str | None]:
    """정규식(DOTALL)에 정확히 한 번 맞는 자리를 지운다."""

    def plant(text: str) -> str | None:
        found = list(re.finditer(pattern, text, flags=re.S))
        return text[: found[0].start()] + text[found[0].end() :] if len(found) == 1 else None

    return plant


RUNS_MIGRATION = Path("esgapi/runs/migrations/0001_initial.py")
SOWNER = "tests/security/test_owner.py"
SRUNS = "tests/security/test_runs.py"
SFK = "tests/security/test_same_company_foreign_keys.py"
SMIG = "tests/security/test_migrations.py"
OWNER_GRANTS = SOWNER + "::test_app_role_reads_every_tenant_table_and_deletes_none"
SEL_RUNS = Path("esgapi/runs/service/selectors/runs.py")
SVC_RUNS = Path("esgapi/runs/service/services/runs.py")
CONTEXT = Path("esgapi/runs/context.py")
TASKS = Path("esgapi/runs/tasks.py")
DEADLINE = Path("esgapi/runs/calc/deadline.py")
CLAIMS = Path("esgapi/runs/calc/claims.py")
SCOPE = "esgapi/core/tests/test_selector_scope.py"
TXN = "esgapi/core/tests/test_transaction_rules.py"
EXEC = "esgapi/runs/tests/test_executor.py"
CTXT = "esgapi/runs/tests/test_context.py"
CALC = "esgapi/runs/tests/calc/test_calc.py"
ACTIONS = Path("esgapi/runs/service/actions/runs.py")
APIS = Path("esgapi/runs/service/apis/runs.py")
JOBS_CALC = Path("esgapi/core/calc/jobs.py")
RAPI = "esgapi/runs/tests/service/apis/test_runs.py"
SHAPE = "esgapi/runs/tests/test_tasks_shape.py"
PERMS = "esgapi/core/tests/test_permissions.py"
CONTRACT = "esgapi/config/tests/test_api_contract.py"
IRUN = "tests_integration/test_run_flow.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
# 통합: 지금 소스로 이미지를 짓고(빌드 잠금 — worker-py 는 build 절이 없고 api-py 의 이미지를 쓴다, compose.yaml) 워커를
# 다시 띄운 뒤 통합 층을 부른다. 환경은 section4 의 통합 단계와 같다(EDK 공개키·짧은 긴 폴링).
INTEGRATION_WRAP = (
    'key="$(uv run --frozen python scripts/dev_edk.py public-key)" || exit 3\n'
    'export EDK_JWT_PUBLIC_KEY="$key" CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1\n'
    '(cd ../.. && scripts/with-build-lock.sh docker compose build api-py > /dev/null 2>&1'
    ' && docker compose up -d --wait worker-py > /dev/null 2>&1) || exit 4\n'
    'exec scripts/test-integration.sh "$@"\n'
)
INTEGRATION = ("통합", ["bash", "-c", INTEGRATION_WRAP, "_", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음, 초록이어야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "runs 0001 의 run_results grant 에 UPDATE",
     [(RUNS_MIGRATION, swap("grant(f'\"{RESULTS}\"', \"SELECT, INSERT\")", "grant(f'\"{RESULTS}\"', \"SELECT, INSERT, UPDATE\")"))],
     [(SECURITY, [SOWNER, SRUNS], {OWNER_GRANTS, SRUNS + "::test_app_role_cannot_change_a_result_or_a_file[results]"}, set())]),
    ("P2", 1, "runs 0001 의 run_steps grant 에 DELETE",
     [(RUNS_MIGRATION, swap("grant(f'\"{STEPS}\"', \"SELECT, INSERT, UPDATE\")", "grant(f'\"{STEPS}\"', \"SELECT, INSERT, UPDATE, DELETE\")"))],
     [(SECURITY, [SOWNER, SRUNS], {OWNER_GRANTS, SRUNS + "::test_app_role_cannot_remove_a_run_row[delete-run_steps]"}, set())]),
    ("P3", 1, "run_steps → run_runs 의 same_company_foreign_key 줄을 지움",
     [(RUNS_MIGRATION, swap("        same_company_foreign_key(table=STEPS, column=\"run_id\", target=RUNS),\n", ""))],
     [(SECURITY, [SFK, SMIG], {SFK + "::test_every_foreign_key_between_company_tables_names_the_company",
                               SMIG + "::test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip"}, set())]),
    ("P4", 1, "run_results 의 크기 CHECK 를 지움",
     [(RUNS_MIGRATION, swap("        size_check(RESULTS, \"body\", RESULT_BODY_MAX_OCTETS),\n", ""))],
     [(SECURITY, [SRUNS], {SRUNS + "::test_a_result_body_over_the_limit_is_refused"}, set())]),
    # ── 커밋 ② 실행기 ──
    ("P5", 2, "runs/service/selectors/runs.py 의 _runs 몸을 RunRow.objects.all() 로",
     [(SEL_RUNS, swap("    return RunRow.for_company(company_id)\n", "    return RunRow.objects.all()\n"))],
     [(PURE, [SCOPE], {SCOPE + "::test_selectors_scope_every_read[runs/service/selectors/runs.py]"}, set())]),
    ("P6", 2, "claim_run 의 _require_transaction 의 raise … 를 pass 로",
     [(SVC_RUNS, swap('        raise NotInTransactionError(f"{name} 는 transaction.atomic() 안에서만 부른다")', "        pass"))],
     [(PURE, [TXN], {TXN + "::test_every_write_sits_inside_a_block[runs/service/services/runs.py]"}, set())]),
    ("P7", 2, "claim_run 이 started_at 을 시도마다 덮어씀",
     [(SVC_RUNS, swap('            started_at=Coalesce(F("started_at"), Value(now)),\n', "            started_at=now,\n"))],
     [(BUSINESS, [EXEC], {EXEC + "::test_started_at_is_the_first_claim_only"}, set())]),
    ("P8", 2, "step_progress 가 partial 을 저장하지 않음(저장 자리는 그 하나)",
     [(SVC_RUNS, swap("update(done=done, total=total, partial=dict(partial), updated_at=now)",
                      "update(done=done, total=total, updated_at=now)"))],
     [(BUSINESS, [EXEC], {EXEC + "::test_past_the_deadline_the_attempt_yields_and_the_next_resumes_from_the_partial"},
       set())]),
    ("P9", 2, "진행 있는 시도도 상한에 셈(finish_run(RunDeferred) 이 progress_attempt 를 보지 않고 늘 +1)",
     [(SVC_RUNS, swap('When(progress_attempt=attempt, then=F("stalled_attempts")), default=F("stalled_attempts") + 1',
                      'When(progress_attempt=-1, then=F("stalled_attempts")), default=F("stalled_attempts") + 1'))],
     [(BUSINESS, [EXEC], {EXEC + "::test_attempts_with_progress_are_not_counted_and_the_run_finishes"}, set())]),
    ("P10", 2, "RunContext.llm() 이 모의 공급사가 아닌 설정으로 지음(mock=False)",
     [(CONTEXT, swap("return build_client(llm_settings(), mock=True, sink=self.sink)",
                     "return build_client(llm_settings(), mock=False, sink=self.sink)"))],
     [(PURE, [CTXT], {CTXT + "::test_the_runner_builds_only_mock_clients_even_when_keys_exist"}, set())]),
    ("P17", 2, "put 을 runs/tasks.py T2 의 with transaction.atomic(durable=True) 몸 안으로",
     [(TASKS, swap("    with transaction.atomic(durable=True):  # T2\n",
                   "    with transaction.atomic(durable=True):  # T2\n"
                   "        documents.default_storage().put(\"k\", content=b\"\", media_type=\"x\")\n"))],
     [(PURE, [TXN], {TXN + "::test_no_outside_call_inside_a_block"}, set())]),
    ("P18", 2, "RunCallSink 가 run_id 를 덮어 적지 않음(기록 그대로 넘김)",
     [(CONTEXT, swap("self._inner.record(replace(record, run_id=self._run_id))", "self._inner.record(record)"))],
     [(BUSINESS, [EXEC], {EXEC + "::test_llm_rows_carry_the_run_id_even_when_the_tags_have_no_run"}, set())]),
    ("P19", 2, "RunYield 를 Exception 의 자식으로",
     [(DEADLINE, swap("class RunYield(BaseException):", "class RunYield(Exception):"))],
     [(PURE, [CALC], {CALC + "::test_run_yield_is_not_an_exception"}, set()),
      (BUSINESS, [EXEC], {EXEC + "::test_past_the_deadline_the_attempt_yields_and_the_next_resumes_from_the_partial"},
       set())]),
    ("P20", 2, "claim_run 이 attempts 를 늘린 뒤 값으로 progress_attempt 와 견줌",
     [(CLAIMS, swap("progress_attempt != attempts:", "progress_attempt != attempts + 1:"))],
     [(BUSINESS, [EXEC], {EXEC + "::test_a_dead_attempt_with_progress_is_not_counted_when_taken_over"}, set())]),
    ("P21", 2, "finish_run 몸(꾸밈 없음 — 부르는 쪽 블록 안에서만 돎)에 put(...) 부름 하나",
     [(SVC_RUNS, swap('    _require_transaction("finish_run")\n',
                      '    _require_transaction("finish_run")\n    if outcome is None:\n        selectors.put("k")\n'))],
     [(PURE, [TXN], {TXN + "::test_worker_services_make_no_outside_call"},
       {TXN + "::test_no_outside_call_inside_a_block"})]),
    ("P23", 2, "단계 사건의 울타리(_fence)에서 attempts 조건을 지움",
     [(SVC_RUNS, swap('.filter(pk=run_id, status="processing", attempts=attempt).update(**values)',
                      '.filter(pk=run_id, status="processing").update(**values)'))],
     [(BUSINESS, [EXEC], {EXEC + "::test_a_late_attempt_writes_nothing_once_another_took_over"}, set())]),
    ("P24", 2, "finish_run 의 울타리에서 attempts 조건을 지움",
     [(SVC_RUNS, swap('    guard = RunRow.for_company(company_id).filter(pk=run_id, status="processing", attempts=attempt)',
                      '    guard = RunRow.for_company(company_id).filter(pk=run_id, status="processing")'))],
     [(BUSINESS, [EXEC], {EXEC + "::test_a_late_attempt_writes_nothing_once_another_took_over"}, set())]),
    ("P22", 2, "step_progress 가 done 을 견주지 않고 늘 progress_attempt = attempt",
     [(SVC_RUNS, swap("    progressed = done > (stored.done or 0)\n", "    progressed = True\n"))],
     [(BUSINESS, [EXEC], {EXEC + "::test_re_checkpointing_the_same_done_is_not_progress[same-done]"}, set())]),
    # ── 커밋 ③ 경로 몸 ──
    ("P11", 3, "create_run 의 record_event 를 지움(§4-14 의 반쪽은 section4 단계 14 를 심은 채 돌려 따로 잰다)",
     [(ACTIONS, cut(r"\n    record_event\(\n        at=now,.*?target_label=document\.file_name,\n    \)"))],
     [(BUSINESS, [RAPI], {RAPI + "::test_create_makes_a_queued_run_with_pending_steps_and_one_message"}, set())]),
    ("P11b", 3, "내려받기의 record_event 를 target_kind=\"file\" 로(AuditRefused — 조용히 0줄)",
     [(APIS, swap('        target_kind="run",\n        target_id=run_id,', '        target_kind="file",\n        target_id=run_id,'))],
     [(BUSINESS, [RAPI], {RAPI + "::test_download_gives_the_output_file_bytes_and_one_audit_line"}, set())]),
    ("P12", 3, "GET /runs/{runId} 의 find_run 에 남의 회사 id(행의 회사)를 넘김",
     [(APIS, swap("    run = selectors.find_run(company_id=company_id, run_id=run_id)\n",
                  "    from esgapi.runs.models import RunRow as _R  # noqa\n"
                  "    _owner = _R.unscoped.filter(pk=run_id).values_list(\"company_id\", flat=True).first()\n"
                  "    run = selectors.find_run(company_id=_owner or company_id, run_id=run_id)\n"))],
     [(SECURITY, [SRUNS], {SRUNS + "::test_another_companys_run_and_file_are_not_found[session]",
                           SRUNS + "::test_another_companys_run_and_file_are_not_found[bearer]"}, set())]),
    ("P13", 3, "내려받기가 단계 산출 파일(step 있음)도 냄",
     [(SEL_RUNS, swap("filter(run_id=run_id, step__isnull=True, name=name)", "filter(run_id=run_id, name=name)"))],
     [(BUSINESS, [RAPI], {RAPI + "::test_download_refuses_step_files_other_companies_and_unknown_names"}, set())]),
    ("P14", 3, "경로 runs_get 의 첫 문장 permitted(...) 를 지움",
     [(APIS, swap('    principal = permitted(request, "runs_get")\n', "    principal = request.auth  # type: ignore\n"))],
     [(PURE, [PERMS], {PERMS + "::test_each_route_checks_its_own_operation_id_first"}, set())]),
    ("P15", 3, "runs_create 응답 선언에서 404 를 다시 지움",
     [(APIS, swap("response={201: RunCreatedOut, 404: ErrorBody, 501: ErrorBody, **TOKEN_BODY_ERROR_RESPONSES},",
                  "response={201: RunCreatedOut, 501: ErrorBody, **TOKEN_BODY_ERROR_RESPONSES},"))],
     [(PURE, [CONTRACT], {CONTRACT + "::test_the_run_and_version_operations_are_the_contract_sheet",
                          CONTRACT + "::test_every_operation_declares_exactly_these_response_codes"}, set())]),
    ("P16", 3, "runs/tasks.py 의 태스크 이름을 runs.run 으로",
     [(TASKS, swap("app.task(name=RUN_TASK_NAME, bind=True)", 'app.task(name="runs.run", bind=True)'))],
     [(PURE, [SHAPE], {SHAPE + "::test_the_task_is_registered_by_its_name"}, set()),
      (INTEGRATION, [IRUN], {IRUN + "::test_the_worker_image_has_the_run_task"}, set())]),
]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT and (ONLY is None or p[0] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], set[str], str]:
    name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, "-vv", *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    passed = set(re.findall(r"^(\S+::\S+(?:\[[^\]]*\])?) PASSED", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, passed, last


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, checks in PLANTS:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
            planted += 1
            continue
        for layer, targets, expected, green in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            planted += 1
            code, failed, passed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed and green <= passed
            caught += 1 if hit else 0
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
            for node in sorted(green):
                print(f"    {'PASSED' if node in passed else '★ 초록 아님'} {node}  (초록이어야 함)")
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

# 통합 반쪽을 심은 채 지은 이미지를 지금 소스로 다시 짓고 워커를 되돌린다(다음 사람이 심은 이미지를 쓰지 않게).
if CONTAINERS and any(layer is INTEGRATION for p in PLANTS for layer, *_ in p[4]):
    rebuilt = subprocess.run(["bash", "-c", INTEGRATION_WRAP.replace('exec scripts/test-integration.sh "$@"\n', ""), "_"],
                             capture_output=True, text=True, check=False)
    print(f"되돌린 이미지·워커: EXIT={rebuilt.returncode}")
    zero_ok = zero_ok and rebuilt.returncode == 0

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
