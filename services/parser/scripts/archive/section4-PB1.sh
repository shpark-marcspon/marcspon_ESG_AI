#!/usr/bin/env bash
# 밴드 PB1 의 §4 자기검증(발주서 band-handoffs/PB1-order.md §4). 줄마다 [n] 이름 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   services/parser/scripts/section4-PB1.sh                 전부
#   services/parser/scripts/section4-PB1.sh --step 1,2,3    일부(번호는 발주서 §4 의 번호)
#
# 환경 변수:
#   PB1_BASE   기준 커밋(기본: 착수 때 적은 9d9c110…)
#   PB1_OUT    산출물 자리(기본: 워크트리 곁의 PB1.out). 산출물은 $PB1_OUT/section4/ 아래. LAB 사본은 $PB1_OUT/lab,
#              공개 보고서 대조는 $PB1_OUT/public-baseline.sh, 보고서 이름은 $PB1_OUT/private.env 에 있다(저장소 밖).
#   PB1_FORBIDDEN_WORDS_FILE  기업명 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 컨테이너를 띄우지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

PARSER="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PARSER/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${PB1_BASE:-9d9c11049d54c6c94cfefd0ff44a25c4d5009619}"
OUT="${PB1_OUT:-$SIDE/PB1.out}"
WORDS="${PB1_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
LAB="$OUT/lab"
FIXED="$PARSER/tests/baseline/synthetic.sha256.json"
TOOL="$PARSER/scripts/parser_baseline.py"
PY="$PARSER/.venv/bin/python"
BASE_PASSED=200 # 기준 커밋에서 잰 pytest 건수(2026-10-16, PB1 착수 때: 200 passed, 38 deselected)
mkdir -p "$S4"
par() { (cd "$PARSER" && uv run --frozen "$@"); }

STEPS="all"
if [ "${1:-}" = "--step" ]; then
  STEPS=",${2:?--step 뒤에 번호},"
fi
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

# 바뀐 파일(커밋된 것 + 작업 트리 + 새 파일), 저장소 뿌리 기준 경로. 지워진 파일도 든다.
changed_files() {
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } | sort -u
}

ALLOWED='^(services/parser/tests/baseline_doc\.py|services/parser/tests/baseline/synthetic\.sha256\.json|services/parser/tests/test_baseline\.py|services/parser/scripts/parser_baseline\.py|services/parser/scripts/(section4|planted-breaks)-PB1\.sh)$'

# §1-2 의 0줄 목록(git pathspec). 새 파일 다섯은 뺀다.
SP=services/parser
ZERO=(
  "$SP/docparse" "$SP/app.py" "$SP/test_app.py" "$SP/README.md" "$SP/schemas" "$SP/pyproject.toml" "$SP/uv.lock"
  "$SP/scripts" ":(exclude)$SP/scripts/parser_baseline.py" ":(exclude,glob)$SP/scripts/*-PB1.sh"
  "$SP/tests" ":(exclude)$SP/tests/baseline_doc.py" ":(exclude)$SP/tests/test_baseline.py" ":(exclude)$SP/tests/baseline"
  scripts README.md apps infra ":(glob)compose*.yaml"
)

# build → parse(사본, 워크트리 venv) → hash. parse_hash <폴더> <PDF 이름> <판>
parse_hash() {
  local dir="$1" name="$2" variant="$3" toc=""
  [ "$variant" = synthetic_toc ] && toc="--toc"
  rm -rf "$dir" && mkdir -p "$dir"
  par python scripts/parser_baseline.py build "$dir/$name" $toc > /dev/null &&
    par python -m docparse parse "$dir/$name" --out "$dir/out" --places > "$dir/summary.json" &&
    par python scripts/parser_baseline.py hash "$dir/out" > "$dir/hash.json"
}

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse HEAD), 산출물 $S4"

if want 1; then
  changed_files > "$S4/changed-files.txt"
  outside=$(grep -Ev "$ALLOWED" "$S4/changed-files.txt")
  n=$(grep -c . "$S4/changed-files.txt")
  echo "    바뀐 파일 $n, 허용 밖 $( [ -n "$outside" ] && echo "$outside" | grep -c . || echo 0)"
  [ -n "$outside" ] && echo "$outside" | sed 's/^/    밖: /'
  report 1 "허용 경로" "$([ -z "$outside" ] && echo 0 || echo 1)"
fi

if want 2; then
  zero=$(git -C "$ROOT" diff "$BASE" --stat -- "${ZERO[@]}" | tail -1)
  untracked=$(git -C "$ROOT" ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)
  dp=$(git -C "$ROOT" diff --stat "$BASE" -- services/parser/docparse | tail -1)
  echo "    diff: ${zero:-(없음)} / 새 파일 $untracked / docparse: ${dp:-(없음)}"
  report 2 "0줄 목록(§1-2)" "$([ -z "$zero" ] && [ "$untracked" = 0 ] && [ -z "$dp" ] && echo 0 || echo 1)"
fi

if want 3; then
  (cd "$ROOT" && uv run --project services/parser --frozen pytest -q -p no:cacheprovider services/parser) > "$S4/pytest.log" 2>&1
  e=$?
  line=$(grep -E 'passed|failed|error' "$S4/pytest.log" | tail -1)
  passed=$(echo "$line" | grep -oE '[0-9]+ passed' | cut -d' ' -f1)
  echo "    $line (기준 $BASE_PASSED passed 대비 +$((${passed:-0} - BASE_PASSED)))"
  report 3 "pytest services/parser" "$e"
fi

if want 4; then
  ok=0
  for v in synthetic synthetic_toc; do
    parse_hash "$OUT/run1/$v" "first-$v.pdf" "$v" || ok=1
    mkdir -p "$OUT/run2/elsewhere"
    parse_hash "$OUT/run2/elsewhere/$v" "second name $v.pdf" "$v" || ok=1
    if cmp -s "$OUT/run1/$v/hash.json" "$OUT/run2/elsewhere/$v/hash.json"; then
      echo "    $v: 두 번 같음 $(par python -c 'import json,sys; print(json.load(open(sys.argv[1]))["all"][:16])' "$OUT/run1/$v/hash.json")…"
    else
      echo "    $v: 두 번 다름"; ok=1
    fi
    # 파이프에 걸지 않는다: 파이프의 종료 코드는 sed 의 것이라 check 의 1 이 버려진다
    res=$(par python scripts/parser_baseline.py check "$OUT/run1/$v/out" "$FIXED" "$v") || ok=1
    echo "    고정값과: $res"
  done
  report 4 "두 번 돌림(다른 이름·폴더)" "$ok"
fi

if want 5; then
  ok=0
  where=$(cd "$LAB/py" && "$PY" -c 'import docparse; print(docparse.__file__)' 2>&1)
  echo "    LAB docparse: $where"
  case "$where" in "$LAB/py/docparse/"*) ;; *) ok=1 ;; esac
  for v in synthetic synthetic_toc; do
    toc=""; [ "$v" = synthetic_toc ] && toc="--toc"
    d="$OUT/lab-run/$v"
    rm -rf "$d" && mkdir -p "$d"
    par python scripts/parser_baseline.py build "$d/$v.pdf" $toc > /dev/null || ok=1
    (cd "$LAB/py" && "$PY" -m docparse parse "$d/$v.pdf" --out "$d/out" --places --engine pdfium) > "$d/summary.json" 2> "$d/err.txt" || ok=1
    res=$("$PY" "$TOOL" check "$d/out" "$FIXED" "$v") || ok=1
    echo "    LAB(pdfium) $res"
  done
  report 5 "동결 (a): LAB(pdfium) == 고정값" "$ok"
fi

if want 6; then
  /bin/bash "$OUT/public-baseline.sh" > "$S4/public-baseline.log" 2>&1
  e=$?
  sed 's/^/    /' "$S4/public-baseline.log"
  report 6 "동결 (b): 공개 보고서 A·B" "$([ "$e" = 0 ] && grep -q '^PUBLIC_BASELINE_FAIL=0$' "$S4/public-baseline.log" && echo 0 || echo 1)"
fi

if want 7; then
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  (cd "$ROOT" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  gates=$(grep '^GATES=' "$S4/check-gates.log" | tail -1)
  echo "    $last / $gates (종료 $e)"
  report 7 "verify.sh --fast · check-gates" "$([ "$last" = "VERIFY_FAST=PASS" ] && [ "$e" = 0 ] && echo 0 || echo 1)"
fi

if want 8; then
  PB1_OUT="$OUT" "$PARSER/scripts/planted-breaks-PB1.sh" > "$S4/planted.log" 2>&1
  e=$?
  grep -E '^\[|^PLANTED|^FINGERPRINT' "$S4/planted.log" | sed 's/^/    /'
  dp=$(git -C "$ROOT" diff --stat -- services/parser/docparse | tail -1)
  echo "    심은 뒤 docparse diff: ${dp:-(없음)}"
  report 8 "PB1 심은 파손" "$([ "$e" = 0 ] && grep -q '^PLANTED=5/5$' "$S4/planted.log" && grep -q '^FINGERPRINT=same' "$S4/planted.log" && [ -z "$dp" ] && echo 0 || echo 1)"
fi

# 이 밴드가 들인 글: 기준 커밋에 있던 파일은 더한 줄만, 새 파일은 전부.
added_text() { # added_text <뿌리 기준 경로>
  if git -C "$ROOT" cat-file -e "$BASE:$1" 2>/dev/null; then
    git -C "$ROOT" diff -U0 "$BASE" -- "$1" | grep '^+' | grep -v '^+++'
  else
    cat "$ROOT/$1"
  fi
}

if want 9; then
  KEYPATH="manufac""-erp|spike""/\\.env" # 키 파일 경로 글. 이 파일에 그 글이 그대로 들지 않게 나눠 적는다
  hits=0; keys=0; opens=0; names=0; mnames=0
  : > "$S4/forbidden-hits.txt"
  if [ ! -f "$WORDS" ]; then
    echo "    낱말 목록이 없다: $WORDS"; hits=1
  else
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if added_text "$f" | grep -F -i -q -f "$WORDS"; then echo "$f" >> "$S4/forbidden-hits.txt"; hits=$((hits + 1)); fi
    done < <(changed_files)
  fi
  msgs=$(git -C "$ROOT" log --format=%B "$BASE..HEAD")
  mhits=0
  if [ -n "$msgs" ] && [ -f "$WORDS" ] && printf '%s' "$msgs" | grep -F -i -q -f "$WORDS"; then mhits=1; fi
  # 보고서 파일 이름 둘(확장자 뺀 이름도). 이름은 찍지 않고 수만 찍는다.
  pats="$S4/report-names.txt"
  (umask 077; : > "$pats")
  if [ -f "$OUT/private.env" ]; then
    sed -nE 's/^PB1_REPORT_[AB]=(.*)$/\1/p' "$OUT/private.env" | while IFS= read -r n; do
      [ -n "$n" ] && printf '%s\n%s\n' "$n" "${n%.pdf}" >> "$pats"
    done
  else
    echo "    private.env 가 없다: $OUT/private.env"; names=1
  fi
  if [ -s "$pats" ]; then
    while IFS= read -r f; do
      [ -f "$ROOT/$f" ] || continue
      if added_text "$f" | grep -F -i -q -f "$pats"; then names=$((names + 1)); fi
    done < <(changed_files)
    if [ -n "$msgs" ] && printf '%s' "$msgs" | grep -F -i -q -f "$pats"; then mnames=1; fi
  fi
  while IFS= read -r f; do
    [ -f "$ROOT/$f" ] || continue
    if added_text "$f" | grep -E -q 'sk-[A-Za-z0-9_-]{20,}'; then echo "    키 꼴: $f"; keys=$((keys + 1)); fi
    if added_text "$f" | grep -E -q "$KEYPATH"; then echo "    키 파일 경로: $f"; opens=$((opens + 1)); fi
  done < <(changed_files)
  [ -n "$msgs" ] && printf '%s' "$msgs" | grep -E -q "sk-[A-Za-z0-9_-]{20,}|$KEYPATH" && keys=$((keys + 1))
  echo "    낱말 $( [ -f "$WORDS" ] && grep -c . "$WORDS" || echo 0)개로 본 파일 $(changed_files | wc -l | tr -d ' ')(더한 줄·새 파일): 걸린 파일 $hits, 커밋 메시지($BASE..HEAD) $mhits"
  echo "    보고서 이름 $(grep -c . "$pats")꼴: 걸린 파일 $names, 커밋 메시지 $mnames / 키 꼴 $keys, 키 파일 경로 $opens"
  cat "$S4/forbidden-hits.txt"
  report 9 "기업명·키·보고서 이름" "$([ "$hits$mhits$names$mnames$keys$opens" = 000000 ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
