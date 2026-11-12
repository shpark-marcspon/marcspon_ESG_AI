# apps/web — ESG 웹 화면

React 18 + Vite. 그린워싱 화면(지금은 목 저장소)과 개발용 데모를 담는다. 부품마다의 쓰는 법(실행·실제 자료 붙이기·층·고른 것)은 [`docs/`](docs/) 에, 저장소 전체를 띄우는 법은 저장소 뿌리 [`README.md`](../../README.md) 에 있다.

## 띄우기

```sh
pnpm install --frozen-lockfile
pnpm --filter @esg/web dev        # http://localhost:15173/ (포트는 WEB_PORT 로 바꾼다)
```

`/api/…` 는 api-py(`API_PY_ORIGIN`, 기본 `http://127.0.0.1:18081`)로 넘긴다(`vite.config.ts`). 경로 `/` 는 `/greenwash` 로 넘어간다.

## 문서

| 문서 | 무엇 |
|---|---|
| [`docs/doc-viewer.md`](docs/doc-viewer.md) | 문서 뷰어(`src/widgets/doc-viewer/`): 입력 계약, 세 층, 실제 자료를 붙이는 법, 글자 자리 |
| [`docs/review-table.md`](docs/review-table.md) | 검토 표(`src/widgets/review-table/`): 입력의 꼴, 전이표, 계산 실패, 모양 없는 컴포넌트, UI 라이브러리 바꾸는 순서 |
| [`docs/api-client.md`](docs/api-client.md) | 서버 호출 클라이언트(`src/shared/api/`): 타입이 오는 길, 실패의 갈래, 무효화 |

각 문서 끝의 「기록」 절은 개발하며 잰 값과 옛 경로다.

## 폴더 다섯

`src/` 는 층 다섯이다. 위층만 아래층을 가져온다: **app > pages > widgets > entities > shared**.

| 폴더 | 뜻 |
|---|---|
| `src/app/` | 앱 틀: 경로 표(`router.tsx`), 그린워싱 경로 컴포넌트(`greenwash/` — 화면을 라우터에 잇는다), 전역 CSS(`styles/`), 구조 규칙 시험(`guards/`). `src/main.tsx` 가 진입점 |
| `src/pages/` | 화면 하나 = 폴더 하나. `greenwash-*` 는 그린워싱 화면(목록·소개·새 점검·처리 상태·결과·검토), `demo-*` 는 데모 |
| `src/widgets/` | 화면 여럿이 쓰는 큰 부품: `doc-viewer`(PDF 문서 뷰어), `review-table`(검토 표) |
| `src/entities/` | 업무 단위(지금은 `greenwash` 하나): 화면 둘 이상이 쓰는 모델·저장소·훅·문구 |
| `src/shared/` | 업무를 모르는 것: `ui`(공용 부품), `api`(서버 호출 클라이언트), `lib`(작은 도우미 — 주소, 읽기 훅 `useLoad`, 시험 도우미) |

슬라이스(부품 폴더, 화면 폴더) 안은 칸으로 나눈다: `model`(순수 함수와 타입) ← `api`(서버 꼴 검사·저장소·목) ← `hooks`(훅과 모양 없는 컴포넌트) ← `ui`(모양), 그리고 `config`(문구 표 — ui 만 가져다 쓴다). 화살표 방향으로만 가져온다. 칸마다 쓸 수 있는 패키지도 정해져 있다(예: pdfjs-dist 는 `widgets/doc-viewer/pdfjs.ts` 만, `@tanstack/react-router` 는 `src/main.tsx` 와 `src/app/` 만).

## 새 파일 자리

- 한 화면만 쓰는 것 → 그 화면 폴더(`src/pages/<화면>/` 의 `model`·`hooks`·`ui`). 밖에서는 그 폴더의 `index.ts` 로만 들어온다.
- 그린워싱 화면 둘 이상이 쓰는 것 → `src/entities/greenwash/` 의 맞는 칸.
- 그린워싱 밖에서도 쓸 부품 → `src/widgets/`(업무 꼴이 있는 큰 부품) 또는 `src/shared/ui/`(공용 부품).
- 업무를 모르는 도우미 → `src/shared/lib/`(파일 하나하나가 문이라 새 파일은 구조 규칙 시험의 문 목록에 더한다).
- 시험만 쓰는 도우미 → 그 슬라이스의 `testing.ts`(예: `entities/greenwash/api/mock/testing.ts` 가짜 저장소, `widgets/review-table/model/testing.ts` 행 만들기) 또는 `shared/lib/testing/`. 제품 코드는 가져오지 못한다.
- 새 화면 → `src/pages/` 에 폴더를 만들고 경로 표에 한 줄 더한다.

자리를 잘못 잡으면 구조 규칙 시험이 빨강이 된다.

## 경로

경로 표는 `src/app/router.tsx` 하나다(TanStack Router 를 코드로 적는다). 화면은 라우터를 모르고 콜백 props 를 받는다 — `src/app/greenwash/` 의 경로 컴포넌트가 navigate 로 잇는다.

데모 넷은 `/dev/*`(`/dev/viewer`·`/dev/table`·`/dev/api`·`/dev/parts`)이고, 개발 서버(DEV)이거나 `VITE_DEMOS=1` 로 빌드했을 때만 경로가 있다. 그 밖의 빌드에는 데모 코드가 들지 않는다(`scripts/check-no-demos.sh` 가 본다).

AD-04 실행 기록의 「시험용 AI 연결」 안내 띠는 서버 지표 `GET /run-logs/metrics` 의 `aiProviderMock` 이 참일 때(모의 공급사)만 보인다. 지표를 받는 중이거나 실패하면 띠는 없다(빌드 값으로 켜고 끄지 않는다 — 밴드 MP1W).

## 확인

- 게이트: `scripts/verify.sh` — 설치·타입·린트·서식·단위 시험·빌드·데모 빠짐·브라우저 받기·브라우저 시험·실제 자료 없음을 처음부터 끝까지 돈다. 단계마다 `EXIT=` 줄, 끝에 `VERIFY=PASS|FAIL`. 브라우저 시험은 포트 하나를 잠깐 쓴다(기본 15174, `WEB_TEST_PORT` 로 바꾼다). 서식 검사(`format:check`)는 `src tools e2e` 만 보고 md 는 보지 않는다.
- 구조 규칙 시험: `src/app/guards/layers.test.ts` — 층 순서, 슬라이스의 공개 표면(밖에서 들어오는 문), 칸 규칙, 라우터·진입 청크 규칙을 이 파일 하나가 지킨다. 규칙을 바꿀 때는 이 파일의 표를 고치고, 「규칙이 실제로 잡는다」 시험에 그 줄을 더한다.
- 단위 시험은 `src/**/*.test.ts(x)` 와 `tools/**/*.test.ts`(vitest), 브라우저 시험은 `e2e/`(Playwright, 빌드 결과를 연다).
