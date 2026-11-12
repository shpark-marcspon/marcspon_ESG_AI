#!/usr/bin/env bash
# 밴드 AD4S 의 심은 파손(발주서 band-handoffs/AD4S-order.md §3-1, 개정 3). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로
# 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AD4S.sh [--boundary 1|2|3] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 —
# 경계 ① 10(P1~P8·P7b·P7c), ② 24(+P9~P17·P12b·P12c·P15b·HB·P9b), ③ 28(+P18~P21). HB = 검증 ① 권고(감독 f8 —
# in_review·confirmed 갈래의 검토 가능 조건). P9b = 9f 허락 조건 (사)(export 가 고른 회사 대신 전 회사를 읽음 — 검증 ② B1).
# 회사 경계 심음(P7)은 예외 없이 터지지 않는 꼴이다 — 업무·보안 층의 잡음은 **단언**으로 빨개진 것만 센다. 빨간 노드의
# 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다.
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: AD4S_OUT(기본: 워크트리 곁의 AD4S.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AD4S_OUT:-$(cd "$ROOT/.." && pwd)/AD4S.out}"
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
BOUNDARY = 3
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2", "3"):
        BOUNDARY, args = int(args[1]), args[2:]
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


OPSEL = Path("esgapi/runs/service/selectors/operator.py")
GWX = Path("esgapi/greenwash/service/selectors/run_extras.py")
GWAPPS = Path("esgapi/greenwash/apps.py")
ROUTE = Path("esgapi/user/service/apis/run_logs.py")
XLSX = Path("esgapi/user/service/utils/run_log_xlsx.py")
PERMS = Path("esgapi/core/permissions.py")
CALC = Path("esgapi/core/calc/audit.py")
AUDSEL = Path("esgapi/core/service/selectors/audit.py")
GWSET = Path("esgapi/greenwash/service/actions/ai_settings.py")
TCALC = "esgapi/core/tests/calc/test_audit.py"
TSVC = "esgapi/core/tests/service/services/test_audit.py"
TAUDIT = "esgapi/user/tests/service/apis/test_audit.py"
TGWSET = "esgapi/greenwash/tests/service/apis/test_ai_settings.py"
TXLSX = "esgapi/user/tests/service/utils/test_run_log_xlsx.py"
TOP = "esgapi/runs/tests/service/selectors/test_operator.py"
TPERM = "esgapi/core/tests/test_permissions.py"
TAPI = "esgapi/user/tests/service/apis/test_run_logs.py"
TGW = "esgapi/greenwash/tests/service/selectors/test_run_extras.py"
TEXTRAS = "esgapi/runs/tests/test_extras.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
SRUN = "tests/security/test_run_logs.py"
SOPCO = "tests/security/test_operator_company.py"
UNSCOPED = TSTATIC + "::test_product_code_does_not_use_unscoped"
SHOWN = TAPI + "::test_the_review_is_shown_only_where_the_greenwash_screen_shows_it"
FILTER = TAPI + "::test_the_review_filter_takes_the_same_rule"
CROSS_F = SRUN + "::test_a_review_row_of_a_does_not_reach_the_runs_of_b"
SAME_SET = TAPI + "::test_the_export_holds_the_same_runs_as_the_list"
CAP = TAPI + "::test_the_export_cap_is_counted_before_reading"
HEADERS = TAPI + "::test_the_export_headers_and_its_audit_line"
LINE = TAPI + "::test_an_exported_line_is_the_lines_values"
EMPTY_CELLS = TXLSX + "::test_empty_numbers_are_an_en_dash_and_empty_words_are_blank"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

REVIEW_PICK = '            review = states.get(row["id"], "pending") if row["id"] in reviewable else None\n'
PENDING = '            one = reviewable & ~Q(id__in=source.run_ids_in(company_id, {"in_review", "confirmed"}))\n'
FILL = '            review=extras.get(row["id"], (None, None))[0],\n'
FILTER_IF = "    if review is not None:\n        condition = _review_q(company_id, review)\n"
PAGE_RETURN = "    return OperatorRunPage(count=count, runs=_operator_runs(company_id, page))\n"
REGISTER = '        EXTRAS.register("greenwash", RunReviewSource())'
RUN_IDS_IN = "        return GreenwashReviewRow.for_company(company_id).filter(state__in=list(states))"
DRY_RUN = (
    '    return Q(status="done", results__schema_version=RESULT_SHAPE) & (\n'
    "        Q(results__body__dryRun=None) | Q(results__body__dryRun__isnull=True)\n"
    "    )\n"
)
DEFAULT_ID = "        if setting_id is None:\n            return (None, name)\n"
EXPORT_ROWS = (
    "    rows = _filtered(company_id, module=module, status=status, date_from=date_from, date_to=date_to, q=q,"
    " review=review)\n    count = rows.count()\n    if count > cap:\n"
)
EXPORT_CHECK = (
    '    if not is_allowed("user_run_log_export", kind=actor_kind):\n        return RunLogForbidden()\n'
    "    rows = _filtered("
)
OVER_CAP = "    if count > cap:\n        return ExportTooLarge(count)\n"
TOO_LARGE = "    if isinstance(found, operator_selectors.ExportTooLarge):\n"
EARLY_AUDIT = (
    "    record_event(at=now(), company_id=company_id, actor_kind=principal.kind, actor_user_id=int(principal.user_id),"
    ' action="download", event="run_logs_exported", result="success", target_kind="run_log_export")\n'
)
NARROW = "            one = reviewable & Q(id__in=source.run_ids_in(company_id, {review}))\n"

# (번호, 경계, 설명, [(파일, 심는 함수)], [(경계, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "값 채우기에서 검토 가능 검사를 지움(원천 모듈 줄이면 늘 pending)",
     [(OPSEL, swap(REVIEW_PICK, '            review = states.get(row["id"], "pending")\n'))],
     [(1, BUSINESS, [TAPI], {SHOWN})]),
    ("P2", 1, "pending 갈래에서 검토 가능 부분 쿼리를 지움",
     [(OPSEL, swap(PENDING, PENDING.replace("one = reviewable & ", "one = Q(module=module) & ")))],
     [(1, BUSINESS, [TAPI], {FILTER})]),
    ("P3", 1, "pending 이 빼는 상태를 {confirmed} 만",
     [(OPSEL, swap(PENDING, PENDING.replace('{"in_review", "confirmed"}', '{"confirmed"}')))],
     [(1, BUSINESS, [TAPI], {FILTER})]),
    ("P4", 1, "원천이 없는 모듈의 줄도 pending 으로 채움",
     [(OPSEL, swap(FILL, '            review=extras.get(row["id"], ("pending", None))[0],\n'))],
     [(1, BUSINESS, [TAPI], {SHOWN})]),
    ("P5", 1, "review 거르기를 쪽 읽은 뒤 파이썬에서",
     [(OPSEL, swap(FILTER_IF, FILTER_IF.replace("if review is not None:", "if False and review is not None:"))),
      (OPSEL, swap(PAGE_RETURN, "    runs = _operator_runs(company_id, page)\n"
                                "    runs = tuple(run for run in runs if review is None or run.review == review)\n"
                                "    return OperatorRunPage(count=count, runs=runs)\n"))],
     [(1, BUSINESS, [TAPI], {TAPI + "::test_the_review_filter_counts_before_paging"})]),
    ("P6", 1, "그린워싱 apps.py 의 EXTRAS.register 줄을 지움",
     [(GWAPPS, swap(REGISTER, "        pass  # 심은 파손 P6"))],
     [(1, BUSINESS, [TAPI], {SHOWN}),
      (1, PURE, [TEXTRAS], {TEXTRAS + "::test_the_process_registry_has_the_greenwash_source"})]),
    ("P7", 1, "run_ids_in 을 GreenwashReviewRow.unscoped 로(예외 없음)",
     [(GWX, swap(RUN_IDS_IN, "        return GreenwashReviewRow.unscoped.filter(state__in=list(states))"))],
     [(1, PURE, [TSTATIC], {UNSCOPED}),
      (1, BUSINESS, [TGW], {TGW + "::test_another_companys_review_row_is_not_seen"}),
      (1, SECURITY, [SRUN], {CROSS_F})]),
    ("P7b", 1, "reviewable_q 에서 dryRun 조건을 지움",
     [(GWX, swap(DRY_RUN, '    return Q(status="done", results__schema_version=RESULT_SHAPE)\n'))],
     [(1, BUSINESS, [TGW], {TGW + "::test_the_two_predicates_agree"}),
      (1, BUSINESS, [TAPI], {SHOWN})]),
    ("P7c", 1, "dryRun null 갈래를 __isnull=True 로만",
     [(GWX, swap("        Q(results__body__dryRun=None) | Q(results__body__dryRun__isnull=True)\n",
                 "        Q(results__body__dryRun__isnull=True)\n"))],
     [(1, BUSINESS, [TAPI], {SHOWN}),
      (1, SECURITY, [SRUN], {CROSS_F})]),
    ("P8", 1, "ai_setting 이 기본 판(aiSettingId None)을 None 으로",
     [(GWX, swap(DEFAULT_ID, "        if setting_id is None:\n            return None\n"))],
     [(1, PURE, [TGW], {TGW + "::test_the_ai_setting_is_read_from_the_versions[default]"}),
      (1, BUSINESS, [TAPI], {TAPI + "::test_the_ai_setting_comes_from_the_versions"})]),
    # ── 경계 ② 내보내기 ──
    ("HB", 2, "in_review·confirmed 갈래에서 검토 가능 조건을 지움(검증 ① 권고)",
     [(OPSEL, swap(NARROW, NARROW.replace("one = reviewable & ", "one = Q(module=module) & ")))],
     [(2, BUSINESS, [TAPI], {FILTER})]),
    ("P9", 2, "export 가 q 를 넘기지 않음",
     [(ROUTE, swap("        q=q,\n        review=review,\n        cap=RUN_LOG_EXPORT_MAX,\n",
                   "        q=None,\n        review=review,\n        cap=RUN_LOG_EXPORT_MAX,\n"))],
     [(2, BUSINESS, [TAPI], {SAME_SET})]),
    ("P9b", 2, "export 가 고른 회사 대신 전 회사의 실행을 읽음(RunRow.unscoped — 예외 없음)",
     [(OPSEL, swap(EXPORT_ROWS, EXPORT_ROWS.replace(
         "_filtered(company_id, module=module, status=status, date_from=date_from, date_to=date_to, q=q,"
         " review=review)", 'RunRow.unscoped.order_by("-created_at", "-id")')))],
     [(2, SECURITY, [SRUN], {SRUN + "::test_the_export_for_b_holds_no_name_of_a"}),
      (2, BUSINESS, [TAPI], {SAME_SET})]),
    ("P10", 2, "상한 비교 > 를 >= 로",
     [(OPSEL, swap(OVER_CAP, OVER_CAP.replace("count > cap", "count >= cap")))],
     [(2, BUSINESS, [TAPI], {CAP}),
      (2, BUSINESS, [TOP], {TOP + "::test_the_export_takes_every_filtered_run_and_stops_over_the_cap"})]),
    ("P11", 2, "file_name 이 시각을 UTC 로",
     [(XLSX, swap("{at.astimezone(KST):", "{at.astimezone(UTC):")),
      (XLSX, swap("from datetime import datetime\n", "from datetime import UTC, datetime\n"))],
     [(2, PURE, [TXLSX], {TXLSX + "::test_the_file_name_is_the_kst_minute"}),
      (2, BUSINESS, [TAPI], {HEADERS})]),
    ("P12", 2, "수식 칸 되돌림(data_type f → s)을 지움",
     [(XLSX, swap('            if cell.data_type == "f":', '            if False:'))],
     [(2, PURE, [TXLSX], {TXLSX + "::test_formula_shaped_names_stay_text"})]),
    ("P12b", 2, "queued 줄의 토큰·비용을 값 그대로(「–」 아님)",
     [(XLSX, swap("        EMPTY if queued else line.tokens,\n        EMPTY if queued else line.cost_usd,\n",
                  "        line.tokens,\n        line.cost_usd,\n"))],
     [(2, PURE, [TXLSX], {EMPTY_CELLS}),
      (2, BUSINESS, [TAPI], {LINE})]),
    ("P12c", 2, "처리 시간 null 을 빈칸으로",
     [(XLSX, swap("        EMPTY if queued or line.duration_sec is None else line.duration_sec,\n",
                  "        EMPTY if queued else line.duration_sec,\n"))],
     [(2, PURE, [TXLSX], {EMPTY_CELLS})]),
    ("P13", 2, "operator_run_export 첫 줄 권한 검사를 지움",
     [(OPSEL, swap(EXPORT_CHECK, "    rows = _filtered("))],
     [(2, PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"}),
      (2, BUSINESS, [TOP], {TOP + "::test_the_export_is_forbidden_to_a_customer_kind_before_anything_is_read"})]),
    ("P14", 2, "권한 표 user_run_log_export 를 CUSTOMER 로",
     [(PERMS, swap('    "user_run_log_export": OPERATOR,\n', '    "user_run_log_export": CUSTOMER,\n'))],
     [(2, PURE, [TPERM], {TPERM + "::test_the_table_is_these_needs"}),
      (2, SECURITY, [SRUN, SOPCO], {SRUN + "::test_a_customer_bearer_gets_no_export",
                                    SOPCO + "::test_the_operator_only_cells_stay_closed_to_a_customer"})]),
    ("P15", 2, "Content-Disposition 을 filename=\"…\" 날 글로",
     [(ROUTE, swap('    response["Content-Disposition"] = disposition\n',
                   """    response["Content-Disposition"] = f'attachment; filename="{name}"'\n"""))],
     [(2, BUSINESS, [TAPI], {HEADERS})]),
    ("P15b", 2, "Cache-Control 줄을 지움",
     [(ROUTE, swap('    response["Cache-Control"] = "no-store"  # 회사 자료(감독 처분)\n', ""))],
     [(2, BUSINESS, [TAPI], {HEADERS}),
      (2, SECURITY, [SRUN], {SRUN + "::test_the_export_for_b_holds_no_name_of_a"})]),
    ("P16", 2, "상한을 넘어도 행을 읽은 뒤 버림",
     [(OPSEL, swap(OVER_CAP, "    if count > cap:\n        _operator_runs(company_id, rows.values(*PAGE_FIELDS))\n"
                             "        return ExportTooLarge(count)\n"))],
     [(2, BUSINESS, [TAPI], {CAP}),
      (2, BUSINESS, [TOP], {TOP + "::test_the_export_takes_every_filtered_run_and_stops_over_the_cap"})]),
    ("P17", 2, "409 앞에 감사 줄",
     [(ROUTE, swap(TOO_LARGE, EARLY_AUDIT + TOO_LARGE))],
     [(2, BUSINESS, [TAPI], {CAP})]),
    # ── 경계 ③ 감사 줄 module ──
    ("P18", 3, "audit_detail 이 module 을 버림",
     [(CALC, swap('    if module is not None:\n        detail["module"] = module\n', ""))],
     [(3, PURE, [TCALC], {TCALC + "::test_the_module_rides_in_the_detail_and_counts_in_its_size"}),
      (3, BUSINESS, [TAUDIT], {TAUDIT + "::test_a_module_line_carries_its_module"}),
      (3, BUSINESS, [TGWSET], {TGWSET + "::test_the_save_and_apply_audit_lines"})]),
    ("P19", 3, "check_event 의 module 꼴 검사를 지움",
     [(CALC, swap('        ("module", module is None or (len(module) <= MODULE_MAX and MODULE_ID.fullmatch(module) is not None)),\n',
                  ""))],
     [(3, PURE, [TCALC], {TCALC + "::test_a_module_outside_the_shape_is_refused[Bad]"}),
      (3, BUSINESS, [TSVC], {TSVC + "::test_a_module_line_keeps_its_module_in_the_detail"})]),
    ("P20", 3, "event_of 가 module 을 늘 None",
     [(AUDSEL, swap("        module=module if isinstance(module, str) else None,\n", "        module=None,\n"))],
     [(3, BUSINESS, [TAUDIT], {TAUDIT + "::test_a_module_line_carries_its_module"})]),
    ("P21", 3, "그린워싱 apply_setting 의 module= 를 지움",
     [(GWSET, swap('            changed_fields=("applied",),\n            module=MODULE,\n',
                   '            changed_fields=("applied",),\n'))],
     [(3, BUSINESS, [TGWSET], {TGWSET + "::test_the_save_and_apply_audit_lines"})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY]) for n, c, w, e, checks in PLANTS]
BOUNDARY_GUARDED = {"P7", "P9b"}  # 회사 경계 심음 — 예외로 빨개지면 무효
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
