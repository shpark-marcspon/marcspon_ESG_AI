#!/usr/bin/env bash
# 밴드 PY8c 의 심은 파손 다섯: 하나씩 심고, 그것을 잡아야 하는 검사가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-PY8c.sh --pure         1~4 (컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/4
#         apps/api-py/scripts/planted-breaks-PY8c.sh --containers   5 (compose 가 떠 있어야 한다). 마지막 줄 PLANTED=<잡은 수>/1
#         apps/api-py/scripts/planted-breaks-PY8c.sh                1~5. 마지막 줄 PLANTED=<잡은 수>/5
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 4 는 pdfium 산출(.lab-golden/pdfium, .lab-golden/ts-pdfium)이 있어야 잰다: section4-PY8c.sh --pure 가 앞에서 만든다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

A=apps/api-py
PLANTED_SH="$A/scripts/planted-breaks.sh"
SERVICES="$A/esgapi/inventory/services.py"
REPLAY="$A/esgapi/inventory/tests/assembly_replay.py"
ASSEMBLY="$A/esgapi/inventory/tests/data/handcalc-assembly.json"
DIGEST="$A/esgapi/reconcile/tests/golden/lab-digest.pdfium.json"
ADAPTER_INSIDE=/app/.venv/lib/python3.13/site-packages/esgapi/core/adapters/parser.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$PLANTED_SH" "$SERVICES" "$REPLAY" "$ASSEMBLY" "$DIGEST")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
container_planted=0
restore_container() {
  [ "$container_planted" -eq 1 ] || return 0
  docker compose up -d --force-recreate --wait api-py > "$log/recreate.txt" 2>&1
  container_planted=0
}
trap 'restore_files; restore_container' EXIT INT TERM

total=0; ok=0
verdict() { # <번호와 설명> <잡았으면 0>
  total=$((total + 1))
  if [ "$2" -eq 0 ]; then ok=$((ok + 1)); echo "$1 → 잡음"; else echo "$1 → ★ 못 잡음"; fi
  restore_files
}
edit() { # <파일> <있던 글자> <바꿀 글자>   글자가 정확히 한 번 있어야 한다(없으면 심지 못한 것이다: 종료 3)
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}

pure() {
  # 1. create() 를 고치기 전 꼴로: 이미 있는 파일도 「새로 만든 것」으로 적어 되돌릴 때 지운다.
  #    빨개져야 하는 것: planted-breaks.sh 의 끝 검사(종료 1, 「작업 트리가 처음과 다르다」). PLANTED=10/10 은 그대로 나온다.
  edit "$PLANTED_SH" 'if [ -e "$1" ]; then cp "$1" "$backup/$(echo "$1" | tr / _)"; touched+=("$1"); else created+=("$1"); fi' 'created+=("$1")' || exit 3
  "$PLANTED_SH" > "$log/1.txt" 2>&1; code=$?
  gone=1; [ -f "$SERVICES" ] || gone=0
  tail -4 "$log/1.txt" | sed 's/^/    /'
  echo "    (종료 $code · 추적 파일 services.py 가 $([ "$gone" -eq 0 ] && echo 지워졌다 || echo 남아 있다))"
  [ "$code" -eq 1 ] && grep -q '작업 트리가 처음과 다르다' "$log/1.txt" && grep -q 'esgapi/inventory/services.py' "$log/1.txt" && grep -q '^PLANTED=10/10$' "$log/1.txt" && [ "$gone" -eq 0 ]
  verdict "1. planted-breaks.sh 의 create() 를 고치기 전 꼴로(있는 파일을 created 에)" $?
  # 되돌린 뒤 두 파일이 처음과 같은가. 다르면 더 가지 않는다.
  if ! sums | diff - "$keep/.sums-before" > /dev/null; then echo "★ 1 을 되돌린 뒤 파일이 처음과 다르다"; sums | diff - "$keep/.sums-before"; exit 1; fi

  # 2. 재통과가 조립한 계수 대신 패키지의 표본 표를 넣는다. 표본으로 계산이 되게 활동 데이터의 이름 바꾸기도 뺀다
  #    (표본 표만 넣으면 이름이 안 맞아 「계수 없음」으로 요란하게 깨진다. 조용히 표본으로 계산되는 쪽을 심는다).
  #    빨개져야 하는 것: 재통과의 evidence.factor.id 대조(「계수: … 로 계산됐다」) → test_the_engine_used_the_assembled_factor_…
  edit "$REPLAY" 'factors = [factor]' 'factors = read_data("factors.kr-ets-sample.json")["factors"]' || exit 3
  edit "$REPLAY" 'return {**activity, **patch}' 'return dict(activity)' || exit 3
  (cd "$A" && uv run --frozen pytest -q -rf -m "not django_db and not security" esgapi/inventory/tests/test_assembly_replay.py) > "$log/2.txt" 2>&1; code=$?
  grep -E '^FAILED|^[0-9]+ (passed|failed)' "$log/2.txt" | sed 's/^/    /' | cut -c1-200
  grep -o '계수: [^ ]* 로 계산됐다' "$log/2.txt" | sort | uniq -c | sed 's/^/    /'
  [ "$code" -ne 0 ] && grep -q '^FAILED .*test_the_engine_used_the_assembled_factor_and_not_a_sample' "$log/2.txt" && grep -q '계수: kr-ets-sample:.* 로 계산됐다' "$log/2.txt"
  verdict "2. 재통과가 조립한 계수 대신 패키지의 표본 표로 계산" $?

  # 3. 사본의 N01 기대 co2e 한 글자(2.6170848 → 2.6170849). 빨개져야 하는 것: 재통과 (나)의 N01.
  edit "$ASSEMBLY" '"co2e": "2.6170848"' '"co2e": "2.6170849"' || exit 3
  (cd "$A" && uv run --frozen pytest -q -rf -m "not django_db and not security" esgapi/inventory/tests/test_assembly_replay.py) > "$log/3.txt" 2>&1; code=$?
  grep -E '^FAILED|^[0-9]+ (passed|failed)' "$log/3.txt" | sed 's/^/    /' | cut -c1-200
  [ "$code" -ne 0 ] && grep -q '^FAILED .*test_replayed_value_equals_the_hand_calculation\[N01\]' "$log/3.txt"
  verdict "3. handcalc-assembly.json 사본의 N01 기대 co2e 한 글자" $?

  # 4. pdfium digest 의 건수 하나(첫 문서의 facts 2938 → 2939). 빨개져야 하는 것: check_lab --digest lab-digest.pdfium.json
  if [ -f "$A/.lab-golden/pdfium/kb_2025_kor/document.json" ] && [ -f "$A/.lab-golden/ts-pdfium/kb_2025_kor.json" ]; then
    python3 - "$DIGEST" <<'PY' || exit 3
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
old = '"count": 2938'
if old not in text:
    sys.exit(f"심을 자리가 없다: {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, '"count": 2939', 1))
PY
    (cd "$A" && uv run --frozen python -m esgapi.reconcile.tests.golden.check_lab --input .lab-golden/pdfium --ts .lab-golden/ts-pdfium --digest esgapi/reconcile/tests/golden/lab-digest.pdfium.json) > "$log/4.txt" 2>&1; code=$?
    grep -E '^★|^골든' "$log/4.txt" | sed 's/^/    /' | cut -c1-200
    [ "$code" -ne 0 ] && grep -q '^★ kb_2025_kor: .*digest' "$log/4.txt" && grep -q '^골든: 다르다' "$log/4.txt"
    verdict "4. lab-digest.pdfium.json 의 건수 하나" $?
  else
    total=$((total + 1))
    echo "4. lab-digest.pdfium.json 의 건수 하나 → ★ 못 잼(pdfium 산출이 없다: section4-PY8c.sh --pure 가 먼저 만든다)"
  fi
}

containers() {
  # 5. 어댑터의 Content-Type 을 application/json 으로. 이미지에 실린 코드를 컨테이너 안에서 바꾼다(.venv 는 root 소유라 -u 0).
  #    테스트가 exec 로 새 파이썬을 띄우므로 gunicorn 을 다시 켤 필요가 없다. 되돌리기는 컨테이너를 새로 만드는 것이다.
  #    빨개져야 하는 것: tests_integration/test_parser_flow.py. 까닭: 파서에서 application/json 은 옛 약속의 갈래라
  #    415 가 아니라 본문(PDF)의 JSON 검증 실패 422 → 어댑터의 rejected.
  total=$((total + 1))
  if ! docker compose exec -T api-py grep -q '"Content-Type": "application/pdf"' "$ADAPTER_INSIDE" 2> "$log/5-pre.txt"; then
    echo "5. 어댑터의 Content-Type 을 application/json 으로 → ★ 못 잼(떠 있는 api-py 에서 심을 자리를 찾지 못했다)"; cat "$log/5-pre.txt"; return
  fi
  container_planted=1
  if ! docker compose exec -u 0 -T api-py sed -i 's#"Content-Type": "application/pdf"#"Content-Type": "application/json"#' "$ADAPTER_INSIDE" 2> "$log/5-sed.txt" \
    || ! docker compose exec -T api-py grep -q '"Content-Type": "application/json"' "$ADAPTER_INSIDE"; then
    echo "5. 어댑터의 Content-Type 을 application/json 으로 → ★ 못 잼(컨테이너 안의 파일을 바꾸지 못했다)"; cat "$log/5-sed.txt"; restore_container; return
  fi
  (cd "$A" && uv run --frozen pytest -q -rf -c tests_integration/pytest.ini tests_integration/test_parser_flow.py) > "$log/5.txt" 2>&1; code=$?
  grep -E '^FAILED|^[0-9]+ (passed|failed)' "$log/5.txt" | sed 's/^/    /' | cut -c1-200
  grep -o "{'kind': '[a-z_]*', 'detail': '[^']*', 'code': [^,]*, 'status': [0-9A-Za-z]*}" "$log/5.txt" | sort -u | sed 's/^/    본 갈래: /'
  caught=1
  [ "$code" -ne 0 ] && grep -q '^FAILED .*test_adapter_reaches_the_running_parser' "$log/5.txt" && grep -q "'kind': 'rejected'" "$log/5.txt" && caught=0
  restore_container
  # 되돌린 것을 잰다: 새 컨테이너의 어댑터는 다시 application/pdf 이고 같은 테스트가 초록이다.
  back=1
  docker compose exec -T api-py grep -q '"Content-Type": "application/pdf"' "$ADAPTER_INSIDE" \
    && (cd "$A" && uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration/test_parser_flow.py) > "$log/5-back.txt" 2>&1 && back=0
  echo "    (되돌린 뒤: 어댑터 application/pdf, 같은 테스트 $([ "$back" -eq 0 ] && echo 초록 || echo '★ 빨강'))"
  if [ "$caught" -eq 0 ] && [ "$back" -eq 0 ]; then ok=$((ok + 1)); echo "5. 어댑터의 Content-Type 을 application/json 으로 → 잡음"
  else echo "5. 어댑터의 Content-Type 을 application/json 으로 → ★ 못 잡음"; tail -30 "$log/5.txt"; fi
}

case "$MODE" in
  --pure) pure ;;
  --containers) containers ;;
  all) pure; containers ;;
esac

# ── 끝 검사: 베껴 둔 파일과 작업 트리가 처음과 같은가 ──
restore_files
if ! sums | diff "$keep/.sums-before" - || ! git status --porcelain | diff "$keep/.status-before" -; then
  echo "★ 작업 트리가 처음과 다르다(< 처음, > 지금). PLANTED 를 내지 않는다"
  exit 1
fi
echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ]
