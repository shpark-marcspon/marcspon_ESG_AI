#!/usr/bin/env bash
# 밴드 DJ52(MARC-TICK-64: Django 를 6.1.2 에서 5.2.18 로 내린다. 그러려고 올림 확인의 커밋 뒤 갈고리에서 partial 을 뺀다)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-DJ52.sh                전체(--pure 뒤에 --containers). 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-DJ52.sh --pure         컨테이너 없이 도는 것만(반복해 돌려도 된다)
#         apps/api-py/scripts/section4-DJ52.sh --containers   컨테이너 층 한 번(api-py 이미지 짓기 → 이미지 안의 Django 단언 → 띄우기 → 업무 → 보안 → 통합 → 심은 파손 ③ → 내리기 → 이미지 치우기)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. AWS 로 나가는 호출 0: 브로커는 compose 의 queue(SQS 흉내, sqs://queue:9324)뿐이다.
# 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 심은 파손은 `uv run --no-sync --frozen pytest` 로 돌린다: pyproject 나 잠금을 일부러 어긋나게 한 동안 uv 가
#   잠금을 다시 쓰거나 환경을 다시 맞추지 않게. 설치된 Django 는 그 동안에도 5.2.18 이다((가) 가 초록인 것으로 본다).
# ★ makemigrations --check 와 manage.py check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라
#   「consistent migration history」 RuntimeWarning 한 줄이 난다. 기대다). DB 의 적용 기록까지 보는 것은 업무 층의
#   esgapi/config/tests/test_migrations.py 다.
set -u
cd "$(dirname "$0")/../../.."
B=eedeb85   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

T="$(mktemp -d)"   # 저장소 밖. 기록과 심은 파손의 사본을 둔다(지우지 않는다. 운영체제가 치운다)
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
test -n "$PROJECT" || { echo ".env 에 COMPOSE_PROJECT_NAME 이 없다" >&2; exit 2; }
GUARD=esgapi/config/tests/test_django_series.py
SVC=apps/api-py/esgapi/core/documents/services.py
EACH=esgapi/core/tests/test_documents_services.py::test_each_unfinished_job_is_sent_with_its_own_id
PY=apps/api-py/pyproject.toml
LOCK=apps/api-py/uv.lock

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1-4) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -x \
    -e 'apps/api-py/pyproject.toml' \
    -e 'apps/api-py/uv.lock' \
    -e 'apps/api-py/esgapi/config/settings/base.py' \
    -e 'apps/api-py/esgapi/core/documents/services.py' \
    -e 'apps/api-py/esgapi/core/tests/test_documents_services.py' \
    -e 'apps/api-py/esgapi/config/tests/test_django_series.py' \
    -e 'apps/api-py/scripts/section4-DJ52.sh' \
    -e 'README.md'
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다: 메모리 free 20% 이상, 1분 부하 12 미만. 30초마다, 최대 10분.
# 10분 뒤에도 안 되면 띄우지 않는다(1 을 돌려준다).
gate() {
  local tries=0 free load
  while :; do
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 30초)"
      return 0
    fi
    [ "$tries" -ge 20 ] && { echo "  (문이 안 열렸다: free ${free:-?}% · 1분 부하 ${load:-?} · 10분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 30
  done
}

echo "── 부하와 포트 (.env)"
uptime
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env

pure_part() {
  local started=$SECONDS
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "^(▶|EXIT=)|passed|failed|error" "$T/fast.log" | tail -44; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  echo; echo "── Django 의 판: 설치된 것, 잠금, 지킴이 테스트"
  run '(cd apps/api-py && uv run --frozen python -W error -c "import django; print(django.VERSION); assert django.VERSION[:3] == (5, 2, 18)")'
  run '(cd apps/api-py && uv lock --check 2>&1 | tail -2; exit ${PIPESTATUS[0]})'
  run '(cd apps/api-py && uv run --frozen pytest -q "$GUARD" 2>&1 | tail -2; exit ${PIPESTATUS[0]})'                 # 3 passed
  run 'n="$(cd apps/api-py && uv run --frozen pytest --collect-only -q 2>/dev/null | grep -c "test_django_series")"; echo "  경로 없이 부른 pytest 가 지킴이 테스트에서 모으는 건수: $n (3 이상)"; [ "$n" -ge 3 ]'
  run 'n="$(cd apps/api-py && uv run --frozen pytest --collect-only -q -m "not django_db and not security" 2>/dev/null | grep -c "test_django_series")"; echo "  빠른 게이트의 순수 층(-m)이 모으는 건수: $n (3 이상)"; [ "$n" -ge 3 ]'
  run '(cd apps/api-py && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python -W error manage.py check 2>&1 | tail -2; exit ${PIPESTATUS[0]})'
  run '(cd apps/api-py && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; grep -c "RuntimeWarning" "$T/mm.txt"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  echo; echo "── 판을 바꾼 것은 django 한 줄뿐"
  run 'git diff -U0 "$B" -- "$PY" | grep "^[+-][^+-]"; test "$(git diff -U0 "$B" -- "$PY" | grep -c "^[+-][^+-]")" = 2 && git diff -U0 "$B" -- "$PY" | grep -q "^-    \"django==6\.1\.2\",$" && git diff -U0 "$B" -- "$PY" | grep -q "^+    \"django==5\.2\.18\",$"'
  # 잠금: 꾸러미의 목록이 같고, 판이 바뀐 것은 django 하나, 내용이 바뀐 것은 django 와 esgapi(우리 꾸러미의 requires-dist 표기)뿐.
  run 'git show "$B:$LOCK" > "$T/lock-base.toml" && (cd apps/api-py && uv run --frozen python - "$T/lock-base.toml" uv.lock <<"PY"
import sys, tomllib
old, new = ({p["name"]: p for p in tomllib.load(open(path, "rb"))["package"]} for path in sys.argv[1:3])
assert set(old) == set(new), (sorted(set(old) - set(new)), sorted(set(new) - set(old)))
moved = sorted(n for n in old if old[n].get("version") != new[n].get("version"))
differ = sorted(n for n in old if old[n] != new[n])
print(f"  꾸러미 {len(new)}개 · 판이 바뀐 것 {moved} · 내용이 바뀐 것 {differ}")
print("  django:", old["django"]["version"], "→", new["django"]["version"], "· 의존", [d["name"] for d in new["django"]["dependencies"]])
assert moved == ["django"] and differ == ["django", "esgapi"]
assert old["django"]["dependencies"] == new["django"]["dependencies"]
PY
)'
  run 'git diff --numstat "$B" -- "$LOCK"'
  echo; echo "── 경계: 허용 경로 밖 0, 마이그레이션 0, 설정은 주석 두 줄뿐"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'n="$(changed | grep -c "/migrations/")"; echo "  바뀌거나 새로 생긴 마이그레이션 파일: $n"; [ "$n" = 0 ]'
  run 'n="$(changed | grep "^apps/api-py/esgapi/" | grep -v "/tests/" | grep -v -x -e "$SVC" -e "apps/api-py/esgapi/config/settings/base.py" | wc -l | tr -d " ")"; echo "  services.py·base.py(주석) 말고 바뀐 제품 코드 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --numstat "$B" -- "$SVC"; test "$(grep -c "partial(" "$SVC")" = 0 && grep -q "^from functools import cache$" "$SVC" && test "$(grep -c "robust=True" "$SVC")" = "$(git show "$B:$SVC" | grep -c "robust=True")"'   # partial 을 부르는 곳도 들이는 곳도 없다(글자는 까닭을 적은 문서 줄에만)
  run 'test "$(git diff "$B" -- apps/api-py/esgapi/core/tests/test_documents_services.py | grep -c "^-[^-]")" = 0'   # 있던 테스트에는 더하기만(단언을 깎지 않았다)
  run 'git diff --quiet "$B" -- apps/api-py/generated compose.yaml scripts infra apps/web apps/server packages services docker'
  run 'git diff -U0 "$B" -- apps/api-py/esgapi/config/settings/base.py | grep "^[+-][^+-]"; test "$(git diff -U0 "$B" -- apps/api-py/esgapi/config/settings/base.py | grep "^[+-][^+-]" | grep -v -c "^[+-]#")" = 0 && grep -q "^DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440$" apps/api-py/esgapi/config/settings/base.py'
  # 주석이 가리키는 자리가 설치된 Django 에서 그 글자인가
  run 'sed -n "315p" apps/api-py/.venv/lib/python3.13/site-packages/django/conf/global_settings.py; test "$(sed -n "315p" apps/api-py/.venv/lib/python3.13/site-packages/django/conf/global_settings.py)" = "DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # i.e. 2.5 MB"'
  run 'test "$(grep -c -E "filterwarnings|xfail|mark\.skip|skipif" apps/api-py/"$GUARD")" = 0 && test "$(git diff "$B" -- "$PY" | grep -c -E "^[+-].*(filterwarnings|xfail)")" = 0'   # 경고 예외·건너뛰기를 더하지 않았다

  echo; echo "── 심은 파손 둘 (저장소 밖 사본 $T 로 되돌리고 sha256 을 견준다)"
  local guard_b="$GUARD::test_django_is_pinned_and_locked_to_the_same_5_2_version"
  local guard_a="$GUARD::test_the_installed_django_is_in_the_5_2_series"
  cp "$PY" "$T/pyproject.toml.keep"; cp "$LOCK" "$T/uv.lock.keep"
  local py_sha lock_sha
  py_sha="$(sha "$PY")"; lock_sha="$(sha "$LOCK")"
  git status --porcelain > "$T/before.txt"
  # ① pyproject 의 줄만 django==6.1.2 로 되돌린다 → (나) 가 빨갛다. (가) 는 초록(설치는 그대로).
  sed -i '' 's/^    "django==5\.2\.18",$/    "django==6.1.2",/' "$PY"
  run 'test "$(grep -c "^    \"django==6\.1\.2\",$" "$PY")" = 1 && ! cmp -s "$PY" "$T/pyproject.toml.keep"'              # 심어졌다
  run '(cd apps/api-py && uv run --no-sync --frozen pytest -q "'"$guard_b"'" > "$T/planted.txt" 2>&1; code=$?; tail -4 "$T/planted.txt"; grep -q "^FAILED .*::test_django_is_pinned_and_locked_to_the_same_5_2_version" "$T/planted.txt" || code="FAILED 줄 없음"; echo "  심은 파손 ①(pyproject 를 6.1.2 로) · (나): pytest 종료 $code (1 이어야 한다)"; [ "$code" = 1 ])'
  run '(cd apps/api-py && uv run --no-sync --frozen pytest -q "'"$guard_a"'" 2>&1 | tail -1; exit ${PIPESTATUS[0]})'           # 설치는 그대로 5.2
  run 'test "$(sha "$LOCK")" = "'"$lock_sha"'"'                                                                        # ① 을 돌리는 동안 잠금이 다시 쓰이지 않았다
  cp "$T/pyproject.toml.keep" "$PY"
  run 'test "$(sha "$PY")" = "'"$py_sha"'" && test "$(sha "$LOCK")" = "'"$lock_sha"'"'
  # ② 잠금의 django 판 글자만 6.1.2 로 바꾼다(설치는 그대로) → (나) 가 빨갛다.
  sed -i '' '/^name = "django"$/{n;s/^version = "5\.2\.18"$/version = "6.1.2"/;}' "$LOCK"
  run 'test "$(grep -A1 "^name = \"django\"$" "$LOCK" | tail -1)" = "version = \"6.1.2\"" && test "$(diff "$LOCK" "$T/uv.lock.keep" | grep -c "^[<>]")" = 2'   # 한 줄만 다르다
  run '(cd apps/api-py && uv run --no-sync --frozen pytest -q "'"$guard_b"'" > "$T/planted.txt" 2>&1; code=$?; tail -4 "$T/planted.txt"; grep -q "^FAILED .*::test_django_is_pinned_and_locked_to_the_same_5_2_version" "$T/planted.txt" || code="FAILED 줄 없음"; echo "  심은 파손 ②(잠금의 판 글자를 6.1.2 로) · (나): pytest 종료 $code (1 이어야 한다)"; [ "$code" = 1 ])'
  run '(cd apps/api-py && uv run --no-sync --frozen pytest -q "'"$guard_a"'" 2>&1 | tail -1; exit ${PIPESTATUS[0]})'
  cp "$T/uv.lock.keep" "$LOCK"
  run 'test "$(sha "$LOCK")" = "'"$lock_sha"'" && test "$(sha "$PY")" = "'"$py_sha"'"'
  run 'git status --porcelain | diff - "$T/before.txt"'                                                                  # 작업 트리가 심기 전 그대로
  run '(cd apps/api-py && uv lock --check 2>&1 | tail -1; exit ${PIPESTATUS[0]})'
  run '(cd apps/api-py && uv run --frozen python -c "import django, sys; print(django.VERSION); sys.exit(django.VERSION[:3] != (5, 2, 18))")'   # 설치가 그대로다
  run '(cd apps/api-py && uv run --frozen pytest -q "$GUARD" 2>&1 | tail -1; exit ${PIPESTATUS[0]})'                     # 되돌린 뒤 3 passed
}

# 한 층을 돌리고 EXIT 를 찍는다. 다시 돌리지 않는다(빨가면 빨간 대로 남긴다).
layer() { # <이름> <명령…>
  local name="$1" code started=$SECONDS
  shift
  echo; echo "▶ $*"
  "$@"; code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  if [ "$code" -ne 0 ]; then
    memory_pressure | grep percentage
    [ "$name" = "통합 층" ] && docker compose logs --no-color --tail 80 api-py migrate-py worker-py queue parser
  fi
}

containers_part() {
  echo; echo "── 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  run 'test ! -e "$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"'   # 감독의 전량이 도는 중이 아니다
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'                                                                # 포트 넷이 비어 있다
  [ "$busy" = 0 ] || return 1
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  # scripts/verify.sh 의 차례를 본뜬다: 공개키 내보내기 → 이미지 짓기 → (이미지 안의 판 단언) → 전부 띄우기 → 층 셋.
  run 'docker compose build api-py 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  echo; echo "── 이미지 안의 Django (방금 지은 이미지. api-py·worker-py·migrate-py 가 같은 이미지를 쓴다)"
  run 'docker compose run --rm --no-deps -T api-py python -c "import django,sys; print(django.VERSION); sys.exit(django.VERSION[:3] != (5, 2, 18))"'
  run 'docker compose run --rm --no-deps -T api-py python -c "import ninja,sys; print(ninja.__version__); sys.exit(ninja.__version__ != \"1.7.1\")"'
  run 'docker compose up -d --wait 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  run 'docker compose exec -T worker-py python -c "import django,sys; from urllib.parse import urlsplit; from esgapi.config.celery import app; print(django.VERSION, app.conf.broker_url.split(\":\")[0]); sys.exit(not (django.VERSION[:3] == (5, 2, 18) and urlsplit(app.conf.broker_url).hostname == \"queue\"))"'   # 떠 있는 워커도 5.2.18, 브로커는 로컬 흉내
  layer "업무 층" apps/api-py/scripts/test-business.sh -n 2
  layer "보안 층" apps/api-py/scripts/test-security.sh
  layer "통합 층" apps/api-py/scripts/test-integration.sh
  echo; echo "── 심은 파손 ③: 커밋 뒤에 부를 것이 반복 변수 job 을 닫아 잡게 고친다 → 일감 둘짜리 테스트가 빨갛다"
  cp "$SVC" "$T/services.py.keep"
  local svc_sha; svc_sha="$(sha "$SVC")"
  git status --porcelain > "$T/before-c.txt"
  run 'apps/api-py/scripts/test-business.sh "$EACH" 2>&1 | tail -1; exit ${PIPESTATUS[0]}'                                  # 심기 전: 1 passed
  sed -i '' 's/transaction\.on_commit(_sending(send, tenant_id=job\.tenant_id, job_id=job\.id, kind=job\.kind), robust=True)/transaction.on_commit(lambda: send(tenant_id=job.tenant_id, job_id=job.id, kind=job.kind), robust=True)/' "$SVC"
  run 'test "$(grep -c "on_commit(lambda: send(tenant_id=job.tenant_id" "$SVC")" = 1 && test "$(diff "$SVC" "$T/services.py.keep" | grep -c "^[<>]")" = 2'   # 한 줄만 다르다
  run 'apps/api-py/scripts/test-business.sh "$EACH" > "$T/planted3.txt" 2>&1; code=$?; tail -3 "$T/planted3.txt"; grep -q "^FAILED .*::test_each_unfinished_job_is_sent_with_its_own_id" "$T/planted3.txt" || code="FAILED 줄 없음"; echo "  심은 파손 ③(job 을 닫아 잡음): pytest 종료 $code (1 이어야 한다)"; [ "$code" = 1 ]'
  cp "$T/services.py.keep" "$SVC"
  run 'test "$(sha "$SVC")" = "'"$svc_sha"'" && git status --porcelain | diff - "$T/before-c.txt"'
  run 'apps/api-py/scripts/test-business.sh "$EACH" 2>&1 | tail -1; exit ${PIPESTATUS[0]}'                                  # 되돌린 뒤: 1 passed
  run 'test -z "$(docker compose logs --no-color worker-py queue api-py | grep -i "amazonaws")"'                              # 기록 어디에도 AWS 의 주소가 없다
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

boundary_part() {
  echo
  echo "── 바뀐 파일 (기준 $B 대비, 새 파일 포함)"
  changed
  run 'n="$(outside | wc -l | tr -d " ")"; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
}

case "$MODE" in
  --pure) pure_part; boundary_part ;;
  --containers) containers_part; boundary_part ;;
  all) pure_part; containers_part; boundary_part ;;
esac
echo
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
