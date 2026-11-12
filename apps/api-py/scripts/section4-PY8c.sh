#!/usr/bin/env bash
# 밴드 PY8c(MARC-TICK-60, 마무리의 남은 코드 넷: ① planted-breaks.sh 고침 ② 엔진 재통과 ③ pdfium 골든 ④ 파서 통합)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-PY8c.sh                  전체. 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-PY8c.sh --pure [--reuse]  컨테이너 없이 도는 것만(반복해 돌려도 된다)
#         apps/api-py/scripts/section4-PY8c.sh --containers      통합 층 한 번(띄우기 → 통합 7 → 심은 파손 5 → 내리기 → 이미지 치우기)
#         apps/api-py/scripts/section4-PY8c.sh --build-fixture   ④ 의 고정물 PDF 를 cells.json 에서 다시 짓는다(커밋하는 파일을 쓴다)
#   --reuse: .lab-golden/pdfium 에 분해 산출이 있으면 네 보고서의 분해를 건너뛴다(입력의 sha256 은 check_lab 이 digest 와 견준다).
#            마지막 한 번은 --reuse 없이 돌린다.
# 전량 scripts/verify.sh 는 돌리지 않는다(이 밴드는 게이트를 고치지 않는다. 전량은 감독이 병합 뒤 main 에서).
# 환경 변수: ESG_LAB(esg-lab 의 자리), REPORTS(공개 보고서 PDF 의 폴더). 둘 다 읽고 실행만 한다(파일 변경 0).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다. AI 공급사 호출 0.
# bash 전용이다(${PIPESTATUS[0]}, 프로세스 치환). 임시 파일은 지우지 않는다(mktemp 의 것이라 운영체제가 치운다).
set -u
cd "$(dirname "$0")/../../.."
B=b22c31e   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 와 esg-lab 의 tsx 가 Node 22 를 쓴다
MODE="${1:-all}"
REUSE=0
case "$MODE" in all | --pure | --containers | --build-fixture) ;; *) echo "사용: $0 [--pure [--reuse]|--containers|--build-fixture]" >&2; exit 2 ;; esac
[ "${2:-}" = "--reuse" ] && REUSE=1

export ESG_LAB="${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
REPORTS="${REPORTS:?REPORTS=<공개 보고서 PDF 폴더의 경로> 를 준다}"
T="$(mktemp -d)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
test -n "$PROJECT" || { echo ".env 에 COMPOSE_PROJECT_NAME 이 없다" >&2; exit 2; }
OUT="$PWD/apps/api-py/.lab-golden/pdfium"
GOLDEN=apps/api-py/esgapi/reconcile/tests/golden
FIXTURE="$PWD/apps/api-py/tests_integration/data/ruled-table"
DOCS="kb_2025_kor kb_2025_databook_kor samsung_2026_kor cosmax_2025_kor"

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다: 메모리 free 20% 이상, 1분 부하 12 미만. 30초마다, 최대 10분(그 뒤엔 그냥 돈다).
gate() {
  local tries=0 free load
  while [ "$tries" -lt 20 ]; do
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then break; fi
    tries=$((tries + 1)); sleep 30
  done
  echo "  (문: free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 30초)"
}

# ④ 의 고정물: cells.json(표의 칸과 열의 x 좌표) → PDF 한 쪽. 두 경로 다 절대 경로로 준다(--directory 가 cwd 를 바꾼다).
# services/parser/tests/conftest.py 의 synthetic_ruled_page 와 같은 꼴이다: 세로선 없이 칸마다 가로 토막, 맨 위는 굵은 줄.
# 결정적이다(pdfbuild 의 /ID 가 내용의 md5 다. 시각·난수가 없다): 같은 cells.json 이면 같은 바이트가 나온다.
build_fixture() { # <cells.json> <out.pdf>
  uv run --directory services/parser --frozen python - "$1" "$2" <<'PY'
import json
import sys

from tests import pdfbuild
from tests.conftest import hline, put

spec = json.load(open(sys.argv[1], encoding="utf-8"))
xs, rows = spec["columnEdges"], spec["rows"]
numeric = set(spec["numericColumns"])
merged = {tuple(pair) for pair in spec["mergedDown"]}
doc = pdfbuild.Doc()
page = doc.new_page(width=spec["page"]["width"], height=spec["page"]["height"])
y = spec["top"]
for i, row in enumerate(rows):
    base = y + spec["baselineOffset"]
    for j, text in enumerate(row):
        if not text:
            continue
        if j in numeric:
            put(page, xs[j + 1] - 2, base, text, right=True)  # 숫자 열은 오른쪽 맞춤
        else:
            put(page, xs[j] + 2, base, text)
    y += spec["rowHeight"]
    for j in range(len(row)):
        if (i, j) not in merged:  # 아래 행과 세로로 합쳐진 칸은 밑줄 토막을 그리지 않는다
            hline(page, xs[j], xs[j + 1], y)
for j in range(len(rows[0])):
    hline(page, xs[j], xs[j + 1], spec["top"], width=1.0)
doc.save(sys.argv[2])
PY
}

if [ "$MODE" = "--build-fixture" ]; then
  build_fixture "$FIXTURE.cells.json" "$FIXTURE.pdf" || exit 1
  echo "지었다: apps/api-py/tests_integration/data/ruled-table.pdf  $(wc -c < "$FIXTURE.pdf" | tr -d ' ') B  sha256 $(shasum -a 256 < "$FIXTURE.pdf" | cut -d' ' -f1)"
  exit 0
fi

have_parsed() { local d; for d in $DOCS; do [ -f "$OUT/$d/document.json" ] && [ -f "$OUT/$d/char-places.json" ] || return 1; done; }
parse_reports() {
  local d started
  if [ "$REUSE" -eq 1 ] && have_parsed; then
    echo "  (--reuse: $OUT 의 분해 산출을 그대로 쓴다. 분해하지 않았다)"
    return 0
  fi
  for d in $DOCS; do
    started=$SECONDS
    uv run --directory services/parser --frozen python -m docparse parse "$REPORTS/$d.pdf" --places --out "$OUT/$d" > /dev/null || return 1
    echo "  분해 $d  $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/')"
  done
}

echo "── 부하와 포트 (.env)"
uptime
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env

pure_part() {
  run 'git -C "$ESG_LAB" rev-parse --short HEAD ; git -C "$ESG_LAB" status --porcelain > "$T/lab-before.txt" ; wc -l < "$T/lab-before.txt"'
  local started=$SECONDS
  run 'scripts/verify.sh --fast'                                           # 끝 줄 VERIFY_FAST=PASS
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"

  echo; echo "── ① planted-breaks.sh 를 돌려도 작업 트리가 그대로인가"
  git status --porcelain > "$T/before.txt"; shasum -a 256 apps/api-py/esgapi/inventory/services.py > "$T/svc.txt"
  run 'apps/api-py/scripts/planted-breaks.sh'                              # PLANTED=10/10
  run 'git status --porcelain | diff - "$T/before.txt" && shasum -a 256 -c "$T/svc.txt"'   # 스크립트 밖에서 따로 잰다
  run 'test "$(git diff --numstat "$B" -- README.md | cut -f1)" = 0 && test "$(git diff --numstat "$B" -- README.md | cut -f2)" -le 2 && ! grep -q "지운 채 끝난다" README.md'
  run '(cd apps/api-py && uv run --frozen python scripts/readme_audit.py paths --rev HEAD | tail -1 && uv run --frozen python scripts/readme_audit.py forward --rev HEAD | tail -1)'

  echo; echo "── ② 엔진 재통과"
  run '(cd apps/api-py && uv run --frozen pytest -q -m "not django_db and not security" esgapi/inventory/tests/test_assembly_replay.py)'
  run '(cd "$ESG_LAB/ts" && pnpm -s -F factor-assembly exec tsx src/cli.ts verify-handcalc --json) > "$T/ts-replay.json"'
  run '(cd apps/api-py && uv run --frozen python -m esgapi.inventory.tests.assembly_replay --json) > "$T/py-replay.json"'
  F='[.rows[] | {caseId, expectedCo2e, actualCo2e, status: .outcome.status, factor: .outcome.assembledFactorId}]'
  # 줄 10, 다섯 칸 일치. 덤으로 JSON 전체도 견준다(전체가 달라도 EXIT 는 다섯 칸의 것이다).
  run 'test "$(jq "$F | length" "$T/ts-replay.json")" = 10 && diff <(jq -S "$F" "$T/ts-replay.json") <(jq -S "$F" "$T/py-replay.json") && jq -c .summary "$T/ts-replay.json" "$T/py-replay.json" && { diff <(jq -S . "$T/ts-replay.json") <(jq -S . "$T/py-replay.json") > /dev/null && echo "  (JSON 전체도 같다)" || echo "  (다섯 칸 밖에서 다른 데가 있다)"; }'
  run 'test "$(shasum -a 256 apps/api-py/esgapi/inventory/tests/data/handcalc-assembly.json | cut -d" " -f1)" = "$(shasum -a 256 "$ESG_LAB/data/ghg-calc/handcalc-assembly.json" | cut -d" " -f1)"'
  run 'test -z "$(git diff --diff-filter=MDR --name-only "$B" -- apps/api-py/esgapi/inventory/tests | grep -v "data/README.md$")"'   # 기존 테스트 파일은 고치지 않았다

  echo; echo "── ③ pdfium 골든"
  run 'parse_reports'
  run '"$GOLDEN/make-golden.sh" --input apps/api-py/.lab-golden/pdfium --out apps/api-py/.lab-golden/ts-pdfium | tail -2'
  run '(cd apps/api-py && uv run --frozen python -m esgapi.reconcile.tests.golden.check_lab --input .lab-golden/pdfium --ts .lab-golden/ts-pdfium --digest esgapi/reconcile/tests/golden/lab-digest.pdfium.json) | tee "$T/check-pdfium.txt"; test "${PIPESTATUS[0]}" = 0 && grep -q "합: 값 후보 8755" "$T/check-pdfium.txt" && test "$(grep -c "TS 와 같은 구획 8/8" "$T/check-pdfium.txt")" = 4'   # 32/32, 합 8755
  run '"$GOLDEN/make-golden.sh" | tail -1 && (cd apps/api-py && uv run --frozen python -m esgapi.reconcile.tests.golden.check_lab) | tail -3'   # 옛 digest(C1, 8,773)도 그대로
  run 'git diff --quiet "$B" -- "$GOLDEN/lab-digest.json" "$GOLDEN/lab-digest.places.json"'
  # 골든 도구를 고쳤으면 여기 보인다(check_lab.py 의 주석 두 줄은 감독 판정으로 고쳤다. 그 밖은 0 이어야 한다).
  run 'git diff --stat "$B" -- "$GOLDEN/check_lab.py" "$GOLDEN/make-golden.sh" "$GOLDEN/dump.py" "$GOLDEN/dump_places.py" "$GOLDEN/dump.mts"; test "$(git diff --numstat "$B" -- "$GOLDEN/check_lab.py" | cut -f1,2 | tr "\t" " ")" = "2 2" && git diff --quiet "$B" -- "$GOLDEN/make-golden.sh" "$GOLDEN/dump.py" "$GOLDEN/dump_places.py" "$GOLDEN/dump.mts"'

  echo; echo "── ④ 의 고정물"
  run 'build_fixture "$FIXTURE.cells.json" "$T/again.pdf" && test "$(shasum -a 256 < "$T/again.pdf")" = "$(shasum -a 256 < "$FIXTURE.pdf")" && shasum -a 256 < "$FIXTURE.pdf"'   # 다시 지어 sha256 일치
  run 'git diff --quiet "$B" -- apps/api-py/tests_integration/test_flow.py apps/api-py/tests_integration/pytest.ini apps/api-py/tests_integration/conftest.py'   # 0줄
  run '! grep -rn "pdfbuild" apps/api-py/tests_integration --include="*.py"'   # 통합 테스트의 .py 는 pdfbuild 를 import 하지 않는다
  run 'n="$(cd apps/api-py && uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration --collect-only | grep -c "::test_")"; echo "  통합 테스트 $n 건이 모인다(돌리지는 않는다)"; test "$n" = 7'

  echo; echo "── 공통"
  run 'git -C "$ESG_LAB" status --porcelain | diff - "$T/lab-before.txt"'                 # esg-lab 변경 0
  run 'apps/api-py/scripts/check-wheel.sh'                                                # wheel 에 tests 없음
  run 'apps/api-py/scripts/planted-breaks-PY8c.sh --pure'                                 # 심은 파손 1~4
}

containers_part() {
  echo; echo "── 컨테이너 (통합 층만. 전량 verify.sh 가 아니다)"
  run 'test ! -e "$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"'   # 감독의 전량이 도는 중이 아니다
  local port
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다. 띄우지 않는다"; echo "EXIT=1"; return 1; fi
  done
  echo "  (포트 넷이 비어 있다)"
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  gate
  local started=$SECONDS
  run 'docker compose up -d --build --wait 2>&1 | tail -5; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  started=$SECONDS
  echo; echo "▶ apps/api-py/scripts/test-integration.sh"                                   # 7 passed
  apps/api-py/scripts/test-integration.sh; local code=$?
  echo "EXIT=$code"
  if [ "$code" -ne 0 ]; then
    # 빨가면 내리기 전에 기록을 남기고 통합 층만 한 번 더(이미지를 다시 짓지 않는다).
    uptime; docker compose logs --no-color --tail 60 api-py parser
    echo; echo "▶ apps/api-py/scripts/test-integration.sh (한 번 더)"
    apps/api-py/scripts/test-integration.sh; echo "EXIT=$?"
  fi
  echo "  (통합 층에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'apps/api-py/scripts/planted-breaks-PY8c.sh --containers'                           # 심은 파손 5 (못 재면 그 사실)
  run 'docker compose down -v 2>&1 | tail -3; test "${PIPESTATUS[0]}" = 0'
  run 'test -z "$(docker ps -a --format "{{.Names}}" | grep "^$PROJECT-")"'              # 자기 컨테이너 0
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3; test -z "$(docker images --format "{{.Repository}}" | grep "^$PROJECT/")"'
}

boundary_part() {
  # 허용 경로 밖 0 (기준 $B 와 견준다. 커밋 전에도 뒤에도 같은 답을 낸다: 작업 트리 + 새 파일)
  run 'test -z "$({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E "^(README\.md$|apps/api-py/scripts/(planted-breaks|section4-PY8c|planted-breaks-PY8c)\.sh$|apps/api-py/esgapi/inventory/tests/|apps/api-py/esgapi/reconcile/tests/golden/|apps/api-py/tests_integration/|apps/api-py/\.gitignore$)")"'
  echo
  echo "── 바뀐 파일 (기준 $B 대비, 새 파일 포함)"
  { git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u
}

case "$MODE" in
  --pure) pure_part; boundary_part ;;
  --containers) containers_part; boundary_part ;;
  all) pure_part; containers_part; boundary_part ;;
esac
