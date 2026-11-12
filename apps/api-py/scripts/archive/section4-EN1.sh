#!/usr/bin/env bash
# 밴드 EN1 의 §4 자기검증(발주서 band-handoffs/EN1-order.md §4). 줄마다 [n] … EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-EN1.sh                         전부(경계 3 = 커밋 ③ 뒤)
#   apps/api-py/scripts/section4-EN1.sh --boundary 1 --step 1,3  일부. 경계(1·2·3)가 시험 수·계약 수·낡은 글 검사를 고른다
#
# 환경 변수:
#   EN1_BASE   기준 커밋(기본: 워크트리를 만든 main e973637 = GX1 병합)
#   EN1_OUT    산출물 자리(기본: 워크트리 곁의 EN1.out). collect-base.txt·bodies-before/ 가 여기 있어야 한다
#   EN1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(15 가 BASE..HEAD 의 메시지와 함께 본다)
# 커밋 ① 은 제목의 「EN1 ①」로 찾는다. 아직 없으면(커밋 전) 5·6 은 스테이징된 트리(index)를 잰다.
# 2·8 은 Postgres 가 떠 있어야 한다(scripts/worktree-env.sh EN1 → docker compose up -d --wait postgres). 컨테이너를 띄우지 않는다.
# 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${EN1_BASE:-e9736373593386d4c2fcefdd27e5ec2ad05600dc}"
OUT="${EN1_OUT:-$SIDE/EN1.out}"
S4="$OUT/section4"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

STEPS="all"
BOUNDARY=3
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --boundary) BOUNDARY="${2:?--boundary 뒤에 1~3}"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
case "$BOUNDARY" in 1|2|3) ;; *) echo "--boundary 는 1~3"; exit 2 ;; esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

C1="$(git -C "$ROOT" log --format=%H --grep='EN1 ①' "$BASE..HEAD" | tail -1)"
echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD) C1=${C1:-<index>} BOUNDARY=$BOUNDARY"

# 기준 트리(BASE 의 apps/api-py)를 한 번 풀어 둔다 — 5·7·9·10 이 쓴다. git worktree 를 쓰지 않는다.
BASETREE="$S4/base-tree"
if [ ! -f "$BASETREE/.base-$BASE" ]; then
  rm -rf "$BASETREE"; mkdir -p "$BASETREE"
  git -C "$ROOT" archive "$BASE" apps/api-py | tar -x -C "$BASETREE"
  # check_test_layout.py 가 git ls-files 로 시험 파일을 모으므로 풀어 둔 트리에 따로 git 을 하나 둔다(저장소 밖, 산출물 자리).
  (cd "$BASETREE" && git init -q && git add -A && git -c user.name=en1 -c user.email=en1@local commit -q -m base)
  : > "$BASETREE/.base-$BASE"
fi
BASE_API="$BASETREE/apps/api-py"

HELPER="$S4/en1_helper.py"
cat > "$HELPER" <<'PY'
import ast
import io
import re
import subprocess
import sys
import tokenize
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
C1 = sys.argv[3]  # 커밋 ① 의 해시, 없으면 "" (스테이징된 트리)
CMD = sys.argv[4]
ARGS = sys.argv[5:]
API = ROOT / "apps/api-py"
INV = "apps/api-py/esgapi/inventory/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


# §2-1 의 git mv 38건(옛 → 새, inventory 안의 상대 경로)
S12 = ["__init__", "activity", "aggregate", "calc", "provenance", "serialize", "tables", "types", "units"]
S3 = ["__init__", "calc", "catalog", "lexical_v1", "llm_steps", "memory", "normalize", "pipeline", "ports",
      "ranking", "review", "serialize", "shortlister", "types", "units"]
SHEETS = ["__init__", "crosscheck", "dropdowns", "factor_layout", "factors", "grid"]
MOVES = (
    [(f"calc/{n}.py", f"engines/scope12/engine_1/{n}.py") for n in S12]
    + [(f"calc/scope3/{n}.py", f"engines/scope3/llm_first_1/{n}.py") for n in S3]
    + [("calc/jsrepr.py", "tools/jsrepr.py"), ("xlsx_reader.py", "tools/xlsx_reader.py")]
    + [(f"calc/scope3_sheets/{n}.py", f"tools/scope3_sheets/{n}.py") for n in SHEETS]
    + [("flows/shapes.py", "contracts/shapes.py"), ("flows/scope12.py", "flows/scope12_engine_1.py"),
       ("flows/scope3.py", "flows/scope3_llm_first_1.py"),
       ("tests/calc/test_calc.py", "tests/engines/scope12/engine_1/test_calc.py"),
       ("tests/calc/scope3/test_pipeline.py", "tests/engines/scope3/llm_first_1/test_pipeline.py"),
       ("tests/flows/test_shapes.py", "tests/contracts/test_shapes.py")]
)
OLD_MODS = ("esgapi.inventory.calc", "esgapi.inventory.flows.shapes", "esgapi.inventory.flows.scope12",
            "esgapi.inventory.flows.scope3", "esgapi.inventory.xlsx_reader", "esgapi.inventory.tests.calc")
VOCAB = "esgapi/inventory/tests/flows/test_vocab.py"


def is_old(mod: str) -> bool:
    return any(mod == o or mod.startswith(o + ".") for o in OLD_MODS)


def import_lines(src: str) -> set[int]:
    lines: set[int] = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            lines.update(range(n.lineno, n.end_lineno + 1))
    return lines


def old_imports(src: str) -> list[str]:
    hits = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            for a in n.names:
                for m in (n.module, f"{n.module}.{a.name}"):
                    if is_old(m):
                        hits.append(f"{n.lineno}: from {n.module} import {a.name}")
                        break
        elif isinstance(n, ast.Import):
            hits += [f"{n.lineno}: import {a.name}" for a in n.names if is_old(a.name)]
    return hits


def scan_paths(tree: str) -> list[str]:
    """§4-4 의 범위: esgapi/**/*.py · scripts/*.py(archive 밖) · tests/**/*.py. tree 는 "" (작업 트리) 또는 커밋."""
    if tree:
        names = git("ls-tree", "-r", "--name-only", tree, "--", "apps/api-py").split()
    else:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "--", "apps/api-py").split()
    out = []
    for p in names:
        r = p[len("apps/api-py/"):]
        if not r.endswith(".py"):
            continue
        if r.startswith("esgapi/") or r.startswith("tests/") or (r.startswith("scripts/") and r.count("/") == 1):
            out.append(p)
    return out


def read(tree: str, p: str) -> str | None:
    if tree:
        return git("show", f"{tree}:{p}")
    f = ROOT / p
    return f.read_text(encoding="utf-8") if f.exists() else None


# 앞이 `esgapi/inventory/` 인 전체 경로도 낡은 글이다(`tools/xlsx_reader.py` 같은 새 자리는 앞이 `tools/` 라 걸리지 않는다).
STALE = re.compile(r"(?:(?<![\w./-])|(?<=esgapi/inventory/))(calc/|tests/calc/|scope3_sheets/|xlsx_reader\.py|flows/(shapes|scope12|scope3)\.py)")
# prompts/ 는 바이트 0(발주서 §1-2)이라 낡은 글도 남긴다(prompts/README.md:14 의 `calc/scope3/llm_steps.py` 한 줄).
STALE_SKIP = ("tests/data/", "data/", "prompts/", "tests/planted-breaks-PY4.sh", "tests/planted-breaks-PY7.sh")
# 낡은 글이 아니라 코드인 글자열 토큰: 경로 조각(tests/s3sheets_probe.py 의 inventory / "tools" / "xlsx_reader.py")
STALE_CODE_TOKENS = {'"xlsx_reader.py"'}


def stale_lines(tree: str) -> list[str]:
    """§2-3 ③ 의 낡은 경로 글. inventory 안, .py 는 COMMENT·STRING 토큰만, .md·.sh 는 줄 전체."""
    if tree:
        names = git("ls-tree", "-r", "--name-only", tree, "--", INV).split()
    else:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "--", INV).split()
    hits = []
    for p in names:
        r = p[len(INV):]
        if r.startswith(STALE_SKIP) or not r.endswith((".py", ".md", ".sh")):
            continue
        src = read(tree, p)
        if src is None:
            continue
        if r.endswith(".py"):
            seen = set()
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING) and tok.string not in STALE_CODE_TOKENS:
                    for i, line in enumerate(tok.string.splitlines(), start=tok.start[0]):
                        if STALE.search(line) and i not in seen:
                            seen.add(i)
                            hits.append(f"{p}:{i}")
        else:
            hits += [f"{p}:{i}" for i, line in enumerate(src.splitlines(), 1) if STALE.search(line)]
    return hits


def cmd_oldpaths() -> int:
    tree = ARGS[0] if ARGS else ""
    hits = []
    for p in scan_paths(tree):
        src = read(tree, p)
        if src is None:
            continue
        try:
            hits += [f"{p}:{h}" for h in old_imports(src)]
        except SyntaxError:
            print(f"구문 오류(건너뜀): {p}")
    for h in hits[:20]:
        print("  ", h)
    print(f"OLD_IMPORTS={len(hits)}")
    return 0


def cmd_stale() -> int:
    tree = ARGS[0] if ARGS else ""
    hits = stale_lines(tree)
    for h in hits[:60]:
        print("  ", h)
    print(f"STALE_LINES={len(hits)} FILES={len({h.rsplit(':', 1)[0] for h in hits})}")
    return 0


def cmd_collect() -> int:
    """3: BASE 의 node id 를 §2-1 대응으로 옮긴 묶음이 지금 것(test_vocab 뺌)과 같은가. 대응표를 쓴다."""
    base_file, now_file, expect, map_out = ARGS
    def ids(f: str) -> list[str]:
        return [x.strip() for x in Path(f).read_text(encoding="utf-8").splitlines() if "::" in x]
    base, now = ids(base_file), ids(now_file)
    tmap = {f"esgapi/inventory/{o}": f"esgapi/inventory/{n}" for o, n in MOVES if o.startswith("tests/")}
    mapped = []
    lines = []
    for i in base:
        path, rest = i.split("::", 1)
        new = tmap.get(path, path) + "::" + rest
        mapped.append(new)
        if new != i:
            lines.append(f"{i}\t{new}")
    Path(map_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    vocab = [i for i in now if i.startswith(VOCAB + "::")]
    rest_now = [i for i in now if not i.startswith(VOCAB + "::")]
    ok = True
    print(f"수: BASE {len(base)} · 지금 {len(now)}(test_vocab {len(vocab)}) · 기대 {expect}")
    ok &= len(now) == int(expect)
    names_base = Counter(i.split("::")[-1] for i in base)
    names_now = Counter(i.split("::")[-1] for i in rest_now)
    print(f"이름 묶음 같음: {names_base == names_now}")
    ok &= names_base == names_now
    same = Counter(mapped) == Counter(rest_now)
    print(f"옛→새 node id 대응이 지금 묶음과 같음: {same} (옮긴 node {len(lines)} · 대응표 {map_out})")
    ok &= same
    if not same:
        for x in sorted((Counter(mapped) - Counter(rest_now)).elements())[:10]:
            print("   BASE 에만:", x)
        for x in sorted((Counter(rest_now) - Counter(mapped)).elements())[:10]:
            print("   지금에만:", x)
    for v in vocab:
        print("   새:", v)
    return 0 if ok else 1


# §4-5 의 열거한 줄(파일, 줄 안에 있어야 하는 글자). 줄 번호가 밀리므로 글자로 고른다.
ENUMERATED = [
    ("apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py", '"esgapi.inventory.'),
    ("apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py", "root = Path(xlsx_reader.__file__).parents["),
    ("apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py", "assert opening == ["),
    ("apps/api-py/esgapi/inventory/tests/s3sheets_probe.py", 'inventory / "'),
    ("apps/api-py/esgapi/inventory/tests/test_flows.py", "assert {p.name for p in files} >= {"),
    ("apps/api-py/esgapi/core/tests/test_transaction_rules.py", "pipeline.py:call"),
    ("apps/api-py/esgapi/core/tests/test_transaction_rules.py", "# Scope 3 분류 호출(밴드 CU1 이 업무 층에서 classify_group 으로 옮김)"),
    ("apps/api-py/scripts/planted-breaks.sh", 'append esgapi/reference/service/services/reference.py "from esgapi.inventory.'),
    ("apps/api-py/.importlinter", "    esgapi.inventory.engines"),
    ("apps/api-py/.importlinter", "    esgapi.inventory.contracts"),
    ("apps/api-py/.importlinter", "    esgapi.inventory.tools"),
    ("apps/api-py/.importlinter", ";    esgapi.*.calc 는 모듈마다의 calc 패키지와 그 아래 전부다(지금 있는 것은 "),
    ("apps/api-py/.importlinter", ";    inventory 의 엔진·계약·도구는 calc 가 아니라 engines·contracts·tools 라(밴드 EN1)"),
]
BAND_SCRIPTS = ("apps/api-py/scripts/section4-EN1.sh", "apps/api-py/scripts/planted-breaks-EN1.sh")


def cmd_linekinds() -> int:
    """5: 커밋 ① 의 바뀐 줄이 import 줄 ∪ 열거한 줄 ∪ 새 __init__ docstring ∪ (import 사이의) 빈 줄 밖 0 인가."""
    rng = [BASE, C1] if C1 else ["--cached", BASE]
    diff = git("diff", "-M", "-U0", "--no-color", *rng)
    old_tree, new_tree = BASE, (C1 or "")
    cache: dict[tuple[str, str], tuple[set[int], list[str]] | None] = {}

    def info(tree: str, p: str):
        k = (tree, p)
        if k not in cache:
            try:
                src = git("show", f"{tree}:{p}") if tree else git("show", f":{p}")
            except subprocess.CalledProcessError:
                cache[k] = None
                return None
            imp = import_lines(src) if p.endswith(".py") else set()
            cache[k] = (imp, src.splitlines())
        return cache[k]

    kinds = Counter()
    bad = []
    a_path = b_path = None
    a_ln = b_ln = 0
    new_file = False
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            a_path = b_path = None
            new_file = False
            continue
        if line.startswith("new file mode"):
            new_file = True
        if line.startswith("--- "):
            a_path = None if line[4:] == "/dev/null" else line[6:]
            continue
        if line.startswith("+++ "):
            b_path = None if line[4:] == "/dev/null" else line[6:]
            continue
        m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            a_ln, b_ln = int(m.group(1)), int(m.group(2))
            continue
        if not line or line[0] not in "+-" or line.startswith(("+++", "---")):
            continue
        sign, text = line[0], line[1:]
        path = a_path if sign == "-" else b_path
        tree = old_tree if sign == "-" else new_tree
        ln = a_ln if sign == "-" else b_ln
        if sign == "-":
            a_ln += 1
        else:
            b_ln += 1
        if path in BAND_SCRIPTS:
            kinds["밴드 스크립트(새 파일)"] += 1
            continue
        got = info(tree, path) if path else None
        if got and ln in got[0]:
            kinds["import 줄"] += 1
        elif any(path == f and s in text for f, s in ENUMERATED):
            kinds["열거한 줄"] += 1
        elif sign == "+" and path and path.endswith("/__init__.py") and text.startswith('"""') and text.endswith('"""'):
            kinds["새 __init__ docstring"] += 1
        elif text.strip() == "":
            kinds["빈 줄"] += 1
        else:
            bad.append(f"{sign}{path}:{ln}: {text[:100]}")
    for k, v in sorted(kinds.items()):
        print(f"   {k}: {v}")
    for b in bad[:30]:
        print("   ★ 밖:", b)
    print(f"LINES_OUTSIDE={len(bad)}")
    return 0 if not bad else 1


def cmd_renames() -> int:
    """6: §2-1 의 38건이 R 인가. R090 밑은 수와 까닭을 찍는다(빈 __init__ 은 git 이 R 로 못 잇는다)."""
    rng = [BASE, C1] if C1 else ["--cached", BASE]
    out = git("diff", "-M", "--name-status", *rng, "--", INV)
    status = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if parts[0].startswith("R"):
            status[(parts[1][len(INV):], parts[2][len(INV):])] = parts[0]
        else:
            status.setdefault(("?", parts[-1][len(INV):]), parts[0])
    fails = 0
    low = []
    for o, n in MOVES:
        s = status.get((o, n))
        if s is None:
            empty = git("show", f"{BASE}:{INV}{o}") == ""
            print(f"   R 아님: {o} → {n}" + ("  (옛 파일이 빈 파일 — git 은 빈 파일의 이름 바꿈을 잇지 않는다)" if empty else ""))
            if not empty:
                fails += 1
            continue
        if int(s[1:]) < 90:
            if o.rsplit("/", 1)[-1] == n.rsplit("/", 1)[-1]:
                low.append(f"{s} {o} → {n}")
            else:
                print(f"   R090 밑(이름이 바뀐 이동이라 R090 조건 밖 — import 줄이 몸의 큰 몫): {s} {o} → {n}")
    print(f"   R 인 것: {sum(1 for o, n in MOVES if (o, n) in status)}/{len(MOVES)}")
    for x in low:
        print("   R090 밑:", x)
    fails += len(low)
    head = git("diff", "-M", "--name-status", BASE, "HEAD", "--", INV + "contracts/shapes.py", INV + "flows/shapes.py")
    print("   HEAD 의 contracts/shapes.py(따로 적음):", " ".join(head.split()) or "(BASE..HEAD 에 아직 없음)")
    return 0 if fails == 0 else 1


def cmd_surface() -> int:
    """9: 표면(service/**·api.py·apps.py) → 엔진(BASE 는 calc·calc.scope3, 지금은 engines) import 문의 수."""
    tree = ARGS[0] if ARGS else ""
    if tree:
        names = git("ls-tree", "-r", "--name-only", tree, "--", INV).split()
    else:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "--", INV).split()
    eng_base = ("esgapi.inventory.calc",)
    tools_base = ("esgapi.inventory.calc.jsrepr", "esgapi.inventory.calc.scope3_sheets")
    count = Counter()
    for p in names:
        r = p[len(INV):]
        if not (r.startswith("service/") or r in ("api.py", "apps.py")) or not r.endswith(".py"):
            continue
        for n in ast.walk(ast.parse(read(tree, p) or "")):
            mods = []
            if isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module]
            elif isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            for m in mods:
                if m == "esgapi.inventory.data_loader":
                    count["data_loader"] += 1
                    continue
                if tree:
                    hit = m.startswith(eng_base) and not m.startswith(tools_base)
                else:
                    hit = m.startswith("esgapi.inventory.engines")
                if hit:
                    count[r.split("/")[1] if r.startswith("service/") else r] += 1
    print(f"   {dict(sorted(count.items()))}")
    print(f"SURFACE_ENGINE_IMPORTS={sum(v for k, v in count.items() if k != 'data_loader')}"
          f" WITH_DATA_LOADER={sum(count.values())}")
    return 0


sys.exit({"oldpaths": cmd_oldpaths, "stale": cmd_stale, "collect": cmd_collect, "linekinds": cmd_linekinds,
          "renames": cmd_renames, "surface": cmd_surface}[CMD]())
PY
helper() { (cd "$API_PY" && uv run --frozen python "$HELPER" "$ROOT" "$BASE" "${C1:-}" "$@"); }

# ── 1. 순수 층 ──
if want 1; then
  api pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$S4/1-pure.txt" 2>&1
  rc=$?; tail -1 "$S4/1-pure.txt"; report 1 "순수 층(esgapi 전 모듈)" "$rc"
fi

# ── 2. 업무·보안 층(Postgres 하나) ──
if want 2; then
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/inventory \
    esgapi/core/tests/test_transaction_rules.py) > "$S4/2-business.txt" 2>&1
  rc1=$?; tail -1 "$S4/2-business.txt"
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider \
    tests/security/test_request_transactions.py) > "$S4/2-security.txt" 2>&1
  rc2=$?; tail -1 "$S4/2-security.txt"
  report 2 "업무 층(inventory + test_transaction_rules) · 보안 층(test_request_transactions)" "$((rc1 + rc2))"
fi

# ── 3. 시험 수·이름 ──
if want 3; then
  if [ "$BOUNDARY" -ge 2 ]; then expect=886; else expect=869; fi
  api pytest --collect-only -q -p no:cacheprovider esgapi/inventory > "$S4/3-collect-now.txt" 2>&1
  helper collect "$OUT/collect-base.txt" "$S4/3-collect-now.txt" "$expect" "$OUT/node-map.txt"
  report 3 "시험 수 $expect · 이름 묶음 · 옛→새 node id 대응" "$?"
fi

# ── 4. 옛 경로 0 ──
if want 4; then
  rc=0
  echo "  BASE(양성 대조):"; helper oldpaths "$BASE" | tail -1 | sed 's/^/    /'
  base_n="$(helper oldpaths "$BASE" | sed -n 's/^OLD_IMPORTS=//p')"
  [ "${base_n:-0}" -gt 0 ] || { echo "  ★ 양성 대조가 0 — 검사가 아무것도 물지 못한다"; rc=1; }
  echo "  지금:"; now="$(helper oldpaths)"; printf '%s\n' "$now" | sed 's/^/    /'
  printf '%s\n' "$now" | grep -qx 'OLD_IMPORTS=0' || rc=1
  closed=":!apps/api-py/scripts/archive"
  # 파이프 끝의 상태만 남으므로 git grep 의 종료 코드는 따로 받는다(0 맞음 · 1 없음 · 2 이상 실패).
  g="$({ git -C "$ROOT" grep -n -P 'esgapi\.inventory\.(calc|xlsx_reader|flows\.(shapes|scope12|scope3)\b)' -- . "$closed" \
    ':!apps/api-py/scripts/section4-S3a.sh' ':!apps/api-py/scripts/planted-breaks-S3a.sh' \
    ':!apps/api-py/scripts/section4-UT1.sh' ':!apps/api-py/scripts/planted-breaks-UT1.sh' \
    ':!apps/api-py/scripts/section4-PY8c.sh' ':!apps/api-py/scripts/planted-breaks-PY8c.sh' \
    ':!apps/api-py/scripts/section4-RR1.sh' ':!apps/api-py/scripts/planted-breaks-RR1.sh' \
    ':!apps/api-py/scripts/rehearsal.sh' ':!apps/api-py/scripts/section4-EN1.sh'; echo "GREP_RC=$?"; } \
    | grep -v '^apps/api-py/scripts/planted-breaks.sh:90:')"
  grc="$(printf '%s\n' "$g" | sed -n 's/^GREP_RC=//p')"; g="$(printf '%s\n' "$g" | grep -v '^GREP_RC=')"
  [ "${grc:-9}" -le 1 ] || { echo "  ★ 글자열 git grep 이 실패(종료 ${grc:-?})"; rc=1; }
  gb="$({ git -C "$ROOT" grep -c -P 'esgapi\.inventory\.(calc|xlsx_reader|flows\.(shapes|scope12|scope3)\b)' "$BASE" -- . "$closed"; echo "GREP_RC=$?"; } \
    | awk -F: '/^GREP_RC=/ {split($0, a, "="); r = a[2]; next} {s += $NF} END {print s + 0, r}')"
  gbrc="${gb#* }"; gb="${gb%% *}"
  [ "${gbrc:-9}" = 0 ] || { echo "  ★ BASE 글자열 git grep 이 실패(종료 ${gbrc:-?})"; rc=1; }
  echo "  글자열 git grep: BASE $gb 줄 → 지금 $(printf '%s' "$g" | grep -c . ) 줄"
  [ "${gb:-0}" -gt 0 ] || { echo "  ★ 글자열 양성 대조가 0 — 검사가 아무것도 물지 못한다"; rc=1; }
  [ -z "$g" ] || { printf '%s\n' "$g" | head -10 | sed 's/^/    ★ /'; rc=1; }
  if [ "$BOUNDARY" -ge 3 ]; then
    echo "  낡은 경로 글(§2-3 ③): BASE $(helper stale "$BASE" | tail -1)"
    st="$(helper stale)"; printf '%s\n' "$st" | sed 's/^/    /'
    printf '%s\n' "$st" | grep -q '^STALE_LINES=0 ' || rc=1
  fi
  I="$API_PY/esgapi/inventory"
  for f in "$I/calc" "$I/xlsx_reader.py" "$I/flows/shapes.py" "$I/flows/scope12.py" "$I/flows/scope3.py" "$I/tests/calc"; do
    [ -e "$f" ] && { echo "    ★ 옛 자리에 있음: ${f#"$ROOT"/}"; rc=1; }
  done
  report 4 "옛 경로 0(AST import · 글자열$([ "$BOUNDARY" -ge 3 ] && echo ' · 낡은 글') · 옛 파일 자리)" "$rc"
fi

# ── 5. 커밋 ① 의 바뀐 줄 종류 ──
if want 5; then
  helper linekinds; rc=$?
  report 5 "커밋 ① 의 바뀐 줄 = import ∪ 열거한 줄 ∪ __init__ docstring ($([ -n "$C1" ] && echo "${C1:0:7}" || echo index))" "$rc"
fi

# ── 6. rename ──
if want 6; then
  helper renames; report 6 "§2-1 의 git mv 38건이 R(같은 이름 이동은 R090 이상, 빈 __init__ 은 예외)" "$?"
fi

# ── 7. 계약 바이트 ──
if want 7; then
  rc=0
  git -C "$ROOT" diff --quiet "$BASE" -- apps/api-py/generated apps/api-py/esgapi/inventory/tests/data \
    apps/api-py/esgapi/inventory/prompts apps/api-py/esgapi/inventory/data || rc=1
  echo "  generated·tests/data·prompts·data 의 BASE 와 diff: $([ "$rc" = 0 ] && echo 없음 || echo ★있음)"
  dump='import json, sys, esgapi
m = __import__(sys.argv[1], fromlist=["RESULT_SHAPES"])
print(esgapi.__file__, file=sys.stderr)
print(json.dumps({k: v.json_schema() for k, v in m.RESULT_SHAPES.items()}, ensure_ascii=False, indent=1, sort_keys=True))'
  # cwd 가 sys.path 맨 앞('')이라 API_PY 밖(S4)에서 돈다 — 그래야 PYTHONPATH 의 BASE 트리가 이긴다.
  (cd "$S4" && PYTHONPATH="$BASE_API" uv run --project "$API_PY" --frozen python -c "$dump" esgapi.inventory.flows.shapes) \
    > "$S4/7-schema-base.json" 2> "$S4/7-schema-base.err" || rc=1
  (cd "$API_PY" && uv run --frozen python -c "$dump" esgapi.inventory.contracts.shapes) \
    > "$S4/7-schema-now.json" 2> "$S4/7-schema-now.err" || rc=1
  echo "  BASE 덤프의 esgapi: $(tail -1 "$S4/7-schema-base.err")"
  if cmp -s "$S4/7-schema-base.json" "$S4/7-schema-now.json"; then
    echo "  RESULT_SHAPES json_schema() cmp: 같음($(wc -c < "$S4/7-schema-now.json" | tr -d ' ') 바이트)"
  else echo "  ★ RESULT_SHAPES json_schema() cmp: 다름"; rc=1; fi
  api pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$S4/7-api-contract.txt" 2>&1 || rc=1
  tail -1 "$S4/7-api-contract.txt"
  report 7 "계약 바이트(generated·tests/data·prompts·data · 결과 꼴 스키마 · OpenAPI)" "$rc"
fi

# ── 8. HTTP 본문 ──
if want 8; then
  rc=0
  rm -rf "$OUT/bodies-after"
  (cd "$API_PY" && RR1_BODIES_DIR="$OUT/bodies-after" env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider \
    esgapi/inventory/tests/test_route_bodies.py) > "$S4/8-bodies.txt" 2>&1 || rc=1
  tail -1 "$S4/8-bodies.txt"
  if [ ! -d "$OUT/bodies-before" ]; then echo "  ★ bodies-before 가 없다 — 다시 뜰 수 없으니 멈추고 묻는다"; rc=1
  else
    if [ "$(cd "$OUT/bodies-before" && ls)" != "$(cd "$OUT/bodies-after" && ls)" ]; then echo "  ★ 파일 이름 목록이 다르다"; rc=1; fi
    same=0; all=0
    for f in "$OUT/bodies-before"/*; do
      all=$((all + 1)); cmp -s "$f" "$OUT/bodies-after/$(basename "$f")" && same=$((same + 1))
    done
    echo "  bodies 같음 $same/$all (전 HEAD $(cat "$OUT/bodies-before.HEAD" 2>/dev/null | cut -c1-7))"
    [ "$same" = "$all" ] && [ "$all" -gt 0 ] || rc=1
  fi
  report 8 "HTTP 본문 바이트(RR1 bodies)" "$rc"
fi

# ── 9. 흐름·표면 ──
if want 9; then
  rc=0
  reg='import sys, esgapi.inventory.flows.registration as r
print([f.id for f in r.FLOWS], r.DEFAULTS)
print("shapes 실림:", any(m.endswith(".shapes") and m.startswith("esgapi.inventory") for m in sys.modules))'
  b="$(cd "$S4" && PYTHONPATH="$BASE_API" uv run --project "$API_PY" --frozen python -c "$reg")"
  n="$(cd "$API_PY" && uv run --frozen python -c "$reg")"
  echo "  BASE: $b" | tr '\n' ' '; echo; echo "  지금: $n" | tr '\n' ' '; echo
  [ "$b" = "$n" ] || rc=1
  printf '%s\n' "$n" | grep -q '^shapes 실림: False$' || rc=1
  sb="$(helper surface "$BASE")"; sn="$(helper surface)"
  echo "  표면 → 엔진 BASE: $(printf '%s' "$sb" | tr '\n' ' ')"; echo "  표면 → 엔진 지금: $(printf '%s' "$sn" | tr '\n' ' ')"
  # 발주서 ⑦ 의 「22문」은 엔진 21 + data_loader 1 이다(BASE e973637 실측: services 14 · schemas 4 · actions 3).
  [ "$(printf '%s' "$sb" | tail -1)" = "SURFACE_ENGINE_IMPORTS=21 WITH_DATA_LOADER=22" ] || rc=1
  [ "$(printf '%s' "$sb" | tail -1)" = "$(printf '%s' "$sn" | tail -1)" ] || rc=1
  report 9 "흐름 id·DEFAULTS·등록 길에 꼴 없음·표면 → 엔진 21(+data_loader 1 = 22)" "$rc"
fi

# ── 10. lint-imports·자리 ──
if want 10; then
  rc=0
  (cd "$API_PY" && COLUMNS=400 uv run --frozen lint-imports --no-cache) > "$S4/10-lint.txt" 2>&1 || rc=1
  grep '^Contracts: ' "$S4/10-lint.txt"
  if [ "$BOUNDARY" -ge 2 ]; then want_n=15; else want_n=11; fi
  n_file="$(grep -c '^\[importlinter:contract:' "$API_PY/.importlinter")"
  n_test="$(sed -n 's/.*importlinter:contract:")\]) == \([0-9]*\)$/\1/p' "$API_PY/esgapi/reconcile/tests/test_tasks_registered.py")"
  echo "  계약 수: 파일 $n_file · test_tasks_registered $n_test · 기대 $want_n"
  [ "$n_file" = "$want_n" ] && [ "$n_test" = "$want_n" ] || rc=1
  grep -q "^Contracts: $want_n kept, 0 broken" "$S4/10-lint.txt" || rc=1
  (cd "$BASE_API" && python3 scripts/check_test_layout.py --list) 2>&1 | grep 'esgapi/inventory' > "$S4/10-layout-base.txt"
  (cd "$API_PY" && python3 scripts/check_test_layout.py --list) > "$S4/10-layout-now-all.txt" 2>&1 || rc=1
  grep 'esgapi/inventory' "$S4/10-layout-now-all.txt" > "$S4/10-layout-now.txt"
  head -1 "$S4/10-layout-now-all.txt" | sed 's/^/  지금 전체: /'
  for t in base now; do
    printf '  inventory %s: ' "$t"
    for k in 비춤 자유 허용 어김; do printf '%s %s · ' "$k" "$(grep -c "^  $k " "$S4/10-layout-$t.txt")"; done; echo
  done
  [ "$(grep -c '^  어김 ' "$S4/10-layout-now.txt")" = 0 ] || rc=1
  report 10 "lint-imports($want_n kept)·계약 수·자리 규칙 어김 0" "$rc"
fi

# ── 11. 게이트 --fast ──
if want 11; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/11-verify-fast.txt" 2>&1
  rc=$?; tail -1 "$S4/11-verify-fast.txt"
  grep -q '^VERIFY_FAST=PASS' "$S4/11-verify-fast.txt" || rc=1
  report 11 "scripts/verify.sh --fast" "$rc"
fi

# ── 12. check-gates ──
if want 12; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/check-gates.sh) > "$S4/12-check-gates.txt" 2>&1
  rc=$?; tail -2 "$S4/12-check-gates.txt"
  grep -n 'H1' "$S4/12-check-gates.txt" | head -3 | sed 's/^/  /'
  report 12 "scripts/check-gates.sh(H1 탐침 포함)" "$rc"
fi

# ── 13. 심은 파손 ──
if want 13; then
  rc=0
  if [ "$BOUNDARY" -ge 2 ]; then
    (cd "$API_PY" && scripts/planted-breaks-EN1.sh) > "$S4/13-planted-EN1.txt" 2>&1 || rc=1
    tail -2 "$S4/13-planted-EN1.txt"
    grep -q '^FINGERPRINT=same$' "$S4/13-planted-EN1.txt" || rc=1
    m=34
  else m=30; fi
  (cd "$API_PY" && scripts/planted-breaks.sh) > "$S4/13-planted.txt" 2>&1 || rc=1
  grep -E '^(20\.|3[0-3]\.)' "$S4/13-planted.txt" | sed 's/^/  /'
  tail -1 "$S4/13-planted.txt"
  grep -q "^PLANTED=$m/$m$" "$S4/13-planted.txt" || rc=1
  report 13 "심은 파손(planted-breaks.sh $m/$m$([ "$BOUNDARY" -ge 2 ] && echo ' · planted-breaks-EN1.sh'))" "$rc"
fi

# ── 14. 허용 경로 ──
if want 14; then
  changed="$( (git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files --others --exclude-standard) | sort -u)"
  bad="$(printf '%s\n' "$changed" | grep . | grep -v -E '^apps/api-py/esgapi/inventory/' \
    | grep -v -x -E 'apps/api-py/scripts/(section4|planted-breaks)-EN1\.sh|apps/api-py/scripts/planted-breaks\.sh|apps/api-py/\.importlinter|apps/api-py/esgapi/(reconcile/tests/test_tasks_registered|core/tests/test_transaction_rules|config/tests/test_request_schemas_reject_bool)\.py')"
  inner="$(printf '%s\n' "$changed" | grep -E '^apps/api-py/esgapi/inventory/(tests/data|prompts|data)/')"
  echo "  바뀐 파일 $(printf '%s\n' "$changed" | grep -c .) · 허용 밖 $(printf '%s' "$bad" | grep -c .) · 계약 자료 안 $(printf '%s' "$inner" | grep -c .)"
  printf '%s\n' "$bad" "$inner" | grep . | sed 's/^/    ★ /'
  [ -z "$bad" ] && [ -z "$inner" ]; report 14 "허용 경로 밖 0" "$?"
fi

# ── 15. 키 꼴 ──
if want 15; then
  k="$( (git -C "$ROOT" diff "$BASE" | grep '^+'; git -C "$ROOT" log --format=%B "$BASE..HEAD"; \
    [ -n "${EN1_COMMIT_MSG_FILE:-}" ] && cat "$EN1_COMMIT_MSG_FILE"; \
    git -C "$ROOT" ls-files --others --exclude-standard -z | (cd "$ROOT" && xargs -0 cat 2>/dev/null)) \
    | grep -c -E 'sk-[A-Za-z0-9_-]{20,}')"
  echo "  키 꼴: $k"
  [ "$k" = 0 ]; report 15 "diff·커밋 메시지에 키 꼴 0" "$?"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
