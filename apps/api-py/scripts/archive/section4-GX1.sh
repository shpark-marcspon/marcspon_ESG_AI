#!/usr/bin/env bash
# 밴드 GX1 의 §4 자기검증(발주서 band-handoffs/GX1-order.md §4). 줄마다 [n] … EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-GX1.sh                        전부(경계 ⑤ = ④ 의 옛 경로 목록 + 계약 수 11)
#   apps/api-py/scripts/section4-GX1.sh --step 1,3             일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-GX1.sh --boundary 2 --step 3  옛 경로 목록을 그 경계까지(누적)로. 5 는 4 와 같은 목록에
#                                                               계약 수 11(5 단계)
#
# 환경 변수:
#   GX1_BASE   기준 커밋(기본: 워크트리를 만든 main 92f1af4…)
#   GX1_OUT    산출물 자리(기본: 워크트리 곁의 GX1.out). 산출물은 $GX1_OUT/section4/ 아래
#   GX1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(있으면 13 이 $BASE..HEAD 의 메시지와 함께 본다)
#   GX1_REPORT_FILE      보고 파일(기본: 워크트리 곁 band-reports/GX1-greenwash-axes.md — 있으면 13 이 본다)
#   GX1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${GX1_BASE:-92f1af422e84f55f95bcbf4efa5279fd751c80c9}"
OUT="${GX1_OUT:-$SIDE/GX1.out}"
WORDS="${GX1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
REPORT="${GX1_REPORT_FILE:-$(cd "$SIDE/.." && pwd)/band-reports/GX1-greenwash-axes.md}"
S4="$OUT/section4"
E="apps/api-py/esgapi"
G="$E/greenwash"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
# 키를 환경에 두고 돌리지 않는다(발주서 §1-10)
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

STEPS="all"
BOUNDARY=5
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --boundary) BOUNDARY="${2:?--boundary 뒤에 1~5}"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
case "$BOUNDARY" in 1|2|3|4|5) ;; *) echo "--boundary 는 1~5"; exit 2 ;; esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

# 파이썬 도우미 하나(하위 명령으로 가른다). 표준 라이브러리만 — 7 단계만 esgapi 를 들인다.
HELPER="$S4/gx1_helper.py"
cat > "$HELPER" <<'PY'
import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
BOUNDARY = int(sys.argv[3])
CMD = sys.argv[4]
ARGS = sys.argv[5:]
API = ROOT / "apps/api-py"
GW = API / "esgapi/greenwash"
P = "esgapi.greenwash."

# §4-3 의 옛 모듈(누적). calc 는 그 아래 전부.
OLD_BY = {
    1: ["flows.textnorm", "flows.pdfium_locate"],
    2: ["flows.shapes", "flows.review_shapes", "flows.compare_shapes", "flows.terms_shapes", "flows.wire",
        "flows.xlsx", "flows.compare"],
    3: ["calc", "flows.gw1", "flows.result"],
    4: ["flows.adapters", "flows.colab"],
}
CALC_FILES = ["__init__", "checker", "chunking", "dryrun", "heuristics", "parts", "pdftext", "ports", "prompts",
              "retrieval", "wordcount"]
COPIES = [n for n in CALC_FILES if n != "__init__"]


def old_modules(b: int) -> list[str]:
    return [P + m for k in range(1, min(b, 4) + 1) for m in OLD_BY[k]]


def old_files(b: int) -> list[str]:
    files: list[str] = []
    for m in old_modules(b):
        rel = m.removeprefix(P)
        if rel == "calc":
            files += [f"calc/{n}.py" for n in CALC_FILES]
        else:
            files.append(rel.replace(".", "/") + ".py")
    return files


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout


def imports_of(src: str) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.append(node.module)
            names += [f"{node.module}.{a.name}" for a in node.names]
    return names


def hit(name: str, olds: list[str]) -> bool:
    return any(name == o or name.startswith(o + ".") for o in olds)


def targets(paths: list[str]) -> list[str]:
    keep = []
    for p in paths:
        if not p.endswith(".py"):
            continue
        if p.startswith("apps/api-py/esgapi/") or (
            p.startswith("apps/api-py/scripts/") and p.count("/") == 2
        ):
            keep.append(p)
    return keep


def scan(read, paths: list[str], olds: list[str]) -> list[str]:
    found = []
    for p in targets(paths):
        try:
            names = imports_of(read(p))
        except SyntaxError as exc:
            found.append(f"{p}: SyntaxError {exc}")
            continue
        found += [f"{p}: {n}" for n in names if hit(n, olds)]
    return found


def cmd_old_imports() -> int:
    olds = old_modules(BOUNDARY)
    every = old_modules(4)
    base_paths = git("ls-tree", "-r", "--name-only", BASE).splitlines()
    base_hits = scan(lambda p: git("show", f"{BASE}:{p}"), base_paths, every)
    now_paths = [p for p in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
                 if (ROOT / p).is_file()]
    now_hits = scan(lambda p: (ROOT / p).read_text(encoding="utf-8"), now_paths, olds)
    print(f"    양성 대조: BASE 트리의 옛 경로 import(④ 목록) {len(base_hits)}")
    print(f"    지금 트리(경계 {BOUNDARY} 목록 {len(olds)} 개)의 옛 경로 import {len(now_hits)}")
    for h in now_hits:
        print(f"    옛 import: {h}")
    present = [f for f in old_files(BOUNDARY) if (GW / f).exists()]
    print(f"    없어야 할 옛 파일 {len(old_files(BOUNDARY))} 가운데 있는 것 {len(present)}")
    for f in present:
        print(f"    옛 파일 있음: {f}")
    bad = len(now_hits) + len(present) + (1 if not base_hits else 0)
    if BOUNDARY >= 4:
        flows = sorted(p.name for p in (GW / "flows").glob("*.py"))
        want = ["__init__.py", "colab_e0.py", "registration.py"]
        print(f"    flows/*.py = {flows}")
        bad += 0 if flows == want else 1
        bad += 1 if (GW / "calc").exists() else 0
    # 글자열 꼴(-P). 빼는 자리: archive, 닫힌 밴드 스크립트 다섯, 이 밴드의 스크립트 둘
    names = "|".join(sorted({m.removeprefix(P).replace(".", r"\.") for m in olds}, key=len, reverse=True))
    pattern = rf"esgapi\.greenwash\.({names})\b"
    excl = [":!apps/api-py/scripts/archive", ":!apps/api-py/scripts/section4-G1a.sh",
            ":!apps/api-py/scripts/planted-breaks-G1a.sh", ":!apps/api-py/scripts/planted-breaks-G1d.sh",
            ":!apps/api-py/scripts/section4-GTE1.sh", ":!apps/api-py/scripts/planted-breaks-GTE1.sh",
            ":!apps/api-py/scripts/section4-GX1.sh", ":!apps/api-py/scripts/planted-breaks-GX1.sh"]
    out = subprocess.run(["git", "-C", str(ROOT), "grep", "-n", "--untracked", "-P", pattern, "--", "apps/api-py", *excl],
                         capture_output=True, text=True, check=False)
    lines = [ln for ln in out.stdout.splitlines() if ln]
    print(f"    글자열 꼴(-P) {len(lines)}")
    for ln in lines:
        print(f"    글자열: {ln}")
    bad += len(lines)
    return 1 if bad else 0


AXES = {
    "engines": ("engines", ["contracts", "outputs", "flows", "service", "api"]),
    "contracts": ("contracts", ["engines", "flows", "outputs", "service"]),
    "tools": ("tools", ["engines", "contracts", "outputs", "flows"]),
    "outputs": ("outputs", ["engines", "flows"]),
}


def cmd_rules() -> int:
    bad = 0
    groups = [(k, sorted((GW / d).rglob("*.py")), f) for k, (d, f) in AXES.items()]
    groups.append(("service·api.py", [*sorted((GW / "service").rglob("*.py")), GW / "api.py"], ["engines"]))
    for name, files, forbidden in groups:
        olds = [P + f for f in forbidden]
        found = [f"{p.relative_to(GW)}: {n}" for p in files for n in imports_of(p.read_text(encoding="utf-8"))
                 if hit(n, olds)]
        print(f"    {name}: 파일 {len(files)}, 금지({'|'.join(forbidden)}) import {len(found)}")
        for h in found:
            print(f"    걸림: {h}")
        bad += len(found)
    return 1 if bad else 0


def normalize(src: str, ours: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == ours:
                node.module = "greenwash"
            elif node.module.startswith(ours + "."):
                node.module = "greenwash." + node.module.removeprefix(ours + ".")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == ours or a.name.startswith(ours + "."):
                    a.name = "greenwash" + a.name.removeprefix(ours)
    return ast.dump(tree, include_attributes=False)


IMPORT_LINE = re.compile(r"^(from esgapi\.greenwash\.[\w.]+ import .*|import esgapi\.greenwash\.\S.*|[ ]+[\w ,]+,?|\))$")


def cmd_copies() -> int:
    import difflib

    moved = (GW / "engines/e0").is_dir()
    here = GW / ("engines/e0" if moved else "calc")
    ours = P + ("engines.e0" if moved else "calc")
    bad = 0
    changed = 0
    for n in COPIES:
        old = git("show", f"{BASE}:apps/api-py/esgapi/greenwash/calc/{n}.py")
        new = (here / f"{n}.py").read_text(encoding="utf-8")
        same_ast = normalize(old, P + "calc") == normalize(new, ours)
        diff = [ln for ln in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
                if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
        odd = [ln for ln in diff if not IMPORT_LINE.match(ln[1:])]
        changed += len(diff)
        if not same_ast or odd:
            bad += 1
            print(f"    {n}.py: 정규화 AST {'같음' if same_ast else '다름'}, import 밖 줄 {len(odd)}")
            for ln in odd[:5]:
                print(f"      {ln}")
    print(f"    사본 {len(COPIES)}: 바뀐 줄(+/-) {changed}, 정규화 AST·import 줄 밖 어긋남 {bad} (자리 {here.relative_to(GW)})")
    pinned = {ln.split()[0] for ln in (GW / "tests/data/gw1-ast-sha256.txt").read_text(encoding="utf-8").splitlines()
              if ln and not ln.startswith("#")}
    names = {p.name for p in here.glob("*.py") if p.name != "__init__.py"}
    want = pinned | ({"checker.py", "result.py", "gw1.py"} if moved else {"checker.py"})
    print(f"    고정 {len(pinned)}, 폴더의 이름 - 고정 = {sorted(names - pinned)}")
    bad += 0 if (names == want and len(pinned) == 9) else 1
    return 1 if bad else 0


def cmd_breadth() -> int:
    import pathlib

    sys.path.insert(0, str(API))
    from esgapi.greenwash.tests.flows import test_boundary as tb

    seen: list[pathlib.Path] = []
    original = pathlib.Path.read_text

    def spy(self: pathlib.Path, *a, **k):  # type: ignore[no-untyped-def]
        seen.append(self.resolve())
        return original(self, *a, **k)

    def run(fn) -> set[str]:  # type: ignore[no-untyped-def]
        seen.clear()
        pathlib.Path.read_text = spy  # type: ignore[method-assign]
        try:
            fn()
        finally:
            pathlib.Path.read_text = original  # type: ignore[method-assign]
        return {str(p.relative_to(GW.resolve())) for p in seen}

    first = run(tb.test_flow_modules_touch_nothing_outside_their_adapters)
    second = run(tb.test_the_copies_and_flows_do_not_import_jsonschema_or_rpds)
    flows15 = ["__init__", "adapters", "colab", "compare", "compare_shapes", "gw1", "pdfium_locate", "registration",
               "result", "review_shapes", "shapes", "terms_shapes", "textnorm", "wire", "xlsx"]
    new_of = {
        "flows/adapters.py": ["flows/colab_e0.py", "tools/ports.py", "tools/pdftext_pypdf.py", "tools/coordinates.py",
                              "tools/llm_bridge.py"],
        "flows/colab.py": ["flows/colab_e0.py"],
        "flows/compare.py": ["outputs/compare.py"],
        "flows/xlsx.py": ["outputs/xlsx.py"],
        "flows/gw1.py": ["engines/e0/gw1.py"],
        "flows/result.py": ["engines/e0/result.py"],
        "flows/pdfium_locate.py": ["tools/pdfium_locate.py"],
        "flows/textnorm.py": ["tools/textnorm.py"],
        **{f"flows/{n}.py": [f"contracts/{n}.py"] for n in ("shapes", "review_shapes", "compare_shapes",
                                                             "terms_shapes", "wire")},
        **{f"calc/{n}.py": [f"engines/e0/{n}.py"] for n in CALC_FILES},
    }

    def where(old: str) -> list[str]:
        """옛 파일의 지금 자리: 있는 새 자리 전부 + 옛 자리가 아직 있으면 그것."""
        got = [p for p in new_of.get(old, []) if (GW / p).is_file()]
        if (GW / old).is_file():
            got.append(old)
        return got

    bad = 0
    for label, scanned, base in (
        ("첫 시험", first, [f"flows/{n}.py" for n in flows15] + ["apps.py"]),
        ("둘째 시험", second, [f"calc/{n}.py" for n in CALC_FILES] + [f"flows/{n}.py" for n in flows15]),
    ):
        missing = [(o, w) for o in base for w in (where(o) or ["(자리 없음)"]) if w not in scanned]
        print(f"    {label}: 기준 {len(base)} → 지금 훑음 {len(scanned)}, 대응 빠짐 {len(missing)}")
        for o, w in missing:
            print(f"      빠짐: {o} → {w}")
        bad += len(missing) + (1 if len(scanned) < len(base) else 0)
    text = (GW / ("tests/outputs/test_compare.py" if (GW / "tests/outputs/test_compare.py").exists()
                  else "tests/flows/test_compare.py")).read_text(encoding="utf-8")
    mods = sorted(set(re.findall(r"esgapi\.greenwash\.[\w.]*\w", text)))
    for m in mods:
        ok = importlib.util.find_spec(m) is not None
        print(f"    test_compare 의 모듈 이름 {m}: {'있음' if ok else '없음'}")
        bad += 0 if ok else 1
    return 1 if bad else 0


def cmd_nodes() -> int:
    """기준 node 를 파일 대응표로 옮긴 집합 = 지금 node 집합. 대응표를 ARGS[1] 에 쓴다."""
    base_nodes, now_nodes = Path(ARGS[0]).read_text().splitlines(), Path(ARGS[1]).read_text().splitlines()
    out = Path(ARGS[2])
    t = "esgapi/greenwash/tests/"
    files = {
        "flows/test_textnorm.py": "tools/test_textnorm.py",
        "flows/test_pdfium_locate.py": "tools/test_pdfium_locate.py",
        "test_contracts_review_report_terms.py": "contracts/test_contracts_review_report_terms.py",
        "test_contracts_shapes_paths.py": "contracts/test_contracts_shapes_paths.py",
        "flows/test_shapes.py": "contracts/test_shapes.py",
        "flows/test_wire.py": "contracts/test_wire.py",
        "flows/test_xlsx.py": "outputs/test_xlsx.py",
        "flows/test_compare.py": "outputs/test_compare.py",
        **{f"calc/test_{n}.py": f"engines/e0/test_{n}.py" for n in ("checker", "checker_resume", "heuristics",
                                                                    "parts_wordcount")},
        "flows/test_colab.py": "flows/test_colab_e0.py",
    }
    rows, mapped = [], []
    for node in base_nodes:
        path, _, rest = node.partition("::")
        rel = path.removeprefix(t)
        new = files.get(rel)
        target = t + new if new and (API / t / new).is_file() else path
        mapped.append(f"{target}::{rest}")
        rows.append(f"{node}\t{target}::{rest}")
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    a, b = sorted(mapped), sorted(now_nodes)
    extra, lost = sorted(set(b) - set(a)), sorted(set(a) - set(b))
    moved = sum(1 for r in rows if r.split("\t")[0] != r.split("\t")[1])
    print(f"    node 대응: 옮긴 node {moved}, 대응표에 없는 지금 node {len(extra)}, 사라진 기준 node {len(lost)}")
    for x in extra[:10]:
        print(f"      새: {x}")
    for x in lost[:10]:
        print(f"      사라짐: {x}")
    return 0 if a == b else 1


sys.exit({"old-imports": cmd_old_imports, "rules": cmd_rules, "copies": cmd_copies, "breadth": cmd_breadth,
          "nodes": cmd_nodes}[CMD]())
PY
helper() { api python "$HELPER" "$ROOT" "$BASE" "$BOUNDARY" "$@"; }

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 경계 목록 $BOUNDARY, 산출물 $S4"

if want 1; then
  rm -f "$S4/netlog.txt"
  G1A_NET_LOG="$S4/netlog.txt" api pytest -q -p no:cacheprovider -p esgapi.greenwash.tests.netcount esgapi/greenwash \
    > "$S4/pytest-greenwash.log" 2>&1
  e=$?
  tail -1 "$S4/pytest-greenwash.log" | sed 's/^/    /'
  nlog=$( [ -f "$S4/netlog.txt" ] && grep -c . "$S4/netlog.txt" || echo 0)
  blocked=$( [ -f "$S4/netlog.txt" ] && awk '{s += $1} END {print s + 0}' "$S4/netlog.txt" || echo 0)
  echo "    네트워크 시도 기록 $nlog 줄, 막힌 시도 합 $blocked"
  report 1 "greenwash 시험 전부 초록·네트워크 시도 0" "$([ "$e" = 0 ] && [ "$nlog" -gt 0 ] && [ "$blocked" = 0 ] && echo 0 || echo 1)"
fi

if want 2; then
  api pytest --collect-only -q -p no:cacheprovider esgapi/greenwash > "$S4/collect.log" 2>&1
  e=$?
  grep '::' "$S4/collect.log" > "$S4/collect-nodes.txt"
  sed 's/^.*:://' "$S4/collect-nodes.txt" | LC_ALL=C sort > "$S4/collect-names.txt"
  n=$(grep -c . "$S4/collect-nodes.txt")
  same=1
  cmp -s "$OUT/collect-base.txt" "$S4/collect-names.txt" && same=0
  helper nodes "$OUT/collect-base-nodes.txt" "$S4/collect-nodes.txt" "$S4/node-map.tsv"
  m=$?
  echo "    node $n (기준 347) · 이름 묶음 기준과 $([ "$same" = 0 ] && echo 같음 || echo 다름) · 대응표 $S4/node-map.tsv"
  report 2 "시험 수·이름 그대로" "$([ "$e" = 0 ] && [ "$n" = 347 ] && [ "$same" = 0 ] && [ "$m" = 0 ] && echo 0 || echo 1)"
fi

if want 3; then
  helper old-imports
  report 3 "옛 경로 import 0(경계 $BOUNDARY 목록)" "$?"
fi

if want 4; then
  git -C "$ROOT" diff --quiet "$BASE" -- "$G/tests/data" apps/api-py/generated "$G/prompts"
  d=$?
  new=$(git -C "$ROOT" ls-files -o --exclude-standard -- "$G/tests/data" apps/api-py/generated "$G/prompts" | grep -c .)
  api pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$S4/api-contract.log" 2>&1
  c=$?
  echo "    tests/data·generated·prompts diff 종료 $d, 새 파일 $new · $(tail -1 "$S4/api-contract.log")"
  report 4 "계약 바이트 같음" "$([ "$d" = 0 ] && [ "$new" = 0 ] && [ "$c" = 0 ] && echo 0 || echo 1)"
fi

if want 5; then
  api lint-imports > "$S4/lint-imports.log" 2>&1
  e=$?
  kept=$(grep -Eo 'Contracts: [0-9]+ kept, [0-9]+ broken' "$S4/lint-imports.log" | tail -1)
  nk=$(echo "$kept" | awk '{print $2}')
  sections=$(grep -c '^\[importlinter:contract:' "$API_PY/.importlinter")
  pinned_n=$(grep -Eo 'importlinter:contract:"\)\]\) == [0-9]+' "$API_PY/esgapi/reconcile/tests/test_tasks_registered.py" | grep -Eo '[0-9]+$')
  want_n=7
  [ "$BOUNDARY" = 5 ] && want_n=11
  api python scripts/check_test_layout.py --list > "$S4/test-layout.log" 2>&1
  t=$?
  gw=$(grep 'esgapi/greenwash/' "$S4/test-layout.log")
  echo "    $kept · 계약 절 $sections · test_tasks_registered $pinned_n · 기대 $want_n"
  echo "    자리 규칙: $(head -1 "$S4/test-layout.log") (종료 $t)"
  echo "    greenwash: 비춤 $(echo "$gw" | grep -c '^  비춤') · 자유 $(echo "$gw" | grep -c '^  자유') · 허용 $(echo "$gw" | grep -c '^  허용') · 어김 $(echo "$gw" | grep -c '^  어김') (BASE 실측 비춤 14 · 자유 7 · 어김 0)"
  echo "$gw" | grep -v '^  비춤\|^  자유' | sed 's/^/    /'
  report 5 "lint-imports·자리 규칙" \
    "$([ "$e" = 0 ] && [ "$nk" = "$want_n" ] && [ "$sections" = "$want_n" ] && [ "$pinned_n" = "$want_n" ] && [ "$t" = 0 ] && echo 0 || echo 1)"
fi

if want 6; then
  git -C "$ROOT" diff --quiet "$BASE" -- "$G/tests/data/gw1-ast-sha256.txt"
  h=$?
  api pytest -q -p no:cacheprovider -rA esgapi/greenwash/tests/test_copy_ast.py > "$S4/copy-ast.log" 2>&1
  c=$?
  nine=$(grep -c '^PASSED .*test_a_copy_has_the_gw1_ast\[' "$S4/copy-ast.log")
  helper copies
  k=$?
  echo "    해시 파일 diff 종료 $h · test_copy_ast $(tail -1 "$S4/copy-ast.log") · 고정 parametrize PASSED $nine"
  report 6 "AST 고정" "$([ "$h" = 0 ] && [ "$c" = 0 ] && [ "$nine" = 9 ] && [ "$k" = 0 ] && echo 0 || echo 1)"
fi

if want 7; then
  helper breadth
  report 7 "넓이 그대로" "$?"
fi

if want 8; then
  # 작업 트리 대 기준(git mv 는 색인에 있다). 커밋 뒤에는 BASE..HEAD 와 같다.
  git -C "$ROOT" diff -M --name-status "$BASE" -- "$G" > "$S4/rename.txt"
  git -C "$ROOT" diff -M20% --name-status "$BASE" -- "$G/flows" > "$S4/rename-m20.txt"
  bad=0
  pairs=""
  t="tests"
  [ "$BOUNDARY" -ge 1 ] && pairs="$pairs flows/textnorm.py:tools/textnorm.py flows/pdfium_locate.py:tools/pdfium_locate.py
    $t/flows/test_textnorm.py:$t/tools/test_textnorm.py $t/flows/test_pdfium_locate.py:$t/tools/test_pdfium_locate.py"
  if [ "$BOUNDARY" -ge 2 ]; then
    for n in shapes review_shapes compare_shapes terms_shapes wire; do pairs="$pairs flows/$n.py:contracts/$n.py"; done
    for n in xlsx compare; do pairs="$pairs flows/$n.py:outputs/$n.py"; done
    for n in contracts_review_report_terms contracts_shapes_paths; do pairs="$pairs $t/test_$n.py:$t/contracts/test_$n.py"; done
    for n in shapes wire; do pairs="$pairs $t/flows/test_$n.py:$t/contracts/test_$n.py"; done
    for n in xlsx compare; do pairs="$pairs $t/flows/test_$n.py:$t/outputs/test_$n.py"; done
  fi
  if [ "$BOUNDARY" -ge 3 ]; then
    for n in checker chunking dryrun heuristics parts pdftext ports prompts retrieval wordcount __init__; do
      pairs="$pairs calc/$n.py:engines/e0/$n.py"
    done
    for n in result gw1; do pairs="$pairs flows/$n.py:engines/e0/$n.py"; done
    for n in checker checker_resume heuristics parts_wordcount __init__; do pairs="$pairs $t/calc/test_$n.py:$t/engines/e0/test_$n.py"; done
  fi
  [ "$BOUNDARY" -ge 4 ] && pairs="$pairs flows/colab.py:flows/colab_e0.py $t/flows/test_colab.py:$t/flows/test_colab_e0.py"
  for pair in $pairs; do
    old="$G/${pair%%:*}"; new="$G/${pair#*:}"
    old=$(echo "$old" | sed 's#tests/calc/test___init__#tests/calc/__init__#'); new=$(echo "$new" | sed 's#tests/engines/e0/test___init__#tests/engines/e0/__init__#')
    line=$(awk -F'\t' -v o="$old" -v n="$new" '$2 == o && $3 == n' "$S4/rename.txt")
    score=$(echo "$line" | cut -f1 | sed 's/^R//')
    case "$old" in
      */calc/__init__.py|*/tests/calc/__init__.py|*/tests/flows/test_textnorm.py|*/flows/colab.py)
        echo "    예외 ${old#"$G"/} → ${new#"$G"/}: ${line:-(짝 없음 — D+A)}" | cut -f1 ; continue ;;
    esac
    if [ -z "$score" ] || [ "$score" -lt 90 ]; then
      echo "    R090 미만: ${old#"$G"/} → ${new#"$G"/} ${score:-(짝 없음)}"; bad=$((bad + 1))
    fi
  done
  echo "    짝 $(echo $pairs | wc -w | tr -d ' ') 개 · R090 미만(예외 넷 밖) $bad"
  echo "    colab.py → colab_e0.py: -M $(awk -F'\t' '$2 ~ /flows\/colab.py$/ {print $1}' "$S4/rename.txt") · -M20% $(awk -F'\t' '$2 ~ /flows\/colab.py$/ {print $1}' "$S4/rename-m20.txt")"
  grep -E '^[DA]' "$S4/rename.txt" | sed 's/^/    /'
  report 8 "rename 유사도" "$([ "$bad" = 0 ] && echo 0 || echo 1)"
fi

if want 9; then
  api python -c "import sys; import esgapi.greenwash.flows.registration as r; \
print(sorted(m for m in sys.modules if m.startswith('esgapi.greenwash.') and m.endswith('shapes'))); \
print('pypdfium2' in sys.modules); print([f.id for f in r.FLOWS], r.DEFAULTS)" > "$S4/registry.txt" 2>&1
  e=$?
  sed 's/^/    지금: /' "$S4/registry.txt"
  [ -f "$OUT/registry-base.txt" ] && sed 's/^/    BASE: /' "$OUT/registry-base.txt"
  l1=$(sed -n 1p "$S4/registry.txt"); l3=$(sed -n 3p "$S4/registry.txt")
  report 9 "등록 길 무게" "$([ "$e" = 0 ] && [ "$l1" = "[]" ] && [ "$l3" = "['greenwash.colab@E0'] {'greenwash': 'greenwash.colab@E0'}" ] && echo 0 || echo 1)"
fi

if want 10; then
  helper rules
  report 10 "규칙 세 줄 손 검사(AST)" "$?"
fi

if want 11; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  api python -c "import runpy; runpy.run_path('scripts/g1a_compare.py', run_name='probe')" > "$S4/g1a-probe.log" 2>&1
  p=$?
  echo "    $last / ${gates:-(GATES= 줄 없음)} (종료 $e) · g1a_compare 실어 보기 종료 $p"
  report 11 "verify.sh --fast · check-gates · g1a_compare 실림" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && [ "$p" = 0 ] && echo 0 || echo 1)"
fi

changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

if want 12; then
  changed_files > "$S4/changed-files.txt"
  allowed="^($G/|apps/api-py/scripts/g1a_compare\.py$|apps/api-py/scripts/(section4|planted-breaks)-GX1\.sh$|apps/api-py/\.importlinter$|$E/reconcile/tests/test_tasks_registered\.py$|README\.md$|$E/config/tests/test_api_contract\.py$)"
  outside=$(grep -Ev "$allowed" "$S4/changed-files.txt")
  zero=$(grep -E "^($G/tests/data/|$G/prompts/)" "$S4/changed-files.txt")
  # 허락 받은 공유 파일의 바뀐 줄 수(더한+뺀)
  for f in apps/api-py/.importlinter "$E/reconcile/tests/test_tasks_registered.py" README.md "$E/config/tests/test_api_contract.py"; do
    echo "    공유 $f: $(git -C "$ROOT" diff --numstat "$BASE" -- "$f" | awk '{print "+" $1 " -" $2}')"
  done
  echo "    바뀐 파일 $(grep -c . "$S4/changed-files.txt") · 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0) · tests/data·prompts $( [ -n "$zero" ] && echo "$zero" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  [ -n "$zero" ] && echo "$zero" | sed 's/^/    0 이어야: /'
  report 12 "허용 경로" "$([ -z "$outside" ] && [ -z "$zero" ] && echo 0 || echo 1)"
fi

if want 13; then
  { git -C "$ROOT" diff -U0 "$BASE" | awk '/^\+\+\+ / {next} /^\+/ {print substr($0, 2)}'
    git -C "$ROOT" ls-files -o --exclude-standard --full-name | while IFS= read -r f; do [ -f "$ROOT/$f" ] && cat "$ROOT/$f"; done
  } > "$S4/added-lines.txt"
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  draft="${GX1_COMMIT_MSG_FILE:-}"
  [ -n "$draft" ] && [ -f "$draft" ] && msgs="$msgs
$(cat "$draft")"
  [ -f "$REPORT" ] && msgs="$msgs
$(cat "$REPORT")"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다"; hits=1; mhits=1
  else
    hits=$(grep -F -i -c -f "$WORDS" "$S4/added-lines.txt")
    mhits=$(printf '%s\n' "$msgs" | grep -F -i -c -f "$WORDS")
  fi
  keys=$( { cat "$S4/added-lines.txt"; printf '%s\n' "$msgs"; } | grep -E -c 'sk-[A-Za-z0-9_-]{20,}')
  echo "    더한 줄 $(grep -c . "$S4/added-lines.txt") 에서 낱말 걸림 $hits · 메시지($(git -C "$ROOT" rev-list --count "$BASE..HEAD") 커밋${draft:+ + 초안}$( [ -f "$REPORT" ] && echo ' + 보고')) 걸림 $mhits · 키 꼴 $keys"
  report 13 "기업명·키 꼴 0" "$([ "$hits$mhits$keys" = 000 ] && echo 0 || echo 1)"
fi

if want 14; then
  if [ -x "$API_PY/scripts/planted-breaks-GX1.sh" ]; then
    (cd "$API_PY" && GX1_OUT="$OUT" GX1_BASE="$BASE" scripts/planted-breaks-GX1.sh) > "$S4/planted.log" 2>&1
    e=$?
    grep -E '^ *\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
    total=$(grep -Eo '^PLANTED=[0-9]+/[0-9]+' "$S4/planted.log" | sed 's/PLANTED=//')
    report 14 "심은 파손" "$([ "$e" = 0 ] && [ -n "$total" ] && [ "${total%/*}" = "${total#*/}" ] && grep -q '^FINGERPRINT=same' "$S4/planted.log" && echo 0 || echo 1)"
  else
    echo "    planted-breaks-GX1.sh 가 아직 없다"
    report 14 "심은 파손" 1
  fi
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
