#!/usr/bin/env bash
# 밴드 T1a(MARC-TICK-84)의 심은 파손 여덟: 하나씩 심고, 그것을 잡아야 하는 자리가 잡는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-T1a.sh        마지막 줄 PLANTED=<잡은 수>/8
# 0번은 심지 않고 돌린다: 자리 검사 0 · scripts/verify.sh --fast PASS 여야 한다(처음부터 빨간 것을 「잡았다」고 세지 않게.
#   0번이 빨가면 PLANTED 를 내지 않고 종료 1).
# 6번은 대조다: 규칙에 맞는 자리(중간 폴더까지 __init__.py)라 자리 검사가 초록이어야 「잡음」으로 센다.
# 심는 것은 전부 새 파일이거나 허용 목록 한 줄이다. 새 파일은 지우고, 허용 목록은 저장소 밖 임시 폴더의 사본으로
# 되돌린다(git 을 쓰지 않는다. 죽어도 trap 이 되돌린다). 끝에서 `git status --porcelain` 과 `git diff` 의 sha256 이
# 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 자리 검사는 종료 1 이고 **심은 경로**가 **적어 둔 까닭**(R1·R2·R3·필요 없는 허용)으로 찍힌다.
#   --fast 는 끝 줄 VERIFY_FAST=FAIL 이고 **적어 둔 그 단계만** EXIT≠0, EXIT= 15줄.
# 컨테이너 0, 네트워크 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."

A=apps/api-py
ALLOW="$A/scripts/test-layout-allow.txt"
INV="$A/esgapi/inventory/tests"
BODY='"""T1a 가 심은 파일."""


def test_planted() -> None:
    assert sum([1]) == 1
'
LAYOUT_STEP="in_api_py uv run --frozen python scripts/check_test_layout.py"
PURE_STEP="in_api_py uv run --frozen pytest -q -n 4 --durations=15 -m not django_db and not security"

keep="$(mktemp -d)"   # 저장소 밖
log="$(mktemp -d)"
cp "$ALLOW" "$keep/allow"
fingerprint() { git status --porcelain; git diff | shasum -a 256; }
fingerprint > "$keep/.before"
planted=()   # 심은 새 파일·폴더(지울 것)
restore() {
  local p
  for p in "${planted[@]:-}"; do [ -n "$p" ] && rm -rf "$p"; done
  planted=()
  cp "$keep/allow" "$ALLOW"
}
trap 'restore' EXIT INT TERM

put() { # <경로> <내용>   새 파일만 심는다(있으면 종료 3)
  [ -e "$1" ] && { echo "★ 심을 자리에 이미 있다: $1" >&2; exit 3; }
  planted+=("$1")
  printf '%s' "$2" > "$1"
}
newdir() { # <폴더>   새 폴더만(있으면 종료 3)
  [ -e "$1" ] && { echo "★ 심을 자리에 이미 있다: $1" >&2; exit 3; }
  planted+=("$1")
  mkdir -p "$1"
}
layout() { (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$1" 2>&1; }

total=0; ok=0
verdict() { # <번호와 설명> <잡았나 0|1> <나온 것>
  total=$((total + 1))
  if [ "$2" -eq 1 ]; then ok=$((ok + 1)); echo "# $1 → 잡음 · $3"; else echo "# $1 → ★ 못 잡음 · $3"; fi
}
# 자리 검사: 종료 1, 그 경로가 그 까닭으로
layout_catches() { # <번호와 설명> <경로(esgapi/…)> <까닭의 무늬>
  local f="$log/$total.layout" code
  layout "$f"; code=$?
  local line; line="$(grep -F "$2 ← " "$f" | head -1)"
  local caught=0
  [ "$code" -eq 1 ] && printf '%s\n' "$line" | grep -q -E "$3" && caught=1
  verdict "$1" "$caught" "종료 $code · $(head -1 "$f") · ${line:-그 경로의 줄 없음}"
}
# --fast: FAIL, 그 단계만 EXIT≠0, EXIT= 15줄
fast_catches() { # <번호와 설명> <단계 이름>
  local f="$log/$total.fast" code
  scripts/verify.sh --fast > "$f" 2>&1; code=$?
  awk '/^▶ / { n = substr($0, 5) } /^EXIT=/ { print substr($0, 6) "\t" n }' "$f" > "$f.exits"
  local red; red="$(grep -v -E $'^0\t' "$f.exits")"
  local n; n="$(grep -c '^EXIT=' "$f")"
  local caught=0
  [ "$code" -eq 1 ] && [ "$(tail -1 "$f")" = "VERIFY_FAST=FAIL" ] && [ "$n" -eq 15 ] &&
    [ "$(printf '%s\n' "$red" | cut -f2)" = "$2" ] && caught=1
  verdict "$1" "$caught" "종료 $code · 끝 줄 $(tail -1 "$f") · EXIT= ${n}줄 · 빨간 단계: $(printf '%s' "$red" | tr '\t\n' ' ;')"
}

# ── 0. 심지 않고(초록이어야 한다) ──
layout "$log/0.layout"; c0=$?
scripts/verify.sh --fast > "$log/0.fast" 2>&1; f0=$?
echo "# 0 심지 않음 → 자리 검사 종료 $c0 · $(head -1 "$log/0.layout") · --fast 종료 $f0 · 끝 줄 $(tail -1 "$log/0.fast")"
if [ "$c0" -ne 0 ] || [ "$f0" -ne 0 ] || [ "$(tail -1 "$log/0.fast")" != "VERIFY_FAST=PASS" ]; then
  echo "★ 0번이 빨갛다 — 심기 전부터 빨간 것을 잡았다고 세지 않는다. 기록: $log" >&2
  exit 1
fi

# ── 1~6. 자리 검사만 ──
put "$INV/test_scope3_zz_planted.py" "$BODY"
layout_catches "1 inventory/tests/test_scope3_zz_planted.py(평평한 접두사 scope3)" esgapi/inventory/tests/test_scope3_zz_planted.py '← R2 '
restore

newdir "$INV/nowhere"
put "$INV/nowhere/__init__.py" ""
put "$INV/nowhere/test_zz_planted.py" "$BODY"
layout_catches "2 inventory/tests/nowhere/test_zz_planted.py(소스 폴더 없음)" esgapi/inventory/tests/nowhere/test_zz_planted.py '← R1 '
restore

newdir "$INV/calc"
newdir "$INV/calc/scope3"
put "$INV/calc/scope3/test_zz_planted.py" "$BODY"
layout_catches "3 inventory/tests/calc/scope3/test_zz_planted.py(__init__.py 없음)" esgapi/inventory/tests/calc/scope3/test_zz_planted.py '← R3 '
restore

printf '%s\n' esgapi/accounts/tests/test_api.py >> "$ALLOW"
layout_catches "4 허용 목록에 규칙에 맞는 accounts/tests/test_api.py" esgapi/accounts/tests/test_api.py '← 필요 없는 허용'
restore

grep -v -x -F esgapi/inventory/tests/test_scope3_ranking.py "$keep/allow" > "$ALLOW"
layout_catches "5 허용 목록에서 inventory/tests/test_scope3_ranking.py 를 지움" esgapi/inventory/tests/test_scope3_ranking.py '← R2 '
restore

newdir "$INV/calc"
newdir "$INV/calc/scope3"
put "$INV/calc/__init__.py" ""
put "$INV/calc/scope3/__init__.py" ""
put "$INV/calc/scope3/test_zz_planted.py" "$BODY"
layout "$log/6.layout"; c6=$?
c6ok=0
[ "$c6" -eq 0 ] && head -1 "$log/6.layout" | grep -q '어김 0$' && c6ok=1
verdict "6 (대조) inventory/tests/calc/{__init__,scope3/__init__,scope3/test_zz_planted}.py — 초록이어야" "$c6ok" "종료 $c6 · $(head -1 "$log/6.layout")"
restore

# ── 7~8. --fast ──
put "$INV/test_scope3_zz_planted.py" "$BODY"
fast_catches "7 1번을 심고 --fast(자리 검사 단계만 빨갛다)" "$LAYOUT_STEP"
restore

put "$A/esgapi/accounts/tests/test_zz_planted.py" "${BODY/== 1/== 2}"
fast_catches "8 accounts/tests/test_zz_planted.py 의 assert sum([1]) == 2 로 --fast(순수 층 단계만 빨갛다, -n 4 아래)" "$PURE_STEP"
restore

trap - EXIT INT TERM
fingerprint > "$keep/.after"
if ! cmp -s "$keep/.before" "$keep/.after"; then
  echo "★ 되돌린 뒤가 처음과 다르다(git status 나 git diff)" >&2
  diff "$keep/.before" "$keep/.after" >&2
  exit 1
fi
echo "지문 같음: git status --porcelain $(($(wc -l < "$keep/.after") - 1))줄 · git diff sha256 $(tail -1 "$keep/.after" | cut -c1-16) · 기록 $log"
echo "PLANTED=$ok/$total"
[ "$ok" -eq 8 ] && [ "$total" -eq 8 ]
