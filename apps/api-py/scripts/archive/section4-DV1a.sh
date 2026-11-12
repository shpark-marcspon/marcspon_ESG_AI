#!/usr/bin/env bash
# 밴드 DV1a(MARC-TICK-177) §4 의 자기검증. 데이터 검증 코랩의 도구 없는 바닥(esgapi/dataverify)을 잰다.
#   사용: apps/api-py/scripts/section4-DV1a.sh [--step <n>[,<n>…]] [--planted] [--msg <파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>, 종료 코드는 그것이 0 일 때만 0. 아무것도 없으면 1~6.
#   --planted 는 7단계(심은 파손 P1~P12, 끝 줄 PLANTED=<잡음>/12 — 이 경계에 아직 없는 파일의 파손은 「해당 없음」),
#   --msg 는 8단계(커밋 메시지 초안의 제목·트레일러), 9단계(scripts/verify.sh --fast)는 --step 9 로만 돈다.
# 출력 자리는 S4_OUT(기본 DV1a.out). 검증자는 S4_OUT=…/DV1a.verify 로 돌려 러너 기록을 덮지 않는다.
# 심은 파손은 원본을 $S4_OUT/planted/ 에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(checkout·restore·stash 0).
# macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I. LLM·네트워크·키 파일·컨테이너 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=90c2f6df372c3a3823c6511892850fd11dd2ccd0
OUT="${S4_OUT:-$ROOT/../DV1a.out}"
FORBIDDEN=/Users/leedongeon/Desktop/marcspon/esg-app.worktrees/G1a.out/forbidden-words.txt
REPORT=/Users/leedongeon/Desktop/marcspon/band-reports/DV1a.md
API="$ROOT/apps/api-py"
DV=esgapi/dataverify
mkdir -p "$OUT/planted"

ONLY=""
PLANTED=0
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--msg <파일>]" >&2; exit 2 ;;
  esac
done
if [ -z "$ONLY" ]; then
  if [ "$PLANTED" = 1 ]; then ONLY=7; elif [ -n "$MSG" ]; then ONLY=8; else ONLY=1,2,3,4,5,6; fi
fi

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }
api() { (cd "$API" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$@"); }

# 1. 순수 시험 전부
if want 1; then
  api uv run --frozen pytest -q "$DV" -p no:cacheprovider > "$OUT/s1-pytest.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s1-pytest.log")"
  report 1 "pytest esgapi/dataverify" "$code"
fi

# 2. lint-imports 와 계약 수 16
if want 2; then
  api uv run --frozen lint-imports > "$OUT/s2-lint-imports.log" 2>&1
  code=$?
  n=$(grep -c '^\[importlinter:contract' "$API/.importlinter")
  echo "  계약 수 $n · $(grep 'Contracts:' "$OUT/s2-lint-imports.log")"
  if [ "$n" != 16 ]; then code=1; fi
  report 2 "lint-imports(계약 16)" "$code"
fi

# 3. 시험 자리
if want 3; then
  api uv run --frozen python scripts/check_test_layout.py > "$OUT/s3-layout.log" 2>&1
  code=$?
  echo "  $(head -1 "$OUT/s3-layout.log")"
  report 3 "check_test_layout" "$code"
fi

# 4. pyright strict 와 완화 줄(tests/ 안에만)
if want 4; then
  api uv run --frozen pyright "$DV" > "$OUT/s4-pyright.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s4-pyright.log")"
  (cd "$API" && grep -rn '^# pyright:' "$DV" --include='*.py') > "$OUT/s4-relax.txt"
  sed 's/^/  완화 /' "$OUT/s4-relax.txt"
  if grep -v "^$DV/tests/" "$OUT/s4-relax.txt" | grep -q .; then echo "  ★ tests/ 밖의 완화 줄"; code=1; fi
  report 4 "pyright $DV" "$code"
fi

PY_HELPER="$(mktemp -t s4dv1a.XXXXXX)"
PLANT_SRC=""   # 7단계가 심는 동안만 차 있다 — 도중에 끝나도(오류·Ctrl-C) 원본을 되쓴다
PLANT_KEEP=""
trap 'rm -f "$PY_HELPER"; if [ -n "$PLANT_SRC" ]; then cp "$PLANT_KEEP" "$PLANT_SRC"; fi' EXIT
trap 'exit 130' INT TERM
cat > "$PY_HELPER" <<'PYEOF'
import os, re, subprocess, sys

MODE, BASE = sys.argv[1], sys.argv[2]
API = "apps/api-py/"
DV = API + "esgapi/dataverify/"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def changed():
    names = set(git("diff", "--name-only", BASE).splitlines())
    names |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(names)


ALLOWED = re.compile(r"^(apps/api-py/esgapi/dataverify/.*|apps/api-py/\.importlinter|apps/api-py/scripts/section4-DV1a\.sh)$")
LINT_ROWS = [  # (앞 줄, 더한 줄, 그 줄이 들어가는 조건 — 처분 ③ 표, 파일 안의 차례(가·나·다·바). 앞 줄은 main 90c2f6d 의 줄 또는 바로 앞에 더한 줄)
    ("    esgapi.runs", "    esgapi.dataverify", None),
    ("    esgapi.greenwash", "    esgapi.dataverify", None),
    ("    esgapi.runs.models", "    esgapi.dataverify.models", None),
    ("    esgapi.greenwash.** -> esgapi.greenwash.models", "    esgapi.dataverify.** -> esgapi.dataverify.models", None),
    ("    esgapi.greenwash.engines", "    esgapi.dataverify.engines", "engines"),
    ("    esgapi.dataverify.engines", "    esgapi.dataverify.contracts", "engines"),
    ("    esgapi.dataverify.contracts", "    esgapi.dataverify.outputs", "outputs"),
    ("    esgapi.greenwash", "    esgapi.dataverify", None),
    ("    esgapi.greenwash.** -> esgapi.greenwash.**", "    esgapi.dataverify.** -> esgapi.dataverify.**", None),
]


def step5():
    bad = 0
    files = changed()
    for f in files:
        print(f"  {'' if ALLOWED.match(f) else '★ 허용 밖 '}{f}")
        if not ALLOWED.match(f):
            bad += 1
    diff = git("diff", "-U0", BASE, "--", API + ".importlinter").splitlines()
    minus = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    plus = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    rows = [(a, t) for a, t, cond in LINT_ROWS if cond is None or os.path.isdir(DV + cond)]
    print(f"  .importlinter: 지운 줄 {len(minus)} · 더한 줄 {len(plus)} · 표의 줄 {len(rows)}")
    if minus or sorted(plus) != sorted(t for _, t in rows):
        bad += 1
        print("  ★ .importlinter 의 더한 줄이 처분 ③ 표와 다르다")
    # 자리: 표의 차례대로, 앞 줄 바로 뒤에 있어야 한다(같은 글의 줄이 여러 목록에 들어가므로 차례째 본다).
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


def added_text():
    """BASE 이후 더한 줄(추적 파일의 diff ^+ 와 새 파일 전부)."""
    lines = [l[1:] for l in git("diff", "-U0", BASE).splitlines() if l.startswith("+") and not l.startswith("+++")]
    for f in git("ls-files", "--others", "--exclude-standard").splitlines():
        try:
            lines += open(f, encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            lines.append(f"<바이너리 {f}>")
    return lines


def step6(forbidden, report, msg):
    bad = 0
    words = [w.strip() for w in open(forbidden, encoding="utf-8") if w.strip()]
    texts = {"diff ^+": added_text(), "커밋 메시지": git("log", "--format=%B", f"{BASE}..HEAD").splitlines()}
    if os.path.isfile(msg):
        texts["메시지 초안"] = open(msg, encoding="utf-8").read().splitlines()
    if os.path.isfile(report):
        texts["보고"] = open(report, encoding="utf-8").read().splitlines()
    key = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
    nums = re.compile("|".join(("14" "03", "15" "30", "16" "42")))  # 셀 14 의 예시 수(이 파일에 글자째 두지 않는다)
    for name, lines in texts.items():
        w = sum(1 for l in lines if any(x in l for x in words))
        k = sum(1 for l in lines if key.search(l))
        n = sum(1 for l in lines if nums.search(l)) if name != "보고" else 0  # 보고는 바꾼 수를 적는다
        print(f"  {name}: 줄 {len(lines)} · 기업명 {w} · 키 꼴 {k} · 예시 수 {n}")
        bad += w + k + n
    numstat = git("diff", "--numstat", BASE).splitlines()
    binary = [l for l in numstat if l.startswith("-\t")]
    exts = [f for f in changed() if re.search(r"\.(xlsx|csv|ipynb)$", f)]
    print(f"  바이너리 {len(binary)} · xlsx·csv·ipynb 경로 {len(exts)}")
    return bad + len(binary) + len(exts)


TRAILERS = [
    "Ticket: MARC-TICK-177",
    "Derives-from: MARC-ENT-297",
    "Concerns: MARC-ISSUE-186",
    "Constraint: 코랩대로(약점 포함) — MARC-ENT-297",
    "Rejected: 약점 1 고침 | 같은 입력 같은 결과 위반(처분 ⑦)",
    "Directive: engines/colab_156 은 고치지 않는다 — 다음 판은 engines/<판>/ 새로",
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
]


def step8(path):
    text = open(path, encoding="utf-8").read().rstrip("\n")
    lines = text.split("\n")
    bad = 0
    if not re.match(r"(feat|fix)\(dataverify\): DV1a ", lines[0]):
        print("  ★ 제목 꼴")
        bad += 1
    tail = lines[-len(TRAILERS):]
    if tail != TRAILERS or lines[-len(TRAILERS) - 1] != "":
        print("  ★ 트레일러 일곱 줄이 끝에 한 문단(앞에 빈 줄)으로 없다")
        bad += 1
    print(f"  제목: {lines[0]}")
    return bad


if MODE == "5":
    sys.exit(min(step5(), 1))
elif MODE == "6":
    sys.exit(min(step6(sys.argv[3], sys.argv[4], sys.argv[5]), 1))
elif MODE == "8":
    sys.exit(min(step8(sys.argv[3]), 1))
PYEOF

# 5. 허용 경로 밖 0줄, .importlinter 는 처분 ③ 표의 줄만
if want 5; then
  python3 -I "$PY_HELPER" 5 "$BASE"
  report 5 "허용 경로·.importlinter 줄" $?
fi

# 6. 기업명·키 꼴·예시 수·바이너리 0
if want 6; then
  python3 -I "$PY_HELPER" 6 "$BASE" "$FORBIDDEN" "$REPORT" "${MSG:-$ROOT/../DV1a.out/commit-msg.txt}"
  report 6 "기업명·키 꼴·예시 수·바이너리" $?
fi

# 7. 심은 파손. 줄: 번호|파일(api-py 기준)|바꿀 글|바꿀 글(\n 은 줄바꿈)|빨개질 시험(빈칸으로 나눔, lint = lint-imports)
plant() {  # plant <파일> <옛 글> <새 글> → 0 이면 심음
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
if want 7; then
  E=$DV/engines/colab_156
  T=$DV/tests/engines/colab_156
  PLANTS="P1|$E/tools.py|    ok = abs(diff) <= tolerance|    ok = abs(diff) < tolerance|$T/test_tools.py
P2|$E/tools.py|    if 0.0 <= ff <= 1.0:|    if False:|$T/test_tools.py
P3|$E/tools.py|                and rec.get(\"단위\") == 단위|                and True|$T/test_tools.py
P4|$E/tools.py|        v = v.replace(\",\", \"\").replace(\" \", \"\")|        v = v.replace(\" \", \"\")|$T/test_tools.py
P5|$E/tools.py|        raise NameError(\"name 'e' is not defined\")|        pass|$T/test_tools.py $T/test_dispatch.py
P6|$E/dispatch.py|args.get(\"limit\", 200)|args.get(\"limit\", 50)|$T/test_dispatch.py
P7|$E/schemas.py|\"required\": [\"a\", \"b\", \"c\", \"tolerance\"]|\"required\": [\"a\", \"b\", \"c\"]|$T/test_schemas.py
P8|$DV/contracts/shapes.py|    warnings: list[ResultWarning]\\n|    warnings: list[ResultWarning]\\n    extra: int\\n|$DV/tests/contracts/test_shapes.py
P9|$DV/outputs/xlsx.py|    \"허용 오차\",\\n||$DV/tests/outputs/test_xlsx.py
P10a|$E/tools.py|\"\"\"\\n\\n|\"\"\"\\n\\nimport django  # noqa: F401\\n|lint
P10b|$DV/contracts/shapes.py|\"\"\"\\n\\n|\"\"\"\\n\\nimport django  # noqa: F401\\n|lint
P10c|$DV/outputs/xlsx.py|\"\"\"\\n\\n|\"\"\"\\n\\nimport django  # noqa: F401\\n|lint
P11|$E/tools.py|\"\"\"\\n\\n|\"\"\"\\n\\nimport esgapi.dataverify.contracts  # noqa: F401\\n|$T/test_purity.py
P12|$E/inputs.py|    if \"환경\" in data:|    for theme in data:\\n        data_split[theme] = data[theme]\\n    if False:|$T/test_inputs.py"
  caught=0
  applicable=0
  p10_caught=0
  p10_seen=0
  : > "$OUT/s7-planted.txt"
  while IFS='|' read -r id file old new tests; do
    [ -n "$id" ] || continue
    src="$API/$file"
    if [ ! -f "$src" ]; then echo "  $id 해당 없음(이 경계에 $file 없음)" | tee -a "$OUT/s7-planted.txt"; continue; fi
    if [ "$tests" = lint ]; then  # 「다」 목록에 그 폴더의 줄이 들어간 경계부터 잰다(처분 ③ 표)
      layer=$(echo "$file" | sed -E 's#^esgapi/dataverify/([a-z]+)/.*#\1#')
      if ! grep -qx "    esgapi.dataverify.$layer" "$API/.importlinter"; then
        echo "  $id 해당 없음(「다」에 esgapi.dataverify.$layer 줄이 아직 없음)" | tee -a "$OUT/s7-planted.txt"; continue
      fi
    fi
    keep="$OUT/planted/$id.$(basename "$file")"
    cp "$src" "$keep"
    PLANT_SRC="$src"
    PLANT_KEEP="$keep"
    if ! (cd "$API" && plant "$file" "$old" "$new"); then cp "$keep" "$src"; echo "  $id 심지 못함" | tee -a "$OUT/s7-planted.txt"; failed=$((failed + 1)); continue; fi
    if [ "$tests" = lint ]; then
      api uv run --frozen lint-imports > "$OUT/planted/$id.log" 2>&1
      code=$?
      # 「다」가 그 층에서 django 를 막았다고 말해야 잡은 것이다(lint-imports 는 계약 이름을 줄바꿈해 찍는다)
      if [ "$code" != 0 ] && grep -q "^esgapi.dataverify.$layer is not allowed to import django" "$OUT/planted/$id.log"; then red=1; else red=0; fi
    else
      # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
      api uv run --frozen pytest -q -x $tests -p no:cacheprovider > "$OUT/planted/$id.log" 2>&1
      code=$?
      if [ "$code" = 1 ]; then red=1; else red=0; fi
    fi
    cp "$keep" "$src"
    PLANT_SRC=""
    if ! cmp -s "$keep" "$src"; then echo "  ★ $id 되쓰기 실패"; failed=$((failed + 1)); fi
    case "$id" in
      P10*) p10_seen=$((p10_seen + 1)); p10_caught=$((p10_caught + red)) ;;
      *) applicable=$((applicable + 1)); caught=$((caught + red)) ;;
    esac
    echo "  $id $([ "$red" = 1 ] && echo 잡음 || echo ★놓침) (EXIT=$code, $tests)" | tee -a "$OUT/s7-planted.txt"
  done <<EOF
$PLANTS
EOF
  if [ "$p10_seen" -gt 0 ]; then
    applicable=$((applicable + 1))
    if [ "$p10_caught" = "$p10_seen" ]; then caught=$((caught + 1)); fi
    echo "  P10 셋 가운데 $p10_seen 해당, $p10_caught 잡음"
  fi
  echo "  해당 $applicable"
  echo "PLANTED=$caught/12"
  if [ "$caught" != "$applicable" ]; then report 7 "심은 파손" 1; else report 7 "심은 파손" 0; fi
fi

# 8. 커밋 메시지 초안
if want 8; then
  [ -n "$MSG" ] || MSG="$ROOT/../DV1a.out/commit-msg.txt"  # 초안은 늘 러너 자리(검증자가 S4_OUT 을 바꿔도)
  python3 -I "$PY_HELPER" 8 "$BASE" "$MSG"
  report 8 "커밋 메시지($MSG)" $?
fi

# 9. 빠른 게이트(뿌리에서)
if want 9; then
  start=$(date +%s)
  scripts/verify.sh --fast > "$OUT/s9-verify-fast.log" 2>&1
  code=$?
  echo "  $(tail -1 "$OUT/s9-verify-fast.log") · $(( $(date +%s) - start ))초"
  report 9 "scripts/verify.sh --fast" "$code"
fi

echo "SECTION4_FAIL=$failed"
[ "$failed" = 0 ]
