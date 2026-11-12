#!/usr/bin/env bash
# 밴드 LT1 의 §4 자기검증(발주서 band-handoffs/LT1-order.md §4 — core.llm 에 temperature 자리).
# 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-LT1.sh                  전부
#   apps/api-py/scripts/section4-LT1.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-LT1.sh --after-commit   전부 + git status --porcelain 0
#
# 환경 변수:
#   LT1_BASE   기준 커밋(기본: 워크트리를 만들 때의 main d64d5e2)
#   LT1_OUT    산출물 자리(기본: 워크트리 곁의 LT1.out). 산출물은 $LT1_OUT/section4/ 아래
# 컨테이너는 쓰지 않는다(이 밴드는 업무 층을 건드리지 않는다). 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# 5 는 gen-ts-types.sh 를 다시 돌린다(pnpm dlx openapi-typescript — 네트워크와 node/pnpm PATH 가 필요하다).
# 실제 LLM 호출 0, API 키를 읽지 않는다. macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${LT1_BASE:-d64d5e2}"
OUT="${LT1_OUT:-$SIDE/LT1.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
A="apps/api-py"
E="$A/esgapi"

STEPS="all"
AFTER=0
case "${1:-}" in
  --step) STEPS=",${2:?--step 뒤에 번호}," ;;
  --after-commit) AFTER=1 ;;
  "") ;;
  *) echo "사용: $0 [--step 1,2,… | --after-commit]"; exit 2 ;;
esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse --short HEAD), 산출물 $S4"

# ── 1. 빠른 게이트 ──
if want 1; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  echo "    $last"
  report 1 "verify.sh --fast" "$([ "$last" = "VERIFY_FAST=PASS" ] && echo 0 || echo 1)"
fi

# ── 2. core 의 llm 시험(순수 층. DB 를 쓰는 test_llm_sink_db 는 업무 층이라 뺀다 — 이 밴드는 그 길을 건드리지 않는다) ──
if want 2; then
  (cd "$API_PY" && PYTHONPYCACHEPREFIX="$S4/pycache" uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" \
    esgapi/core/tests/llm esgapi/core/tests/test_llm_*.py) > "$S4/llm-tests.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/llm-tests.log") (종료 $e)"
  report 2 "core 의 llm 시험" "$e"
fi

# ── 3. 심은 파손: 빨강, 되돌린 뒤 지문 같음 ──
if want 3; then
  (cd "$API_PY" && uv run --frozen python - "$S4" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1])
types_py = Path("esgapi/core/llm/types.py")
client_py = Path("esgapi/core/llm/client.py")
openai_py = Path("esgapi/core/llm/providers/openai.py")
T = "esgapi/core/tests/llm/test_temperature.py::"


def fingerprint() -> str:
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True)
    diff = subprocess.run(["git", "diff", "HEAD", "--", "."], capture_output=True)
    return status.stdout + hashlib.sha256(diff.stdout).hexdigest()


def plant(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


BREAKS = [
    (
        "if temperature: — 0.0 이 빠짐(to_json)",
        types_py,
        "        if self.temperature is not None:\n",
        "        if self.temperature:\n",
        T + "test_zero_temperature_goes_into_the_neutral_body_and_changes_the_hash",
    ),
    (
        "to_json 이 None 도 실음 — 기존 해시가 바뀜",
        types_py,
        "        if self.temperature is not None:\n",
        "        if True:\n",
        T + "test_without_temperature_bodies_and_hashes_match_the_baseline_commit",
    ),
    (
        "if request.temperature: — 0.0 이 빠짐(openai 어댑터)",
        openai_py,
        "        if request.temperature is not None:\n",
        "        if request.temperature:\n",
        T + "test_openai_adapter_sends_zero_temperature",
    ),
    (
        "openai 어댑터에서 싣기 뺌",
        openai_py,
        "        if request.temperature is not None:\n            params[\"temperature\"] = request.temperature\n",
        "",
        T + "test_openai_adapter_sends_zero_temperature",
    ),
    (
        "경로 검사 뺌 — 대체 모델이 받지 않는 경로가 지나감(덤)",
        client_py,
        "        _check_temperature(request.temperature, models)\n",
        "",
        T + "test_temperature_on_a_route_with_an_unsupported_model_is_refused_before_any_call[mock-then-luna-keys4]",
    ),
]

before = fingerprint()
ok = 0
pycache = {**os.environ, "PYTHONPYCACHEPREFIX": str(out / "pycache")}
for i, (name, path, old, new, test) in enumerate(BREAKS, 1):
    held = path.read_bytes()
    try:
        plant(path, old, new)
        done = subprocess.run(
            ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", test],
            capture_output=True, text=True, check=False, env=pycache,
        )
    finally:
        path.write_bytes(held)
    (out / f"planted-{i}.log").write_text(done.stdout + done.stderr, encoding="utf-8")
    red = done.returncode != 0 and "1 failed" in done.stdout
    ok += red
    print(f"    {i}. {name} → {'빨강' if red else '★ 초록(안 걸림)'} ({test.split('::')[1]})")
same = fingerprint() == before
print(f"PLANTED={ok}/{len(BREAKS)}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
sys.exit(0 if ok == len(BREAKS) and same else 1)
PY
  ) > "$S4/planted.log" 2>&1
  e=$?
  cat "$S4/planted.log"
  report 3 "심은 파손 다섯 빨강·지문 같음" "$e"
fi

# ── 4. 허용 경로 밖 diff 0, greenwash·models.json·게이트 파일 diff 0 ──
ALLOWED="^($E/core/llm/(types|client)\.py|$E/core/llm/providers/[a-z_]+\.py|$E/core/llm/data/README\.md|$E/core/tests/(test_llm_[a-z_]+|llm_support|llm/.+)\.py|$A/scripts/section4-LT1\.sh)$"
ZERO=(
  "$E/greenwash" "$E/core/llm/data/models.json"
  compose.yaml docker scripts/verify.sh scripts/check-gates.sh scripts/git-hooks .importlinter "$A/.importlinter"
  .env.example "$A/generated" apps/web "$A/pyproject.toml" "$A/uv.lock" pnpm-lock.yaml
)
if want 4; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } \
    | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(grep -c . "$S4/outside.txt")
  zero=$(git -C "$ROOT" diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)
  zero_new=$(git -C "$ROOT" ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)
  pre=$(grep -c '^\.pre-commit' "$S4/changed.txt")
  echo "    바뀐 파일 $(grep -c . "$S4/changed.txt"), 허용 밖 $n, 0줄 목록 $zero(+새 파일 $zero_new), .pre-commit* $pre"
  sed 's/^/    바뀜: /' "$S4/changed.txt"
  sed 's/^/    밖: /' "$S4/outside.txt"
  report 4 "허용 밖 0·greenwash·models.json·게이트 0" "$([ "$n$zero$zero_new$pre" = 0000 ] && echo 0 || echo 1)"
fi

# ── 5. generated/ 같음(다시 뽑아 diff 0) ──
if want 5; then
  G="$A/generated"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  ge=$?
  git -C "$ROOT" diff --quiet "$BASE" -- "$G"
  d=$?
  new=$(git -C "$ROOT" ls-files -o --exclude-standard -- "$G" | grep -c .)
  echo "    다시 뽑기 종료 $ge · 기준 대비 diff $([ "$d" = 0 ] && echo 0 || echo 있음) · 새 파일 $new"
  report 5 "generated 같음" "$([ "$ge$d$new" = 000 ] && echo 0 || echo 1)"
fi

# ── 6. 게이트 자기 검사 ──
if want 6; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  echo "    $(grep '^GATES=' "$S4/check-gates.log" | tail -1) (종료 $e)"
  report 6 "check-gates.sh" "$e"
fi

if [ "$AFTER" = 1 ]; then
  porcelain=$(git -C "$ROOT" status --porcelain)
  echo "    git status --porcelain: $(printf '%s' "$porcelain" | grep -c .) 줄"
  [ -n "$porcelain" ] && printf '%s\n' "$porcelain" | sed 's/^/    /'
  report after "커밋 뒤 작업 트리 깨끗함" "$([ -z "$porcelain" ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
