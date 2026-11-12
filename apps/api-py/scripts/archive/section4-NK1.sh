#!/usr/bin/env bash
# 밴드 NK1(MARC-TICK-170) §4 의 자기검증. reconcile 의 숫자 읽기·종류·문서 입력표를 전체 == 로 견주는 순수 시험
# (scan_numbers 부호·_token_kind 갈래·classify_cell·locate_quote·kind_of 경계·kinds 눈금·validate_document), 그리고
# test_places 의 적재 때 값을 함수 범위 고정물로 옮긴 것.
#   사용: apps/api-py/scripts/section4-NK1.sh [--step <n>[,<n>…]] [--planted] [--mutmut] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>. --planted 는 6단계(심은 파손, 끝 줄 PLANTED=<잡음>/10),
#   --mutmut 은 7단계만(대상 네 파일의 mutmut 을 다시 잰다 — 감독 허락 뒤에만 부른다), --msg 는 8단계만(커밋 메시지
#   초안의 트레일러). --step 도 --planted 도 --mutmut 도 --msg 도 없으면 1~5 와 8(초안은 NK1.out/commit-msg.txt).
# 출력 자리는 S4_OUT(기본 NK1.out). 검증자는 S4_OUT=…/NK1.verify 로 돌려 러너 기록을 덮지 않는다. 바닥 파일
# (base-ga.txt·base-surv.txt·base-ga-diffs.txt)과 커밋 메시지 초안은 늘 NK1.out 에서 읽는다.
# 커밋 전에는 스테이징된 트리를 잰다(git show ":<경로>", git diff --cached). 시험을 돌리는 1·6 단계는 작업 트리에서 도니
# 4단계가 「작업 트리 = 스테이징」을 함께 본다. 심은 파손은 cp 로 베끼고 되쓰고 cmp(checkout·restore·stash 0).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. 실제 LLM 호출 0, 키 파일 0, 컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=175c73d3084e851182952028474edcc31e385caf
BASEDIR="$ROOT/../NK1.out"
OUT="${S4_OUT:-$ROOT/../NK1.out}"
KNOWN=/Users/leedongeon/Desktop/marcspon/weekly/known-survivors.txt
mkdir -p "$OUT"

ONLY=""
PLANTED=0
MUTMUT=0
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --mutmut) MUTMUT=1; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--mutmut] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
if [ -z "$ONLY" ]; then
  if [ "$PLANTED" = 1 ]; then ONLY=6; elif [ "$MUTMUT" = 1 ]; then ONLY=7; elif [ -n "$MSG" ]; then ONLY=8; else ONLY=1,2,3,4,5,8; fi
fi
[ -n "$MSG" ] || MSG="$BASEDIR/commit-msg.txt"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }

# 대상 시험(주간 ② 의 선택 안). 폴더째가 아니라 파일을 나열한다(폴더를 넘기면 django_db 파일까지 모인다).
TESTS="esgapi/reconcile/tests/test_notation.py esgapi/reconcile/tests/test_kinds.py
esgapi/reconcile/tests/test_document.py esgapi/reconcile/tests/test_places.py esgapi/reconcile/tests/test_facts.py
esgapi/reconcile/tests/test_golden_synthetic.py esgapi/reconcile/tests/calc/test_shape.py
esgapi/reconcile/tests/calc/test_notation.py esgapi/reconcile/tests/calc/test_kinds.py
esgapi/reconcile/tests/calc/test_document.py"
MARK="not django_db and not security and not not_under_mutmut"
CALC="apps/api-py/esgapi/reference/calc apps/api-py/esgapi/reconcile/calc"

run_tests() {  # run_tests <출력 파일> [pytest 인자…]
  local log="$1"; shift
  # shellcheck disable=SC2086  # TESTS 는 빈칸으로 나눈 경로 목록이다
  (cd "$ROOT/apps/api-py" && uv run --frozen pytest -q $TESTS -m "$MARK" -p no:cacheprovider "$@") > "$log" 2>&1
}

PY_HELPER="$(mktemp -t s4nk1.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, re, subprocess, sys

MODE = sys.argv[1]
BASE = sys.argv[2]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


NEW_FILES = [
    "apps/api-py/esgapi/reconcile/tests/calc/test_notation.py",
    "apps/api-py/esgapi/reconcile/tests/calc/test_kinds.py",
    "apps/api-py/esgapi/reconcile/tests/calc/test_document.py",
]
# 3(a): 결과 전체를 내는 호출. extract_document 는 `.kinds` 를 붙였을 때만(그 자체가 종류 표 전체다).
# kinds_of·kinds_in 은 calc/test_kinds.py 의 도우미로, extract_document(…).kinds 를 그대로 돌려준다.
RESULT_CALLS = {"scan_numbers", "classify_cell", "locate_quote", "classify_kinds", "kind_of", "validate_document",
                "_round_pair", "_evenly_spaced", "kinds_of", "kinds_in"}
# 허용: ==/is 의 한 쪽 전체 · isinstance 의 첫 인자 · len() · return(도우미가 그대로 돌려줌).
ALLOWED_COMPARE = (ast.Eq, ast.Is)
# 3(b): 모듈 몸(함수 밖·데코레이터·기본값)에서 부르면 안 되는 대상 함수(§1-4).
TARGETS = {"scan_numbers", "classify_cell", "locate_quote", "kind_of", "classify_kinds", "_round_pair",
           "_evenly_spaced", "validate_document", "read_fields", "check", "extract_document"}


def callee(node):
    if isinstance(node, ast.Call):
        f = node.func
        return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    return None


def is_producer(node, tainted):
    if isinstance(node, ast.Call) and callee(node) in RESULT_CALLS:
        return True
    if isinstance(node, ast.Attribute) and node.attr == "kinds" and callee(node.value) == "extract_document":
        return True
    return isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in tainted


def step3():
    bad = 0
    for path in NEW_FILES:
        source = git("show", f":{path}")
        tree = ast.parse(source)
        short = path.removeprefix("apps/api-py/esgapi/reconcile/tests/")
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        tainted = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None and is_producer(node.value, set()):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                tainted |= {t.id for t in targets if isinstance(t, ast.Name)}
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
            elif isinstance(up, ast.Call) and node is not up.func:
                name = callee(up)
                if not ((name == "isinstance" and up.args and up.args[0] is node) or name == "len"):
                    why = f"{name}() 의 인자"
            elif isinstance(up, ast.keyword):
                why = "다른 함수의 인자"
            if why:
                bad += 1
                print(f"  ★ 부분 비교({why}): {short}:{node.lineno} {text}")
            else:
                kind = type(up).__name__
                print(f"  전체({kind}): {short}:{node.lineno} {text}")
        # (b) 적재 때 호출·cache·모듈 범위 고정물
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
    print(f"  ★ 합 {bad}")
    return 1 if bad else 0


ALLOWED = re.compile(r"^apps/api-py/(esgapi/reconcile/tests/.+|scripts/section4-NK1\.sh)$")


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


# 6: 심은 파손. (번호, 파일, 줄, 바꿀 글자, 새 글자)
NOTATION = "apps/api-py/esgapi/reconcile/calc/notation.py"
KINDS = "apps/api-py/esgapi/reconcile/calc/kinds.py"
DOCUMENT = "apps/api-py/esgapi/reconcile/calc/document.py"
PLANTS = {
    "P1": (NOTATION, 333, 'sign = "triangle_negative"', 'sign = "minus"'),
    "P2": (NOTATION, 342, "unit = pct", "unit = None"),
    "P3": (NOTATION, 247, "start >= a and end <= b", "start > a and end <= b"),
    "P4": (NOTATION, 263, "and len(num) <= 2", "and len(num) <= 3"),
    "P5": (KINDS, 97, "len(digits) <= 2", "len(digits) <= 3"),
    "P6": (KINDS, 171, "return step > 0 and", "return step >= 0 and"),
    "P7": (KINDS, 233, "per_block.get(fact.where.block_id, 0) + 1", "per_block.get(None, 0) + 1"),
    "P8": (DOCUMENT, 107, "(raw[0], raw[1], raw[2], raw[3])", "(raw[1], raw[1], raw[2], raw[3])"),
    "P9": (DOCUMENT, 127, 'method=t["method"],', "method=None,"),
    "P10": ("apps/api-py/esgapi/reconcile/calc/shape.py", 89, 'ReadField(path, "integer", required)',
            'ReadField(path, "string", required)'),
}


def plant(name):
    path, line, old, new = PLANTS[name]
    with open(path, encoding="utf-8") as f:
        rows = f.read().split("\n")
    row = rows[line - 1]
    if row.count(old) != 1:
        print(f"  ★ {name} {path}:{line} 에 「{old}」 가 하나가 아니다: {row.strip()}")
        return 1
    rows[line - 1] = row.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))
    print(f"  {name} {path}:{line}: {row.strip()}  →  {rows[line - 1].strip()}")
    return 0


# 7: 견주기. 결과 파일의 생존(killed 아님) 이름 가운데 known 에 없는 것.
TARGET = re.compile(r"^esgapi\.reconcile\.calc\.(notation|kinds|document|shape)\.")


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


def group(name):
    fn = re.sub(r"__mutmut_[0-9]+$", "", name).rsplit(".", 1)[1]
    return {"x_scan_numbers": "표 7", "x_read_fields": "표 8", "x_kind_of": "표 10", "x__token_kind": "표 11",
            "x__round_pair": "표 15", "x_classify_kinds": "표 15", "x_validate_document": "표 16",
            "x__box": "표 16", "x_read_source": "표 16"}.get(fn, "나머지")


def step7():
    out, known_path, basedir, *results = sys.argv[3:]
    with open(known_path, encoding="utf-8") as f:
        known = {l.split()[1] for l in f if l.startswith("### ")}
    with open(f"{basedir}/base-ga.txt", encoding="utf-8") as f:
        before = {l.strip() for l in f if l.strip()}
    with open(f"{basedir}/base-surv.txt", encoding="utf-8") as f:
        base_surv = {l.strip() for l in f if l.strip()}
    alive = survivors(results)
    after = alive - known
    killed, remain, new = before - after, before & after, after - before
    known_died = (base_surv & known) - alive
    for name, rows in (("after-ga.txt", after), ("killed.txt", killed), ("remain.txt", remain), ("new.txt", new),
                       ("known-died.txt", known_died)):
        with open(f"{out}/{name}", "w", encoding="utf-8") as f:
            f.write("".join(f"{n}\n" for n in sorted(rows)))

    def fn(n):
        return re.sub(r"__mutmut_[0-9]+$", "", n)

    funcs = sorted({fn(n) for n in before | after})
    with open(f"{out}/mut-table.md", "w", encoding="utf-8") as f:
        f.write("| 함수 | 무리 | 앞(가) | 뒤(가) | 죽음 | 새로 남 |\n|---|---|---:|---:|---:|---:|\n")
        for g in funcs:
            b = sum(1 for n in before if fn(n) == g)
            a = sum(1 for n in after if fn(n) == g)
            k = sum(1 for n in killed if fn(n) == g)
            w = sum(1 for n in new if fn(n) == g)
            f.write(f"| {g.removeprefix('esgapi.reconcile.calc.')} | {group(g + '__mutmut_0')} | {b} | {a} | {k} | {w} |\n")
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


sys.exit({"3": step3, "4": step4, "plant": lambda: plant(sys.argv[3]), "7": step7, "8": step8}[MODE]())
PYEOF

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
  for p in P1 P2 P3 P4 P5 P6 P7 P8 P9 P10; do
    case "$p" in
      P1|P2|P3|P4) file=apps/api-py/esgapi/reconcile/calc/notation.py ;;
      P5|P6|P7) file=apps/api-py/esgapi/reconcile/calc/kinds.py ;;
      P8|P9) file=apps/api-py/esgapi/reconcile/calc/document.py ;;
      *) file=apps/api-py/esgapi/reconcile/calc/shape.py ;;
    esac
    cp "$file" "$OUT/planted/$p.orig"
    if python3 -I "$PY_HELPER" plant "$BASE" "$p"; then
      run_tests "$OUT/planted/$p.log"
      rc=$?
      red=$(grep -E '^FAILED ' "$OUT/planted/$p.log" | sed -E 's/^FAILED ([^ ]+).*/\1/' | tr '\n' ' ')
      if [ "$rc" != 0 ] && [ -n "$red" ]; then caught=$((caught + 1)); echo "  $p 빨강: $red"; else echo "  ★ $p 초록(종료 $rc)"; fi
    fi
    cp "$OUT/planted/$p.orig" "$file"
    cmp -s "$OUT/planted/$p.orig" "$file" || echo "  ★ $p 되쓰기 실패: $file"
    [ "$(git status --porcelain)" = "$start" ] || echo "  ★ $p 뒤 git status 가 시작과 다르다"
  done
  echo "PLANTED=$caught/10"
  # shellcheck disable=SC2086
  git diff --quiet -- $CALC
  back=$?
  echo "  되쓴 뒤 git diff --quiet calc EXIT=$back"
  rc=0
  [ "$caught" = 10 ] && [ "$back" = 0 ] && [ "$(git status --porcelain)" = "$start" ] || rc=1
  report 6 "심은 파손 P1~P10" "$rc"
fi

if want 7; then
  cache_before="$(ls ~/.cache/esg-weekly/ 2>/dev/null)"
  common="$(git rev-parse --path-format=absolute --git-common-dir)"
  [ -e "$common/verify.lock" ] && echo "  ★ verify.lock 있음" || echo "  verify.lock 없음"
  uptime | sed 's/^/  시작 부하: /'
  vm_stat | head -3 | sed 's/^/  /'
  C=$(git commit-tree "$(git write-tree)" -p HEAD -m 'NK1 staged (임시, ref 없음)')
  echo "  스테이징 트리 커밋 객체 $C"
  rm -rf "$OUT/mut"
  t0=$(date +%s)
  WEEKLY_WORK_ROOT="$OUT/wr" scripts/weekly.sh --commit "$C" --mutmut-only --out "$OUT/mut" \
    --known "$KNOWN" --only esgapi/reconcile/calc/notation.py --only esgapi/reconcile/calc/kinds.py \
    --only esgapi/reconcile/calc/document.py --only esgapi/reconcile/calc/shape.py > "$OUT/s4-7-weekly.log" 2>&1
  wrc=$?
  echo "  weekly 종료 $wrc · $(( $(date +%s) - t0 ))초"
  uptime | sed 's/^/  끝 부하: /'
  tail -3 "$OUT/s4-7-weekly.log" | sed 's/^/  /'
  rc=$wrc
  grep -q '^WEEKLY=OK' "$OUT/s4-7-weekly.log" || rc=1
  grep -h -E '^(mutmut_done|targets_count|targets_source|mutmut_wall|rev_hash|result|work_removed)=' "$OUT"/mut/*/meta.txt | sed 's/^/  meta /'
  # shellcheck disable=SC2046
  python3 -I "$PY_HELPER" 7 "$BASE" "$OUT" "$KNOWN" "$BASEDIR" $(ls "$OUT"/mut/*/mutmut-results.txt) || rc=1
  [ "$(ls ~/.cache/esg-weekly/ 2>/dev/null)" = "$cache_before" ] || { rc=1; echo "  ★ ~/.cache/esg-weekly 가 바뀌었다"; }
  report 7 "mutmut 다시 재기(대상 네 파일)" "$rc"
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
