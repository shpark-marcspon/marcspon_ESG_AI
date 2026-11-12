#!/usr/bin/env bash
# 밴드 X1a(MARC-TICK-166)의 심은 파손: 옮긴 파일(runs 앱)을 기계 검사가 전과 같은 세기로 무는가(발주서 §3 의 P1~P9).
#   사용: apps/api-py/scripts/planted-breaks-X1a.sh --commit <2|3> [--with-containers]
#     --commit 2 는 P1~P6·P9, 3 은 전부. P7·P8 은 컨테이너(보안 층)가 필요하다: --with-containers 가 없으면 「안 돌림」으로
#     찍고 심음의 수에 넣어 잡음 수가 모자라게 한다(조용한 초록 금지). --with-containers 면 이 워크트리의 compose 의
#     Postgres 가 떠 있어야 한다(section4-X1a.sh 가 띄운다).
# 계약(.importlinter)의 판정은 scripts/planted-breaks.sh 가 한다. 여기 P5·P6 은 옮긴 자리에서 계약이 무는지만 다시 본다.
# 심기 전의 바이트를 임시 폴더에 들고 있다가 되쓴다(checkout·stash 를 쓰지 않는다). 심을 때마다 파일이 그 바이트와
# 같은지 먼저 본다. 끝 줄 둘: PLANTED=<잡음>/<심음>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
set -u
cd "$(dirname "$0")/.."

COMMIT=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <2|3> [--with-containers]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 2 | 3) ;; *) echo "--commit <2|3> 이 필요하다" >&2; exit 2 ;; esac

backup="$(mktemp -d /private/tmp/x1a.XXXXXX)"
case "$backup" in /private/tmp/x1a.*) ;; *) exit 99 ;; esac
touched=()

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
  printf 'cached %s\n' "$(git diff --cached -- . | shasum -a 256 | cut -d' ' -f1)"
}
fingerprint > "$backup/.fingerprint-before"

restore() {
  local f
  for f in "${touched[@]:-}"; do
    [ -n "$f" ] && cp "$backup/$(echo "$f" | tr / _)" "$f"
  done
  touched=()
}
trap 'restore; rm -rf "$backup"' EXIT

# <파일> <옛 글> <새 글> — 옛 글이 꼭 한 번 있어야 심는다(없거나 둘이면 「못 심음」).
plant() {
  local f="$1" key
  key="$backup/$(echo "$f" | tr / _)"
  if [ -e "$key" ]; then
    cmp -s "$key" "$f" || { echo "  ★ $f 가 들고 있던 바이트와 다르다(앞 심기가 안 되돌려졌다)"; return 1; }
  else
    cp "$f" "$key"
  fi
  touched+=("$f")
  python3 - "$f" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
n = text.count(old)
if n != 1:
    print(f"  ★ 심을 글이 {n}번 있다: {old!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}

ENV_PY=(env -u OPENAI_API_KEY)
total=0; caught=0
# <번호> <설명> — 앞에서 심었고, 뒤의 판정 함수가 0 을 내면 잡음
judge() {
  local id="$1" desc="$2" verdict="$3"
  total=$((total + 1))
  if [ "$verdict" = 0 ]; then caught=$((caught + 1)); mark="잡음"; else mark="★ 못 잡음"; fi
  printf '%-4s %-90s → %s\n' "$id" "$desc" "$mark"
  restore
}
# pytest 노드들이 전부 빨개졌는가(실패로 끝나고, 각 노드가 FAILED/ERROR 줄에 있다)
pytest_red() { # <기록 파일> <노드…>
  local log="$1"; shift
  (cd . && "${ENV_PY[@]}" uv run --frozen pytest -q -p no:cacheprovider -rfE "$@" > "$log" 2>&1)
  local code=$? node
  [ "$code" = 0 ] && return 1
  for node in "$@"; do
    grep -q -E "^(FAILED|ERROR) ${node//[/\\[}" "$log" || { echo "    (빨갛지 않은 노드: $node)"; return 1; }
  done
  return 0
}
# 보안 층의 노드(파일 하나)가 실패로 끝나는가 — 보안 층 실행기로
security_red() { # <기록 파일> <파일::이름 무늬…>
  local log="$1"; shift
  scripts/test-security.sh -p no:cacheprovider -q -rfE "$@" > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/    /'
  [ "$code" != 0 ] && grep -q -E "^(FAILED|ERROR) " "$log"
}
lint_broken() { # <기록 파일> <계약 이름 앞머리>
  COLUMNS=400 uv run --frozen lint-imports --no-cache > "$1" 2>&1
  grep -q "^$2.* BROKEN" "$1"
}
L="$backup/log"; mkdir -p "$L"

echo "── X1a 심은 파손 · 커밋 $COMMIT · 컨테이너 $CONTAINERS · HEAD $(git rev-parse --short HEAD)"

# P1 — Selector 의 문 함수가 회사를 묻지 않으면 Selector 검사가 무는가(옮긴 자리 runs/service/selectors/jobs.py)
if plant esgapi/runs/service/selectors/jobs.py "    return JobRow.for_company(company_id)" "    return JobRow.objects.all()"; then
  pytest_red "$L/p1" "esgapi/core/tests/test_selector_scope.py::test_selectors_scope_every_read[runs/service/selectors/jobs.py]"; v=$?
else v=1; fi
judge P1 "runs selectors/jobs.py 의 _jobs 를 JobRow.objects.all() 로" "$v"

# P2 — Service 가 회사 범위 밖 매니저로 쓰면 Service 검사가 무는가(고친 자리에서 runs 의 jobs 를 읽는가)
if plant esgapi/runs/service/services/jobs.py "    guard = JobRow.for_company(company_id).filter(pk=job_id, status=row.status, attempts=row.attempts)" "    guard = JobRow.unscoped.filter(pk=job_id, status=row.status, attempts=row.attempts)"; then
  pytest_red "$L/p2" "esgapi/core/tests/test_selector_scope.py::test_core_services_only_write_and_name_the_tenant"; v=$?
else v=1; fi
judge P2 "runs services/jobs.py 의 claim_job 안 JobRow.for_company(company_id) 를 JobRow.unscoped 로" "$v"

# P3 — 워커 서비스의 지킴이를 무르면 트랜잭션 규칙 검사가 무는가(+ 컨테이너면 보안 층의 「블록 밖이면 던진다」)
if plant esgapi/runs/service/services/jobs.py '        raise NotInTransactionError(f"{name} 는 transaction.atomic() 안에서만 부른다")' "        pass"; then
  pytest_red "$L/p3" "esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[runs/service/services/jobs.py]"; v=$?
  if [ "$v" = 0 ] && [ "$CONTAINERS" = 1 ]; then
    security_red "$L/p3s" "tests/security/test_jobs.py::test_the_claim_must_be_called_inside_a_transaction"; v=$?
  elif [ "$CONTAINERS" = 0 ]; then
    echo "    (보안 층 tests/security/test_jobs.py 몫은 안 돌림 — --with-containers 없음. 순수 몫만 판정)"
  fi
else v=1; fi
judge P3 "runs services/jobs.py 의 _require_transaction 의 raise 를 pass 로" "$v"

# P4 — 경로가 권한 문장을 빠뜨리면 권한 검사가 무는가(옮긴 자리 runs/service/apis/runs.py)
if plant esgapi/runs/service/apis/runs.py '    permitted(request, "runs_list")
' ""; then
  pytest_red "$L/p4" "esgapi/core/tests/test_permissions.py::test_each_route_checks_its_own_operation_id_first"; v=$?
else v=1; fi
judge P4 "runs/service/apis/runs.py 의 runs_list 첫 문장 permitted(…) 를 지움" "$v"

# P5 — core 의 문서 selector 가 예외(runs.models) 밖의 runs 를 import 하면 계약 가 가 무는가
if plant esgapi/core/service/selectors/documents.py "from esgapi.runs.models import JobRow
" "from esgapi.runs.models import JobRow
import esgapi.runs.service.selectors.jobs
"; then
  lint_broken "$L/p5" "가\. core 는 업무 모듈을 import 하지 않는다"; v=$?
else v=1; fi
judge P5 "core/service/selectors/documents.py 에 import esgapi.runs.service.selectors.jobs (예외 밖)" "$v"

# P6 — runs 의 경로가 models 를 import 하면 계약 라(와일드카드 *.service.apis)가 무는가
if plant esgapi/runs/service/apis/runs.py "from esgapi.core.auth.bearer import permitted
" "from esgapi.core.auth.bearer import permitted
from esgapi.runs.models import JobRow
"; then
  lint_broken "$L/p6" "라\. api\.py·service/apis·tasks\.py 는 models 를 직접 import 하지 않는다"; v=$?
else v=1; fi
judge P6 "runs/service/apis/runs.py 에 from esgapi.runs.models import JobRow" "$v"

# P7·P8 — 마이그레이션(보안 층). 테스트 DB 를 새로 만든다(--create-db).
if [ "$COMMIT" = 3 ]; then
  if [ "$CONTAINERS" = 1 ]; then
    if plant esgapi/runs/migrations/0001_initial.py '        same_company_foreign_key(table=JOBS, column="document_id", target=DOCUMENTS),
' ""; then
      security_red "$L/p7" --create-db tests/security/test_same_company_foreign_keys.py tests/security/test_migrations.py; v=$?
    else v=1; fi
    judge P7 "runs 0001 에서 same_company_foreign_key(…) 줄을 지움" "$v"
    if plant esgapi/runs/migrations/0001_initial.py "    grant(f'\"{JOBS}\"', \"SELECT, INSERT, UPDATE\")," "    grant(f'\"{JOBS}\"', \"SELECT, INSERT, UPDATE, DELETE\"),"; then
      security_red "$L/p8" --create-db tests/security/test_owner.py tests/security/test_documents.py; v=$?
    else v=1; fi
    judge P8 "runs 0001 의 grant 에 DELETE 를 더함" "$v"
    # 되돌린 마이그레이션으로 테스트 DB 를 다시 세워 둔다(뒤 실행이 심은 꼴의 DB 를 다시 쓰지 않게)
    scripts/test-security.sh -p no:cacheprovider -q --create-db tests/security/test_migrations.py > "$L/p78-after" 2>&1
    echo "    (되돌린 뒤 보안 test_migrations: $(tail -1 "$L/p78-after"))"
  else
    total=$((total + 2))
    echo "P7   runs 0001 에서 same_company_foreign_key(…) 줄을 지움 → ★ 안 돌림(--with-containers 없음)"
    echo "P8   runs 0001 의 grant 에 DELETE 를 더함 → ★ 안 돌림(--with-containers 없음)"
  fi
fi

# P9 — 앱 목록에서 runs 를 빼면 설정 검사와 Django 가 무는가(수집 오류도 빨강)
if plant esgapi/config/apps_list.py '    "esgapi.runs",
' ""; then
  ("${ENV_PY[@]}" uv run --frozen pytest -q -p no:cacheprovider -rfE esgapi/config/tests/test_settings.py esgapi/core/tests/test_documents_models.py > "$L/p9" 2>&1); code=$?
  tail -1 "$L/p9" | sed 's/^/    /'
  grep -m 2 -E "^(FAILED|ERROR) |RuntimeError: " "$L/p9" | cut -c1-160 | sed 's/^/    /'
  v=1
  [ "$code" != 0 ] && grep -q -E "^(FAILED|ERROR) esgapi/config/tests/test_settings.py::test_the_app_list_is_core_and_the_four_modules|^ERROR esgapi/core/tests/test_documents_models.py|RuntimeError: Model class esgapi.runs.models.JobRow" "$L/p9" && v=0
else v=1; fi
judge P9 "config/apps_list.py 에서 \"esgapi.runs\" 를 지움" "$v"

restore
fingerprint > "$backup/.fingerprint-after"
if diff "$backup/.fingerprint-before" "$backup/.fingerprint-after" > "$backup/.fingerprint-diff"; then
  fp=same
else
  fp=differs
  echo "★ 작업 트리가 처음과 다르다:"; cat "$backup/.fingerprint-diff"
fi
echo "PLANTED=$caught/$total"
echo "FINGERPRINT=$fp"
[ "$caught" = "$total" ] && [ "$fp" = same ]
