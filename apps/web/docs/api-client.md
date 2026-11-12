# 서버 호출 클라이언트 (shared/api)

**연습용 선택이고 패칭 컨벤션이 아니다.** `apps/web` 이 Python API(`apps/api-py`)를 부르는 길 하나(`src/shared/api/`)와, 그 길을 쓰는 데모 화면 하나(`src/pages/demo-api/`, 주소 `/dev/api`)다. 폴더 이름, 실패의 갈래, 무효화 정책, `QueryClient` 의 기본값은 화면 하나를 서버에 이어 보려고 고른 것이다. 문서 뷰어와 검토 표는 서버를 부르지 않는다.

경로는 `apps/web/` 기준이다. 폴더 규칙(층 다섯, 칸)은 [`../README.md`](../README.md) 에 있다. 잰 값과 개발 기록은 끝의 [기록](#기록)에 있다.

## 무엇을 들였나

| 꾸러미 | 왜 |
|---|---|
| `openapi-fetch` | 계약 타입(`paths`)을 입힌 `fetch`. 경로·요청 칸·응답 칸이 타입으로 묶인다. 런타임 코드가 작다 |
| `openapi-react-query` | 위의 것을 TanStack Query 의 조회·변경으로 감싼다. 키를 손으로 적지 않는다 |
| `@tanstack/react-query` | 서버 상태의 캐시와 다시 받기 |

판은 전부 캐럿 없이 고정이다(`apps/web/package.json`). 들일 때 확인한 판·라이선스는 [기록](#기록)에 있다.

## 띄우는 법

```sh
# 1. api-py 를 띄운다(저장소 뿌리 docs/development.md 의 「Python API (apps/api-py)」 절). 회사를 등록하고 그 회사의 고객사 사용자를 만든다
#    (docs/development.md 「손으로 따라가기」의 1 회사 등록·2 고객사 사용자 만들기).
#    교환에 붙여넣을 EDK 토큰은 apps/api-py/scripts/dev_edk.py token 으로 만든다(쓰는 법은 그 파일 머리말. api-py 는 dev_edk.py public-key 의 공개키로 떠 있어야 한다).
# 2. web 을 띄운다. API_PY_ORIGIN 은 api-py 의 주소다(안 주면 http://127.0.0.1:18081).
API_PY_ORIGIN=http://127.0.0.1:18081 pnpm --filter @esg/web dev
# 3. 브라우저로 http://localhost:15173/dev/api 에 가서 토큰을 입력칸에 붙여넣고 「교환」을 누른다.
```

데모 경로(`/dev/*`)는 개발 서버이거나 `VITE_DEMOS=1` 로 빌드했을 때만 있다(`src/app/router.tsx`).

화면은 위에서 아래로 한 흐름이다: 교환(`POST /auth/exchange`) → 내 세션(`GET /me`) → 사업장(`GET /sites`, `POST /sites`) → 계산(`POST /inventory/calc`) → 기준정보(`GET /reference/factors?limit=5`) → Scope 3 후보 추리기(`POST /inventory/scope3/shortlist`). 메뉴도 디자인도 없다. 계산과 후보 추리기의 요청은 `docs/development.md` 「손으로 따라가기」의 6(인벤토리 계산)·8(Scope 3 후보 추리기)의 예시 그대로다(`src/pages/demo-api/examples.ts`). 기준정보에 낱줄이 보이려면 계수를 먼저 들인다(`docs/development.md` 「손으로 따라가기」의 7).

**브라우저는 api-py 를 직접 부르지 않는다.** 쪽과 같은 출처의 `/api/…` 로 부르고 Vite 의 프록시가 그 주소 그대로(접두를 떼지 않고) api-py 로 넘긴다(`vite.config.ts` 의 `API_PROXY_KEY`. `dev` 와 `preview` 둘 다). api-py 도 서버 안에서 `/api` 아래에 API 를 둔다. 프록시 키는 경계가 있는 정규식이라 `/apix` 나 `/api-py` 는 타지 않는다(`tools/vite-config.test.ts`). api-py 에는 CORS 가 없고, 같은 출처여야 세션 쿠키가 실린다. 프록시는 Vite 의 것이라 **빌드한 정적 파일만 다른 서버에 올리면 이 길이 없다**(그때는 그 서버가 `/api/` 를 넘기거나, api-py 가 빌드 결과를 같이 낸다 — `WEB_DIST_DIR`, `apps/api-py/esgapi/config/settings/base.py`).

**토큰은 붙여넣기로만 받는다.** 연습용 개인키와 서명 코드는 web 에 없다. 화면은 토큰을 교환 요청의 본문에만 싣고, 교환이 끝나면(성공이든 거절이든) 입력칸을 비우고 그 변경의 기록을 캐시에서 뺀다. TanStack Query 는 변경의 변수(여기서는 토큰이 든 본문)를 변경 기록에 5분쯤 들고 있기 때문이다. 세션 쿠키는 `HttpOnly` 라 화면이 읽지 못한다. 「세션이 있는가」는 `GET /me` 의 답으로만 안다. 이 화면은 교환이 낸 세션 쿠키로 부르고, `Authorization` 머리는 싣지 않는다.

## 타입이 오는 길

`apps/api-py/generated/api.d.ts`(커밋된 계약 타입) 하나를 `src/shared/api/model/` 이 상대 경로의 `import type` 으로 가져온다. 타입 import 는 빌드에서 지워지므로 번들에 들지 않는다. 그 파일을 가져오는 곳은 `src/shared/api/` 안뿐이고(구조 규칙 시험 `src/app/guards/layers.test.ts` 가 지킨다), 화면은 `src/shared/api/index.ts` 가 다시 내보낸 타입(`Schemas["CalcIn"]` 같은)을 쓴다.

계약이 바뀌면 `pnpm --filter @esg/web typecheck` 가 그 동작을 부르는 줄에서 빨개진다. 무엇이 빨개지고 무엇이 초록인지 계약 타입을 한 줄씩 바꿔 가며 잰 표는 [기록](#기록)에 있다. 요점은 둘이다.

- 경로, 요청의 칸, 화면이 읽는 응답의 칸, 갈래를 가르는 글자(후보 추리기 답의 `status: "no_candidates"`)가 바뀌면 빨강이다.
- `operationId` 의 이름, `api.d.ts` 가 `openapi.json` 과 어긋남, 화면이 읽지 않는 칸은 **web 이 모른다.** 앞의 둘은 api-py 의 계약 테스트(`esgapi/config/tests/test_api_contract.py`)가 지킨다.

생성된 타입은 서버에서 기본값이 있는 칸도 필수로 낸다(`CalcIn.groupBy`). 예시 요청에는 서버의 기본값을 그대로 적었다.

## 변경 뒤의 무효화

변경(`POST /sites`, 교환)이 성공하면 `["get"]` 으로 시작하는 조회를 전부 무효로 표시한다(`createInvalidatingMutation`). openapi-react-query 의 키가 `["get", 경로]` 또는 `["get", 경로, init]` 이라 앞부분 하나로 조회 전부가 걸린다. 화면은 만들기의 응답을 목록에 덧붙이지 않고 다시 받은 것만 그린다. 변경이 실패하면 무효화하지 않는다. 계산과 후보 추리기는 `POST` 이지만 서버의 상태를 바꾸지 않으므로(저장하지 않는다) 무효화하지 않는 변경으로 부른다.

한계: 묶음을 고르지 않는다. 사업장을 하나 만들어도 기준정보까지 다시 받는다. 화면과 조회가 늘면 낭비가 된다. 낙관적 갱신이 없다.

## 실패의 갈래

`src/shared/api` 를 거친 호출은 **2xx 가 아니면 반드시 실패**이고, 던져지는 것은 셋 가운데 하나다(`src/shared/api/model/failure.ts`).

| 갈래 | 언제 | 화면 |
|---|---|---|
| `{kind:"api", status, code, message, fields}` | 서버가 정한 꼴 `{error:{code,message,fields,legacyCode}}` 로 거절(401 `NO_SESSION`, 403 `FORBIDDEN` …). `code` 는 대문자 이름이다. `fields` 는 422 `VALIDATION_ERROR` 의 칸 오류이고 그 밖에는 빈 객체다 | `code` 와 `message` 를 글자로 |
| `{kind:"unexpected", status, body?}` | 2xx 가 아닌데 그 꼴이 아니다: 글자 본문, 빈 본문 | 「서버에 닿지 못했다」와 상태 코드 |
| `{kind:"network"}` | 답을 받지 못했다 | 「서버에 닿지 못했다」 |

따로 가르는 까닭: 이 라이브러리 조합은 본문이 빈 실패를 실패로 잡지 못한다. `Content-Length: 0` 인 502 는 조회에서 `null` 로 성공하고, 길이 없이 chunked 로 빈 502 는 변경에서 성공한다. 둘째가 Vite 의 프록시가 api-py 에 닿지 못했을 때의 답이다(`502`, `Content-Type: text/plain`, `Transfer-Encoding: chunked`, 본문 없음). 그래서 `client.ts` 가 통신 함수를 감싸 `response.ok` 가 아니면 본문을 읽어 갈래로 바꿔 던진다. 옛 소문자 `legacyCode` 는 읽지 않는다.

200 안의 갈래는 실패가 아니다: 계산의 행마다의 `status: "failed"`, 후보 추리기의 `status: "no_candidates"` 는 답으로 그린다. 자동 다시 시도, 로그인 화면으로 보내기, 토큰 갱신은 없다.

## 세션 쿠키가 브라우저에서 실리는가

세션 쿠키는 `Secure` 인데 로컬의 주소는 `http://` 다. Chromium 은 루프백 주소를 믿을 수 있는 출처로 보아 담고 되보낸다. 잰 표와 재지 않은 것은 [기록](#기록)에 있다. 떠 있는 api-py 에 닿는 이 확인은 `e2e/live/api-live.pw.ts` 가 한 흐름으로 돈다(아래 「확인하는 법」).

## 폴더와 층

```
src/shared/api/
  model/      실패의 갈래와 가름, 변경 뒤 무효로 표시할 키. React·DOM·통신을 모른다. 계약 타입을 다시 내보낸다
  client.ts   층 밖의 어댑터 하나. createApi({ baseUrl, fetch? }). openapi-* 를 아는 파일은 이것뿐
  hooks/      변경에 성공하면 조회를 무효로 표시하는 훅
  index.ts    공개 표면. 폴더 밖은 이것으로만 들어온다
  testing.ts  시험이 쓰는 도우미(제품 코드는 가져오지 못한다)
src/pages/demo-api/ ApiPage.tsx(화면), examples.ts(예시 요청 둘). QueryClient 는 여기서 만든다
```

문서 뷰어의 꼴을 줄였다. 클라이언트에는 모양이 없어 `ui/` 가 없다. 구조 규칙 시험 `src/app/guards/layers.test.ts` 가 방향과 문, 그리고 「`shared/api` 는 패칭 기본값을 품지 않는다」(`FETCHING_DEFAULT`)를 글자로 잰다. 경로 표 `src/app/router.tsx` 는 이 화면을 게으르게 부른다(`lazyRouteComponent`). 그래서 다른 화면의 진입 청크에 TanStack Query 가 들지 않는다.

## 확인하는 법

- 게이트: `apps/web/scripts/verify.sh`([문서 뷰어](doc-viewer.md#확인하는-법)). 클라이언트의 단위 시험(`src/shared/api/client.test.ts`, `model/failure.test.ts`, `hooks/useInvalidatingMutation.test.tsx`), 화면의 시험(`src/pages/demo-api/behavior.test.tsx`), 빌드 결과를 여는 브라우저 시험(`e2e/api-demo.spec.ts` — 서버 없이 `/api/` 아래의 요청을 시험이 채운다)이 여기서 돈다.
- 떠 있는 api-py 에 닿는 확인(`e2e/live/`)은 **어느 게이트에도 들어 있지 않다**(`scripts/verify.sh`, `apps/web/scripts/verify.sh`, `pnpm test:browser` 가 줍지 않는다. 파일 이름이 `.spec.ts` 가 아니다). 손으로 돌려야 돈다. api-py 를 띄우고 테넌트와 토큰을 준비한 뒤 `apps/web` 에서:

```sh
F9_TOKEN=… F9_TENANT=… API_PY_ORIGIN=… WEB_TEST_PORT=… pnpm exec playwright test -c e2e/live/playwright.config.ts
```

## 고른 것과 바꾸는 법

| 자리 | 지금 | 바꾸려면 |
|---|---|---|
| 클라이언트 | openapi-fetch + openapi-react-query | `src/shared/api/client.ts` 하나를 다시 쓴다. `model/` 과 화면이 쓰는 `Schemas` 는 그대로 |
| 타입을 들이는 길 | 상대 경로의 `import type` | 워크스페이스 패키지나 `tsconfig` 의 `paths` 로. `src/shared/api/model/` 의 import 두 줄 |
| 서버에 닿는 길 | Vite 의 프록시(`/api`) | `vite.config.ts` 의 `server.proxy`. 직접 부르려면 api-py 에 CORS 와 쿠키의 `SameSite` 결정이 먼저다 |
| 무효화 | 변경 뒤 `["get"]` 전부 | `src/shared/api/model/keys.ts` 와 `hooks/useInvalidatingMutation.ts` |
| 패칭 기본값 | 화면이 정한다(다시 시도만 끔) | `src/pages/demo-api/ApiPage.tsx` 의 `createDemoQueryClient` |
| 화면을 고르는 법 | 경로 `/dev/api` | `src/app/router.tsx` |

## 안 한 것

- **인증 흐름의 제품 꼴.** 로그인 화면, 토큰 갱신, 401 뒤의 이동, 로그아웃, EDK 연동이 없다. 테넌트를 등록하는 길도 화면에 없다.
- **기존 부품을 서버에 잇기.** 문서 뷰어와 검토 표는 그대로다.
- **부르지 않는 경로.** 위 흐름의 여섯 밖은 부르지 않는다. 예: `/auth/logout`, `/reference/sources`, `/reference/assemble*`, `/inventory/scope3/classify`(생성 모델을 부른다).
- **응답의 런타임 검증.** 타입은 계약에서 오고, 서버가 계약과 다르게 답하면 web 은 모른다.
- **web 을 compose 에 넣기, 떠 있는 서버에 닿는 확인을 게이트에 넣기.**

## 기록

개발하며 남긴 글과 잰 값이다. **그때 경로는 옛 이름이다**(웹이 층 다섯으로 바뀌기 전). 아래 표로 지금 자리를 찾는다.

| 그때 | 지금 |
|---|---|
| `src/api/` | `src/shared/api/` |
| `src/api/domain/` | `src/shared/api/model/` |
| `headless/`(`headless/useInvalidatingMutation.ts`) | `src/shared/api/hooks/`(`hooks/useInvalidatingMutation.ts`) |
| `src/api/layers.test.ts` | `src/app/guards/layers.test.ts` |
| `src/api-demo/` | `src/pages/demo-api/` |
| `?view=api`(`http://localhost:15173/?view=api`) | `/dev/api`(`http://localhost:15173/dev/api`) |
| `src/main.tsx`(화면 고르기, 동적 `import()`) | `src/app/router.tsx`(`lazyRouteComponent`) |
| `/api-py/…`(프록시가 접두를 뗌) | `/api/…`(그대로 넘김) |
| `domain/` | `model/` |

그때의 글:

- 그때 `apps/web` 이 부르던 것은 「아래의 Python API」(같은 뿌리 `README.md` 의 「Python API (apps/api-py)」 절)였다. 지금 api-py 의 개발 글은 저장소 뿌리 `docs/development.md` 의 「Python API (apps/api-py)」 절에 있다.
- 「기반 밴드가 정한다」고 적었다(패칭 컨벤션을 정할 자리).
- 그때 브라우저는 쪽과 같은 출처의 `/api-py/…` 로 불렀고 Vite 의 프록시가 접두를 떼어 api-py 로 넘겼다. 빌드한 정적 파일만 다른 서버에 올리면 그 서버가 `/api-py/` 를 넘겨야 했다. 그때 「서버에 닿는 길」 칸은 「Vite 의 프록시(`/api-py`)」였다.
- 그때 실패의 갈래 `api` 에는 `fields` 가 없었고, 서버의 오류 꼴과 code 는 아래 표와 같았다(code 는 소문자).

| 갈래 | 언제 | 화면 |
|---|---|---|
| `{kind:"api", status, code, message}` | 서버가 정한 꼴 `{error:{code,message}}` 로 거절(401 `no_session`, 403 `forbidden` …) | `code` 와 `message` 를 글자로 |

- 그때 `main.tsx` 가 이 화면을 게으르게 불러(동적 `import()`) 문서 뷰어와 검토 표의 진입 청크에 TanStack Query 가 들지 않았다. 화면을 고르는 법은 `?view=api` 였다.
- 그때 확인하는 법은 `apps/web/scripts/section4-F9.sh`(컨테이너 없이: 게이트, 새 테스트, 의존성·잠금 파일, 진입 청크, 심은 파손 14)와 `apps/web/scripts/section4-F9.sh --containers`(api-py 를 띄워 브라우저로 한 흐름) 였다. 닫힌 밴드의 스크립트라 지금 확인하는 법으로 쓰지 않는다.

**들인 꾸러미**(그때의 표):

| 꾸러미 | 판 | 라이선스 | 왜 |
|---|---|---|---|
| `openapi-fetch` | 0.17.0 | MIT | 계약 타입(`paths`)을 입힌 `fetch`. 경로·요청 칸·응답 칸이 타입으로 묶인다. 런타임 코드가 작다 |
| `openapi-react-query` | 0.5.4 | MIT | 위의 것을 TanStack Query 의 조회·변경으로 감싼다. 키를 손으로 적지 않는다 |
| `@tanstack/react-query` | 5.103.0 | MIT | 서버 상태의 캐시와 다시 받기 |

딸려 온 것 둘: `@tanstack/query-core` 5.103.0, `openapi-typescript-helpers` 0.1.0(둘 다 MIT). 판·라이선스·나온 날은 `npm view` 로 확인했다(2026-10-08). `@tanstack/react-query` 는 그날의 최신(5.104.1, 엿새 전에 나옴)이 아니라 그 앞 판으로 묶었다. 판은 전부 캐럿 없이 고정이다.

**계약이 바뀌면 web 의 typecheck 는.** 그때 `apps/web/scripts/planted-breaks-F9.sh` 가 계약 타입의 한 줄씩을 바꿔 가며 잰 표다(닫힌 밴드의 스크립트다).

| 바뀐 것 | web 의 typecheck |
|---|---|
| 경로(`"/sites"`) | 빨강. 그 경로를 부르는 줄 |
| 요청의 칸(`SiteIn.name`, `CalcIn.gwpSetId`) | 빨강. 본문을 짓는 줄, 예시 요청 상수 |
| 응답의 칸(`ExchangeOut.tenant`, `MeOut.tenantId`, `SitesOut.sites`, `FactorsOut.total`) | 빨강. 그 칸을 읽는 줄 |
| 갈래를 가르는 글자(후보 추리기 답의 `status: "no_candidates"`) | 빨강. 그 글자와 견주는 줄 |
| `operationId` 의 이름(두 자리 다 개명) | **초록.** openapi-fetch 는 경로와 메서드로 타입을 찾는다. 이 이름은 api-py 의 계약 테스트(`esgapi/config/tests/test_api_contract.py`)가 지킨다 |
| `api.d.ts` 가 `openapi.json` 과 어긋남 | **web 은 모른다.** 같은 계약 테스트의 sha256 대조가 잰다 |
| 화면이 읽지 않는 칸 | **초록.** 쓰는 줄이 없으면 빨개질 줄도 없다 |

빈 502 의 꼴(`502`, `Content-Type: text/plain`, `Transfer-Encoding: chunked`, 본문 없음)은 Vite 8.3.2 에서 확인했다.

**세션 쿠키가 브라우저에서 실리는가**(그때 잰 표):

| 주소 | 쿠키가 담김 | 되보냄 | `document.cookie` |
|---|---|---|---|
| `http://127.0.0.1:<포트>/` | 예 (`httpOnly`, `secure`, `sameSite: "Lax"`, `path: "/"`) | 예 (`GET /me` 가 200, 그 뒤의 다섯 동작도) | `""` |
| `http://localhost:<포트>/` | 예 (같은 속성) | 예 (`GET /me` 가 200) | 재지 않음 |

잰 것(2026-10-08): 머리 없는 Chromium 153.0.8010.12(`@playwright/test` 1.63.0), `vite preview`(Vite 8.3.2)의 프록시, compose 로 띄운 api-py. `apps/web/e2e/live/api-live.pw.ts` 가 한 흐름으로 돈다. 그때 프록시는 `/api-py` 를 떼는 꼴이었다.

재지 않은 것(무효 조건): Chromium 밖의 브라우저(Safari, Firefox), 루프백 밖의 이름(LAN IP, 컨테이너 이름. `Secure` 쿠키가 담기지 않을 수 있다), `vite preview` 가 아닌 `vite dev` 에서의 쿠키(프록시 설정은 같은 것을 쓴다).
