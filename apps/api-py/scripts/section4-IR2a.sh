#!/usr/bin/env bash
# 밴드 IR2a(MARC-TICK-288) §4 의 자기검증. 중대성평가 IRO 2부(결과 꼴 @2·엔진 글·단계·최종 엑셀)를 잰다.
#   사용: apps/api-py/scripts/section4-IR2a.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0.
#   아무것도 없으면 1~7·9·10. 8(심은 파손)은 --planted 일 때만 돈다 — 작업 트리의 파일을 하나씩 고쳐 쓰고 바이트째
#   되돌리므로(SIGTERM·예외에도 되돌린다) 같은 워크트리에서 다른 실행과 겹치지 않게 한 번에 하나만.
#   --msg 는 6·9단계가 함께 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 없으면 HEAD 커밋 메시지).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/IR2a.out). 검증자는 S4_OUT=…/IR2a.verify 로 돌려 러너 기록을 덮지 않는다.
# 읽기판(받은 코랩의 뽑은 판)은 워크트리 밖이다 — MARCSPON_ROOT(기본 워크트리의 ../..) 아래에서 읽고, 못 읽으면 FAIL.
#   읽기판의 글은 이 스크립트에도 출력에도 싣지 않는다(줄 범위·수·EXIT 만). 7단계가 뗀 셀 조각은 S4_OUT 아래(git 밖)
#   에만 둔다(MARC-ENT-310). 도우미는 scripts/materiality_compare_ir2a.py.
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 -I. LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=2f2bbfaf
OUT="${S4_OUT:-$ROOT/../IR2a.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
READING_DIR="$MARCSPON_ROOT/received-derived/2026-10-15/중대성평가 IRO 코랩"
FORBIDDEN="$MARCSPON_ROOT/esg-app.worktrees/G1a.out/forbidden-words.txt"
API="$ROOT/apps/api-py"
M=esgapi/materiality
N0=153
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

PY_HELPER="$(mktemp -t s4ir2a.XXXXXX)"
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


# 허용 경로(§2-1~§2-4 + 감독 허락 Q1·Q2)
ALLOWED = re.compile(
    r"^apps/api-py/("
    r"esgapi/materiality/contracts/(shapes|wire)\.py"
    r"|esgapi/materiality/tests/data/flow-shapes/materiality\.result@2\.schema\.json"
    r"|esgapi/materiality/tests/data/examples/result2-sample\.json"
    r"|esgapi/materiality/tests/contracts/(test_shapes_v2|test_wire_part2|test_shapes)\.py"
    r"|esgapi/materiality/engines/colab_155/(part2_prompts|part2_parsing|part2_render|constants)\.py"
    r"|esgapi/materiality/prompts/README\.md"
    r"|esgapi/materiality/prompts/(impact|financial|pathway)/1\.md"
    r"|esgapi/materiality/tests/engines/colab_155/(test_part2_prompts|test_part2_parsing|test_part2_render|test_purity)\.py"
    r"|esgapi/materiality/flows/part2_155\.py"
    r"|esgapi/materiality/tests/test_axes\.py"
    r"|esgapi/materiality/tests/flows/(support|test_part2_155|test_part2_failures)\.py"
    r"|esgapi/materiality/outputs/(final_xlsx|xlsx)\.py"
    r"|esgapi/materiality/tests/outputs/(test_final_xlsx|test_xlsx)\.py"
    r"|scripts/section4-IR2a\.sh"
    r"|scripts/materiality_compare_ir2a\.py"
    r")$"
)
PART1 = re.compile(
    r"^apps/api-py/esgapi/materiality/("
    r"engines/colab_155/(prompts|whitelists|parsing|outcomes|inputs)\.py"
    r"|flows/(colab_155|registration)\.py"
    r"|prompts/(regulation|keywords|controversy)/"
    r"|tests/data/flow-shapes/materiality\.(input|result)@1\.schema\.json"
    r")"
)
ADD_ONLY = [
    M + "contracts/shapes.py",
    M + "contracts/wire.py",
    M + "engines/colab_155/constants.py",
    M + "prompts/README.md",
    M + "tests/flows/support.py",
    M + "tests/engines/colab_155/test_purity.py",
    M + "tests/outputs/test_xlsx.py",
]
"""더하기만(^- 0). test_purity.py 는 감독 허락 Q1(이름 셋 더하기)."""
ONE_LINE = {M + "tests/contracts/test_shapes.py": 1}
"""감독 허락 Q2: 꼴 집합 한 줄."""
XLSX = M + "outputs/xlsx.py"
XLSX_MINUS = {'        _put(sheet, f"F{r}", f)', '        _put(sheet, f"G{r}", g)'}
"""1부 엑셀에서 지워도 되는 줄: F/G 칸 쓰기(잘림 표시 갈래로 바꿈)."""
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
    part1 = [f for f in paths if PART1.match(f)]
    for f in part1:
        print(f"  ★ 1부 파일이 바뀜: {f}")
    bad += len(part1)
    trees = [f for f in paths if f.startswith(FORBIDDEN_TREES)]
    for f in trees:
        print(f"  ★ core·config·generated·.importlinter: {f}")
    bad += len(trees)
    for f in ADD_ONLY:
        minus = removed_lines(f)
        if minus:
            print(f"  ★ 더하기만 파일에서 지운 줄 {len(minus)}: {f}")
            bad += 1
    for f, limit in ONE_LINE.items():
        minus = removed_lines(f)
        if len(minus) > limit:
            print(f"  ★ {f} 지운 줄 {len(minus)} > {limit}")
            bad += 1
    odd = [l for l in removed_lines(XLSX) if l not in XLSX_MINUS]
    for l in odd:
        print(f"  ★ xlsx.py 에서 잘림 갈래 밖의 지운 줄: {l.strip()[:60]}")
    bad += len(odd)
    print(
        f"  바뀐 경로 {len(paths)} · 허용 밖 {len(outside)} · 1부 {len(part1)} · core 등 {len(trees)} · "
        f"xlsx.py 지운 줄 {len(removed_lines(XLSX))}(F/G 갈래 밖 {len(odd)})"
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
TRIVIAL = {"from textwrap import dedent", "if value is None:", '"parsed": parsed,', 'if __name__ == "__main__":', "return None"}
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
    "Ticket: MARC-TICK-288",
    "Derives-from: MARC-ENT-425",
    "Concerns: MARC-ISSUE-345",
    "Constraint: 2부는 코랩 의도대로 고쳐 옮김 — 프롬프트 글 그대로, 출력 형식 절만 JSON — MARC-ENT-425",
    "Constraint: 실호출 0, 저장소에 코랩 코드 사본 0 — MARC-ENT-262, MARC-ENT-310",
    "Directive: 1부 엔진·흐름은 고치지 않는다 — 2부 상수는 engines/colab_155/part2_* 와 flows/part2_155.py 에만",
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
]
FIRST = "Directive: materiality.result@1 은 고치지 않는다 — 꼴을 바꾸면 새 판"
TITLE = re.compile(r"^(feat|fix)\(materiality\): IR2a [①②③④⑤] ")


def step9(msg):
    lines = open(msg, encoding="utf-8").read().rstrip("\n").split("\n")
    bad = 0
    if not TITLE.match(lines[0]):
        bad += 1
        print("  ★ 제목이 IR2a ①~⑤ 꼴이 아니다")
    block = []
    for line in reversed(lines):
        if not line.strip():
            break
        block.insert(0, line)
    need = TRAILERS + ([FIRST] if "IR2a ①" in lines[0] else [])
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


E = M + "engines/colab_155/"
F = M + "flows/part2_155.py"
W = M + "contracts/wire.py"
O = M + "outputs/"
T = "esgapi/materiality/tests/"
P2 = T + "flows/test_part2_155.py"
PF = T + "flows/test_part2_failures.py"
# 심은 파손: (번호, 파일, 옛 글, 새 글, 빨개져야 할 것들). 빨개질 것: ("pytest", 경로) · ("lint",) · ("s7",)
PLANTS = [
    ("P1", W, 'bundle_of_regulation(found["regulation"])', 'bundle_of_regulation(list(by_name.values())[-1]["regulation"])',
     [("pytest", T + "contracts/test_wire_part2.py"), ("pytest", P2)]),
    ("P2", E + "part2_prompts.py", '      {controversies if controversies.strip() else "제공된 컨트로버시 정보 없음"}',
     '      {str({"묶음": controversies})}', [("pytest", T + "engines/colab_155/test_part2_prompts.py"), ("s7",)]),
    ("P3", E + "part2_prompts.py", "value-chain mapping, and causal impact identification.",
     "value chain mapping, and causal impact identification.",
     [("pytest", T + "engines/colab_155/test_part2_prompts.py"), ("s7",)]),
    ("P4", E + "part2_render.py", '("Topic", "Subtopic", "영향 정의", "영향 유형", "컨트로버시/규제/정책")',
     '("Topic", "Subtopic", "영향 유형", "영향 정의", "컨트로버시/규제/정책")',
     [("pytest", T + "engines/colab_155/test_part2_render.py")]),
    ("P5", F, "        timeout_ms=TIMEOUT_MS_PART2,\n    )\n", "        timeout_ms=TIMEOUT_MS_PART2,\n        temperature=0.1,\n    )\n",
     [("pytest", P2), ("s7",)]),
    ("P6", F, '    ("impact", _impact),\n    ("financial", _financial),\n',
     '    ("financial", _financial),\n    ("impact", _impact),\n', [("pytest", P2)]),
    ("P7", F, "        spent += _cost(result)\n",
     "        if isinstance(result, CutOff):\n            result = llm.call(cast(\"Any\", request))\n        spent += _cost(result)\n",
     [("pytest", PF)]),
    ("P8", F, "    warnings += wire.truncated_warnings(calls)\n", "", [("pytest", PF)]),
    ("P9a", F, "    if spent >= inputs.max_cost_usd:\n", "    if False:\n", [("pytest", PF)]),
    ("P9b", F, '    return cast("float", carried[step].data["spentUsd"])',
     '    return 0.0 if step == SEED else cast("float", carried[step].data["spentUsd"])', [("pytest", PF)]),
    ("P10", E + "part2_parsing.py", '"impact_type": None if fin is None else fin.get("impact_type"),',
     '"impact_type": row.get("impact_type"),', [("pytest", T + "engines/colab_155/test_part2_parsing.py"), ("pytest", P2)]),
    ("P11", W, "    notes.unknown += sum(1 for a in chosen if a not in known)\n", "    notes.unknown += 0\n",
     [("pytest", T + "contracts/test_wire_part2.py"), ("pytest", P2)]),
    ("P12", O + "xlsx.py", "    return text[:keep] + mark, len(text)\n", "    return text[:CELL_LIMIT], len(text)\n",
     [("pytest", T + "outputs/test_final_xlsx.py"), ("pytest", T + "outputs/test_xlsx.py")]),
    ("P13", F, '    return cast("dict[str, Any]", json.loads(adapter.dump_json(result)))', "    return dict(result)",
     [("pytest", P2)]),
    ("P14", F, "import json\n", "import json\n\nimport django  # noqa: F401\n", [("lint",)]),
    ("P15", O + "final_xlsx.py", "enumerate(raw_json_chunks(result), 1)", "enumerate([json.dumps(result, ensure_ascii=False)], 1)",
     [("pytest", T + "outputs/test_final_xlsx.py")]),
]


def red(check, out, reading):
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")}
    if check[0] == "pytest":
        cmd = ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", check[1]]
    elif check[0] == "lint":
        cmd = ["uv", "run", "--frozen", "lint-imports"]
    else:
        cmd = ["uv", "run", "--frozen", "python", "-I", "scripts/materiality_compare_ir2a.py", reading,
               os.path.join(out, "planted-s7")]
    done = subprocess.run(cmd, cwd=API, env=env, capture_output=True, text=True)
    lines = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    if check[0] == "s7":
        tail = [l for l in lines if l.startswith("COLAB_DIFF=")][-1:] or [""]
        if not re.match(r"^COLAB_DIFF=[1-9][0-9]*$", tail[0]):
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
elif MODE == "8":
    sys.exit(step8(sys.argv[3], sys.argv[4]))
elif MODE == "9":
    sys.exit(min(step9(sys.argv[3]), 1))
PYEOF

# 1. materiality(N0 153 → N1)
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
  api uv run --frozen pyright $M scripts/materiality_compare_ir2a.py > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  api uv run --frozen ruff check $M scripts/materiality_compare_ir2a.py > "$OUT/s4-ruff.log" 2>&1 || code=1
  api uv run --frozen ruff format --check $M scripts/materiality_compare_ir2a.py >> "$OUT/s4-ruff.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s4-ruff.log")"
  python3 -I "$PY_HELPER" 4 "$BASE" || code=1
  report 4 "pyright·ruff·완화 줄" "$code"
fi

# 5. 허용 경로·1부 0줄·더하기만·xlsx.py 잘림 갈래·core 등 0줄
if want 5; then
  python3 -I "$PY_HELPER" 5 "$BASE"
  report 5 "허용 경로·1부 0줄·더하기만" $?
fi

# 6. 금지 글·키·바이너리·코랩 code 셀 줄 겹침
if want 6; then
  if reading_ok && [ -r "$FORBIDDEN" ]; then
    python3 -I "$PY_HELPER" 6 "$BASE" "$READING" "$MSG" "$MARCSPON_ROOT/band-reports/IR2a.md" "$FORBIDDEN"
    code=$?
  else
    echo "  ★ 읽기판이나 금지 글 목록을 못 읽는다"
    code=1
  fi
  report 6 "금지 글·키·바이너리·코랩 겹침" "$code"
fi

# 7. 코랩 글·읽기·요청 몸 대조(셀을 실행 때 떼어 S4_OUT 아래서만)
if want 7; then
  if reading_ok; then
    rm -rf "$OUT/s7-pieces"
    api uv run --frozen python -I scripts/materiality_compare_ir2a.py "$READING" "$OUT/s7-pieces" > "$OUT/s7-colab.log" 2>&1
    code=$?
    grep -v '^COLAB_DIFF=' "$OUT/s7-colab.log" | sed 's/^/  /' | tail -30
    grep '^COLAB_DIFF=' "$OUT/s7-colab.log" || { echo "COLAB_DIFF=없음(대조가 끝나지 않았다)"; code=1; }
    report 7 "코랩 글·읽기·요청 몸 대조" "$code"
  else
    report 7 "코랩 글·읽기·요청 몸 대조" 1
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
