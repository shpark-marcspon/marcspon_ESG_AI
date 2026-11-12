#!/usr/bin/env bash
# 밴드 CR1(MARC-TICK-200: 개발 compose 저장소 CORS — 웹 출처만 브라우저 서명 PUT)의 §4 자기검증. 발주서 §4.
#   사용: apps/api-py/scripts/section4-CR1.sh                    경계 + 빠른 층 + verify.sh --fast
#         apps/api-py/scripts/section4-CR1.sh --with-containers  + 컨테이너 층(통합 표적·브라우저 탐침·심은 파손 10)
# 단계마다 EXIT=<n> <초>, 끝 줄 SECTION4_FAIL=<n>(0 이 아니면 스크립트가 1 로 끝난다). 출력은 S4_OUT(기본
# 워크트리 옆 CR1.out/). 전량 scripts/verify.sh 는 돌리지 않는다(감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# ★ compose config --format json 출력에는 비밀이 있다: STORAGE_CORS_ORIGINS 값만 곧바로 꺼내고 나머지는 찍지도
#   파일로 두지도 않는다. 키 값은 출력에 0.
# ★ 컨테이너 층의 문(MARC-ENT-241·292): 자기 밖 esg-app* 프로젝트 둘 이하(셋 미만) · free ≥ 20% · 1분 부하 < 24.
#   build 는 scripts/with-build-lock.sh 로만. 60초 간격, 최대 30분 — 넘기면 컨테이너 층을 건너뛰고 실패로 센다.
# ★ 브라우저 탐침은 apps/web 의 @playwright/test 1.63.0 과 이미 받아 둔 chromium 을 쓴다(설치하지 않는다).
#   페이지는 127.0.0.1 에만 묶은 한 번짜리 정적 서버(파일 하나)가 허락 출처의 포트(WEB_PORT)와 목록 밖 15999 에서
#   내주고, 탐침이 끝나면 pid 로 바로 닫는다(감독 74 허락 2026-10-20 — page.route 로 지은 페이지는 크롬의 LNA 가
#   loopback 으로 가는 fetch 를 CORS 판정 전에 막았다, 1차 실측). 탐침 스크립트·페이지는 S4_OUT 에 쓴다(저장소 밖).
# AI 공급사 호출 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
B=732acf7   # BASE(발주서 머리)
A=apps/api-py
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C
WITH_CONTAINERS=0
case "${1:-}" in
  "") ;;
  --with-containers) WITH_CONTAINERS=1 ;;
  *) echo "사용: $0 [--with-containers]" >&2; exit 2 ;;
esac
S4_OUT="${S4_OUT:-$(cd "$ROOT/.." && pwd)/CR1.out}"
mkdir -p "$S4_OUT"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }

FAILS=0
run() {   # run <이름> <명령…>: EXIT=<n> <초>
  local name="$1"; shift
  echo
  echo "▶ $name"
  local start=$SECONDS
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code $((SECONDS - start))s"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}

# compose config 의 storage-cors 출처(값만). 비밀은 파이프 안에서 버린다.
origins_of() { (cd "$ROOT" && eval "$1 docker compose config --format json") | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["storage-cors"]["environment"]["STORAGE_CORS_ORIGINS"])'; }

# ── 1. 경계 ───────────────────────────────────────────────────────────
boundary() {
  local outside
  outside="$(git status --porcelain | grep -v -E '^.. (compose\.yaml|docker/storage_cors\.py|\.env\.example|scripts/(worktree-env|verify)\.sh|README\.md|apps/api-py/scripts/(check-worktree-env|section4-CR1|planted-breaks-CR1)\.sh|apps/api-py/esgapi/config/tests/test_compose_storage_cors\.py|apps/api-py/tests_integration/test_storage_cors\.py)$')"
  [ -z "$outside" ] || { echo "  ★ 허용 밖: $outside"; return 1; }
  git diff --numstat "$B" -- compose.yaml .env.example scripts/worktree-env.sh scripts/verify.sh README.md "$A/scripts/check-worktree-env.sh" | sed 's/^/  numstat /'
  local f
  for f in compose.yaml .env.example "$A/scripts/check-worktree-env.sh"; do
    [ "$(git diff --numstat "$B" -- "$f" | cut -f2)" = 0 ] || { echo "  ★ $f 에서 지운 줄이 있다"; return 1; }
  done
  [ "$(git diff --numstat "$B" -- scripts/worktree-env.sh | cut -f2)" -le 4 ] || { echo "  ★ worktree-env.sh 지운 줄 > 4"; return 1; }
  test "$(git diff --numstat "$B" -- scripts/verify.sh)" = "1	1	scripts/verify.sh" || { echo "  ★ verify.sh 가 −1 +1 이 아니다"; return 1; }
  git diff --quiet "$B" -- apps/api-py/esgapi ':!apps/api-py/esgapi/config/tests/test_compose_storage_cors.py' infra apps/web \
    docker/api-py.Dockerfile docker/parser.Dockerfile docker/elasticmq.conf docker/postgres-init.sh scripts/check-gates.sh \
    apps/api-py/tests_integration/conftest.py apps/api-py/tests_integration/pytest.ini apps/api-py/pyproject.toml apps/api-py/uv.lock \
    || { echo "  ★ 0줄 자리가 바뀌었다"; return 1; }
  echo "  경계 안"
}
run "1. 경계(허용 경로·numstat·0줄 자리, BASE $B)" boundary

# ── 2. 빠른 층 ────────────────────────────────────────────────────────
NEW_PY="esgapi/config/tests/test_compose_storage_cors.py tests_integration/test_storage_cors.py"
run "2a. 빠른 시험(새 파일 + test_env + test_worker_pool)" \
  "cd $A && uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_compose_storage_cors.py esgapi/config/tests/test_env.py esgapi/runs/tests/test_worker_pool.py"
run "2b. ruff check·format(새 시험 둘은 api-py 설정, docker/storage_cors.py 는 --config pyproject.toml = apps/api-py/pyproject.toml)" \
  "cd $A && uv run --frozen ruff check $NEW_PY && uv run --frozen ruff format --check $NEW_PY && uv run --frozen ruff check --config pyproject.toml ../../docker/storage_cors.py && uv run --frozen ruff format --check --config pyproject.toml ../../docker/storage_cors.py"
run "2c. pyright(새 시험 둘)" "cd $A && uv run --frozen pyright $NEW_PY"
run "2d. 시험 자리 규칙" "cd $A && uv run --frozen python scripts/check_test_layout.py"
run "2e. check-worktree-env.sh(WEB_PORT = 칸+4)" "$A/scripts/check-worktree-env.sh"
run "2f. compose config -q" "docker compose config -q"
compose_port_substitution() {
  local got
  got="$(origins_of 'WEB_PORT=20004')" || return 1
  echo "  WEB_PORT=20004 → $(echo "$got" | tr ',' '\n' | grep -c ':20004$') 개가 :20004 (출처 $(echo "$got" | tr ',' '\n' | wc -l | tr -d ' ') 개)"
  [ "$(echo "$got" | tr ',' '\n' | grep -c ':20004$')" = 2 ]
}
run "2g. WEB_PORT=20004 의 storage-cors 출처에 :20004 둘" compose_port_substitution
run "2h. bash -n 새 스크립트 둘" "bash -n $A/scripts/section4-CR1.sh && bash -n $A/scripts/planted-breaks-CR1.sh"
gates() {
  scripts/check-gates.sh > "$S4_OUT/check-gates.log" 2>&1
  local code=$?
  grep -A20 '▶ compose.yaml: 프로필 ts' "$S4_OUT/check-gates.log" | grep -m1 '^EXIT=' | sed 's/^/  ts 검사 /'
  tail -1 "$S4_OUT/check-gates.log" | sed 's/^/  /'
  return $code
}
run "2i. scripts/check-gates.sh 전체(로그 $S4_OUT/check-gates.log)" gates
run "2j. 심은 파손 빠른 일곱" "$A/scripts/planted-breaks-CR1.sh"

# ── 3. 컨테이너 층 ────────────────────────────────────────────────────
gate() {
  local tries=0 free load others me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d ' ')"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" -le 2 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 자기 밖 esg-app* 프로젝트 $others · free ${free:-?}% · 1분 부하 ${load:-?} · 기다림 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: 자기 밖 $others · free ${free:-?}% · 부하 ${load:-?} · 30분)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

# 컨테이너 안에서 제품 코드로 서명 주소를 만들거나(presign <n> <키…>) 객체를 본다(head <키>). 마지막 줄 JSON.
INSIDE='
import json, sys
import django
django.setup()
from esgapi.core.service.services import documents as services
storage = services.default_storage()
if sys.argv[1] == "presign":
    size = int(sys.argv[2])
    print(json.dumps([storage.presign_upload(k, content_length=size).url for k in sys.argv[3:]]))
else:
    head = storage.head(sys.argv[2])
    print(json.dumps({"type": type(head).__name__, "size": getattr(head, "size_bytes", None)}))
'
inside() { docker compose exec -T api-py python -c "$INSIDE" "$@" | tail -1; }

probe() {
  local first size=4096 key other_key urls allowed_url other_url
  local web_port first other="http://127.0.0.1:15999"
  web_port="$(env_value WEB_PORT)"; web_port="${web_port:-15173}"
  # 허락 출처 = compose 가 치환한 목록 중 127.0.0.1:WEB_PORT(서버를 127.0.0.1 에만 묶으므로).
  first="$(origins_of '' | tr ',' '\n' | grep -x "http://127.0.0.1:$web_port")" || { echo "  ★ 목록에 http://127.0.0.1:$web_port 가 없다"; return 1; }
  origins_of '' | tr ',' '\n' | grep -qx "$other" && { echo "  ★ $other 가 허락 목록에 있다"; return 1; }
  key="it-cors-probe/$(uuidgen | tr 'A-Z' 'a-z').bin"
  other_key="it-cors-probe/$(uuidgen | tr 'A-Z' 'a-z').bin"
  urls="$(inside presign "$size" "$key" "$other_key")" || return 1
  allowed_url="$(echo "$urls" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0])')"
  other_url="$(echo "$urls" | python3 -c 'import json,sys; print(json.load(sys.stdin)[1])')"
  echo "  허락 출처 $first · 목록 밖 $other · 크기 $size"
  echo "  같은 출처 curl preflight(목록 밖): $(curl -s -o /dev/null -D - -X OPTIONS -H "Origin: $other" -H 'Access-Control-Request-Method: PUT' "$other_url" | tr -d '\r' | awk 'NR==1{s=$2} tolower($1)=="access-control-allow-origin:"{a=$2} END{print "status " s " ACAO " (a==""?"없음":a)}')"
  echo "  같은 출처 curl preflight(허락): $(curl -s -o /dev/null -D - -X OPTIONS -H "Origin: $first" -H 'Access-Control-Request-Method: PUT' -H 'Access-Control-Request-Headers: content-type' "$allowed_url" | tr -d '\r' | awk 'NR==1{s=$2} tolower($1)=="access-control-allow-origin:"{a=$2} END{print "status " s " ACAO " (a==""?"없음":a)}')"
  cat > "$S4_OUT/browser-probe.mjs" <<'JS'
// CR1 브라우저 탐침(section4-CR1.sh 가 씀). 인자: <apps/web/package.json> <허락 출처> <허락 주소> <목록 밖 출처> <목록 밖 주소> <크기>
// 페이지는 section4 가 127.0.0.1 에 잠깐 띄운 정적 서버가 내준다(가로채지 않는다).
import { createRequire } from "node:module";
const [pkg, allowed, allowedUrl, OTHER, otherUrl, sizeText] = process.argv.slice(2);
const size = Number(sizeText);
const { chromium } = createRequire(pkg)("@playwright/test");
const browser = await chromium.launch();
const out = {};
async function attempt(origin, url) {
  const page = await browser.newPage();
  const logs = [];
  // 서명 주소의 질의 문자열(자격 증명 이름·서명)은 찍지 않는다.
  page.on("console", (m) => logs.push(m.text().replace(/\?X-Amz-[^'"\s]*/g, "?<서명 가림>")));
  const response = await page.goto(`${origin}/`);
  const seenOrigin = await page.evaluate(() => location.origin);
  const result = await page.evaluate(
    async ([u, n]) => {
      try {
        const r = await fetch(u, { method: "PUT", body: new Blob([new Uint8Array(n)]), headers: { "content-type": "application/pdf" } });
        return { status: r.status, etag: r.headers.get("etag") };
      } catch (e) {
        return { error: `${e.name}: ${e.message}` };
      }
    },
    [url, size],
  );
  await page.close();
  return { goto: response?.status(), origin: seenOrigin, ...result, console: logs };
}
out.allowed = await attempt(allowed, allowedUrl);
out.other = await attempt(OTHER, otherUrl);
await browser.close();
console.log(JSON.stringify(out));
JS
  local pkg="$ROOT/apps/web/package.json" result code page_dir pids="" port
  [ -f "$ROOT/apps/web/node_modules/@playwright/test/package.json" ] || { echo "  ★ apps/web 의 @playwright/test 가 없다(pnpm install 먼저 — verify.sh --fast 가 한다)"; return 1; }
  # 한 번짜리 정적 서버 둘: 127.0.0.1 에만, 파일 하나(index.html)만 있는 폴더를 내준다.
  page_dir="$S4_OUT/probe-page"
  rm -rf "$page_dir"; mkdir -p "$page_dir"
  printf '<!doctype html><title>cr1</title>\n' > "$page_dir/index.html"
  for port in "$web_port" 15999; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "  ★ 포트 $port 를 이미 누가 듣고 있다"; kill $pids 2>/dev/null; return 1; fi
    python3 -m http.server "$port" --bind 127.0.0.1 --directory "$page_dir" > "$S4_OUT/probe-server-$port.log" 2>&1 &
    pids="$pids $!"
  done
  for port in "$web_port" 15999; do
    for _ in $(seq 50); do curl -s -o /dev/null "http://127.0.0.1:$port/" && break; sleep 0.1; done
  done
  echo "  정적 서버: 127.0.0.1:$web_port · 127.0.0.1:15999 (pid$pids)"
  result="$(node "$S4_OUT/browser-probe.mjs" "$pkg" "$first" "$allowed_url" "$other" "$other_url" "$size" 2> "$S4_OUT/browser-probe.err")"
  code=$?
  kill $pids 2>/dev/null; wait $pids 2>/dev/null
  echo "  정적 서버 닫음: lsof $web_port·15999 LISTEN $( (lsof -nP -iTCP:"$web_port" -sTCP:LISTEN; lsof -nP -iTCP:15999 -sTCP:LISTEN) 2>/dev/null | grep -vc '^COMMAND') 줄"
  [ "$code" = 0 ] || { echo "  ★ 탐침이 실패했다:"; sed 's/^/    /' "$S4_OUT/browser-probe.err" | head -20; return 1; }
  echo "$result" > "$S4_OUT/browser-probe.json"
  echo "  탐침: $result"
  local head
  head="$(inside head "$key")" || return 1
  echo "  head(허락 출처의 키): $head"
  python3 - "$result" "$head" "$first" "$size" "$other" <<'PY'
import json, sys
r, head, first, size, other_origin = json.loads(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
a, o = r["allowed"], r["other"]
assert a["goto"] == 200 and a["origin"] == first, a
assert o["goto"] == 200 and o["origin"] == other_origin, o  # 목록 밖 페이지가 정말 그 출처에서 떴다
allowed = f"allowed:{a.get('status', 'blocked')}"
print(f"  허락 출처 PUT 의 ETag(Expose 로 읽힘): {a.get('etag') or '없음'}")
other = "other:blocked" if o.get("error", "").startswith("TypeError") else f"other:{o.get('status')}"
head_ok = head["type"] == "ObjectFound" and head["size"] == size
print(f"BROWSER_PUT={allowed} {other} head:{head['type'] if head_ok else 'mismatch'}")
if a.get("error"):
    print("  허락 출처 fetch 오류:", a["error"], a["console"])
    if any("loopback" in line and "address space" in line for line in a["console"]):
        print("LNA_SUSPECT=1 (크롬이 loopback 주소 공간 접근을 막음 — 같은 출처 curl preflight 줄과 맞춰 본다, 발주서 §5)")
sys.exit(0 if (a.get("status") == 200 and a.get("etag") and other == "other:blocked" and head_ok) else 1)
PY
}

# run 은 서브셸에서 돈다: 아래 단계들은 run 하나로 감싸지 않고 맨 위에서 하나씩 부른다(FAILS 를 잃지 않게).
containers() {
  run "3a. build(빌드 잠금)" "scripts/with-build-lock.sh docker compose build > '$S4_OUT/build.log' 2>&1"
  run "3b. up -d --wait" "docker compose up -d --wait"
  storage_cors_ran() {
    local id state
    id="$(docker compose ps -a -q storage-cors)"
    state="$(docker compose ps -a storage-cors --format '{{.Status}}')"
    echo "  storage-cors: $state · 로그 $(docker logs "$id" 2>&1 | tail -1)"
    python3 - "$(docker inspect -f '{{.State.StartedAt}} {{.State.FinishedAt}}' "$id")" <<'PY'
import sys
from datetime import datetime
a, b = sys.argv[1].split()
p = lambda s: datetime.fromisoformat(s[:26].rstrip("Z") if "." in s else s.rstrip("Z"))
print(f"  storage-cors 걸린 시간 {(p(b) - p(a)).total_seconds():.2f}s")
PY
    case "$state" in "Exited (0)"*) ;; *) return 1 ;; esac
    docker logs "$id" 2>&1 | tail -1 | grep -q 'origins=4 methods=PUT,GET,HEAD$'
  }
  run "3c. storage-cors Exited (0)·origins=4" storage_cors_ran
  run "3d. 통합 표적(test_storage_cors + test_upload_flow, --durations=0)" \
    "cd $A && uv run --frozen pytest -q -p no:cacheprovider -c tests_integration/pytest.ini --durations=0 tests_integration/test_storage_cors.py tests_integration/test_upload_flow.py"
  run "3e. 브라우저 탐침" probe
  run "3f. 심은 파손 10(--with-containers)" "$A/scripts/planted-breaks-CR1.sh --with-containers"
  leftovers() {
    docker compose down -v > /dev/null 2>&1
    local me c v
    me="$(env_value COMPOSE_PROJECT_NAME)"
    c="$(docker ps -a --filter "label=com.docker.compose.project=$me" -q | wc -l | tr -d ' ')"
    v="$(docker volume ls --filter "label=com.docker.compose.project=$me" -q | wc -l | tr -d ' ')"
    echo "  남은 컨테이너 $c · 볼륨 $v"
    [ "$c" = 0 ] && [ "$v" = 0 ]
  }
  run "3g. down -v·남은 것 0" leftovers
}
if [ "$WITH_CONTAINERS" = 1 ]; then
  echo
  echo "▶ 3. 컨테이너 층의 문"
  if gate; then
    docker compose down -v > /dev/null 2>&1   # 깨끗한 상태에서 시작한다
    # 통합 시험이 EDK 인 척 서명할 키 쌍의 공개키만 컨테이너에 준다(선례 scripts/verify.sh 의 전량).
    EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
    export EDK_JWT_PUBLIC_KEY
    containers
  else
    echo "EXIT=1 (문이 안 열려 컨테이너 층을 건너뜀)"
    FAILS=$((FAILS + 1))
  fi
fi

# ── 4. verify.sh --fast ───────────────────────────────────────────────
fast_gate() {
  scripts/verify.sh --fast > "$S4_OUT/verify-fast.log" 2>&1
  local code=$?
  tail -1 "$S4_OUT/verify-fast.log" | sed 's/^/  /'
  return $code
}
run "4. scripts/verify.sh --fast(로그 $S4_OUT/verify-fast.log)" fast_gate

echo
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
