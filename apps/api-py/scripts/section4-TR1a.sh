#!/usr/bin/env bash
# 밴드 TR1a(MARC-TICK-184) §4 의 자기검증. 영문번역 코랩 엔진 판(esgapi/translation)을 잰다.
#   사용: apps/api-py/scripts/section4-TR1a.sh [--step <n>[,<n>…]] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0. 아무것도 없으면 1~16 전부.
#   그 커밋에 닿지 않는 단계(예: ①② 의 16)는 「해당 없음」을 찍고 EXIT=0 이다(무엇이 없어서인지 한 줄).
#   --msg 는 13단계가 함께 볼 커밋 메시지 초안(기본 $S4_OUT/commit-msg.txt — 있으면).
# 출력 자리는 S4_OUT(기본 esg-app.worktrees/TR1a.out). 검증자는 S4_OUT=…/TR1a.verify 로 돌려 러너 기록을 덮지 않는다.
# BASE 트리의 값(1·10 의 시간, 5 의 계약 수, 9 의 노드 id)은 `git archive BASE` 를 $S4_OUT/base-tree 에 풀어 한 번 재고
#   $S4_OUT/base-*.txt 에 둔다(다음 실행은 그 값을 쓴다).
# 읽기판(받은 코랩의 뽑은 판)은 워크트리 밖이다 — MARCSPON_ROOT(기본 워크트리의 ../..) 아래에서 읽고, 못 읽으면 FAIL.
#   읽기판의 글은 이 스크립트에도 출력에도 싣지 않는다(이름·sha·수·EXIT 만).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=34302e1603d67c87e2cfabe5dc54d05dd6c088a7
OUT="${S4_OUT:-$ROOT/../TR1a.out}"
MARCSPON_ROOT="${MARCSPON_ROOT:-$ROOT/../..}"
READING="$MARCSPON_ROOT/received-derived/2026-10-15/영문번역 코랩/보고서_AI번역_v3_1.md"
API="$ROOT/apps/api-py"
TR=esgapi/translation
mkdir -p "$OUT"

ONLY=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
[ -n "$MSG" ] || MSG="$ROOT/../TR1a.out/commit-msg.txt"

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }
echo "BASE=$BASE HEAD=$(git rev-parse HEAD)"

# 지금 커밋 경계(N2): BASE 이후 TR1a 커밋 수 + 스테이징이 있으면 1. 「해당 없음」 판정은 파일 유무가 아니라 이것으로.
done_commits=$(git log --format=%s "$BASE..HEAD" | grep -c '^feat(translation): TR1a ')
staged_n=$(git diff --cached --name-only | grep -c .)
CB=$((done_commits + (staged_n > 0 ? 1 : 0)))
[ "$CB" -ge 1 ] || CB=1
[ "$CB" -le 4 ] || CB=4
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

PY_HELPER="$(mktemp -t s4tr1a.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, hashlib, os, re, subprocess, sys

MODE, BASE = sys.argv[1], sys.argv[2]
API = "apps/api-py/"
TR = API + "esgapi/translation/"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def untracked():
    return git("ls-files", "--others", "--exclude-standard").splitlines()


def changed():
    return sorted(set(git("diff", "--name-only", BASE).splitlines()) | set(untracked()))


def added_lines():
    """BASE 이후 더한 줄(추적 파일의 diff ^+ 와 새 파일 전부)."""
    lines = [l[1:] for l in git("diff", "-U0", BASE).splitlines() if l.startswith("+") and not l.startswith("+++")]
    for f in untracked():
        try:
            lines += open(f, encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            lines.append(f"<바이너리 {f}>")
    return lines


ALLOWED = re.compile(
    r"^(apps/api-py/esgapi/translation/.*|apps/api-py/\.importlinter"
    r"|apps/api-py/scripts/(section4|planted-breaks)-TR1a\.sh)$"
)
# 처분 ⑭ 표(BASE 34302e1 의 줄. ccd3194 와 줄 번호가 같다 — 머리 :3 만 바뀜): (앞 줄, 더한 줄, 들어가는 조건 폴더)
LINT_ROWS = [
    ("    esgapi.dataverify", "    esgapi.translation", None),  # 가 :24
    ("    esgapi.dataverify", "    esgapi.translation", None),  # 나 source :51
    ("    esgapi.dataverify.models", "    esgapi.translation.models", None),  # 나 forbidden :60
    ("    esgapi.dataverify.** -> esgapi.dataverify.models", "    esgapi.translation.** -> esgapi.translation.models", None),
    ("    esgapi.dataverify.outputs", "    esgapi.translation.contracts", None),  # 다 :105
    ("    esgapi.translation.contracts", "    esgapi.translation.engines", "engines"),  # 다 ②
    ("    esgapi.translation.engines", "    esgapi.translation.tools", "tools"),  # 다 ③
    ("    esgapi.dataverify", "    esgapi.translation", None),  # 바 forbidden :182
    ("    esgapi.dataverify.** -> esgapi.dataverify.**", "    esgapi.translation.** -> esgapi.translation.**", None),
]


def step6():
    bad = 0
    diff = git("diff", "-U0", BASE, "--", API + ".importlinter").splitlines()
    minus = [l for l in diff if re.match(r"^-[^-]", l)]
    plus = [l[1:] for l in diff if re.match(r"^\+[^+]", l)]
    rows = [(a, t) for a, t, cond in LINT_ROWS if cond is None or os.path.isdir(TR + cond)]
    print(f"  .importlinter: 지운 줄 {len(minus)} · 더한 줄 {len(plus)} · 표의 줄 {len(rows)}")
    if minus or sorted(plus) != sorted(t for _, t in rows):
        bad += 1
        print("  ★ 더한 줄이 처분 ⑭ 표와 다르다")
    lines = open(API + ".importlinter", encoding="utf-8").read().split("\n")
    at = 0
    for anchor, text in rows:
        hit = next((i for i in range(at, len(lines) - 1) if lines[i] == anchor and lines[i + 1] == text), None)
        if hit is None:
            bad += 1
            print(f"  ★ 자리가 표와 다르다: {anchor.strip()} 뒤의 {text.strip()}")
        else:
            at = hit + 1
    return bad


def step11():
    pats = ["anthropic.Anthropic(", "create_anthropic_client", "load_live", "os.environ"]
    hits = [l for l in added_lines() if any(p in l for p in pats) and "pats = [" not in l]
    own = open(API + "esgapi/core/llm/providers/anthropic.py", encoding="utf-8").read()
    pos = sum(1 for p in pats if p in own)
    print(f"  diff ^+ 의 실호출 무늬 {len(hits)} · 양성 대조(core anthropic.py 에 든 무늬) {pos}")
    return int(bool(hits) or pos == 0)


def step12():
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


def step13(reading, msg, report):
    bad = 0
    names, frag, line2449 = names_from_reading(reading)
    pats = [boundary(n) for n in names] + [boundary(frag, re.IGNORECASE)]
    pos = sum(1 for p in pats[:-1] if p.search(line2449))
    print(f"  이름 {len(names)}(일반 낱말 {len(COMMON)} 뺌) · 양성 대조: R/2449 줄에서 {pos}/{len(names)}")
    if len(names) != 9 or pos != 9:
        bad += 1
    texts = {"diff ^+": added_lines(), "커밋 메시지": git("log", "--format=%B", f"{BASE}..HEAD").splitlines()}
    for name, path in (("메시지 초안", msg), ("보고", report), ("prompts/README.md", TR + "prompts/README.md")):
        if os.path.isfile(path):
            texts[name] = open(path, encoding="utf-8").read().splitlines()
    # 키 꼴: 앞이 영숫자가 아닌 자리의 sk-(코랩 프롬프트 글의 「Risk-Response-…」 같은 낱말 안 sk- 를 빼려고 — 커밋 ③)
    key = re.compile(r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{20,}|" + "sk-" + "ant-)")
    fake = "sk" + "-" + "A" * 24
    if not key.search(f"x {fake}") or key.search("Risk-Response-Strengthening Governance"):
        print("  ★ 키 꼴 양성·음성 대조 실패")
        bad += 1
    tag =re.compile(r"\[고객사\]|\[Client\]|\[Pe" + r"er|\[자회사\]")
    for name, lines in texts.items():
        n = sum(1 for l in lines if any(p.search(l) for p in pats))
        k = sum(1 for l in lines if key.search(l))
        t = sum(1 for l in lines if tag.search(l)) if name in ("diff ^+", "커밋 메시지", "prompts/README.md") else 0
        print(f"  {name}: 줄 {len(lines)} · 실명 {n} · 키 꼴 {k} · 바꿈 표지 {t}")
        bad += n + k + t
    exts = [f for f in changed() if re.search(r"\.(docx|xlsx|xls|csv|ipynb)$", f)]
    print(f"  docx·xlsx·xls·csv·ipynb 경로 {len(exts)}")
    bad += len(exts)
    company = []
    for f in changed():
        if f.startswith(TR + "tests/") and os.path.isfile(f):
            company += re.findall(r'"name":[ ]*"([^"]*)"', open(f, encoding="utf-8").read())
    odd = [c for c in company if not (c.startswith("가상") or c.startswith("ABC Corp"))]
    print(f"  시험 자료의 회사 이름 칸 {len(company)} · 가상·ABC Corp 밖 {len(odd)}")
    return bad + len(odd)


def step15():
    strict = "# py" + "right:|py" + "right: ignore|type" + ": ignore"  # 이 파일의 줄이 스스로 걸리지 않게 나눠 적는다
    relax = re.compile(strict + "|ca" + r"st\(")
    lines = [l for l in added_lines() if relax.search(l)]
    for l in lines:
        print(f"  완화·cast 줄: {l.strip()[:100]}")
    copies = [f for f in changed() if "colab_reference" in f]
    print(f"  완화·cast 줄 {len(lines)} · colab_reference 이름 파일 {len(copies)}")
    return int(bool(copies) or any(re.search(strict, l) for l in lines))


PROMPT_CONSTS = [  # (셀, 이름) — 셀 30~44·60 의 평 문자열 상수 열다섯(읽기판 R/ 줄은 README 표)
    (30, "TERMINOLOGY_CONSISTENCY_PROMPT"), (31, "SUBJECT_PRONOUN_PROMPT"), (32, "NUMBER_UNIT_PROMPT"),
    (33, "FRAGMENTARY_CONTENT_PROMPT"), (34, "OFFICIAL_REPORT_STYLE_PROMPT"), (34, "LEXICAL_GUARDRAILS_PROMPT"),
    (34, "ANTI_MACHINE_TRANSLATION_PROMPT"), (34, "BILINGUAL_EDITORIAL_POLISH_PROMPT"),
    (34, "GENERIC_EDITORIAL_QA_PROMPT"), (36, "CEO_MESSAGE_TONE"), (36, "STORY_TONE"), (36, "GENERAL_TONE"),
    (41, "STYLE_A_PROMPT"), (41, "STYLE_B_PROMPT"), (60, "QA_SYSTEM_PROMPT"),
]


def cell_code(reading, cell):
    """읽기판에서 셀 하나의 코드 블록(```python … ```)."""
    text = open(reading, encoding="utf-8").read()
    m = re.search(rf"^### 셀 {cell} · code\n\n(`{{3,4}})python\n(.*?)\n\1$", text, re.S | re.M)
    if not m:
        raise SystemExit(f"  ★ 읽기판에서 셀 {cell} 의 코드를 못 찾았다")
    return m.group(2)


def reading_consts(reading):
    out = {}
    for cell, name in PROMPT_CONSTS:
        for node in ast.walk(ast.parse(cell_code(reading, cell))):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                out[name] = ast.literal_eval(node.value)
    return out


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def engine_consts(path):
    """엔진 prompts.py 의 같은 이름 상수(평 문자열 대입)를 AST 로 읽는다(엔진을 import 하지 않는다)."""
    out = {}
    for node in ast.parse(open(path, encoding="utf-8").read()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def readme_shas(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\| `([A-Z_]+)` \|.*\| `([0-9a-f]{64})` \|", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def compare(reading, engine_path, readme_path):
    theirs = reading_consts(reading)
    ours = engine_consts(engine_path)
    pinned = readme_shas(readme_path)
    ok = 0
    for _, name in PROMPT_CONSTS:
        a = sha(theirs[name]) if name in theirs else None
        b = sha(ours[name]) if isinstance(ours.get(name), str) else None
        c = pinned.get(name)
        same = a is not None and a == b == c
        ok += same
        print(f"  {'' if same else '★ '}{name} 읽기판 {(a or '없음')[:12]} · 엔진 {(b or '없음')[:12]} · README {(c or '없음')[:12]}")
    return ok


def step16(reading, engine_path, readme_path, scratch):
    ok = compare(reading, engine_path, readme_path)
    print(f"PROMPT_CONSTS={ok}/{len(PROMPT_CONSTS)}")
    # 양성 대조: 엔진 상수 하나에 한 글자 심은 사본(임시 자리)으로 같은 검사가 빨개지는가
    src = open(engine_path, encoding="utf-8").read()
    planted = src.replace('STYLE_A_PROMPT = """\nStyle A', 'STYLE_A_PROMPT = """\nStyle  A', 1)
    if planted == src:
        print("  ★ 양성 대조를 심을 자리가 없다")
        return 1
    copy = os.path.join(scratch, "prompts-planted.py")
    open(copy, "w", encoding="utf-8").write(planted)
    red = compare(reading, copy, readme_path)
    print(f"  양성 대조(한 글자 심음): {red}/{len(PROMPT_CONSTS)} — {'빨강' if red < len(PROMPT_CONSTS) else '★ 초록'}")
    return int(ok != len(PROMPT_CONSTS) or red == len(PROMPT_CONSTS))


if MODE == "6":
    sys.exit(min(step6(), 1))
elif MODE == "11":
    sys.exit(step11())
elif MODE == "12":
    sys.exit(min(step12(), 1))
elif MODE == "13":
    sys.exit(min(step13(sys.argv[3], sys.argv[4], sys.argv[5]), 1))
elif MODE == "15":
    sys.exit(step15())
elif MODE == "16":
    sys.exit(step16(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]))
PYEOF

reading_ok() {
  if [ ! -r "$READING" ]; then echo "  ★ 읽기판을 못 읽는다(MARCSPON_ROOT=$MARCSPON_ROOT)"; return 1; fi
  return 0
}

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

# 2. translation 표적
if want 2; then
  api uv run --frozen pytest -q -p no:cacheprovider esgapi/translation > "$OUT/s2-translation.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s2-translation.log")"
  report 2 "pytest $TR" "$code"
fi

# 3. 바이트 0
if want 3; then
  git diff --quiet "$BASE" -- apps/api-py/generated apps/web apps/api-py/esgapi/core apps/api-py/esgapi/config \
    apps/api-py/esgapi/greenwash apps/api-py/esgapi/dataverify apps/api-py/esgapi/inventory apps/api-py/esgapi/runs \
    apps/api-py/pyproject.toml apps/api-py/uv.lock README.md
  report 3 "기존 경로 바이트 0" $?
fi

# 4. INSTALLED_APPS·라우터 0(양성 대조: dataverify 가 .importlinter 에 있다)
if want 4; then
  out=$(git grep -n 'esgapi\.translation' -- apps/api-py/esgapi/config)
  rc=$?
  pos=$(git grep -c 'esgapi\.dataverify' -- apps/api-py/.importlinter | cut -d: -f2)
  echo "  config 의 translation 줄 $(printf '%s' "$out" | grep -c .) (git grep 종료 $rc) · 양성 대조 ${pos:-0}"
  code=0
  if [ "$rc" != 1 ] || [ "${pos:-0}" -lt 1 ]; then code=1; fi
  report 4 "INSTALLED_APPS·라우터 0" "$code"
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

# 6. .importlinter 더하기만, 처분 ⑭ 표의 줄
if want 6; then
  python3 -I "$PY_HELPER" 6 "$BASE"
  report 6 ".importlinter 더하기만" $?
fi

# 7. 심은 파손
if want 7; then
  "$API/scripts/planted-breaks-TR1a.sh" --commit "$CB" > "$OUT/s7-planted.log" 2>&1
  code=$?
  grep -E '^(PLANTED|FINGERPRINT)=' "$OUT/s7-planted.log" | sed 's/^/  /'
  report 7 "심은 파손(커밋 ${CB} 까지)" "$code"
fi

# 8. 시험 자리
if want 8; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s8-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s8-layout.log")"
  if ! git diff --quiet "$BASE" -- apps/api-py/scripts/test-layout-allow.txt; then code=1; echo "  ★ 허용 목록이 바뀌었다"; fi
  report 8 "check_test_layout·허용 목록 0줄" "$code"
fi

# 9. BASE 의 노드 id 가 HEAD 의 부분집합
if want 9; then
  if [ ! -f "$OUT/base-s9.txt" ]; then
    base_api uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi tests 2>/dev/null | grep '::' | sort > "$OUT/base-s9.txt"
  fi
  api uv run --frozen pytest -q -p no:cacheprovider --collect-only esgapi tests 2>/dev/null | grep '::' | sort > "$OUT/s9-head.txt"
  gone=$(comm -23 "$OUT/base-s9.txt" "$OUT/s9-head.txt" | grep -c .)
  echo "  BASE $(grep -c . "$OUT/base-s9.txt") · HEAD $(grep -c . "$OUT/s9-head.txt") · BASE 에만 $gone"
  code=0
  if [ "$gone" != 0 ] || [ "$(grep -c . "$OUT/base-s9.txt")" = 0 ]; then code=1; fi
  report 9 "노드 id 부분집합" "$code"
fi

# 10. 빠른 게이트(뿌리에서)
if want 10; then
  start=$(date +%s)
  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast > "$OUT/s10-verify-fast.log" 2>&1
  code=$?
  last=$(tail -1 "$OUT/s10-verify-fast.log")
  echo "  $last · $(( $(date +%s) - start ))초"
  if [ "$last" != "VERIFY_FAST=PASS" ]; then code=1; fi
  report 10 "scripts/verify.sh --fast" "$code"
fi

# 11. 실호출 0
if want 11; then
  tries=$(cat "$OUT"/s1-pure.log "$OUT"/s2-translation.log 2>/dev/null | grep -c -E '소켓 연결을 시도했다|이름 풀이를 시도했다')
  echo "  시험 기록의 막힌 소켓 시도 $tries"
  python3 -I "$PY_HELPER" 11 "$BASE"
  code=$?
  if [ "$tries" != 0 ]; then code=1; fi
  report 11 "실호출 0" "$code"
fi

# 12. 허용 경로
if want 12; then
  python3 -I "$PY_HELPER" 12 "$BASE"
  report 12 "허용 경로" $?
fi

# 13. 원본·비밀·실명
if want 13; then
  if reading_ok; then
    python3 -I "$PY_HELPER" 13 "$BASE" "$READING" "$MSG" "$MARCSPON_ROOT/band-reports/TR1a.md"
    code=$?
  else
    code=1
  fi
  report 13 "원본·비밀·실명" "$code"
fi

# 14. 작업 트리(커밋 전에는 스테이징만 남아야 한다 — 스테이징 안 된 변경·추적 밖 파일 0)
if want 14; then
  loose=$(git status --porcelain | grep -v -E '^[AMDR] ' | grep -c .)
  echo "  스테이징 밖 $loose 줄 · 전체 $(git status --porcelain | grep -c .) 줄"
  code=0
  if [ "$loose" != 0 ]; then code=1; git status --porcelain | grep -v -E '^[AMDR] ' | sed 's/^/  /'; fi
  report 14 "작업 트리" "$code"
fi

# 15. 타입
if want 15; then
  api uv run --frozen pyright > "$OUT/s15-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s15-pyright.log")"
  python3 -I "$PY_HELPER" 15 "$BASE" || code=1
  report 15 "pyright strict·완화 줄" "$code"
fi

# 16. 프롬프트 상수 ↔ 읽기판(커밋 ③ 부터)
if want 16; then
  if [ "$CB" -lt 3 ]; then
    echo "  해당 없음 — 커밋 경계 ${CB}(상수는 커밋 ③ 부터)"
    report 16 "프롬프트 상수 ↔ 읽기판" 0
  elif [ ! -f "$API/$TR/engines/colab_158/prompts.py" ]; then
    echo "  ★ 커밋 경계 ${CB} 인데 $TR/engines/colab_158/prompts.py 가 없다"
    report 16 "프롬프트 상수 ↔ 읽기판" 1
  elif reading_ok; then
    scratch=$(mktemp -d /private/tmp/tr1a.XXXXXX)
    python3 -I "$PY_HELPER" 16 "$BASE" "$READING" "$API/$TR/engines/colab_158/prompts.py" "$API/$TR/prompts/README.md" "$scratch"
    code=$?
    case "$scratch" in /private/tmp/tr1a.*) rm -rf "$scratch" ;; esac
    report 16 "프롬프트 상수 ↔ 읽기판" "$code"
  else
    report 16 "프롬프트 상수 ↔ 읽기판" 1
  fi
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
