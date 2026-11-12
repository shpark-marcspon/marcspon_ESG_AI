# 마크스폰 ESG 공시 대응 AI 솔루션

ESG 공시 업무(온실가스 인벤토리 산정, 그린워싱 점검 등)를 돕는 AI 모듈과 그 바탕 서비스의 소스 저장소입니다.
마크스폰의 EDK 에 내장하지 않고, 별도 서비스로 띄워 단방향 API 로 잇는 구성입니다.

1. [무엇인가](#무엇인가)
2. [구조](#구조)
3. [갈아끼우는 구조](#갈아끼우는-구조)
4. [빠른 시작](#빠른-시작)
5. [설정](#설정)
6. [API](#api)
7. [의존성](#의존성)
8. [문서](#문서)
9. [알아 둘 것](#알아-둘-것)

---

## 무엇인가

AI 모듈 여섯(온실가스 인벤토리, 그린워싱 검출, 중대성평가 IRO, 데이터 검증, 영문번역, 보고서 작성)이 한 서비스 바탕 위에 섭니다.
모든 모듈이 같은 바탕을 씁니다. 바탕은 회사·사용자·사업장, 문서 올리기와 비동기 처리, LLM 호출 층(호출 기록·비용 상한·모의 공급사), 회사별 데이터 격리입니다.
아래 표는 지금 저장소에 있는 코드만 적습니다.

### 모듈별 상태

| 모듈 | 지금 상태 | 코드 위치 |
|---|---|---|
| 공통 바탕 (로그인·사용자·회사·사업장·문서·실행) | 아이디·비밀번호 로그인과 토큰 갱신·폐기, 첫 로그인 뒤 비밀번호 바꾸기가 있습니다. 운영 관리자의 고객사 사용자 관리(만들기·목록·비밀번호 초기화)가 있습니다. 사업장 등록·조회와 문서 올리기(서명된 주소)·상태 보기가 있습니다. 올린 PDF 는 워커가 파서에 보내 분해합니다. 실행(`/runs`)은 꼴만 있습니다(501) | `apps/api-py/esgapi/core/`, `apps/api-py/esgapi/user/`, `apps/api-py/esgapi/organization/` |
| 온실가스 인벤토리 — Scope 1·2 | 계산 엔진과 계산 경로(`POST /inventory/calc`)가 있습니다. 계산 경로는 결과를 저장하지 않습니다. 패키지에 실린 계수 표는 표본입니다 | `apps/api-py/esgapi/inventory/` |
| 온실가스 인벤토리 — Scope 3 | 배출계수 후보 추리기(낱말 검색. 생성 모델을 부르지 않습니다)와 그 경로가 있습니다. 분류 엔진과 입력 xlsx 시트 읽기가 있습니다. 분류 경로는 떠 있는 서버에서 늘 503 을 냅니다. 실제 모델 호출로 검증하지 않았습니다 | `apps/api-py/esgapi/inventory/` |
| 기준정보 (배출계수·GWP) | 배출계수 표 적재(관리 명령)와 조회·조립 경로가 있습니다. 전부 읽기 경로입니다 | `apps/api-py/esgapi/reference/` |
| 그린워싱 검출 | 받은 Colab 로직을 서버 흐름으로 옮겼습니다(추출 → 색인 → 판정 → 단어 빈도 → 문장 위치 → 엑셀). 기본 단어 경로가 있습니다. 결과·검토·비교·엑셀 경로는 꼴만 있습니다(501). 실제 모델 호출로 검증하지 않았습니다. 웹 화면 여섯(목록·소개·새 점검·처리 상태·결과·검토)은 목 저장소로 동작합니다. 서버에 잇지 않았습니다 | `apps/api-py/esgapi/greenwash/`, `apps/web/src/pages/greenwash-*/`, `apps/web/src/entities/greenwash/` |
| 데이터 검증 | 문서 분해 결과에서 값 후보를 뽑는 규칙과 분해 작업(워커)이 있습니다. 받은 Colab 의 계산 검토(Plan → 검토 → 인사이트 → 엑셀)를 서버 흐름으로 옮겼고, 문서 없이 실행(`POST /runs`, 모듈 `dataverify`)으로 돌리고 결과는 `GET /dataverify/runs/{run_id}/result`(결과 꼴 `dataverify.result@2`)로, 실행 목록은 `GET /dataverify/runs`(입력 출처·요약 `dataverify.digest@1`, `status` 여러 값·`mine` 거름)로 읽습니다. 실제 모델 호출로 검증하지 않았습니다 | `apps/api-py/esgapi/reconcile/`, `apps/api-py/esgapi/dataverify/` |
| 중대성평가 IRO | 받은 Colab 의 1부(규제·키워드·컨트로버시 조사)와 2부(환경·사회 영향·재무 영향·재무 Impact Pathway)를 한 실행 흐름으로 옮겼고(엑셀 둘), 문서 없이 실행(`POST /runs`, 모듈 `materiality`)으로 돌리고 결과는 `GET /materiality/runs/{run_id}/result`(결과 꼴 `materiality.result@2`)로, 실행 목록은 `GET /materiality/runs`(요약 `materiality.digest@1`의 2-1·2-2 줄 수, `status` 여러 값·`mine` 거름)로 읽습니다. 운영 관리자도 작업 회사로 실행·결과·엑셀을 다룹니다. 실제 모델 호출로 검증하지 않았습니다 | `apps/api-py/esgapi/materiality/` |
| 영문번역 | 코드 없음 | — |
| 보고서 작성 | 1차 뼈(RP1): 프로젝트(연도·이름)에 전년도 보고서 PDF 하나를 달고 목차 트리를 넣은 뒤 문서 없이 실행(`POST /runs`, 모듈 `drafting`)하면 쪽 → 목차 잎 → 잎마다 개조식 bullet(출처 = 블록·문장, 서버 코드가 대 봄)을 짓고, 결과는 `GET /drafting/runs/{run_id}/result`(결과 꼴 `drafting.bullets@3`)로 읽습니다. 목차를 고치면 앞 실행을 이어 받아 바뀐 잎만 다시 짓습니다. RAG·임베딩 없음. 실제 모델 호출로 검증하지 않았습니다 | `apps/api-py/esgapi/drafting/` |

---

## 구조

pnpm 워크스페이스(TypeScript)와 uv 프로젝트(Python)가 한 저장소에 있는 모노레포입니다.

| 경로 | 언어 | 역할 |
|---|---|---|
| `apps/api-py/` | Python (Django + django-ninja) | 본 API 서버입니다. 업무 모듈(`esgapi/<모듈>/`)과 공통 바탕(`esgapi/core/`)이 있습니다. 같은 이미지로 API(`api-py`), 마이그레이션(`migrate-py`), 작업 워커(`worker-py`, Celery)를 띄웁니다 |
| `apps/api-py/generated/` | — | API 계약(`apps/api-py/generated/openapi.json`)과, 그것에서 만든 프론트용 타입(`apps/api-py/generated/api.d.ts`)입니다 |
| `apps/web/` | TypeScript (React + Vite) | 웹 화면입니다. 그린워싱 화면 여섯(지금은 목 저장소), 문서 뷰어·검토 표 부품, 서버 호출 클라이언트, 개발용 데모 넷이 있습니다. 폴더 규칙은 `apps/web/README.md` 에 있습니다 |
| `services/parser/` | Python (FastAPI + pypdfium2) | PDF 를 섹션·문단·표와 글자 위치로 분해하는 서비스입니다. DB 에 닿지 않고 상태가 없습니다 |
| `packages/ui/`, `packages/common/`, `packages/tailwind-config/`, `packages/typescript-config/` | TypeScript | EDK 공유 키트(부품, 아이콘·색·폰트, Tailwind 설정, tsconfig)입니다. 받은 그대로 두고 고치지 않습니다 |
| `docker/` | — | 이미지 정의(`docker/api-py.Dockerfile`, `docker/parser.Dockerfile`), DB 초기화 스크립트(`docker/postgres-init.sh`), 로컬 큐 정의(`docker/elasticmq.conf`)입니다 |
| `compose.yaml` | — | 로컬에서 전체를 띄우는 구성입니다 |
| `infra/terraform/` | Terraform | AWS 배포 구성의 초안입니다. 적용한 적이 없습니다. 처음의 TypeScript 서버 뼈대 시절 구성을 기준으로 써서 api-py 에 맞게 다시 써야 합니다 |
| `scripts/` | Bash | 전체 검증(`scripts/verify.sh`) 등 저장소 단위 스크립트입니다 |
| `docs/` | — | 개발 문서(`docs/development.md`)입니다 |

### 로컬 구성 (compose)

`compose.yaml` 의 서비스는 여덟입니다.

| 서비스 | 하는 일 | 프로덕션에서 대응하는 것 |
|---|---|---|
| `api-py` | API 서버입니다. 호스트 포트는 `API_PY_PORT`(비우면 18081, `compose.yaml`)입니다. 웹 빌드도 같은 프로세스가 냅니다 | 컨테이너 서비스(로드밸런서 뒤) |
| `migrate-py` | DB 마이그레이션입니다. 한 번 돌고 끝납니다 | 배포 때 한 번 도는 작업 |
| `worker-py` | 비동기 작업 워커(Celery)입니다. `api-py` 와 같은 이미지입니다 | 컨테이너 서비스 |
| `parser` | PDF 분해 서비스입니다. 호스트에 포트를 열지 않습니다 | 워커 곁의 컨테이너 |
| `postgres` | PostgreSQL 입니다 | 관리형 PostgreSQL |
| `storage` | S3 호환 저장소(원본 파일)입니다 | S3 |
| `storage-cors` | 저장소 버킷에 CORS 규칙(웹 출처만 브라우저 PUT 허락)을 쓰고 끝납니다. `api-py` 는 이것이 성공한 뒤에 뜹니다 | 버킷의 CORS 설정(`infra/terraform/modules/storage`) |
| `queue` | SQS 호환 큐입니다 | SQS |

---

## 갈아끼우는 구조

AI 모듈은 계산 방법이나 프롬프트가 바뀔 수 있다고 보고 짰습니다. 바뀌는 단위마다 `<이름>@<판>` 꼴의 이름을 붙입니다.
새 방법은 새 판으로 더합니다. 옛 판은 그대로 두고, 어느 판을 쓸지만 바꿉니다.

모듈 폴더(`inventory`, `greenwash`)는 세 축과 흐름으로 나뉩니다.

| 자리 | 무엇이 있나 | 예 |
|---|---|---|
| 엔진(`engines`) | 계산·판정 로직입니다. 판마다 폴더가 따로 있습니다 | `apps/api-py/esgapi/inventory/engines/scope12/engine_1/`, `apps/api-py/esgapi/greenwash/engines/e0/` |
| 계약(`contracts`) | 밖으로 나가는 결과 꼴입니다. 칸을 바꾸면 새 판(`@2`)입니다 | `scope12.result@2`, `greenwash.result@1` (`apps/api-py/esgapi/inventory/contracts/shapes.py`, `apps/api-py/esgapi/greenwash/contracts/shapes.py`) |
| 도구(`tools`) | 판과 무관한 도구입니다 | `apps/api-py/esgapi/inventory/tools/xlsx_reader.py`, `apps/api-py/esgapi/greenwash/tools/coordinates.py` |
| 흐름(`flows`) | 엔진과 계약을 잇는 처리 순서 한 벌입니다 | `scope12.engine@1`, `scope3.llm-first@1`, `greenwash.colab@E0` |

- 규칙은 세 줄입니다. 엔진은 계약을 모릅니다. 계약은 엔진을 모릅니다. 둘을 잇는 것은 흐름뿐입니다. `apps/api-py/.importlinter` 의 계약이 이 규칙을 기계로 지킵니다.
- 모듈의 기본 흐름은 흐름 등록 파일의 `DEFAULTS` 한 줄로 고릅니다(`apps/api-py/esgapi/inventory/flows/registration.py`, `apps/api-py/esgapi/greenwash/flows/registration.py`).
- 프롬프트도 판이 있습니다. 이름 `<모듈>/<이름>@<판>` 이 파일 `esgapi/<모듈>/prompts/<이름>/<판>.md` 에 대응합니다(예: `greenwash/detect@1`, `inventory/scope3-classify@1`). 호출 기록에 판이 남습니다.
- 판은 크기를 견주지 않는 표지입니다. 그린워싱의 `E0` 은 받은 Colab 을 그대로 옮긴 판입니다.
- 흐름을 실제 요청으로 돌리는 실행기는 없습니다. 흐름은 지금 시험에서만 돕니다.

폴더 지도, 규칙의 기계, 다음 판을 넣는 법은 모듈 README 가 정본입니다: [`apps/api-py/esgapi/inventory/README.md`](apps/api-py/esgapi/inventory/README.md), [`apps/api-py/esgapi/greenwash/README.md`](apps/api-py/esgapi/greenwash/README.md).

---

## 빠른 시작

### 필요한 도구

| 도구 | 판 | 어디에 |
|---|---|---|
| Docker (Compose 포함) | — | 서버 전체를 띄울 때 |
| Node.js | 22.22.2 이상(`apps/web/package.json` 의 `engines`. 뿌리 `package.json` 은 22 이상) | TypeScript 쪽과 `scripts/verify.sh` |
| pnpm | 10.28.1(`package.json` 의 `packageManager`. `corepack enable` 로 켭니다) | TypeScript 쪽 |
| Python | 3.13(`apps/api-py/pyproject.toml` 의 `requires-python`) | API 서버·파서의 테스트를 컨테이너 밖에서 돌릴 때 |
| uv | 저장소에 고정한 판이 없습니다. 이미지 안에서는 0.7.13 입니다(`docker/api-py.Dockerfile`) | Python 의존성 설치와 테스트 |

### 1. 설정 파일

```sh
cp .env.example .env
```

`.env.example` 의 비밀번호와 키는 로컬 컨테이너끼리만 쓰는 가짜 값입니다. `.env` 는 git 에 넣지 않습니다.
포트가 다른 프로그램과 겹치면 `.env` 의 `*_PORT` 값만 바꿉니다.

### 2. 서버 띄우기

`API_PY_PORT` 를 바꿨다면 아래 18081 도 그 값으로 바꿉니다.

```sh
docker compose up -d --build --wait         # 이미지를 짓고, 전부 준비될 때까지 기다립니다
docker compose ps -a                        # migrate-py·storage-cors 는 Exited (0), 나머지 여섯은 running 이면 됩니다
curl -s http://localhost:18081/api/healthz  # 살아 있음
curl -s http://localhost:18081/api/readyz   # DB 에 닿음
```

API 의 경로는 전부 `/api` 아래에 있습니다. 포트는 `.env` 의 `API_PY_PORT` 입니다.

내릴 때:

```sh
docker compose down       # 컨테이너만 지웁니다. 데이터(볼륨)는 남습니다
docker compose down -v    # 데이터까지 지웁니다
```

DB 볼륨이 예전 판에서 만들어졌다면 `docker compose down -v` 뒤에 다시 띄웁니다. DB 초기화 스크립트는 빈 볼륨에서 한 번만 돕니다.

### 3. 초기 데이터

회사 등록과 배출계수 적재는 관리 명령으로 합니다. 둘 다 주인 역할로 도는 `migrate-py` 컨테이너에서 돌립니다.

```sh
# 회사 하나 등록 (예시 값)
docker compose run --rm -e DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate migrate-py \
  python manage.py seed_company --name '예시 회사' --business-licence-number 000-00-00001 --subdomain tenant-a

# 저장소에 실린 배출계수 사본과 대응표 적재(표본입니다. Scope 3 후보는 들어 있지 않습니다)
docker compose run --rm migrate-py python manage.py import_factors
```

계정은 `api-py` 컨테이너에서 만듭니다(첫 운영 관리자, 고객사 사용자):

```sh
docker compose exec api-py python manage.py create_user --admin --username <아이디> --name <이름>
docker compose exec api-py python manage.py create_user --company tenant-a --username <아이디> --name <이름>
```

비밀번호는 명령줄 인자로 받지 않고 입력으로 두 번 묻습니다(`--password-stdin` 이면 표준 입력 한 줄).
고객사 사용자는 로그인(`POST /auth/login`) 본문에 회사의 `companySubdomain`(위 예에서는 `tenant-a`)을 함께 보냅니다. 운영 관리자는 넣지 않습니다.
만든 계정은 첫 로그인 뒤 비밀번호를 바꿔야 합니다. 로그인부터 계산까지 이어지는 예는 `docs/development.md` 의 「손으로 따라가기」에 있습니다.

### 4. 웹 띄우기

「2. 서버 띄우기」를 마치면 웹도 이미 `http://localhost:18081/` 에 떠 있습니다. `api-py` 이미지를 지을 때 웹을 소스에서 빌드해 넣고(`docker/api-py.Dockerfile`), api-py 가 그것을 API 와 같은 주소에서 내줍니다. 웹 코드를 고친 뒤에는 `docker compose up -d --build` 로 이미지를 다시 짓습니다.

개발할 때는 개발 서버를 띄웁니다. 고친 코드가 바로 반영되고, 개발용 데모(`/dev/*`)가 열립니다. 개발 서버에는 Docker 가 필요 없습니다. 필요한 Node.js·pnpm 판은 위 「필요한 도구」 표에 있습니다.

```sh
pnpm install --frozen-lockfile     # 저장소 뿌리에서 한 번
pnpm --filter @esg/web dev         # http://localhost:15173/ 에 뜹니다. 포트가 겹치면 WEB_PORT=<포트> 를 앞에 붙입니다
```

- ★ 개발 서버는 저장소 뿌리의 `.env` 를 읽지 않습니다(`apps/web/vite.config.ts` 는 프로세스 환경의 `WEB_PORT` 만 봅니다). 브라우저가 서명한 주소로 저장소에 파일을 올리려면 개발 서버의 출처가 저장소의 CORS 허락 출처(compose 의 `storage-cors`, 기본 localhost·127.0.0.1 × `WEB_PORT`·`API_PY_PORT`)에 들어야 합니다. 워크트리에서는 `.env` 의 `WEB_PORT` 가 15173 이 아니라서 맨 `pnpm --filter @esg/web dev` 는 15173 에 떠 올리기가 막힙니다. 늘 `WEB_PORT=$(sed -n 's/^WEB_PORT=//p' .env | grep . || echo 15173) pnpm --filter @esg/web dev` 로 띄웁니다(`.env` 에 `WEB_PORT` 가 없으면(이 밴드 전에 만든 main·워크트리) 15173. 빈 값이면 vite 가 포트 0 에 뜹니다). 다른 출처를 허락하려면 `.env` 의 `STORAGE_CORS_ORIGINS` 를 적고 `docker compose up -d` 를 다시 합니다.
- 개발 서버는 `/api` 로 시작하는 요청을 접두 그대로 api-py 로 넘깁니다. 넘길 곳은 `API_PY_ORIGIN` 이고 기본은 `http://127.0.0.1:18081` 입니다(`apps/web/vite.config.ts`). `API_PY_PORT` 를 바꿨다면 `API_PY_ORIGIN=http://127.0.0.1:<그 포트>` 를 같이 줍니다.
- 주소 `/` 는 그린워싱 화면(`/greenwash`)으로 넘어갑니다. 그린워싱 화면은 목 저장소로 동작하고, 서버를 부르지 않습니다.
- 개발용 데모 넷(`/dev/viewer`, `/dev/table`, `/dev/api`, `/dev/parts`)은 개발 서버에서만 열립니다. 빌드 결과에는 들지 않습니다(`VITE_DEMOS=1` 로 빌드했을 때만 듭니다).
- 빌드 결과(`apps/web/dist/`)는 `pnpm --filter @esg/web build` 로 만듭니다. compose 밖에서 api-py 를 돌리면서 그것을 내주게 하는 설정은 아래 「설정」 표의 `WEB_DIST_DIR` 줄입니다(이미지 안에서는 이미지가 정합니다).

### 5. 테스트와 검증

```sh
scripts/verify.sh            # 전량: 깨끗한 상태에서 이미지를 짓고 띄워 업무·보안·통합 층까지. 끝 줄 VERIFY=PASS
scripts/verify.sh --fast     # 컨테이너 없이 도는 단계만. 끝 줄 VERIFY_FAST=PASS
scripts/verify.sh --plan     # 돌리지 않고 단계 이름만
apps/web/scripts/verify.sh   # 웹의 게이트
```

전량은 같은 compose 프로젝트의 컨테이너와 볼륨(데이터)을 지우고 시작하고, 끝나면 다시 지웁니다. 「3. 초기 데이터」에서 넣은 것도 사라집니다.
단계마다 `EXIT=` 줄이 나옵니다. 단계 목록은 `scripts/verify.sh` 의 머리 글이 정본입니다.

Python 쪽을 따로 돌릴 때:

```sh
cd apps/api-py
uv sync --frozen
uv run ruff check . && uv run pyright
uv run pytest -q -m "not django_db and not security"   # 순수 층(컨테이너 없이)
scripts/test-business.sh -n 2                          # 업무 층. 컨테이너가 떠 있어야 합니다
scripts/test-security.sh                               # 보안 층. 컨테이너가 떠 있어야 합니다
scripts/test-integration.sh                            # 통합. export EDK_JWT_PUBLIC_KEY="$(uv run python scripts/dev_edk.py public-key)" 한 뒤 띄운 컨테이너가 있어야 합니다(docs/development.md 「Python API」의 「띄우는 법」)
```

파서의 테스트는 뿌리에서 `uv run --project services/parser --frozen pytest -q services/parser` 로 돌립니다.

---

## 설정

설정은 환경 변수로만 받습니다. 목록과 로컬용 값은 [`.env.example`](.env.example) 에, 컨테이너에 넣는 꼴은 `compose.yaml` 에 있습니다.
필수 값이 빠지면 서버가 뜨기 전에 빠진 것을 모아 알리고 멈춥니다. 필수는 `DATABASE_URL_PY`, `EDK_JWT_PUBLIC_KEY`, `EDK_JWT_AUDIENCE`, `EDK_JWT_ISSUER`, `SESSION_SECRET`, `SESSION_TTL_SECONDS` 여섯입니다.
`compose.yaml` 은 `SESSION_SECRET` 에 기본값을 두지 않습니다. `.env` 에 없으면 `docker compose` 가 시작 전에 멈춥니다. `.env.example` 의 값은 로컬 전용이라 서버가 뜰 때 경고를 냅니다. 로컬 밖에서는 무작위 32바이트 이상의 값을 넣습니다.

| 묶음 | 대표 변수 | 비고 |
|---|---|---|
| 포트 | `API_PY_PORT`, `POSTGRES_PORT`, `STORAGE_PORT` | 호스트에 여는 포트입니다 |
| DB | `POSTGRES_*`, `APP_DB_PASSWORD`, `DATABASE_URL_PY` | 주인 역할(마이그레이션)과 앱 역할(요청 처리)을 나눕니다 |
| 파일 저장소 | `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT`, `MAX_UPLOAD_BYTES` | 로컬은 S3 호환 컨테이너, 프로덕션은 S3 입니다 |
| 작업 큐 | `CELERY_*`, `JOB_*` | 로컬의 큐 주소는 `compose.yaml` 에 글자로 적혀 있습니다 |
| 토큰 | `SESSION_SECRET`, `SESSION_TTL_SECONDS` | 로그인 토큰의 서명 키와 옛 교환 쿠키의 수명입니다 |
| EDK 토큰 | `EDK_JWT_PUBLIC_KEY`, `EDK_JWT_AUDIENCE`, `EDK_JWT_ISSUER` | 옛 토큰 교환(`POST /auth/exchange`)의 검증 값입니다 |
| LLM | `LLM_OPENAI_API_KEY`, `LLM_ANTHROPIC_API_KEY`, `LLM_GEMINI_API_KEY`, `LLM_MODELS_FILE`, `LLM_LOG_SINK`, `LLM_RPM` | 전부 선택입니다 |
| 실 공급사 전환 | `LLM_RUN_MODE`, `LLM_RUN_MAX_USD` | 비우면 실행기는 모의 공급사만 씁니다. `live` 로 켜는 조건은 `docs/development.md` 의 「실 공급사 전환 점검표」입니다 |
| 영문번역 금액 상한 | `TRANSLATION_RUN_MAX_USD` | 선택. 기본 5(USD) — 실행 하나의 호출 비용 위끝이 넘으면 공급사 전에 `over_budget`(`MARC-ENT-262` 한 번 5 USD) |
| 파서 | `PARSER_URL`, `PARSER_TIMEOUT_MS` | 비우면 기본값입니다 |
| 웹 정적 서빙 | `WEB_DIST_DIR` | 비우면 꺼집니다. 이미지는 웹 빌드 자리를 넣습니다 |

변수마다의 뜻과 읽는 파일은 `docs/development.md` 의 「환경 변수」에 있습니다. 기본값은 `apps/api-py/esgapi/config/env.py` 가 정본입니다.

### LLM 키 없이 돌리기

LLM 키는 전부 선택입니다. 키를 비워 두면 서버는 그대로 뜨고, 모의 공급사와 dry-run 만 돕니다.
키가 없는 공급사의 모델을 부르면 공급사를 부르지 않고 이름 있는 오류(`LiveSetupError`)로 끝납니다.

```sh
# 공급사를 부르지 않고, 조립된 요청과 어림 토큰·비용만 봅니다
docker compose exec api-py python manage.py llm_call --prompt core/hello@1 --var name=김 --route light --dry-run
# 모의 공급사가 미리 정한 답을 돌려줍니다
docker compose exec api-py python manage.py llm_call --prompt core/hello@1 --var name=김 --route mock --mock-text '{"ok":true}'
```

실제 공급사 호출은 비용이 듭니다. 그 공급사의 키와 호출 비용 상한(`--limit-usd`)이 둘 다 있어야 부릅니다.
모델 ID·단가·경로는 코드가 아니라 자료 파일 `apps/api-py/esgapi/core/llm/data/models.json` 에 있습니다. 그 출처와 확인 일자는 `apps/api-py/esgapi/core/llm/data/README.md` 에 있습니다.

진짜 키는 `.env` 에만 적고 `.env.example` 이나 저장소에는 적지 않습니다.

---

## API

### 계약 (OpenAPI)

- 파일: [`apps/api-py/generated/openapi.json`](apps/api-py/generated/openapi.json) — 코드에서 뽑은 계약입니다. 코드와 어긋나면 테스트(`apps/api-py/esgapi/config/tests/test_api_contract.py`)가 실패합니다.
- 프론트용 타입: `apps/api-py/generated/api.d.ts` 입니다. `apps/api-py/scripts/gen-ts-types.sh` 로 다시 만듭니다.
- 계약의 paths 키에는 접두가 없고, servers 의 `/api` 가 접두를 말합니다. 호스트에서 부르는 주소는 `http://localhost:18081/api/<경로>` 입니다.
- 서버를 띄운 뒤: `http://localhost:18081/api/docs`(문서 화면), `http://localhost:18081/api/openapi.json`(계약).

### 인증

- `POST /auth/login` 이 access·refresh 토큰 짝을 냅니다. 회사 경로는 `Authorization: Bearer <access>` 머리로 부릅니다.
- 회사·사용자 id 는 토큰에서만 옵니다. 요청 본문·쿼리·헤더로 받지 않습니다.
- EDK 토큰을 세션 쿠키로 바꾸는 옛 교환(`POST /auth/exchange`) 길이 아직 남아 있습니다. 회사 경로는 Bearer 머리가 없을 때만 그 쿠키를 봅니다.

### 경로 묶음

경로는 32, 동작은 37 입니다(센 곳: `apps/api-py/scripts/readme_audit.py facts`). 동작마다의 표는 `docs/development.md` 의 「경로 목록」에 있습니다.

| 묶음 | 경로 | 상태 |
|---|---|---|
| 상태 확인 | `GET /healthz`, `GET /readyz` | 있습니다(인증 없음) |
| 인증 | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/revoke`, `POST /auth/exchange`, `POST /auth/logout` | 있습니다(`/auth/exchange`·`/auth/logout` 은 옛 쿠키 길) |
| 사용자 | `GET /me`, `GET /users/me`, `POST /users/me/password`, `GET /users`, `POST /users`, `POST /users/{user_id}/password-reset` | 있습니다(`/users` 와 비밀번호 초기화는 운영 관리자, `/me` 는 옛 쿠키 길) |
| 사업장 | `GET /sites`, `POST /sites` | 있습니다 |
| 기준정보 | `GET /reference/sources`, `GET /reference/factors`, `POST /reference/assemble`, `POST /reference/assemble-electricity` | 있습니다(읽기만) |
| 인벤토리 | `POST /inventory/calc`, `POST /inventory/scope3/shortlist`, `POST /inventory/scope3/classify` | 있습니다(저장하지 않음). `classify` 는 떠 있는 서버에서 늘 503 `LLM_NOT_CONFIGURED` 입니다 |
| 문서 | `POST /documents`, `POST /documents/{document_id}/confirm`, `GET /documents/{document_id}` | 있습니다. 만들기의 `reportYear`·`previousDocumentId` 칸에 값이 있으면 501 입니다 |
| 문서 | `GET /documents`, `GET /documents/{document_id}/versions` | 꼴만 있습니다(501) |
| 실행 | `POST /runs`, `GET /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/files/{name}` | 꼴만 있습니다(501) |
| 그린워싱 | `GET /greenwash/runs/{run_id}/result`, `GET /greenwash/runs/{run_id}/review`, `PUT /greenwash/runs/{run_id}/review`, `GET /greenwash/compare`, `GET /greenwash/runs/{run_id}/report` | 꼴만 있습니다(501) |
| 그린워싱 | `GET /greenwash/terms/default` | 있습니다 |

올린 PDF 가 워커와 파서를 거쳐 `done` 으로 끝나는 길은 통합 테스트 `apps/api-py/tests_integration/test_worker_flow.py` 가 잽니다.

### 오류 꼴

오류 응답은 한 가지 꼴입니다(`apps/api-py/esgapi/core/exceptions.py`).

```
{"error": {"code": "<대문자 이름>", "message": "<문장>", "fields": <칸별 문장 | null>, "legacyCode": <옛 소문자 이름 | null>}}
```

프론트는 `code` 로 가릅니다. 자주 만나는 것은 다음과 같습니다. 전체 표는 `docs/development.md` 의 「오류의 꼴과 code」에 있습니다.

| 상황 | 상태 | `code` |
|---|---|---|
| 요청의 꼴이 틀렸습니다(`fields` 에 칸마다 까닭) | 422 | `VALIDATION_ERROR` |
| Bearer 도 쿠키도 없습니다 | 401 | `NO_SESSION` |
| Bearer 토큰이 틀렸습니다 | 444 | `TOKEN_NOT_VALID` |
| 첫 로그인 뒤 비밀번호를 아직 바꾸지 않았습니다 | 403 | `PASSWORD_CHANGE_REQUIRED` |
| 권한 표가 그 주체를 받지 않습니다 | 403 | `FORBIDDEN` |
| 없는 경로이거나 그런 것이 없습니다(다른 회사의 것도 같은 답) | 404 | `NOT_FOUND` |
| 꼴만 있는 동작입니다 | 501 | `NOT_IMPLEMENTED` |

---

## 의존성

- 판은 잠금 파일이 고정합니다. Python 은 `apps/api-py/uv.lock`·`services/parser/uv.lock` 이 고정하고, `apps/api-py/pyproject.toml`·`services/parser/pyproject.toml` 에도 `==` 로 적습니다. TypeScript 는 `pnpm-lock.yaml` 이 고정합니다. `package.json` 에는 범위 판이 남아 있습니다.
- 설치는 잠금 파일대로만 합니다(`uv sync --frozen`, `pnpm install --frozen-lockfile`).
- 받은 코랩의 로직을 옮긴 모듈은 우선 코랩이 쓰던 라이브러리와 판을 그대로 씁니다. 방식이 확정되거나 바뀌면 정리합니다.
  - 지금 그 몫은 그린워싱이 쓰는 일곱입니다: `pypdf`, `langchain-text-splitters`, `langchain-core`, `numpy`, `tiktoken`, `jsonschema`, `openpyxl`. 판은 `apps/api-py/pyproject.toml` 의 그 주석 아래에 있습니다.
  - Scope 3 코랩 흐름(`scope3.colab@157`)은 `pandas`·`rapidfuzz` 를 더 쓰고 `numpy`·`openpyxl` 은 같이 씁니다.
  - 영문번역(`translation`)은 Word 를 읽고 쓰는 데 `python-docx` 와 그것이 끄는 `lxml` 을 씁니다.

---

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/development.md`](docs/development.md) | 상세 개발 문서입니다. 요청이 지나는 길, 모듈 지도, 경로 목록, 오류, 환경 변수 전체, 테스트 층, 모듈별 세부 동작, 일부러 하지 않은 것 |
| [`services/parser/README.md`](services/parser/README.md) | 파서의 HTTP 약속, 상한, 가져온 코드의 대응표와 라이선스 기록 |
| [`services/parser/schemas/README.md`](services/parser/schemas/README.md) | 파서 산출 스키마 |
| [`infra/README.md`](infra/README.md) | AWS 배포 구성 초안(적용 전)과 확인한 범위 |
| [`apps/api-py/esgapi/inventory/README.md`](apps/api-py/esgapi/inventory/README.md) | 인벤토리의 폴더 지도, 규칙 세 줄, 다음 판 넣는 법 |
| [`apps/api-py/esgapi/greenwash/README.md`](apps/api-py/esgapi/greenwash/README.md) | 그린워싱의 폴더 지도, 규칙 세 줄, 다음 판 넣는 법 |
| [`apps/api-py/esgapi/reference/data/README.md`](apps/api-py/esgapi/reference/data/README.md) | 저장소에 실린 배출계수 사본의 출처 |
| [`apps/api-py/esgapi/core/llm/data/README.md`](apps/api-py/esgapi/core/llm/data/README.md) | 모델 ID·단가 자료의 출처와 확인 일자 |
| [`apps/api-py/esgapi/inventory/data/README.md`](apps/api-py/esgapi/inventory/data/README.md) | 인벤토리에 실린 표본 표의 출처 |
| [`apps/api-py/esgapi/inventory/prompts/README.md`](apps/api-py/esgapi/inventory/prompts/README.md) | 인벤토리의 프롬프트 |

| 웹 문서 | 내용 |
|---|---|
| [`apps/web/README.md`](apps/web/README.md) | 웹의 폴더 규칙(층 다섯), 새 파일 자리, 경로 표, 게이트 |
| [`apps/web/docs/doc-viewer.md`](apps/web/docs/doc-viewer.md) | 문서 뷰어 부품: 입력 계약, 층, 실제 자료를 붙이는 법, 글자 자리 |
| [`apps/web/docs/review-table.md`](apps/web/docs/review-table.md) | 검토 표 부품: 입력의 꼴, 전이표, 계산 실패, UI 라이브러리를 바꾸는 순서 |
| [`apps/web/docs/api-client.md`](apps/web/docs/api-client.md) | 서버 호출 클라이언트: 타입이 오는 길, 실패의 갈래, 무효화 |

---

## 알아 둘 것

- 코드 주석, 커밋 제목, 문서에 보이는 `MARC-…` 번호는 공급사 내부의 작업 기록 번호입니다. 이 저장소만으로 읽는 데에는 필요하지 않습니다.
- 이 저장소는 공급사 작업 저장소를 그대로 올린 것입니다.
- 코드에 대한 의견은 이 레포의 GitHub 이슈로 받습니다.
- main 에 병합될 때마다 반영합니다.
- 비공개 저장소이며 이용 조건은 계약을 따릅니다.
- 오픈소스 의존성은 판을 고정했습니다. 서드파티 라이선스 목록은 정리 중입니다.
- 배출계수 사본(`apps/api-py/esgapi/reference/data/factors.kr.jsonl`)의 이용 조건은 확인 중입니다.
- Scope 3 배출계수 책(`apps/api-py/esgapi/inventory/data/scope3/scope3-factor-book.xlsx`)의 이용 조건은 확인 중입니다.
