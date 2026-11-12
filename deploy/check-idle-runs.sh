#!/usr/bin/env bash
# 다시 띄우기 전에 진행 중인 실행·일감이 없는지 본다(밴드 DP1, MARC-ENT-352 2). 도는 자리: 서버. 읽기만 한다.
#   사용: deploy/check-idle-runs.sh       종료 0 = 진행 중 0(또는 첫 배포) · 1 = 진행 중 있음 · 2 = 읽지 못함
# 세는 것: run_runs·run_jobs 의 status queued·processing 을 회사(company_id)별로 — 찍는 것은 표·회사 id·수뿐(내용 0).
# 주인 역할(postgres 컨테이너의 POSTGRES_USER — 표 주인)로 ${POSTGRES_DB}_py 를 밝혀 읽는다.
# 「첫 배포」로 지나가는 것은 postgres 볼륨(<프로젝트>_postgres-data)이 없을 때뿐. 볼륨이 있는데 못 읽으면 2.
# 남은 것이 있으면 끝나길 기다린다. 재부팅·워커 죽음 뒤 영영 안 끝나는 것은 docs/deploy-demo.md 「멈춘 실행」(requeue).
# 환경 변수(로컬 리허설용): DEPLOY_ROOT(기본 /srv/esg-demo — 이 스크립트가 /srv/esg-demo2/… 에 있으면 그쪽) · APP_DIR(기본 $DEPLOY_ROOT/current) · ENV_FILE(기본 $DEPLOY_ROOT/shared/.env).
set -euo pipefail

# 기본 뿌리는 이 스크립트가 놓인 벌을 따른다(밴드 DM1): /srv/esg-demo2/… 아래면 둘째 벌, 그 밖은 첫 벌.
here="$(cd "$(dirname "$0")" && pwd)"
case "$here" in /srv/esg-demo2/*) default_root=/srv/esg-demo2 ;; *) default_root=/srv/esg-demo ;; esac
root="${DEPLOY_ROOT:-$default_root}"
app="${APP_DIR:-$root/current}"
env_file="${ENV_FILE:-$root/shared/.env}"
[ -r "$env_file" ] || { echo "env 파일을 읽을 수 없다: $env_file" >&2; exit 2; }
# 도커에 못 닿으면 볼륨 검사가 「없음」으로 읽혀 첫 배포로 지나간다 — 먼저 멈춘다(리뷰 L1)
docker info >/dev/null 2>&1 || { echo "도커에 닿지 못했다(docker info)" >&2; exit 2; }
# 비밀이 아닌 이름 하나만 읽는다(파일 전체를 셸에 싣지 않는다).
project="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$env_file" | tail -n 1)"
[ -n "$project" ] || { echo "COMPOSE_PROJECT_NAME 이 없다: $env_file" >&2; exit 2; }

if ! docker volume inspect "${project}_postgres-data" >/dev/null 2>&1; then
  echo "첫 배포: 볼륨 ${project}_postgres-data 가 없다 — 진행 중 실행 0 으로 본다"
  exit 0
fi

cd "$app"
sql="SELECT 'run_runs', company_id, count(*) FROM run_runs WHERE status IN ('queued','processing') GROUP BY company_id
UNION ALL
SELECT 'run_jobs', company_id, count(*) FROM run_jobs WHERE status IN ('queued','processing') GROUP BY company_id
ORDER BY 1, 2"
if ! out="$(docker compose -p "$project" --env-file "$env_file" -f compose.yaml -f deploy/compose.prod.yaml exec -T postgres \
    sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "${POSTGRES_DB}_py" -At -F " " -c "$1"' sh "$sql")"; then
  echo "읽지 못했다(볼륨은 있다 — postgres 가 떠 있는지, 표가 있는지 본다)" >&2
  exit 2
fi
if [ -z "$out" ]; then
  echo "진행 중 실행 0 (run_runs·run_jobs 의 queued·processing)"
  exit 0
fi
echo "진행 중 있음 — 표 회사id 수:"
echo "$out" | sed 's/^/  /'
exit 1
