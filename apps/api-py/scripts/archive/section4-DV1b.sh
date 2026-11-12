#!/usr/bin/env bash
# 밴드 DV1b(MARC-TICK-188) §4 의 자기검증. 데이터 검증에 core.llm call_tools 위 도구 고리(흐름 dataverify.colab@156),
# ISSUE-195(AST 시험의 상대 import), esg-lab py/dvcolab 의 고리 대조.
#   사용: apps/api-py/scripts/section4-DV1b.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>…] [--live]
#   단계마다 "[n] … EXIT=<코드>", 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0. 아무것도 없으면 1~8.
#   --planted 는 9(PLANTED=<잡음>/22 — PLANT_ONLY="P15a P15b" 처럼 줄이면 분모도 준다), --msg 는 10(커밋 메시지 다섯),
#   11(scripts/verify.sh --fast)은 --step 11, --live 는 12.
# 출력 자리 S4_OUT(기본 DV1b.out, 검증자는 DV1b.verify). esg-lab 쪽은 LAB_WT(기본 esg-lab.worktrees/DV1b).
# 심은 파손은 원본을 $S4_OUT/planted/ 에 cp 로 들고 있다가 되쓰고 cmp 한다(checkout·restore·stash 0).
# 정규식 낱말은 쪼개 적는다(이 파일이 grep 에 걸리지 않게). macOS /bin/bash 3.2, 파이썬 도움은 python3 -I.
# LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=b7e0c3310edd6572dad3ac86e3741bd2fc766213
LAB_BASE=9fa6ce57bd92202a90f603606acc63a5957672da
MARC=/Users/leedongeon/Desktop/marcspon
OUT="${S4_OUT:-$MARC/esg-app.worktrees/DV1b.out}"
LAB_WT="${LAB_WT:-$MARC/esg-lab.worktrees/DV1b}"
FORBIDDEN=$MARC/esg-app.worktrees/G1a.out/forbidden-words.txt
REPORT=$MARC/band-reports/DV1b.md
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
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY "$@"); }
lab() { (cd "$LAB_WT/py" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY "$@"); }

PY_HELPER="$(mktemp -t s4dv1b.XXXXXX)"
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
    r"^apps/api-py/(esgapi/dataverify/tests/engines/colab_156/(test_purity|test_loop)\.py|esgapi/dataverify/tests/test_axes\.py"
    r"|esgapi/dataverify/engines/colab_156/loop\.py|esgapi/dataverify/contracts/wire\.py"
    r"|esgapi/dataverify/tests/contracts/test_wire_insight\.py"
    r"|esgapi/dataverify/flows/(__init__|colab_156|registration)\.py"
    r"|esgapi/dataverify/tests/flows/(__init__|support|test_colab_156|test_registration)\.py"
    r"|\.importlinter|scripts/section4-DV1b\.sh|scripts/dataverify_compare_dump\.py)$"
)
LAB_ALLOWED = re.compile(r"^py/dvcolab/.*$")
FROZEN = tuple("apps/api-py/esgapi/dataverify/" + p for p in (
    "engines/colab_156/__init__.py", "engines/colab_156/tools.py", "engines/colab_156/dispatch.py",
    "engines/colab_156/schemas.py", "engines/colab_156/inputs.py", "engines/colab_156/prompts.py",
    "contracts/shapes.py", "tests/data/", "outputs/", "prompts/")) + ("py/scope3colab/",)


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
    flows = os.path.isdir(os.path.join(app, "apps/api-py/esgapi/dataverify/flows"))
    print(f"  .importlinter: 지운 줄 {len(minus)} · 더한 줄 {len(plus)} · flows 폴더 {'있음' if flows else '없음'}")
    if minus or plus != (["    esgapi.dataverify.flows"] if flows else []):
        bad += 1
    wire = git(app, "diff", "-U0", base, "--", "apps/api-py/esgapi/dataverify/contracts/wire.py").splitlines()
    wire_minus = [l for l in wire if l.startswith("-") and not l.startswith("---")]
    print(f"  contracts/wire.py 지운 줄: {len(wire_minus)}")
    bad += len(wire_minus)
    frozen = git(app, "diff", "--stat", base, "--", *[p for p in FROZEN if p.startswith("apps/")]).strip()
    lab_frozen = git(lab, "diff", "--stat", lab_base, "--", "py/scope3colab/").strip()
    print(f"  얼린 자리 diff: esg-app {'0' if not frozen else frozen} · esg-lab scope3colab {'0' if not lab_frozen else lab_frozen}")
    return bad + (1 if frozen else 0) + (1 if lab_frozen else 0)


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


COMMON_HEAD = ["Ticket: MARC-TICK-188", "Derives-from: MARC-ENT-302", "Concerns: MARC-ISSUE-187"]
CONSTRAINTS = [
    "Constraint: store:false 로 앞 항목을 다시 싣는 core 고리 위 — previous_response_id 안 씀(MARC-ENT-301)",
    "Constraint: 저장소에 받은 코랩 코드 사본 0 — 견줌은 esg-lab dvcolab(MARC-ENT-310)",
]
DIRECTIVE = "Directive: engines/colab_156 의 기존 파일은 고치지 않는다 — 코랩 규칙의 더함은 loop.py, 다음 판은 engines/<판>/ 새로"
REJECT_LIMIT = "Rejected: 도구 결과 상한을 넘으면 단계 실패 | 그때까지의 비용만 쓰고 결과 0 — 모델에 error 글로 돌려줌(처분 ③)"
REJECT_GLOBAL = "Rejected: 흐름 전역 등록 | 끼움(X1b-1) 없이는 실행 불가 — DV1d(처분 ①)"
COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TITLES = [
    ("test(dataverify): DV1b ① AST 순수·축 시험이 상대 import 를 푼다 (ISSUE-195)", ["Concerns: MARC-ISSUE-195"], []),
    ("feat(dataverify): DV1b ② 엔진 loop — 도구 실행기(인자 파싱·직렬화·결과 상한)·HINTS 읽기·검토 걸음",
     ["Concerns: MARC-ISSUE-191"], [REJECT_LIMIT]),
    ("feat(dataverify): DV1b ③ 흐름 dataverify.colab@156 — call_tools 위 Plan·검토·인사이트(web_search)·결과·엑셀·dry-run",
     ["Concerns: MARC-ISSUE-191"], [REJECT_LIMIT, REJECT_GLOBAL]),
    ("chore(dataverify): DV1b ④ 고리 대조 명령·자기검증 스크립트", [], []),
    ("feat(dvcolab): DV1b ⑤ 데이터 검증 코랩 고리 대조(run_responses_" + "loop 을 가짜 HTTP 로)", [], []),
]


def trailers(extra_concerns, rejected):
    return COMMON_HEAD + extra_concerns + CONSTRAINTS + rejected + [DIRECTIVE, COAUTHOR]


def step10(msgs):
    bad = 0
    if not 1 <= len(msgs) <= 5:
        print(f"  ★ 메시지 {len(msgs)}개(① 부터 차례로 하나~다섯)")
        return 1
    for path, (title, concerns, rejected) in zip(msgs, TITLES):
        lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
        want = trailers(concerns, rejected)
        tail = lines[-len(want):]
        ok = lines[0] == title and tail == want and lines[-len(want) - 1] == ""
        print(f"  {'' if ok else '★ '}{os.path.basename(path)}: {lines[0]}")
        if not ok:
            for w, t in zip(want, tail):
                if w != t:
                    print(f"      기대 {w!r}\n      실제 {t!r}")
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

# 1. 순수 시험 전부, 수집 수(BASE 266)
if want 1; then
  api uv run --frozen pytest -q "$DV" -p no:cacheprovider > "$OUT/s1-pytest.log" 2>&1
  code=$?
  api uv run --frozen pytest -q --collect-only "$DV" -p no:cacheprovider > "$OUT/s1-collect.log" 2>&1
  n1=$(grep -c '::' "$OUT/s1-collect.log")
  echo "  $(tail -1 "$OUT/s1-pytest.log") · 수집 N0=266 → N1=$n1"
  for f in tests/engines/colab_156/test_purity.py tests/test_axes.py tests/engines/colab_156/test_loop.py \
           tests/contracts/test_wire_insight.py tests/flows/test_colab_156.py tests/flows/test_registration.py; do
    echo "    $f $(grep -c "^$DV/$f::" "$OUT/s1-collect.log")"
  done
  report 1 "pytest esgapi/dataverify" "$code"
fi

# 2. lint-imports 계약 17, 「다」 목록에 esgapi.dataverify.flows 한 번(흐름 폴더가 있을 때)
if want 2; then
  api uv run --frozen lint-imports > "$OUT/s2-lint-imports.log" 2>&1
  code=$?
  n=$(grep -c '^\[importlinter:contract' "$API/.importlinter")
  da=$(awk '/^\[importlinter:contract:pure-modules\]/{f=1;next} /^\[/{f=0} f' "$API/.importlinter" | grep -cx '    esgapi.dataverify.flows')
  want_da=0
  if [ -d "$API/$DV/flows" ]; then want_da=1; fi
  echo "  계약 수 $n · 다 안 dataverify.flows $da(기대 $want_da) · $(grep 'Contracts:' "$OUT/s2-lint-imports.log")"
  if [ "$n" != 17 ] || [ "$da" != "$want_da" ]; then code=1; fi
  report 2 "lint-imports(계약 17·다 1줄)" "$code"
fi

# 3. 시험 자리
if want 3; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s3-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s3-layout.log")"
  report 3 "check_test_layout" "$code"
fi

# 4. pyright strict 와 완화 줄(파일 머리 # pyright: 줄은 tests 안에만)
if want 4; then
  api uv run --frozen pyright "$DV" scripts/dataverify_compare_dump.py > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  (cd "$API" && grep -rn '^# pyright:' "$DV" scripts/dataverify_compare_dump.py) > "$OUT/s4-relax.txt"
  echo "  완화 줄 $(grep -c . "$OUT/s4-relax.txt")"
  sed 's/^/  완화 /' "$OUT/s4-relax.txt"
  outside=$(grep -v "^$DV/tests/" "$OUT/s4-relax.txt" | grep -c .)
  if [ "$outside" != 0 ]; then code=1; fi
  report 4 "pyright $DV + dump" "$code"
fi

# 5. 허용 경로(두 저장소), .importlinter 한 줄, wire 지운 줄 0, 얼린 자리 diff 0
if want 5; then
  python3 -I "$PY_HELPER" 5 "$ROOT" "$BASE" "$LAB_WT" "$LAB_BASE"
  report 5 "허용 경로·.importlinter·wire 더하기만·얼린 자리" $?
fi

# 6. 코랩 꼴 0: (i) 코랩 함수 이름(esg-app 더한 줄) (ii) 더한 줄의 읽기판 code 줄 겹침 (iii) 기록
if want 6; then
  pat="run_responses""_loop|_find_function_calls""_from_responses|_extract_output_text""_from_responses|RESPONSES""_URL|colab_""reference"
  hits=$(git -C "$ROOT" diff -U0 "$BASE" -- apps/api-py | grep '^+' | grep -v '^+++' | grep -cE "$pat")
  new=$(git -C "$ROOT" ls-files --others --exclude-standard -- apps/api-py | grep -v 'scripts/section4-DV1b.sh$' | while read -r f; do grep -lE "$pat" "$ROOT/$f"; done | grep -c .)
  echo "  (i) 코랩 함수 이름(esg-app 추적 diff 더한 줄 $hits · 새 파일 $new — section4 자신 뺌)"
  python3 -I "$PY_HELPER" 6 "$ROOT" "$BASE" "$LAB_WT" "$LAB_BASE" "$COLAB_MD"
  code=$?
  if [ "$hits" != 0 ] || [ "$new" != 0 ]; then code=1; fi
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

# 9. 심은 파손 P1~P21(P15 는 a·b 둘 — 분모 22). 줄: 번호|파일(api-py 기준)|옛 글|새 글(\n 줄바꿈)|빨개질 시험(lint = 다)
#    PLANT_ONLY="P15a P15b" 처럼 주면 그것만(경계 ①·② 용).
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
  F=$DV/flows/colab_156.py
  FT=$DV/tests/flows/test_colab_156.py
  PLANTS="P1|$E/loop.py|        text = json.dumps(output, ensure_ascii=False)\n        if len|        text = json.dumps(output)\n        if len|$T/test_loop.py $FT
P2|$E/loop.py|        text = json.dumps(output, ensure_ascii=False)\n        if len|        text = json.dumps(output, ensure_ascii=False, separators=(\",\", \":\"))\n        if len|$T/test_loop.py $FT
P3|$E/loop.py|        if not parsed:\n            self.unparsable_args += 1|        if not parsed:\n            raise ValueError(\"unparsable\")|$T/test_loop.py $FT
P4|$E/loop.py|        if len(text) > self._max_output_chars:|        if False:|$T/test_loop.py $FT
P5|$F|SYSTEM_PLACEMENT: Final = \"input_message\"|SYSTEM_PLACEMENT: Final = \"instructions\"|$FT
P6|$F|        temperature=TEMPERATURE,\n        tool_choice=TOOL_CHOICE,|        tool_choice=TOOL_CHOICE,|$FT
P7|$F|        vars={\"system\": system, \"user\": user},\n        max_output_tokens=max_output_tokens,\n|        vars={\"system\": system, \"user\": user},\n|$FT
P8|$E/loop.py|    wanted = review_max_steps(hints)|    wanted = len(hints) * 2|$T/test_loop.py $FT
P9|$E/loop.py|loop_steps=max(1, min(wanted, cap))|loop_steps=max(1, wanted)|$T/test_loop.py $FT
P10|$F|    check_costs(inputs.max_cost_usd)\n    data_split|    data_split|$FT
P11|$F|            return Ended(\"done\", True, report_text(result.text), None, model)|            return Ended(\"done\", False, report_text(result.text), None, model)|$FT
P12|$F|            \"checks\": checks,\n            \"failure\": _failure|            \"checks\": [],\n            \"failure\": _failure|$FT
P13|$E/loop.py|    if not read:\n        return None\n|    if not read:\n        return None\n    if isinstance(value, dict):\n        value = list(value)\n|$T/test_loop.py $FT
P14|$F|(WEB_SEARCH,) if stage == \"insight\" else FUNCTION_TOOLS|(WEB_SEARCH, *FUNCTION_TOOLS) if stage == \"insight\" else FUNCTION_TOOLS|$FT
P15a|$E/inputs.py|    return data_split\n|    return data_split\n\n\nfrom ...contracts import shapes  # noqa: E402, F401\n|$T/test_purity.py
P15b|$DV/contracts/wire.py|    return cast(\"Check\", record)\n|    return cast(\"Check\", record)\n\n\nfrom ..engines.colab_156 import tools  # noqa: E402, F401\n|$DV/tests/test_axes.py
P16|$F|    if inputs.web_search:\n        run = run_loop(|    if True:\n        run = run_loop(|$FT
P17|$F|import math\n|import math\n\nimport django  # noqa: F401\n|lint
P18|$F|        \"warnings\": warnings,\n    }\n    try:|        \"warnings\": warnings,\n        \"extra\": None,\n    }\n    try:|$FT
P19|$F|        max_cost_usd=max_cost_usd,\n        system_placement|        system_placement|$FT
P20|$F|json_safe(record.args)|record.args|$FT
P21|$F|TOOL_OUTPUT_MAX_CHARS: Final = 100_000|TOOL_OUTPUT_MAX_CHARS: Final = 10_000_000|$FT"
  caught=0
  total=0
  : > "$OUT/s9-planted.txt"
  while IFS='|' read -r id file old new tests; do
    [ -n "$id" ] || continue
    if [ -n "${PLANT_ONLY:-}" ]; then case " $PLANT_ONLY " in *" $id "*) ;; *) continue ;; esac; fi
    total=$((total + 1))
    src="$API/$file"
    keep="$OUT/planted/$id.$(basename "$file")"
    cp "$src" "$keep"
    PLANT_SRC="$src"
    PLANT_KEEP="$keep"
    if ! (cd "$API" && plant "$file" "$old" "$new"); then cp "$keep" "$src"; PLANT_SRC=""; echo "  $id 심지 못함" | tee -a "$OUT/s9-planted.txt"; failed=$((failed + 1)); continue; fi
    if [ "$tests" = lint ]; then
      api uv run --frozen lint-imports > "$OUT/planted/$id.log" 2>&1
      code=$?
      if [ "$code" != 0 ] && grep -q 'django·ninja·psycopg 를 import 하지 않는다 BROKEN' "$OUT/planted/$id.log" && grep -q 'esgapi.dataverify.flows.colab_156 -> django' "$OUT/planted/$id.log"; then red=1; else red=0; fi
    else
      present=""
      for t in $tests; do if [ -f "$API/$t" ]; then present="$present $t"; fi; done  # 경계 ②: 흐름 시험은 ③ 에서 생긴다
      tests="${present# }"
      # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록
      api uv run --frozen pytest -q $tests -p no:cacheprovider > "$OUT/planted/$id.log" 2>&1
      code=$?
      if [ "$code" = 1 ]; then red=1; else red=0; fi
    fi
    cp "$keep" "$src"
    PLANT_SRC=""
    if ! cmp -s "$keep" "$src"; then echo "  ★ $id 되쓰기 실패"; failed=$((failed + 1)); fi
    caught=$((caught + red))
    reds=$(grep -c '^FAILED' "$OUT/planted/$id.log")
    echo "  $id $([ "$red" = 1 ] && echo 잡음 || echo ★놓침) (EXIT=$code, 빨간 시험 $reds, $tests)" | tee -a "$OUT/s9-planted.txt"
  done <<EOF
$PLANTS
EOF
  echo "PLANTED=$caught/$total"
  if [ "$caught" != "$total" ] || [ "$total" = 0 ]; then report 9 "심은 파손" 1; else report 9 "심은 파손" 0; fi
  if [ -z "${PLANT_ONLY:-}" ] && [ "$total" != 22 ]; then echo "  ★ 분모 $total(22 이어야 한다)"; failed=$((failed + 1)); fi
fi

# 10. 커밋 메시지(① ② ③ ④ esg-app, ⑤ esg-lab — 앞에서부터 차례로)
if want 10; then
  # shellcheck disable=SC2086
  python3 -I "$PY_HELPER" 10 $MSGS
  report 10 "커밋 메시지" $?
fi

# 11. 빠른 게이트(뿌리에서)
if want 11; then
  start=$(date +%s)
  scripts/verify.sh --fast > "$OUT/s11-verify-fast.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s11-verify-fast.log") · $(( $(date +%s) - start ))초"
  report 11 "scripts/verify.sh --fast" "$code"
fi

# 12. dvcolab 실측: 손 사례·seed 1·seed 2 를 코랩 쪽 → 엔진 명령 → 견줌(고리 사례 포함),
#     loops 없는 사례 파일로 낸 엔진 JSON 이 BASE 의 명령과 바이트 같음
if want 12; then
  live="$OUT/live"
  rm -rf "$live"
  mkdir -p "$live"
  code=0
  for run in hand seed1 seed2; do
    case "$run" in hand) extra="" ;; seed1) extra="--random 500 --seed 1" ;; seed2) extra="--random 500 --seed 2" ;; esac
    start=$(date +%s)
    # shellcheck disable=SC2086
    lab uv run --frozen python -m dvcolab run $extra --out "$live/$run-colab" > "$live/$run-colab.log" 2>&1
    a=$?
    api uv run --frozen python scripts/dataverify_compare_dump.py --cases "$live/$run-colab/cases.json" --out "$live/$run-engine.json" > "$live/$run-engine.log" 2>&1
    b=$?
    # shellcheck disable=SC2086
    lab uv run --frozen python -m dvcolab run $extra --out "$live/$run-diff" --engine-result "$live/$run-engine.json" > "$live/$run-diff.log" 2>&1
    c=$?
    echo "  $run: 코랩 쪽 EXIT=$a · 엔진 명령 EXIT=$b · 견줌 EXIT=$c · $(( $(date +%s) - start ))초 · $(tail -1 "$live/$run-diff.log")"
    if [ "$a" != 0 ] || [ "$b" != 0 ] || [ "$c" != 0 ]; then code=1; fi
  done
  # loops 칸 없는 사례 → BASE 의 명령과 바이트 같음
  python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); d.pop("loops",None); json.dump(d,open(sys.argv[2],"w",encoding="utf-8"),ensure_ascii=False)' "$live/hand-colab/cases.json" "$live/hand-noloops.json"
  git -C "$ROOT" show "$BASE:apps/api-py/scripts/dataverify_compare_dump.py" > "$live/dump-base.py"
  api uv run --frozen python "$live/dump-base.py" --cases "$live/hand-noloops.json" --out "$live/noloops-base.json" > /dev/null 2>&1
  b1=$?
  api uv run --frozen python scripts/dataverify_compare_dump.py --cases "$live/hand-noloops.json" --out "$live/noloops-head.json" > /dev/null 2>&1
  b2=$?
  if [ "$b1" = 0 ] && [ "$b2" = 0 ] && cmp -s "$live/noloops-base.json" "$live/noloops-head.json"; then
    echo "  loops 없는 사례: BASE 명령과 HEAD 명령의 엔진 JSON 바이트 같음"
  else
    echo "  ★ loops 없는 사례: BASE EXIT=$b1 · HEAD EXIT=$b2 · 바이트 다름"; code=1
  fi
  report 12 "dvcolab 실측(손·seed 1·seed 2·loops 없음)" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
