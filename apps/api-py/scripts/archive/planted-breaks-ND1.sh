#!/usr/bin/env bash
# 밴드 ND1 의 심은 파손(발주서 band-handoffs/ND1-order.md §3, 개정 2 + MARC-TICK-236 노트의 9f 조건 (사)). 하나씩
# 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다.
# 파일을 지우는 심음은 지운 뒤 같은 바이트로 다시 쓴다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-ND1.sh [--boundary 1|2] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 —
# 경계 ① 22(P1~P11·P15~P25 — 9f (사)의 넷 중 셋 P23·P24·P25 포함), ② 26(+P12~P14 + 9f (사)의 P26).
# 마이그레이션을 고치는 심음(P1·P16·P19·P25)은 테스트 DB 를 새로 짓는 층(업무·보안 — --reuse-db 없음)에서만 뜻이 있다.
# 회사 경계 심음(P10·P26)은 예외 없이 터지지 않는 꼴이다 — 업무·보안 층의 잡음은 **단언**으로 빨개진 것만 센다. 빨간 노드의
# 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다.
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: ND1_OUT(기본: 워크트리 곁의 ND1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${ND1_OUT:-$(cd "$ROOT/.." && pwd)/ND1.out}"
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
BOUNDARY = 2
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2"):
        BOUNDARY, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


DELETE = "<지움>"  # 심는 함수가 이것을 돌려주면 파일을 지운다(되돌림은 원본 바이트를 다시 씀)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def delete(text: str) -> str | None:
    return DELETE


BIND = Path("esgapi/core/flows/binding.py")
MODELS = Path("esgapi/runs/models.py")
MIG = Path("esgapi/runs/migrations/0002_run_document_optional.py")
ACT = Path("esgapi/runs/service/actions/runs.py")
SCHEMA = Path("esgapi/runs/service/schemas/runs.py")
RUNSEL = Path("esgapi/runs/service/selectors/runs.py")
TASKS = Path("esgapi/runs/tasks.py")
TBIND = "esgapi/runs/tests/test_binding.py"
TAPI = "esgapi/runs/tests/service/apis/test_runs.py"
TVER = "esgapi/runs/tests/service/apis/test_runs_versions.py"
TEXEC = "esgapi/runs/tests/test_executor.py"
TMODELS = "esgapi/runs/tests/test_models.py"
TSEL = "esgapi/runs/tests/service/selectors/test_runs.py"
TCONTRACT = "esgapi/config/tests/test_api_contract.py"
TMIGCHK = "esgapi/config/tests/test_migrations.py"
SRUNS = "tests/security/test_runs.py"
SMIG = "tests/security/test_migrations.py"
OPSEL = Path("esgapi/runs/service/selectors/operator.py")
XLSX = Path("esgapi/user/service/utils/run_log_xlsx.py")
LOGSCHEMA = Path("esgapi/user/service/schemas/run_logs.py")
TLOGS = "esgapi/user/tests/service/apis/test_run_logs.py"
TXLSX = "esgapi/user/tests/service/utils/test_run_log_xlsx.py"
TOP = "esgapi/runs/tests/service/selectors/test_operator.py"
SLOGS = "tests/security/test_run_logs.py"
LOG_LINE = TLOGS + "::test_a_documentless_run_is_a_line_with_null_document_fields"
OP_READ = TOP + "::test_a_documentless_run_is_read_with_no_document_and_q_leaves_it_out"
MIG_ROUND = SMIG + "::test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip"
REFUSED = TAPI + "::test_documentless_refusals_write_nothing"
MADE = TAPI + "::test_a_documentless_flow_makes_a_run_without_a_document"
LIMIT = TAPI + "::test_the_options_limit_is_per_flow_and_the_app_is_the_only_lock_under_the_db_ceiling"
QUOTES = TAPI + "::test_quote_heavy_options_under_the_app_limit_fit_the_wrapped_db_ceiling"
LISTED = TAPI + "::test_a_documentless_run_lists_and_reads_with_null_document_fields"
LEFT = TSEL + "::test_run_page_keeps_a_documentless_run_with_no_name_through_a_left_join"
ORDER = TAPI + "::test_the_create_order_puts_the_document_before_the_flow"
BARE_DONE = TEXEC + "::test_a_documentless_run_goes_to_done_without_reading_a_document"
BARE_FACTS = TEXEC + "::test_a_documentless_facts_binding_gets_the_company_and_the_run_versions"
NULL_ROW = TEXEC + "::test_a_document_flow_run_without_a_document_fails_once"
STAMPS = TVER + "::test_a_documentless_facts_binding_stamps_the_companys_versions"
KEY_ORDER = TMODELS + "::test_run_options_come_back_in_the_written_key_order_and_a_null_document_is_a_run"


def both(name: str) -> set[str]:
    """보안 층의 VIA 두 갈래(session·bearer)."""
    return {f"{SRUNS}::{name}[session]", f"{SRUNS}::{name}[bearer]"}


S_F = both("test_a_documentless_run_stays_inside_its_company")
S_F2 = both("test_another_companys_document_id_on_a_documentless_flow_is_not_found")
S_C = both("test_another_companys_run_and_file_are_not_found")
S_G = {SRUNS + "::test_a_null_document_does_not_open_the_child_rows_to_another_company"}

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

DUP_CHECK = (
    "        if flow_id in self._bindings or flow_id in self._documentless:\n"
    '            raise FlowRegistryError(f"흐름 {flow_id} 의 끼움이 이미 있다")\n'
    "        if not 1"
)
EARLY_FLOW = (
    "    early = _flow(module, flow_id)\n"
    "    if early is None:\n"
    "        return UnknownFlow()\n"
    "    if BINDINGS.documentless(early.id) is None and isinstance(BINDINGS.get(early.id), NoBinding):\n"
    "        return FlowNotRunnable(early.id)\n"
    "    document = None\n"
)
IGNORED_DOCUMENT = (
    "    early = _flow(module, flow_id)\n"
    "    if early is not None and BINDINGS.documentless(early.id) is not None:\n"
    "        document_id = None\n"
    "    document = None\n"
)
CEILING_ADD = "        migrations.RunSQL(sql=options_check(OPTIONS_CEILING_OCTETS), reverse_sql=DROP_CHECK),\n    ]\n"
DROP_STEP_FK = 'migrations.RunSQL(\'ALTER TABLE "run_steps" DROP CONSTRAINT "run_steps_run_id_same_company_fk";\'),'

# (번호, 경계, 설명, [(파일, 심는 함수)], [(경계, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "0002 를 지우고 모델만 null=True",
     [(MIG, delete)],
     [(1, BUSINESS, [TMIGCHK], {TMIGCHK + "::test_models_and_migrations_agree"}),
      (1, SECURITY, [SMIG], {MIG_ROUND})]),
    ("P2", 1, "register_documentless 가 문서 갈래(_bindings)를 안 봄",
     [(BIND, swap(DUP_CHECK, DUP_CHECK.replace("flow_id in self._bindings or ", "")))],
     [(1, PURE, [TBIND], {TBIND + "::test_a_flow_is_bound_once_across_both_branches_in_either_order"})]),
    ("P3", 1, "만들기의 DocumentRequired 갈래 지움",
     [(ACT, swap("        if document is None:\n            return DocumentRequired()\n", ""))],
     [(1, BUSINESS, [TAPI], {REFUSED + "[document_flow_without_a_document-expected3]",
                             REFUSED + "[document_flow_with_null-expected4]",
                             REFUSED + "[default_flow_without_a_document-expected5]"})]),
    ("P4", 1, "DocumentNotAccepted 지움",
     [(ACT, swap("        if document is not None:\n            return DocumentNotAccepted()\n", ""))],
     [(1, BUSINESS, [TAPI], {REFUSED + "[bare_with_my_document-expected0]"}),
      (1, SECURITY, [SRUNS], S_F2)]),
    ("P5", 1, "documentId 가 있어도 흐름·끼움을 문서보다 먼저 봄",
     [(ACT, swap("    document = None\n", EARLY_FLOW))],
     [(1, BUSINESS, [TAPI], {ORDER})]),
    ("P6", 1, "run_page 이름을 str(…) 그대로(None → 「None」)",
     [(RUNSEL, swap("None if name is None else str(name)", "str(name)"))],
     [(1, BUSINESS, [TAPI], {LISTED}),
      (1, BUSINESS, [TSEL], {LEFT}),
      (1, SECURITY, [SRUNS], S_F)]),
    ("P7", 1, "run_page 에 .filter(document__isnull=False)",
     [(RUNSEL, swap('    rows = rows.order_by("-created_at", "-id")\n    lines',
                    '    rows = rows.filter(document__isnull=False).order_by("-created_at", "-id")\n    lines'))],
     [(1, BUSINESS, [TAPI], {LISTED}),
      (1, BUSINESS, [TSEL], {LEFT}),
      (1, SECURITY, [SRUNS], S_F)]),
    ("P8", 1, "실행기의 문서 없는 갈래도 문서를 읽음(_document)",
     [(TASKS, swap("            if bare is None:\n                document = (", "            if True:\n                document = ("))],
     [(1, BUSINESS, [TEXEC], {BARE_DONE, BARE_FACTS})]),
    ("P9", 1, "NULL 문서 가드가 RunDeferred() 를 돌려줌",
     [(TASKS, swap('                    _failed("document_missing")\n                    if claimed.run.document_id is None',
                   '                    RunDeferred()\n                    if claimed.run.document_id is None'))],
     [(1, BUSINESS, [TEXEC], {NULL_ROW})]),
    ("P10", 1, "selectors/runs.py:_runs 를 RunRow.unscoped 로(회사 거름 없음 — 예외 없음)",
     [(RUNSEL, swap("    return RunRow.for_company(company_id)\n", "    return RunRow.unscoped.all()\n"))],
     [(1, SECURITY, [SRUNS], S_F | S_C)]),
    ("P11", 1, "RunIn.documentId 를 필수로 되돌림",
     [(SCHEMA, swap("    documentId: int | None = Field(\n        default=None,\n", "    documentId: int = Field(\n"))],
     [(1, PURE, [TCONTRACT], {TCONTRACT + "::test_the_run_and_version_operations_are_the_contract_sheet"}),
      (1, BUSINESS, [TAPI], {MADE + "[absent]"})]),
    ("P15", 1, "만들기가 흐름의 상한 대신 16KiB",
     [(ACT, swap("    limit = BINDINGS.options_limit(flow.id)\n", "    limit = 16 * 1024\n"))],
     [(1, BUSINESS, [TAPI], {LIMIT, QUOTES})]),
    ("P16", 1, "0002 가 CHECK 를 안 올림(16KiB 로 다시 닮)",
     [(MIG, swap("options_check(OPTIONS_CEILING_OCTETS), reverse_sql", "options_check(OPTIONS_MAX_OCTETS_0001), reverse_sql"))],
     [(1, BUSINESS, [TAPI], {LIMIT, QUOTES})]),
    ("P17", 1, "등록부가 MAX 넘는 상한을 받음",
     [(BIND, swap("if not 1 <= max_options_bytes <= DOCUMENTLESS_OPTIONS_MAX_OCTETS:", "if not 1 <= max_options_bytes:"))],
     [(1, PURE, [TBIND], {TBIND + "::test_an_options_limit_outside_one_to_the_max_is_refused[262145]"})]),
    ("P18", 1, "options 를 맨 JSONField 로",
     [(MODELS, swap('= OrderedJSONField(default=dict)  # pyright', '= models.JSONField(default=dict)  # pyright'))],
     [(1, BUSINESS, [TMODELS], {KEY_ORDER}),
      (1, BUSINESS, [TAPI], {QUOTES})]),
    ("P19", 1, "CEILING = 256KiB(이스케이프 몫 없음 — 0002 와 모델 둘 다)",
     [(MIG, swap("OPTIONS_CEILING_OCTETS = 2 * 256 * 1024 + 64", "OPTIONS_CEILING_OCTETS = 256 * 1024 + 64")),
      (MODELS, swap("RUN_OPTIONS_CEILING_OCTETS = 2 * DOCUMENTLESS_OPTIONS_MAX_OCTETS + 64",
                    "RUN_OPTIONS_CEILING_OCTETS = DOCUMENTLESS_OPTIONS_MAX_OCTETS + 64"))],
     [(1, BUSINESS, [TAPI], {QUOTES})]),
    ("P20", 1, "실행기가 문서 없는 둘째 꼴을 RunFactsBinding(문서 꼴) 갈래로",
     [(TASKS, swap("        binding = BINDINGS.get(claimed.run.flow_id)\n",
                   "        binding = BINDINGS.get(claimed.run.flow_id)\n"
                   "        binding = bare if isinstance(bare, flow_ports.RunFactsBinding) else binding\n")),
      (TASKS, swap("                if bare is not None:  #", "                if bare is not None and binding is not bare:  #"))],
     [(1, BUSINESS, [TEXEC], {BARE_FACTS})]),
    ("P21", 1, "만들기가 문서 없는 둘째 꼴에 versions() 를 부름",
     [(ACT, swap("        if isinstance(binding, flow_ports.DocumentlessFactsBinding):\n"
                 "            return binding.versions_with(options, company_id=company_id)\n", ""))],
     [(1, BUSINESS, [TVER], {STAMPS})]),
    ("P22", 1, "실행기가 문서 없는 끼움의 inputs 를 company_id 빼고 부름",
     [(TASKS, swap("else bare.inputs(claimed.run.options, company_id=company)", "else bare.inputs(claimed.run.options)"))],
     [(1, BUSINESS, [TEXEC], {BARE_DONE})]),
    ("P23", 1, "9f (사): _options_too_large 검사 지움(문서 흐름 16KiB 의 앱 잠금 없음)",
     [(ACT, swap("    if _options_too_large(options, limit):\n        return OptionsRejected(options_too_large(limit))\n", ""))],
     [(1, BUSINESS, [TAPI], {LIMIT, TAPI + "::test_create_refusals_write_nothing[options_too_large-expected8]"})]),
    ("P24", 1, "9f (사): 문서 없는 흐름이 documentId 를 문서 검사 없이 버리고 NULL 로 201",
     [(ACT, swap("    document = None\n", IGNORED_DOCUMENT))],
     [(1, SECURITY, [SRUNS], S_F2),
      (1, BUSINESS, [TAPI], {REFUSED + "[bare_with_my_document-expected0]", REFUSED + "[bare_with_their_document-expected1]"})]),
    ("P25", 1, "9f (사): 시험 DB 에서 run_steps 같은 회사 FK DROP(0002 끝에 RunSQL)",
     [(MIG, swap(CEILING_ADD, CEILING_ADD.replace("    ]\n", "        " + DROP_STEP_FK + "\n    ]\n")))],
     [(1, SECURITY, [SRUNS], S_G)]),
    # ── 경계 ② 운영 관리자 기록 ──
    ("P12", 2, "운영 관리자 읽기에 .filter(document__isnull=False)",
     [(OPSEL, swap("    return RunRow.for_company(company_id)\n", "    return RunRow.for_company(company_id).filter(document__isnull=False)\n"))],
     [(2, BUSINESS, [TLOGS], {LOG_LINE}),
      (2, BUSINESS, [TOP], {OP_READ})]),
    ("P13", 2, "엑셀이 문서 이름 None 을 「–」로",
     [(XLSX, swap("        line.document_name,\n", "        EMPTY if line.document_name is None else line.document_name,\n"))],
     [(2, PURE, [TXLSX], {TXLSX + "::test_a_documentless_run_has_a_blank_document_cell"}),
      (2, BUSINESS, [TLOGS], {LOG_LINE})]),
    ("P14", 2, "RunLogOut.documentName: str",
     [(LOGSCHEMA, swap("    documentName: str | None = Field(", "    documentName: str = Field("))],
     [(2, BUSINESS, [TLOGS], {LOG_LINE})]),
    ("P26", 2, "9f (사): 운영 관리자 목록·엑셀의 회사 거름 지움(RunRow.unscoped — 예외 없음)",
     [(OPSEL, swap("    return RunRow.for_company(company_id)\n", "    return RunRow.unscoped.all()\n"))],
     [(2, SECURITY, [SLOGS], {SLOGS + "::test_a_documentless_run_of_a_is_not_in_bs_list_or_workbook"})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY]) for n, c, w, e, checks in PLANTS]
BOUNDARY_GUARDED = {"P10", "P26"}  # 회사 경계 심음 — 예외로 빨개지면 무효
EXCEPTION = re.compile(r"UnscopedQueryError|Internal Server Error|Traceback")


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str, str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last, text


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for _commit, layer, targets, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, last, _ = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
    """잡았으면 True, 못 잡았으면 False, 컨테이너가 없어 다 돌리지 못했으면 None."""
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            if new == DELETE:
                f.unlink()
                continue
            f.write_text(new, encoding="utf-8")
        hit_all, skipped = True, False
        for _commit, layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last, text = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            raised = number in BOUNDARY_GUARDED and layer[0] != "순수" and bool(EXCEPTION.search(text))
            if raised:
                print(f"{label} 예외로 빨강(무효 — 단언으로 빨개져야 한다)")
                hit = False
            hit_all = hit_all and hit
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, _commit, what, edits, checks in PLANTS:
    planted += 1
    result = plant_and_check(number, what, edits, checks)
    caught += 1 if result is True else 0
    print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
