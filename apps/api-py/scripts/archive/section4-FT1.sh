#!/usr/bin/env bash
# 밴드 FT1(MARC-TICK-172) §4 의 자기검증. reconcile 의 값 후보 뽑기(calc/facts.py)를 전체 == 로 견주는 순수 시험
# (Extraction·grid_facts 의 출력 칸 전부, 머리글 찾기 _headers_for·_header_rows_for·inner_header_rows·estimate_header),
# 그리고 test_mask·test_facts 의 적재 때 값(뽑기·synthetic_document 의 머리글 추정)을 시험 안으로 옮긴 것.
#   사용: apps/api-py/scripts/section4-FT1.sh [--step <n>[,<n>…]] [--planted] [--premeasure] [--mutmut] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>. --planted 는 6단계(심은 파손, 끝 줄 PLANTED=<잡음>/12),
#   --premeasure 는 0단계만(바닥 main 의 facts.py 를 시험 고치기 전에 다시 잰다 — §2-1(e), 감독 허락 뒤에만),
#   --mutmut 은 7단계만(스테이징 트리의 facts.py 를 다시 잰다 — 감독 허락 뒤에만 부른다), --msg 는 8단계만(커밋 메시지
#   초안의 트레일러). 아무것도 없으면 1~5 와 8(초안은 FT1.out/commit-msg.txt).
# 출력 자리는 S4_OUT(기본 FT1.out). 검증자는 S4_OUT=…/FT1.verify 로 돌려 러너 기록을 덮지 않는다. 바닥 파일
# (base-ga.txt·base-surv.txt·base-ga-diffs.txt·pre-ga.txt·known-names.txt)과 커밋 메시지 초안은 늘 FT1.out 에서 읽는다.
# 커밋 전에는 스테이징된 트리를 잰다(git show ":<경로>", git diff --cached). 시험을 돌리는 1·6 단계는 작업 트리에서 도니
# 4단계가 「작업 트리 = 스테이징」을 함께 본다. 심은 파손은 cp 로 베끼고 되쓰고 cmp(checkout·restore·stash 0).
# 심기는 새 파일(calc/test_facts.py·calc/test_facts_headers.py)의 시험이 빨개져야 잡은 것으로 센다.
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. 실제 LLM 호출 0, 키 파일 0, 컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=7444685bb02db4771acef3a6ae6d29e5d4978ef1
BASEDIR="$ROOT/../FT1.out"
OUT="${S4_OUT:-$ROOT/../FT1.out}"
KNOWN=/Users/leedongeon/Desktop/marcspon/weekly/known-survivors.txt
mkdir -p "$OUT"

ONLY=""
PLANTED=0
PREMEASURE=0
MUTMUT=0
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --premeasure) PREMEASURE=1; shift ;;
    --mutmut) MUTMUT=1; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--premeasure] [--mutmut] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
if [ -z "$ONLY" ]; then
  if [ "$PLANTED" = 1 ]; then ONLY=6; elif [ "$PREMEASURE" = 1 ]; then ONLY=0; elif [ "$MUTMUT" = 1 ]; then ONLY=7
  elif [ -n "$MSG" ]; then ONLY=8; else ONLY=1,2,3,4,5,8; fi
fi
[ -n "$MSG" ] || MSG="$BASEDIR/commit-msg.txt"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }

# 대상 시험(주간 ② 의 선택 안). 폴더째가 아니라 파일을 나열한다(폴더를 넘기면 django_db 파일까지 모인다).
TESTS="esgapi/reconcile/tests/test_facts.py esgapi/reconcile/tests/test_mask.py
esgapi/reconcile/tests/test_golden_synthetic.py esgapi/reconcile/tests/test_places.py
esgapi/reconcile/tests/test_kinds.py esgapi/reconcile/tests/test_notation.py esgapi/reconcile/tests/test_document.py
esgapi/reconcile/tests/calc/test_shape.py esgapi/reconcile/tests/calc/test_notation.py
esgapi/reconcile/tests/calc/test_kinds.py esgapi/reconcile/tests/calc/test_document.py
esgapi/reconcile/tests/calc/test_facts.py esgapi/reconcile/tests/calc/test_facts_headers.py"
# 심기를 「잡았다」고 셀 새 파일(esgapi/reconcile/tests/ 아래). golden·평평한 시험만 빨개지면 잡지 못한 것이다.
NEWTESTS="calc/test_facts.py calc/test_facts_headers.py"
MARK="not django_db and not security and not not_under_mutmut"
CALC="apps/api-py/esgapi/reference/calc apps/api-py/esgapi/reconcile/calc apps/api-py/esgapi/core/calc"
FACTS_PY=apps/api-py/esgapi/reconcile/calc/facts.py

run_tests() {  # run_tests <출력 파일> [pytest 인자…]
  local log="$1"; shift
  # shellcheck disable=SC2086  # TESTS 는 빈칸으로 나눈 경로 목록이다
  (cd "$ROOT/apps/api-py" && uv run --frozen pytest -q $TESTS -m "$MARK" -p no:cacheprovider "$@") > "$log" 2>&1
}

PY_HELPER="$(mktemp -t s4ft1.XXXXXX)"
PLANT_BACKUP=""  # 6단계가 심는 동안만 차 있다 — 도중에 끝나도 facts.py 를 되쓴다
trap 'rm -f "$PY_HELPER"; if [ -n "$PLANT_BACKUP" ]; then cp "$PLANT_BACKUP" "$FACTS_PY"; fi' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, re, subprocess, sys

MODE = sys.argv[1]
BASE = sys.argv[2]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


NEW_FILES = [
    "apps/api-py/esgapi/reconcile/tests/calc/test_facts.py",
    "apps/api-py/esgapi/reconcile/tests/calc/test_facts_headers.py",
]
# 3(b) 만 보는 고친 평평한 파일(§2-3-5 — 적재 때 뽑기를 시험 안으로 옮긴 것).
FIXED_FILES = [
    "apps/api-py/esgapi/reconcile/tests/test_facts.py",
    "apps/api-py/esgapi/reconcile/tests/test_mask.py",
]
# 3(a): 결과 전체를 내는 호출(§4-3). 새 파일에 결과를 그대로 돌려주는 도우미는 없다.
RESULT_CALLS = {"extract_document", "extract_grids", "grid_facts", "_headers_for", "_header_rows_for",
                "inner_header_rows", "estimate_header", "_own_titles"}
# 허용: ==/is 의 한 쪽 전체 · isinstance 의 첫 인자 · len() · return(도우미가 그대로 돌려줌).
# ★: 첨자·속성의 값 · 튜플 풀기(facts, _ = grid_facts(…)) · 컴프리헨션 iter · == 아닌 비교 · 다른 함수의 인자 ·
#    == 의 두 쪽이 다 결과(기대값 쪽 호출).
ALLOWED_COMPARE = (ast.Eq, ast.Is)
# 3(b): 모듈 몸(함수 밖·데코레이터·기본값)에서 부르면 안 되는 대상 함수(§1-4).
TARGETS = {"extract_document", "extract_grids", "grid_facts", "estimate_header", "inner_header_rows", "_headers_for",
           "_header_rows_for", "_own_titles", "synthetic_document", "validate_document", "scan_numbers",
           "classify_cell"}


def callee(node):
    if isinstance(node, ast.Call):
        f = node.func
        return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    return None


def is_producer(node, tainted):
    if isinstance(node, ast.Call) and callee(node) in RESULT_CALLS:
        return True
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in tainted


def loadtime_check(path, short, source, tree):
    bad = 0
    loadtime = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            loadtime += list(stmt.decorator_list)
            if not isinstance(stmt, ast.ClassDef):
                loadtime += list(stmt.args.defaults) + [d for d in stmt.args.kw_defaults if d is not None]
        else:
            loadtime.append(stmt)
    for top in loadtime:
        for node in ast.walk(top):
            if isinstance(node, ast.Call) and callee(node) in TARGETS:
                bad += 1
                print(f"  ★ 적재 때 호출: {short}:{node.lineno} {ast.get_source_segment(source, node)}")
    for node in ast.walk(tree):
        name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
        if name in ("cache", "lru_cache"):
            bad += 1
            print(f"  ★ {name}: {short}:{node.lineno}")
        if isinstance(node, ast.Call) and callee(node) == "fixture":
            for kw in node.keywords:
                if kw.arg == "scope" and not (isinstance(kw.value, ast.Constant) and kw.value.value == "function"):
                    bad += 1
                    print(f"  ★ 함수 범위가 아닌 고정물: {short}:{node.lineno}")
    return bad


def step3():
    bad = 0
    for path in NEW_FILES + FIXED_FILES:
        source = git("show", f":{path}")
        tree = ast.parse(source)
        short = path.removeprefix("apps/api-py/esgapi/reconcile/tests/")
        if path in NEW_FILES:
            parent = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parent[child] = node
            tainted = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None and is_producer(node.value, set()):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for t in targets:
                        if isinstance(t, ast.Name):
                            tainted.add(t.id)
                        else:
                            bad += 1
                            print(f"  ★ 부분 비교(튜플 풀기): {short}:{node.lineno} {ast.get_source_segment(source, node)}")
            # (a) 부분 비교
            for node in ast.walk(tree):
                if not is_producer(node, tainted):
                    continue
                up = parent.get(node)
                text = ast.get_source_segment(source, node)
                why = None
                if isinstance(up, (ast.Subscript, ast.Attribute)) and up.value is node:
                    why = "첨자·속성"
                elif isinstance(up, ast.comprehension) and up.iter is node:
                    why = "컴프리헨션 iter"
                elif isinstance(up, ast.Compare) and not all(isinstance(op, ALLOWED_COMPARE) for op in up.ops):
                    why = "== 아닌 비교"
                elif isinstance(up, ast.Compare) and all(is_producer(side, tainted) for side in [up.left, *up.comparators]):
                    why = "== 의 두 쪽이 다 결과"
                elif isinstance(up, ast.Call) and node is not up.func:
                    name = callee(up)
                    if not ((name == "isinstance" and up.args and up.args[0] is node) or name == "len"):
                        why = f"{name}() 의 인자"
                elif isinstance(up, ast.keyword):
                    why = "다른 함수의 인자"
                elif isinstance(up, (ast.Tuple, ast.List, ast.Starred)):
                    why = "튜플·목록의 한 칸"
                if why:
                    bad += 1
                    print(f"  ★ 부분 비교({why}): {short}:{node.lineno} {text}")
                else:
                    kind = type(up).__name__
                    print(f"  전체({kind}): {short}:{node.lineno} {text}")
        # (b) 적재 때 호출·cache·모듈 범위 고정물
        bad += loadtime_check(path, short, source, tree)
    print(f"  ★ 합 {bad}")
    return 1 if bad else 0


ALLOWED = re.compile(r"^apps/api-py/(esgapi/reconcile/tests/.+|scripts/section4-FT1\.sh)$")


def step4():
    bad = 0
    changed = [p for p in git("diff", "--cached", "--name-only", BASE).split("\n") if p]
    print(f"  바뀐 경로 {len(changed)}")
    for p in changed:
        mark = "" if ALLOWED.match(p) else "  ★ 허용 밖"
        bad += 1 if mark else 0
        print(f"  {p}{mark}")
    for p in [p for p in git("ls-files", "-o", "--exclude-standard").split("\n") if p]:
        bad += 1
        print(f"  ★ 추적 밖 새 파일(스테이징 안 됨): {p}")
    unstaged = [p for p in git("diff", "--name-only").split("\n") if p]
    for p in unstaged:
        bad += 1
        print(f"  ★ 작업 트리 ≠ 스테이징: {p}")
    return 1 if bad else 0


# 6: 심은 파손(§3, 줄은 7444685). (번호, 줄, 바꿀 글자, 새 글자) — 모두 facts.py.
FACTS = "apps/api-py/esgapi/reconcile/calc/facts.py"
PLANTS = {
    "P1": (258, "table_status=grid.status,", "table_status=None,"),
    "P2": (281, "continue", "break"),
    "P3": (206, "mark.row == row and mark.col == col", "mark.row == row or mark.col == col"),
    "P4": (450, 'page.text_layer == "none"', 'page.text_layer != "none"'),
    "P5": (381, "<= _UNIT_LINE_CELL_MAX", "< _UNIT_LINE_CELL_MAX"),
    "P6": (415, "Span(token.start, token.end, token.occurrence)", "Span(token.start, token.end, None)"),
    "P7": (468, "return Extraction(doc_id, file_name,", "return Extraction(None, file_name,"),
    "P8": (171, "normalize_text(_cell(grid, i, c)), c != col))", "normalize_text(_cell(grid, i, c)), c == col))"),
    "P9": (163, "normalize_text(_cell(grid, r, j)), True))", "normalize_text(_cell(grid, r, j)), False))"),
    "P10": (139, "inner[i] == block[0] - 1", "inner[i] == block[0] + 1"),
    "P11": (87, "while len(rows) > 1 and", "while len(rows) >= 1 and"),
    "P12": (336, "for other in titles[:3]]", "for other in titles[:4]]"),
}


def plant(name):
    line, old, new = PLANTS[name]
    with open(FACTS, encoding="utf-8") as f:
        rows = f.read().split("\n")
    row = rows[line - 1]
    if row.count(old) != 1:
        print(f"  ★ {name} {FACTS}:{line} 에 「{old}」 가 하나가 아니다: {row.strip()}")
        return 1
    rows[line - 1] = row.replace(old, new)
    with open(FACTS, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))
    print(f"  {name} facts.py:{line}: {row.strip()}  →  {rows[line - 1].strip()}")
    return 0


# 0·7: 견주기. 결과 파일의 생존(killed 아님) 이름 가운데 known 에 없는 것.
TARGET = re.compile(r"^esgapi\.reconcile\.calc\.facts\.")


def survivors(paths):
    names = set()
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if ": killed" in line or ":" not in line:
                    continue
                name = line.strip().split(": ", 1)[0]
                if TARGET.match(name):
                    names.add(name)
    return names


def diff_lines(path, header):
    """`### <이름>` 블록마다 -/+ 줄(앞뒤 빈칸을 뗀 것)의 목록. header 는 이름을 꺼내는 함수."""
    out, name = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("### "):
                name = header(line)
                out[name] = []
            elif name and (line.startswith("-") or line.startswith("+")) and not line.startswith(("---", "+++")):
                out[name].append(line[0] + line[1:].strip())
    return out


def fn(n):
    return re.sub(r"__mutmut_[0-9]+$", "", n)


def group(name):
    short = fn(name).rsplit(".", 1)[1]
    if short in ("x_grid_facts", "x_extract_document", "x_extract_grids"):
        return "표 1"
    if short in ("x__headers_for", "x__header_rows_for", "x_inner_header_rows", "x_estimate_header"):
        return "표 2"
    return "나머지"


def read_set(path):
    with open(path, encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}


def write_set(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(f"{n}\n" for n in sorted(rows)))


def known_names(path):
    with open(path, encoding="utf-8") as f:
        return {l.split()[1] for l in f if l.startswith("### ")}


def step0():
    out, known_path, basedir, *results = sys.argv[3:]
    known = known_names(known_path)
    before = read_set(f"{basedir}/base-ga.txt")
    pre = survivors(results) - known
    killed, new = before - pre, pre - before
    write_set(f"{out}/pre-ga.txt", pre)
    write_set(f"{out}/pre-killed.txt", killed)
    write_set(f"{out}/pre-new.txt", new)
    funcs = sorted({fn(n) for n in before | pre})
    with open(f"{out}/pre-table.md", "w", encoding="utf-8") as f:
        f.write("| 함수 | 무리 | 바닥(가) | 지금 main(가) | 이미 죽음 | 새로 남 |\n|---|---|---:|---:|---:|---:|\n")
        for g in funcs:
            b = sum(1 for n in before if fn(n) == g)
            a = sum(1 for n in pre if fn(n) == g)
            k = sum(1 for n in killed if fn(n) == g)
            w = sum(1 for n in new if fn(n) == g)
            f.write(f"| {g.removeprefix('esgapi.reconcile.calc.facts.')} | {group(g)} | {b} | {a} | {k} | {w} |\n")
    groups = {}
    for n in pre:
        groups[group(n)] = groups.get(group(n), 0) + 1
    print(f"  지금 삶의 무리: 표 1 {groups.get('표 1', 0)} · 표 2 {groups.get('표 2', 0)} · 나머지 {groups.get('나머지', 0)}")
    print(f"PRE_KILLED={len(killed)}/{len(before)}")
    print(f"PRE_ALIVE={len(pre)}")
    print(f"PRE_NEW={len(new)}")
    return 0 if not new else 1


def step7():
    out, known_path, basedir, *results = sys.argv[3:]
    known = known_names(known_path)
    before = read_set(f"{basedir}/base-ga.txt")
    pre = read_set(f"{basedir}/pre-ga.txt")
    base_surv = read_set(f"{basedir}/base-surv.txt")
    alive = survivors(results)
    after = alive - known
    killed, remain, new = before - after, before & after, after - before
    band_killed = pre - after
    known_died = (base_surv & known) - alive
    for name, rows in (("after-ga.txt", after), ("killed.txt", killed), ("remain.txt", remain), ("new.txt", new),
                       ("band-killed.txt", band_killed), ("known-died.txt", known_died)):
        write_set(f"{out}/{name}", rows)

    funcs = sorted({fn(n) for n in before | pre | after})
    with open(f"{out}/mut-table.md", "w", encoding="utf-8") as f:
        f.write("| 함수 | 무리 | 바닥(가) | 지금 main(가) | 뒤(가) | 이 밴드가 죽임 | 새로 남 |\n"
                "|---|---|---:|---:|---:|---:|---:|\n")
        for g in funcs:
            b = sum(1 for n in before if fn(n) == g)
            p = sum(1 for n in pre if fn(n) == g)
            a = sum(1 for n in after if fn(n) == g)
            k = sum(1 for n in band_killed if fn(n) == g)
            w = sum(1 for n in new if fn(n) == g)
            f.write(f"| {g.removeprefix('esgapi.reconcile.calc.facts.')} | {group(g)} | {b} | {p} | {a} | {k} | {w} |\n")
    # 남은 것의 diff 글자가 바닥과 같은지(같은 이름이 같은 변이인지): 주간 survivors.txt 의 -/+ 줄과 견준다.
    base_diffs = diff_lines(f"{basedir}/base-ga-diffs.txt", lambda l: l[4:].strip())
    now = {}
    for path in results:
        now.update(diff_lines(path.replace("mutmut-results.txt", "survivors.txt"), lambda l: l[4:].split("\t")[1]))
    differ = [n for n in sorted(remain) if base_diffs.get(n) != now.get(n)]
    for n in differ:
        print(f"  ★ 남은 것의 diff 가 바닥과 다르다: {n}")
    print(f"  남은 것 diff 같음 {len(remain) - len(differ)}/{len(remain)}")
    print(f"  사라진 생존(known 에 든 바닥 생존 가운데 죽음) {len(known_died)}")
    print(f"MUT_KILLED={len(killed)}/{len(before)}")
    print(f"MUT_REMAIN={len(remain)}")
    print(f"MUT_NEW={len(new)}")
    print(f"BAND_KILLED={len(band_killed)}/{len(pre)}")
    return 0 if not new and not differ else 1


def step8():
    path = sys.argv[3]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parsed = subprocess.run(["git", "interpret-trailers", "--parse"], input=text, capture_output=True, text=True,
                            check=True).stdout
    keys = {}
    for line in parsed.splitlines():
        key, _, value = line.partition(":")
        keys.setdefault(key.strip(), []).append(value.strip())
    bad = 0
    want = {"Ticket": r"^MARC-TICK-[0-9]+$", "Concerns": r"^MARC-ISSUE-155$", "Derives-from": r"^MARC-ENT-280$",
            "Rejected": r".", "Constraint": r".", "Directive": r".", "Confidence": r"^(high|medium|low)$",
            "Scope-risk": r"^(narrow|moderate|broad)$", "Not-tested": r".", "Co-Authored-By": r"."}
    for key, pattern in want.items():
        values = keys.get(key, [])
        ok = bool(values) and all(re.search(pattern, v) for v in values)
        bad += 0 if ok else 1
        print(f"  {'' if ok else '★ '}{key}: {len(values)} {values[:1]}")
    last = text.rstrip("\n").split("\n")[-1]
    if last != "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>":
        bad += 1
        print(f"  ★ 끝 줄이 Co-Authored-By 가 아니다: {last}")
    first = text.split("\n", 1)[0]
    print(f"  제목: {first}")
    return 1 if bad else 0


sys.exit({"0": step0, "3": step3, "4": step4, "plant": lambda: plant(sys.argv[3]), "7": step7, "8": step8}[MODE]())
PYEOF

# mutmut 한 번(0·7 단계가 같이 쓴다): run_mutmut <커밋> <일터 뿌리> <결과 뿌리> <로그>
run_mutmut() {
  local rev="$1" wroot="$2" res="$3" log="$4"
  common="$(git rev-parse --path-format=absolute --git-common-dir)"
  [ -e "$common/verify.lock" ] && echo "  ★ verify.lock 있음" || echo "  verify.lock 없음"
  uptime | sed 's/^/  시작 부하: /'
  vm_stat | head -3 | sed 's/^/  /'
  rm -rf "$res"
  t0=$(date +%s)
  WEEKLY_WORK_ROOT="$wroot" scripts/weekly.sh --commit "$rev" --mutmut-only --out "$res" \
    --known "$KNOWN" --only esgapi/reconcile/calc/facts.py > "$log" 2>&1
  wrc=$?
  echo "  weekly 종료 $wrc · $(( $(date +%s) - t0 ))초"
  uptime | sed 's/^/  끝 부하: /'
  tail -3 "$log" | sed 's/^/  /'
  grep -q '^WEEKLY=OK' "$log" || wrc=1
  grep -h -E '^(mutmut_done|targets_count|targets_source|mutmut_wall|rev_hash|result|work_removed)=' "$res"/*/meta.txt | sed 's/^/  meta /'
  return "$wrc"
}

if want 0; then
  cache_before="$(ls ~/.cache/esg-weekly/ 2>/dev/null)"
  run_mutmut "$BASE" "$OUT/wr-pre" "$OUT/pre" "$OUT/s4-0-weekly.log"
  rc=$?
  # shellcheck disable=SC2046
  python3 -I "$PY_HELPER" 0 "$BASE" "$OUT" "$KNOWN" "$BASEDIR" $(ls "$OUT"/pre/*/mutmut-results.txt) || rc=1
  [ "$(ls ~/.cache/esg-weekly/ 2>/dev/null)" = "$cache_before" ] || { rc=1; echo "  ★ ~/.cache/esg-weekly 가 바뀌었다"; }
  report 0 "지금 main 다시 재기(facts.py, 시험 고치기 전)" "$rc"
fi

if want 1; then
  run_tests "$OUT/s4-1.log" --durations=5
  rc=$?
  tail -8 "$OUT/s4-1.log" | sed 's/^/  /'
  report 1 "대상 시험(주간 ② 의 선택, 새 파일 포함)" "$rc"
fi

if want 2; then
  # shellcheck disable=SC2086
  (cd "$ROOT/apps/api-py" && uv run --frozen pytest -q $TESTS -m django_db --co -p no:cacheprovider) > "$OUT/s4-2.log" 2>&1
  co=$?
  tail -2 "$OUT/s4-2.log" | sed 's/^/  /'
  # pytest 는 모은 것이 0 이면 종료 5 다 — 그것이 통과다
  rc=0
  if [ "$co" != 5 ] || ! grep -q "no tests collected" "$OUT/s4-2.log"; then rc=1; echo "  ★ django_db 시험이 모였다(종료 $co)"; fi
  marks=$(git diff --cached -U0 "$BASE" -- 'apps/api-py/esgapi/*/tests/*' | grep -E '^\+' | grep -c -E 'django_db|not_under_mutmut|mark\.security')
  echo "  더한 줄의 표식 $marks"
  [ "$marks" = 0 ] || rc=1
  report 2 "django_db 0 (대상 파일 모음 0 · 더한 줄 표식 0)" "$rc"
fi

if want 3; then
  python3 -I "$PY_HELPER" 3 "$BASE"
  rc=$?
  report 3 "부분 비교 0 · 적재 때 호출 0 (ast)" "$rc"
fi

if want 4; then
  python3 -I "$PY_HELPER" 4 "$BASE"
  rc=$?
  # shellcheck disable=SC2086
  git diff --cached --quiet "$BASE" -- $CALC || { rc=1; echo "  ★ 운영 코드(calc)가 스테이징에서 바뀌었다"; }
  # shellcheck disable=SC2086
  git diff --quiet "$BASE" -- $CALC || { rc=1; echo "  ★ 운영 코드(calc)가 작업 트리에서 바뀌었다"; }
  report 4 "경계(바뀐 경로·운영 코드 0·작업 트리 = 스테이징)" "$rc"
fi

if want 5; then
  (cd "$ROOT/apps/api-py" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s4-5.log" 2>&1
  rc=$?
  head -3 "$OUT/s4-5.log" | sed 's/^/  /'
  allowed=$(grep -o -E '허용 [0-9]+' "$OUT/s4-5.log" | head -1 | awk '{print $2}')
  echo "  허용 ${allowed:-?} (바닥 71)"
  [ "${allowed:-999}" -le 71 ] || rc=1
  report 5 "자리 규칙" "$rc"
fi

if want 6; then
  start="$(git status --porcelain)"
  caught=0
  mkdir -p "$OUT/planted"
  for p in P1 P2 P3 P4 P5 P6 P7 P8 P9 P10 P11 P12; do
    cp "$FACTS_PY" "$OUT/planted/$p.orig"
    PLANT_BACKUP="$OUT/planted/$p.orig"
    if python3 -I "$PY_HELPER" plant "$BASE" "$p"; then
      run_tests "$OUT/planted/$p.log"
      rc=$?
      red=$(grep -E '^FAILED ' "$OUT/planted/$p.log" | sed -E 's/^FAILED ([^ ]+).*/\1/' | tr '\n' ' ')
      newred=0
      for f in $NEWTESTS; do
        n=$(grep -c -E "^FAILED esgapi/reconcile/tests/$f::" "$OUT/planted/$p.log")
        newred=$((newred + n))
      done
      if [ "$rc" != 0 ] && [ "$newred" -gt 0 ]; then
        caught=$((caught + 1)); echo "  $p 빨강(새 파일 $newred): $red"
      elif [ "$rc" != 0 ]; then
        echo "  ★ $p 새 시험 초록(다른 빨강: $red)"
      else
        echo "  ★ $p 초록(종료 $rc)"
      fi
    fi
    cp "$OUT/planted/$p.orig" "$FACTS_PY"
    PLANT_BACKUP=""
    cmp -s "$OUT/planted/$p.orig" "$FACTS_PY" || echo "  ★ $p 되쓰기 실패: $FACTS_PY"
    [ "$(git status --porcelain)" = "$start" ] || echo "  ★ $p 뒤 git status 가 시작과 다르다"
  done
  echo "PLANTED=$caught/12"
  # shellcheck disable=SC2086
  git diff --quiet -- $CALC
  back=$?
  echo "  되쓴 뒤 git diff --quiet calc EXIT=$back"
  rc=0
  [ "$caught" = 12 ] && [ "$back" = 0 ] && [ "$(git status --porcelain)" = "$start" ] || rc=1
  report 6 "심은 파손 P1~P12" "$rc"
fi

if want 7; then
  cache_before="$(ls ~/.cache/esg-weekly/ 2>/dev/null)"
  C=$(git commit-tree "$(git write-tree)" -p HEAD -m 'FT1 staged (임시, ref 없음)')
  echo "  스테이징 트리 커밋 객체 $C"
  run_mutmut "$C" "$OUT/wr" "$OUT/mut" "$OUT/s4-7-weekly.log"
  rc=$?
  # shellcheck disable=SC2046
  python3 -I "$PY_HELPER" 7 "$BASE" "$OUT" "$KNOWN" "$BASEDIR" $(ls "$OUT"/mut/*/mutmut-results.txt) || rc=1
  [ "$(ls ~/.cache/esg-weekly/ 2>/dev/null)" = "$cache_before" ] || { rc=1; echo "  ★ ~/.cache/esg-weekly 가 바뀌었다"; }
  report 7 "mutmut 다시 재기(facts.py, 스테이징 트리)" "$rc"
fi

if want 8; then
  if [ -f "$MSG" ]; then
    python3 -I "$PY_HELPER" 8 "$BASE" "$MSG"
    rc=$?
  else
    echo "  ★ 커밋 메시지 초안이 없다: $MSG"
    rc=1
  fi
  report 8 "커밋 메시지 초안 트레일러" "$rc"
fi

echo "SECTION4_FAIL=$failed"
