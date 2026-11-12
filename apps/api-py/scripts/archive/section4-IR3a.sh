#!/usr/bin/env bash
# 밴드 IR3a(MARC-TICK-308) §4 의 자기검증. 중대성평가 IRO 흐름 전역 등록·실행기 끼움(POST /runs {module: "materiality"}
# → materiality.iro@155, 「오늘」= 실행 시각의 Asia/Seoul 날짜)을 잰다.
#   사용: apps/api-py/scripts/section4-IR3a.sh [--step <n>[,<n>…]] [--planted] [--with-containers] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드> <초>s" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0.
#   아무것도 없으면 1~9·10·12·13(10 은 --with-containers 가 없으면 「안 돌림」 EXIT=1). 11(심은 파손)은 --planted 일
#   때만 돈다 — 작업 트리의 파일을 하나씩 고쳐 쓰고 바이트째 되돌리므로(SIGTERM·예외에도 되돌린다) 같은 워크트리에서
#   다른 실행과 겹치지 않게 한 번에 하나만. 심은 파손의 업무 시험 몫은 컨테이너가 떠 있어야 빨강을 본다.
#   --msg 는 12단계가 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 없으면 HEAD 커밋 메시지).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/IR3a.out). 검증자는 S4_OUT=…/IR3a.verify 로 돌려 러너 기록을 덮지 않는다.
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 -I. LLM·네트워크·키 파일 0(공급사는 모의만).
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE="$(git merge-base main HEAD)"
OUT="${S4_OUT:-$ROOT/../IR3a.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
FORBIDDEN="$MARCSPON_ROOT/esg-app.worktrees/G1a.out/forbidden-words.txt"
API="$ROOT/apps/api-py"
M=esgapi/materiality
N0=320  # materiality 순수 시험 수(BASE d29205f9). 업무 시험은 BASE 에 0
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,8,9,10,12,13
MSG=""
CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) ONLY="$ONLY,11"; shift ;;
    --with-containers) CONTAINERS=1; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--with-containers] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
[ -n "$MSG" ] || MSG="$OUT/commit-msg.txt"

failed=0
started=0
begin() { started=$(date +%s); }
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3 $(( $(date +%s) - started ))s"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  -u ANTHROPIC_API_KEY -u GEMINI_API_KEY "$@"); }
echo "BASE=$BASE HEAD=$(git rev-parse HEAD)"

PY_HELPER="$(mktemp -t s4ir3a.XXXXXX)"
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


# §1-1·§1-3 허용 경로(닫힌 목록)
ALLOWED = re.compile(
    r"^("
    r"apps/api-py/esgapi/materiality/apps\.py"
    r"|apps/api-py/esgapi/materiality/flows/binding_155\.py"
    r"|apps/api-py/esgapi/materiality/contracts/options_shapes\.py"
    r"|apps/api-py/esgapi/materiality/tests/data/flow-shapes/options/materiality\.options@1\.schema\.json"
    r"|apps/api-py/esgapi/materiality/tests/test_apps\.py"
    r"|apps/api-py/esgapi/materiality/tests/flows/test_binding_155\.py"
    r"|apps/api-py/esgapi/materiality/tests/flows/test_runs_materiality\.py"
    r"|apps/api-py/esgapi/materiality/tests/contracts/test_options_shapes\.py"
    r"|apps/api-py/esgapi/materiality/tests/flows/support\.py"
    r"|apps/api-py/esgapi/materiality/flows/(registration|colab_155|part2_155|iro_155)\.py"
    r"|apps/api-py/esgapi/materiality/tests/flows/test_registration\.py"
    r"|apps/api-py/scripts/(section4-IR3a\.sh|materiality_compare_ir3a\.py)"
    r"|apps/api-py/esgapi/config/apps_list\.py"
    r"|apps/api-py/esgapi/config/tests/test_settings\.py"
    r"|README\.md"
    r"|docs/development\.md"
    r")$"
)
DOCSTRING_ONLY = [M + f"flows/{n}.py" for n in ("registration", "colab_155", "part2_155", "iro_155")] + [
    M + "tests/flows/test_registration.py"
]
ADD_ONLY = [M + "tests/flows/support.py"]
SHARED = {
    API + "esgapi/config/apps_list.py": (1, 0),
    API + "esgapi/config/tests/test_settings.py": (1, 0),
    "README.md": (1, 1),
    "docs/development.md": (1, 0),
}
README_MINUS = "| 중대성평가 IRO | 코드 없음 | — |"


def strip_docstrings(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(
                body[0].value.value, str
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


def step1():
    paths = changed()
    outside = [f for f in paths if not ALLOWED.match(f)]
    for f in outside:
        print(f"  ★ 허용 경로 밖: {f}")
    print(f"  바뀐 경로 {len(paths)} · outside={len(outside)}")
    return len(outside)


def step2():
    bad = 0
    for f in DOCSTRING_ONLY:
        now = open(f, encoding="utf-8").read()
        then = git("show", f"{BASE}:{f}")
        same = strip_docstrings(now) == strip_docstrings(then)
        print(f"  {f.rsplit('/', 1)[-1]}: docstring 뺀 AST 같음 {same}")
        bad += not same
    for f in ADD_ONLY:
        minus = [l for l in git("diff", "-U0", BASE, "--", f).splitlines() if l.startswith("-") and not l.startswith("---")]
        print(f"  {f.rsplit('/', 1)[-1]}: 지운 줄 {len(minus)}")
        bad += len(minus)
    return bad


def step3():
    bad = 0
    rows = {}
    for line in git("diff", "--numstat", BASE, "--", *SHARED).splitlines():
        plus, minus, path = line.split("\t")
        rows[path] = (int(plus), int(minus))
    for path, want in SHARED.items():
        got = rows.get(path, (0, 0))
        ok = got == want
        print(f"  {path}: +{got[0]}/-{got[1]} (기대 +{want[0]}/-{want[1]}) {'' if ok else '★'}")
        bad += not ok
    minus = [l[1:] for l in git("diff", "-U0", BASE, "--", "README.md").splitlines() if l.startswith("-") and not l.startswith("---")]
    ok = minus == [README_MINUS]
    print(f"  README 지운 줄 = 「중대성평가 IRO | 코드 없음」 {ok}")
    return bad + (not ok)


KEY_FILES = ("marcspon" + "-openai", "spike" + "/.env")
"""키 파일 이름(이 파일에 글자째 두면 스스로 걸린다 — 이어 짓는다)."""


def step9(msg, words_path):
    bad = 0
    words = [w.strip() for w in open(words_path, encoding="utf-8") if w.strip() and not w.startswith("#")]
    texts = {"diff ^+": added_lines(), "커밋 메시지": git("log", "--format=%B", f"{BASE}..HEAD").splitlines()}
    if os.path.isfile(msg):
        texts["메시지 초안"] = open(msg, encoding="utf-8").read().splitlines()
    key = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
    if not key.search("sk" + "-" + "A" * 20):
        print("  ★ 키 꼴 양성 대조 실패")
        bad += 1
    for name, lines in texts.items():
        w = sum(1 for l in lines if any(x in l for x in words))
        k = sum(1 for l in lines if key.search(l))
        f = sum(1 for l in lines if any(n in l for n in KEY_FILES))
        print(f"  {name}: 줄 {len(lines)} · 금지 글 {w} · 키 꼴 {k} · 키 파일 이름 {f}")
        bad += w + k + f
    print(f"  금지 글 {len(words)}개")
    exts = [f for f in changed() if re.search(r"\.(xlsx|csv|ipynb)$", f)]
    binary = [f for f in changed() if os.path.isfile(f) and b"\0" in open(f, "rb").read()]
    print(f"  xlsx·csv·ipynb 경로 {len(exts)} · 바이너리 {len(binary)}")
    return bad + len(exts) + len(binary)


TRAILERS = [
    "Ticket: MARC-TICK-308",
    "Derives-from: MARC-ENT-439",
    "Constraint: 실호출 0 — 실행기는 모의 공급사만 — MARC-ENT-262",
    "Constraint: 흐름·엔진·계약·core·runs 0줄 — 이어 돌기의 중간 단계 파일은 실행기가 이미 저장·옮김",
    "Directive: 「오늘」은 binding_155.clock() 하나에서만 읽는다 — 흐름(iro_155)은 시계를 읽지 않는다",
    "Directive: RUN_MAX_COST_USD 는 실호출을 켜는 밴드에서 다시 정한다",
]
TITLE = "feat(materiality): IR3a 흐름 전역 등록·실행기 끼움 — "


def step12(msg):
    lines = open(msg, encoding="utf-8").read().rstrip("\n").split("\n")
    bad = 0
    if not lines[0].startswith(TITLE):
        bad += 1
        print("  ★ 제목이 IR3a 꼴이 아니다")
    block = []
    for line in reversed(lines):
        if not line.strip():
            break
        block.insert(0, line)
    missing = [t for t in TRAILERS if t not in block]
    for t in missing:
        print(f"  ★ 트레일러 없음: {t[:40]}")
    loose = [l for l in block if not re.match(r"^[A-Z][A-Za-z-]+: ", l)]
    if not (block and block[-1].startswith("Co-Authored-By: ")):
        bad += 1
        print("  ★ 끝 줄이 Co-Authored-By 가 아니다")
    print(f"  제목 줄 {len(lines[0])}자 · 끝 문단 {len(block)}줄 · 빠진 트레일러 {len(missing)} · 트레일러 꼴 아닌 줄 {len(loose)}")
    return bad + len(missing) + len(loose)


B = M + "flows/binding_155.py"
O = M + "contracts/options_shapes.py"
A = M + "apps.py"
T = "esgapi/materiality/tests/"
TB = T + "flows/test_binding_155.py"
TA = T + "test_apps.py"
TR = T + "flows/test_runs_materiality.py"
# 심은 파손: (번호, 파일, [(옛 글, 새 글)], 빨개져야 할 것들). 빨개질 것: ("pytest", 경로) · ("biz", -k 식)
PLANTS = [
    ("P1", O, [("@with_config(FORBID)\nclass MaterialityOptions", "class MaterialityOptions")],
     [("pytest", TB), ("biz", "do_not_fit")]),
    ("P2", B, [("        accepted = OPTIONS_SHAPES[SHAPE].validate_python(options, strict=True)\n",
                '        accepted = cast("MaterialityOptions", options)\n')],
     [("pytest", TB)]),
    ("P3", B, [("    return clock().astimezone(SEOUL).date()", "    return clock().date()")],
     [("pytest", TB), ("biz", "seoul_date")]),
    ("P4", B, [("    return clock().astimezone(SEOUL).date()", "    return date.today()")], [("pytest", TB)]),
    ("P5", B, [("RUN_MAX_COST_USD: Final = 5.0", "RUN_MAX_COST_USD: Final = 50.0")], [("pytest", TB)]),
    ("P6", B, [("tags=Tags(tenant=str(company_id), module=MODULE)", 'tags=Tags(tenant=str(company_id), module="dataverify")')],
     [("pytest", TB), ("biz", "company_tags")]),
    ("P7", A, [("        BINDINGS.register_documentless(\n", "        (lambda *args, **kwargs: None)(\n")],
     [("pytest", TA), ("biz", "to_done")]),
    ("P8", A, [("        if self.apps is not global_apps:\n            return\n", "")], [("pytest", TA)]),
    ("P9", A, [("        BINDINGS.register_documentless(\n", "        BINDINGS.register(\n")],
     [("pytest", TA), ("biz", "to_done")]),
    ("P10", A, [("MaterialityBinding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS", "MaterialityBinding()")],
     [("pytest", TA), ("biz", "20kib")]),
    ("P11", B, [('"promptIds": {**colab_155.PROMPT_IDS, **part2_155.PROMPT_IDS2},', '"promptIds": {**colab_155.PROMPT_IDS},')],
     [("pytest", TB), ("biz", "with_the_versions")]),
    ("P12", B, [('raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요") from None',
                 'raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요: {str(options)[-24:]}") from None')],
     [("pytest", TB)]),
    ("P13", B, [('    if wire.parse_date_range(accepted["input"]["dateRange"], day) is None:', "    if False:")],
     [("pytest", TB), ("biz", "do_not_fit")]),
    ("P14", B, [('        received = cast("Mapping[str, Any]", options["input"])',
                 '        received = cast("Mapping[str, Any]", _accept(options, day)["input"])')],
     [("pytest", TB), ("biz", "same_request_bodies")]),
    ("P15", B, [("        return IroAdapters(llm=ctx.llm())",
                 "        return IroAdapters(llm=__import__('esgapi.materiality.tests.flows.support', fromlist=['x'])"
                 ".real_client(__import__('esgapi.core.llm.providers.mock', fromlist=['x']).MockProvider('openai')))")],
     [("biz", "company_tags")]),
    ("P16", A, [("        from esgapi.materiality.flows import iro_155, registration\n",
                 "        from esgapi.materiality.flows import colab_155, iro_155, registration\n"),
                ("            iro_155.FLOW_ID, MaterialityBinding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS\n        )\n",
                 "            iro_155.FLOW_ID, MaterialityBinding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS\n        )\n"
                 "        BINDINGS.register_documentless(colab_155.FLOW_ID, MaterialityBinding())\n")],
     [("pytest", TA), ("biz", "part1_flow_alone")]),
    # 러너 몫: 열쇠 길에 목록 자리 수가 섞임(input.topics.0.description — 받은 값의 꼴이 문장에 샌다)
    ("P17", B, [("    return \".\".join(part for part in loc if isinstance(part, str))", "    return \".\".join(str(part) for part in loc)")],
     [("pytest", TB)]),
]


def red(check):
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")}
    if check[0] == "pytest":
        cmd = ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", check[1]]
    else:
        cmd = ["scripts/test-business.sh", TR, "-p", "no:cacheprovider", "-k", check[1]]
    done = subprocess.run(cmd, cwd=API, env=env, capture_output=True, text=True)
    lines = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    fails = [l for l in lines if l.startswith(("FAILED", "ERROR"))]
    ran = any(re.search(r"\b[0-9]+ (passed|failed|error)", l) for l in lines)
    return done.returncode != 0 and ran, (fails[:1] or lines[-1:] or [""])[0][:110]


class Stop(Exception):
    pass


def _stop(signum, frame):
    raise Stop()


def step11():
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
                is_red, tail = red(check)
                where = check[1].rsplit("/", 1)[-1]
                print(f"  {name} → {check[0]} {where} {'빨강' if is_red else '★ 초록'} · {tail}")
                ok = ok and is_red
        finally:
            open(path, "wb").write(original)
        if open(path, "rb").read() != original:
            print(f"  ★ {name}: 되돌리기 실패 {path}")
            ok = False
        caught += ok
    print(f"PLANTED={caught}/{len(PLANTS)}")
    return int(caught != len(PLANTS))


if MODE == "1":
    sys.exit(min(step1(), 1))
elif MODE == "2":
    sys.exit(min(step2(), 1))
elif MODE == "3":
    sys.exit(min(step3(), 1))
elif MODE == "9":
    sys.exit(min(step9(sys.argv[3], sys.argv[4]), 1))
elif MODE == "11":
    sys.exit(step11())
elif MODE == "12":
    sys.exit(min(step12(sys.argv[3]), 1))
PYEOF

# 1. 바뀐 경로가 §1-1·§1-3 안
if want 1; then
  begin
  python3 -I "$PY_HELPER" 1 "$BASE"
  report 1 "허용 경로(outside=0)" $?
fi

# 2. §1-2 0줄(1 이 닫힌 목록으로 본다) · docstring 만인 다섯은 docstring 뺀 AST = BASE · support.py 더하기만
if want 2; then
  begin
  python3 -I "$PY_HELPER" 2 "$BASE"
  report 2 "docstring 만·더하기만" $?
fi

# 3. 공통 줄 numstat(+1·+1·+1/−1·+1)과 README 의 지운 줄
if want 3; then
  begin
  python3 -I "$PY_HELPER" 3 "$BASE"
  report 3 "공통 줄 numstat" $?
fi

# 4. import 계약 전부 KEPT, 계약 수 = BASE 의 .importlinter
if want 4; then
  begin
  api uv run --frozen lint-imports > "$OUT/s4-lint.log" 2>&1
  code=$?
  n=$(git show "$BASE:apps/api-py/.importlinter" | grep -c '^\[importlinter:contract')
  got=$(grep 'Contracts:' "$OUT/s4-lint.log")
  echo "  $got · BASE 계약 $n"
  if [ "$got" != "Contracts: $n kept, 0 broken." ]; then code=1; fi
  report 4 "lint-imports" "$code"
fi

# 5. materiality 순수(N0 → N1, 늘기만) + 이름 목록 시험 셋
if want 5; then
  begin
  api uv run --frozen pytest -q -p no:cacheprovider $M -m "not django_db" > "$OUT/s5-pytest.log" 2>&1
  code=$?
  passed=$(tail -1 "$OUT/s5-pytest.log" | sed -n -E 's/^([0-9]+) passed.*/\1/p')
  echo "  materiality 순수: $(tail -1 "$OUT/s5-pytest.log") · N0 $N0"
  if [ -z "$passed" ] || [ "$passed" -le "$N0" ]; then code=1; fi
  api uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_settings.py \
    esgapi/core/tests/test_flows_core_names.py esgapi/runs/tests/test_names.py > "$OUT/s5-names.log" 2>&1 || code=1
  echo "  이름 목록: $(tail -1 "$OUT/s5-names.log")"
  report 5 "pytest 순수·이름 목록" "$code"
fi

# 6. 고정 스키마 넷: options@1 은 다시 뽑아 cmp, input@1·result@1·result@2 는 BASE 와 같음
if want 6; then
  begin
  code=0
  pinned="$M/tests/data/flow-shapes/options/materiality.options@1.schema.json"
  api uv run --frozen python -I -c "import json; from esgapi.materiality.contracts import options_shapes as o; \
print(json.dumps(o.OPTIONS_SHAPES[o.SHAPE].json_schema(), ensure_ascii=False, indent=2))" > "$OUT/s6-options.json" || code=1
  cmp "$OUT/s6-options.json" "$API/$pinned" || code=1
  for s in input@1 result@1 result@2; do
    git diff --quiet "$BASE" -- "apps/api-py/$M/tests/data/flow-shapes/materiality.$s.schema.json" || { echo "  ★ $s 가 바뀜"; code=1; }
  done
  echo "  options@1 다시 뽑음 cmp · input@1·result@1·result@2 = BASE"
  report 6 "고정 스키마 넷" "$code"
fi

# 7. generated/ 0바이트 차이
if want 7; then
  begin
  (cd "$API" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" env -u OPENAI_API_KEY scripts/gen-ts-types.sh) > "$OUT/s7-gen.log" 2>&1
  code=$?
  git diff --quiet -- apps/api-py/generated || code=1
  echo "  generated 차이 $(git diff --numstat -- apps/api-py/generated | wc -l | tr -d ' ') 파일"
  report 7 "gen-ts-types 뒤 generated 0바이트" "$code"
fi

# 8. 시험 자리·pyright·ruff
if want 8; then
  begin
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s8-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s8-layout.log")"
  api uv run --frozen pyright $M scripts/materiality_compare_ir3a.py > "$OUT/s8-pyright.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s8-pyright.log")"
  api uv run --frozen ruff check $M esgapi/config scripts/materiality_compare_ir3a.py > "$OUT/s8-ruff.log" 2>&1 || code=1
  api uv run --frozen ruff format --check $M esgapi/config scripts/materiality_compare_ir3a.py >> "$OUT/s8-ruff.log" 2>&1 || code=1
  echo "  $(tail -1 "$OUT/s8-ruff.log")"
  report 8 "check_test_layout·pyright·ruff" "$code"
fi

# 9. 금지 글·키·확장자·바이너리
if want 9; then
  begin
  if [ -r "$FORBIDDEN" ]; then
    python3 -I "$PY_HELPER" 9 "$BASE" "$MSG" "$FORBIDDEN"
    code=$?
  else
    echo "  ★ 금지 글 목록을 못 읽는다"
    code=1
  fi
  report 9 "금지 글·키·바이너리" "$code"
fi

# 10. 업무 층(컨테이너) — 회귀 모듈 일곱·보안 층 + EXEC_SAME·RESUME_SAME
if want 10; then
  begin
  if [ "$CONTAINERS" = 1 ]; then
    api scripts/test-business.sh -p no:cacheprovider esgapi/materiality esgapi/runs esgapi/config esgapi/core \
      esgapi/dataverify esgapi/greenwash esgapi/translation > "$OUT/s10-business.log" 2>&1
    code=$?
    echo "  업무: $(tail -1 "$OUT/s10-business.log")"
    api scripts/test-security.sh -p no:cacheprovider > "$OUT/s10-security.log" 2>&1 || code=1
    echo "  보안: $(tail -1 "$OUT/s10-security.log")"
    api uv run --frozen python -I scripts/materiality_compare_ir3a.py "$OUT" > "$OUT/s10-compare.log" 2>&1 || code=1
    sed 's/^/  /' "$OUT/s10-compare.log" | grep -v '^  EXEC_SAME='
    grep '^EXEC_SAME=' "$OUT/s10-compare.log" || { echo "EXEC_SAME=없음"; code=1; }
  else
    echo "  안 돌림(--with-containers 없음)"
    code=1
  fi
  report 10 "업무·보안·대조" "$code"
fi

# 11. 심은 파손(--planted)
if want 11; then
  begin
  before=$(git status --porcelain)
  python3 -I "$PY_HELPER" 11 "$BASE" > "$OUT/s11-planted.log" 2>&1
  code=$?
  sed 's/^/  /' "$OUT/s11-planted.log" | grep -v '^  PLANTED='
  grep '^PLANTED=' "$OUT/s11-planted.log"
  if [ "$(git status --porcelain)" != "$before" ]; then code=1; echo "  ★ 심은 파손 뒤 작업 트리가 달라졌다"; fi
  report 11 "심은 파손" "$code"
fi

# 12. 커밋 메시지 트레일러
if want 12; then
  begin
  if [ -f "$MSG" ]; then
    python3 -I "$PY_HELPER" 12 "$BASE" "$MSG"
    report 12 "트레일러($MSG)" $?
  else
    git log -1 --format=%B HEAD > "$OUT/s12-head-msg.txt"
    echo "  메시지 초안이 없어 HEAD 커밋 메시지를 본다"
    python3 -I "$PY_HELPER" 12 "$BASE" "$OUT/s12-head-msg.txt"
    report 12 "트레일러(HEAD)" $?
  fi
fi

# 13. 빠른 게이트(뿌리에서)
if want 13; then
  begin
  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast > "$OUT/s13-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s13-verify-fast.log")
  secs=$(( $(date +%s) - started ))
  echo "  $last · ${secs}초"
  if [ "$secs" -gt 30 ]; then echo "  uptime: $(uptime)"; fi
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 13 "scripts/verify.sh --fast" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
