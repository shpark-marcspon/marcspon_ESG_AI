#!/usr/bin/env bash
# 밴드 DV1c(MARC-TICK-183) §4 의 자기검증. 데이터 검증 코랩 사본을 빼고 시험을 손셈으로, 견줌은 esg-lab py/dvcolab 으로.
#   사용: apps/api-py/scripts/section4-DV1c.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>…] [--live]
#   단계마다 "[n] … EXIT=<코드>", 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0. 아무것도 없으면 1~8.
#   --planted 는 9(PLANTED=<잡음>/12), --msg 는 10(커밋 메시지 넷), 11(scripts/verify.sh --fast)은 --step 11, --live 는 12.
# 출력 자리 S4_OUT(기본 DV1c.out, 검증자는 DV1c.verify). esg-lab 쪽은 LAB_WT(기본 esg-lab.worktrees/DV1c).
# 심은 파손은 원본을 $S4_OUT/planted/ 에 cp 로 들고 있다가 되쓰고 cmp 한다(checkout·restore·stash 0).
# 정규식 낱말은 쪼개 적는다(이 파일이 grep 에 걸리지 않게). macOS /bin/bash 3.2, 파이썬 도움은 python3 -I.
# LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=ccd3194187fc314a3dce31a892343c66289547b6
LAB_BASE=a3d7962d203fe3165ef39509ecf8fab908d47259
MARC=/Users/leedongeon/Desktop/marcspon
OUT="${S4_OUT:-$MARC/esg-app.worktrees/DV1c.out}"
LAB_WT="${LAB_WT:-$MARC/esg-lab.worktrees/DV1c}"
FORBIDDEN=$MARC/esg-app.worktrees/G1a.out/forbidden-words.txt
REPORT=$MARC/band-reports/DV1c.md
COLAB_MD="$MARC/received-derived/2026-10-15/데이터 검증 코랩/데이터리뷰_v7_4평가테스트용_Input2(코랩1~3번)_test시연.md"
API="$ROOT/apps/api-py"
DV=esgapi/dataverify
mkdir -p "$OUT/planted"

ONLY=""
MSGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) ONLY="${ONLY:+$ONLY,}9"; shift ;;
    --msg) shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do MSGS="$MSGS $1"; shift; done; ONLY="${ONLY:+$ONLY,}10" ;;
    --live) ONLY="${ONLY:+$ONLY,}12"; shift ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--msg <파일>…] [--live]" >&2; exit 2 ;;
  esac
done
[ -n "$ONLY" ] || ONLY=1,2,3,4,5,6,7,8

failed=0
report() { echo "[$1] $2 EXIT=$3"; if [ "$3" != 0 ]; then failed=$((failed + 1)); fi; }
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }
lab() { (cd "$LAB_WT/py" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }

PY_HELPER="$(mktemp -t s4dv1c.XXXXXX)"
PLANT_SRC=""
PLANT_KEEP=""
trap 'rm -f "$PY_HELPER"; if [ -n "$PLANT_SRC" ]; then cp "$PLANT_KEEP" "$PLANT_SRC"; fi' EXIT
trap 'exit 130' INT TERM
cat > "$PY_HELPER" <<'PYEOF'
import os, re, subprocess, sys

MODE = sys.argv[1]


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def changed(repo, base):
    names = set(git(repo, "diff", "--name-only", base).splitlines())
    names |= set(git(repo, "ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(names)


def added(repo, base):
    """BASE 이후 더한 줄: 추적 파일 diff ^+ 와 새 파일 전부 — (파일, 줄 번호, 글)."""
    out, path, at = [], None, 0
    for line in git(repo, "diff", "-U0", base).splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            at = int(re.search(r"\+(\d+)", line).group(1))
        elif line.startswith("+") and path:
            out.append((path, at, line[1:]))
            at += 1
    for f in git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
        try:
            for i, text in enumerate(open(os.path.join(repo, f), encoding="utf-8").read().splitlines(), 1):
                out.append((f, i, text))
        except UnicodeDecodeError:
            out.append((f, 0, f"<바이너리 {f}>"))
    return out


APP_ALLOWED = re.compile(
    r"^apps/api-py/(esgapi/dataverify/tests/engines/colab_156/.*|esgapi/dataverify/tests/contracts/test_wire\.py"
    r"|esgapi/dataverify/prompts/README\.md|\.importlinter|scripts/section4-DV1c\.sh|scripts/dataverify_compare_dump\.py)$"
)
LAB_ALLOWED = re.compile(r"^(py/dvcolab/.*|README\.md)$")
FROZEN = ("apps/api-py/esgapi/dataverify/engines/", "apps/api-py/esgapi/dataverify/contracts/",
          "apps/api-py/esgapi/dataverify/outputs/", "apps/api-py/esgapi/dataverify/tests/data/")


def step5(app, base, lab, lab_base):
    bad = 0
    for repo, b, allowed in ((app, base, APP_ALLOWED), (lab, lab_base, LAB_ALLOWED)):
        for f in changed(repo, b):
            ok = bool(allowed.match(f)) and not f.startswith(FROZEN)
            print(f"  {'' if ok else '★ 허용 밖 '}{'esg-lab' if repo == lab else 'esg-app'}: {f}")
            bad += not ok
    diff = git(app, "diff", "-U0", base, "--", "apps/api-py/.importlinter").splitlines()
    minus = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    plus = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    print(f"  .importlinter: 지운 줄 {len(minus)} · 더한 줄 {len(plus)}")
    if minus or plus != ["    esgapi.dataverify"]:
        bad += 1
    frozen = git(app, "diff", "--stat", base, "--", *FROZEN).strip()
    print(f"  엔진·계약·출력·tests/data diff: {'0' if not frozen else frozen}")
    return bad + (1 if frozen else 0)


def code_lines(md):
    """읽기판 code 셀 줄을 빈칸 정규화해 12자 이상인 것의 집합."""
    lines, inside, code = set(), None, False
    for line in open(md, encoding="utf-8").read().splitlines():
        head = re.match(r"^### 셀 \d+ · (code|markdown)", line)
        if head:
            code = head.group(1) == "code"
            continue
        fence = re.match(r"^(`{3,})python\s*$", line)
        if inside is None and fence and code:
            inside = fence.group(1)
            continue
        if inside is not None:
            if line.rstrip() == inside:
                inside = None
                continue
            norm = " ".join(line.split())
            if len(norm) >= 12:
                lines.add(norm)
    return lines


IDIOMS = {'if __name__ == "__main__":'}  # 파이썬 관용구 — 코랩 글이 아니다(보고에 까닭)


def overlap(rows, colab):
    return [(f, i) for f, i, text in rows if " ".join(text.split()) in colab - IDIOMS]


def step6(app, base, lab, lab_base, md):
    colab = code_lines(md)
    bad = 0
    for name, repo, b in (("esg-app", app, base), ("esg-lab", lab, lab_base)):
        hits = overlap(added(repo, b), colab)
        print(f"  (ii) {name} 더한 줄의 읽기판 code 줄 겹침(12자 이상): {len(hits)}")
        for f, i in hits:
            print(f"      {f}:{i}")
        bad += len(hits)
    tests = "apps/api-py/esgapi/dataverify/tests/"
    before = [(f, i, t) for f in git(app, "ls-tree", "-r", "--name-only", base, tests).splitlines() if f.endswith(".py")
              for i, t in enumerate(git(app, "show", f"{base}:{f}").splitlines(), 1)]
    now = [(f, i, t) for f in git(app, "ls-files", tests).splitlines() if f.endswith(".py") and os.path.exists(os.path.join(app, f))
           for i, t in enumerate(open(os.path.join(app, f), encoding="utf-8").read().splitlines(), 1)]
    print(f"  (iii) 기록: DV/tests 트리의 겹침 BASE {len(overlap(before, colab))} → 작업 트리 {len(overlap(now, colab))}")
    return bad


def step7(app, base, lab, lab_base, forbidden, report, msgs):
    words = [w.strip() for w in open(forbidden, encoding="utf-8") if w.strip()]
    key = re.compile("sk" + r"-[A-Za-z0-9_-]{16,}")
    nums = re.compile("|".join(("14" "03", "15" "30", "16" "42")))
    texts = {"esg-app 더한 줄": [t for _, _, t in added(app, base)], "esg-lab 더한 줄": [t for _, _, t in added(lab, lab_base)],
             "esg-app 커밋": git(app, "log", "--format=%B", f"{base}..HEAD").splitlines(),
             "esg-lab 커밋": git(lab, "log", "--format=%B", f"{lab_base}..HEAD").splitlines()}
    for m in msgs:
        if os.path.isfile(m):
            texts[f"메시지 {os.path.basename(m)}"] = open(m, encoding="utf-8").read().splitlines()
    if os.path.isfile(report):
        texts["보고"] = open(report, encoding="utf-8").read().splitlines()
    bad = 0
    for name, lines in texts.items():
        w = sum(1 for l in lines if any(x in l for x in words))
        k = sum(1 for l in lines if key.search(l))
        n = sum(1 for l in lines if nums.search(l))
        print(f"  {name}: 줄 {len(lines)} · 기업명 {w} · 키 꼴 {k} · 예시 수 {n}")
        bad += w + k + n
    for name, repo, b in (("esg-app", app, base), ("esg-lab", lab, lab_base)):
        binary = [l for l in git(repo, "diff", "--numstat", b).splitlines() if l.startswith("-\t")]
        exts = [f for f in changed(repo, b) if re.search(r"\.(xlsx|csv|ipynb)$", f)]
        print(f"  {name}: 바이너리 {len(binary)} · xlsx·csv·ipynb 경로 {len(exts)}")
        bad += len(binary) + len(exts)
    return bad


COMMON = [
    "Ticket: MARC-TICK-183",
    "Derives-from: MARC-ENT-310",
    "Concerns: MARC-ISSUE-186",
    "Constraint: 저장소에 받은 코랩 코드 사본 0(시험의 대조 기준으로도) — MARC-ENT-310",
    "Rejected: 시험 안 코랩 사본 유지 | MARC-ENT-310 (데이터 검증만 예외는 규칙이 갈림)",
    "Directive: 코랩과의 견줌은 esg-lab py/dvcolab 에서 — esg-app 시험에 코랩 코드를 다시 들이지 않는다",
]
TITLES = [
    ("chore(api): DV1c ① .importlinter 차 — runs 는 dataverify 도 모른다", True),
    ("test(dataverify): DV1c ② 코랩 사본 colab_" + "reference 를 빼고 시험을 손셈 기대값으로", False),
    ("chore(dataverify): DV1c ③ 코랩 대조용 엔진 JSON 명령", False),
    ("feat(dvcolab): DV1c ④ 데이터 검증 코랩 대조 도구(실행 때 읽기판에서 읽음, 사본 0)", False),
]
COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def step10(msgs):
    bad = 0
    if len(msgs) != 4:
        print(f"  ★ 메시지 {len(msgs)}개(넷이어야 한다)")
        return 1
    for path, (title, concerns187) in zip(msgs, TITLES):
        lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
        want = COMMON[:3] + (["Concerns: MARC-ISSUE-187"] if concerns187 else []) + COMMON[3:] + [COAUTHOR]
        tail = lines[-len(want):]
        ok = lines[0] == title and tail == want and lines[-len(want) - 1] == ""
        print(f"  {'' if ok else '★ '}{os.path.basename(path)}: {lines[0]}")
        bad += not ok
    return bad


if MODE == "5":
    sys.exit(min(step5(*sys.argv[2:6]), 1))
elif MODE == "6":
    sys.exit(min(step6(*sys.argv[2:7]), 1))
elif MODE == "7":
    sys.exit(min(step7(*sys.argv[2:8], sys.argv[8:]), 1))
elif MODE == "10":
    sys.exit(min(step10(sys.argv[2:]), 1))
PYEOF

# 1. 순수 시험 전부, 수집 수와 약점 12 id
if want 1; then
  api uv run --frozen pytest -q "$DV" -p no:cacheprovider > "$OUT/s1-pytest.log" 2>&1
  code=$?
  api uv run --frozen pytest -q --collect-only "$DV" -p no:cacheprovider > "$OUT/s1-collect.log" 2>&1
  n1=$(grep -c '::' "$OUT/s1-collect.log")
  weak=$(grep '::' "$OUT/s1-collect.log" | grep -c 'weakness')
  echo "  $(tail -1 "$OUT/s1-pytest.log") · 수집 N0=247 → N1=$n1 · 약점 id $weak"
  if [ "$weak" != 12 ]; then code=1; fi
  report 1 "pytest esgapi/dataverify" "$code"
fi

# 2. lint-imports 계약 16, 「차」 목록에 esgapi.dataverify 한 번
if want 2; then
  api uv run --frozen lint-imports > "$OUT/s2-lint-imports.log" 2>&1
  code=$?
  n=$(grep -c '^\[importlinter:contract' "$API/.importlinter")
  cha=$(awk '/^\[importlinter:contract:runs-knows-no-module\]/{f=1;next} /^\[/{f=0} f' "$API/.importlinter" | grep -cx '    esgapi.dataverify')
  echo "  계약 수 $n · 차 안 dataverify $cha · $(grep 'Contracts:' "$OUT/s2-lint-imports.log")"
  if [ "$n" != 16 ] || [ "$cha" != 1 ]; then code=1; fi
  report 2 "lint-imports(계약 16·차 1줄)" "$code"
fi

# 3. 시험 자리
if want 3; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s3-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s3-layout.log")"
  report 3 "check_test_layout" "$code"
fi

# 4. pyright strict 와 완화 줄
if want 4; then
  api uv run --frozen pyright "$DV" scripts/dataverify_compare_dump.py > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  (cd "$API" && grep -rn '^# pyright:' "$DV" scripts/dataverify_compare_dump.py) > "$OUT/s4-relax.txt"
  echo "  완화 줄 $(grep -c . "$OUT/s4-relax.txt")"
  sed 's/^/  완화 /' "$OUT/s4-relax.txt"
  report 4 "pyright $DV + dump" "$code"
fi

# 5. 허용 경로(두 저장소), .importlinter 한 줄, 얼린 자리 diff 0
if want 5; then
  python3 -I "$PY_HELPER" 5 "$ROOT" "$BASE" "$LAB_WT" "$LAB_BASE"
  report 5 "허용 경로·.importlinter·얼린 자리" $?
fi

# 6. 코랩 꼴 0: (i) 식별자 (ii) 더한 줄의 읽기판 줄 겹침 (iii) 기록
if want 6; then
  pat="colab_""reference|clear_value""_cache|colab_""cell3|colab_""plan_prompt|colab_""review_prompt|colab_""insight_prompt|DEBUG ""tool_|global _value""_cache|출처: ""읽기판"
  hits=$(git -C "$ROOT" grep -nE "$pat" -- apps/api-py | grep -v '^apps/api-py/scripts/section4-DV1c.sh:' | grep -c .)
  echo "  (i) 식별자 grep(esg-app apps/api-py): $hits"
  python3 -I "$PY_HELPER" 6 "$ROOT" "$BASE" "$LAB_WT" "$LAB_BASE" "$COLAB_MD"
  code=$?
  if [ "$hits" != 0 ]; then code=1; fi
  report 6 "코랩 꼴 0" "$code"
fi

# 7. 기업명·키 꼴·예시 수·바이너리 0(두 저장소 더한 줄·커밋·메시지·보고)
if want 7; then
  # shellcheck disable=SC2086  # MSGS 는 빈칸으로 나눈 경로 목록
  python3 -I "$PY_HELPER" 7 "$ROOT" "$BASE" "$LAB_WT" "$LAB_BASE" "$FORBIDDEN" "$REPORT" $MSGS
  report 7 "기업명·키 꼴·예시 수·바이너리" $?
fi

# 8. esg-lab 게이트: dvcolab·scope3colab 시험, 전체 pytest 의 실패가 LAB_BASE 와 같은지
if want 8; then
  lab uv run --frozen pytest -q dvcolab/tests scope3colab/tests -p no:cacheprovider > "$OUT/s8-lab-tests.log" 2>&1
  code=$?
  echo "  dvcolab·scope3colab: $(tail -1 "$OUT/s8-lab-tests.log")"
  lab uv run --frozen pytest -q --ignore=greenwash -p no:cacheprovider > "$OUT/s8-lab-all-head.log" 2>&1
  base_wt="$OUT/lab-base-wt"
  rm -rf "$base_wt"
  git -C "$LAB_WT" worktree add --detach -q "$base_wt" "$LAB_BASE" > /dev/null 2>&1
  (cd "$base_wt/py" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q --ignore=greenwash -p no:cacheprovider) > "$OUT/s8-lab-all-base.log" 2>&1
  git -C "$LAB_WT" worktree remove --force "$base_wt" > /dev/null 2>&1
  grep -E '^(FAILED|ERROR) ' "$OUT/s8-lab-all-head.log" | sed 's/ - .*//' | sort > "$OUT/s8-fail-head.txt"
  grep -E '^(FAILED|ERROR) ' "$OUT/s8-lab-all-base.log" | sed 's/ - .*//' | sort > "$OUT/s8-fail-base.txt"
  echo "  전체(--ignore=greenwash) HEAD: $(tail -1 "$OUT/s8-lab-all-head.log")"
  echo "  전체(--ignore=greenwash) LAB_BASE: $(tail -1 "$OUT/s8-lab-all-base.log")"
  # 새 임시 워크트리는 git 밖 자료(data/raw·data/reports 등)가 더 없어 실패가 더 많다 — HEAD 의 실패가 그 안에 들고
  # dvcolab·scope3colab 에는 없으면 이 밴드가 만든 실패가 아니다.
  new=$(comm -23 "$OUT/s8-fail-head.txt" "$OUT/s8-fail-base.txt" | grep -c .)
  ours=$(grep -c 'dvcolab\|scope3colab' "$OUT/s8-fail-head.txt")
  raw=$(grep -cE '^E +factors.sources.SourceUnavailable: .*원자료 없음' "$OUT/s8-lab-all-head.log")
  echo "  실패·오류 HEAD $(grep -c . "$OUT/s8-fail-head.txt") · LAB_BASE $(grep -c . "$OUT/s8-fail-base.txt") · HEAD 에만 $new · dvcolab·scope3colab $ours · 원자료 없음 줄 $raw"
  if [ "$new" != 0 ] || [ "$ours" != 0 ]; then code=1; fi
  report 8 "esg-lab 게이트" "$code"
fi

# 9. 심은 파손 P1~P7·P12~P16. 줄: 번호|파일(api-py 기준)|옛 글|새 글(\n 줄바꿈)|빨개질 시험(lint = lint-imports 의 차)
plant() {
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, old, new = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
if old not in text:
    print(f"  ★ 심을 자리가 없다: {old[:60]!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PYEOF
}
if want 9; then
  E=$DV/engines/colab_156
  T=$DV/tests/engines/colab_156
  PLANTS="P1|$E/tools.py|    ok = abs(diff) <= tolerance|    ok = abs(diff) < tolerance|$T/test_tools.py
P2|$E/tools.py|    if 0.0 <= ff <= 1.0:|    if False:|$T/test_tools.py
P3|$E/tools.py|                and rec.get(\"단위\") == 단위|                and True|$T/test_tools.py
P4|$E/tools.py|        v = v.replace(\",\", \"\").replace(\" \", \"\")|        v = v.replace(\" \", \"\")|$T/test_tools.py
P5|$E/tools.py|        raise NameError(\"name 'e' is not defined\")|        pass|$T/test_tools.py $T/test_dispatch.py
P6|$E/dispatch.py|args.get(\"limit\", 200)|args.get(\"limit\", 50)|$T/test_dispatch.py
P7|$E/schemas.py|\"required\": [\"a\", \"b\", \"c\", \"tolerance\"]|\"required\": [\"a\", \"b\", \"c\"]|$T/test_schemas.py
P12|$E/inputs.py|    if \"환경\" in data:|    for theme in data:\\n        data_split[theme] = data[theme]\\n    if False:|$T/test_inputs.py
P13|$E/prompts.py|검증하는 감사자다.|검증하는 감사자이다.|$T/test_prompts.py
P14|$E/schemas.py|Return numeric value for|Return numeric values for|$T/test_schemas.py
P15|esgapi/runs/models.py|\"\"\"\\n\\n|\"\"\"\\n\\nimport esgapi.dataverify  # noqa: F401\\n|lint
P16|$E/tools.py|        v = v.replace(\",\", \"\").replace(\" \", \"\")|        v = v.replace(\",\", \"\")|$T/test_tools.py"
  caught=0
  : > "$OUT/s9-planted.txt"
  while IFS='|' read -r id file old new tests; do
    [ -n "$id" ] || continue
    src="$API/$file"
    keep="$OUT/planted/$id.$(basename "$file")"
    cp "$src" "$keep"
    PLANT_SRC="$src"
    PLANT_KEEP="$keep"
    if ! (cd "$API" && plant "$file" "$old" "$new"); then cp "$keep" "$src"; PLANT_SRC=""; echo "  $id 심지 못함" | tee -a "$OUT/s9-planted.txt"; failed=$((failed + 1)); continue; fi
    if [ "$tests" = lint ]; then
      api uv run --frozen lint-imports > "$OUT/planted/$id.log" 2>&1
      code=$?
      if [ "$code" != 0 ] && grep -q '차. runs 는 업무 모듈을 import 하지 않는다 BROKEN' "$OUT/planted/$id.log" && grep -q 'esgapi.runs.models -> esgapi.dataverify' "$OUT/planted/$id.log"; then red=1; else red=0; fi
    else
      # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록
      api uv run --frozen pytest -q -x $tests -p no:cacheprovider > "$OUT/planted/$id.log" 2>&1
      code=$?
      if [ "$code" = 1 ]; then red=1; else red=0; fi
    fi
    cp "$keep" "$src"
    PLANT_SRC=""
    if ! cmp -s "$keep" "$src"; then echo "  ★ $id 되쓰기 실패"; failed=$((failed + 1)); fi
    caught=$((caught + red))
    echo "  $id $([ "$red" = 1 ] && echo 잡음 || echo ★놓침) (EXIT=$code, $tests)" | tee -a "$OUT/s9-planted.txt"
  done <<EOF
$PLANTS
EOF
  echo "PLANTED=$caught/12"
  if [ "$caught" != 12 ]; then report 9 "심은 파손" 1; else report 9 "심은 파손" 0; fi
fi

# 10. 커밋 메시지 넷(① ② ③ esg-app, ④ esg-lab)
if want 10; then
  # shellcheck disable=SC2086
  python3 -I "$PY_HELPER" 10 $MSGS
  report 10 "커밋 메시지 넷" $?
fi

# 11. 빠른 게이트(뿌리에서)
if want 11; then
  start=$(date +%s)
  scripts/verify.sh --fast > "$OUT/s11-verify-fast.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s11-verify-fast.log") · $(( $(date +%s) - start ))초"
  report 11 "scripts/verify.sh --fast" "$code"
fi

# 12. dvcolab 실측: 손 사례·seed 1·seed 2 를 코랩 쪽 → 엔진 명령 → 견줌, 같은 seed 재실행의 colab.json 바이트
if want 12; then
  live="$OUT/live"
  rm -rf "$live"
  mkdir -p "$live"
  code=0
  for run in hand seed1 seed2; do
    case "$run" in hand) extra="" ;; seed1) extra="--random 500 --seed 1" ;; seed2) extra="--random 500 --seed 2" ;; esac
    # shellcheck disable=SC2086
    lab uv run --frozen python -m dvcolab run $extra --out "$live/$run-colab" > "$live/$run-colab.log" 2>&1
    a=$?
    api uv run --frozen python scripts/dataverify_compare_dump.py --cases "$live/$run-colab/cases.json" --out "$live/$run-engine.json" > "$live/$run-engine.log" 2>&1
    b=$?
    # shellcheck disable=SC2086
    lab uv run --frozen python -m dvcolab run $extra --out "$live/$run-diff" --engine-result "$live/$run-engine.json" > "$live/$run-diff.log" 2>&1
    c=$?
    echo "  $run: 코랩 쪽 EXIT=$a · 엔진 명령 EXIT=$b · 견줌 EXIT=$c · $(tail -1 "$live/$run-diff.log" | sed 's/ → .*//')"
    if [ "$a" != 0 ] || [ "$b" != 0 ] || [ "$c" != 0 ]; then code=1; fi
  done
  if cmp -s "$live/seed1-colab/colab.json" "$live/seed1-diff/colab.json"; then echo "  seed 1 두 번의 colab.json 바이트 같음"; else echo "  ★ seed 1 colab.json 바이트 다름"; code=1; fi
  report 12 "dvcolab 실측(손·seed 1·seed 2)" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
