# esg-app 개발 문서

이 문서는 저장소를 고치는 사람을 위한 글이다. 지금 코드(api-py · worker-py · parser · SQS 호환 큐 · S3 호환 저장소 · PostgreSQL)가 어떻게 짜여 있고, 어디를 보면 되고, 무엇을 일부러 하지 않았는지를 적는다.
처음 받는 사람이 읽는 글은 저장소 뿌리의 [`README.md`](../README.md)(납품 README)다. 그 글은 띄우는 법과 상태를 짧게 말하고, 자세한 것은 여기를 가리킨다.

이 글은 옛 뿌리 README 의 백엔드 범위를 옮겨 지금 코드에 맞게 고친 것이다. 처음의 TypeScript 서버 뼈대는 걷었다. 지금 서버는 `apps/api-py` 하나다.

글에 나오는 esg-lab 은 공급사의 측정·실험 저장소다. 납품물에 들어 있지 않다. `<esg-lab>` 이 든 명령은 그 저장소가 있을 때만 돈다.

## 띄우는 법

필요한 것: Docker(compose 포함), Node 22 이상과 pnpm 10(`corepack enable`. 웹과 이미지의 웹 빌드), [uv](https://docs.astral.sh/uv/)(Python 테스트를 컨테이너 밖에서 돌릴 때).

```sh
cp .env.example .env                    # 로컬용 설정(가짜 비밀번호뿐이다). 포트가 겹치면 이 파일에서 바꾼다
docker compose up -d --build --wait     # 이미지를 짓고, 전부 준비될 때까지 기다린다
docker compose ps -a                    # 여섯이 running, migrate-py 는 Exited (0) 이면 된다
```

compose 의 서비스는 일곱이다: `parser` `api-py` `migrate-py` `worker-py` `postgres` `storage` `queue`. `migrate-py` 는 한 번 돌고 끝난다(센 곳: `apps/api-py/scripts/readme_audit.py facts` 의 「compose 서비스」 줄).

내릴 때:

```sh
docker compose down        # 컨테이너만 지운다. 데이터(볼륨)는 남는다
docker compose down -v     # 데이터까지 지운다
```

들여다볼 때:

```sh
docker compose logs -f api-py worker-py parser                        # 기록(한 줄 JSON)
docker compose exec postgres psql -U esg_owner -d esg_py              # DB (주인 역할: 전부 보인다)
```

## 요청이 지나는 길

```
 클라이언트(웹 화면, curl)
   │ ① POST /api/auth/login                 ┌──────────────┐  사용자·회사 확인, 토큰 짝 발급   ┌────────────┐
   ├────────────────────────────────────────▶│              │──────────────────────────────────▶│            │
   │ ② POST /api/documents  (Bearer)         │    api-py    │  문서 행(awaiting_upload)        │ PostgreSQL │
   ├────────────────────────────────────────▶│ (Django +    │──────────────────────────────────▶│ (회사 조건 │
   │ ◀── 서명된 올리기 주소 ─────────────────│  django-     │                                   │  과 같은   │
   │ ④ POST /api/documents/{document_id}/confirm   │  ninja)      │  일감(queued). 커밋 뒤 쪽지 ──┐   │  회사 FK)  │
   ├────────────────────────────────────────▶│              │                               │   └────────────┘
   │ ⑥ GET /api/documents/{document_id}     └──────────────┘                               ▼         ▲
   ├────────────────────────────────────────▶       │ head(크기·ETag)                ┌───────────┐     │ ⑤ processing
   │                                                 ▼                                │  queue    │     │   → done / failed
   │ ③ PUT (파일을 직접 올린다)               ┌──────────────┐                        │ (SQS 호환)│     │
   └─────────────────────────────────────────▶│   storage    │◀── get(바이트) ──┐      └───────────┘     │
                                              │  (S3 호환)   │                  │            │ 쪽지      │
                                              └──────────────┘            ┌───────────┐◀────┘           │
                                                                          │ worker-py │─────────────────┘
                                                                          │ (Celery)  │── POST /parse(PDF 바이트) ──▶ parser
                                                                          └───────────┘
```

- 파일은 api-py 를 지나지 않는다. api-py 는 「이 주소로, 이 크기만, 정해진 시간 안에」 올릴 수 있는 서명된 주소를 줄 뿐이다.
- api-py 는 파서를 부르지 않는다. 큐에 쪽지를 넣고, 오래 걸리는 일은 worker-py 가 한다.
- 쪽지에는 회사 id 와 일감 id 만 싣는다. 내용은 DB 와 저장소에 있다.
- 파서는 DB 도 저장소의 키도 모른다. worker-py 가 저장소에서 받은 바이트를 본문으로 보낸다.
- 웹 화면도 같은 api-py 가 같은 출처에서 낸다(아래 「Python API」의 「요청이 지나는 길」).

## 폴더

```
compose.yaml               로컬 구성 전체. 여기부터 읽는다
.env.example               설정 값의 목록과 설명
docker/
  api-py.Dockerfile        api-py · migrate-py · worker-py 가 같이 쓰는 이미지(웹 빌드도 /app/web 에 싣는다)
  parser.Dockerfile        파서의 이미지
  postgres-init.sh         DB 를 처음 세울 때 앱 역할(esg_app)과 DB(esg_py)를 만든다
  elasticmq.conf           로컬 큐(SQS 흉내)의 큐 정의
apps/api-py/               Python API 와 워커(Django + django-ninja + Celery). 아래 「Python API」
apps/web/                  웹 화면(TypeScript, React + Vite). 개발 글은 뿌리 README.md 끝의 웹 블록
services/parser/           PDF 분해 서비스(FastAPI + pypdfium2). services/parser/README.md
packages/                  EDK 공유 키트(ui · common · tailwind-config · typescript-config). 받은 그대로 둔다
scripts/                   verify.sh(게이트), worktree-env.sh, with-build-lock.sh, weekly.sh, check-gates.sh, git-hooks/
infra/                     AWS 인프라의 Terraform 초안(적용한 적 없음). infra/README.md
docs/development.md        이 문서
```

## 읽는 차례

1. `compose.yaml` — 무엇이 뜨고, 누가 누구를 기다리고, 어떤 환경 변수를 받는가.
2. `.env.example` — 바꿀 수 있는 값.
3. `docker/api-py.Dockerfile` — 이미지를 어떻게 짓는가(단계 셋, 잠금 파일대로 설치, 루트가 아닌 사용자).
4. `apps/api-py/esgapi/config/api.py` → `<모듈>/service/apis/` → `<모듈>/service/services/` — 요청 하나가 지나는 길.
5. `apps/api-py/esgapi/core/auth/bearer.py` → `apps/api-py/esgapi/core/permissions.py` → `apps/api-py/esgapi/core/isolation/` — 누가 무엇을, 어느 회사 것을.
6. `apps/api-py/esgapi/reconcile/tasks.py` → `apps/api-py/esgapi/core/service/services/jobs.py` — 큐와 워커.
7. `apps/api-py/tests_integration/` — 위의 것들이 떠 있는 컨테이너에서 실제로 그렇게 도는지.

## 개념마다 어디를 보면 되는가

| 개념 | 한 줄 설명 | 보는 곳 |
|---|---|---|
| 이미지 | 여러 단계로 지어 실행에 필요한 것만 담는다. 루트가 아닌 사용자로 돈다. `.env` 와 테스트는 `.dockerignore` 로 막는다 | `docker/api-py.Dockerfile`, `docker/parser.Dockerfile`, `.dockerignore` |
| 같은 이미지, 다른 명령 | api-py(gunicorn), migrate-py(`migrate`), worker-py(Celery)는 한 이미지다 | `compose.yaml` 의 `command` |
| 설정 | 환경 변수로만 받는다. 뜨기 전에 검사하고 빠진 것을 전부 모아 말하며 멈춘다 | `apps/api-py/esgapi/config/env.py` |
| 마이그레이션 | 앱 기동과 따로 한 번 돈다. 표를 바꿀 수 있는 주인 역할로 돈다. 앱 역할에는 그 권한이 없다 | `compose.yaml` 의 `migrate-py`, `apps/api-py/esgapi/config/settings/migrate.py` |
| 살아 있음 `/api/healthz` | 프로세스가 답하는가. DB 가 죽어도 200 | `apps/api-py/esgapi/config/api.py` |
| 준비됨 `/api/readyz` | DB 에 닿는가. 닿지 못하면 503 | `apps/api-py/esgapi/config/api.py`, `compose.yaml` 의 `healthcheck` |
| 기동 순서 | 기대는 것이 준비될 때까지 기다린 뒤 뜬다 | `compose.yaml` 의 `depends_on` |
| 종료 신호 | SIGTERM 을 받으면 gunicorn 은 받던 요청을, 워커는 하던 태스크를 마치고 내려간다 | `apps/api-py/gunicorn.conf.py`, `compose.yaml` 의 `stop_grace_period` |
| 인증 | 로그인이 낸 Bearer 토큰. 회사 경로는 Bearer 를 먼저 보고, 머리가 없으면 옛 교환 쿠키를 본다 | `apps/api-py/esgapi/core/auth/bearer.py` |
| 권한 | 동작(operationId)마다 고객사 사용자 · 운영 관리자 · 둘 다 가운데 하나 | `apps/api-py/esgapi/core/permissions.py` |
| 회사 격리 | 조회의 조건은 selector 가 회사 id 를 인자로 받아 건다. 조건을 빼먹은 조회는 기본 매니저가 거절하고, 남의 회사 행을 가리키는 외래 키는 DB 가 거절한다 | `apps/api-py/esgapi/core/isolation/` |
| 재시도 | 잠깐의 실패는 간격을 두고 다시 하고, 시도 상한에서 `failed`. 다시 해도 소용없는 실패는 바로 `failed` | `apps/api-py/esgapi/reconcile/tasks.py`, `apps/api-py/esgapi/core/calc/jobs.py` |
| 다시 부를 수 있는 올림 확인 | 끝나지 않은 일감의 쪽지를 다시 넣는다. 중복은 워커의 잡기가 거른다 | `apps/api-py/esgapi/core/service/services/documents.py`, `apps/api-py/esgapi/core/service/services/jobs.py` |
| 서명된 주소 | 클라이언트가 저장소에 직접 올린다. 안에서 보는 주소와 바깥에서 보는 주소를 따로 받는다 | `apps/api-py/esgapi/core/resources/storage.py` |
| 관측 | 요청마다 `X-Request-ID`, 한 줄 JSON 기록(칸은 닫힌 목록) | `apps/api-py/esgapi/core/observability/` |

## AWS 의 무엇에 대응하는가

| compose 의 이것 | AWS 에서는 | 달라지는 점 |
|---|---|---|
| `api-py` | ECS 서비스(로드밸런서 ALB 뒤) | 바깥 요청은 ALB 가 받는다. HTTPS 는 ALB 에서 끝난다 |
| `worker-py` | ECS 서비스(로드밸런서 없음) | 일은 큐에서 꺼내 온다 |
| `parser` | worker-py 곁의 컨테이너 | `PARSER_URL` 만 바뀐다 |
| `migrate-py` | 배포 때 한 번 도는 ECS 태스크(같은 이미지) | 새 버전을 올리기 전에 돌리고, 성공해야 서비스를 바꾼다 |
| `postgres` | Aurora PostgreSQL | 주소와 비밀번호만 바뀐다. 앱 역할(`esg_app`)은 DB 를 만든 뒤 한 번 만든다 |
| `queue` | SQS | 큐는 인프라가 만든다. 앱은 큐를 만들지 않는다 |
| `storage` | S3 버킷 | `S3_ENDPOINT`·`S3_PUBLIC_ENDPOINT` 를 비우고 `S3_FORCE_PATH_STYLE=false` |
| `AWS_ACCESS_KEY_ID` 등 | ECS 태스크 역할(IAM) | 키를 넣지 않는다. 역할이 권한을 준다 |
| `environment:` 와 `.env` | 태스크 정의의 환경 변수. 비밀은 Secrets Manager 나 Parameter Store | 비밀 값이 파일로 돌아다니지 않는다 |
| `healthcheck:` | ALB 대상 그룹 → `/api/readyz`, 컨테이너 → `/api/healthz` | 둘을 나눈다 |
| `stop_grace_period:` | 태스크 정의의 `stopTimeout` | 배포·축소 때 SIGTERM 뒤 기다려 주는 시간 |
| 표준 출력의 기록 | CloudWatch Logs | 앱은 표준 출력에 한 줄씩 쓰면 된다 |

`infra/` 의 Terraform 은 적용한 적이 없다. 처음의 TypeScript 서버 뼈대 시절 구성을 기준으로 쓴 것이라 api-py · worker-py · SQS 에 맞게 다시 써야 한다(`infra/README.md`).

## 고른 도구와 바꾸는 법

| 자리 | 지금 | 바꾸려면 |
|---|---|---|
| 서버 틀 | Django + django-ninja | 경로는 `<모듈>/service/apis/` 에 있다. 업무 규칙(`calc/`, 엔진)은 틀을 모른다 |
| 큐 | Celery + SQS(로컬은 ElasticMQ) | `apps/api-py/esgapi/config/celery.py`, `apps/api-py/esgapi/core/resources/queue.py` |
| DB 접근·마이그레이션 | Django ORM + psycopg | `<모듈>/models.py`·`<모듈>/migrations/` |
| 저장소 SDK | boto3 | `apps/api-py/esgapi/core/resources/storage.py` |
| 로컬의 S3 호환 저장소 | Versity S3 Gateway | `compose.yaml` 의 `storage` 서비스만 |
| 파서 | FastAPI + pypdfium2 | `services/parser/README.md` |
| Python 패키지 | uv(잠금 파일 `uv.lock`) | `apps/api-py/pyproject.toml`, `services/parser/pyproject.toml` |
| 테스트 | pytest, vitest | 아래 「테스트 층」 |

## 확인하는 법

```sh
scripts/verify.sh --fast     # 빠른 게이트: 컨테이너 없이 도는 단계만. 끝 줄 VERIFY_FAST=PASS
scripts/verify.sh            # 전량: 깨끗한 상태에서 이미지를 짓고 띄워 업무·보안·통합 층까지. 끝 줄 VERIFY=PASS
scripts/verify.sh --plan     # 돌리지 않고 단계 이름만 (--fast --plan 은 빠른 게이트의 것)
apps/web/scripts/verify.sh   # 웹의 게이트
```

전량은 같은 compose 프로젝트의 컨테이너와 볼륨(데이터)을 지우고 시작하고, 끝나면 다시 지운다(`scripts/verify.sh` 의 0·8 단계). 손으로 넣은 데이터도 사라진다.

단계마다 `EXIT=` 줄이 나온다. 단계 목록과 잠금(전량은 한 번에 하나, 이미지 짓기는 기계에 하나)의 규칙은 `scripts/verify.sh` 의 머리 글이 정본이다. `VERIFY_FAST=PASS` 는 완료가 아니다: DB 에 닿는 층은 전량에서만 돈다.

게이트나 커밋 훅(`scripts/git-hooks/pre-commit`)을 고쳤으면 `scripts/check-gates.sh` 를 돌린다.

## 워크트리에서 띄우기

```sh
scripts/worktree-env.sh <이름>     # .env 를 만든다: COMPOSE_PROJECT_NAME=esg-app-<이름>, 포트는 이름에서 정해지는 겹치지 않는 값
scripts/with-build-lock.sh docker compose build && docker compose up -d --wait

# 다 쓴 뒤: 컨테이너·볼륨과 그 워크트리가 만든 이미지를 지운다
docker compose down -v && docker image ls -q --filter 'reference=esg-app-<이름>/*' | xargs docker image rm
```

`compose.yaml` 과 `scripts/verify.sh` 는 그 `.env` 의 값을 따른다. 아래 `curl` 예의 포트도 `.env` 의 `API_PY_PORT` 로 바꿔 쓴다.

## 주 1회 정기 실행

병합 게이트에 넣지 않는 무거운 확인 둘(기본값 판 통합, calc 변이 테스트)을 주 1회 손으로 돌린다.

```sh
scripts/weekly.sh          # main 을 저장소 밖 사본에 떠서 돌린다
scripts/weekly.sh --plan   # 무엇을 부르는지만 찍는다
```

자세한 것은 `scripts/weekly.sh` 의 머리 글.

## 일부러 안 한 것

- **CI.** `scripts/verify.sh` 가 CI 가 돌릴 명령의 묶음이다.
- **인프라 적용.** `infra/` 는 초안이다(위).
- **비밀 관리 도구.** 로컬의 가짜 값은 `.env` 에 있다.
- **올린 파일을 지우는 길과 보존 기간**, 멀티파트 올리기, 바이러스 검사.
- **운영자 화면**(Django admin 을 켜지 않았다).

## 프로덕션에서 달라지는 것

- **주소와 비밀.** 환경 변수의 값만 바뀐다. 비밀은 비밀 관리 도구에서 주입되고, 저장소·큐 접근은 키가 아니라 역할로 한다.
- **HTTPS.** 로드밸런서에서 끝난다. DB 연결에도 TLS 를 켠다(`DATABASE_URL_PY` 의 값).
- **재시작.** ECS 는 죽은 컨테이너를 스스로 다시 띄운다. compose 에서는 `storage`·`queue`·`api-py` 에만 다시 띄움을 달았다(통합 시험이 워커와 파서를 일부러 멈춘다).
- **여러 벌.** api-py 와 worker-py 가 둘 이상 떠도 일감은 한 번만 끝나게 썼다(워커의 잡기가 행을 잠그고 상태·임대를 본다). 둘 이상 띄워 시험하지는 않았다.
- **멈춘 일감.** 하드 시간 제한이나 예상 못 한 예외로 `processing` 에 남은 일감은 사람이 `requeue_jobs --tenant` 를 돌릴 때까지 머문다. 주기적으로 도는 장치가 없다.
- **올리는 파일의 제한.** 크기는 서명 조건과 올림 확인 두 곳에서 본다. 파일 종류는 파서가 본다.
- **마이그레이션의 주인 역할.** 로컬에서는 superuser 다. Aurora 에서는 superuser 가 아닌 주인 역할을 쓴다.
- **이미지 받기.** Docker Hub 는 로그인하지 않은 요청 수를 제한한다. CI 와 배포에서는 로그인하거나 미러를 쓴다.

## 파서의 문서 분해 (services/parser)

파서는 PDF 를 섹션·문단·표의 JSON 과 글자 자리로 분해한다. 분해기 `services/parser/docparse/` 는 esg-lab `py/docparse` 를 pdfium 엔진(pypdfium2) 하나만 남겨 가져온 것이고, 지금은 이 저장소가 정본이다.

- **약속**: `POST /parse`, `Content-Type: application/pdf`, 본문이 PDF 바이트 → `{"document", "charPlaces"}`. 두 산출은 스키마로 검사한 뒤에만 나간다. 거절은 `{"detail": {"code", "message"}}` 의 갈래로 온다(4xx 는 다시 해도 같다, 5xx 는 다시 해 볼 만하다).
- 주소를 받아 파서가 내려받던 옛 약속(JSON 본문)은 걷었다. 지금은 415 다.
- 상한(본문 크기·쪽 수·줄 서기·시간)과 기본값은 `services/parser/README.md` 의 「상한 (결함 D4, 밴드 PX)」, 괘선 표 크기의 상한은 「분해 안의 상한 (밴드 PX2)」 에 있다. 여기에 베껴 적지 않는다.
- 분해는 한 번에 한 건, 자식 프로세스 하나에서 돈다. PDF 는 한 번만 연다. 그동안에도 `/healthz` 는 답한다(「한 번에 한 건, 자식 프로세스 하나」).
- 부르는 쪽은 worker-py 다(아래 「Python API」의 「파서」). 기다리는 시간의 차례는 「파서의 시간 상한 < 부르는 쪽 `PARSER_TIMEOUT_MS` < Celery 의 소프트·하드 제한 < 일감의 임대 < 큐의 visibility」 다. 값은 `apps/api-py/esgapi/config/env.py` 의 기본값이 정본이고 `apps/api-py/esgapi/config/tests/test_env.py` 가 그 차례를 잰다.

```sh
uv run --project services/parser --frozen pytest -q services/parser     # 파서의 테스트
```

계약의 전부, 가져온 파일의 대응표, 라이선스 기록은 `services/parser/README.md`.

## Python API (apps/api-py)

이 저장소의 서버다. Python(Django + django-ninja)이고, 업무 모듈이 같은 뼈대로 붙는다. 모듈 폴더는 여덟이다(`config` `core` `greenwash` `inventory` `organization` `reconcile` `reference` `user`. 센 곳: `scripts/readme_audit.py facts` 의 「모듈 폴더」 줄).

```
POST /api/auth/login ──▶ 토큰 짝(access 30분 · refresh 7일) ──▶ Authorization: Bearer <access> ──▶ 회사 경로
   (username·비밀번호, 회사 서브도메인)                              권한 표(operationId 마다)        조회마다 회사 조건
```

- 우리는 사용자의 비밀번호를 받는다(로그인). 해시와 실패 셈·잠금은 `user` 모듈에 있다. 길이와 잠금의 수는 `core/auth/tokens.py` 의 상수다.
- 주체는 둘이다: 운영 관리자(회사 없음)와 고객사 사용자(회사 하나). 무엇을 할 수 있는지는 권한 표 `core/permissions.py` 가 operationId 마다 가른다.
- 회사·사용자 id 는 **토큰(또는 옛 교환 쿠키)에서만** 온다. 요청 본문·쿼리·헤더로 받는 길이 없다.
- 옛 길: EDK 가 서명한 토큰을 우리 세션 쿠키로 바꾸는 교환(`POST /auth/exchange`)이 아직 남아 있다. 회사 경로는 Bearer 머리가 없을 때만 그 쿠키를 본다. 쿠키 이름과 꼴은 `core/tenancy/session.py`·`core/tenancy/middleware.py` 에 있다.
- DB 는 같은 postgres 서버의 **별도 데이터베이스** `${POSTGRES_DB}_py` 다.

### 띄우는 법

```sh
# 교환(옛 길)이나 통합 테스트를 쓸 때만: 연습용 키 쌍(apps/api-py/.dev-keys, git 밖)의 공개키를 준다. .env 의 같은 이름보다 앞선다
export EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run python scripts/dev_edk.py public-key)"
docker compose up -d --build --wait     # api-py 는 migrate-py 가 끝난 뒤에 뜬다
```

`export` 없이 띄워도 뜬다. 로그인(Bearer) 길은 EDK 키를 쓰지 않는다. 그때 교환은 `.env.example` 의 가짜 키라 어떤 토큰도 통하지 않는다.

**이미 DB 볼륨이 있던 사람은** `docker compose down -v` 로 볼륨을 지우고 다시 띄워야 할 수 있다. `${POSTGRES_DB}_py` 를 만드는 `docker/postgres-init.sh` 는 데이터 폴더가 비어 있을 때 한 번만 돈다.

### 손으로 따라가기

회사 등록부터 Scope 3 까지 한 흐름이다(`jq` 가 필요하다). 비밀번호는 명령이 묻는 값을 쓴다.

```sh
API_PY=http://localhost:18081/api          # .env 의 API_PY_PORT. API 의 경로는 전부 /api 아래다

# 1. 회사를 등록한다(주인 역할의 설정에서 도는 seed_company. 같은 값으로 두 번 돌려도 그대로)
docker compose run --rm -e DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate migrate-py \
  python manage.py seed_company --name '가 회사' --business-licence-number 000-00-00001 --subdomain tenant-a

# 2. 그 회사의 고객사 사용자를 만든다. 비밀번호를 두 번 묻는다. 만든 계정은 첫 로그인 뒤 비밀번호를 바꿔야 한다
docker compose exec api-py python manage.py create_user --company tenant-a --username kim --name 김담당

# 3. 로그인한다 → access·refresh 짝. isInitial 이 true 다
read -rs PW
curl -s -X POST $API_PY/auth/login -H 'content-type: application/json' \
  -d "$(jq -n --arg p "$PW" '{companySubdomain:"tenant-a", username:"kim", password:$p}')" > /tmp/esg-login.json
ACCESS=$(jq -r .access /tmp/esg-login.json)

# 4. 비밀번호를 바꾼다(첫 로그인 뒤에는 이것과 /users/me 만 열린다) → 새 짝
read -rs NEW_PW
curl -s -X POST $API_PY/users/me/password -H "authorization: Bearer $ACCESS" -H 'content-type: application/json' \
  -d "$(jq -n --arg c "$PW" --arg n "$NEW_PW" '{currentPassword:$c, newPassword:$n}')" > /tmp/esg-login.json
ACCESS=$(jq -r .access /tmp/esg-login.json)
H="authorization: Bearer $ACCESS"

# 5. 사업장
curl -s -H "$H" $API_PY/users/me
curl -s -H "$H" -X POST $API_PY/sites -H 'content-type: application/json' -d '{"name":"본사"}'
curl -s -H "$H" $API_PY/sites

# 6. 인벤토리 계산. 저장하지 않는다(아래 「인벤토리 계산」)
curl -s -H "$H" -H 'content-type: application/json' $API_PY/inventory/calc -d '{
  "gwpSetId": "kr-ets-decree-annex2",
  "rows": [{"id": "r1", "orgUnit": "site-1", "period": "2025", "sourceType": "stationary_combustion",
            "fuel": "diesel", "sector": "manufacturing_construction",
            "parameterTiers": {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": 2},
            "amount": "1000", "unit": "L"}]
}'
# → rows[0] 의 status "ok" 와 co2e(tCO2eq, 십진 문자열, 반올림 없음), aggregation.total

# 7. 기준정보. 패키지에 실린 사본과 대응표를 먼저 들인다(주인 역할의 컨테이너로 돈다. 아래 「기준정보」)
docker compose run --rm migrate-py python manage.py import_factors
curl -s -H "$H" $API_PY/reference/sources
curl -s -H "$H" "$API_PY/reference/factors?limit=5"

# 8. Scope 3 후보 추리기. 패키지 사본에는 Scope 3 후보가 없다 — 전체 계수 표를 들인 DB 에서만 후보가 나온다
curl -s -H "$H" -H 'content-type: application/json' $API_PY/inventory/scope3/shortlist -d '{
  "row": {"itemName": "노트북 구매", "unit": "대"}, "category": 1, "keywords": ["computer", "laptop"]
}'

# 9. 거절되는 것들. 갈래마다 code 가 다르다
curl -s $API_PY/sites                                         # 401 NO_SESSION (Bearer 도 쿠키도 없다)
curl -s -H 'authorization: Bearer x.y.z' $API_PY/sites        # 444 TOKEN_NOT_VALID
```

다른 회사(`tenant-b`)를 등록하고 그 회사의 사용자로 로그인하면 `GET /sites` 는 빈 목록이다. 조회는 회사 id 를 조건으로 건다(아래 「회사 격리」).

운영 관리자는 `create_user --admin --username <아이디> --name <이름>` 으로 만들고, `companySubdomain` 없이 로그인한다. 운영 관리자는 고객사 사용자 관리(`/users`)만 하고, 회사 경로에는 401 `COMPANY_REQUIRED` 다.

API 문서(브라우저): `http://localhost:18081/api/docs`. 계약(JSON): `/api/openapi.json`.

### 경로 목록

`generated/openapi.json` 의 경로는 32, 동작은 37 이다(센 곳: `scripts/readme_audit.py facts` 의 「OpenAPI 의 경로와 동작」 줄). 계약 문서의 paths 키에는 접두가 없고 servers 의 /api 하나가 접두를 말한다. 그래서 호스트에서 부르는 주소는 `http://localhost:<API_PY_PORT>/api/<경로>` 다.

라우터는 `config/api.py` 에 일곱이 걸려 있다: `user`·`organization` 은 `/`, `inventory`·`reference` 는 `/<모듈 이름>`, `core` 의 문서는 `/documents`, 실행은 `/runs`, `greenwash` 는 /greenwash 아래. 「인증」 칸의 「회사」는 `auth=[company_scoped_auth_or_next, session_cookie]`(Bearer 먼저, 없으면 옛 쿠키)이고 주체는 고객사 사용자여야 한다. 「501」은 꼴만 있고 몸이 없는 동작이다(인증과 권한을 지난 뒤 501 `NOT_IMPLEMENTED`).

| 메서드 | 경로 | 모듈 | 인증과 주체 | 몸 |
|---|---|---|---|---|
| GET | `/healthz` | `config` | 없음 | 있음. DB 를 건드리지 않는다 |
| GET | `/readyz` | `config` | 없음 | 있음. DB 에 닿는지만 본다 |
| POST | `/auth/login` | `user` | 없음(username·비밀번호) | 있음. 토큰 짝 |
| POST | `/auth/refresh` | `user` | 없음(본문의 refresh) | 있음. 새 짝(옛 refresh 는 죽는다) |
| POST | `/auth/revoke` | `user` | 없음(본문의 refresh) | 있음. 그 refresh 의 계보를 끊는다 |
| POST | `/auth/exchange` | `user` | 없음(EDK 토큰. 옛 길) | 있음. 세션 쿠키를 내준다 |
| POST | `/auth/logout` | `user` | 없음 | 있음. 쿠키를 지운다(옛 길) |
| GET | `/me` | `user` | 옛 쿠키 세션만 | 있음. 세션의 내용 |
| GET | `/users/me` | `user` | Bearer. 두 주체 | 있음 |
| POST | `/users/me/password` | `user` | Bearer. 두 주체 | 있음. 새 짝, 다른 refresh 는 끊는다 |
| GET | `/users` | `user` | Bearer. 운영 관리자 | 있음 |
| POST | `/users` | `user` | Bearer. 운영 관리자 | 있음. 고객사 사용자 만들기 |
| POST | `/users/{user_id}/password-reset` | `user` | Bearer. 운영 관리자 | 있음 |
| GET | `/sites` | `organization` | 회사 | 있음 |
| POST | `/sites` | `organization` | 회사 | 있음. `sites` 에 한 행 |
| GET | `/reference/sources` | `reference` | 회사 | 있음(읽기) |
| GET | `/reference/factors` | `reference` | 회사 | 있음(읽기) |
| POST | `/reference/assemble` | `reference` | 회사 | 있음(읽어서 조립만) |
| POST | `/reference/assemble-electricity` | `reference` | 회사 | 있음(읽어서 조립만) |
| POST | `/inventory/calc` | `inventory` | 회사 | 있음. 저장하지 않는다 |
| POST | `/inventory/scope3/shortlist` | `inventory` | 회사 | 있음. 저장하지 않는다 |
| POST | `/inventory/scope3/classify` | `inventory` | 회사 | 있음. 떠 있는 서버에서는 늘 503 |
| POST | `/documents` | `core` | 회사 | 있음. `reportYear`·`previousDocumentId` 에 값이 있으면 501 |
| GET | `/documents` | `core` | 회사 | 501 |
| POST | `/documents/{document_id}/confirm` | `core` | 회사 | 있음 |
| GET | `/documents/{document_id}` | `core` | 회사 | 있음 |
| GET | `/documents/{document_id}/versions` | `core` | 회사 | 501 |
| POST | `/runs` | `core` | 회사 | 501 |
| GET | `/runs` | `core` | 회사 | 501 |
| GET | `/runs/{run_id}` | `core` | 회사 | 501 |
| GET | `/runs/{run_id}/files/{name}` | `core` | 회사 | 501 |
| GET | `/greenwash/runs/{run_id}/result` | `greenwash` | 회사 | 501 |
| GET | `/greenwash/runs/{run_id}/review` | `greenwash` | 회사 | 501 |
| PUT | `/greenwash/runs/{run_id}/review` | `greenwash` | 회사 | 501 |
| GET | `/greenwash/compare` | `greenwash` | 회사 | 501 |
| GET | `/greenwash/runs/{run_id}/report` | `greenwash` | 회사 | 501 |
| GET | `/greenwash/terms/default` | `greenwash` | 회사 | 있음 |
| POST | `/translation/glossary/read` | `translation` | 회사 | 있음. 본문은 xlsx 바이트 그대로, 읽은 짝도 거절도 200(`ok` 판별), 저장하지 않는다(TR3a) |
| GET | `/translation/glossary/template` | `translation` | 회사 | 있음. 빈 용어집 양식 xlsx(TR3a) |
| GET | `/translation/batches` | `translation` | 회사 | 있음. 묶음 목록 한 쪽((문서, 묶음) 한 줄 — `documentId`·`state`·`mine`·`limit`·`offset`, 옵션·결과 본문 0, `inputKind`·`latest.flowId`(TRS3))(TR3b) |
| GET | `/translation/documents/{document_id}/batches/{batch_key}` | `translation` | 회사 | 있음. 묶음 하나(목록 줄 + `truncated`, 없는 묶음 404, `inputKind`·`latest.flowId`(TRS3))(TR3b) |
| GET | `/translation/documents/{document_id}/batches/{batch_key}/archive` | `translation` | 회사 | 있음. [모두 받기] zip — 끝난 파트의 자동수정 병기본(`<part>-<이름>`), 머리 `X-Archive-Missing`, 0 이면 409 `NO_FINISHED_PARTS`(TR3b) |
| GET | `/translation/documents/{document_id}/pages` | `translation` | 회사 | 있음. 올린 docx·txt 의 [PAGE n] 최댓값(그리드 표시용 — 못 세면 `pageCount` null, 없는 문서 404)(TRP6) |
| GET | `/translation/runs/{run_id}/layout` | `translation` | 회사 | 있음. PDF 실행의 블록·좌표 결과 translation.layout@1(워드 실행·없는 실행 404, 안 끝남 409)(TRS3) |

`reconcile` 은 라우터도 경로도 없다.

영문번역 실행의 옵션(`POST /runs` 의 `options`)은 흐름이 등록한 상한 256KiB(`translation/apps.py` 의 `max_options_bytes`, 다른 문서 흐름은 기본 16KiB)까지 받는다 — 넘으면 400 `INVALID_OPTIONS`(TR3a).

`operationId` 는 37 전부 경로 장식자에 `operation_id=` 로 손으로 적은 `<모듈>_<동작>` 이다(교환·`/me`(지금 `user`)와 사업장(지금 `organization`)은 옛 모듈 이름을 딴 `accounts_*` 그대로다). 표는 `config/tests/test_api_contract.py` 에 있고, 권한 표 `core/permissions.py` 와 어긋나면 `core/tests/test_permissions.py` 가 잡는다. 경로를 더하면 두 곳에 한 줄씩 더한다.

### 오류의 꼴과 code

오류 응답의 꼴은 하나다(`core/exceptions.py`):

```
{"error": {"code": "<대문자 이름>", "message": "<문장>", "fields": <칸별 문장 | null>, "legacyCode": <옛 소문자 이름 | null>}}
```

`code` 는 대문자 snake 이고 프론트는 `code` 로 가른다. `legacyCode` 는 옛 소문자 이름이고 한 판만 싣는다. 모듈은 상태 코드도 대문자 글자도 모른다: 오류의 종류와 소문자 이름만 말하고, 종류 → 상태 코드는 `config/api.py` 의 `HTTP_STATUS` 가, 소문자 → 대문자는 `ErrorDetail` 이 바꾼다. 아래 표의 `code` 는 대문자로 적는다.

| 상황 | 상태 | `code` |
|---|---|---|
| 요청의 꼴이 틀렸다(모르는 칸 포함). `fields` 에 칸마다 까닭 | 422 | `VALIDATION_ERROR` |
| 본문이 JSON 이 아니다 등 바닥의 거절 | 400 | `BAD_REQUEST` |
| Bearer 도 쿠키도 없다 | 401 | `NO_SESSION` |
| Bearer 가 필요한 경로(`/users`…)에 머리가 없다 | 401 | `NO_TOKEN` |
| Bearer 토큰이 틀렸다(꼴·서명·만료·aud), refresh 를 쓸 수 없다 | 444 | `TOKEN_NOT_VALID` |
| 회사 경로에 운영 관리자의 Bearer | 401 | `COMPANY_REQUIRED` |
| 첫 로그인·초기화 뒤 비밀번호를 아직 안 바꿨다 | 403 | `PASSWORD_CHANGE_REQUIRED` |
| 로그인 정보가 틀렸다 / 5번 실패해 잠겼다 | 401 | `INVALID_CREDENTIALS` / `ACCOUNT_LOCKED` |
| 권한 표가 그 주체를 받지 않는다 | 403 | `FORBIDDEN` |
| 옛 쿠키 세션이 만료·변조·꼴 틀림 | 401 | `SESSION_EXPIRED` · `SESSION_BAD_SIGNATURE` · `SESSION_MALFORMED` |
| 교환(옛 길)의 거절 | 401 · 403 · 409 | `MALFORMED` `BAD_ALGORITHM` `BAD_SIGNATURE` `EXPIRED` `WRONG_AUDIENCE` `WRONG_ISSUER` `BAD_CLAIMS` · `UNKNOWN_TENANT` `USER_INACTIVE` · `USERNAME_CONFLICT` |
| 없는 경로 / 그런 문서가 없다(다른 회사의 것도 같은 답) | 404 | `NOT_FOUND` |
| 꼴만 있는 동작 | 501 | `NOT_IMPLEMENTED` |
| 본문이 상한(2.5MB, Django 기본값을 `config/settings/base.py` 에 그대로 적은 것)을 넘는다 | 413 | `BODY_TOO_LARGE` |
| DB 에 닿지 못함 | 503 | `UNAVAILABLE` |
| 예상 못 한 예외(본문은 고정 문장) | 500 | `INTERNAL_SERVER_ERROR` |

모듈이 더하는 갈래(자세한 것은 모듈의 절):

| 상황 | 상태 | `code` |
|---|---|---|
| 사용자 관리: username 이 이미 있다 / 회사가 없다 / 사용자가 없다 / 회사를 고를 수 없다 / 새 비밀번호를 쓸 수 없다 | 409 / 404 / 404 / 400 / 400 | `USERNAME_TAKEN` / `COMPANY_NOT_FOUND` / `USER_NOT_FOUND` / `COMPANY_AMBIGUOUS` / `PASSWORD_REJECTED` |
| 기준정보의 조립: 기준정보가 들어와 있지 않다 / 대응표가 둘 이상 | 503 / 409 | `REFERENCE_NOT_LOADED` / `MAPPING_AMBIGUOUS` |
| 인벤토리 계산: 실어 온 표가 검사에 걸림 / 1,000행 초과 | 400 / 413 | `INVALID_TABLES` / `TOO_MANY_ROWS` |
| Scope 3: `license` 의 값이 틀림 / `rowId` 가 겹침 / 묶음 20 초과 / 생성 모델 경로가 서버에 없다 | 400 / 400 / 413 / 503 | `INVALID_LICENSE` / `DUPLICATE_ROW_ID` / `TOO_MANY_GROUPS` / `LLM_NOT_CONFIGURED` |
| 문서 만들기: 크기가 상한(`MAX_UPLOAD_BYTES`)을 넘는다 / 회사 id 가 저장소 키의 토막이 될 꼴이 아니다 | 413 / 409 | `UPLOAD_TOO_LARGE` / `TENANT_ID_NOT_STORABLE` |
| 올림 확인: 저장소에 아직 없다 / 크기가 다르다 | 409 | `NOT_UPLOADED` / `UPLOAD_SIZE_MISMATCH` |
| 올림 확인: 저장소가 거절 / 닿지 못함 / 저장소 설정이 없다 | 503 | `STORAGE_DENIED` / `STORAGE_UNAVAILABLE` / `STORAGE_UNCONFIGURED` |

「못 했다」가 오류가 아닌 답인 자리가 둘 있다: 기준정보의 조립은 `200` 에 `{ok: false, failure}`, 인벤토리 계산의 실패한 행은 `200` 안의 `status: "failed"`.

### 환경 변수

`config/env.py` 가 읽는 키는 39 이다(센 곳: `scripts/readme_audit.py facts` 의 「config/env.py 가 읽는 키」 줄). 필수 여섯 가운데 하나라도 빠지면 서버가 뜨기 전에 빠진 것을 전부 모아 알린다. 선택 키는 빈 값(빈칸뿐인 값 포함)을 「없음」으로 읽는다. 값은 여기 적지 않는다: 로컬용 가짜 값과 설명은 `.env.example`, 컨테이너에 넣는 꼴은 `compose.yaml` 의 `api-py`, 기본값은 `config/env.py` 의 데이터클래스가 정본이다.

| 이름 | 필수인가 | 누가 읽는가 |
|---|---|---|
| `DATABASE_URL_PY` | 필수 | `config/settings/base.py` 의 DB 연결(앱 역할 `esg_app`) |
| `EDK_JWT_PUBLIC_KEY` · `EDK_JWT_AUDIENCE` · `EDK_JWT_ISSUER` | 필수 | `user/service/utils/tokens.py`(옛 교환의 EDK 토큰 검증) |
| `SESSION_SECRET` | 필수. 32바이트 이상 | `core/auth/tokens.py`(access·refresh 서명), `core/tenancy/session.py`(옛 쿠키). `local-only-` 로 시작하는 값이면 기동 때 경고만 하고 막지 않는다(값은 찍지 않는다). `compose.yaml` 에 기본값이 없다(`${SESSION_SECRET:?…}` — `.env` 에 없으면 compose 가 멈춘다) |
| `SESSION_TTL_SECONDS` | 필수. 0보다 큰 정수 | 옛 쿠키 세션의 수명. 토큰의 수명은 코드 상수다(`core/auth/tokens.py`) |
| `LLM_OPENAI_API_KEY` · `LLM_ANTHROPIC_API_KEY` · `LLM_GEMINI_API_KEY` | 선택 | `core/llm/setup.py`. 없는 공급사의 모델을 부르면 `LiveSetupError` |
| `LLM_MODELS_FILE` | 선택. 없으면 패키지에 실린 `core/llm/data/models.json` | `core/llm/setup.py` |
| `LLM_LOG_SINK` | 선택. `memory`·`jsonl`·`db` | `core/llm/setup.py` |
| `LLM_JSONL_PATH` | `LLM_LOG_SINK` 가 `jsonl` 일 때만 필수 | `core/llm/setup.py` |
| `LLM_RPM` | 선택. 0보다 큰 수 | `core/llm/setup.py` |
| `LLM_RUN_MODE` | 선택. `mock`(기본·빈 값)·`live`. 그 밖은 기동 실패. `live` 면 `LLM_LOG_SINK=db`·키 하나 이상·`LLM_RUN_MAX_USD` 가 있어야 뜬다 | `runs/context.py`(실행기가 실제 공급사의 키를 싣는가 — LV1). 아래 「실 공급사 전환 점검표」 |
| `LLM_RUN_MAX_USD` | `LLM_RUN_MODE=live` 면 필수. 0보다 큰 유한한 수(잘못된 값이면 **mock 에서도** 기동 실패) | `runs/context.py`. live 실행 하나(앞 시도 포함)의 호출 비용 상한 — 넘으면 공급사 전에 `budget_exceeded` |
| `TRANSLATION_RUN_MAX_USD` | 선택. 0보다 큰 수, 기본 5 | `translation/apps.py` 가 끼움에 꽂는다. 영문번역 실행 하나의 호출 비용 위끝(dry-run)이 넘으면 공급사 전에 결과 `over_budget`(`MARC-ENT-262` 한 번 5 USD) |
| `DRAFTING_RUN_MAX_USD` | 선택. 0보다 큰 수, 기본 5 | `drafting/apps.py` 가 끼움에 꽂는다. 원고작성 실행 하나의 호출 비용 위끝(dry-run)이 넘으면 공급사 전에 결과 `over_budget`(S2 뒤 재료로 다시 재 넘으면 S3 전에)(`MARC-ENT-262` 한 번 5 USD) |
| `PARSER_URL` | 선택. http(s) 주소 | `reconcile/service/services/parse.py` 의 `default_parser` |
| `PARSER_TIMEOUT_MS` | 선택. 0보다 큰 정수. 기본은 `config/env.py` 의 값 | 같다 |
| `S3_BUCKET` | 선택. 없으면 저장소 없이 뜬다 | `core/service/services/documents.py` 의 `default_storage` |
| `S3_REGION` | `S3_BUCKET` 이 있으면 필수 | 같다 |
| `S3_ENDPOINT` · `S3_PUBLIC_ENDPOINT` | 선택. 서버가 닿는 주소 / 올리기 주소를 서명하는 주소 | 같다 |
| `S3_FORCE_PATH_STYLE` | 선택. `true`·`false` | 같다 |
| `UPLOAD_URL_TTL_SECONDS` · `MAX_UPLOAD_BYTES` | 선택. 0보다 큰 정수 | 같다(올리기 주소의 수명, 올릴 수 있는 크기의 상한) |
| `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY` | 선택. 둘 다 있거나 둘 다 없어야 한다. 없으면 boto3 의 기본 순서(태스크 역할) | 저장소와 큐 |
| `CELERY_BROKER_URL` | 선택. 없으면 브로커 없이 뜬다. `sqs` 주소만 받는다 | `config/celery.py`, `core/resources/queue.py` |
| `CELERY_BROKER_REGION` · `CELERY_QUEUE_URL` | 브로커가 있으면 필수 | `config/celery.py` |
| `CELERY_BROKER_SECURE` · `CELERY_QUEUE_NAME` | 선택 | `config/celery.py`, `core/resources/queue.py` |
| `CELERY_VISIBILITY_TIMEOUT_SECONDS` · `CELERY_TASK_SOFT_TIME_LIMIT_SECONDS` · `CELERY_TASK_TIME_LIMIT_SECONDS` · `CELERY_WAIT_TIME_SECONDS` | 선택 | `config/celery.py`. 미리 만든 큐에서는 큐의 속성이 visibility 를 정한다(`docker/elasticmq.conf`) |
| `JOB_LEASE_SECONDS` · `JOB_MAX_ATTEMPTS` · `JOB_RETRY_DELAY_SECONDS` | 선택 | `reconcile/tasks.py`, `requeue_jobs` |
| `WEB_DIST_DIR` | 선택. 비면 정적 서빙 꺼짐 | `config/settings/base.py`(`config/env.py` 밖). 이미지는 /app/web 을 넣는다. 상대 경로이거나 `index.html` 이 없으면 뜨지 않는다 |

`config/env.py` 밖에서 읽는 것: `migrate-py` 는 주인 역할의 주소 하나만 읽는다(`config/settings/migrate.py`), 듣는 포트는 `gunicorn.conf.py` 가, 호스트에 여는 포트 `API_PY_PORT` 는 `compose.yaml` 이 읽는다. 설정 키를 더하면 `config/env.py`·`.env.example`·`compose.yaml` 세 곳을 같이 고친다.

#### 실 공급사 전환 점검표

실행기(워커)가 실제 LLM 공급사를 부르게 하려면(LV1 — `MARC-ENT-262` 의 사용자 승인 뒤) 아래를 **api-py 와 worker-py 에 같은 값으로** 넣는다. 하나라도 빠지면 기동이 실패하거나(①~④) 화면이 거짓말을 한다(⑤).

1. `LLM_RUN_MODE=live` — 빈 값·`mock` 이면 키가 있어도 실행기는 싣지 않는다(LLM 단계 `setup_error`). 오타는 기동 실패다.
2. `LLM_LOG_SINK=db` — 실비가 표 `core_llm_call_logs`(AD-04 토큰·비용, 실행 상한의 시드)에 남는다. `memory`·`jsonl` 이면 live 는 뜨지 않는다.
3. 공급사 키 — 비밀 저장소에서 환경 변수(`LLM_OPENAI_API_KEY` 등)로 넣는다. 값은 이 글·`.env.example`·로그 어디에도 적지 않는다. `OPENAI_*` 환경 변수(`OPENAI_BASE_URL`·`OPENAI_ORG_ID` 등)는 컨테이너에 넣지 않는다 — SDK 가 스스로 읽어 요청이 가는 곳·조직이 바뀐다(`core/llm/providers/openai.py` 의 ★). 기동 줄은 `llm_run_mode mode=live providers=<이름들> max_usd=… sink=db` 한 줄(키 0).
4. `LLM_RUN_MAX_USD` — 실행 하나의 호출 비용 상한(USD). live 면 명시해야 한다. 잘못된 값(0·음수·nan·inf·글자)은 mock 에서도 기동 실패다 — 쓰지 않으면 비워 둔다. ★ 상한은 **실행 하나 단위뿐**이다 — 회사·하루 상한은 서버에 없다(`MARC-ISSUE-305`. 공급사 쪽 프로젝트 예산 경보를 사람이 건다).
5. api-py·worker-py 같은 값 — `aiProviderMock` 은 **응답한 api-py 의 설정**이다. 두 프로세스의 `LLM_RUN_MODE` 가 다르면(워커만 live 등) 띠가 틀려 보인다.
6. 영문번역 — 그 경로가 부르는 공급사의 키가 없으면 live 에서도 prepare 의 `setup_error` 다(경로 상수는 영문번역 몫 — `MARC-ENT-401`·`402`).

### 모듈 지도

```
apps/api-py/
├── pyproject.toml, uv.lock      의존성(판 고정)과 도구 설정(pytest, ruff, pyright)
├── .importlinter                의존 방향의 계약 열다섯(기계가 지킨다)
├── manage.py, gunicorn.conf.py  Django 명령 입구, 서버 설정
├── esgapi/
│   ├── config/                  띄우는 법. env.py · settings/ · api.py(라우터 일곱, 오류 → 응답, 상태 확인) · urls.py(/api 와 SPA fallback)
│   │                            web.py(웹 빌드 정적 서빙) · celery.py(Celery 앱과 설정)
│   ├── core/                    모듈들이 같이 딛는 바닥. 업무 모듈을 import 하지 않는다
│   │   ├── auth/                Bearer 인증(bearer.py), 주체(principal.py), 토큰 꼴·서명(tokens.py. 순수)
│   │   ├── permissions.py       권한 표(operationId → 누가)
│   │   ├── isolation/           회사 격리의 받침: 기본 매니저(managers.py), 같은 회사 외래 키(foreign_keys.py), 권한 조각(grants.py)
│   │   ├── tenancy/             옛 쿠키 세션의 꼴(session.py), 세션을 요청에 붙이는 미들웨어(middleware.py)
│   │   ├── observability/       request ID, 한 줄 JSON 기록
│   │   ├── flows/               흐름의 틀: 선언·레지스트리·실행(순수)
│   │   ├── llm/                 LLM 호출 층(아래)
│   │   ├── resources/           갈아끼우는 것: 포트(ports/)와 구현(llm · parser · storage), 큐 넣기(queue.py)
│   │   ├── service/             문서·실행 경로, 문서 올리기와 일감의 쓰기·읽기
│   │   ├── calc/                같이 쓰는 순수 규칙: decimal · guards · ids · documents · jobs
│   │   └── management/commands/ export_openapi · llm_call · requeue_jobs
│   ├── user/                    사용자·로그인·토큰·옛 교환. 표 users · user_refresh_tokens. 명령 create_user · reset_password
│   ├── organization/            회사·사업장. 표 company · sites. 명령 seed_company
│   ├── reference/               기준정보(배출계수). 표 넷, 경로 넷. 명령 import_factors
│   ├── inventory/               온실가스 인벤토리. 표 없음, 경로 셋. 세 축(엔진·계약·도구)과 흐름 — inventory/README.md
│   ├── greenwash/               그린워싱 점검. 표 없음, 경로 여섯. 세 축과 흐름·출력 — greenwash/README.md
│   ├── dataverify/              데이터 검증(계산 검토). 표 없음, 결과·목록·EDK 엑셀 읽기·양식 경로 넷(실행은 문서 없는 POST /runs). 세 축과 흐름·출력
│   ├── materiality/             중대성평가 IRO. 표 없음, 결과·목록·가치사슬 읽기 경로 셋(실행은 문서 없는 POST /runs). 세 축과 흐름·출력
│   ├── drafting/                원고작성(보고서 작성 1차 뼈). 표 넷(drafting_ 접두), 경로 다섯(실행은 문서 없는 POST /runs). 세 축과 흐름
│   └── reconcile/               데이터 검증의 앞 절반과 분해 태스크. 표도 경로도 없다
├── tests/security/              보안 층(앱 역할로 붙는다)
├── tests_integration/           떠 있는 컨테이너에 호스트에서 요청을 보내는 테스트
├── scripts/                     test-business.sh · test-security.sh · test-db.sh · test-integration.sh · check-*.sh · planted-breaks.sh
│                                check_test_layout.py · gen-ts-types.sh · dev_edk.py · readme_audit.py
└── generated/                   openapi.json, api.d.ts (계약에서 만든 프론트용 타입. 커밋한다)
```

모듈마다 무엇이 있는가(수는 `scripts/readme_audit.py facts` 로 센 것이다):

| 모듈 | 표 | 동작 | 관리 명령 |
|---|---|---|---|
| `config/` | 없다 | 2 | 없다 |
| `core/` | `core_llm_call_logs` · `core_documents` · `core_jobs` | 9 | `export_openapi` · `llm_call` · `requeue_jobs` |
| `user/` | `users` · `user_refresh_tokens` | 11 | `create_user` · `reset_password` |
| `organization/` | `company` · `sites` | 2 | `seed_company` |
| `reference/` | `reference_sources` · `reference_factor_records` · `reference_factor_scope3_categories` · `reference_mappings` | 4 | `import_factors` |
| `inventory/` | 없다 | 3 | 없다 |
| `greenwash/` | 없다 | 6 | 없다 |
| `reconcile/` | 없다 | 0 | 없다 |

읽는 차례: `config/api.py`(모으기) → `core/auth/bearer.py`(인증) → `core/permissions.py`(권한) → `user/service/apis/login.py` → `user/service/services/login.py`(로그인·refresh) → `core/isolation/managers.py`(회사 범위) → `organization/service/apis/organization.py`(경로) → `tests/security/`. 업무 모듈은 `<모듈>/service/apis/` → `<모듈>/service/services/` → `calc/`(또는 엔진)의 차례로 읽는다.

### 요청이 지나는 길

```
요청 ─▶ gunicorn(일꾼 프로세스) ─▶ Django
         ├▶ RequestIdMiddleware   (core/observability/middleware.py)  X-Request-ID 를 받거나 짓고, 접근 줄 하나
         ├▶ WhiteNoiseMiddleware  WEB_DIST_DIR 의 파일이면 여기서 낸다(웹 빌드)
         └▶ TenantMiddleware      (core/tenancy/middleware.py)  옛 쿠키 세션을 읽어 요청에 붙인다. DB 에 닿지 않는다
              └▶ urls: /api/… → django-ninja ─▶ 인증(Bearer → 옛 쿠키) ─▶ 경로 함수(<모듈>/service/apis/)
                     │                                                   └▶ permitted(권한 표) ─▶ services·selectors
                     │                                                         └▶ <Row>.for_company(회사 id) ─▶ PostgreSQL
                     └ 그 밖의 GET·HEAD → 화면 경로면 index.html(SPA fallback, config/web.py), 아니면 JSON 404
```

- **요청마다의 트랜잭션은 없다.** 한 표의 쓰기는 service 가 자기 블록에서 끝내고, 여러 표는 `actions` 의 함수 하나로 묶는다. 큐 넣기는 커밋 뒤(`on_commit`)에 한다. 그래서 거절은 쓰기 앞에서 한다(`core/tenancy/middleware.py` 의 머리 글).
- **회사 격리.** DB 의 행 수준 정책은 쓰지 않는다. 조회의 조건은 selector 가 회사 id 를 인자로 받아 건다. 그 조건을 빼먹은 길은 `core/isolation/` 의 받침이 막는다: 회사 범위 표의 기본 매니저는 회사를 정하지 않은 조회를 거절하고, 같은 회사 외래 키는 남의 회사 행을 가리키는 하위 행을 DB 가 거절한다. 막지 못하는 길은 `core/isolation/managers.py` 의 머리 글에 적었다.
- **DB 연결은 요청 사이에 다시 쓴다**(`CONN_MAX_AGE`). 연결에 상태를 남기는 SET 을 더하지 않는다.
- `/healthz`·`/readyz`(바깥 주소는 /api 아래)와 ninja 의 문서 둘(`/api/docs`·`/api/openapi.json`)은 인증이 없다.
- 접두 없는 `/healthz`·`/readyz` 는 화면 경로가 아니라 JSON 404 다(예약어. `config/web.py`).

### 모듈의 뼈대와 의존의 방향

모듈 하나가 Django app 하나다. HackSoft Django Styleguide 의 services / selectors 를 따른다.

| 자리 | 하는 일 | 규칙 |
|---|---|---|
| `<모듈>/models.py` · `<모듈>/migrations/` | 표의 꼴 | 새 모델은 `core.models.BaseModel` 을 이어받는다. 회사 칸이 있는 표는 회사 범위 모델로 둔다(아래 「새 표를 만들 때」) |
| `<모듈>/service/services/` | 쓰기 유스케이스 | HTTP 를 모른다. 결과는 예외가 아니라 갈래(frozen dataclass)로 |
| `<모듈>/service/selectors/` | 읽기 | 쓰지 않는다 |
| `<모듈>/service/actions/` | 도메인을 넘는 조립, 여러 표의 쓰기 | 남의 도메인은 여기서만 만난다 |
| `<모듈>/service/apis/` · `<모듈>/api.py` | 경로(`router`) | 얇게: 권한을 보고 services·selectors 를 부르고 schemas 로 답한다 |
| `<모듈>/service/schemas/` | 요청·응답의 꼴 | 본문을 받는 것은 `core.schemas.StrictIn` 을 이어받는다 |
| `calc/` · `<모듈>/service/utils/` · 엔진 | Django 를 모르는 순수 계산·판정 | DB 없이 테스트된다 |
| `tests/` | 순수 층과 업무 층의 테스트 | 소스의 폴더를 비춘다(`scripts/check_test_layout.py`) |

지키는 것은 `uv run lint-imports` 다(`.importlinter` 의 계약 열다섯. 센 곳: `scripts/readme_audit.py facts` 의 「import-linter 계약」 줄).

- **가.** `core` 는 업무 모듈을 import 하지 않는다.
- **나.** 모듈끼리 `models` 를 직접 import 하지 않는다.
- **다.** 순수 모듈(`calc`, 표면의 utils, permissions, `core/tenancy/session.py`, `core/permissions.py`, `config/env.py`, `core/llm` 의 순수 모듈 등)은 `django`·`ninja`·`psycopg` 를 import 하지 않는다.
- **라.** `api.py`·`<모듈>/service/apis/`·`<모듈>/tasks.py` 는 `models` 를 직접 import 하지 않는다.
- **마.** 두 표면(admin·service)은 서로를 import 하지 않는다(`reference/admin` 과 `reference/service`).
- **바.** Service·Selector 는 남의 도메인을 import 하지 않는다(도메인을 넘는 조립은 actions 에서).
- **사.** 시험 밖 코드는 `esgapi.*.tests` 를 import 하지 않는다.
- **아.** 그린워싱 축 넷: 엔진·계약·도구·출력이 서로를 어디까지 들이는가. 뜻은 `greenwash/README.md` 의 「규칙 세 줄」.
- **자.** 인벤토리 축 넷: 엔진·계약·도구와 엔진의 흐름끼리. 뜻은 `inventory/README.md` 의 「규칙 세 줄」.

계약마다 어기는 import 를 심어 그 계약만 빨개지는지 보는 스크립트가 있다: `scripts/planted-breaks.sh`(가~자 열다섯 전부, 깨진 계약을 계약 id 로 센다).

**경로를 더하면 고치게 되는 공유 파일**(더하기만): `generated/`(`scripts/gen-ts-types.sh` 로 다시 만든다), `config/tests/test_api_contract.py` 의 표, `core/permissions.py` 의 권한 표. 의존성을 더하면 `pyproject.toml`·`uv.lock`, 설정 키를 더하면 `config/env.py`·`.env.example`·`compose.yaml`. 아직 경로가 없는 모듈(`reconcile`)은 라우터를 처음 만들 때 `config/api.py` 에 한 줄을 더한다.

### 새 표를 만들 때

모델을 적고 `DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run python manage.py makemigrations <모듈>`. 만들어진 파일은 `uv run ruff check --fix <파일> && uv run ruff format <파일>` 로 다듬는다.

- 앱 역할의 권한은 마이그레이션에 `core/isolation/grants.py` 의 `grant(…)` 로 준다. DELETE 와 표 변경 권한은 주지 않는다.
- 회사 칸(`company_id`)이 있는 표는 `CompanyScopedModel` 을 잇고 기본 매니저를 `CompanyScopedManager` 로 둔다. 쓰는 법은 `core/isolation/managers.py` 의 머리 글.
- 회사 칸이 있는 두 표 사이의 외래 키마다 `core/isolation/foreign_keys.py` 의 두 조각을 같이 넣는다. 빠뜨리면 `tests/security/test_same_company_foreign_keys.py` 가 잡는다.
- 모델과 마이그레이션이 어긋나면 `config/tests/test_migrations.py` 가 잡는다.

### 프론트의 타입

```sh
apps/api-py/scripts/gen-ts-types.sh     # 경로·schemas → generated/openapi.json → generated/api.d.ts
```

생성물 셋은 커밋한다(`generated/openapi.json`, `generated/api.d.ts`, `generated/api.d.ts.source-sha256`). `generated/openapi.json` 이 코드와 어긋나면 `config/tests/test_api_contract.py` 가 잡는다. `api.d.ts` 는 그것을 만든 계약 파일의 sha256 을 곁 파일에 적어 두고 같은 테스트가 견준다.

본문을 받는 경로는 413 을 선언한다(`core.schemas.BODY_ERROR_RESPONSES`). 토큰을 받는 경로는 444 도 선언한다(`TOKEN_ERROR_RESPONSES`).

### 테스트 층

| 층 | 무엇을 | DB 와 역할 | 자리 | 돌리기 |
|---|---|---|---|---|
| 순수 | 규칙·계산·꼴·설정·계약(OpenAPI)·LLM 호출 층(모의 공급사)·흐름 | 없음. 닿으면 실패한다 | `esgapi/<모듈>/tests/` (표시 없음) | `uv run pytest -q -m "not django_db and not security"` |
| 업무 | 경로·services·selectors·모델 | 주인 역할. 테스트마다 되돌린다 | `esgapi/<모듈>/tests/` (`@pytest.mark.django_db`) | `scripts/test-business.sh -n 2` |
| 보안 | 앱 역할의 권한, 회사 경계, 같은 회사 외래 키, 로그인·refresh, 연결에 남는 상태 | 앱 역할(`esg_app`). 진짜로 커밋한다 | `tests/security/` (`@pytest.mark.security`) | `scripts/test-security.sh` |
| 통합 | 떠 있는 컨테이너에 호스트에서 보내는 요청(한 줄기, 올리기, 워커, 파서, 웹, 관측) | 컨테이너가 쓰는 그대로 | `tests_integration/` | `scripts/test-integration.sh` |

- pytest 설정은 하나다(`pyproject.toml`). 업무 층과 보안 층은 Django 가 붙는 역할이 달라(주인 / 앱) 한 번에 돌릴 수 없다. 둘을 차례로 돌리는 것은 `scripts/test-db.sh` 다.
- 업무 층의 주인 역할은 superuser 라 권한(GRANT)이 걸리지 않는다. 「A 가 B 의 것을 못 본다」와 권한은 보안 층에서 잰다.
- 테스트의 자리 규칙(소스의 폴더를 비춘다)은 `scripts/check_test_layout.py` 가 잰다.
- 테스트는 이미지와 wheel 에 실리지 않는다(`scripts/check-wheel.sh`).

### 확인하는 법

뿌리의 `scripts/verify.sh` 가 Python 쪽 단계를 같이 돌린다(위 「확인하는 법」). 따로 돌릴 때:

```sh
cd apps/api-py
uv sync --frozen
uv run ruff check . && uv run ruff format --check .
uv run pyright                                            # strict
uv run lint-imports                                       # 의존 방향의 계약 열다섯
uv run python scripts/check_test_layout.py                # 테스트 자리 규칙
uv run pytest -q -m "not django_db and not security"      # 순수 층
scripts/test-business.sh -n 2                             # 업무 층. 컨테이너가 떠 있어야 한다
scripts/test-security.sh                                  # 보안 층. 컨테이너가 떠 있어야 한다
scripts/test-integration.sh                               # 통합. 위 「띄우는 법」의 export 를 하고 띄운 컨테이너
scripts/planted-breaks.sh                                 # 계약마다 심은 파손
```

커밋할 때는 `scripts/git-hooks/pre-commit` 이 스테이징한 파이썬 파일만 본다(ruff, lint-imports, 건드린 모듈의 순수 층). 훅이 막으면 고친다.

`services/parser` 에도 ruff 와 pyright 가 걸려 있다. 범위와 뺀 것은 `services/parser/README.md` 의 「테스트」.

### LLM 호출 층 (core/llm)

AI 모듈은 공급사 SDK(openai·anthropic·google-genai)를 직접 부르지 않고 `esgapi/core/llm` 을 거친다. 여기서 한 번에 정해지는 것: 경로(route)의 모델 순회와 대체 호출, 스키마 검증과 재시도, 호출 직전의 비용 상한, 분당 호출 간격, 시도마다 남는 호출 기록, 모의 공급사와 dry-run.

```python
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.setup import llm_client          # 설정(LLM_*)에서 세운 이 프로세스의 클라이언트 — 키를 싣지 않는다(LH2)
from esgapi.core.llm.types import Success, Tags

request = CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="light", tags=Tags(company_id, "core"), schema=Answer)
result = llm_client().call(request)                    # 결과 갈래 하나를 돌려준다. 실제 공급사 경로는 키가 없어 LiveSetupError — 흐름의 단계는 실행기의 context.llm()
if isinstance(result, Success): answer = result.data
```

- **결과는 갈래다**(`result.kind`): `success` · `schema_mismatch` · `refusal` · `truncated` · `provider_error` · `timeout` · `budget_exceeded`. 설정·프롬프트·키의 잘못은 결과가 아니라 예외다(`LlmConfigError`·`PromptError`·`LiveSetupError`).
- **프롬프트**는 모듈의 것이다: id `모듈/이름@판` ↔ 파일 `esgapi/<모듈>/prompts/<이름>/<판>.md`. 판을 빼면 거부한다.
- **모델 ID·단가·한도·경로**는 코드에 없고 자료에 있다: `core/llm/data/models.json`. 출처와 확인 일자는 `core/llm/data/README.md`. 테스트·모의 공급사 전용 가상 모델은 `core/llm/data/models.synthetic.json`.
- **temperature**: `CallRequest` 의 `temperature` 칸으로 준다. 경로의 모델이 전부 그것을 받지 않으면 공급사를 부르기 전에 `LlmConfigError` 다. 모델마다 받는지와 범위, 그 출처는 `core/llm/data/README.md` 의 「모델별 temperature」.
- **호출 기록**은 시도마다 한 줄이다. 본문은 기본으로 남기지 않고 해시만 남긴다. 가는 곳은 `LLM_LOG_SINK`: `memory`(기본), `jsonl`, `db`(표 `core_llm_call_logs`).
- **키**는 환경 변수 `LLM_*_API_KEY` 에서만 온다(전부 선택). 키 없이도 서버는 뜬다.
- **Django 를 아는 파일은 셋이다**: `core/llm/setup.py`, `core/llm/sink_db.py`, 관리 명령. 나머지의 순수성은 `uv run lint-imports --config esgapi/core/llm/purity.importlinter` 가 잰다.

돌려 보기(키 없이, 공급사 호출 0):

```sh
docker compose exec api-py python manage.py llm_call --prompt core/hello@1 --var name=김 --route light --dry-run
docker compose exec -e LLM_LOG_SINK=jsonl -e LLM_JSONL_PATH=/tmp/llm.jsonl api-py \
  python manage.py llm_call --prompt core/hello@1 --var name=김 --route mock --mock-text '{"ok":true}'
```

실제 경로(`--dry-run` 을 뺀 실제 route)는 **돈이 든다**: 그 공급사의 키와 `--limit-usd <상한>` 이 둘 다 있어야 부른다.

★ 알아 둘 것: (가) 동기 호출이다. 요청 안에서 부르면 gunicorn 일꾼이 묶이고, 호출의 기본 시간 제한(`core/llm/client.py` 의 `DEFAULT_TIMEOUT_MS`)은 일꾼의 `timeout`(`gunicorn.conf.py`)보다 길다. (나) 비용 상한의 누적과 호출 간격은 프로세스 하나의 것이다(`db` 싱크는 커밋된 행을 일꾼을 넘어 센다. 뜻과 세지 못하는 몫은 `core/llm/sink_db.py` 의 머리 글). (다) 서버 요청 길의 클라이언트(`llm_client()`)는 run mode 와 무관하게 키를 싣지 않는다 — 실제 호출은 상한이 있는 실행기 길(`runs/context.py`)과 `llm_call --limit-usd` 뿐이다. (라) 실제 공급사 호출로 검증하지 않았다(어댑터는 가짜 SDK 객체로 쟀다).

`db` 싱크의 행의 회사는 꼬리표(`Tags`)에 적힌 회사 id 다. 관리 명령은 `--tenant <회사 id>` 가 필수다. 상한도 꼬리표로 고른다(`core/llm/budget.py`). 본문은 DB 에 두지 않는다(칸이 없다). 앱 역할이 이 표를 덧붙이기만 하는지는 `tests/security/test_llm_log.py` 가 잰다.

### 기준정보 (reference)

배출계수와, 그것을 지침의 규칙대로 묶는 조립 규칙이 `esgapi/reference/` 에 있다. esg-lab 의 조립 규칙과 적재 산출물(jsonl)을 옮긴 것이다. 앱은 산출물만 읽는다(PDF 를 읽는 적재기는 옮기지 않았다).

```sh
# 패키지에 실린 사본과 대응표를 들인다. 주인 역할의 컨테이너로 돈다
docker compose run --rm migrate-py python manage.py import_factors
# esg-lab 의 전체 계수 표를 들인다. 기본은 ok·unverified 뿐이다(disputed 는 --include-license 로 명시)
docker compose run --rm -v <esg-lab>/data/factors:/data:ro migrate-py \
  python manage.py import_factors /data/factors.jsonl --mapping /data/mappings.kr-ets.json
```

| 경로 | 무엇 |
|---|---|
| `GET /reference/sources` | 출처 전부와 이용 조건(`licenseStatus`·`licenseNote`) |
| `GET /reference/factors` | 낱줄 찾기. `q` 는 이름의 부분 일치, `limit` 은 200 까지 |
| `POST /reference/assemble` | 고정연소 계수 한 건을 조립(연료·업종·산정등급 → 낱줄 다섯) |
| `POST /reference/assemble-electricity` | 구매 전력 계수 한 건을 조립 |

- **전부 읽기다.** 쓰기 경로가 없다. 표에 회사 칸이 없다(전역 자료). 앱 역할에는 `SELECT` 만 준다 → 요청을 처리하는 프로세스가 계수를 고칠 길이 DB 에 없다(`tests/security/test_reference.py`). 들이는 것은 주인 역할의 관리 명령뿐이고, 앱 역할의 설정으로 부르면 `not_owner` 로 멈춘다.
- **disputed 는 명시해야만 나온다.** 가져오기(`--include-license`)와 조회(`license=`) 두 자리가 따로 거르고 기본은 둘 다 `ok,unverified` 다.
- **조립이 「못 했다」는 오류가 아니라 답이다.** `200` 에 `{ok: false, failure: {kind, …}}`(갈래는 `reference/calc/types.py` 의 `FailureKind`). **기본값이 없다**: 빠진 입력은 채우지 않고 `missing_input` 으로 답한다.
- **조립 규칙은 `reference/calc/` 에 있고 Django 를 모른다**(계약 다). 값은 낱줄의 `value_raw`(출처 표기 그대로의 글자)에서만 읽는다.
- **upsert 는 지우지 않는다.** 새 파일에서 사라진 줄은 DB 에 남는다.
- 자료 사본과 그 출처·확인 일자·이용 조건은 `reference/data/README.md`. 사본은 전부 `unverified`(이용 조건을 확인하지 못함)이고 그 상태로 이미지에 실린다.

Scope 3 계수의 후보 추리기는 `inventory` 쪽에 있다(`reference/service/selectors/reference.py` 의 `scope3_candidate_records` 가 후보가 될 낱줄을 내준다).

### 인벤토리 계산 (inventory)

`inventory` 의 폴더 지도, 규칙 세 줄(엔진은 계약을 모른다 / 계약은 엔진을 모른다 / 둘을 잇는 것은 흐름뿐이다), 「다음 판 넣는 법」은 **`inventory/README.md`** 가 정본이다. 여기에 되풀어 적지 않는다. 자리만 적으면:

- 엔진 Scope 1·2: `inventory/engines/scope12/engine_1/`(흐름 `scope12.engine@1`)
- 엔진 Scope 3: `inventory/engines/scope3/llm_first_1/`(흐름 `scope3.llm-first@1`)
- 계약(결과 꼴): `inventory/contracts/shapes.py`
- 도구: `inventory/tools/jsrepr.py`, `inventory/tools/xlsx_reader.py`, `inventory/tools/scope3_sheets/`
- 흐름과 등록: `inventory/flows/`

Scope 1·2 배출량을 계산하는 경로가 하나 있다(`POST /inventory/calc`). **저장하지 않는다**: 같은 입력이면 같은 출력이고, DB 에 남는 것이 없다. 요청의 예는 위 「손으로 따라가기」의 6번이다.

| | |
|---|---|
| 본문 | `rows`(1,000행까지), `gwpSetId`(기본값 없음), `tables?`(기준정보 표. 안 주면 패키지에 실린 표), `groupBy?` |
| 수 | 전부 **십진 문자열**이다. JSON 의 수로 보내면 거절한다. 응답의 값도 문자열이고 반올림하지 않았다 |
| 200 | 행마다 `status` 가 `"ok"`(값 + 손으로 따라갈 수 있는 단계) 또는 `"failed"`(`failure.kind`). 실패한 행은 합계에 0 으로 들어가지 않는다 |
| 오류 | `INVALID_TABLES`, `TOO_MANY_ROWS`, 꼴 틀림은 422 |

- 엔진은 Django·ninja·DB 를 import 하지 않는다. esg-lab 의 TS 엔진을 옮긴 것이고, 같은 입력에서 글자까지 같은 JSON 을 낸다. 그것을 재는 것이 골든이다(`inventory/tests/data/golden/`).
- **십진수는 직접 만든 것**이다(`core/calc/decimal.py`). 표준 라이브러리의 `decimal.Decimal` 은 정밀도를 넘는 결과를 말없이 반올림하므로 쓰지 않는다. 불리언 거름은 `core/calc/guards.py` 다. 데이터 검증의 `reconcile/calc/dec.py` 도 같은 십진 커널을 들인다.
- **패키지에 실린 표는 표본이다**. 출처와 확인 일자는 `inventory/data/README.md`. 한국 지침의 계수 전량은 여기 없다.
- 속성 테스트는 `hypothesis` 를 쓴다(dev 의존성에만 있고 이미지에는 없다).

### Scope 3 후보 추리기와 분류 (inventory)

| | `POST /inventory/scope3/shortlist` | `POST /inventory/scope3/classify` |
|---|---|---|
| 하는 일 | 낱말 검색으로 계수 후보를 추린다. **생성 모델을 부르지 않는다** | 행을 품목으로 묶어 묶음마다 범주를 묻는다(생성 모델 호출) |
| 200 | `status: "shortlisted"` 또는 `"no_candidates"`. 빈 목록으로 답하지 않는다 | 묶음마다 `classified` · `classification_failed` |
| 그 밖 | `INVALID_LICENSE` | `DUPLICATE_ROW_ID`, `TOO_MANY_GROUPS`, **503 `LLM_NOT_CONFIGURED`** |

- **★ `classify` 는 떠 있는 서버에서 늘 503 이다.** 이 경로가 부르는 것은 모의 공급사의 경로 하나뿐이고(`inventory/service/services/inventory.py` 의 `SCOPE3_ROUTE`), 서버의 클라이언트에는 그 경로가 없다. 되는 길은 테스트가 모의 클라이언트를 꽂아 잰다.
- **숫자는 생성 모델에 넘기지 않는다.** 프롬프트에 가는 것은 품목명·단위·통화·운송의 출발지·도착지·수단뿐이다. 템플릿은 `inventory/prompts/`(프롬프트 id `inventory/scope3-classify@1`·`inventory/scope3-recommend@1`).
- **추리는 방식은 둘**이다: `lexical-v2`(기본. 낱말 단위 BM25), `lexical-v1`(부분 문자열 일치. 견줄 기준).
- **동점은 계수 id 의 유니코드 코드 포인트 순**으로 가른다(`scope3_candidate_records` 가 파이썬에서 놓는다).
- **이용 조건의 기본은 `ok,unverified`** 다. disputed 는 `license` 에 명시해야만 후보가 된다.
- 순수 규칙과 골든 G1 은 엔진 폴더와 `inventory/tests/data/scope3/` 에 있다. 저장소 밖의 실제 표로 재는 것: `uv run python -m esgapi.inventory.tests.scope3_replay <esg-lab>`.

### Scope 3 시트 읽기 (inventory)

마크스폰이 준 Scope 3 계수 책(xlsx)과 입력 템플릿의 드롭다운 정의를 **읽힌 그대로** 메모리의 값으로 세우고, 둘의 어긋남을 자리와 수로 드러낸다. 경로도 표도 없다(지금은 시험만 부른다). 원본 xlsx 는 저장소에 없다.

| 자리 | 무엇 |
|---|---|
| `inventory/tools/xlsx_reader.py` | xlsx 바이트 → 읽힌 표. **xlsx 를 여는 것은 이 파일뿐이다**(표준 라이브러리 `zipfile` + `xml.etree.ElementTree`). 망가진 바이트에 예외를 내지 않고 갈래로 답한다 |
| `inventory/tools/scope3_sheets/grid.py` | 읽힌 표의 값: 칸의 갈래, A1 주소와 범위 |
| `inventory/tools/scope3_sheets/factor_layout.py` · `inventory/tools/scope3_sheets/factors.py` | 계수 책 시트의 꼴과 적재기. 안 든 칸은 `Unaccounted` 로 나온다 |
| `inventory/tools/scope3_sheets/dropdowns.py` | 정의된 이름 → 목록, 데이터 유효성의 꼴 |
| `inventory/tools/scope3_sheets/crosscheck.py` | 드롭다운과 책의 어긋남 검사 |

- **메우지 않고 고르지 않는다.** 단위를 접거나 환산하지 않고, 값 자리의 `-` 를 0 으로 읽지 않는다. 어긋남 검사의 결과에는 「옳은 쪽」 칸이 없다.
- 읽개가 거절하는 것(상한을 넘는 것, 암호 걸린 항목, 바깥을 가리키는 관계 등)과 **안 잰 것**(다른 도구가 저장한 xlsx, 큰 파일의 시간·메모리)은 `inventory/tools/xlsx_reader.py` 의 머리 글에 있다. 올리기 경로에 이 읽개를 잇기 전에 다시 본다.
- 받은 원본과의 대조는 게이트 밖이다: `cd apps/api-py && uv run --frozen python -m esgapi.inventory.tests.s3sheets_probe "<계수 책>" "<템플릿>"` 이 건수와 `시트!칸` 자리만 찍는다(값과 이름은 찍지 않는다).

### 데이터 검증의 규칙 (reconcile)

`esgapi/reconcile/calc/` 는 데이터 검증의 **방법을 가리지 않는 앞 절반**이다: 문서 모델에서 숫자를 전부 찾아 값 후보와 값 아님으로 가르고(`facts`·`notation`), 종류를 붙이고(`kinds`), 값 후보 숫자를 가리고(`mask`), 값 후보의 ID 를 쪽과 상자로 바꾼다(`places`). esg-lab `ts/reconcile` 을 옮긴 순수 모듈이다. 뜻 붙이기와 짝짓기·판정, 모델 호출, 저장, 경로는 아직 없다.

| 파일 | 하는 일 |
|---|---|
| `reconcile/calc/document.py` · `reconcile/calc/places.py` 의 `validate_*` | 바깥에서 온 JSON(문서 모델·글자 자리)의 꼴 검사 |
| `reconcile/calc/notation.py` | 숫자 표기 규칙 |
| `reconcile/calc/facts.py` | 값 후보 · 값 아님 · 격자 · 실패 표 |
| `reconcile/calc/kinds.py` · `reconcile/calc/mask.py` | 값 후보의 종류, 가리기 |
| `reconcile/calc/places.py` | 값 후보 → 쪽과 상자 |
| `reconcile/calc/jstext.py` | JS 의 글자 다루기 흉내(UTF-16 자리) |
| `reconcile/calc/job_summary.py` | 분해 일감의 끝을 표에 적을 작은 요약(정수와 불리언뿐) |
| `reconcile/service/services/parse.py` | 파서 포트 → 꼴 검사 → 같은 PDF 인지(sha256) → 값 후보와 상자의 색인 |
| `reconcile/tasks.py` | Celery 태스크 `jobs.parse`(아래 「워커와 큐 (Celery)」) |

**자리의 단위는 UTF-16 이다.** 값 후보의 자리와 글자 자리는 JS 의 문자열 자리와 같다. 파이썬의 문자열 자리와 다르므로 글을 자를 때는 `jstext.to_units` 를 거친다.

TS 와 같은지(골든)는 구획 여덟의 값 전체 일치로 잰다:

```bash
apps/api-py/esgapi/reconcile/tests/golden/make-golden.sh                              # esg-lab 의 TS 로 덤프 → git 밖
(cd apps/api-py && uv run python -m esgapi.reconcile.tests.golden.check_lab)          # 네 보고서 + 지은 문서
(cd apps/api-py && uv run pytest -q -m "not django_db and not security" esgapi/reconcile)   # 지은 문서 골든
```

무효 조건: 네 문서의 일치는 그 실행 때의 esg-lab 산출에 대해서만 잰 것이고 게이트는 되재지 않는다(입력이 git 밖). 입력은 esg-lab 의 다른 엔진 산출이라 이 저장소의 파서(pdfium)가 낼 문서 모델로는 재지 않았다. 게이트가 되재는 것은 지은 문서(`reconcile/tests/golden/synthetic/`)뿐이다. 옮긴 것은 TS 의 동작이고, 규칙이 다른 문서에서 틀리는 자리가 알려져 있다(고치지 않았다: 고칠지는 정답을 다시 재는 일과 같이 정한다).

### 그린워싱 (greenwash)

흐름 `greenwash.colab@E0` — 단계 extract → index → judge → wordcount → locate → report, 입력 꼴 `greenwash.document@1`, 결과 꼴 `greenwash.result@1`, 출력 `greenwash-report.xlsx`. 마크스폰 Colab 노트북의 재현이다.

- `engines/e0/` 는 esg-lab GW1(노트북을 약점까지 옮긴 판, esg-lab main `2a237d2`)의 **사본이라 고치지 않는다**. 바뀐 것은 import 경로·도구 주석·서식뿐이고 `tests/test_copy_ast.py` 가 GW1 의 정규화 AST sha256 과 견준다. 고친 판은 새 흐름 판으로 낸다.
  예외: `checker.py` 의 스캔 루프는 GL1 에서 이어 돌기 꼭지(resume·checkpoint)를 달아 흐름과 한 벌이 되었다. AST 고정은 나머지 아홉 파일만 본다.
- 흐름은 어댑터(`pdf_text`·`llm`·`embedding`·선택 `coordinates`·`tokens`)로만 바깥에 닿고 클라이언트를 짓지 않는다. LLM 은 `flows/colab_e0.LlmChatBridge` 가 core.llm 의 프롬프트 `greenwash/{detect,eval,repair,low-only}@1` 로 넘긴다(노트북 글은 변수로). dry-run 은 LLM·임베딩을 부르지 않고 `tokens` 로 센다.
- judge 는 쪽마다 체크포인트하고 진행률(`step_progress`)을 낸다. 끊기면 `start_at="judge"` 와 마지막 체크포인트로 이어 돈다.
- 계약(프론트가 기대어 짓는다): 결과 `greenwash.result@1`(`contracts/shapes.py`), 수정본 비교 `greenwash.compare@1`·검토 `greenwash.review@1`(`contracts/compare_shapes.py`·`review_shapes.py`, 초안 판). 고정 스키마는 `tests/data/flow-shapes/`, 지은 예시는 `tests/data/contract-examples/`. 세 꼴 모두 초안 판 시기에는 칸을 @1 안에서 고칠 수 있고(검증 감독 승인, 예: 「추가 단어」 `extraTerms`), 굳힌 뒤에는 칸을 바꾸는 것이 새 판(@2)이다.
- 「추가 단어」 `extra_terms`: 입력에서 정리(정규화 키 `normalize_term(t).replace(" ", "")` 로 중복·기본 목록 비교, 괄호·따옴표가 든 단어와 글자·숫자 없는 단어는 거절, 30자·30개 상한)한 뒤 노트북의 `env_keywords_extra`(escape 해서)와 낱말 빈도(기본 목록과 겹친 것 빼고)에 함께 쓴다. 노트북의 환경 낱말 설정은 프로세스 전역이라 judge 가 점검마다 되돌린다. 빈 목록이면 결과가 G1a 와 같다.
- 문장 위치: `tools/coordinates.PdfiumCoordinates`(pdfium 부분은 `tools/pdfium_locate.py`)가 판정 문장을 pdfium 쪽 글에서 찾아 줄마다 상자(page 1부터, [left, top, right, bottom] pt, 크롭의 왼쪽 위 원점)를 낸다. 글 뽑기는 pypdf 그대로라 코랩 재현은 바뀌지 않는다. 못 찾음·여러 곳·250자 넘음·10줄 넘음·돌린 쪽은 null(화면은 쪽 이동). 공개 보고서 둘의 250자 이하 문장 97.7% 를 찾았다(G1d). 실행마다 짓고 `close()`, pdfium 은 스레드에 안전하지 않다.
- 경로 여섯(`/greenwash` 아래, 쿠키 세션·고객사 사용자): 결과 `GET runs/{run_id}/result`(result@1), 검토 `GET·PUT runs/{run_id}/review`(review@1), 비교 `GET compare?base=&target=`(compare@1), 엑셀 `GET runs/{run_id}/report?confirmed=`(xlsx — G1b-2a) — 비교만 꼴만 있고 몸은 501(결과·검토는 G1b-1, 엑셀은 G1b-2a 가 몸을 채웠다). 기본 단어 `GET terms/default`(`{terms}`, 노트북 GREEN_TERMS 그대로)는 몸이 있다. 실행은 공통 `/runs` 로 한다.
- review@1 의 서버 규칙: 표시가 하나라도 있으면 in_review, PUT `state=confirmed` 면 미검토를 adopted 로 채워 marks = 결과 items 전부, 확정 뒤 PUT 은 409 `REVIEW_LOCKED`(legacyCode `review_locked`). `confirmedAt`·`confirmedBy({id, name})` 는 확정일 때만 값. 제외 사유는 1차에 자유 글.
- 불변 열쇠: 결과는 실행마다 한 번 쓰면 바뀌지 않는다 — `(runId, itemIndex)` 가 문장의 고정 열쇠이고 검토 표시·비교·엑셀이 이것으로 잇는다.
- 흐름 꼴의 키는 camelCase(GC3) — 값(`level`·`state`·`decision`·`outcome`)과 값이 키인 자리(`counts.byLevel`·`byPart`, compare `counts`)는 그대로. engines/e0·단계 자료는 snake, 밖으로 나가는 꼴은 `contracts/wire.result_to_wire` 하나를 거친다.
- GW1 과의 대조는 `apps/api-py/scripts/section4-G1a.sh`(도움 코드는 저장소 밖). 실제 LLM 호출은 아직 하지 않았다.

### 파서

PDF 를 문서 모델로 분해하는 일은 이 프로세스가 하지 않는다. 따로 뜨는 컨테이너 `services/parser` 가 하고, 여기서는 포트로 부른다. 파서의 약속은 위 「파서의 문서 분해」와 `services/parser/README.md` 에 있다.

- 포트는 `core/resources/ports/parser.py`(「PDF 바이트 → 문서 모델 + 글자 자리」), 구현은 `core/resources/parser.py` 의 둘이다: `http`(떠 있는 파서) · `fake`(sha256 → 결과의 표). 쓰는 곳은 `reconcile/service/services/parse.py` 하나이고, 그것을 부르는 것은 워커의 태스크다.
- 주소는 `PARSER_URL`(compose 가 파서 서비스의 주소를 넣는다), 기다리는 최대 시간은 `PARSER_TIMEOUT_MS`(기본은 `config/env.py` 의 값. 파서 자신의 시간 상한보다 길게 두어 파서가 먼저 끊게 했다). 어댑터는 환경을 읽지 않는다: `config/env.py` 가 읽고 `default_parser(config)` 가 명시로 넘긴다. 부르는 꼴은 `POST {PARSER_URL}/parse?file_name=…`, 본문은 PDF 바이트다.
- 실패는 갈래 셋이다: `rejected`(4xx, 다시 해도 안 된다) · `unavailable`(5xx·연결 실패·시간 초과) · `invalid_response`(200 인데 꼴이 틀리다).
- 떠 있는 파서와 맞물려 도는지는 통합 테스트 `tests_integration/test_parser_flow.py` 가 잰다.
- 포트를 갈아끼울 때는 `esgapi.core.resources.<포트>` 의 `make(name, …)` 를 바로 부른다. 시험용 가짜 구현(`FakeStorage`·`FakeParser`)은 `core/tests/resource_fakes.py` 에 있고 제품 코드는 들이지 않는다(계약 사).

### 문서 올리기와 상태 표 (core)

PDF 하나를 **클라이언트가 서명된 주소로 저장소에 직접** 올린다. api-py 는 파일 바이트를 받지 않고, 그 문서와 그 문서에 걸린 일감의 상태만 표에 남긴다(경로 `core/service/apis/documents.py`, 쓰기·읽기 `core/service/`, 순수 규칙 `core/calc/documents.py`, 저장소 포트 `core/resources/ports/storage.py` 와 어댑터 `core/resources/storage.py`).

★ **개발 단계에 실제 고객 문서를 올리지 않는다.** 올린 원본은 저장소에 그대로 남는다. 로컬의 버킷은 compose 의 볼륨이라 `docker compose down -v` 로 지워진다. 지우는 길과 보존 기간은 정하지 않았다.

**한 줄기** (위 「손으로 따라가기」의 `$H` 를 그대로 쓴다. 저장소에 있는 지은 PDF 로 해 본다):

```sh
PDF=apps/api-py/tests_integration/data/ruled-table.pdf      # 지은 표 하나짜리 PDF(실제 문서가 아니다)
SIZE=$(wc -c < "$PDF" | tr -d ' ')

# 1. 만들기: 이름과 크기만 보낸다. 문서 행(awaiting_upload)이 생기고 서명된 올리기 주소가 온다
curl -s -H "$H" -X POST $API_PY/documents -H 'content-type: application/json' \
  -d "{\"fileName\": \"ruled-table.pdf\", \"sizeBytes\": $SIZE}" > /tmp/esg-doc.json
DOC=$(jq -r .document.id /tmp/esg-doc.json); URL=$(jq -r .upload.url /tmp/esg-doc.json)

# 2. 그 주소로 저장소에 직접 올린다(api-py 를 지나지 않는다. 토큰도 싣지 않는다: 주소 자체가 권한이다)
curl -s -o /dev/null -w '%{http_code}\n' -X PUT --data-binary @"$PDF" "$URL"

# 3. 올림 확인: 본문이 없다. 서버가 저장소에 물어 크기를 견주고 ETag 를 적는다 → 문서 uploaded, 일감 queued
curl -s -H "$H" -X POST $API_PY/documents/$DOC/confirm

# 4. 상태 보기(워커가 잡으면 일감이 processing → done 으로 바뀐다)
curl -s -H "$H" $API_PY/documents/$DOC
```

**표 둘**(`core/models.py`, 마이그레이션 `core/migrations/0001_initial.py`). 둘 다 회사 범위 표다(`company_id`). 앱 역할은 읽기·넣기·고치기만 한다(지우지 못한다). 일감은 같은 회사 외래 키로 문서에 걸린다.

- `core_documents`: 문서 하나. 상태 `awaiting_upload ──▶ uploaded`. 저장소의 자리는 서버가 짓는다(`companies/<company_id>/documents/<key_id>/original`. 파일 이름은 표시용이고 키에 들어가지 않는다).
- `core_jobs`: 일감 하나. 상태 `queued ──▶ processing ──▶ done | failed`(재시도·이어받기는 `processing` 에서 다시 `processing`). 일감의 종류(`kind`)는 지금 `parse` 하나다.
- **넣지 않는 것**: 분해 결과의 본문, 서명된 주소, 토큰. `summary` 는 「작은 요약」이고 DB 가 크기를 막는다. 칸의 집합은 `core/tests/test_documents_models.py` 가 글자로 못 박는다.

**올림 확인이 믿는 것과 안 믿는 것.** 믿는 것은 저장소의 `head` 가 말한 크기와 ETag 다. 클라이언트의 「올렸다」는 말은 믿지 않는다. 만들 때 말한 크기(`sizeBytes`)는 올리기 주소의 서명 조건이 되고, 올림 확인이 `head` 의 크기와 견준다. 여러 번 불러도 된다: 일감은 하나로 남고, 끝나지 않은 일감을 큐에 다시 넣는다. 요청마다의 트랜잭션이 없으므로 거절은 쓰기 앞에서 한다(`core/service/services/documents.py` 의 머리 글).

**큐에 넣는 자리는 커밋된 뒤에만 불린다**(`transaction.on_commit`, `core/resources/queue.py`). 브로커에 못 닿아도 올림 확인은 200 이고 일감은 `queued` 로 남는다. 올림 확인을 다시 부르거나 `requeue_jobs` 가 메운다.

**서명 주소가 둘인 까닭.** 어댑터는 클라이언트를 둘 쥔다: 서버가 저장소에 묻는 주소(`S3_ENDPOINT`. compose 에서는 안쪽 이름)와, 올리기 주소를 서명하는 주소(`S3_PUBLIC_ENDPOINT`. 내 컴퓨터에서 닿는 주소). 서명에는 호스트 이름이 들어가 안쪽 이름으로 서명한 주소는 바깥에서 거절된다. 실제 S3 에서는 둘 다 비어 같은 AWS 주소가 된다.

**무효 조건과 안 한 것**

- 저장소의 바깥 동작은 로컬 저장소(Versity Gateway)에서만 잰 것이다. **실제 S3 에서는 재지 않았다**: 크기의 서명 조건을 강제하는가, 「없다」(404)와 「권한 없다」(403)가 어떻게 갈리는가.
- 로컬 저장소에서는 없는 버킷과 틀린 접근 키가 404 다 → 올림 확인이 409 `NOT_UPLOADED` 로 답한다(설정이 틀린 것이 「안 올라옴」으로 읽힌다).
- 주소의 수명 안에는 같은 주소로 다시 올릴 수 있다. 올림 확인 뒤에 바꿔치면 워커가 ETag 를 견주어 분해하지 않고 `failed`·`object_changed` 로 끝낸다.
- 브라우저에서 저장소로 바로 올리려면 저장소에 CORS 설정이 필요하다(안 했다).
- 없는 것: 지우기·보존 기간, 올리다 만 행과 객체의 정리, 멀티파트 올리기, 올리기 주소 다시 내주기, 내려받기 주소. 문서 목록과 판 사슬은 꼴만 있다(501).

### 워커와 큐 (Celery)

요청 밖에서 도는 일을 **큐 → 워커**로 돌린다. 지금 도는 일은 하나다: 올린 PDF 를 파서에 보내 분해한다(태스크 `jobs.parse`, `reconcile/tasks.py`). 로컬의 큐는 SQS 흉내이고 실제 SQS 에는 붙여 보지 않았다.

| 서비스(`compose.yaml`) | 무엇 |
|---|---|
| `worker-py` | `api-py` 와 **같은 이미지, 다른 명령**(Celery 워커, prefork 2). 환경은 `api-py` 의 것을 compose 앵커로 그대로 받는다(앱 역할의 DB 주소뿐). 호스트 포트도 healthcheck 도 없다(SQS 는 원격 제어 명령을 지원하지 않는다) |
| `queue` | SQS 와 같은 API 로 말하는 로컬 큐(ElasticMQ). 큐 `esg-jobs` 를 `docker/elasticmq.conf` 로 미리 만든다. **메모리에만 담는다**: 정본은 DB 의 `core_jobs` 이고 큐는 다시 채울 수 있다 |

```sh
# 일감의 상태(위 「문서 올리기」의 3번 뒤)
curl -s -H "$H" $API_PY/documents/$DOC | jq '.jobs[0] | {status, attempts, errorCode, summary, finishedAt}'
# 워커의 기록: 일감마다 끝을 적었는지, 잡지 않았는지 한 줄
docker compose logs --no-color --tail 20 worker-py
```

지은 PDF 로 일감이 `done` 으로 끝나고 요약의 키가 굳힌 집합인지는 통합 테스트 `tests_integration/test_worker_flow.py` 가 잰다.

**태스크가 하는 일.** 쪽지에는 회사 id 와 일감 id 뿐이다. 나머지는 표에서 읽는다(차례의 정본은 `reconcile/tasks.py` 의 머리 글).

1. **잡기**(트랜잭션 하나. `core/service/services/jobs.py` 의 `claim_job`): 그 회사의 일감 행을 `FOR UPDATE` 로 잠근 뒤 상태와 임대를 본다. 잡으면 `processing`·시도 +1·임대. 커밋한다.
2. **트랜잭션 밖에서** 저장소의 `get` 으로 원본을 받고, ETag 를 올림 확인 때의 것과 견준 뒤, 파서에 보낸다.
3. **끝내기**(둘째 트랜잭션. `finish_job`): 갱신의 조건은 「`processing` 이고 시도가 내 시도」다.

**일감이 끝나는 갈래**: `done`(요약과 문서의 sha256), `failed`(파서가 준 code 나 갈래 이름 — 다시 해도 안 되는 것, `object_changed`, `object_missing`, `attempts_exhausted`, 예상 밖 예외의 `internal` 등), 또는 끝나지 않고 다시 해 봄(저장소에 닿지 못함, 파서 `unavailable`, 소프트 시간 제한 — 이것도 시도를 쓴다). 갈래 표의 정본은 `reconcile/tasks.py` 의 머리 글이다.

**중복은 큐가 아니라 표에서 막는다.** 같은 일감의 쪽지는 여러 번 올 수 있다. 잡기가 행을 잠그고 상태와 임대를 보므로 끝은 한 번만 적힌다. 다만 한 번만 「돈다」가 아니다: 임대가 끝난 뒤 이어받으면 저장소·파서가 두 번 불릴 수 있다.

**다시 넣기.** 쪽지를 잃은 일감을 되살리는 길은 둘이다: 올림 확인을 다시 부른다, 관리 명령 `requeue_jobs` 를 돌린다.

```sh
docker compose exec -T api-py python manage.py requeue_jobs --tenant <회사 id> --dry-run   # 고르기만
docker compose exec -T api-py python manage.py requeue_jobs --tenant <회사 id>             # 큐에 넣는다
```

`--tenant` 가 필수다: 일감 표의 기본 매니저는 회사를 정하지 않은 조회를 거절한다. 회사를 가로질러 훑는 길이 없다.

**설정의 이름과 값**은 `config/celery.py` 의 `celery_conf` 한 곳에 이름으로 적었다(순수 테스트가 글자로 견준다). 시간의 차례(파서 < 파서 클라이언트 < 소프트 < 하드 < 임대 < visibility)와 기본값은 `config/env.py` 의 `JobSettings`·`BrokerSettings` 가 정본이다. 「어림」이라 적힌 값은 재서 정한 값이 아니다.

**★ 브로커 주소에는 늘 호스트가 있어야 한다.** 요청이 가는 끝점은 브로커 주소의 호스트에서만 온다. 호스트 없는 주소로는 큐 주소가 로컬이어도 **진짜 AWS 를 부른다**. 그래서 로컬의 주소 셋은 `compose.yaml` 에 글자로 적혀 있고(`.env` 로 바꾸지 못한다), 설정(`config/env.py`)이 그 꼴을 뜨기 전에 막는다.

```
CELERY_BROKER_URL  sqs://queue:9324                                  (호스트 = 끝점)
CELERY_QUEUE_URL   http://queue:9324/000000000000/esg-jobs
```

정식의 방향(이 저장소는 IAM 을 짜지 않았다): 인프라가 큐를 만들고, 앱의 권한은 `SendMessage`·`ReceiveMessage`·`DeleteMessage`·`ChangeMessageVisibility`·`GetQueueAttributes` 다.

**무효 조건과 안 한 것**

- **하드 시간 제한에 걸린 일감과 갈래 밖 예외는 `processing` 으로 남는다**(쪽지는 ack 된다). 임대가 끝난 뒤 `requeue_jobs --tenant` 를 돌려야 다시 잡힌다. 워커 프로세스가 죽은 경우는 큐의 재전달로 스스로 돌아온다.
- 워커를 갈아 끼우면(배포) 그 순간 넣은 쪽지가 visibility 뒤에야 다시 올 수 있다(잃지는 않는다).
- 다시 넣기는 **회사 하나씩**이고 주기적으로 돌리는 장치가 없다.
- 로컬의 큐는 메모리다. `queue` 가 다시 뜨면 쪽지가 사라진다(일감은 표에 남는다).
- **실제 SQS 에서 재지 않았다**(계정이 없다).
- 워커는 `api-py` 의 환경을 통째로 받는다(최소 권한이 아니다).
- 워커에 **LLM 을 부르는 태스크가 없다**. 실행(`/runs`)의 실행기도 없다(경로는 501).
- 브로커 설정 없이 띄운 워커는 끝난다. `api-py` 는 브로커 없이도 뜬다: 그때 일감은 `queued` 에 머문다.

### 일부러 안 한 것 · 미결

분해 결과의 저장, 실행(`/runs`)의 실행기와 진행률·취소, LLM 을 부르는 태스크, 올린 파일을 지우는 길과 보존 기간, 브라우저에서 저장소로 바로 올리기(저장소의 CORS), 진짜 EDK 연동, Django admin(`django.contrib.admin` 을 켜지 않았고 모듈에 `admin.py` 도 없다). LLM 호출 층과 계산 엔진은 서 있지만 **실제 공급사를 부르는 경로는 없다**(위 「LLM 호출 층」「Scope 3 후보 추리기와 분류」). 그리고:

- **access 토큰은 서버가 끊지 못한다.** 계정을 끄거나 비밀번호를 바꿔도 이미 낸 access 는 만료까지 통한다. refresh 는 DB 를 본다(`core/auth/bearer.py`·`core/auth/tokens.py` 의 머리 글).
- **옛 교환 쿠키 길이 아직 남아 있다.** 서버에 세션 목록이 없어 로그아웃은 쿠키를 지울 뿐이다. 다른 사이트에서 온 POST 에 쿠키가 실리지 않게 하는 것은 `SameSite=Lax` 하나다(`user/service/apis/auth.py`).
- **EDK 토큰 안의 이름(`tenant_id`·`role`·`name`)은 추정이다.** 진짜 EDK 가 무엇을 싣는지는 정해지지 않았다.
- **경로가 없는 모듈이 하나다**: `reconcile`.
- **`invalid_tables` 응답은 받은 값을 싣는다**(문장은 200자·20건까지. `inventory/service/apis/inventory.py`). 보안상 뺄지는 다시 본다.
- **데이터 검증의 방법**은 정해지지 않았다. `reconcile` 의 뒤 절반은 그 뒤의 일이다.
- **납품물의 오픈소스 라이선스 조건**은 확인 중이다. 기준정보 사본이 `unverified` 인 채 이미지에 실린다, `hypothesis` 는 dev 의존성에만 있다.

## 웹 (apps/web)

웹(apps/web)의 개발 글은 [`apps/web/README.md`](../apps/web/README.md)(폴더 규칙·경로·게이트)와 [`apps/web/docs/`](../apps/web/docs/)(부품별 글: 문서 뷰어·검토 표·서버 호출 클라이언트)에 있다.
