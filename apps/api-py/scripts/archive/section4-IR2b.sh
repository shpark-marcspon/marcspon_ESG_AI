#!/usr/bin/env bash
# 밴드 IR2b(MARC-TICK-305) §4 의 자기검증. 중대성평가 IRO 1부 → 2부 한 실행(흐름 materiality.iro@155·기간 창)을 잰다.
#   사용: apps/api-py/scripts/section4-IR2b.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0.
#   아무것도 없으면 1~8·10·11. 9(심은 파손)는 --planted 일 때만 돈다 — 작업 트리의 파일을 하나씩 고쳐 쓰고 바이트째
#   되돌리므로(SIGTERM·예외에도 되돌린다) 같은 워크트리에서 다른 실행과 겹치지 않게 한 번에 하나만.
#   --msg 는 6·10단계가 함께 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 없으면 HEAD 커밋 메시지).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/IR2b.out). 검증자는 S4_OUT=…/IR2b.verify 로 돌려 러너 기록을 덮지 않는다.
# 읽기판(받은 코랩의 뽑은 판)은 워크트리 밖이다 — MARCSPON_ROOT(기본 워크트리의 ../..) 아래에서 읽고, 못 읽으면 FAIL.
#   읽기판의 글은 이 스크립트에도 출력에도 싣지 않는다(줄 범위·수·EXIT 만 — 6단계의 겹침 셈에만 쓴다).
#   7·8단계 도우미는 scripts/materiality_compare_ir2b.py(모의 공급사의 요청 대조·기간 사례 표, 출력은 S4_OUT 아래만).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 -I. LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=0a41a1c7
OUT="${S4_OUT:-$ROOT/../IR2b.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
READING_DIR="$MARCSPON_ROOT/received-derived/2026-10-15/중대성평가 IRO 코랩"
FORBIDDEN="$MARCSPON_ROOT/esg-app.worktrees/G1a.out/forbidden-words.txt"
API="$ROOT/apps/api-py"
M=esgapi/materiality
N0=241
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,8,10,11
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) ONLY="$ONLY,9"; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
[ -n "$MSG" ] || MSG="$OUT/commit-msg.txt"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY "$@"); }
echo "BASE=$BASE HEAD=$(git rev-parse HEAD)"

READING=""
for f in "$READING_DIR"/*.md; do [ -r "$f" ] && READING="$f"; done
reading_ok() {
  if [ -z "$READING" ]; then echo "  ★ 읽기판을 못 읽는다(MARCSPON_ROOT=$MARCSPON_ROOT)"; return 1; fi
  return 0
}

PY_HELPER="$(mktemp -t s4ir2b.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, os, re, signal, subprocess, sys

MODE, BASE = sys.argv[1], sys.argv[2]
API = "apps/api-py/"
M = API + "esgapi/materiality/"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def untracked():
    return git("ls-files", "--others", "--exclude-standard").splitlines()


def changed():
    return sorted(set(git("diff", "--name-only", BASE).splitlines()) | set(untracked()))


def added_lines(paths=None):
    """BASE 이후 더한 줄(추적 파일의 diff ^+ 와 새 파일 전부)."""
    spec = ["--", *paths] if paths else []
    lines = [l[1:] for l in git("diff", "-U0", BASE, *spec).splitlines() if l.startswith("+") and not l.startswith("+++")]
    for f in untracked():
        if paths and f not in paths:
            continue
        try:
            lines += open(f, encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            lines.append(f"<바이너리 {f}>")
    return lines


def removed_lines(path):
    return [l[1:] for l in git("diff", "-U0", BASE, "--", path).splitlines() if l.startswith("-") and not l.startswith("---")]


# 허용 경로(§2-1·§2-2)
ALLOWED = re.compile(
    r"^apps/api-py/("
    r"esgapi/materiality/contracts/(shapes|wire)\.py"
    r"|esgapi/materiality/tests/data/flow-shapes/materiality\.result@2\.schema\.json"
    r"|esgapi/materiality/tests/contracts/(test_shapes_v2|test_wire_window)\.py"
    r"|esgapi/materiality/flows/(iro_155|registration)\.py"
    r"|esgapi/materiality/outputs/final_xlsx\.py"
    r"|esgapi/materiality/tests/flows/(support|test_iro_155|test_iro_failures|test_registration)\.py"
    r"|esgapi/materiality/tests/test_axes\.py"
    r"|scripts/section4-IR2b\.sh"
    r"|scripts/materiality_compare_ir2b\.py"
    r")$"
)
FROZEN = re.compile(
    r"^apps/api-py/esgapi/materiality/("
    r"flows/(colab_155|part2_155)\.py"
    r"|engines/"
    r"|prompts/"
    r"|outputs/xlsx\.py"
    r"|tests/data/flow-shapes/materiality\.(input|result)@1\.schema\.json"
    r")"
)
"""1부·2부 단계와 @1 — 0줄(§1-3·§1-5)."""
ADD_ONLY = [M + "contracts/wire.py", M + "tests/flows/support.py"]
"""더하기만(^- 0)."""
SHAPES = M + "contracts/shapes.py"
SHAPES_MINUS = {"    = 영향 유형·리스크 종류가 시킨 값 밖(값은 그대로 둠).\"\"\""}
"""shapes.py 에서 지워도 되는 줄: MaterialityWarning2.code docstring 끝 줄(두 뜻을 이어 씀)."""
SHAPES_PLUS = re.compile(r'^(    "items_out_of_range",|    "item_date_unreadable",|    = 영향 유형·리스크 종류가 시킨 값 밖\(값은 그대로 둠\), items_out_of_range = .*|    밖인 1부 항목을 뺌.*item_date_unreadable = .*)$')
"""shapes.py 에 더해도 되는 줄: WarningCode2 두 값과 code docstring 두 뜻(①)."""
FINAL_XLSX = M + "outputs/final_xlsx.py"
FORBIDDEN_TREES = ("apps/api-py/esgapi/core/", "apps/api-py/esgapi/config/", "apps/api-py/generated/", "apps/api-py/.importlinter")


def step4():
    """완화 줄(type: ignore·pyright:)은 tests/ 만."""
    bad = 0
    for f in changed():
        if not f.endswith(".py") or "/tests/" in f or not os.path.isfile(f):
            continue
        lines = added_lines([f])
        n = sum(1 for l in lines if "type: ignore" in l or "pyright:" in l)
        if n:
            print(f"  ★ 완화 줄 {n}: {f}")
            bad += n
    print(f"  tests/ 밖 완화 줄 {bad}")
    return bad


def step5():
    bad = 0
    paths = changed()
    outside = [f for f in paths if not ALLOWED.match(f)]
    for f in outside:
        print(f"  ★ 허용 경로 밖: {f}")
    bad += len(outside)
    frozen = [f for f in paths if FROZEN.match(f)]
    for f in frozen:
        print(f"  ★ 1부·2부 단계·@1 파일이 바뀜: {f}")
    bad += len(frozen)
    trees = [f for f in paths if f.startswith(FORBIDDEN_TREES)]
    for f in trees:
        print(f"  ★ core·config·generated·.importlinter: {f}")
    bad += len(trees)
    for f in ADD_ONLY:
        minus = removed_lines(f)
        if minus:
            print(f"  ★ 더하기만 파일에서 지운 줄 {len(minus)}: {f}")
            bad += 1
    odd_minus = [l for l in removed_lines(SHAPES) if l not in SHAPES_MINUS]
    odd_plus = [l for l in added_lines([SHAPES]) if not SHAPES_PLUS.match(l)]
    for l in odd_minus + odd_plus:
        print(f"  ★ shapes.py 에서 ① 밖의 줄: {l.strip()[:60]}")
    bad += len(odd_minus) + len(odd_plus)
    xlsx_minus = removed_lines(FINAL_XLSX)
    xlsx_plus = [l for l in added_lines([FINAL_XLSX]) if l.strip() and not l.startswith("    ")]
    if len(xlsx_minus) > 1 or xlsx_plus:
        print(f"  ★ final_xlsx.py 가 docstring 밖으로 바뀜(지운 줄 {len(xlsx_minus)})")
        bad += 1
    print(
        f"  바뀐 경로 {len(paths)} · 허용 밖 {len(outside)} · 1부·2부·@1 {len(frozen)} · core 등 {len(trees)} · "
        f"shapes.py ① 밖 {len(odd_minus) + len(odd_plus)} · final_xlsx.py 지운 줄 {len(xlsx_minus)}"
    )
    return bad


def code_lines(reading):
    """읽기판 code 셀 줄(공백 정규화, 12자 이상) — 여러 줄 문자열(프롬프트 글) 안의 줄은 뺀다."""
    text = open(reading, encoding="utf-8").read()
    code, prompt = set(), set()
    for m in re.finditer(r"^### 셀 \d+ · code\n\n(`{3,4})python\n(.*?)\n\1$", text, re.S | re.M):
        src = m.group(2)
        inside = set()
        try:
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.Constant, ast.JoinedStr)) and (node.end_lineno or node.lineno) > node.lineno:
                    inside.update(range(node.lineno + 1, (node.end_lineno or node.lineno) + 1))
        except SyntaxError:
            pass
        for i, line in enumerate(src.splitlines(), 1):
            norm = " ".join(line.split())
            if len(norm) >= 12:
                (prompt if i in inside else code).add(norm)
    return code - prompt, len(prompt)


KEY_FILES = ("marcspon" + "-openai", "spike" + "/.env")
"""키 파일 이름(이 파일에 글자째 두면 스스로 걸린다 — 이어 짓는다)."""
TRIVIAL = {
    "from textwrap import dedent",
    "if value is None:",
    '"parsed": parsed,',
    'if __name__ == "__main__":',
    "return None",
    "if not isinstance(text, str):",
}
"""코랩 코드와 겹쳐도 사본이 아닌 짧은 꼴(흔한 import·문·JSON 열쇠)."""


def step6(reading, msg, report, words_path):
    bad = 0
    words = [w.strip() for w in open(words_path, encoding="utf-8") if w.strip() and not w.startswith("#")]
    texts = {"diff ^+": added_lines(), "커밋 메시지": git("log", "--format=%B", f"{BASE}..HEAD").splitlines()}
    for name, path in (("메시지 초안", msg), ("보고", report)):
        if os.path.isfile(path):
            texts[name] = open(path, encoding="utf-8").read().splitlines()
    key = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
    if not key.search("sk" + "-" + "A" * 20):
        print("  ★ 키 꼴 양성 대조 실패")
        bad += 1
    for name, lines in texts.items():
        w = sum(1 for l in lines if any(x in l for x in words))
        k = sum(1 for l in lines if key.search(l))
        f = sum(1 for l in lines if any(name in l for name in KEY_FILES))
        print(f"  {name}: 줄 {len(lines)} · 금지 글 {w} · 키 꼴 {k} · 키 파일 이름 {f}")
        bad += w + k + f
    print(f"  금지 글 {len(words)}개")
    exts = [f for f in changed() if re.search(r"\.(xlsx|csv|ipynb)$", f)]
    binary = [f for f in changed() if os.path.isfile(f) and b"\0" in open(f, "rb").read()]
    print(f"  xlsx·csv·ipynb 경로 {len(exts)} · 바이너리 {len(binary)}")
    bad += len(exts) + len(binary)
    colab, prompt_lines = code_lines(reading)
    ours = {" ".join(l.split()) for l in added_lines()}
    overlap = sorted(l for l in ours & colab if l not in TRIVIAL)
    for l in overlap:
        print(f"  ★ 코랩 code 셀 줄과 겹침(공백 정규화 12자 이상): {len(l)}자")
    print(
        f"  코랩 code 셀 줄 {len(colab)}(프롬프트 글 줄 {prompt_lines} 뺌) · 더한 줄 {len(ours)} · "
        f"겹침 {len(overlap)}(사소한 꼴 {len(TRIVIAL)} 뺌)"
    )
    if len(colab) < 100:
        print("  ★ 읽기판 code 셀 줄이 너무 적다 — 대조가 안 문다")
        bad += 1
    return bad + len(overlap)


TRAILERS = [
    "Ticket: MARC-TICK-305",
    "Concerns: MARC-ISSUE-355",
    "Derives-from: MARC-ENT-439",
    "Constraint: 1부 뒤 사람 손 없이 2부로 한 실행 — 다시 올린 엑셀 길은 자리만 — MARC-ENT-439",
    "Constraint: 1부 호출은 코랩 그대로, 기간은 2부 입력을 지을 때만 거름 — MARC-ENT-425",
    "Constraint: 실호출 0, 저장소에 코랩 코드 사본 0 — MARC-ENT-262, MARC-ENT-310",
    "Directive: 1부·2부 단계 코드는 고치지 않는다 — 잇기는 flows/iro_155.py 에서 colab_155.FLOW.run_step 과 part2_155.STEPS 를 감싸서만",
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
]
FIRST = "Directive: 「오늘」은 흐름 입력 today 로만 — 시계를 직접 읽지 않는다"
SECOND = (
    "Directive: 다시 올린 엑셀 읽기는 1차에 없다(MARC-ENT-439) — shortlist 길을 만드는 밴드가 RAW_JSON 되읽은 결과에 "
    "xlsx_cell_truncated 를 다시 단다"
)
TITLE = re.compile(r"^feat\(materiality\): IR2b [①②] ")


def step9(msg):
    lines = open(msg, encoding="utf-8").read().rstrip("\n").split("\n")
    bad = 0
    if not TITLE.match(lines[0]):
        bad += 1
        print("  ★ 제목이 IR2b ①② 꼴이 아니다")
    block = []
    for line in reversed(lines):
        if not line.strip():
            break
        block.insert(0, line)
    need = TRAILERS + ([FIRST] if "IR2b ①" in lines[0] else [SECOND] if "IR2b ②" in lines[0] else [])
    missing = [t for t in need if t not in block]
    for t in missing:
        print(f"  ★ 트레일러 없음: {t.split(':')[0]}")
    loose = [l for l in block if not re.match(r"^[A-Z][A-Za-z-]+: ", l)]
    last = block[-1] if block else ""
    if not last.startswith("Co-Authored-By: "):
        bad += 1
        print("  ★ 끝 줄이 Co-Authored-By 가 아니다")
    print(f"  제목 줄 {len(lines[0])}자 · 끝 문단 {len(block)}줄 · 빠진 트레일러 {len(missing)} · 트레일러 꼴 아닌 줄 {len(loose)}")
    return bad + len(missing) + len(loose)


W = M + "contracts/wire.py"
I = M + "flows/iro_155.py"
R = M + "flows/registration.py"
T = "esgapi/materiality/tests/"
TW = T + "contracts/test_wire_window.py"
TI = T + "flows/test_iro_155.py"
TF = T + "flows/test_iro_failures.py"
TR = T + "flows/test_registration.py"
# 심은 파손: (번호, 파일, [(옛 글, 새 글)], 빨개져야 할 것들). 빨개질 것: ("pytest", 경로) · ("lint",) · ("s7",)
PLANTS = [
    ("P1", W, [("    windowed = copy.deepcopy(dict(result))", '    windowed = cast("dict[str, Any]", result)'),
               ('            parsed = copy.deepcopy(cast("dict[str, Any]", outcome["parsed"]))',
                '            parsed = cast("dict[str, Any]", outcome["parsed"])')],
     [("pytest", TW), ("pytest", TI)]),
    ("P2", W, [("        elif start <= day <= end:", "        elif start < day < end:")], [("pytest", TW)]),
    ("P3", W, [('    published = item_date(element.get("publish_date"))\n'
                '    return published if published is not None else item_date(element.get("event_date"))',
                '    published = item_date(element.get("event_date"))\n'
                '    return published if published is not None else item_date(element.get("publish_date"))')],
     [("pytest", TW)]),
    ("P4", W, [("            tally.unreadable += 1\n            kept.append(element)\n", "            tally.unreadable += 1\n")],
     [("pytest", TW), ("pytest", TI)]),
    ("P5", W, [("    if tally.unreadable:", "    if False:")], [("pytest", TW)]),
    ("P6", W, [("    end = today if matched.group(2)", "    end = date.today() if matched.group(2)")],
     [("pytest", TW), ("pytest", TI)]),
    ("P7", I, [('    window = wire.parse_date_range(received["dateRange"], today)\n',
                '    window = wire.parse_date_range(received["dateRange"], today) or (date.min, date.max)\n')],
     [("pytest", TF)]),
    ("P8", I, [("wire.part2_input_from_result(inputs.received, windowed)", "wire.part2_input_from_result(inputs.received, part1)")],
     [("pytest", TI), ("s7",)]),
    ("P9", I, [('        "result": part1,', '        "result": windowed,')], [("pytest", TI)]),
    ("P10", I, [("*wire.truncated_warnings(calls)]", "]")], [("pytest", TF)]),
    ("P11", I, [('        "spentUsd": carried["controversy"].data["spentUsd"],', '        "spentUsd": 0.0,')], [("pytest", TF)]),
    ("P12", I, [('files=(*carried["report"].files, *out.files)', "files=out.files")], [("pytest", TI)]),
    ("P13", R, [('DEFAULTS: Final[dict[str, str]] = {"materiality": iro_155.FLOW_ID}',
                 'DEFAULTS: Final[dict[str, str]] = {"materiality": colab_155.FLOW_ID}')],
     [("pytest", TR), ("pytest", TI)]),
    ("P14", I, [("        received=inputs.received, tags=inputs.tags,",
                 '        received={**inputs.received, "geoScope": inputs.received["geoScope"] + "."}, tags=inputs.tags,')],
     [("pytest", TI), ("s7",)]),
    ("P15", I, [("from collections.abc import Mapping\n", "from collections.abc import Mapping\n\nimport django  # noqa: F401\n")],
     [("lint",)]),
]


def red(check, out, reading):
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")}
    if check[0] == "pytest":
        cmd = ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", check[1]]
    elif check[0] == "lint":
        cmd = ["uv", "run", "--frozen", "lint-imports"]
    else:
        cmd = ["uv", "run", "--frozen", "python", "-I", "scripts/materiality_compare_ir2b.py", "compare",
               os.path.join(out, "planted-s7")]
    done = subprocess.run(cmd, cwd=API, env=env, capture_output=True, text=True)
    lines = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    if check[0] == "s7":
        tail = [l for l in lines if l.startswith("PART1_SAME=")][-1:] or [""]
        got = re.match(r"^PART1_SAME=([0-9]+) PART2_SAME=([0-9]+)$", tail[0])
        if not got or int(got.group(1)) + int(got.group(2)) == 0:
            return False, "★ 대조가 다름 수를 내지 못했다(멈춤이나 0) · " + (tail[0] or (lines[-1:] or [""])[0])[:80]
        return True, tail[0]
    fails = [l for l in lines if l.startswith("FAILED") or "broken" in l.lower()]
    return done.returncode != 0, (fails[:1] or lines[-1:] or [""])[0][:110]


class Stop(Exception):
    pass


def _stop(signum, frame):
    raise Stop()


def step8(out, reading):
    signal.signal(signal.SIGTERM, _stop)
    caught = 0
    for name, path, edits, checks in PLANTS:
        ok = True
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        counts = [text.count(old) for old, _ in edits]
        if counts != [1] * len(edits):
            print(f"  ★ {name}: 심을 자리가 하나씩이 아니다({counts})")
            continue
        for old, new in edits:
            text = text.replace(old, new)
        try:
            open(path, "w", encoding="utf-8").write(text)
            for check in checks:
                is_red, tail = red(check, out, reading)
                print(f"  {name} → {check[0]} {check[1].rsplit('/', 1)[-1] if len(check) > 1 else ''} "
                      f"{'빨강' if is_red else '★ 초록'} · {tail}")
                ok = ok and is_red
        finally:
            open(path, "wb").write(original)
        if open(path, "rb").read() != original:
            print(f"  ★ {name}: 되돌리기 실패 {path}")
            ok = False
        caught += ok
    print(f"PLANTED={caught}/{len(PLANTS)}")
    return int(caught != len(PLANTS))


if MODE == "4":
    sys.exit(min(step4(), 1))
elif MODE == "5":
    sys.exit(min(step5(), 1))
elif MODE == "6":
    sys.exit(min(step6(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]), 1))
elif MODE == "9":
    sys.exit(step8(sys.argv[3], sys.argv[4]))
elif MODE == "10":
    sys.exit(min(step9(sys.argv[3]), 1))
PYEOF

# 1. materiality(N0 241 → N1)
if want 1; then
  api uv run --frozen pytest -q $M -p no:cacheprovider > "$OUT/s1-pytest.log" 2>&1
  code=$?
  tries=$(grep -c -E '소켓 연결을 시도했다|이름 풀이를 시도했다' "$OUT/s1-pytest.log")
  passed=$(tail -1 "$OUT/s1-pytest.log" | sed -n -E 's/^([0-9]+) passed.*/\1/p')
  echo "  materiality: $(tail -1 "$OUT/s1-pytest.log") · N0 $N0 · 막힌 소켓 시도 $tries"
  if [ "$tries" != 0 ] || [ -z "$passed" ] || [ "$passed" -le "$N0" ]; then code=1; fi
  report 1 "pytest $M" "$code"
fi

# 2. import 계약 17, materiality 다 안 넷 그대로
if want 2; then
  api uv run --frozen lint-imports > "$OUT/s2-lint.log" 2>&1
  code=$?
  got=$(grep 'Contracts:' "$OUT/s2-lint.log")
  n=$(grep -c -E '^    esgapi\.materiality\.(contracts|engines|outputs|flows)$' "$API/.importlinter")
  echo "  $got · .importlinter 의 materiality 다 안 줄 $n"
  if [ "$got" != "Contracts: 17 kept, 0 broken." ] || [ "$n" != 4 ]; then code=1; fi
  report 2 "lint-imports(계약 17)" "$code"
fi

# 3. 시험 자리
if want 3; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s3-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s3-layout.log")"
  report 3 "check_test_layout" "$code"
fi

# 4. 타입·꼴(완화는 tests/ 만)
if want 4; then
  api uv run --frozen pyright $M scripts/materiality_compare_ir2b.py > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  api uv run --frozen ruff check $M scripts/materiality_compare_ir2b.py > "$OUT/s4-ruff.log" 2>&1 || code=1
  api uv run --frozen ruff format --check $M scripts/materiality_compare_ir2b.py >> "$OUT/s4-ruff.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s4-ruff.log")"
  python3 -I "$PY_HELPER" 4 "$BASE" || code=1
  report 4 "pyright·ruff·완화 줄" "$code"
fi

# 5. 허용 경로·1부·2부 단계 0줄·더하기만·shapes.py ① 줄만·core 등 0줄
if want 5; then
  python3 -I "$PY_HELPER" 5 "$BASE"
  report 5 "허용 경로·1부·2부 0줄·더하기만" $?
fi

# 6. 금지 글·키·바이너리·코랩 code 셀 줄 겹침
if want 6; then
  if reading_ok && [ -r "$FORBIDDEN" ]; then
    python3 -I "$PY_HELPER" 6 "$BASE" "$READING" "$MSG" "$MARCSPON_ROOT/band-reports/IR2b.md" "$FORBIDDEN"
    code=$?
  else
    echo "  ★ 읽기판이나 금지 글 목록을 못 읽는다"
    code=1
  fi
  report 6 "금지 글·키·바이너리·코랩 겹침" "$code"
fi

# 7. 요청 대조(1부 단독·2부 시험 흐름·창을 좁힌 손 거름)
if want 7; then
  api uv run --frozen python -I scripts/materiality_compare_ir2b.py compare "$OUT/s7" > "$OUT/s7-compare.log" 2>&1
  code=$?
  grep -v '^PART1_SAME=' "$OUT/s7-compare.log" | sed 's/^/  /' | tail -20
  grep '^PART1_SAME=' "$OUT/s7-compare.log" || { echo "PART1_SAME=없음(대조가 끝나지 않았다)"; code=1; }
  report 7 "요청 대조" "$code"
fi

# 8. 기간 사례 표
if want 8; then
  api uv run --frozen python -I scripts/materiality_compare_ir2b.py window "$OUT" > "$OUT/s8-window.log" 2>&1
  code=$?
  grep -v '^WINDOW_CASES=' "$OUT/s8-window.log" | sed 's/^/  /' | tail -5
  grep '^WINDOW_CASES=' "$OUT/s8-window.log" || { echo "WINDOW_CASES=없음"; code=1; }
  report 8 "기간 사례 표" "$code"
fi

# 9. 심은 파손(--planted). 하나씩 심고 빨강을 보고 바이트째 되돌린다. 끝나고 git status 가 시작 때와 같아야 한다.
if want 9; then
  before=$(git status --porcelain)
  python3 -I "$PY_HELPER" 9 "$BASE" "$OUT" "-" > "$OUT/s9-planted.log" 2>&1
  code=$?
  sed 's/^/  /' "$OUT/s9-planted.log" | grep -v '^  PLANTED='
  grep '^PLANTED=' "$OUT/s9-planted.log"
  if [ "$(git status --porcelain)" != "$before" ]; then code=1; echo "  ★ 심은 파손 뒤 작업 트리가 달라졌다"; fi
  report 9 "심은 파손" "$code"
fi

# 10. 커밋 메시지 트레일러
if want 10; then
  if [ -f "$MSG" ]; then
    python3 -I "$PY_HELPER" 10 "$BASE" "$MSG"
    report 10 "트레일러($MSG)" $?
  else
    git log -1 --format=%B HEAD > "$OUT/s10-head-msg.txt"
    echo "  메시지 초안이 없어 HEAD 커밋 메시지를 본다"
    python3 -I "$PY_HELPER" 10 "$BASE" "$OUT/s10-head-msg.txt"
    report 10 "트레일러(HEAD)" $?
  fi
fi

# 11. 빠른 게이트(뿌리에서)
if want 11; then
  start=$(date +%s)
  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast > "$OUT/s11-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s11-verify-fast.log")
  secs=$(( $(date +%s) - start ))
  echo "  $last · ${secs}초"
  if [ "$secs" -gt 30 ]; then echo "  uptime: $(uptime)"; fi
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 11 "scripts/verify.sh --fast" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
