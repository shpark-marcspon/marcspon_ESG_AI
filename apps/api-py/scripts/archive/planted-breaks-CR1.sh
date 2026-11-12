#!/usr/bin/env bash
# 밴드 CR1(MARC-TICK-200: 개발 compose 저장소 CORS)의 심은 파손. 발주서 §3-4.
#   사용: apps/api-py/scripts/planted-breaks-CR1.sh                    빠른 일곱(P3~P9)
#         apps/api-py/scripts/planted-breaks-CR1.sh --with-containers  + 컨테이너 셋(P1·P2·P10) = 10
# 하나씩 심고, 표적 시험이 빨개지는지 보고, 되쓴다. 끝 줄 PLANTED=<잡은>/<심은> 과 FINGERPRINT=same|changed.
# ★ 되쓰기는 같은 inode 로(cat 원본 > 파일). docker/storage_cors.py 는 :ro 단일 파일 바인드 마운트라
#   mv·새 파일로 바꾸면 컨테이너가 옛 inode 를 본다.
# ★ 컨테이너 몫은 떠 있는 이 워크트리의 compose(section4-CR1.sh --with-containers 가 띄움)에서만 돈다.
#   심은 상태로 storage-cors 를 다시 돌리고(Exited (0)·api-py healthy 를 먼저 단언) 통합 표적을 돌린 뒤,
#   되쓰고 storage-cors 를 다시 돌려 규칙을 원래대로 쓴다. `up` 실패는 빨강으로 세지 않는다.
# 키 값은 찍지 않는다. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
WITH_CONTAINERS=0
case "${1:-}" in
  "") ;;
  --with-containers) WITH_CONTAINERS=1 ;;
  *) echo "사용: $0 [--with-containers]" >&2; exit 2 ;;
esac

T="$(mktemp -d)"
FILES=(docker/storage_cors.py compose.yaml scripts/worktree-env.sh)
fingerprint() { for f in "${FILES[@]}"; do printf '%s %s\n' "$(shasum -a 256 "$f" | cut -d' ' -f1)" "$(stat -f %i "$f")"; done; }
BEFORE="$(fingerprint)"
for f in "${FILES[@]}"; do cp "$f" "$T/$(basename "$f").orig"; done
# 끊겨도(Ctrl-C·SIGTERM) 심은 파손을 남기지 않는다: 원본을 같은 inode 로 되쓰고 지운다.
# INT·TERM 은 exit 만 한다(되쓰기는 EXIT 한 곳) — bash 는 INT·TERM trap 뒤에 스크립트를 이어 돌려서, 거기서 $T 를
# 지우면 다음 심기가 없는 사본으로 원본을 비운다(2026-10-20 실측: TERM 한 번에 원본 셋이 빈 파일).
trap 'for f in "${FILES[@]}"; do [ -f "$T/$(basename "$f").orig" ] && cat "$T/$(basename "$f").orig" > "$f"; done; rm -rf "$T"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

PLANTED=0
CAUGHT=0
ROWS=()

# replace <파일> <옛 글자> <새 글자>: 옛 글자가 꼭 한 번 있어야 한다. 같은 inode 로 쓴다.
replace() {
  python3 - "$1" "$2" "$3" > "$T/new" <<'PY' || return 1
import sys
path, old, new = sys.argv[1:]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)} 번 있다: {old!r}")
sys.stdout.write(text.replace(old, new))
PY
  cat "$T/new" > "$1"
}
restore() { cat "$T/$(basename "$1").orig" > "$1"; }

# P9: storage-cors 덩어리를 api-py 와 migrate-py 사이로 옮긴다.
move_between_api_py_and_migrate_py() {
  python3 - compose.yaml > "$T/new" <<'PY' || return 1
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
found = re.search(r"\n  storage-cors:\n.*?(?=\n\n  queue:\n)", text, re.S)
assert found is not None
block = found.group(0)
text = text.replace(block, "", 1)
at = text.index("\n\n  migrate-py:\n")
sys.stdout.write(text[:at] + "\n" + block + text[at:])
PY
  cat "$T/new" > compose.yaml
}

# fast <번호> <시험 노드…>: 표적 시험이 빨개져야(그 노드가 FAILED 로 나와야) 잡은 것이다.
fast() {
  local id="$1"; shift
  local out="$T/$id.log" red=""
  (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider "$@") > "$out" 2>&1
  red="$(sed -n 's/^FAILED \([^ ]*\).*/\1/p' "$out" | sed 's/.*:://' | sort -u | tr '\n' ' ')"
  echo "$red"
}

record() {   # record <번호> <심은 것> <빨개진 것> <기대 표적>
  PLANTED=$((PLANTED + 1))
  local verdict="놓침"
  case " $3 " in *" $4 "*) CAUGHT=$((CAUGHT + 1)); verdict="잡음" ;; esac
  ROWS+=("$1 | $2 | ${3:-(없음)} | $verdict")
  echo "  $1 $verdict — 빨강: ${3:-(없음)}"
}

FAST_TESTS=esgapi/config/tests/test_compose_storage_cors.py
echo "▶ 빠른 파손 일곱"

replace docker/storage_cors.py 'ALLOWED_METHODS = ("PUT", "GET", "HEAD")' 'ALLOWED_METHODS = ("GET", "HEAD")' \
  && record P3 "ALLOWED_METHODS 에서 PUT 뺌" "$(fast P3 "$FAST_TESTS")" test_the_rule_has_the_same_shape_as_the_terraform_one
restore docker/storage_cors.py

replace compose.yaml '      VGW_HEALTH: /health
' '      VGW_HEALTH: /health
      VGW_CORS_ALLOW_ORIGIN: http://localhost:15999
' && record P4 "storage 에 VGW_CORS_ALLOW_ORIGIN" "$(fast P4 "$FAST_TESTS")" test_the_storage_has_no_global_cors_fallback
restore compose.yaml

replace compose.yaml '      storage-cors: { condition: service_completed_successfully }
' '' && record P5 "api-py 의 storage-cors depends_on 지움" "$(fast P5 "$FAST_TESTS")" test_api_py_starts_after_the_rule_is_written
restore compose.yaml

replace compose.yaml ',http://localhost:${API_PY_PORT:-18081},http://127.0.0.1:${API_PY_PORT:-18081}}' '}' \
  && record P6 "기본 출처에서 API_PY_PORT 둘 뺌" "$(fast P6 "$FAST_TESTS")" test_the_storage_cors_block_writes_the_web_origins_once
restore compose.yaml

replace docker/storage_cors.py 'ORIGIN = re.compile(r"^https?://[^/\s*]+$")' 'ORIGIN = re.compile(r"^https?://[^/\s*]+/?$")' \
  && record P7 "parse_origins 의 끝 / 거절 지움" "$(fast P7 "$FAST_TESTS")" test_parse_origins_keeps_the_order_and_refuses_the_rest
restore docker/storage_cors.py

if replace scripts/worktree-env.sh '-e "s/^WEB_PORT=.*/WEB_PORT=$(( base + 4 ))/"' '-e "s/^WEB_PORT=.*/WEB_PORT=$(( base + 5 ))/"'; then
  if "$A/scripts/check-worktree-env.sh" > "$T/P8.log" 2>&1; then red=""; else red="check-worktree-env.sh"; fi
  record P8 "worktree-env 의 WEB_PORT base+4 → base+5" "$red" check-worktree-env.sh
fi
restore scripts/worktree-env.sh

# P9 는 test_env.py 의 저장소 키 시험이 가려서(초록) 빠른 6 만 빨개진다 — 둘 다 돌려 「6 만」을 본다.
if move_between_api_py_and_migrate_py; then
  red="$(fast P9 "$FAST_TESTS" esgapi/config/tests/test_env.py)"
  [ "$red" = "test_the_storage_cors_block_sits_between_storage_and_queue " ] || red="$red(6 말고도 빨강)"
  record P9 "storage-cors 를 api-py 와 migrate-py 사이로" "$red" test_the_storage_cors_block_sits_between_storage_and_queue
fi
restore compose.yaml

if [ "$WITH_CONTAINERS" = 1 ]; then
  echo
  echo "▶ 컨테이너 파손 셋"
  INTEGRATION=tests_integration/test_storage_cors.py
  # rerun_rule: storage-cors 를 다시 돌리고 Exited (0)·api-py healthy 를 단언한다. 실패면 1(빨강으로 세지 않는다).
  # 바인드 마운트의 파일을 컨테이너가 호스트와 같은 바이트로 보는지 sha256 으로 확인한다(최대 20초).
  # Docker Desktop 의 파일 공유는 같은 inode 로 되쓴 직후 옛 크기로 잘린 글을 보일 때가 있다(1차 실행 P2·P10 의
  # SyntaxError — 2026-10-20 실측).
  same_bytes_inside() {
    local want got tries=0
    want="$(shasum -a 256 docker/storage_cors.py | cut -d' ' -f1)"
    while [ "$tries" -lt 20 ]; do
      got="$(docker compose run --rm --no-deps -T storage-cors python -c 'import hashlib; print(hashlib.sha256(open("/opt/storage_cors.py", "rb").read()).hexdigest())' 2>/dev/null | tail -1)"
      [ "$got" = "$want" ] && return 0
      tries=$((tries + 1)); sleep 1
    done
    echo "    ★ 컨테이너가 20초 안에 호스트와 같은 storage_cors.py 를 보지 못했다"
    return 1
  }
  rerun_rule() {
    same_bytes_inside || return 1
    docker compose up -d --force-recreate --no-deps storage-cors > "$T/up.log" 2>&1 || { cat "$T/up.log"; return 1; }
    local id code
    id="$(docker compose ps -a -q storage-cors)"
    code="$(docker wait "$id")"
    local state health
    state="$(docker compose ps -a storage-cors --format '{{.Status}}')"
    health="$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q api-py)")"
    echo "    storage-cors: $state · 로그 $(docker logs "$id" 2>&1 | tail -1) · api-py $health"
    [ "$code" = 0 ] && case "$state" in "Exited (0)"*) true ;; *) false ;; esac && [ "$health" = healthy ]
  }
  # 빨개진 시험 이름들. pytest 가 0 이 아닌데 FAILED 가 없으면(고정물 ERROR 등) ERROR 를 돌려준다.
  integration() {
    local id="$1" out="$T/$1.log" code red
    (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -c tests_integration/pytest.ini "$INTEGRATION") > "$out" 2>&1
    code=$?
    red="$(sed -n 's/^FAILED \([^ ]*\).*/\1/p' "$out" | sed 's/.*:://' | sort -u | tr '\n' ' ')"
    [ "$code" != 0 ] && [ -z "$red" ] && red="ERROR"
    echo "$red"
  }
  container_break() {   # container_break <번호> <심은 것> <기대 표적> <옛 글자> <새 글자>
    if replace docker/storage_cors.py "$4" "$5" && rerun_rule; then
      record "$1" "$2" "$(integration "$1")" "$3"
    else
      PLANTED=$((PLANTED + 1)); ROWS+=("$1 | $2 | (심은 상태로 못 띄움) | 놓침"); echo "  $1 심은 상태로 못 띄움"
    fi
    restore docker/storage_cors.py
    rerun_rule || echo "  ★ 되쓴 뒤 storage-cors 가 0 으로 끝나지 않았다"
  }

  container_break P1 "rule_for 의 AllowedOrigins 를 http://x.invalid 하나로" test_the_web_origins_get_a_preflight_and_a_signed_put \
    '"AllowedOrigins": list(origins),' '"AllowedOrigins": ["http://x.invalid"],'
  container_break P2 "rule_for 의 AllowedOrigins 끝에 *" test_another_origin_gets_no_cors_headers \
    '"AllowedOrigins": list(origins),' '"AllowedOrigins": [*origins, "*"],'
  container_break P10 "main 이 put 대신 delete_bucket_cors, 되읽기 없이 0" test_the_web_origins_get_a_preflight_and_a_signed_put \
    '    rule = rule_for(origins)
' '    client.delete_bucket_cors(Bucket=bucket)
    print("storage-cors: (심은 파손 P10) 규칙을 지웠다")
    return 0
    rule = rule_for(origins)
'
  echo "▶ 되쓴 규칙으로 통합 둘이 다시 초록인가"
  after="$(integration after)"
  [ -z "$after" ] && echo "  초록" || echo "  ★ 빨강: $after"
fi

echo
echo "| # | 심은 것 | 빨개진 시험 | 판정 |"
echo "|---|---|---|---|"
for row in "${ROWS[@]}"; do echo "| $row |"; done
AFTER="$(fingerprint)"
[ "$BEFORE" = "$AFTER" ] && FP=same || FP=changed
echo "PLANTED=$CAUGHT/$PLANTED"
echo "FINGERPRINT=$FP"
[ "$CAUGHT" = "$PLANTED" ] && [ "$FP" = same ] && [ "${after:-}" = "" ]
