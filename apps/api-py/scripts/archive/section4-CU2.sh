#!/usr/bin/env bash
# 밴드 CU2 의 §4 자기검증(발주서 band-handoffs/CU2-order.md §4 — core/registry 걷기, 가짜 둘을 제품 밖으로,
# js_string(None) 재현, SESSION_SECRET 경고). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-CU2.sh                  전부
#   apps/api-py/scripts/section4-CU2.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-CU2.sh --after-commit   전부 + git status --porcelain 0
#
# 환경 변수:
#   CU2_BASE   기준 커밋(기본: 워크트리를 만들 때의 main e646b27)
#   CU2_OUT    산출물 자리(기본: 워크트리 곁의 CU2.out). 산출물은 $CU2_OUT/section4/ 아래
#   CU2_FORBIDDEN_WORDS_FILE  회사 이름 낱말 목록(기본: 워크트리 곁의 G1a.out/forbidden-words.txt — 이 파일만 연다)
# 2 는 이 워크트리의 compose(.env 의 COMPOSE_PROJECT_NAME)의 postgres 가 떠 있어야 한다 — 띄우고 내리는 일은
# 부르는 쪽(러너의 컨테이너 규칙)이 한다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# 6 은 gen-ts-types.sh 를 다시 돌린다(pnpm dlx openapi-typescript@7.13.0 — 네트워크와 node/pnpm PATH 가 필요하다).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${CU2_BASE:-e646b27}"
OUT="${CU2_OUT:-$SIDE/CU2.out}"
WORDS="${CU2_FORBIDDEN_WORDS_FILE:-$SIDE/G1a.out/forbidden-words.txt}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
A="apps/api-py"
E="$A/esgapi"
SELF="$A/scripts/section4-CU2.sh"

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

# ── 2. 가짜·registry 를 쓰던 업무·보안 시험 그 층만(컨테이너) ──
BUSINESS_TESTS="esgapi/core/tests/service/apis/test_runs.py esgapi/core/tests/test_documents_api.py
esgapi/core/tests/test_documents_services.py esgapi/core/tests/test_jobs_services.py
esgapi/core/tests/test_observability_api.py esgapi/core/tests/test_selectors_tenant.py
esgapi/reconcile/tests/test_tasks_parse.py"
SECURITY_TESTS="tests/security/test_documents.py tests/security/test_documents_race.py tests/security/test_jobs.py
tests/security/test_tenant_paths.py"
if want 2; then
  # shellcheck disable=SC2086  # 파일 목록을 낱말로 나눈다
  (cd "$API_PY" && scripts/test-business.sh -p no:cacheprovider $BUSINESS_TESTS) > "$S4/business.log" 2>&1
  b=$?
  # shellcheck disable=SC2086
  (cd "$API_PY" && scripts/test-security.sh -p no:cacheprovider $SECURITY_TESTS) > "$S4/security.log" 2>&1
  s=$?
  echo "    업무: $(tail -1 "$S4/business.log") (종료 $b)"
  echo "    보안: $(tail -1 "$S4/security.log") (종료 $s)"
  report 2 "업무·보안 층(가짜를 쓰는 파일 열하나)" "$([ "$b$s" = 00 ] && echo 0 || echo 1)"
fi

# ── 3. 제품 모듈(esgapi/** 의 tests·testing 밖)에 FakeStorage|FakeParser|core.registry 0 ──
if want 3; then
  git -C "$ROOT" grep -n -E 'FakeStorage|FakeParser|core\.registry|from esgapi\.core import registry' -- \
    "$E" ":(exclude,glob)$E/**/tests/**" ":(exclude,glob)$E/**/testing.py" > "$S4/product-grep.txt"
  n=$(grep -c . "$S4/product-grep.txt")
  fake=$(git -C "$ROOT" grep -n -F '"fake"' -- "$E/core/resources" | grep -c .)
  reg=$([ -e "$ROOT/$E/core/registry.py" ] && echo 1 || echo 0)
  echo "    제품 모듈의 걸림 $n · core/resources 의 \"fake\" $fake · core/registry.py 있음 $reg"
  cat "$S4/product-grep.txt"
  report 3 "제품 모듈에 가짜·registry 0" "$([ "$n$fake$reg" = 000 ] && echo 0 || echo 1)"
fi

# ── 4. 심은 파손 넷: 빨강, 되돌린 뒤 지문 같음 ──
if want 4; then
  (cd "$API_PY" && uv run --frozen python - "$S4" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1])
storage = Path("esgapi/core/resources/storage.py")
parser = Path("esgapi/core/resources/parser.py")
env = Path("esgapi/config/env.py")
T_STORAGE = "esgapi/core/tests/test_storage_adapter.py::test_the_product_module_has_no_fake_and_make_refuses_it"
T_PARSER = "esgapi/core/tests/test_parser_port.py::test_the_product_module_has_no_fake_and_make_refuses_it"
T_ENV = "esgapi/config/tests/test_env.py::test_a_local_only_session_secret_starts_but_warns_loudly"
T_ENV_VALUE = "esgapi/config/tests/test_env.py::test_the_warning_does_not_print_the_secret_value"


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
        "make(\"fake\") 되살림(storage)",
        storage,
        '    if name != "s3":\n',
        '    if name == "fake":\n'
        "        from esgapi.core.tests.resource_fakes import FakeStorage\n\n"
        "        return FakeStorage(upload_ttl_s=upload_ttl_s)\n"
        '    if name != "s3":\n',
        T_STORAGE,
    ),
    (
        "ADAPTERS 의 \"fake\" 되살림(parser)",
        parser,
        'ADAPTERS: Final[tuple[str, ...]] = ("http",)',
        'ADAPTERS: Final[tuple[str, ...]] = ("http", "fake")',
        T_PARSER,
    ),
    ("local-only- 경고 끔", env, "    if warning is not None:\n", "    if False and warning is not None:\n", T_ENV),
    (
        "경고에 SESSION_SECRET 값을 찍음",
        env,
        "        print(warning, file=sys.stderr)",
        "        print(warning, session_secret, file=sys.stderr)",
        T_ENV_VALUE,
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
  report 4 "심은 파손 넷 빨강·지문 같음" "$e"
fi

# ── 5. 허용 경로 밖 diff 0, 게이트 파일 diff 0, 0줄 목록 diff 0, 회사 이름 줄 diff 0 ──
# 허용: 발주서 §1 + 감독 허락(2026-10-16 저녁, sid:MARC-TICK-126 노트: planted-breaks.sh 1번·core/__init__.py 머리말
# 한 줄·resources/llm.py 머리말 구절, 가짜 자리 resource_fakes.py 와 tests/security 넷의 import 줄, 검증 뒤 ports 머리말 둘).
ALLOWED="^($E/core/(registry|__init__)\.py|$E/core/resources/(storage|parser|llm)\.py|$E/core/resources/ports/(storage|parser)\.py|$E/[a-z_]+/tests/.+\.py|$E/inventory/calc/(jsrepr|activity|aggregate)\.py|$E/config/env\.py|$A/tests/security/test_(documents|documents_race|jobs|tenant_paths)\.py|$A/scripts/(section4-CU2|planted-breaks)\.sh)$"
ZERO=(
  "$E/greenwash" "$E/inventory/xlsx_reader.py" "$E/inventory/calc/scope3_sheets" "$E/core/flows/registry.py"
  "$E/core/auth" "$E/core/tenancy" "$E/core/isolation" "$E/core/calc/documents.py"
  compose.yaml docker scripts/verify.sh scripts/check-gates.sh .pre-commit-config.yaml "$A/.importlinter" .env.example
  apps/web "$A/generated" services/parser "$A/pyproject.toml" "$A/uv.lock" pnpm-lock.yaml
)
if want 5; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } \
    | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(grep -c . "$S4/outside.txt")
  zero=$(git -C "$ROOT" diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)
  zero_new=$(git -C "$ROOT" ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)
  pre=$(grep -c '^\.pre-commit' "$S4/changed.txt")
  if [ -f "$WORDS" ]; then
    names=$(git -C "$ROOT" diff "$BASE" -- . ":!$SELF" | grep '^[-+][^-+]' | grep -c -F -i -f "$WORDS")
    names_new=$(git -C "$ROOT" ls-files -o --exclude-standard -z | (cd "$ROOT" && xargs -0 cat 2>/dev/null) \
      | grep -c -F -i -f "$WORDS")
  else
    echo "    낱말 목록이 없다: $WORDS"; names=1; names_new=0
  fi
  echo "    바뀐 파일 $(grep -c . "$S4/changed.txt"), 허용 밖 $n, 0줄 목록 $zero(+새 파일 $zero_new), .pre-commit* $pre, 회사 이름 줄 $names(+새 파일 $names_new)"
  sed 's/^/    밖: /' "$S4/outside.txt"
  report 5 "허용 밖 0·게이트·0줄 목록 0·회사 이름 줄 0" "$([ "$n$zero$zero_new$pre$names$names_new" = 000000 ] && echo 0 || echo 1)"
fi

# ── 6. generated/ 같음(다시 뽑아 diff 0) ──
if want 6; then
  G="$A/generated"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  ge=$?
  git -C "$ROOT" diff --quiet "$BASE" -- "$G"
  d=$?
  new=$(git -C "$ROOT" ls-files -o --exclude-standard -- "$G" | grep -c .)
  echo "    다시 뽑기 종료 $ge · 기준 대비 diff $([ "$d" = 0 ] && echo 0 || echo 있음) · 새 파일 $new"
  report 6 "generated 같음" "$([ "$ge$d$new" = 000 ] && echo 0 || echo 1)"
fi

# ── 7. 게이트 자기 검사 ──
if want 7; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  e=$?
  echo "    $(grep '^GATES=' "$S4/check-gates.log" | tail -1) (종료 $e)"
  report 7 "check-gates.sh" "$e"
fi

if [ "$AFTER" = 1 ]; then
  porcelain=$(git -C "$ROOT" status --porcelain)
  echo "    git status --porcelain: $(printf '%s' "$porcelain" | grep -c .) 줄"
  [ -n "$porcelain" ] && printf '%s\n' "$porcelain" | sed 's/^/    /'
  report after "커밋 뒤 작업 트리 깨끗함" "$([ -z "$porcelain" ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
