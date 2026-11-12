#!/usr/bin/env bash
# 밴드 TR1b(MARC-TICK-193) §4 의 자기검증. 영문번역의 Word 쪽(tools/docx_reader·outputs)을 잰다. section4-TR1a.sh 판별 복사.
#   사용: apps/api-py/scripts/section4-TR1b.sh [--step <n>[,<n>…]] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0. 아무것도 없으면 1~17 전부.
#   그 커밋에 닿지 않는 단계(예: ②③ 의 17)는 「해당 없음」을 찍고 EXIT=0 이다(커밋 경계로 판정 — 파일 유무가 아니라).
#   --msg 는 14단계가 함께 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 있으면).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/TR1b.out). 검증자는 S4_OUT=…/TR1b.verify 로 돌려 러너 기록을 덮지 않는다.
# BASE 트리의 값(1 의 시간, 5 의 계약 수, 10 의 노드 id)은 `git archive BASE` 를 $S4_OUT/base-tree 에 풀어 한 번 재고
#   $S4_OUT/base-*.txt 에 둔다(다음 실행은 그 값을 쓴다).
# 읽기판(받은 코랩의 뽑은 판)은 워크트리 밖이다 — MARCSPON_ROOT(기본 워크트리의 ../..) 아래에서 읽고, 못 읽으면 FAIL.
#   읽기판의 글은 이 스크립트에도 출력에도 싣지 않는다(이름·sha·수·EXIT 만).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. LLM·네트워크·키 파일 0. 컨테이너는 17(커밋 ①)만 —
#   빌드는 scripts/with-build-lock.sh 로, compose 프로젝트는 -p esg-app-tr1b 로 못박고, 띄운 것은 run --rm 이 내린다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=181a483745404fb49f916c8642743961668156e8
PROJECT=esg-app-tr1b
OUT="${S4_OUT:-$ROOT/../TR1b.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
READING="$MARCSPON_ROOT/received-derived/2026-10-15/영문번역 코랩/보고서_AI번역_v3_1.md"
API="$ROOT/apps/api-py"
TR=esgapi/translation
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
[ -n "$MSG" ] || MSG="$OUT/commit-msg.txt"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }
echo "BASE=$BASE HEAD=$(git rev-parse HEAD)"

# 지금 커밋 경계: BASE 이후 TR1b 커밋 수 + 스테이징이 있으면 1.
done_commits=$(git log --format=%s "$BASE..HEAD" | grep -c -E '^(build\(api-py\)|feat\(translation\)|fix\(translation\)): TR1b ')
staged_n=$(git diff --cached --name-only | grep -c .)
CB=$((done_commits + (staged_n > 0 ? 1 : 0)))
[ "$CB" -ge 1 ] || CB=1
[ "$CB" -le 4 ] || CB=4  # 커밋 ④ = 병합 전 가지 리뷰의 고침(감독)
echo "커밋 경계 ${CB}(커밋 ${done_commits} + 스테이징 ${staged_n} 경로)"

base_tree() {  # BASE 트리를 한 번 푼다
  if [ ! -f "$OUT/base-tree/.unpacked" ]; then
    rm -rf "$OUT/base-tree"
    mkdir -p "$OUT/base-tree"
    git archive "$BASE" | tar -x -C "$OUT/base-tree"
    : > "$OUT/base-tree/.unpacked"
  fi
}
base_api() { base_tree; (cd "$OUT/base-tree/apps/api-py" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }

PY_HELPER="$(mktemp -t s4tr1b.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import os, re, subprocess, sys, tomllib

MODE, BASE, CB = sys.argv[1], sys.argv[2], int(sys.argv[3])
API = "apps/api-py/"
TR = API + "esgapi/translation/"
DOCX_FILES = {TR + f for f in ("tools/docx_reader.py", "outputs/docx_bilingual.py", "outputs/docx_qa.py", "outputs/readback.py")}


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def git_bytes(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def untracked():
    return git("ls-files", "--others", "--exclude-standard").splitlines()


def changed():
    return sorted(set(git("diff", "--name-only", BASE).splitlines()) | set(untracked()))


def new_files():
    """BASE 에 없던 파일(스테이징·커밋·추적 밖 모두)."""
    added = git("diff", "--name-only", "--diff-filter=A", BASE).splitlines()
    return sorted(set(added) | set(untracked()))


def added_lines_by_file():
    """파일 → BASE 이후 더한 줄(추적 파일의 diff ^+ 와 추적 밖 새 파일 전부)."""
    out, current = {}, None
    for l in git("diff", "-U0", BASE).splitlines():
        if l.startswith("+++ "):
            current = l[6:] if l.startswith("+++ b/") else None
        elif l.startswith("+") and current is not None:
            out.setdefault(current, []).append(l[1:])
    for f in untracked():
        try:
            out[f] = open(f, encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            out[f] = [f"<바이너리 {f}>"]
    return out


def added_lines():
    return [l for lines in added_lines_by_file().values() for l in lines]


ALLOWED = re.compile(
    r"^(apps/api-py/esgapi/translation/tools/docx_(reader|dump)\.py"
    r"|apps/api-py/esgapi/translation/outputs/.*"
    r"|apps/api-py/esgapi/translation/tests/.*"
    r"|apps/api-py/esgapi/translation/contracts/shapes\.py"
    r"|apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure\.py"  # 감독 처분 — 경계 :149 한 줄
    r"|apps/api-py/(pyproject\.toml|uv\.lock|\.importlinter)"
    r"|README\.md"
    r"|apps/api-py/scripts/(section4|planted-breaks)-TR1b\.sh)$"
)
SCHEMA_FILES = (TR + "tests/data/flow-shapes/translation.input@1.schema.json",
                TR + "tests/data/flow-shapes/translation.result@1.schema.json")
# 처분 ⑭ 표(BASE 181a483 의 줄): (앞 줄, 더한 줄, 들어가는 커밋, 자리 — "once" 파일에 한 곳 · "end" 파일 끝 두 줄)
#   차 의 앞뒤 줄 짝(dataverify → translation)은 가·나·바 에도 이미 있어 파일 끝 자리로 가른다.
LINT_ROWS = [
    ("    esgapi.translation.tools", "    esgapi.translation.outputs", 2, "once"),  # 다 source :113 뒤
    ("    esgapi.dataverify", "    esgapi.translation", 1, "end"),  # 차 forbidden :347 뒤(파일 끝)
]


def step4():
    bad = 0
    stat = git("diff", "--numstat", BASE, "--", TR + "contracts/shapes.py").split()
    plus, minus = (int(stat[0]), int(stat[1])) if stat else (0, 0)
    print(f"  shapes.py 더함 {plus} · 지움 {minus}")
    if plus > 2 or minus > 1:
        bad += 1
    for f in (*SCHEMA_FILES, TR + "contracts/wire.py"):
        if subprocess.run(["git", "diff", "--quiet", BASE, "--", f]).returncode != 0:
            print(f"  ★ {f} 가 바뀌었다")
            bad += 1
    return bad


def step6():
    bad = 0
    diff = git("diff", "-U0", BASE, "--", API + ".importlinter").splitlines()
    minus = [l for l in diff if re.match(r"^-[^-]", l)]
    plus = [l[1:] for l in diff if re.match(r"^\+[^+]", l)]
    rows = [(a, t, where) for a, t, c, where in LINT_ROWS if c <= CB]
    print(f"  .importlinter: 지운 줄 {len(minus)} · 더한 줄 {len(plus)} · 표의 줄(커밋 {CB} 까지) {len(rows)}")
    if minus or sorted(plus) != sorted(t for _, t, _ in rows):
        bad += 1
        print("  ★ 더한 줄이 처분 ⑭ 표와 다르다")
    lines = open(API + ".importlinter", encoding="utf-8").read().split("\n")
    filled = [l for l in lines if l.strip()]
    for anchor, text, where in rows:
        hits = [i for i in range(len(lines) - 1) if lines[i] == anchor and lines[i + 1] == text]
        ok = len(hits) == 1 if where == "once" else filled[-2:] == [anchor, text]
        print(f"  {'' if ok else '★ '}{anchor.strip()} 뒤의 {text.strip()} — {where}(짝 {len(hits)} 곳)")
        bad += 0 if ok else 1
    return bad


def lock_packages(text):
    return {p["name"]: p for p in tomllib.loads(text)["package"]}


def step7():
    bad = 0
    diff = git("diff", "-U0", BASE, "--", API + "pyproject.toml").splitlines()
    minus = [l for l in diff if re.match(r"^-[^-]", l)]
    pins = [l[1:].strip() for l in diff if re.match(r"^\+[^+]", l) and "==" in l]
    print(f"  pyproject: 지운 줄 {len(minus)} · 더한 == 줄 {pins}")
    if minus or pins != ['"python-docx==1.2.0",', '"lxml==6.1.3",']:
        bad += 1
    base = lock_packages(git("show", f"{BASE}:{API}uv.lock"))
    head = lock_packages(open(API + "uv.lock", encoding="utf-8").read())
    new = sorted(set(head) - set(base))
    gone = sorted(set(base) - set(head))
    print(f"  uv.lock: 새 패키지 {new} · 사라진 패키지 {gone}")
    if new != ["lxml", "python-docx"] or gone:
        bad += 1
    changed_pkgs = []
    for name, pkg in base.items():
        if name == "esgapi" or name not in head:
            continue
        for key in ("version", "source", "sdist", "wheels", "dependencies"):
            if pkg.get(key) != head[name].get(key):
                changed_pkgs.append(f"{name}.{key}")
    print(f"  있던 패키지의 version·source·sdist·wheels·dependencies 바뀜 {len(changed_pkgs)} {changed_pkgs[:5]}")
    bad += int(bool(changed_pkgs))
    bdeps = {d["name"] for d in base["esgapi"].get("dependencies", [])}
    hdeps = {d["name"] for d in head["esgapi"].get("dependencies", [])}
    bmeta = {d["name"] for d in base["esgapi"]["metadata"]["requires-dist"]}
    hmeta = {d["name"] for d in head["esgapi"]["metadata"]["requires-dist"]}
    print(f"  esgapi 의 의존 차이 {sorted(hdeps - bdeps)}·{sorted(bdeps - hdeps)} · requires-dist 차이 {sorted(hmeta - bmeta)}·{sorted(bmeta - hmeta)}")
    if hdeps - bdeps != {"lxml", "python-docx"} or bdeps - hdeps or hmeta - bmeta != {"lxml", "python-docx"} or bmeta - hmeta:
        bad += 1
    return bad


def step12():
    pats = ["anthropic.Anthropic(", "load_live", "os.environ", "urlopen", "requests.", "socket."]
    hits = [(f, l) for f, lines in added_lines_by_file().items() for l in lines
            if any(p in l for p in pats) and "pats = [" not in l and not f.endswith("section4-TR1b.sh")]
    for f, l in hits:
        print(f"  ★ {f}: {l.strip()[:100]}")
    own = open(API + "esgapi/core/llm/providers/anthropic.py", encoding="utf-8").read()
    pos = sum(1 for l in own.splitlines() if any(p in l for p in pats))
    print(f"  diff ^+ 의 실호출·네트워크 무늬 {len(hits)}(이 스크립트 자신은 뺌) · 양성 대조(core anthropic.py 의 줄) {pos}")
    return int(bool(hits) or pos == 0)


def step13():
    bad = 0
    for f in changed():
        ok = ALLOWED.match(f) and "__pycache__" not in f
        print(f"  {'' if ok else '★ 허용 밖 '}{f}")
        bad += 0 if ok else 1
    return bad


COMMON = {"The", "This", "These", "Those", "We", "Our", "It", "In", "As", "Through", "Building", "Having", "Guided",
          "Against", "With", "By", "For", "From"}


def names_from_reading(reading):
    """읽기판 R/2449(정규식 갈래)과 R/375(함수 이름)에서 이름을 뽑는다 — 이 파일에 이름 글자 0."""
    lines = open(reading, encoding="utf-8").read().split("\n")
    m = re.search(r"\(\?:([A-Za-z|]+)\)\\b", lines[2448])
    f = re.search(r"def glossary_to_(\w+)_text", lines[374])
    if not m or not f:
        raise SystemExit("  ★ 읽기판 R/2449·R/375 에서 갈래·함수 이름을 못 찾았다")
    names = [x for x in m.group(1).split("|") if x not in COMMON]
    return names, f.group(1), lines[2448]


def boundary(word, flags=0):
    return re.compile(r"(^|[^A-Za-z])" + re.escape(word) + r"([^A-Za-z]|$)", flags)


def step14(reading, msg, report):
    bad = 0
    names, frag, line2449 = names_from_reading(reading)
    pats = [boundary(n) for n in names] + [boundary(frag, re.IGNORECASE)]
    pos = sum(1 for p in pats[:-1] if p.search(line2449))
    print(f"  이름 {len(names)}(일반 낱말 {len(COMMON)} 뺌) · 양성 대조: R/2449 줄에서 {pos}/{len(names)}")
    if len(names) != 9 or pos != 9:
        bad += 1
    texts = {"diff ^+": added_lines(), "커밋 메시지": git("log", "--format=%B", f"{BASE}..HEAD").splitlines()}
    for name, path in (("메시지 초안", msg), ("보고", report)):
        if os.path.isfile(path):
            texts[name] = open(path, encoding="utf-8").read().splitlines()
    key = re.compile(r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{20,}|" + "sk-" + "ant-)")
    fake = "sk" + "-" + "A" * 24
    if not key.search(f"x {fake}") or key.search("Risk-Response-Strengthening Governance"):
        print("  ★ 키 꼴 양성·음성 대조 실패")
        bad += 1
    tag = re.compile(r"\[고객사\]|\[Client\]|\[Pe" + r"er|\[자회사\]")
    for name, lines in texts.items():
        n = sum(1 for l in lines if any(p.search(l) for p in pats))
        k = sum(1 for l in lines if key.search(l))
        t = sum(1 for l in lines if tag.search(l)) if name in ("diff ^+", "커밋 메시지") else 0
        print(f"  {name}: 줄 {len(lines)} · 실명 {n} · 키 꼴 {k} · 바꿈 표지 {t}")
        bad += n + k + t
    exts = [f for f in new_files() if re.search(r"\.(docx|dotx|docm|zip|xlsx|xls|csv|ipynb)$", f)]
    signed = []
    for f in new_files():
        if os.path.isfile(f):
            with open(f, "rb") as handle:
                if handle.read(4) == b"PK\x03\x04":
                    signed.append(f)
    print(f"  새 파일 {len(new_files())} · docx·dotx·docm·zip·xlsx·xls·csv·ipynb 경로 {len(exts)} · zip 서명 파일 {len(signed)}")
    bad += len(exts) + len(signed)
    company = []
    for f in changed():
        if f.startswith(TR + "tests/") and os.path.isfile(f):
            company += re.findall(r'"name":[ ]*"([^"]*)"', open(f, encoding="utf-8").read())
    odd = [c for c in company if not (c.startswith("가상") or c.startswith("ABC Corp"))]
    print(f"  시험 자료의 회사 이름 칸 {len(company)} · 가상·ABC Corp 밖 {len(odd)}")
    return bad + len(odd)


def step16():
    head = "# py" + "right:"  # 이 파일의 줄이 스스로 걸리지 않게 나눠 적는다
    ignore = re.compile("py" + "right: ignore|type" + ": ignore")
    cast = re.compile("ca" + r"st\(")
    noqa = re.compile("# no" + "qa: S")
    bad = 0
    counts = {"머리 완화": 0, "ignore": 0, "cast": 0, "noqa S": 0}
    for f, lines in sorted(added_lines_by_file().items()):
        if f.endswith("section4-TR1b.sh"):
            continue
        for l in lines:
            s = l.strip()
            if s.startswith(head):
                counts["머리 완화"] += 1
                where = "" if f in DOCX_FILES else "★ 넷 밖 "
                bad += int(bool(where))
                print(f"  {where}머리 완화 {f}: {s[:100]}")
            elif ignore.search(l):
                counts["ignore"] += 1
                print(f"  ignore {f}: {s[:100]}")
            if cast.search(l):
                counts["cast"] += 1
                print(f"  cast {f}: {s[:100]}")
            if noqa.search(l):
                counts["noqa S"] += 1
                print(f"  noqa {f}: {s[:100]}")
    print("  " + " · ".join(f"{k} {v}" for k, v in counts.items()))
    return bad


if MODE == "4":
    sys.exit(min(step4(), 1))
elif MODE == "6":
    sys.exit(min(step6(), 1))
elif MODE == "7":
    sys.exit(min(step7(), 1))
elif MODE == "12":
    sys.exit(step12())
elif MODE == "13":
    sys.exit(min(step13(), 1))
elif MODE == "14":
    sys.exit(min(step14(sys.argv[4], sys.argv[5], sys.argv[6]), 1))
elif MODE == "16":
    sys.exit(min(step16(), 1))
PYEOF

reading_ok() {
  if [ ! -r "$READING" ]; then echo "  ★ 읽기판을 못 읽는다(MARCSPON_ROOT=$MARCSPON_ROOT)"; return 1; fi
  return 0
}
helper() { python3 -I "$PY_HELPER" "$1" "$BASE" "$CB" "${@:2}"; }

# 1. 순수 층 초록(시간은 BASE 와 함께)
if want 1; then
  start=$(date +%s)
  api uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$OUT/s1-pure.log" 2>&1
  code=$?
  took=$(( $(date +%s) - start ))
  if [ ! -f "$OUT/base-s1.txt" ]; then
    bstart=$(date +%s)
    base_api uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$OUT/base-s1.log" 2>&1
    echo "$? $(( $(date +%s) - bstart )) $(tail -1 "$OUT/base-s1.log")" > "$OUT/base-s1.txt"
  fi
  echo "  HEAD ${took}초 · $(tail -1 "$OUT/s1-pure.log")"
  echo "  BASE(종료 코드·초·끝 줄) $(cat "$OUT/base-s1.txt")"
  report 1 "순수 층 pytest" "$code"
fi

# 2. translation 표적(수집 수 — BASE 243 + 새 시험)
if want 2; then
  api uv run --frozen pytest -q -p no:cacheprovider esgapi/translation > "$OUT/s2-translation.log" 2>&1
  code=$?
  n=$(api uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi/translation 2>/dev/null | grep -c '::')
  echo "  $(tail -1 "$OUT/s2-translation.log") · 수집 $n(BASE 243 + $((n - 243)))"
  report 2 "pytest $TR" "$code"
fi

# 3. 바이트 0
if want 3; then
  git diff --quiet "$BASE" -- apps/api-py/generated apps/web docker compose.yaml scripts docs \
    apps/api-py/esgapi/core apps/api-py/esgapi/runs apps/api-py/esgapi/config apps/api-py/esgapi/greenwash \
    apps/api-py/esgapi/dataverify apps/api-py/esgapi/inventory apps/api-py/esgapi/translation/engines \
    apps/api-py/esgapi/translation/prompts apps/api-py/esgapi/translation/tools/llm_bridge.py \
    apps/api-py/esgapi/translation/tools/compare_dump.py \
    ':(exclude)apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py'
  code=$?
  # 감독 처분(경계 test_s3sheets_is_pure.py:149): 그 파일은 더함 1·지움 1, 바뀐 줄은 읽개 목록 단언 하나
  stat=$(git diff --numstat "$BASE" -- apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py)
  line=$(git diff -U0 "$BASE" -- apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py | grep -c -E '^\+    assert opening == \["inventory/tools/xlsx_reader.py", "translation/tools/docx_reader.py"\]$')
  echo "  test_s3sheets_is_pure.py numstat ${stat:-0 0 -} · 허락된 줄 ${line}"
  case "$stat" in "1	1	"*) [ "$line" = 1 ] || code=1 ;; *) code=1 ;; esac
  report 3 "기존 경로 바이트 0" "$code"
fi

# 4. 계약 파일은 모듈 주석 한 줄(고정 스키마 둘·wire.py 0)
if want 4; then
  helper 4
  report 4 "shapes.py 주석 한 줄·스키마 0" $?
fi

# 5. import 계약 — BASE 트리와 같은 수
if want 5; then
  if [ ! -f "$OUT/base-s5.txt" ]; then
    base_api uv run --frozen lint-imports 2>&1 | grep 'Contracts:' > "$OUT/base-s5.txt"
  fi
  api uv run --frozen lint-imports > "$OUT/s5-lint.log" 2>&1
  code=$?
  n=$(sed -E 's/.*Contracts: ([0-9]+) kept.*/\1/' "$OUT/base-s5.txt")
  got=$(grep 'Contracts:' "$OUT/s5-lint.log")
  echo "  HEAD $got · BASE $(cat "$OUT/base-s5.txt")"
  if [ "$got" != "Contracts: $n kept, 0 broken." ]; then code=1; fi
  report 5 "lint-imports(BASE 수 ${n})" "$code"
fi

# 6. .importlinter 더하기만, 처분 ⑭ 표의 줄(그 커밋까지)
if want 6; then
  helper 6
  report 6 ".importlinter 더하기만" $?
fi

# 7. 의존성·잠금(더한 둘뿐, 있던 패키지 그대로, uv 0.7.13 lock --check)
if want 7; then
  helper 7
  code=$?
  api uvx --from 'uv==0.7.13' uv lock --check > "$OUT/s7-lock-check.log" 2>&1
  rc=$?
  echo "  uv lock --check(uv 0.7.13) 종료 $rc · $(tail -1 "$OUT/s7-lock-check.log")"
  if [ "$rc" != 0 ]; then code=1; fi
  report 7 "의존성·잠금" "$code"
fi

# 8. 심은 파손
if want 8; then
  "$API/scripts/planted-breaks-TR1b.sh" --commit "$CB" > "$OUT/s8-planted.log" 2>&1
  code=$?
  grep -E '^(PLANTED|FINGERPRINT)=' "$OUT/s8-planted.log" | sed 's/^/  /'
  report 8 "심은 파손(커밋 ${CB} 까지)" "$code"
fi

# 9. 시험 자리
if want 9; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s9-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s9-layout.log")"
  if ! git diff --quiet "$BASE" -- apps/api-py/scripts/test-layout-allow.txt; then code=1; echo "  ★ 허용 목록이 바뀌었다"; fi
  report 9 "check_test_layout·허용 목록 0줄" "$code"
fi

# 10. BASE 의 노드 id 가 HEAD 의 부분집합
if want 10; then
  if [ ! -f "$OUT/base-s10.txt" ]; then
    base_api uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi tests 2>/dev/null | grep '::' | sort > "$OUT/base-s10.txt"
  fi
  api uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi tests 2>/dev/null | grep '::' | sort > "$OUT/s10-head.txt"
  gone=$(comm -23 "$OUT/base-s10.txt" "$OUT/s10-head.txt" | grep -c .)
  echo "  BASE $(grep -c . "$OUT/base-s10.txt") · HEAD $(grep -c . "$OUT/s10-head.txt") · BASE 에만 $gone"
  code=0
  if [ "$gone" != 0 ] || [ "$(grep -c . "$OUT/base-s10.txt")" = 0 ]; then code=1; fi
  report 10 "노드 id 부분집합" "$code"
fi

# 11. 빠른 게이트(뿌리에서)
if want 11; then
  start=$(date +%s)
  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast > "$OUT/s11-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s11-verify-fast.log")
  echo "  $last · $(( $(date +%s) - start ))초(30초를 넘으면 보고 — MARC-ENT-252)"
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 11 "scripts/verify.sh --fast" "$code"
fi

# 12. 실호출·네트워크 0
if want 12; then
  tries=$(cat "$OUT"/s1-pure.log "$OUT"/s2-translation.log 2>/dev/null | grep -c -E '소켓 연결을 시도했다|이름 풀이를 시도했다')
  echo "  시험 기록의 막힌 소켓 시도 $tries"
  helper 12
  code=$?
  if [ "$tries" != 0 ]; then code=1; fi
  report 12 "실호출·네트워크 0" "$code"
fi

# 13. 허용 경로
if want 13; then
  helper 13
  report 13 "허용 경로" $?
fi

# 14. 원본·비밀·실명·파일 꼴
if want 14; then
  if reading_ok; then
    helper 14 "$READING" "$MSG" "$MARCSPON_ROOT/band-reports/TR1b.md"
    code=$?
  else
    code=1
  fi
  report 14 "원본·비밀·실명·파일 꼴" "$code"
fi

# 15. 작업 트리(커밋 전에는 스테이징만 남아야 한다 — 스테이징 안 된 변경·추적 밖 파일 0)
if want 15; then
  loose=$(git status --porcelain | grep -v -E '^[AMDR] ' | grep -c .)
  echo "  스테이징 밖 $loose 줄 · 전체 $(git status --porcelain | grep -c .) 줄"
  code=0
  if [ "$loose" != 0 ]; then code=1; git status --porcelain | grep -v -E '^[AMDR] ' | sed 's/^/  /'; fi
  report 15 "작업 트리" "$code"
fi

# 16. 타입(완화 머리는 docx 파일 넷에만)
if want 16; then
  api uv run --frozen pyright > "$OUT/s16-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s16-pyright.log")"
  helper 16 || code=1
  report 16 "pyright strict·완화 줄" "$code"
fi

# 17. 이미지(커밋 ① 만): 빌드 잠금 아래 api-py 빌드 → 컨테이너 안 import·판·휠 태그·NEEDED, 이미지 크기 앞/뒤, check-wheel
if want 17; then
  if [ "$CB" != 1 ]; then
    echo "  해당 없음 — 커밋 경계 ${CB}(이미지 확인은 커밋 ① 만, 처분 ⑯)"
    report 17 "이미지" 0
  else
    free=$(memory_pressure | grep percentage | sed -E 's/.*: ([0-9]+)%/\1/')
    load=$(uptime | sed -E 's/.*load averages?: ([0-9.]+).*/\1/')
    echo "  띄우기 전 메모리 free ${free}% · 1분 부하 ${load}(기준 free ≥20%·부하 <24 — MARC-ENT-241)"
    code=0
    if [ "${free:-0}" -lt 20 ] || [ "$(echo "${load:-99} >= 24" | bc)" = 1 ]; then
      echo "  ★ 기준 밖 — 띄우지 않는다(기다렸다 다시)"
      code=1
    else
      before=$(docker image inspect esg-app/api-py:local --format '{{.Size}} {{.Created}}' 2>/dev/null)
      echo "  앞(main 의 esg-app/api-py:local 크기·지은 때) ${before:-없음}"
      scripts/with-build-lock.sh docker compose -p "$PROJECT" build api-py > "$OUT/s17-build.log" 2>&1
      rc=$?
      echo "  빌드(잠금 아래) 종료 $rc · $(tail -1 "$OUT/s17-build.log")"
      [ "$rc" = 0 ] || code=1
      after=$(docker image inspect "$PROJECT/api-py:local" --format '{{.Size}} {{.Created}} {{.Architecture}}' 2>/dev/null)
      echo "  뒤($PROJECT/api-py:local 크기·지은 때·아키텍처) ${after:-없음}"
      docker compose -p "$PROJECT" run --rm --no-deps -T api-py python -I -c '
import docx, lxml.etree as e, importlib.metadata as m, glob, os, struct
print("LXML_VERSION", e.LXML_VERSION, "LIBXML", e.LIBXML_VERSION, "ICONV", e.ICONV_COMPILED_VERSION)
d = m.distribution("lxml")
print("WHEEL", [l for l in d.read_text("WHEEL").splitlines() if l.startswith("Tag:")])
print("python-docx", m.version("python-docx"))
root = os.path.dirname(e.__file__)
print("lxml.libs", sorted(glob.glob(root + "/../lxml.libs*")))
so = glob.glob(root + "/etree*.so")[0]
b = open(so, "rb").read()
# ELF64 LE: 구역 머리에서 .dynamic·.dynstr 를 찾아 DT_NEEDED(1) 를 읽는다(실행 0)
shoff, = struct.unpack_from("<Q", b, 0x28); shentsize, shnum, shstrndx = struct.unpack_from("<HHH", b, 0x3A)
secs = [struct.unpack_from("<IIQQQQIIQQ", b, shoff + i * shentsize) for i in range(shnum)]
names = secs[shstrndx]
def nm(off): end = b.index(b"\0", names[4] + off); return b[names[4] + off:end].decode()
by = {nm(s[0]): s for s in secs}
dyn, dynstr = by[".dynamic"], by[".dynstr"]
need = []
for i in range(dyn[5] // 16):
    tag, val = struct.unpack_from("<qQ", b, dyn[4] + i * 16)
    if tag == 1:
        end = b.index(b"\0", dynstr[4] + val); need.append(b[dynstr[4] + val:end].decode())
print("NEEDED", need)
lic = [f for f in d.files if "LICENSE" in str(f).upper()]
print("LICENSES", [str(f) for f in lic])
' > "$OUT/s17-import.log" 2>&1
      rc=$?
      sed 's/^/  /' "$OUT/s17-import.log"
      [ "$rc" = 0 ] || code=1
      grep -q 'LXML_VERSION (6, 1, 3, 0)' "$OUT/s17-import.log" || { echo "  ★ LXML_VERSION 이 (6, 1, 3, 0) 이 아니다"; code=1; }
      left=$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Names}}' | grep -c .)
      echo "  남은 컨테이너(프로젝트 $PROJECT) $left"
      [ "$left" = 0 ] || code=1
      # run 이 만든 빈 볼륨·네트워크(이 프로젝트 것뿐)를 내린다
      docker compose -p "$PROJECT" down -v > "$OUT/s17-down.log" 2>&1
      rc=$?
      echo "  down -v(프로젝트 $PROJECT) 종료 $rc"
      [ "$rc" = 0 ] || code=1
    fi
    "$API/scripts/check-wheel.sh" > "$OUT/s17-check-wheel.log" 2>&1
    rc=$?
    echo "  check-wheel.sh 종료 $rc · $(tail -1 "$OUT/s17-check-wheel.log")"
    [ "$rc" = 0 ] || code=1
    report 17 "이미지(커밋 ①)" "$code"
  fi
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
