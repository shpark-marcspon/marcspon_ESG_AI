# 시연 배포 — EC2 한 대 + compose

마크스폰 시연용 서버 한 대의 세우기·올리기·되살리기 절차다(밴드 DP1, 결정 `MARC-ENT-416`·`MARC-ENT-418`). 서버는 지금의 `compose.yaml` 을 그대로 띄우고, `deploy/compose.prod.yaml` 이 앞에 TLS 역프록시(Caddy)를 하나 더한다. Terraform(`infra/terraform`)은 쓰지 않는다.

**무효 조건**: 서비스 이름·포트(api-py 8000, storage 7070), 서명 꼴(서명한 올리기 주소에 호스트가 들어감), 큐 종류(메모리 큐 ElasticMQ), 웹을 api-py 가 같은 출처에서 내는 꼴 가운데 하나라도 바뀌면 이 문서와 `deploy/` 를 다시 잰다.

```
브라우저 ──443──▶ proxy(Caddy, Let's Encrypt) ──▶ api-py:8000   https://<SITE_DOMAIN>   (웹 + /api)
                          └──────────────────────▶ storage:7070  https://<FILES_DOMAIN>  (서명한 PUT·OPTIONS 만)
서버 안: api-py · worker-py · parser · postgres · storage · queue (+ 한 번짜리 migrate-py · storage-cors)
```

| 자리 | 무엇 |
|---|---|
| `/srv/esg-demo/releases/<해시>` | `ship.sh` 가 푼 코드(최근 3개) |
| `/srv/esg-demo/current` | 지금 띄운 코드(심볼릭) |
| `/srv/esg-demo/shared/.env` | 서버 비밀 하나(deploy 소유, 600). `deploy/env.prod.example` 이 이름 목록 |
| `/srv/esg-demo/shared/DEPLOYED` | 올린 커밋의 기록(UTC 시각 해시) |
| `/srv/esg-demo/backup/` | DB 덤프 7개 · `backup.log` |
| 도커 볼륨 `esg-demo_postgres-data` · `esg-demo_storage-data` · `esg-demo_caddy-data` | DB · 올린 문서 · 인증서 — **지우지 않는다** |

스크립트는 전부 `deploy/` 에 있고 머리 주석이 쓰는 법이다. 운영 기계에서 도는 것: `ship.sh` · `put-llm-key.sh` · `smoke.sh`. 서버에서 도는 것: `bootstrap-host.sh`(root) · `make-env.sh` · `up.sh` · `check-idle-runs.sh` · `backup-db.sh`(deploy 사용자).

**권한**: 배포는 마크스폰 AWS 계정의 사람 IAM 사용자(넓은 권한)로 한다. 좁은 정책 사용자는 만들 수 없어서(그 계정에서 IAM 사용자·정책 만들기 불가) `deploy/iam-policy.json` 은 **배포가 부르는 AWS 동작의 닫힌 목록**이다. 마크스폰이 좁은 사용자를 만들 때 그대로 붙이는 파일이고(`ACCOUNT_ID`·`HOSTED_ZONE_ID` 를 바꿔 넣음), 그전까지 울타리는 「아래 1절 표 밖의 AWS 명령을 부르지 않는다」 하나다. 지우는 동작(`Terminate*`·`Delete*`·`ReleaseAddress` 등)은 목록에 없다 — 걷기는 관리자가 한다(10절).

## 1. 처음 세우기

리전 `ap-northeast-2`, 프로필 `marcspon`(짧은 세션 — 만료되면 다시 로그인), 태그 `Project=marcspon-demo`. 운영 기계에서 `esg-app` 저장소 뿌리에 서서.

| # | 어디서 | 무엇 |
|---|---|---|
| C1 | 운영 | `aws sts get-caller-identity --profile marcspon` — 계정·사용자 확인 |
| C2 | 운영 | `ssh-keygen -t ed25519 -f ~/.ssh/marcspon-demo`(개인키는 이 기계 밖으로 내지 않음) · `aws ec2 import-key-pair --key-name marcspon-demo --public-key-material fileb://~/.ssh/marcspon-demo.pub --tag-specifications 'ResourceType=key-pair,Tags=[{Key=Project,Value=marcspon-demo}]'` |
| C3 | 운영 | `describe-vpcs --filters Name=isDefault,Values=true` · `describe-subnets` · `describe-images --owners 099720109477 --filters 'Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*'`(가장 새 것) |
| C4 | 운영 | `create-security-group --group-name marcspon-demo-web`(태그) · ingress tcp 80·443 `0.0.0.0/0` · tcp 22 `<운영 공인 IP>/32`(`curl https://checkip.amazonaws.com`) |
| C5 | 운영 | `run-instances` — `t4g.large` · `--metadata-options HttpTokens=required` · `--block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,Encrypted=true,DeleteOnTermination=false}'` · `--disable-api-termination` · `--tag-specifications` 를 **instance 와 volume 둘 다**(볼륨 태그가 없으면 DLM 이 아무것도 안 찍고 오류도 없다) |
| C6 | 운영 | `allocate-address`(태그) · `associate-address` |
| C7 | 운영 | 주소: (가) 이 계정 Route53 존이면 `change-resource-record-sets` 로 A 레코드 둘(`SITE`·`FILES` → EIP) / (나) 마크스폰 도메인의 하위 이름이면 마크스폰에 EIP 를 알려 A 레코드 둘 |
| C8 | 운영 | (DLM 기본 역할이 있을 때만 — 마크스폰 관리자가 `aws dlm create-default-role --resource-type snapshot`) `dlm create-lifecycle-policy` — 대상 볼륨 태그 `Project=marcspon-demo`, 매일 1회, 7개 |
| C9 | 서버 | `ssh ubuntu@<EIP> 'sudo bash -s' < deploy/bootstrap-host.sh` |
| C10 | 운영→서버 | `dig +short <SITE>` · `dig +short <FILES>` = EIP 확인 → `deploy/ship.sh deploy@<EIP> <병합된 main 해시>` → 서버에서 `/srv/esg-demo/current/deploy/make-env.sh <SITE> <FILES>` → `/srv/esg-demo/current/deploy/up.sh`(처음은 **mock** — `LLM_RUN_MODE` 빈 값. 이때 Caddy 가 인증서를 받는다) → `esg_app` 역할이 있는지(아래) |
| C11 | 운영 | `deploy/smoke.sh <SITE> <FILES>` 전부 ok(발급자 Let's Encrypt). 발급이 안 되면 9절 |
| C12 | 운영→서버 | **SDK 변수 지움** — `sudo cut -d= -f1 /srv/esg-demo/shared/.env` 에 `OPENAI_*`·`ANTHROPIC_*`·`GEMINI_API_KEY` 같은 SDK 이름이 없을 것(live 면 기동 거절, 목록 `apps/api-py/esgapi/config/env.py`, 앱 키는 `LLM_*_API_KEY` 만) → `deploy/put-llm-key.sh deploy@<EIP>`(마크스폰 키 → `LLM_RUN_MODE=live`) → 서버에서 `up.sh` → `docker compose -p esg-demo … logs api-py | grep llm_run_mode` 한 줄 `mode=live providers=openai max_usd=5.0 sink=db` |
| C13~14 | 서버 | 회사·계정(5절) |
| C15 | 운영·서버 | `crontab -l`(deploy) 에 백업 줄 · `backup-db.sh` 한 번 · DLM 정책 `ENABLED`(있으면) · `describe-volumes --filters Name=tag:Project,Values=marcspon-demo` = 1 |
| C16 | 운영 | 다운 알림(10절): `route53 create-health-check`(HTTPS `/api/readyz`) · `change-tags-for-resource` · us-east-1 에서 `sns create-topic`(태그) · `sns subscribe`(email) · `cloudwatch put-metric-alarm`(태그) → 받는 사람이 확인 링크 |

`esg_app` 역할 확인(첫 up 뒤, postgres 에 다시 띄움을 달아 initdb 실패가 가려질 수 있어서):
`docker compose -p esg-demo --env-file /srv/esg-demo/shared/.env -f compose.yaml -f deploy/compose.prod.yaml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT rolname FROM pg_roles"' | grep -cx esg_app` → `1`.

아래에서 `dc` 는 서버의 `cd /srv/esg-demo/current && docker compose -p esg-demo --env-file /srv/esg-demo/shared/.env -f compose.yaml -f deploy/compose.prod.yaml` 의 줄임이다. `-p esg-demo` 를 빼지 않는다 — 셸에 내보낸 `COMPOSE_PROJECT_NAME` 이 `--env-file` 을 이겨 새 빈 볼륨으로 뜬다.

**이미지 받기가 막히면**(Docker Hub 익명 한도 429) 이 차례로:
1. 그냥 받기 — `up.sh` 가 받는다. 잠시 뒤 다시 돌려 본다.
2. 429 가 이어지면 운영 기계(맥, arm64 — 서버와 같은 아키텍처)에서 받아 넘긴다: `docker pull <이미지@다이제스트>` → `docker save <이미지@다이제스트> | ssh deploy@<EIP> docker load`. 이미지 이름은 `compose.yaml`·`deploy/compose.prod.yaml`·`docker/*.Dockerfile` 의 `FROM`·`image:` 줄 그대로(다이제스트 고정이라 같은 것이 간다). 넘긴 뒤 서버에서 `docker image inspect <이미지@다이제스트>` 가 찾히는지 본다 — 도커의 이미지 저장 방식에 따라 `load` 가 다이제스트 이름을 안 남길 수 있다(재지 않음). 안 찾히면 3.
3. 그래도 필요하면 사용자가 서버에서 직접 `docker login`(Docker Hub 읽기 전용 액세스 토큰 — 사용자가 친다).
배포 러너는 로그인하지 않는다.

## 2. 다시 올리기

1. **진행 중 실행 0**: 서버에서 `deploy/check-idle-runs.sh` → 0 이어야 한다. 남아 있으면 끝날 때까지 기다린다(그린워싱 한 번이 5분 안팎). 실패한 실행은 고친 뒤 **새 실행으로** 다시 돌린다(`MARC-ENT-352` 2). 기다려도 줄지 않으면 3절.
2. 운영 기계에서 `deploy/ship.sh deploy@<EIP> <병합된 main 해시>`.
3. 서버에서 `/srv/esg-demo/current/deploy/up.sh` — 1을 다시 보고, 빌드하고, **교체 전 로그를 떠 두고**(`/srv/esg-demo/logs/<UTC>/compose.log.gz`·`ps.txt`, 600, 서비스마다 끝 2만 줄·gzip, 최근 10개 — 읽기 `zcat`), **새 이미지로 `migrate --plan` 을 세어 적용할 것이 있으면 `backup-db.sh` 를 먼저**(덤프가 실패하면 올리지 않고 멈춘다), 띄우고, proxy 를 늘 다시 만들고(새 release 의 `Caddyfile` 을 읽게 — `current` 심볼릭 경로가 같아 compose 가 저절로는 안 바꾼다), proxy 너머 `/api/readyz` 200 을 본다.
4. 운영 기계에서 `deploy/smoke.sh <SITE> <FILES>`. 안 되면 7절 「되돌리기」.

## 3. 멈춘 실행

큐는 메모리라 queue 컨테이너가 다시 뜨면(재부팅 포함) 비고(`compose.yaml` 의 queue), 큐에 다시 넣는 일은 저절로 되지 않는다. 그래서 재부팅·워커 죽음 뒤 DB 에 `queued`·`processing` 이 남으면 `check-idle-runs.sh` 가 영영 1 을 내고 `up.sh` 가 멈춘다. 차례:

1. 임대 시간(`JOB_LEASE_SECONDS`, 기본 330초)이 지나길 기다린다.
2. `check-idle-runs.sh` 가 찍은 회사 id 마다: `dc exec -T api-py python manage.py requeue_runs --tenant <id> --dry-run` → 고른 것을 보고 `--dry-run` 없이 한 번 → `requeue_jobs --tenant <id>` 도 같은 꼴.
3. 실행이 끝나길 기다려 `check-idle-runs.sh` 를 다시 본다.

`check-idle-runs.sh` 가 2(읽지 못함)면 postgres 가 안 떠 있는지 본다(`dc ps postgres`). 멈춰 있으면 `dc start postgres` 뒤 다시 본다(볼륨이 있는데 못 읽는 것은 첫 배포로 넘기지 않는다).

**재부팅 뒤 할 일**: 컨테이너는 다시 뜬다(`restart: unless-stopped`). `check-idle-runs.sh` 가 0 이 아니면 이 절을 한다.

## 4. 하지 않는 것

서버에서: `docker compose down -v` · `docker volume rm|prune` · `docker system prune --volumes` · `COMPOSE_PROJECT_NAME` 바꾸기(새 빈 볼륨) · postgres 데이터 폴더 손대기 · 인스턴스 걷기 · `.env` 를 `docker compose config`·`env`·`printenv`·`docker inspect`·`set -x` 로 찍기 · 서버에서 시험 돌리기. AWS 에서 지우는 명령 0.

둘째 벌(11절)에서도 같다: `dc2 down -v` 금지(내리기는 `stop`) · `COMPOSE_PROJECT_NAME`(`esg-demo2`)·뿌리 바꾸기 · 한 벌의 `up.sh`·`ship.sh` 로 다른 벌 올리기 · 둘째 벌에 회사 둘째 만들기(로그인 401) · 둘째 벌에 proxy 띄우기(443 은 첫 벌 하나).

**허락된 정리**(디스크): `docker image prune -f`(`up.sh` 가 함) · `docker builder prune -f --filter until=72h` · 옛 releases(`ship.sh` 가 3개만 남김) · 옛 덤프(`backup-db.sh` 가 7개만 남김). 볼륨·컨테이너 지우기는 여전히 0.

## 5. 회사와 계정

- 회사: `dc run --rm migrate-py python manage.py seed_company --name <이름> --business-licence-number <번호> --subdomain <서브도메인>` — 주인 역할 설정은 migrate-py 에만 있다.
- 사람 계정: 서버에서 비밀번호를 만들어 root 만 읽는 파일에만 둔다. 파일은 먼저 `sudo install -m 600 -o root -g root /dev/null /srv/esg-demo/shared/initial-passwords` 로 만든다(쓰는 순간 권한이 열려 있지 않게). 예: `pw=$(openssl rand -hex 12)` → `printf '%s\n' "$pw" | dc exec -T api-py python manage.py create_user --company <서브도메인> --username <아이디> --name <이름> --password-stdin` → `printf '%s %s\n' <아이디> "$pw" | sudo tee -a /srv/esg-demo/shared/initial-passwords >/dev/null`. 운영 관리자는 `--admin`. 전부 첫 로그인 때 비밀번호를 바꿔야 한다.
- 비밀번호 넘기기: 사용자가 `ssh ubuntu@<EIP> sudo cat /srv/esg-demo/shared/initial-passwords` 로 꺼내 전한 뒤 `sudo rm` 한다.
- 잃었을 때: `dc exec -T api-py python manage.py reset_password --admin|--company <서브도메인> --username <아이디> --password-stdin`(refresh 계보도 끊긴다).
- **스모크 계정 정리**: 스모크가 끝나면, 주소를 마크스폰(대외 `MARC-TICK-75`)에 넘기기 전에 `dp1-smoke-admin`·`dp1-smoke` 를 `reset_password … --password-stdin` 에 버리는 무작위 값으로 초기화한다(계정 끄기 명령이 없어 이것이 끄기다). 옛 비밀번호로 로그인이 401 인지 보고, 비밀번호 파일(서버 임시 파일·운영 기계 `DP1.out/smoke.pass`)을 지운다.

## 6. 키 바꾸기

`deploy/put-llm-key.sh deploy@<EIP>` → 서버에서 `up.sh`. 키는 운영 기계의 키 파일에서 ssh 표준 입력으로만 간다(인자·화면 0). 실호출을 바로 끊으려면 `put-llm-key.sh deploy@<EIP> --mock` → `up.sh`.
**mock 으로 띄우면 영문번역은 늘 `setup_error` 다 — 배포본은 live 로만 쓴다**(`MARC-ISSUE-331` 1).
그 밖의 비밀(DB·저장소·세션)은 `make-env.sh` 가 한 번 만든 뒤 바꾸지 않는다. DB 비밀번호는 DB 안 역할에도 들어 있어 `.env` 만 바꾸면 닿지 못한다.
상한: `LLM_RUN_MAX_USD=5.00` · `TRANSLATION_RUN_MAX_USD=10.00`(`MARC-ENT-416` → 영문번역만 `MARC-ENT-513`, 서버 .env 10-29 반영). 하루·회사 상한은 시연 뒤(`MARC-ISSUE-305`). AWS Budgets 경보·OpenAI 프로젝트 예산 경보는 계정 주인이 건다.
`INVENTORY_SCOPE3_RUNS_ENABLED`(`MARC-ENT-535`) — 비거나 없으면 꺼짐. 끄는 법은 서버 `.env` 값을 `false` 로 두고 `up.sh`.

## 7. 백업·되살리기

- 매일 18:30 UTC(03:30 KST) `backup-db.sh` 가 `/srv/esg-demo/backup/db-<UTC>.dump` 를 만들고 7개만 남긴다. EBS 스냅숏(DLM, 역할이 있을 때)이 덤프와 올린 문서(`storage-data`)를 같이 담는다.
- 되살리기는 **새 DB 이름에 먼저**(덮어쓰기 0): `dc exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" restore_check && pg_restore -U "$POSTGRES_USER" -d restore_check --no-owner' < /srv/esg-demo/backup/<파일>` 로 보고, 바꿀지는 사람이 정한다.
- 새 서버로 옮길 때는 postgres 가 init 스크립트(`docker/postgres-init.sh` — `esg_app` 역할)를 먼저 돈 뒤(첫 up) 되살린다. 덤프에는 역할이 없다.
- 올린 문서는 스냅숏에서 볼륨을 새로 만들어 붙인다(관리자).

### 되돌리기(새 release 가 안 될 때)

먼저 1절 「진행 중 실행 0」(`check-idle-runs.sh`). 아래 `dc` 는 1절의 줄임이고, 「앞 release」는 `ls -1t /srv/esg-demo/releases`·`/srv/esg-demo/shared/DEPLOYED` 의 앞 줄이다(최근 3개만 남는다).

1. **마이그레이션이 없던 올림**(`up.sh` 가 「적용할 마이그레이션 0」): 운영 기계에서 `deploy/ship.sh deploy@<EIP> <앞 해시>` → 서버에서 `up.sh`. 코드만 돌아가고 DB 는 그대로다.
2. **마이그레이션이 있던 올림**(`up.sh` 가 「적용할 마이그레이션 n개 — 먼저 덤프」와 그 목록을 찍었다): 둘 중 하나.
   - **되감기**(되돌릴 수 있는 마이그레이션일 때 — 파일 머리 주석의 「되돌림」을 읽는다): 새 release 가 아직 `current` 일 때 `dc run --rm migrate-py python manage.py migrate <앱> <앞 번호>`(예: `migrate runs 0003`). 목록에 앱이 여럿이면 앱마다. 그 뒤 1처럼 앞 해시를 ship → `up.sh`(「적용할 마이그레이션 0」이어야 한다).
   - **덤프로 되살리기**(되감을 수 없거나 데이터가 상했을 때): 1처럼 앞 해시를 ship 하되 `up.sh` 전에 `dc stop api-py worker-py` → 먼저 이 7절 위 「되살리기」 줄(`restore_check` 새 DB)로 그 덤프를 되살려 본 뒤, 사람이 정해 제자리에 되살린다: `dc exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" "${POSTGRES_DB}_py" && createdb -U "$POSTGRES_USER" "${POSTGRES_DB}_py" && pg_restore -U "$POSTGRES_USER" -d "${POSTGRES_DB}_py" --no-owner' < /srv/esg-demo/backup/<그 올림 직전 덤프>` → `up.sh`. **덤프 뒤에 생긴 실행·문서 기록은 잃는다**(올린 파일은 storage 볼륨에 남지만 DB 행이 없다). 지우는 명령이라 사람이 직접 친다.
3. 교체 전 로그(`/srv/esg-demo/logs/<UTC>/`)에서 옛 컨테이너가 남긴 마지막 줄을 본다 — `up.sh` 가 찍은 「교체 전 로그:」 경로.

## 8. 운영 기계 IP 가 바뀌면

보안 그룹 22 의 옛 /32 를 `aws ec2 revoke-security-group-ingress`, 새 /32 를 `authorize-security-group-ingress`(둘 다 닫힌 목록에 있다).

## 9. 인증서

Caddy 가 스스로 받고 갱신하고, 실패하면 스스로 다시 해 본다. 발급처는 Let's Encrypt 하나로 고정(`deploy/Caddyfile` 전역 `cert_issuer acme`). 발급이 안 되면(DNS 가 EIP 가 아님 등) Let's Encrypt 한도를 태우지 않게 `dc stop proxy`(down 아님)로 멈추고, `dig` 로 두 이름을 고친 뒤 `up.sh`. 인증서는 볼륨 `esg-demo_caddy-data` 에 있다.
ACME 연락 메일은 두지 않는다(값이 비면 Caddyfile 이 읽히지 않는다). Let's Encrypt 는 메일 없이 발급하고, 잃는 것은 만료 알림 메일뿐이다 — 갱신은 Caddy 가 스스로 한다.

## 10. 로그·멈춤·걷기·이슈

- 로그: `dc logs --since <UTC 시각> <서비스>`. 바꾸기 전 컨테이너의 로그는 `up.sh` 가 `/srv/esg-demo/logs/<UTC>/` 에 떠 둔다(최근 10개). 키 값이 로그에 없는지는 서브셸에서 수만 센다(값을 찍지 않는다).
- **다운 알림**: Route53 상태 검사(HTTPS `https://<SITE>/api/readyz`, 30초마다·2번 실패면 실패, 태그 `Project=marcspon-demo`) → CloudWatch 경보 `marcspon-demo-readyz-down`(**us-east-1** — Route53 지표는 거기에만, `HealthCheckStatus` Minimum < 1 이 60초 1번, 데이터 없음도 경보) → SNS 주제 `marcspon-demo-alerts`(us-east-1) → 메일(경보와 복구 둘 다). 메일은 받는 사람이 구독 확인 링크를 눌러야 온다. 만든 명령: `route53 create-health-check` · `route53 change-tags-for-resource` · `sns create-topic` · `sns subscribe` · `cloudwatch put-metric-alarm`. 시험: `aws cloudwatch set-alarm-state --region us-east-1 --alarm-name marcspon-demo-readyz-down --state-value ALARM --state-reason test`(관리자).
- 멈춤·비용: 인스턴스를 멈춰도 탄력적 IP·EBS 는 과금된다. 멈춤·켜기·재부팅은 닫힌 목록에 있다. 다시 켠 뒤 3절.
- 걷기(시연이 끝난 뒤, 계정 관리자가): 종료 보호 끄기 → 인스턴스 종료 → 볼륨(`DeleteOnTermination=false` 라 남음) · EIP 놓기 · 스냅숏 · DLM 정책 · 보안 그룹 · 키 쌍 · 상태 검사 · 경보 · SNS 주제(us-east-1).
- 이슈의 자리:
  - `MARC-ISSUE-237`(브라우저 서명 PUT CORS): 해당함. `https://SITE` → `https://FILES` 는 다른 출처이고 허락 출처는 `STORAGE_CORS_ORIGINS` 하나(`https://SITE`). `smoke.sh` 의 OPTIONS 둘과 서명 PUT 으로 잰다.
  - `MARC-ISSUE-88`(tiktoken 인터넷): 서버는 바깥 망이 열려 있다. 못 받아도 흐름은 안 깨진다.
  - `MARC-ISSUE-305`(하루 상한): 시연 뒤.
  - `MARC-ISSUE-331`: 1(mock 기동의 번역 setup_error)은 시연 뒤, 2(번역 상한 칸)는 `deploy/compose.prod.yaml` 이 배포본에만 넘긴다.
- `ALLOWED_HOSTS = ["*"]`(`apps/api-py/esgapi/config/settings/base.py`)는 「ALB 가 받을 호스트를 거른다」에 기댄다. 이 서버에서는 Caddy 가 그 자리다: 두 이름 밖 Host 는 앱에 닿지 않는다(`smoke.sh` 「다른 Host → 응답 0」).
- Caddy 는 `/api` 본문을 21 MiB 까지 다 받은 뒤 api-py 에 넘긴다(`deploy/Caddyfile` `request_buffers`, 밴드 PX1). gunicorn sync 일꾼의 30초가 느린 망의 전송 시간을 세지 않게 — 버퍼 없이는 20MB 올리기를 ~650KiB/s 이하로 보내면 500 이었다. 크기는 가장 큰 앱 본문 상한 `GHG_UPLOAD_MAX_BYTES` 20 MiB(`MARC-ENT-593`) + 1 MiB 여유이고, 넘는 본문의 거절은 지금처럼 앱(413)이 한다. 버퍼가 메모리라 proxy `mem_limit` 은 256m.

## 11. 둘째 벌(데모 고정판)

같은 EC2 에 compose 한 벌 더(`esg-demo2`, 뿌리 `/srv/esg-demo2`)를 띄워 마크스폰이 데이터를 세팅해 두고 건드리지 않는 데모 전용 주소를 낸다(결정 `MARC-ENT-674`, 요청 `MARC-ISSUE-665`, 밴드 DM1). 첫 벌(`esg-demo`)은 테스트용으로 그대로다. **둘째 벌 안에도 회사는 하나만** 둔다 — 웹은 서브도메인을 보내지 않아(`MARC-ENT-283`) 회사가 둘이면 그 벌의 고객사 로그인이 전부 401 이다.

```
브라우저 ──443──▶ 첫 벌 proxy(Caddy 하나) ──▶ 첫 벌 api-py·storage         <SITE>·<FILES>
                         └─ 공유 네트워크 esg-edge ─▶ 둘째 벌 relay(demo2-edge) ─▶ 둘째 벌 api-py·storage   <DEMO2_SITE>·<DEMO2_FILES>
```

- 443 은 첫 벌 Caddy 하나다. 둘째 벌은 proxy 를 띄우지 않고(`PROXY_ROLE=none`) relay(`deploy/compose.edge-relay.yaml`·`deploy/Caddyfile.relay`)만 공유 네트워크에 붙인다. 둘째 이름 블록(`deploy/Caddyfile.demo2`)은 첫 벌과 같은 snippet 을 쓴다(HSTS·`-Server`·본문 버퍼 21 MiB / 서명 PUT·OPTIONS 만·copy 막기·60MB).
- 둘째 벌의 api-py·storage 를 공유 네트워크에 바로 붙이지 않는다: compose 가 서비스 이름을 그 네트워크의 별칭으로도 달아, 첫 벌 proxy 의 `api-py` 조회가 둘째 벌로 샐 수 있다(DM1 실측 — 같은 별칭이 두 네트워크에 있으면 도커 DNS 는 한쪽 것만 낸다).
- 첫 벌 `.env` 에 `DEMO2_SITE_DOMAIN`·`DEMO2_FILES_DOMAIN` 이 비면 첫 벌은 지금과 같다(Caddy adapt JSON·컨테이너 네트워크가 BASE 와 같음 — DM1 실측). 채우면 첫 벌 `up.sh` 가 `deploy/compose.edge-proxy.yaml` 을 얹고 `esg-edge` 를 없으면 만든다.
- 스크립트의 기본 뿌리는 스크립트가 놓인 벌이다(`/srv/esg-demo2/…` 의 `up.sh`·`backup-db.sh`·`check-idle-runs.sh` 는 `/srv/esg-demo2`). 한 벌의 `up.sh` 로 다른 벌을 올리면 멈춘다. `up.sh` 가드: `/srv/esg-demo` ↔ `esg-demo`·`edge`, `/srv/esg-demo2` ↔ `esg-demo2`·`none`.
- 둘째 벌의 호스트 포트(127.0.0.1 들여다보기)는 25432·29000·28081 — 첫 벌 기본(15432·19000·18081)과 겹치면 못 뜬다. `make-env.sh` 가 채운다.

아래 `dc2` 는 서버의 `cd /srv/esg-demo2/current && docker compose -p esg-demo2 --env-file /srv/esg-demo2/shared/.env -f compose.yaml -f deploy/compose.prod.yaml -f deploy/compose.edge-relay.yaml` 의 줄임이다(`-p esg-demo2` 를 빼지 않는다).

### 세우는 차례

| # | 어디서 | 무엇 |
|---|---|---|
| D1 | 운영 | DNS A 레코드 둘(`<DEMO2_SITE>`·`<DEMO2_FILES>` → 같은 EIP) — 1절 C7 과 같은 꼴. `dig +short` 둘 다 EIP 확인 |
| D2 | 운영 | DM1 이 병합된 main 을 첫 벌에 올린다: `deploy/ship.sh deploy@<EIP> <병합된 main 해시>` → 서버 `/srv/esg-demo/current/deploy/up.sh`(둘째 이름 없이 — 첫 벌 그대로인지 `smoke.sh <SITE> <FILES>`) |
| D3 | 서버 | 첫 벌 `.env` 에 두 칸: `printf 'DEMO2_SITE_DOMAIN=%s\nDEMO2_FILES_DOMAIN=%s\n' <DEMO2_SITE> <DEMO2_FILES> >> /srv/esg-demo/shared/.env`(값을 한 번만 — 두 번 더하면 마지막 줄이 이긴다) |
| D4 | 서버 | `/srv/esg-demo/current/deploy/up.sh` — `esg-edge` 를 만들고 proxy 를 다시 만든다. 이때 Caddy 가 둘째 이름 둘의 인증서를 받는다. 둘째 벌이 아직 없으니 둘째 이름은 502(정상) |
| D5 | 서버 | `sudo bash /srv/esg-demo/current/deploy/bootstrap-host.sh /srv/esg-demo2` — `/srv/esg-demo2/{releases,shared,backup}` 와 둘째 벌 백업 cron 한 줄(18:45 UTC) |
| D6 | 운영 | `SHIP_ROOT=/srv/esg-demo2 deploy/ship.sh deploy@<EIP> <사용자가 정한 판의 해시>` |
| D7 | 서버 | `/srv/esg-demo2/current/deploy/make-env.sh <DEMO2_SITE> <DEMO2_FILES> /srv/esg-demo2` — 비밀은 새로 만든다(첫 벌과 나누지 않음). `COMPOSE_PROJECT_NAME=esg-demo2`·`PROXY_ROLE=none`·포트 셋이 채워진다 |
| D8 | 운영→서버 | LLM 키: `ENV_PATH=/srv/esg-demo2/shared/.env deploy/put-llm-key.sh deploy@<EIP>`(1절 C12 의 SDK 변수 확인도 그 파일로). mock 으로 먼저 띄우려면 이 줄을 D9 뒤로 |
| D9 | 서버 | `/srv/esg-demo2/current/deploy/up.sh` — proxy 를 빼고 relay 와 함께 띄우고, 첫 벌 proxy 너머 `https://<DEMO2_SITE>/api/readyz` 200 을 본다. 「첫 벌 proxy 가 없다」로 멈추면 D3·D4 |
| D10 | 서버 | `esg_app` 역할 확인(1절 아래 줄을 `dc2` 로) |
| D11 | 서버 | 회사 **하나**·계정: 5절 명령을 `dc2` 로, 비밀번호 파일은 `/srv/esg-demo2/shared/initial-passwords` |
| D12 | 운영 | `deploy/smoke.sh <DEMO2_SITE> <DEMO2_FILES>` 전부 ok · `deploy/smoke.sh <SITE> <FILES>` 도 전부 ok(첫 벌 그대로) |

### 배포는 따로

둘째 벌은 **사용자가 정한 판만** 올린다(데모 고정판). 첫 벌을 올릴 때(`ship.sh` 기본 뿌리 · `/srv/esg-demo/current/deploy/up.sh`)는 둘째 벌의 release·컨테이너·볼륨을 건드리지 않는다. 둘째 벌을 올릴 때는 `SHIP_ROOT=/srv/esg-demo2 deploy/ship.sh …` → `/srv/esg-demo2/current/deploy/up.sh`. 둘째 벌의 `up.sh` 는 proxy 를 만들지 않으니 Caddyfile 을 바꾸는 판(둘째 이름 블록·snippet)은 **첫 벌**에 올라가야 반영된다.
`docker image prune -f`(두 벌의 `up.sh`)는 이름 없는 이미지 가운데 어느 컨테이너도 안 쓰는 것만 지운다. 벌마다 이미지 이름이 다르고(`esg-demo/…`·`esg-demo2/…`), 둘째 벌을 `stop` 으로 내려 두어도 컨테이너가 남아 그 이미지는 지워지지 않는다(`down` 은 하지 않는다).

### 백업

`bootstrap-host.sh /srv/esg-demo2` 가 단 cron 줄: `45 18 * * * DEPLOY_ROOT=/srv/esg-demo2 /srv/esg-demo2/current/deploy/backup-db.sh >> /srv/esg-demo2/backup/backup.log 2>&1`(03:45 KST — 첫 벌 03:30 과 엇갈림). 확인: `crontab -l`(deploy) 에 `backup-db.sh` 줄 둘. 덤프는 `/srv/esg-demo2/backup/db-*.dump` 7개. EBS 스냅숏(DLM)은 같은 볼륨이라 두 벌을 같이 담는다.

### 다운 알림

10절과 같은 꼴로 둘째 이름에 하나 더(같은 SNS 주제 `marcspon-demo-alerts`):
1. `aws route53 create-health-check --profile marcspon --caller-reference marcspon-demo2-$(date +%s) --health-check-config 'Type=HTTPS,FullyQualifiedDomainName=<DEMO2_SITE>,Port=443,ResourcePath=/api/readyz,RequestInterval=30,FailureThreshold=2'` → 나온 `HealthCheck.Id`
2. `aws route53 change-tags-for-resource --profile marcspon --resource-type healthcheck --resource-id <Id> --add-tags Key=Project,Value=marcspon-demo Key=Name,Value=marcspon-demo2-readyz`
3. `aws cloudwatch put-metric-alarm --profile marcspon --region us-east-1 --alarm-name marcspon-demo2-readyz-down --namespace AWS/Route53 --metric-name HealthCheckStatus --dimensions Name=HealthCheckId,Value=<Id> --statistic Minimum --period 60 --evaluation-periods 1 --threshold 1 --comparison-operator LessThanThreshold --treat-missing-data breaching --alarm-actions <주제 ARN> --ok-actions <주제 ARN> --tags Key=Project,Value=marcspon-demo`
주제 ARN 은 `aws sns list-topics --region us-east-1 --profile marcspon` 의 `marcspon-demo-alerts`. 구독은 이미 있다(새로 확인 링크 0). 시험: `aws cloudwatch set-alarm-state --region us-east-1 --alarm-name marcspon-demo2-readyz-down --state-value ALARM --state-reason test`(관리자).

### 스냅숏(판을 띄운 뒤)

① **DB 덤프에 이름 붙여 따로**: 서버에서 `/srv/esg-demo2/current/deploy/backup-db.sh` → 찍힌 덤프를 `install -m 600 /srv/esg-demo2/backup/db-<UTC>.dump /srv/esg-demo2/backup/snapshot-<판 짧은 해시>-<YYYYMMDD>.dump`. `backup-db.sh` 는 `db-*.dump` 만 지우니 `snapshot-*` 는 남는다. 올린 문서(`esg-demo2_storage-data`)는 덤프에 없다 — ②가 담는다.
② **EBS 스냅숏**(사용자 AWS 로그인으로 — 닫힌 목록 `Snap`·`TagOnCreate` 안): `aws ec2 describe-instances --profile marcspon --filters Name=tag:Project,Values=marcspon-demo --query 'Reservations[].Instances[].BlockDeviceMappings[].Ebs.VolumeId'` → `aws ec2 create-snapshot --profile marcspon --volume-id <루트 볼륨> --description "marcspon demo2 <판 짧은 해시> <YYYY-MM-DD>" --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Project,Value=marcspon-demo},{Key=Name,Value=demo2-<판 짧은 해시>}]'`. 지우는 명령은 두지 않는다(걷기는 관리자 — 10절). 컨테이너가 떠 있는 채 찍은 것은 크래시 일관이다 — DB 는 ①의 덤프가 정본.
- 월 비용 어림 **[추정]**: EBS 스냅숏은 쓴 블록만 증분으로 매기고 표준 등급 단가를 GB-월 0.05 USD 안팎으로 보면, 30 GiB 볼륨 가운데 쓴 9 GiB 안팎(디스크 29%)의 첫 스냅숏이 월 0.5 USD 안팎이다. 단가는 확인하지 않았다 — 걸기 전에 https://aws.amazon.com/ebs/pricing/ 의 서울 리전 「Snapshots · Standard」 줄을 확인한다.

### 걸리는 점

- 같은 기계(t4g.large 2 vCPU · 7.8G · 스왑 2G · 디스크 30 GiB): 두 벌이 CPU·메모리·디스크를 나눠 쓴다. 쉰 상태 두 벌 메모리 합은 DM1 리허설 실측(보고 `band-reports/DM1.md`). 두 벌에서 동시에 무거운 실행을 돌리지 않는다.
- 첫 벌을 올릴 때마다 proxy 를 다시 만들어 **둘째 이름도 몇 초 끊긴다**. 데모 직전에는 첫 벌을 올리지 않는다.
- LLM 키 장부가 섞인다(같은 마크스폰 키를 두 벌이 쓴다): 벌별 셈은 각 벌 DB 의 호출 기록 표(`core_llm_call_logs`)로 한다.

### 되돌리기 · 둘째 벌만 내리기

- 둘째 벌만 내리기: `dc2 stop` — **`down -v` 금지**(볼륨·데모 데이터가 지워진다). 다시 켜기 `dc2 start`. 내려가 있는 동안 둘째 이름은 502, 첫 벌은 그대로다(DM1 실측).
- 둘째 이름을 첫 벌 Caddy 에서 빼기: 첫 벌 `.env` 의 `DEMO2_*` 두 줄을 빈 값으로 → 첫 벌 `up.sh`(proxy 가 공유 네트워크 없이 다시 만들어진다). `esg-edge` 네트워크는 남아도 된다.
- 둘째 벌의 판 되돌리기는 7절 「되돌리기」를 `SHIP_ROOT=/srv/esg-demo2`·`/srv/esg-demo2/current/deploy/up.sh`·`dc2` 로.
