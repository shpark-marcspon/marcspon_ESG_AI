#!/usr/bin/env bash
# 밴드 FC1(MARC-TICK-169) §4 의 자기검증. 실패 결과의 구조 칸을 전체 == 로 견주는 순수 시험(electricity·assemble·
# policy·sector·result_to_json·text_of·shape.check).
#   사용: apps/api-py/scripts/section4-FC1.sh [--step <n>[,<n>…]] [--planted] [--mutmut]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>. --planted 는 6단계(심은 파손, 끝 줄 PLANTED=<잡음>/7),
#   --mutmut 은 7단계만(대상 여섯 파일의 mutmut 을 다시 잰다 — 감독 허락 뒤에만 부른다).
#   --step 도 --planted 도 --mutmut 도 없으면 1~5.
# 커밋 전에는 스테이징된 트리를 잰다(git show ":<경로>", git diff --cached). 시험을 돌리는 1·6 단계는 작업 트리에서 도니
# 4단계가 「작업 트리 = 스테이징」을 함께 본다. 심은 파손은 cp 로 베끼고 되쓰고 cmp(checkout·restore·stash 0).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. 실제 LLM 호출 0, 키 파일 0, 컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=341dbb8a5be5b9a666bc138c06e05a9f7a5a5619
OUT="$ROOT/../FC1.out"
KNOWN=/Users/leedongeon/Desktop/marcspon/weekly/known-survivors.txt
mkdir -p "$OUT"

ONLY=""
PLANTED=0
MUTMUT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --mutmut) MUTMUT=1; shift ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--mutmut]" >&2; exit 2 ;;
  esac
done
if [ -z "$ONLY" ]; then
  if [ "$PLANTED" = 1 ]; then ONLY=6; elif [ "$MUTMUT" = 1 ]; then ONLY=7; else ONLY=1,2,3,4,5; fi
fi

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }

# 대상 시험(주간 ② 의 선택 안). django_db 파일(test_api.py·test_import.py)은 넣지 않는다.
TESTS="esgapi/reference/tests/test_assemble.py esgapi/reference/tests/test_calc_is_pure.py
esgapi/reference/tests/test_electricity.py esgapi/reference/tests/test_failures.py esgapi/reference/tests/test_golden.py
esgapi/reference/tests/test_jsonl.py esgapi/reference/tests/test_names.py esgapi/reference/tests/test_schemas.py
esgapi/reference/tests/test_value_raw.py esgapi/reference/tests/calc/test_types.py
esgapi/reconcile/tests/test_document.py esgapi/reconcile/tests/test_places.py esgapi/reconcile/tests/calc/test_shape.py"
MARK="not django_db and not security and not not_under_mutmut"
CALC="apps/api-py/esgapi/reference/calc apps/api-py/esgapi/reconcile/calc"

run_tests() {  # run_tests <출력 파일> [pytest 인자…]
  local log="$1"; shift
  # shellcheck disable=SC2086  # TESTS 는 빈칸으로 나눈 경로 목록이다
  (cd "$ROOT/apps/api-py" && uv run --frozen pytest -q $TESTS -m "$MARK" -p no:cacheprovider "$@") > "$log" 2>&1
}

PY_HELPER="$(mktemp -t s4fc1.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, re, subprocess, sys

MODE = sys.argv[1]
BASE = sys.argv[2]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


# 3: subset( 의 첫 인자가 실패 결과인 호출을 ast 로 센다(줄 나눔 무관).
# 실패 결과 = 실패를 내는 함수의 호출, 또는 그런 호출을 담은 이름(같은 함수 안의 대입).
FAILURE_CALLS = {"failure_of", "result_to_json", "_electricity", "failed", "raw"}
SUBSET_FILES = [
    "apps/api-py/esgapi/reference/tests/test_electricity.py",
    "apps/api-py/esgapi/reference/tests/test_assemble.py",
    "apps/api-py/esgapi/reference/tests/test_names.py",
    "apps/api-py/esgapi/reference/tests/test_failures.py",
    "apps/api-py/esgapi/reference/tests/calc/test_types.py",
    "apps/api-py/esgapi/reconcile/tests/calc/test_shape.py",
]


def callee(node):
    if isinstance(node, ast.Call):
        f = node.func
        return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    return None


def step3():
    bad = 0
    for path in SUBSET_FILES:
        source = git("show", f":{path}")
        tree = ast.parse(source)
        tainted = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and callee(node.value) in FAILURE_CALLS:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                tainted |= {t.id for t in targets if isinstance(t, ast.Name)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and callee(node) == "subset" and node.args):
                continue
            first = node.args[0]
            # subset(failure_of(…)[…], …) 꼴도 실패 결과로 본다
            root = first
            while isinstance(root, (ast.Subscript, ast.Attribute)):
                root = root.value
            hit = callee(root) in FAILURE_CALLS or (isinstance(root, ast.Name) and root.id in tainted)
            text = ast.get_source_segment(source, first)
            short = path.removeprefix("apps/api-py/esgapi/")
            if hit:
                bad += 1
                print(f"  ★ 실패 결과를 subset 으로: {short}:{node.lineno} {text}")
            else:
                print(f"  성공 쪽: {short}:{node.lineno} {text}")
    print(f"  실패 subset {bad}")
    return 1 if bad else 0


ALLOWED = re.compile(r"^apps/api-py/(esgapi/(reference|reconcile)/tests/.+|scripts/section4-FC1\.sh)$")


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
PLANTS = {
    "P1": ("apps/api-py/esgapi/reference/calc/electricity.py", 226, "value=text_of(given_period), ", ""),
    "P2": ("apps/api-py/esgapi/reference/calc/electricity.py", 309, 'criteria["기간"] = _period_text(gir["period"])', "pass"),
    "P3": ("apps/api-py/esgapi/reference/calc/policy.py", 48, 'reason="적용할 산정등급을 정하지 않았다 (기본값 없음)"', "reason=None"),
    "P4": ("apps/api-py/esgapi/reference/calc/sector.py", 71, "ksicCode=ksic_code", "ksicCode=None"),
    "P5": ("apps/api-py/esgapi/reference/calc/assemble.py", 96, "recordVersion=record.source.version", "recordVersion=None"),
    "P6": ("apps/api-py/esgapi/reference/calc/types.py", 229, '{"ok": False, "failure"', '{"ok": None, "failure"'),
    "P7": ("apps/api-py/esgapi/reconcile/calc/shape.py", 144, "ShapeProblem(here, ", "ShapeProblem(None, "),
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
TARGET = re.compile(
    r"^esgapi\.(reference\.calc\.(electricity|assemble|policy|sector|types)\.|reconcile\.calc\.shape\.x_check__)"
)


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


def step7():
    out, known_path, base_ga, *results = sys.argv[3:]
    with open(known_path, encoding="utf-8") as f:
        known = {l.split()[1] for l in f if l.startswith("### ")}
    with open(base_ga, encoding="utf-8") as f:
        before = {l.strip() for l in f if l.strip()}
    after = survivors(results) - known
    killed, remain, new = before - after, before & after, after - before
    for name, rows in (("after-ga.txt", after), ("killed.txt", killed), ("remain.txt", remain), ("new.txt", new)):
        with open(f"{out}/{name}", "w", encoding="utf-8") as f:
            f.write("".join(f"{n}\n" for n in sorted(rows)))

    def fn(n):
        return re.sub(r"__mutmut_[0-9]+$", "", n)

    funcs = sorted({fn(n) for n in before | after})
    with open(f"{out}/mut-table.md", "w", encoding="utf-8") as f:
        f.write("| 함수 | 앞(가) | 뒤(가) | 죽음 | 새로 남 |\n|---|---:|---:|---:|---:|\n")
        for g in funcs:
            b = sum(1 for n in before if fn(n) == g)
            a = sum(1 for n in after if fn(n) == g)
            k = sum(1 for n in killed if fn(n) == g)
            w = sum(1 for n in new if fn(n) == g)
            f.write(f"| {g} | {b} | {a} | {k} | {w} |\n")
    print(f"MUT_KILLED={len(killed)}/{len(before)}")
    print(f"MUT_REMAIN={len(remain)}")
    print(f"MUT_NEW={len(new)}")
    return 0 if not new else 1


sys.exit({"3": step3, "4": step4, "plant": lambda: plant(sys.argv[3]), "7": step7}[MODE]())
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
  hits=$(git grep --cached -n -E 'subset\((failure_of|_electricity|result_to_json)' -- apps/api-py/esgapi/reference/tests | wc -l | tr -d ' ')
  echo "  한 줄 grep $hits"
  python3 -I "$PY_HELPER" 3 "$BASE"
  rc=$?
  [ "$hits" = 0 ] || rc=1
  report 3 "실패 결과를 subset 으로 견주는 호출 0 (ast)" "$rc"
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
  report 5 "자리 규칙" "$rc"
fi

if want 6; then
  start="$(git status --porcelain)"
  caught=0
  mkdir -p "$OUT/planted"
  for p in P1 P2 P3 P4 P5 P6 P7; do
    case "$p" in
      P1|P2) file=apps/api-py/esgapi/reference/calc/electricity.py ;;
      P3) file=apps/api-py/esgapi/reference/calc/policy.py ;;
      P4) file=apps/api-py/esgapi/reference/calc/sector.py ;;
      P5) file=apps/api-py/esgapi/reference/calc/assemble.py ;;
      P6) file=apps/api-py/esgapi/reference/calc/types.py ;;
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
  echo "PLANTED=$caught/7"
  # shellcheck disable=SC2086
  git diff --quiet -- $CALC
  back=$?
  echo "  되쓴 뒤 git diff --quiet calc EXIT=$back"
  rc=0
  [ "$caught" = 7 ] && [ "$back" = 0 ] && [ "$(git status --porcelain)" = "$start" ] || rc=1
  report 6 "심은 파손 P1~P7" "$rc"
fi

if want 7; then
  cache_before="$(ls ~/.cache/esg-weekly/ 2>/dev/null)"
  common="$(git rev-parse --path-format=absolute --git-common-dir)"
  [ -e "$common/verify.lock" ] && echo "  ★ verify.lock 있음" || echo "  verify.lock 없음"
  uptime | sed 's/^/  시작 부하: /'
  vm_stat | head -3 | sed 's/^/  /'
  C=$(git commit-tree "$(git write-tree)" -p HEAD -m 'FC1 staged (임시, ref 없음)')
  echo "  스테이징 트리 커밋 객체 $C"
  rm -rf "$OUT/mut"
  t0=$(date +%s)
  WEEKLY_WORK_ROOT="$OUT/wr" scripts/weekly.sh --commit "$C" --mutmut-only --out "$OUT/mut" \
    --known "$KNOWN" --only esgapi/reference/calc/electricity.py --only esgapi/reference/calc/assemble.py \
    --only esgapi/reference/calc/policy.py --only esgapi/reference/calc/sector.py \
    --only esgapi/reference/calc/types.py --only esgapi/reconcile/calc/shape.py > "$OUT/s4-7-weekly.log" 2>&1
  wrc=$?
  echo "  weekly 종료 $wrc · $(( $(date +%s) - t0 ))초"
  uptime | sed 's/^/  끝 부하: /'
  tail -3 "$OUT/s4-7-weekly.log" | sed 's/^/  /'
  rc=$wrc
  grep -q '^WEEKLY=OK' "$OUT/s4-7-weekly.log" || rc=1
  # shellcheck disable=SC2046
  python3 -I "$PY_HELPER" 7 "$BASE" "$OUT" "$KNOWN" "$OUT/base-ga.txt" $(ls "$OUT"/mut/*/mutmut-results.txt) || rc=1
  [ "$(ls ~/.cache/esg-weekly/ 2>/dev/null)" = "$cache_before" ] || { rc=1; echo "  ★ ~/.cache/esg-weekly 가 바뀌었다"; }
  report 7 "mutmut 다시 재기(대상 여섯 파일)" "$rc"
fi

echo "SECTION4_FAIL=$failed"
