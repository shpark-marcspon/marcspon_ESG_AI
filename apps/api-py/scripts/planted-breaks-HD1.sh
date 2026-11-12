#!/usr/bin/env bash
# 밴드 HD1 의 심은 파손(발주서 band-handoffs/HD1-order.md §3-1 P1~P24 — archive/planted-breaks-RX1b.sh 꼴). 하나씩 심고 겨눈
# 시험만 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — 끝에 sha·status 대조). SIGINT·SIGTERM
# 이 와도 되쓴다.
# 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-HD1.sh [--commit 1|2|3] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 0 아닌 종료이고 빨개져야 할
# 노드가 전부 FAILED 로 찍힘. 「BASE 대조」가 있는 P 는 겨눈 시험 파일을 BASE(HD1_BASE) 의 바이트로 바꿔 같은 심음에서
# 초록인지도 본다(구멍의 재현 — 초록이어야 맞음). 분모: ① 7 · ② 19 · ③ 24(누적, --commit). X 로 시작하는 것은 러너가
# 경계마다 더한 하나(분모 밖 — EXTRA=).
# 끝 줄 PLANTED=<잡음>/<심음>, 앞 줄 P0=·FINGERPRINT=·BASE_CONTROL=·EXTRA=. 산출물: HD1_OUT(기본 워크트리 곁의
# HD1.out)/planted/. 공급사를 부르지 않는다(키를 지운 환경). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${HD1_OUT:-$(cd "$ROOT/.." && pwd)/HD1.out}"
BASE="${HD1_BASE:-aff154be}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  -u LLM_RUN_MODE uv run --frozen python - "$OUT/planted" "$BASE" "$@" <<'PY'
import hashlib
import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
BASE = sys.argv[2]
args = sys.argv[3:]
CONTAINERS = False
ONLY = None
COMMIT = 3
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    elif args[0] == "--commit" and len(args) > 1:
        COMMIT, args = int(args[1]), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def _term(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _term)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def append(extra: str) -> Callable[[str], str | None]:
    return lambda text: text + extra


def base_bytes(path: Path) -> bytes:
    rel = f"apps/api-py/{path.as_posix()}"
    return subprocess.run(["git", "show", f"{BASE}:{rel}"], capture_output=True, check=True).stdout


E = Path("esgapi")
RUNS_SEL = E / "runs/service/selectors/runs.py"
SCOPE = E / "core/tests/test_selector_scope.py"
LLM1 = E / "inventory/engines/scope3/llm_first_1/calc.py"
SHEETS = E / "inventory/tools/scope3_sheets/grid.py"
COLAB = E / "inventory/engines/scope3/colab_157/units.py"
FLOWS = E / "inventory/flows/registration.py"
REF_T = E / "reference/tests/test_calc_is_pure.py"

T_SCOPE = "esgapi/core/tests/test_selector_scope.py"
T_LLM1 = "esgapi/inventory/tests/test_scope3_is_pure.py"
T_SHEETS = "esgapi/inventory/tests/test_s3sheets_is_pure.py"
T_COLAB = "esgapi/inventory/tests/engines/scope3/colab_157/test_purity.py"
T_FLOWS = "esgapi/inventory/tests/test_flows.py"
T_REF = "esgapi/reference/tests/test_calc_is_pure.py"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)


def planted_fn(line: str) -> str:
    """AST 만 보는 시험을 위한 심음 — 함수 몸 안이라 import 해도 돌지 않는다."""
    return f"\n\ndef _hd1_planted() -> None:  # 심은 파손\n    {line}\n"


# (번호, 경계, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)], BASE 대조 시험 파일들)
PLANTS = [
    ("P1", 1, "runs selector 에 RunRow.unscoped.filter 한 줄(310)",
     [(RUNS_SEL, append(planted_fn("RunRow.unscoped.filter(pk=1)")))],
     [(PURE, [T_SCOPE], {T_SCOPE + "::test_selectors_scope_every_read[runs/service/selectors/runs.py]"})],
     [SCOPE]),
    ("P2", 1, "selector_unscoped_problems 의 unscoped 검사 지움",
     [(SCOPE, swap('        if isinstance(node, ast.Attribute) and node.attr == "unscoped"\n',
                   "        if False\n"))],
     [(PURE, [T_SCOPE], {T_SCOPE + "::test_the_unscoped_checker_catches_what_it_should",
                         T_SCOPE + "::test_the_unscoped_allow_list_is_by_path"})],
     []),
    ("P3", 1, "llm_first_1 에 상대 금지 import(from ....service import services)",
     [(LLM1, append(planted_fn("from ....service import services  # noqa: F401")))],
     [(PURE, [T_LLM1], {T_LLM1 + "::test_no_module_imports_files_clocks_randomness_network_django_or_reference"})],
     [E / "inventory/tests/test_scope3_is_pure.py"]),
    ("P4", 1, "scope3_sheets 에 상대 금지 import(from .. import xlsx_reader)",
     [(SHEETS, append(planted_fn("from .. import xlsx_reader  # noqa: F401")))],
     [(PURE, [T_SHEETS],
       {T_SHEETS + "::test_no_module_in_the_folder_imports_files_zip_xml_network_django_or_the_reader"})],
     [E / "inventory/tests/test_s3sheets_is_pure.py"]),
    ("P5", 1, "colab_157 에 상대 금지 import(from ..llm_first_1 import calc)",
     [(COLAB, append(planted_fn("from ..llm_first_1 import calc  # noqa: F401")))],
     [(PURE, [T_COLAB], {T_COLAB + "::test_no_module_imports_files_clocks_randomness_network_django_or_the_other_version"})],
     [E / "inventory/tests/engines/scope3/colab_157/test_purity.py"]),
    ("P6", 1, "flows 에 상대 금지 import(from ..service import services)",
     [(FLOWS, append(planted_fn("from ..service import services  # noqa: F401")))],
     [(PURE, [T_FLOWS], {T_FLOWS + "::test_flows_call_no_service"})],
     [E / "inventory/tests/test_flows.py"]),
    ("P7", 1, "reference resolve 가 level 을 버림",
     [(REF_T, swap("    if node.level == 0:\n        return node.module or \"\"\n",
                   "    if True:\n        return node.module or \"\"\n"))],
     [(PURE, [T_REF], {T_REF + "::test_relative_imports_are_resolved"})],
     []),
    ("X1", 1, "flows 에 `from .. import service`(이름이 꾸러미인 상대 꼴 — 러너 더함)",
     [(FLOWS, append(planted_fn("from .. import service  # noqa: F401")))],
     [(PURE, [T_FLOWS], {T_FLOWS + "::test_flows_call_no_service"})],
     [E / "inventory/tests/test_flows.py"]),
]

# ── ② runbundle(405 R1~R7·S2) ──
CALC_BUNDLE = E / "runbundle/calc/bundle.py"
GATE = E / "runbundle/calc/gate.py"
IMPORT = E / "runbundle/service/actions/import_.py"
EXPORT = E / "runbundle/service/actions/export.py"
TB = "esgapi/runbundle/tests/calc/test_bundle_hd1.py"
TG = "esgapi/runbundle/tests/calc/test_gate_hd1.py"
TI = "esgapi/runbundle/tests/service/actions/test_import_hd1.py"
TE = "esgapi/runbundle/tests/service/actions/test_export_hd1.py"
TO = "esgapi/runbundle/tests/service/actions/test_export.py"
CAP = "                if total > DEFAULT_MAX_BYTES:\n"
CAP_JSON = "            if total + len(text) > DEFAULT_MAX_BYTES:\n"
PLANTS += [
    ("P8", 2, "loads 의 ValueError·RecursionError 잡기 지움",
     [(CALC_BUNDLE, swap('    except ValueError:\n        raise Refused("bundle.json 에 자릿수 상한을 넘는 정수가 있다") from None\n'
                         '    except RecursionError:\n        raise Refused("bundle.json 의 중첩이 너무 깊다") from None\n', ""))],
     [(PURE, [TB], {TB + "::test_an_integer_past_the_digit_limit_is_refused",
                    TB + "::test_nesting_past_the_recursion_limit_is_refused"}),
      (BUSINESS, [TI], {TI + "::test_an_integer_past_the_digit_limit_is_refused",
                        TI + "::test_nesting_past_the_recursion_limit_is_refused"})],
     []),
    ("P9", 2, "꼭 실을 칸 검사 지움(check_carried 의 칸 고리)",
     [(GATE, swap('        if not REQUIRED_COLUMNS[table] <= set(bundle.tables[table]):\n', "        if False:\n"))],
     [(PURE, [TG], {TG + "::test_a_missing_required_column_is_refused[run_runs-launch_key]"}),
      (BUSINESS, [TI], {TI + "::test_a_missing_required_column_is_refused_before_any_read[run_runs-launch_key-import]",
                        TI + "::test_a_missing_required_column_is_refused_before_any_read[run_runs-launch_key-dry_run]"})],
     []),
    ("P10", 2, "position bool 허용",
     [(GATE, swap("            if not isinstance(position, int) or isinstance(position, bool):\n",
                  "            if not isinstance(position, int):\n"))],
     [(PURE, [TG], {TG + "::test_a_position_that_is_not_an_int_is_refused[bool-run_steps]"}),
      (BUSINESS, [TI], {TI + "::test_a_position_that_is_not_an_int_is_refused[bool]"})],
     []),
    ("P11", 2, "실행 0 거절 지움",
     [(GATE, swap("    if not runs:\n        raise Refused(\"묶음에 실행이 없다\")\n", ""))],
     [(PURE, [TG], {TG + "::test_a_bundle_without_runs_is_refused"}),
      (BUSINESS, [TI], {TI + "::test_a_shape_the_export_cannot_make_is_refused[no_runs]"})],
     []),
    ("P12", 2, "안 쓰인 문서 거절 지움",
     [(GATE, swap("    if set(documents) - reached:\n", "    if False:\n"))],
     [(PURE, [TG], {TG + "::test_a_document_no_run_uses_is_refused"}),
      (BUSINESS, [TI], {TI + "::test_a_shape_the_export_cannot_make_is_refused[unused_document]"})],
     []),
    ("P13", 2, "dry-run 앞 taken_keys 읽기 지움",
     [(IMPORT, swap("    if bundle_selectors.taken_keys(company_id=company_id, keys=keys):  # 그때의 모습(잠금 없음 — HD1 R3)\n"
                    "        raise Refused(\"이 묶음은 이미 그 회사에 넣었다\")\n", ""))],
     [(BUSINESS, [TI], {TI + "::test_a_dry_run_after_the_import_is_refused"})],
     []),
    ("P14", 2, "S2 모듈 확인 지움",
     [(GATE, swap("                if not isinstance(pointed, int) or isinstance(pointed, bool) or modules.get(pointed) != module:\n",
                  "                if False:\n"))],
     [(PURE, [TG], {TG + "::test_a_module_row_pointing_elsewhere_is_refused[other_module]"}),
      (BUSINESS, [TI], {TI + "::test_a_module_row_pointing_at_another_modules_run_is_refused"})],
     []),
    ("P15", 2, "내보내기 합 상한 지움(blob·bundle.json 둘 다)",
     [(EXPORT, swap(CAP, "                if False:\n")), (EXPORT, swap(CAP_JSON, "            if False:\n"))],
     [(BUSINESS, [TE], {TE + "::test_a_bundle_past_the_import_default_limit_is_not_written"})],
     []),
    ("P16", 2, "⑤ 다시 읽은 blob sha 대조 지움",
     [(IMPORT, swap("            if len(data) != size or hashlib.sha256(data).hexdigest() != item.blob:\n",
                    "            if False:\n"))],
     [(BUSINESS, [TI], {TI + "::test_a_blob_swapped_before_the_puts_fails_after_rolling_back"})],
     []),
    ("P17", 2, "shared 를 거절로 되돌림(문서 쪽)",
     [(CALC_BUNDLE, swap('        if blob is None or blob.role not in ("document", SHARED):\n',
                         '        if blob is None or blob.role != "document":\n'))],
     [(PURE, [TB], {TB + "::test_a_shared_blob_passes_both_sides"}),
      (BUSINESS, [TI], {TI + "::test_the_same_bytes_as_a_document_and_a_run_file_travel_as_one_shared_blob"})],
     []),
    ("P18", 2, "안전망 지움",
     [(IMPORT, swap("    except (KeyError, TypeError, ValueError, RecursionError) as err:",
                    "    except ZeroDivisionError as err:"))],
     [(BUSINESS, [TI], {TI + "::test_the_safety_net_names_the_exception_only[KeyError]"})],
     []),
    ("P24", 2, "내보내기 임시 파일 finally 지움",
     [(EXPORT, swap("    finally:\n        Path(temp).unlink(missing_ok=True)\n", "    finally:\n        pass\n"))],
     [(BUSINESS, [TE], {TE + "::test_bytes_that_differ_while_writing_leave_no_file[file]"})],
     []),
    ("X2", 2, "check_gates 가 check_carried 를 부르지 않음(러너 더함 — 안전망 글로 바뀌면 빨강)",
     [(IMPORT, swap("    check_carried(bundle)\n    check_shape(bundle)\n", "    check_shape(bundle)\n"))],
     [(BUSINESS, [TI], {TI + "::test_a_missing_required_column_is_refused_before_any_read[run_runs-launch_key-import]"})],
     []),
]

# ── ③ 모듈 줄 S1·S3·347 ① ──
T_ACT = E / "translation/service/actions/bundle.py"
G_ACT = E / "greenwash/service/actions/bundle.py"
DV_ACT = E / "dataverify/service/actions/runs.py"
TT = "esgapi/translation/tests/service/actions/test_bundle_carrier.py"
GT = "esgapi/greenwash/tests/service/actions/test_bundle_carrier.py"
TR = "esgapi/runs/tests/service/selectors/test_runs.py"
DT = "esgapi/dataverify/tests/service/apis/test_dataverify_runs.py"
PLANTS += [
    ("P19", 3, "_swap 이 int 아닌 fromRunId 를 그대로 둠",
     [(T_ACT, swap('    raise CarrierRefused(f"묶음의 {key} 가 정수 실행 id 가 아니다")\n', "    return fields\n"))],
     [(BUSINESS, [TT], {TT + "::test_a_forged_from_run_id_is_refused[text]",
                        TT + "::test_a_forged_from_run_id_is_refused[true]",
                        TT + "::test_a_bundle_with_a_text_from_run_id_is_refused_with_no_writes"})],
     []),
    ("P20", 3, "검토 겹침 검사 지움",
     [(G_ACT, swap("        if len(set(reviewed)) != len(reviewed):\n", "        if False:\n"))],
     [(BUSINESS, [GT], {GT + "::test_a_forged_review_bundle_is_refused_before_writing[two_reviews]"})],
     []),
    ("P21", 3, "검토 없는 표시 검사 지움",
     [(G_ACT, swap('            if row["runOldId"] not in reviewed:\n', "            if False:\n"))],
     [(BUSINESS, [GT], {GT + "::test_a_forged_review_bundle_is_refused_before_writing[mark_without_review]"})],
     []),
    ("P22", 3, "새 selector 가 options 칸을 CASE 밖에서 통째 읽음",
     [(RUNS_SEL, swap('            When(_nul_marked(), then=F("options")),\n            default=Value(None),\n',
                      '            When(_nul_marked(), then=F("options")),\n            default=F("options"),\n'))],
     [(BUSINESS, [TR], {TR + "::test_run_page_brief_never_selects_the_whole_options_outside_the_nul_branch"})],
     []),
    ("P23", 3, "itemCount 투영이 테마 꼴 밖에서 0(BASE None)",
     [(DV_ACT, swap("        if kind != \"array\" or length is None:\n            return None\n",
                    "        if kind != \"array\" or length is None:\n            continue\n"))],
     [(BUSINESS, [DT], {DT + "::test_the_four_fields_equal_the_base_count_for_every_shape[theme_text]",
                        DT + "::test_the_four_fields_equal_the_base_count_for_every_shape[theme_null]"})],
     []),
    ("X3", 3, "\\u0000 표시 줄을 비키지 않음(러너 더함 — pg 가 쪽 전체를 오류로)",
     [(RUNS_SEL, swap("        When(_nul_marked(), then=Value(None, output_field=JSONField())),\n", ""))],
     [(BUSINESS, [DT], {DT + "::test_the_four_fields_equal_the_base_count_for_every_shape[nul_in_item]"})],
     []),
]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT and (ONLY is None or p[0] in ONLY)]
EXCEPTION = re.compile(r"NameError|SyntaxError|ImportError")  # 심은 글이 이런 오류로 빨개지면 무효


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str, str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last, text


files = sorted({f for p in PLANTS for f, _ in p[3]} | {f for p in PLANTS for f in p[5]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _failed, last, _ = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant(number: str, what: str, edits) -> bool:
    for f, fn in edits:
        text = f.read_text(encoding="utf-8")
        new = fn(text)
        if new is None or new == text:
            print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
            return False
        f.write_text(new, encoding="utf-8")
    return True


def plant_and_check(number: str, what: str, edits, checks, base_tests) -> tuple[bool | None, bool | None]:
    originals = {f: f.read_bytes() for f, _ in edits} | {f: f.read_bytes() for f in base_tests}
    try:
        if not plant(number, what, edits):
            return False, None
        hit_all, skipped = True, False
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last, text = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            if EXCEPTION.search(text):
                print(f"{label} 이름·문법·import 오류로 빨강(무효 — 심은 글이 틀렸다)")
                hit = False
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)}"
                  f" — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        control = None
        if base_tests:
            for f in base_tests:
                f.write_bytes(base_bytes(f))
            layer, targets, _expected = checks[0]
            code, failed, last, _text = run(layer, targets, LOGS / f"{number}-base.log")
            control = code == 0
            print(f"{number}/BASE 대조 {'초록(구멍 재현)' if control else '빨강'} EXIT={code} {last}")
        return (None if skipped and hit_all else hit_all), control
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = extra_caught = extra = 0
controls: list[bool] = []
try:
    for number, _commit, what, edits, checks, base_tests in PLANTS:
        result, control = plant_and_check(number, what, edits, checks, base_tests)
        if control is not None:
            controls.append(control)
        if number.startswith("X"):
            extra += 1
            extra_caught += 1 if result is True else 0
        else:
            planted += 1
            caught += 1 if result is True else 0
        print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")
except KeyboardInterrupt:
    print("멈춤(INT·TERM) — 심은 파일은 되썼다")
same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"BASE_CONTROL={sum(controls)}/{len(controls)}")
print(f"EXTRA={extra_caught}/{extra}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
ok = zero_ok and same and caught == planted and planted > 0 and all(controls) and extra_caught == extra
sys.exit(0 if ok else 1)
PY
