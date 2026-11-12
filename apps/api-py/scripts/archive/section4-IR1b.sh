#!/usr/bin/env bash
# 밴드 IR1b(MARC-TICK-282) §4 의 자기검증. 중대성평가 IRO 1부 흐름 materiality.colab@155 와 core.llm 최소 고침을 잰다.
#   사용: apps/api-py/scripts/section4-IR1b.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0.
#   아무것도 없으면 1~7·9·10. 8(심은 파손)은 --planted 일 때만 돈다 — 작업 트리의 파일을 하나씩 고쳐 쓰고 바이트째
#   되돌리므로 같은 워크트리에서 다른 실행과 겹치지 않게 한 번에 하나만.
#   --msg 는 6·9단계가 함께 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 없으면 HEAD 커밋 메시지).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/IR1b.out). 검증자는 S4_OUT=…/IR1b.verify 로 돌려 러너 기록을 덮지 않는다.
# 읽기판(받은 코랩의 뽑은 판)은 워크트리 밖이다 — MARCSPON_ROOT(기본 워크트리의 ../..) 아래에서 읽고, 못 읽으면 FAIL.
#   읽기판의 글은 이 스크립트에도 출력에도 싣지 않는다(줄 범위·수·EXIT 만). 7단계가 뗀 셀 8 조각은 S4_OUT 아래(git 밖)
#   에만 둔다(MARC-ENT-310). 도우미는 scripts/materiality_compare_ir1b.py.
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 -I. LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=99fa3660
OUT="${S4_OUT:-$ROOT/../IR1b.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
READING_DIR="$MARCSPON_ROOT/received-derived/2026-10-15/중대성평가 IRO 코랩"
FORBIDDEN="$MARCSPON_ROOT/esg-app.worktrees/G1a.out/forbidden-words.txt"
API="$ROOT/apps/api-py"
M=esgapi/materiality
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,9,10
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) ONLY="$ONLY,8"; shift ;;
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

PY_HELPER="$(mktemp -t s4ir1b.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import os, re, subprocess, sys

MODE, BASE = sys.argv[1], sys.argv[2]
API = "apps/api-py/"
M = API + "esgapi/materiality/"
C = API + "esgapi/core/"


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


# 허용 경로(§2-1 core 71-1~71-4 · §2-2 흐름 · §2-3 스크립트)
CORE_71 = {
    C + "llm/data/models.json",
    C + "llm/data/README.md",
    C + "llm/client.py",
    C + "llm/types.py",
    C + "llm/providers/openai.py",
    C + "tests/llm/test_config_gpt41.py",
    C + "tests/llm/test_config_gpt4o.py",
    C + "tests/test_llm_cost.py",
    C + "tests/calc/test_ai_settings.py",
    C + "tests/llm/providers/test_openai_web_search.py",
}
CORE_71_3 = [C + "tests/llm/test_config_gpt41.py", C + "tests/test_llm_cost.py", C + "tests/calc/test_ai_settings.py"]
ALLOWED = re.compile(
    r"^apps/api-py/("
    r"esgapi/materiality/flows/(__init__|colab_155|registration)\.py"
    r"|esgapi/materiality/prompts/(regulation|keywords|controversy)/1\.md"
    r"|esgapi/materiality/prompts/README\.md"
    r"|esgapi/materiality/tests/test_axes\.py"
    r"|esgapi/materiality/tests/flows/(__init__|support|test_colab_155|test_failures|test_registration)\.py"
    r"|\.importlinter"
    r"|scripts/section4-IR1b\.sh"
    r"|scripts/materiality_compare_ir1b\.py"
    r")$"
)
IR1A = re.compile(r"^apps/api-py/esgapi/materiality/(engines/|contracts/shapes\.py|tests/data/|outputs/xlsx\.py)")


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
    outside = [f for f in paths if not (ALLOWED.match(f) or f in CORE_71)]
    for f in outside:
        print(f"  ★ 허용 경로 밖: {f}")
    bad += len(outside)
    core = [f for f in paths if f.startswith(C)]
    print(f"  바뀐 경로 {len(paths)} · core {len(core)}(71-1~71-4 목록 {len(CORE_71)} 안) · 허용 밖 {len(outside)}")
    ir1a = [f for f in paths if IR1A.match(f)]
    for f in ir1a:
        print(f"  ★ IR1a 경로가 바뀜: {f}")
    bad += len(ir1a)
    wire = M + "contracts/wire.py"
    wire_minus = removed_lines(wire)
    if wire_minus:
        print(f"  ★ wire.py 에서 지운 줄 {len(wire_minus)}(더하기만)")
        bad += 1
    lint = API + ".importlinter"
    plus = [l for l in git("diff", "-U0", BASE, "--", lint).splitlines() if l.startswith("+") and not l.startswith("+++")]
    minus = removed_lines(lint)
    print(f"  .importlinter ^+ {len(plus)} · ^- {len(minus)}")
    if plus != ["+    esgapi.materiality.flows"] or minus:
        bad += 1
        print("  ★ .importlinter 는 「    esgapi.materiality.flows」 한 줄 더하기만")
    # 71-3 의 셋(새 test_config_gpt4o.py 는 새 파일): 지운 줄은 단언·시험 이름·LOOP_ROUTES·주석뿐
    odd = []
    for f in CORE_71_3:
        for l in removed_lines(f):
            s = l.strip()
            if not (s.startswith("assert ") or s.startswith("def test_") or s.startswith("LOOP_ROUTES") or s.startswith("#")):
                odd.append((f, s[:60]))
    for f, s in odd:
        print(f"  ★ 71-3 에서 단언·이름 밖의 지운 줄: {f}: {s}")
    print(f"  71-3 셋의 지운 줄 {sum(len(removed_lines(f)) for f in CORE_71_3)} · 단언·이름 밖 {len(odd)}")
    return bad + len(odd)


def code_lines(reading):
    """읽기판 code 셀 줄(공백 정규화, 12자 이상)."""
    text = open(reading, encoding="utf-8").read()
    out = set()
    for m in re.finditer(r"^### 셀 \d+ · code\n\n(`{3,4})python\n(.*?)\n\1$", text, re.S | re.M):
        for line in m.group(2).splitlines():
            norm = " ".join(line.split())
            if len(norm) >= 12:
                out.add(norm)
    return out


KEY_FILES = ("marcspon" + "-openai", "spike" + "/.env")
"""키 파일 이름(이 파일에 글자째 두면 스스로 걸린다 — 이어 짓는다)."""
TRIVIAL = {"|---|---|---|", '"results": {', "return out", "return None", 'if __name__ == "__main__":'}
"""코랩 코드와 겹쳐도 사본이 아닌 짧은 꼴(표 줄·JSON 열쇠·흔한 문)."""


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
    colab = code_lines(reading)
    ours = {" ".join(l.split()) for l in added_lines()}
    overlap = sorted(l for l in ours & colab if l not in TRIVIAL)
    for l in overlap:
        print(f"  ★ 코랩 code 셀 줄과 겹침(공백 정규화 12자 이상): {len(l)}자")
    print(f"  코랩 code 셀 줄 {len(colab)} · 더한 줄 {len(ours)} · 겹침 {len(overlap)}(사소한 꼴 {len(TRIVIAL)} 뺌)")
    if len(colab) < 100:
        print("  ★ 읽기판 code 셀 줄이 너무 적다 — 대조가 안 문다")
        bad += 1
    return bad + len(overlap)


TRAILERS = [
    "Ticket: MARC-TICK-282",
    "Derives-from: MARC-ENT-425",
    "Concerns: MARC-ISSUE-345",
    "Constraint: 1부는 코랩 그대로(gpt-4o·t 0.1·web_search low·기간 미전달) — MARC-ENT-425",
    "Constraint: 실호출 0, 저장소에 코랩 코드 사본 0 — MARC-ENT-262, MARC-ENT-310",
    "Directive: engines/colab_155 는 고치지 않는다 — 흐름 상수(JOIN·상한·경로)는 flows/colab_155.py 에만",
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
]
TITLE = re.compile(r"^(feat\(core-llm\)|feat\(materiality\)|chore\(materiality\)): IR1b [①②③] ")


def step9(msg):
    lines = open(msg, encoding="utf-8").read().rstrip("\n").split("\n")
    bad = 0
    if not TITLE.match(lines[0]):
        bad += 1
        print("  ★ 제목이 IR1b ①②③ 꼴이 아니다")
    block = []
    for line in reversed(lines):
        if not line.strip():
            break
        block.insert(0, line)
    # ① 은 Directive 줄이 다르다(core 커밋) — 그 커밋에는 Directive 를 묻지 않는다
    need = [t for t in TRAILERS if not (lines[0].startswith("feat(core-llm)") and t.startswith("Directive:"))]
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


F = M + "flows/colab_155.py"
T = "esgapi/materiality/tests/flows/"
# 심은 파손: (번호, 파일, 옛 글, 새 글, 빨개져야 할 것들). 빨개질 것: ("pytest", 경로) · ("lint",) · ("s7",)
PLANTS = [
    ("P1", F, 'USER_JOIN: Final = "\\n\\n"', 'USER_JOIN: Final = "\\n"', [("pytest", T + "test_colab_155.py"), ("s7",)]),
    ("P2", F, "        temperature=constants.TEMPERATURE,\n", "", [("pytest", T + "test_colab_155.py"), ("s7",)]),
    ("P3", F, 'SYSTEM_PLACEMENT: Final = "input_message"', 'SYSTEM_PLACEMENT: Final = "instructions"',
     [("pytest", T + "test_colab_155.py"), ("s7",)]),
    ("P4", F, "search_context_size=constants.SEARCH_CONTEXT_SIZE, user_location",
     'search_context_size="medium", user_location', [("pytest", T + "test_colab_155.py"), ("s7",)]),
    ("P5", F, '        FlowStep(name="regulation", run=_regulation),\n        FlowStep(name="keywords", run=_keywords),\n',
     '        FlowStep(name="keywords", run=_keywords),\n        FlowStep(name="regulation", run=_regulation),\n',
     [("pytest", T + "test_colab_155.py")]),
    ("P6", F, "for attempt in range(1 + constants.RETRY_ON_INCOMPLETE):", "for attempt in range(1):",
     [("pytest", T + "test_failures.py")]),
    ("P7", F, "text, failure, ending = cut.partial_text, failure_of", "text, failure, ending = None, failure_of",
     [("pytest", T + "test_failures.py")]),
    ("P8", F, "text, failure, ending = None, failure_of(kind, failure_message(result)), kind",
     "text, failure, ending = None, None, kind", [("pytest", T + "test_failures.py")]),
    ("P9a", F, "        if spent >= inputs.max_cost_usd:\n", "        if False:\n", [("pytest", T + "test_failures.py")]),
    ("P9b", F, "        if spent >= inputs.max_cost_usd:\n", "        if attempt == 0 and spent >= inputs.max_cost_usd:\n",
     [("pytest", T + "test_failures.py")]),
    ("P10", F, 'return StepOutput(data={"results": [dumped]}, files=(report,))',
     'return StepOutput(data={"results": [result]}, files=(report,))', [("pytest", T + "test_colab_155.py")]),
    ("P11", F, "        max_output_tokens=MAX_OUTPUT_TOKENS,\n        timeout_ms=TIMEOUT_MS,\n",
     "        timeout_ms=TIMEOUT_MS,\n", [("pytest", T + "test_colab_155.py")]),
    ("P12", F, "import json\n", "import json\n\nimport django  # noqa: F401\n", [("lint",)]),
    ("P13", F, "search_context_size=constants.SEARCH_CONTEXT_SIZE, user_location=ApproximateLocation(country=user_location)",
     "search_context_size=constants.SEARCH_CONTEXT_SIZE", [("pytest", T + "test_colab_155.py"), ("s7",)]),
]


def red(check, out, reading):
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")}
    if check[0] == "pytest":
        cmd, cwd = ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", check[1]], API
    elif check[0] == "lint":
        cmd, cwd = ["uv", "run", "--frozen", "lint-imports"], API
    else:
        cmd = ["uv", "run", "--frozen", "python", "-I", "scripts/materiality_compare_ir1b.py", reading,
               os.path.join(out, "planted-s7")]
        cwd = API
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    lines = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    if check[0] == "s7":
        tail = [l for l in lines if l.startswith("COLAB_DIFF=")][-1:] or [""]
        if not re.match(r"^COLAB_DIFF=[1-9][0-9]*$", tail[0]):
            return False, "★ 대조가 다름 수를 내지 못했다(멈춤이나 0) · " + (tail[0] or (lines[-1:] or [""])[0])[:80]
        return True, tail[0]
    fails = [l for l in lines if l.startswith("FAILED") or "broken" in l.lower()]
    return done.returncode != 0, (fails[:1] or lines[-1:] or [""])[0][:110]


def step8(out, reading):
    caught = 0
    for name, path, old, new, checks in PLANTS:
        ok = True
        original = open(path, "rb").read()
        text = original.decode("utf-8")
        if text.count(old) != 1:
            print(f"  ★ {name}: 심을 자리가 하나가 아니다({text.count(old)})")
            continue
        try:
            open(path, "w", encoding="utf-8").write(text.replace(old, new))
            for check in checks:
                is_red, tail = red(check, out, reading)
                print(f"  {name} → {check[0]} {'빨강' if is_red else '★ 초록'} · {tail}")
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
elif MODE == "8":
    sys.exit(step8(sys.argv[3], sys.argv[4]))
elif MODE == "9":
    sys.exit(min(step9(sys.argv[3]), 1))
PYEOF

# 1. materiality(N0 117 → N1) + core.llm 표적
if want 1; then
  api uv run --frozen pytest -q $M -p no:cacheprovider > "$OUT/s1-pytest.log" 2>&1
  code=$?
  tries=$(grep -c -E '소켓 연결을 시도했다|이름 풀이를 시도했다' "$OUT/s1-pytest.log")
  passed=$(tail -1 "$OUT/s1-pytest.log" | sed -n -E 's/^([0-9]+) passed.*/\1/p')
  echo "  materiality: $(tail -1 "$OUT/s1-pytest.log") · N0 117 · 막힌 소켓 시도 $tries"
  if [ "$tries" != 0 ] || [ -z "$passed" ] || [ "$passed" -le 117 ]; then code=1; fi
  api uv run --frozen pytest -q -p no:cacheprovider esgapi/core/tests/llm esgapi/core/tests/test_llm_cost.py \
    esgapi/core/tests/calc/test_ai_settings.py > "$OUT/s1-core.log" 2>&1 || code=1
  echo "  core.llm: $(tail -1 "$OUT/s1-core.log")"
  report 1 "pytest $M + core.llm" "$code"
fi

# 2. import 계약 17, 다 안 esgapi.materiality.flows 한 번
if want 2; then
  api uv run --frozen lint-imports > "$OUT/s2-lint.log" 2>&1
  code=$?
  got=$(grep 'Contracts:' "$OUT/s2-lint.log")
  n=$(grep -c '^    esgapi\.materiality\.flows$' "$API/.importlinter")
  echo "  $got · .importlinter 의 esgapi.materiality.flows 줄 $n"
  if [ "$got" != "Contracts: 17 kept, 0 broken." ] || [ "$n" != 1 ]; then code=1; fi
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
  api uv run --frozen pyright $M esgapi/core/llm scripts/materiality_compare_ir1b.py > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  api uv run --frozen ruff check $M esgapi/core/llm esgapi/core/tests scripts/materiality_compare_ir1b.py \
    > "$OUT/s4-ruff.log" 2>&1 || code=1
  api uv run --frozen ruff format --check $M esgapi/core/llm esgapi/core/tests scripts/materiality_compare_ir1b.py \
    >> "$OUT/s4-ruff.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s4-ruff.log")"
  python3 -I "$PY_HELPER" 4 "$BASE" || code=1
  report 4 "pyright·ruff·완화 줄" "$code"
fi

# 5. 허용 경로·.importlinter·IR1a 0줄·core 는 71 목록만
if want 5; then
  python3 -I "$PY_HELPER" 5 "$BASE"
  report 5 "허용 경로·.importlinter·core 71" $?
fi

# 6. 금지 글·키·바이너리·코랩 code 셀 줄 겹침
if want 6; then
  if reading_ok && [ -r "$FORBIDDEN" ]; then
    python3 -I "$PY_HELPER" 6 "$BASE" "$READING" "$MSG" "$MARCSPON_ROOT/band-reports/IR1b.md" "$FORBIDDEN"
    code=$?
  else
    echo "  ★ 읽기판이나 금지 글 목록을 못 읽는다"
    code=1
  fi
  report 6 "금지 글·키·바이너리·코랩 겹침" "$code"
fi

# 7. 코랩 요청 몸 대조(셀 8 클래스를 실행 때 떼어 S4_OUT 아래서만)
if want 7; then
  if reading_ok; then
    rm -rf "$OUT/s7-pieces"
    api uv run --frozen python -I scripts/materiality_compare_ir1b.py "$READING" "$OUT/s7-pieces" > "$OUT/s7-colab.log" 2>&1
    code=$?
    grep -v '^COLAB_DIFF=' "$OUT/s7-colab.log" | sed 's/^/  /' | tail -30
    grep '^COLAB_DIFF=' "$OUT/s7-colab.log" || { echo "COLAB_DIFF=없음(대조가 끝나지 않았다)"; code=1; }
    report 7 "코랩 요청 몸 대조" "$code"
  else
    report 7 "코랩 요청 몸 대조" 1
  fi
fi

# 8. 심은 파손(--planted). 하나씩 심고 빨강을 보고 바이트째 되돌린다. 끝나고 git status 가 시작 때와 같아야 한다.
if want 8; then
  if reading_ok; then
    before=$(git status --porcelain)
    python3 -I "$PY_HELPER" 8 "$BASE" "$OUT" "$READING" > "$OUT/s8-planted.log" 2>&1
    code=$?
    sed 's/^/  /' "$OUT/s8-planted.log" | grep -v '^  PLANTED='
    grep '^PLANTED=' "$OUT/s8-planted.log"
    if [ "$(git status --porcelain)" != "$before" ]; then code=1; echo "  ★ 심은 파손 뒤 작업 트리가 달라졌다"; fi
  else
    code=1
  fi
  report 8 "심은 파손" "$code"
fi

# 9. 커밋 메시지 트레일러
if want 9; then
  if [ -f "$MSG" ]; then
    python3 -I "$PY_HELPER" 9 "$BASE" "$MSG"
    report 9 "트레일러($MSG)" $?
  else
    git log -1 --format=%B HEAD > "$OUT/s9-head-msg.txt"
    echo "  메시지 초안이 없어 HEAD 커밋 메시지를 본다"
    python3 -I "$PY_HELPER" 9 "$BASE" "$OUT/s9-head-msg.txt"
    report 9 "트레일러(HEAD)" $?
  fi
fi

# 10. 빠른 게이트(뿌리에서)
if want 10; then
  start=$(date +%s)
  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast > "$OUT/s10-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s10-verify-fast.log")
  secs=$(( $(date +%s) - start ))
  echo "  $last · ${secs}초"
  if [ "$secs" -gt 30 ]; then echo "  uptime: $(uptime)"; fi
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 10 "scripts/verify.sh --fast" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
