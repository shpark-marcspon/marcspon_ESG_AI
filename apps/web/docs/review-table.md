# 검토 표 (widgets/review-table)

AI 가 낸 후보(카테고리, 배출계수)를 사람이 행마다 보고 고르고 확정하는 표다. 행이 수천 개여도 화면에 보이는 만큼만 그린다. 여러 행을 한 번에 반영·확정할 수 있고, 최종 확정한 행만 결과 합계에 든다.

**서버를 부르지 않는다.** 검토 상태는 화면 안에만 있어 새로 고치면 사라진다. **데모 화면의 배출량 재계산은 대역이다**(`src/pages/demo-table/standInCalc.ts`). 진짜 계산은 서버의 일이고, 표는 계산 함수를 밖에서 받는다.

이 글의 요점은 화면이 아니라 **층 나누기**다. 디자인이나 UI 라이브러리가 정해져 화면을 통째로 바꿔도 업무 로직과 헤드리스 층이 남게 했다. TanStack Table·Virtual, 폴더 나눔, 이름은 연습용으로 고른 것이고 정해진 스택이나 컨벤션이 아니다.

경로는 `apps/web/` 기준이다. 폴더 규칙(층 다섯, 칸)은 [`../README.md`](../README.md) 에 있다. 잰 값과 개발 기록은 끝의 [기록](#기록)에 있다.

## 띄우는 법

```sh
pnpm install --frozen-lockfile
pnpm --filter @esg/web dev        # 브라우저로 http://localhost:15173/dev/table 에 간다
```

데모 경로(`/dev/*`)는 개발 서버이거나 `VITE_DEMOS=1` 로 빌드했을 때만 있다(`src/app/router.tsx`). 화면 위의 줄에서 자료와 화면을 고른다(주소로도 된다). 줄의 링크는 바꾸려는 인자만 바꾸고 주소의 나머지는 그대로 싣는다(카드 화면에서 자료를 바꿔도 `&screen=cards` 가 남고, `&calcFail=1` 을 붙인 채 화면을 바꿔도 남는다). 가짜가 아닌 자료로 갈 때만 `rows` 를 뺀다.

| 주소 | 무엇 |
|---|---|
| `/dev/table?data=sample` | 손으로 쓴 예시(`public/sample/review-table.json`). 일곱 상태가 다 있고 후보가 0·1·2·3개인 행이 있다. `data` 를 안 주면 이것이다 |
| `/dev/table?data=fake` | 코드로 만든 가짜 행(씨앗 고정, `src/pages/demo-table/fakeRows.ts`). `&rows=` 로 행 수를 바꾼다 |
| `/dev/table?data=local` | 실제 자료(아래처럼 변환해 두었을 때) |
| `&screen=cards` | 같은 자료를 둘째 화면(카드 목록)으로 본다 |
| `&calcDelay=` | 계산 대역이 그만큼(ms) 뒤에 답한다. 「재계산 대기」가 어떻게 보이는지 볼 때 |
| `&calcFail=` | 계산 대역이 행마다 첫 계산을 실패한다(숫자는 실패할 횟수). 「계산하지 못했다」와 「다시 계산」을 볼 때. `&calcDelay=` 와 같이 주면 실패도 그만큼 늦게 온다 |

써 볼 것: 행 왼쪽의 `▸` 로 펼치기 → 다른 후보 고르기(수정) → 최종 확정, `&calcFail=1` 을 붙이고 같은 일을 해 보기(계산 실패 → 다시 계산), 사유 없이 반려해 보기, 머리글을 눌러 정렬, 글자·상태·카테고리로 걸러 보기, 걸러 본 뒤 「일괄 반영」「일괄 최종 확정」(건너뛴 개수와 까닭이 옆에 나온다), 표를 누른 뒤 <kbd>↓</kbd> <kbd>↑</kbd> <kbd>j</kbd> <kbd>k</kbd> <kbd>PageDown</kbd> <kbd>End</kbd> 로 이동, <kbd>Space</kbd> 로 고르기, <kbd>Enter</kbd> 로 펼치기.

실제 자료를 붙이려면(카테고리 분류·계수 추천 실측의 산출물. 저장소 밖에 둔다):

```sh
export VIEWER_DATA_DIR=~/viewer-data                  # 결과를 쓸 폴더. 저장소 밖을 권한다
export ESG_LAB_OUT=<실측 산출물 폴더>                  # 그 아래 measure-openai/scope3-s100/rows.json (다른 실행은 TABLE_RUN 으로)
export ESG_LAB_DATA=<실측 저장소의 data 폴더>          # 그 아래 factors/factors.jsonl
pnpm --filter @esg/web convert:table
pnpm --filter @esg/web dev                            # http://localhost:15173/dev/table?data=local
```

그 자료에 무엇이 있고 없는가:

- 품목명, 단위, 예측 카테고리, 추천 계수(0~3개), 계산 기준, 상태는 실행 결과 `rows.json` 에 있다.
- 계수의 이름·값·단위·출처는 계수 표 `factors.jsonl` 에 있다.
- 후보별 매핑 이유, 신뢰도는 `rows.json` 에 **없다.** 옆의 호출 기록 `calls.jsonl` 의 응답 글에 있다. 호출 기록에는 행 id 가 없어 품목명+단위로 잇는다(이유는 계수 id 까지 맞는 것만 붙인다).
- 수량, 금액은 `rows.json` 에 **없다.** 실행에 넣었던 내역 `scope3-examples/rows.synthetic.jsonl` 에 있다(전부 가상 내역).
- 계산된 배출량은 **어디에도 없다**(계산 상태의 이름만 있다). 변환이 대역으로 채운다: 수량 × 계수 ÷ 1000(tCO2eq), 단위가 같을 때만(kg ↔ t 만 바꾼다. `tools/lab/scope3.ts`).

얼마나 채워지는가를 센 값은 [기록](#기록)에 있다.

`rows.json` 에는 정답(`gold`)이 붙어 있다. 변환은 그 필드를 읽지 않고 표의 입력에 싣지 않는다(`tools/lab/scope3.test.ts` 가 본다).

## 세 층

```
src/widgets/review-table/
  index.ts              공개 표면. 폴더 밖에서는 여기서만 가져다 쓴다
  model/                업무 로직. 순수 TypeScript. React, TanStack, DOM 을 모른다(바깥 것은 zod 하나)
    row.ts                행의 모양. AI 원본값(ai) / 사람이 고친 값(edit) / 검토 상태를 따로 든다          ← 1
    transitions.ts        허용 전이표(자료)와 조건, 동작 하나 적용하기                                  ← 2
    bulk.ts               일괄 동작: 되는 행만 바꾸고, 건너뛴 행을 까닭별로 센다                        ← 3
    summary.ts            상태별 개수, 최종확정 행만의 합계, 임시 합계
    filter.ts             걸러 보기의 조건(상태, 카테고리, 글자)
    input.ts              입력의 꼴과 검증(zod)
    format.ts             배출량의 단위 글자와 표기(한 곳에서만 정한다)
  hooks/                React 훅과 모양 없는 컴포넌트. TanStack 을 감싼다. 모양(CSS, 색·테두리·글꼴)을 모른다
    useReviewRows.ts      행의 상태를 들고 업무 로직을 돌린다. 계산 함수와 저장(onChange)을 밖에서 받는다  ← 4
    useReviewTable.ts     정렬, 걸러 보기, 행 고르기, 일괄 대상 정하기 (TanStack Table)                 ← 5
    useRowWindow.ts       보이는 행만 그리기, 지금 행, 펼침, 키보드 (TanStack Virtual)                  ← 6
    useReviewBoard.ts     위 셋을 묶은 훅. 화면은 이것 하나만 부른다
    RowStack.tsx          행 창(모양 없는 컴포넌트): 스크롤 상자, 높이 잡기, 보이는 행 놓기, 키보드 받기, grid 의 접근성 구조(머리글 줄을 받으면 그것까지)  ← 7
    RowFrame.tsx          행 틀(모양 없는 컴포넌트): 한 행만 다시 그리기(memo), 행의 상태 표시, 높이 재기
  ui/                   화면. 바꿔 끼우는 층. 생김만 있다
    ReviewTable.tsx       표 모양: 머리글 줄의 칸, 칸의 배치, 행의 속                                   ← 8
    RowDetail.tsx         펼친 행: 후보 목록, 카테고리 고치기, 단추들
    Toolbar.tsx           걸러 보기, 요약, 일괄 동작
    review-table.css      모양(`rt-` 접두). 읽을 수 있을 만큼만
src/pages/demo-table/   표를 쓰는 쪽의 예. 공개 표면만 쓴다
  TablePage.tsx           띄워 보는 화면: 자료 읽기 → 검증 → 열과 계산 함수를 정해 표에 넘긴다
  columns.tsx             열 구성(표의 입력)
  ReviewCards.tsx         둘째 화면(카드 목록). 같은 훅과 같은 RowStack 위에 얹었다. 증명용               ← 9
  behavior.test.tsx       같은 동작 테스트를 표와 카드 둘 다에 돌린다
  fakeRows.ts             가짜 행 만들기(씨앗 고정)
  standInCalc.ts          ★ 계산 대역
src/app/guards/layers.test.ts                 구조 규칙 시험(이 부품의 규칙 포함)
tools/convert-table.ts, tools/lab/scope3.ts   실제 자료 → 표의 입력(쓰기 전에 parseTableInput 으로 검증한다)
tools/measure-table.ts                        많은 행에서 걸리는 시간 재기
e2e/review-table.spec.ts                      실제 브라우저 테스트
```

import 는 한 방향이다: `model ← hooks ← ui`. `ui` 는 TanStack 을 직접 부르지 않는다. 폴더 밖은 문 둘로만 들어온다: `widgets/review-table/index.ts`(화면까지 든 표면. `pages/demo-table` 이 쓴다)와 `widgets/review-table/model/index.ts`(화면 없는 표면. node 에서 도는 `tools/` 가 쓴다. `index.ts` 는 CSS 와 화면을 같이 내보내 node 가 값을 읽지 못한다). 이 규칙은 구조 규칙 시험 `src/app/guards/layers.test.ts` 가 파일을 글자로 읽어 지킨다(`DOORS`·`SLICES` 의 `widgets/review-table` 줄. 업무 로직에 `import … from "react"` 한 줄을 넣으면 빨개진다).

`hooks/` 칸의 규칙은 **「모양을 모른다」**다(문서 뷰어와 같다). CSS 를 가져오지 않고 색·테두리·글꼴의 값을 품지 않는다. 마크업, 자리를 잡는 인라인 style(`height`, `transform`, `overflow-y`), 상태 표시(`data-*`, `aria-*`)는 가진다. 이것도 `layers.test.ts` 가 글자로 지키는데, 글자로는 다 못 잡는다(변수로 건너온 값, 이름 붙은 색 등. 잡는 것과 못 잡는 것은 그 파일 머리말). 뷰어의 규칙과 한 곳이 다르다: 여기서는 `filter` 가 걸러 보기의 이름이라 모양 키의 목록에서 뺐다(`lookKeyExcept`).

| 층 | 밖에 내놓는 것 | 이 층을 바꾸는 때 |
|---|---|---|
| model | `ReviewRow`, `parseTableInput`, `TRANSITIONS`, `applyAction` · `checkAction` · `allowedActions`, 재계산의 결과 넣기(`applyRecalculated` · `applyRecalcFailed` · `retryRecalc`), `applyBulk`, `summarize`, `matchesFilter`, 이름표(`STATUS_LABEL`, `ACTION_LABEL`), 배출량 표기(`EMISSION_UNIT` 과 `format.ts` 의 함수) | 검토 규칙이 바뀔 때. 서버가 같은 규칙을 검사해야 한다(React 를 모르므로 서버와 같이 쓰는 자리로 옮길 수 있다) |
| hooks | `useReviewBoard`(와 그 속의 훅 셋), 모양 없는 컴포넌트 `RowStack` · `RowFrame`, 열의 꼴 `ReviewColumn`, 계산 함수의 꼴 `Calculate`, 행의 속을 그리는 함수의 꼴 `RenderRow` | 표 라이브러리를 바꿀 때(TanStack 을 부르는 곳은 `useReviewTable.ts`, `useRowWindow.ts` 둘뿐이다). 서버를 붙일 때는 `useReviewRows.ts`. 행을 놓는 법이나 키보드를 받는 법, 접근성 구조를 바꿀 때는 `RowStack.tsx` · `RowFrame.tsx` |
| ui | `ReviewTable` | 디자인이나 UI 라이브러리가 정해질 때. 통째로 새로 쓴다(생김만 있다) |

## 입력의 꼴

`src/widgets/review-table/model/input.ts` 가 정의하고 검증한다. `parseTableInput(raw)` 가 `{ ok: true, input }` 또는 `{ ok: false, errors }` 를 돌려준다.

```jsonc
{
  "version": 2,
  "unit": "tCO2eq",                             // 배출량(emission)의 단위. 이 글자만 받는다
  "notice": "…",                               // (선택) 화면 위에 보일 알림
  "categories": ["구매한 제품과 서비스", "자본재"],   // 카테고리를 고칠 때 고를 수 있는 값
  "rows": [
    {
      "id": "s1",
      "raw": { "itemName": "수지 원료", "quantity": 1200, "unit": "kg" },   // 원본 데이터. 키의 뜻은 표가 모른다. 열 구성이 골라 보여 준다
      "processing": "결과 생성",                 // (선택) 처리 상태. 서버가 준 값 그대로
      "ai": {
        "category": "구매한 제품과 서비스",        // AI 가 분류한 카테고리. 없으면 null
        "categoryNote": "생산에 쓰는 원료다.",     // (선택)
        "candidates": [                          // AI 가 제안한 계수들. 첫 번째가 대표. 0개일 수 있다
          { "id": "s1-a", "factorName": "…", "factorValue": 1.5, "factorUnit": "kgCO2e/kg",
            "source": "…", "reason": "…", "confidence": "high",   // (선택) 출처, 적용 기준, 신뢰도
            "emission": 1.8 }                    // 이 후보로 계산한 배출량(tCO2eq). 값이 나오지 않았으면 null
        ]
      },
      "review": {                                // 검토 상태의 처음 값. 서버가 생기면 저장된 값이 여기로 온다
        "status": "pending",                     // pending · accepted · declined · edited · rerequested · rejected · finalized
        "rejectReason": "…",                     // 반려일 때 필수
        "edit": { "category": "자본재", "candidateId": "s1-b", "emission": 3 }   // (선택) 사람이 고친 값. 재계산이 실패한 채로 저장된 행이면 "emission": null, "recalcFailed": true
      }
    }
  ]
}
```

- **판과 단위.** `version` 은 2, `unit` 은 `"tCO2eq"` 만 받는다(`model/format.ts` 의 `EMISSION_UNIT`). 칸 이름 `emission` 에는 단위가 없어서, 판 1(kgCO2e) 자료가 1000배 큰 값으로 조용히 읽히지 않게 판과 단위 글자로 막는다. 화면의 배출량 표기(자리수, 아주 작은 값의 `<0.001`)도 `model/format.ts` 한 곳에서 정한다.
- **원본값과 수정값을 따로 둔다.** `ai` 는 받은 뒤로 바뀌지 않는다. 사람이 고친 것은 `edit` 에 들어가고, 화면은 「지금 값」을 `currentCategory` · `currentCandidate` · `currentEmission` 으로 읽는다.
- **열은 입력이다.** 표는 무엇을 열로 보일지 정하지 않는다. 쓰는 쪽이 `ReviewColumn[]` 을 넘긴다(`{ id, header, value(row), render?, sortable?, width?, align? }`. 예는 `pages/demo-table/columns.tsx`).
- **계산과 저장은 밖에서 받는다.** `calculate({ row, category, candidate })` 가 배출량을 돌려준다(바로 또는 `Promise` 로). `null` 을 돌려주면 「계산해 보니 값이 없다」이고, 거부하거나 예외를 내면 「계산하지 못했다」다(아래 [계산 실패](#계산-실패)). `onChange(바뀐 행들)` 이 저장을 붙일 자리다.

```tsx
import { parseTableInput, ReviewTable } from "../../widgets/review-table/index.ts";

const parsed = parseTableInput(raw);
if (parsed.ok) {
  <ReviewTable rows={parsed.input.rows} categories={parsed.input.categories} columns={columns} calculate={calculate} onChange={save} />;
}
```

## 검토 상태와 전이표

전이표는 `src/widgets/review-table/model/transitions.ts` 의 `TRANSITIONS` 에 **자료로** 있다. `TRANSITIONS[지금 상태][동작] = 다음 상태` 이고, 칸이 없으면 그 동작은 안 된다.

| 지금 상태 ↓ / 동작 → | 반영 | 미반영 | 수정 | 재추천 요청 | 반려 | 최종 확정 | 되돌리기 | 확정 취소 |
|---|---|---|---|---|---|---|---|---|
| 검토대기 | 반영 | 미반영 | 수정 | 재추천요청 | 반려 | · | · | · |
| 반영 | · | 미반영 | 수정 | 재추천요청 | 반려 | 최종확정 | 검토대기 | · |
| 수정 | 반영 | 미반영 | 수정 | 재추천요청 | 반려 | 최종확정 | 검토대기 | · |
| 미반영 | 반영 | · | 수정 | 재추천요청 | 반려 | · | 검토대기 | · |
| 재추천요청 | · | · | · | · | · | · | 검토대기 | · |
| 반려 | · | · | · | · | · | · | 검토대기 | · |
| 최종확정 | · | · | · | · | · | · | · | 반영 또는 수정 |

표 옆의 조건(`checkAction`):

- 반영: 후보가 하나 이상 있어야 한다. 수정했던 행을 반영하면 수정값을 버리고 AI 제안으로 돌아간다.
- 수정: 카테고리를 고치거나 그 행의 다른 후보를 고른다. 수정하면 **재계산 대기**가 되고, 계산 함수가 답할 때까지 배출량이 비고 최종 확정이 안 된다.
- 반려: 사유가 있어야 한다(빈칸뿐인 것도 안 된다).
- 최종 확정: 반영 또는 수정 상태에서만. 후보가 있고, 재계산 대기가 아니고, 재계산이 실패한 채가 아니고, 배출량이 있어야 한다.
- 되돌리기: 검토대기로 가면서 수정값과 반려 사유를 버린다. 확정 취소: 수정값이 남아 있으면 수정으로, 없으면 반영으로 돌아간다.

**★ 이 가운데 요구에서 온 것과 여기서 정한 것.**

| 요구에서 온 것 | 여기서 정한 기본값(물어야 하는 것) |
|---|---|
| 상태의 이름 일곱 | 전이표의 모든 칸. 요구 어디에도 전이표가 없다 |
| 반영은 최종 확정이 아니다. 최종 확정한 행만 결과에 든다 | 검토대기에서 곧바로 최종 확정하지 못한다(반영이나 수정을 거친다) |
| 반려는 사유가 필수다 | 미반영 행은 최종 확정하지 못한다(결과에서 빼는 것을 따로 확정하지 않는다) |
| 수정하면 배출량을 재계산하고, 원본값과 수정값을 둘 다 남긴다 | 확정한 뒤 되돌릴 수 있다(확정 취소). 재추천요청·반려에서는 되돌리기만 된다 |
| | 수정했던 행을 반영하면 수정값을 버린다. 되돌리기도 버린다 |
| | 일괄 동작 전부(요구에 일괄 처리가 없다): 대상, 건너뛰는 규칙 |

**전이표를 고치는 법.** `TRANSITIONS` 의 줄을 고친다. 예를 들어 검토대기에서 곧바로 최종 확정하게 하려면 `pending` 줄에 `finalize: "finalized"` 를 더한다. 그다음 `transitions.test.ts` 의 `EXPECTED`(같은 표를 일부러 따로 적어 둔 기대값)도 같이 고친다. 그 테스트가 일곱 상태 × 여덟 동작의 56칸을 전부 돈다. 조건을 바꾸려면 `checkAction` 을, 상태를 더하려면 `row.ts` 의 `ReviewStatus` · `STATUSES` · `STATUS_LABEL` 과 `input.ts` 의 목록을 같이 고친다. 전이표의 칸만 바꿀 때는 화면을 고칠 것이 없다(`allowedActions` 가 주는 대로 단추를 그린다). 동작의 종류를 새로 더할 때는 화면도 고친다: 두 화면(`ui/RowDetail.tsx`, `pages/demo-table/ReviewCards.tsx`)에 「단추 하나로 끝나는 동작」의 목록(`SIMPLE`)이 있다.

## 계산 실패

계산 함수가 실패하면(`Promise` 를 거부하거나 예외를 낸다) 그 행에 **「계산하지 못했다」**가 남는다. 「배출량이 없다」(계산 함수가 `null` 을 답했다. 단위가 안 맞는 행 같은 것)와 다른 상태다. 앞의 것은 다시 부르면 풀릴 수 있고, 뒤의 것은 다시 불러도 같다.

| | 계산하지 못했다(실패) | 배출량이 없다 |
|---|---|---|
| 언제 | 계산 함수가 거부했거나 예외를 냈다 | 계산 함수가 `null` 을 답했다. 또는 대표 후보에 값이 없다 |
| 행의 모습(`row.edit`) | `emission: null`, `recalcFailed: true` | `emission: null` |
| 묻는 함수 | `isRecalcFailed(row)` | `currentEmission(row) === null` |
| 최종 확정이 안 되는 까닭 | `recalc_failed` 「계산하지 못했다(계산이 실패했다). 다시 계산해야 한다.」 | `no_emission` 「배출량이 없다(계산해도 값이 나오지 않는다).」 |
| 다시 시도 | 된다(`board.retry(rowId)`). 다시 재계산 대기가 된다 | 없다 |
| 요약 | `summary.recalcFailed` 에 센다 | 세지 않는다 |

- **상태는 업무 로직에 있다**(`model/row.ts` 의 `RowEdit.recalcFailed`, `model/transitions.ts` 의 `applyRecalcFailed` · `retryRecalc`). 화면은 `isRecalcFailed` 를 물어 보일 뿐이다. 계산을 부르고 실패를 받는 곳은 `hooks/useReviewRows.ts` 다.
- **전이표는 그대로다.** 실패와 다시 시도는 검토 상태를 바꾸지 않는다(수정 상태인 채로 배출량만 다시 구한다). 그래서 「다시 계산」은 전이표의 동작이 아니라 따로 둔 함수다. 최종 확정의 조건에 까닭 하나(`recalc_failed`)가 더해졌을 뿐이다. 그래서 사람이 「값이 없는 행」과 「잠깐 실패한 행」을 가를 수 있다.
- 화면: 펼친 행에 알림과 「다시 계산」 단추, 행의 배출량 칸에 「계산 실패」, 요약에 「계산 실패 n」. 일괄 최종 확정은 실패한 행을 건너뛰고 까닭을 따로 적는다(「수정 3개: 계산하지 못했다(계산이 실패했다). 다시 계산해야 한다.」).
- 실패한 행을 다시 고치거나(다른 후보, 다른 카테고리) 반영·되돌리기를 하면 실패 표시는 사라진다. 기다리는 동안 다시 고쳤으면 늦게 온 실패는 버린다(늦게 온 답과 같다).
- 하지 않은 것: 실패의 까닭(오류 글)을 행에 남기지 않는다. 자동으로 다시 시도하지 않는다. 일괄 「다시 계산」이 없다. 실패가 서버의 것인지 네트워크의 것인지 가르지 않는다. 전부 서버를 붙일 때 정할 것이다.

## 일괄 동작

- 대상은 둘 중 하나다: **걸러 본 결과 전체**, 또는 **고른 행 가운데 걸러 본 결과 안에 있는 것**. 걸러서 안 보이는 행은 골라 두었더라도 대상이 아니다(고른 채로는 남는다).
- **화면에 그려졌는지와 무관하다.** 대상은 걸러 본 결과에서 뽑는다(`useReviewTable.ts` 의 `targetIds`). 5,000행 가운데 DOM 에는 30~40행만 있어도 5,000행이 대상이다.
- 못 하는 행은 건너뛰고, 몇 개가 왜 건너뛰어졌는지 돌려준다(`applyBulk` 의 `skipped`: 그때의 상태와 까닭별 개수). 예: 「검토대기 3,412개: 지금 상태에서는 할 수 없는 동작이다」「반영 12개: 배출량이 없다」「수정 3개: 계산하지 못했다」.
- 일괄 최종 확정은 검토대기 행을 건너뛴다. 「일괄 반영 → 일괄 최종 확정」 두 번이 한 묶음이다.

## 많은 행에서

보이는 행만 그린다(TanStack Virtual). 펼친 행처럼 높이가 다른 행은 높이를 미리 계산하지 않고, 그려진 뒤에 잰 값을 쓴다(`useRowWindow.ts` 의 `measureRef`). 그 값은 크기 변화를 지켜보다가 알게 되므로(ResizeObserver), 펼친 높이가 스크롤 길이에 들어오는 것은 화면이 그려진 뒤 한두 프레임 늦다. 그 틈에 펼친 행 속 입력 칸에서 <kbd>End</kbd> 를 누르면 브라우저가 옛 끝까지만 굴러간다(펼친 만큼 모자란다). 자동 조작이 펼치자마자 누를 때만 나는 일이고 사람 손이 닿는 틈이 아니라 고치지 않았다(해 본 고침과 걷어 낸 까닭은 [아래 표](#모양-없는-컴포넌트-행-창과-행-틀)). 그려 본 적 없는 행은 접힌 높이로 어림하므로(`estimateRowHeight`), 펼친 행이 많으면 스크롤 막대의 길이가 지나가면서 조금씩 맞춰진다. 행을 놓고 재는 일은 `RowStack` 과 `RowFrame` 이 한다.

DOM 에 있는 행 수와 동작마다 걸린 시간을 잰 값은 [기록](#기록)에 있다. `pnpm --filter @esg/web measure:table` 이 재는 스크립트다(떠 있는 개발 서버에 붙는다. 아래 기록의 ★).

## 모양 없는 컴포넌트 (행 창과 행 틀)

화면이 직접 다루던 구조를 `hooks/` 의 컴포넌트 둘로 내렸다. 화면을 바꿔도 이 구조는 다시 쓰지 않는다.

```
<RowStack>                                   hooks/RowStack.tsx
  <div role="grid" aria-rowcount tabIndex=0 data-testid="rt-scroll" style="overflow-y: auto">   스크롤 상자. 키보드를 여기서 받는다
    <div style="height: 행을 다 쌓은 높이; position: relative">                                  스크롤 막대의 길이가 된다
      <div style="transform: translateY(첫 행의 자리)">                                          그릴 행들의 묶음. 한꺼번에 내린다
        <RowFrame> …                         hooks/RowFrame.tsx (memo)
          <div role="row" data-index data-row-id data-status data-calc-failed data-active aria-selected aria-rowindex>
            {renderRow(row, { index, selected, active, expanded })}                             ← 화면이 그리는 속
```

머리글 줄이 있는 화면(표)은 `header` 를 준다. 그러면 grid 가 한 겹 바깥으로 나가 머리글 줄과 스크롤 상자를 같이 감싼다. 스크롤 상자는 같은 요소이고 역할만 `rowgroup` 으로 바뀐다.

```
<RowStack header={머리글 줄의 칸들}>
  <div role="grid" aria-rowcount={행 수 + 1} class={classNames.grid}>
    <div role="row" aria-rowindex=1 class={classNames.header}>{header}</div>                    머리글 줄. 칸(role="columnheader")은 화면이 그린다
    <div role="rowgroup" tabIndex=0 data-testid="rt-scroll" style="overflow-y: auto">           스크롤 상자. 위와 같다
      …  <div role="row" aria-rowindex={순서 + 2} …>                                            자료 행은 2부터
```

행 수(`aria-rowcount`)와 행의 순서(`aria-rowindex`)는 머리글 줄까지 센다(WAI-ARIA APG 「Grid and Table Properties」: 행 수는 머리글 줄을 포함한 전체, 순서는 머리글 줄을 포함한 모든 행에). grid 의 아래에는 `row` 나 `rowgroup` → `row` 가 온다(WAI-ARIA 1.2 의 grid). `header` 를 안 주는 화면(카드)은 위의 첫 그림 그대로다.

| 맡는 것 | 어디 |
|---|---|
| 스크롤 상자에 ref 달기, 전체 높이 잡기, 보이는 행 놓기 | `RowStack` (무엇을 그릴지는 `useRowWindow` 가 정한다) |
| 키보드 받기. 입력 칸·고르기 칸·단추 안에서 누른 키와 Ctrl·Meta·Alt 조합은 무시 | `RowStack` (키의 뜻은 `useRowWindow` 의 `handleKey`) |
| `role="grid"` · `aria-rowcount`, 머리글 줄의 `role="row"` · `aria-rowindex=1`, 행의 `role="row"` · `aria-rowindex` · `aria-selected` | `RowStack`, `RowFrame` |
| 한 행만 다시 그리기(`memo`), 행의 상태 표시(`data-status`, `data-calc-failed`, `data-active`), 높이 재기(ref + `data-index`) | `RowFrame` |
| 칸(`role="gridcell"`), 머리글 줄의 칸(`role="columnheader"`, `aria-sort`, 모두 고르기), 칸의 배치(`grid-template-columns`), 펼친 속, 조작 띠 | 화면(`ui/`) |

**모양을 입히는 법.** 셋이다. 하나도 안 줘도 행은 제자리에 놓이고 키보드를 받는다.

```tsx
const renderRow = useCallback<RenderRow>(                     // ★ useCallback 으로 감싼다(아래)
  (row, state) => <MyCells row={row} selected={state.selected} expanded={state.expanded} columns={columns} act={act} />,
  [columns, act],
);
<RowStack
  window={board.window} rowCount={board.table.rows.length} selectedIds={board.table.selectedIds}
  classNames={{ scroller: "rt-scroll", row: "rt-row", grid: "rt-grid" }}   // 1) 클래스 이름: 스크롤 상자와 행. grid 와 header 는 header 를 줄 때만 쓰인다
  renderRow={renderRow}                                        // 2) 행의 속을 그리는 함수
  header={<MyHeaderCells columns={columns} />}                 // (선택) 머리글 줄의 칸들. 칸마다 role="columnheader" 를 붙인다
/>
```

```css
/* 3) 행의 상태 표시를 보는 CSS */
.rt-scroll { flex: 1; min-height: 0; }                 /* ★ 스크롤 상자의 높이는 쓰는 쪽이 묶는다. 어디서도 안 묶이면 행을 전부 그린다 */
.rt-grid { flex: 1; min-height: 0; display: flex; flex-direction: column; }   /* header 를 주면 바깥의 grid 도 묶는다. 그 안에서 스크롤 상자가 머리글 아래를 채운다 */
.rt-row[aria-selected="true"] { background: … }
.rt-row[data-active] { box-shadow: … }
```

쓰는 쪽이 지켜야 하는 것 셋:

1. **`renderRow` 를 `useCallback` 으로 감싼다.** 행 틀은 `memo` 라서 행 객체와 순서·고르기·지금 행·펼침이 그대로면 다시 그리지 않는다. `renderRow` 가 그릴 때마다 새 함수면 그 `memo` 가 뚫려, 한 행을 바꿔도 화면의 행이 전부 다시 그려진다. 안에서 쓰는 것(열, 동작 함수)은 의존 목록에 적는다. 훅이 주는 동작 함수(`act`, `retry`, `toggleSelected`, `toggleExpanded`, `setActiveId`)는 늘 같은 함수다. 이것을 어기면 `hooks/components.test.tsx` 와 `ui/ReviewTable.test.tsx` 의 「한 행만 다시 그리기」가 빨개진다.
2. **스크롤 상자의 높이가 묶이게 한다**(`classNames.scroller` 로, 또는 부모가 묶는다). 어디서도 안 묶이면 상자가 행을 다 쌓은 높이로 늘어나 전부 그린다. `header` 를 주면 바깥의 grid 도 같이 묶는다(`classNames.grid`).
3. **접힌 행의 실제 높이를 `estimateRowHeight` 와 맞춘다.** 행의 생김은 화면의 것이라 헤드리스 층은 그 높이를 모른다.

**고른 것과 바꾸는 법.**

| 고른 것 | 바꾸려면 |
|---|---|
| 행을 놓는 법은 하나: 흐름대로 쌓고 묶음을 한꺼번에 내린다 | `RowStack.tsx` 의 묶음 `<div>` |
| 훅이 스크롤 요소의 ref 를 쥔다(뷰어의 훅은 ref 를 안 내주고 값으로만 말한다) | `useRowWindow.ts`, `RowStack.tsx` |
| `RowStack` 이 `RowFrame` 을 직접 놓는다 | `RowStack.tsx` |
| 행의 속은 그리는 함수로(`renderRow`) | `RowFrame.tsx` |
| 머리글 줄의 칸은 화면이 그리고, 줄 자체와 그것을 grid 안에 넣는 일은 `RowStack` 이 한다(`header`). 「걸러 본 결과가 전부 골라졌는가」만 훅의 값(`table.allSelected`)으로 | `ui/ReviewTable.tsx`, `RowStack.tsx`, `useReviewTable.ts` |
| 머리글 줄은 스크롤 상자 밖, grid 안에 둔다 | `RowStack.tsx` 의 끝 |
| 펼친 높이가 스크롤 길이에 한두 프레임 늦게 들어오는 것은 그대로 둔다 | `RowFrame.tsx`, `useRowWindow.ts` |
| `grid-template-columns` 는 모양으로 본다(화면에 둔다) | `ui/ReviewTable.tsx` 의 `template` |
| 스크롤 상자의 이름표 `data-testid="rt-scroll"` 를 `RowStack` 이 붙인다 | `RowStack.tsx` |

고른 까닭과 버린 것은 [기록](#기록)의 표에 있다.

**UI 라이브러리의 표 부품을 받을 수 있는가**(들이지 않았다. 문서만 봤다). shadcn 의 `Table` · `TableRow` · `TableCell` 은 진짜 `<table>` · `<tr>` · `<td>` 를 낸다. `RowStack` 과 `RowFrame` 은 `<div>` 를 내므로 그 부품을 **부품째로는 못 끼운다.** 되는 길은 그 부품이 쓰는 클래스 이름을 `classNames` 와 `renderRow` 안의 요소에 입히는 것이고(생김만 가져온다), `<tr>` 이어야 하면 `RowFrame` 의 바깥 요소를 고쳐야 한다(가상 스크롤과 `<table>` 은 본래 잘 안 맞는다. 묶음을 내리는 `<div>` 가 `<tbody>` 안에 못 들어간다).

## 화면을 다른 UI 라이브러리로 바꾸는 순서

1. `src/widgets/review-table/ui/` 를 새로 쓴다. 맨 위 부품에서 `useReviewBoard({ rows, columns, calculate, onChange, estimateRowHeight })` 를 부른다. `estimateRowHeight` 는 새 화면의 접힌 행 높이(px)다. CSS 의 실제 높이와 같아야 한다.
2. 행들은 `<RowStack>` 에 맡긴다. 화면이 쓰는 것은 클래스 이름과, 행의 속을 그리는 `renderRow`(`useCallback`)뿐이다. 스크롤 상자의 ref, 높이 잡기, 행 내리기, 높이 재기, 키보드 가드, `role` 과 상태 표시는 쓰지 않는다.
3. 누른 것을 훅에 넘긴다: `board.act(rowId, action)`, `board.bulk(scope, action)`, `board.retry(rowId)`(계산 실패한 행의 「다시 계산」. 보일지는 `isRecalcFailed(row)` 에 묻는다), `table.setFilter`, `table.toggleSelected`, `table.selectAll`(표시는 `table.allSelected`), `column.toggleSort`, `window.toggleExpanded`, `window.setActiveId`. 어떤 단추를 보일지는 `allowedActions(row.status)`, 잠글지는 `checkAction(row, action)` 에 묻는다. 화면에 규칙을 적지 않는다.
4. `pages/demo-table/behavior.test.tsx` 의 `SCREENS` 에 새 화면을 더해 같은 동작 테스트가 통과하는지 본다. 이 테스트가 화면에 요구하는 것은 이름표뿐이다(파일 머리말). 행과 스크롤 상자의 이름표는 `RowStack` 이 이미 붙인다.
5. `src/widgets/review-table/index.ts` 가 내보내는 화면을 바꾼다. `model/` 과 `hooks/` 는 고치지 않는다. 구조 규칙 시험 `src/app/guards/layers.test.ts` 의 `SLICES` 에서 `widgets/review-table` 줄의 `ui` 패키지 목록에 새 UI 라이브러리의 이름을 더한다.

실제로 해 본 것이 `pages/demo-table/ReviewCards.tsx` 다. `ui/` 의 것을 하나도 가져오지 않고 공개 표면만 써서 카드 목록을 그렸고, 같은 동작 테스트가 표와 카드 둘 다에서 통과한다. 카드 화면은 표에 있던 흠 하나도 같이 물려받았다: 펼친 행 속의 입력 칸에서 <kbd>End</kbd> 처럼 브라우저가 스스로 스크롤하는 키를 누르면 끝에 조금 못 미쳐 멈출 때가 있다(행을 흐름대로 쌓고 묶음을 내리는 법과 브라우저의 스크롤 앵커링이 부딪힌다. 고치지 않았다). 새로 쓸 파일의 줄 수와 정리 전후는 [기록](#기록)에 있다.

## 문서 뷰어의 검토 상태와의 관계

**따로 두었다.** 뷰어의 것(`src/widgets/doc-viewer/model/review.ts`: 검토대기·확정·반려 셋, 항목 하나에 붙는다)과 표의 것(일곱 상태, 후보·재계산·배출량 조건이 붙는다)은 상태도 조건도 다르다. 겹치는 것은 「반려는 사유가 필수다」 한 줄과 결과의 꼴(`{ ok, … }`)뿐이라, 공통 코드를 뽑으면 한 줄짜리 함수 하나가 두 부품을 묶게 된다. 뷰어의 검토가 무엇에 붙는지(값 한 쌍인지, 표인지, 문서인지)도 아직 정해지지 않았다. 그것이 정해지고 뷰어의 항목이 이 표의 행과 같은 것이 되면, 그때 뷰어가 이 폴더의 `model` 을 쓰게 하면 된다.

## 확인하는 법

`apps/web/scripts/verify.sh` 가 문서 뷰어의 것과 같이 돌린다([문서 뷰어](doc-viewer.md#확인하는-법)). 검토 표의 몫은: 업무 로직 단위 테스트(전이표 56칸, 조건, 일괄, 요약, 입력 검증, 배출량 표기·단위), 구조 규칙 시험(`src/app/guards/layers.test.ts`. 파일을 글자로 읽는 것이라 문자열을 조립한 import 는 못 잡는다. 헤드리스 칸이 모양을 품지 않는지도 여기서 본다), 헤드리스 훅 테스트, 모양 없는 컴포넌트 테스트(`hooks/components.test.tsx`: CSS 없이 그려도 보이는 행만 제자리에 놓이는가, 키보드 가드, 접근성 속성, 한 행만 다시 그리기), 표 화면에만 있는 것의 테스트(`ui/ReviewTable.test.tsx`: 모두 고르기, 키보드를 받는 자리, 잠긴 조작, 건너뛴 까닭과 반려 사유의 글자, 한 행만 다시 그리기, 계산 실패의 표시), 두 화면 공통 동작 테스트, 실제 브라우저 테스트(`e2e/review-table.spec.ts`: 가짜 5,000행, 계산 실패 흐름, 카드 화면에서 5,000행의 끝까지 가기, 펼친 행 속 입력 칸에서 End, 접근성 트리에서 머리글 줄이 grid 의 첫 행인지와 스크롤해도 제자리인지), 그리고 저장소에 정답 필드나 실제 계수 id 가 든 JSON 이 없는지(`verify.sh` 의 마지막 단계).

## 안 한 것

- **서버 연결.** 자료 가져오기, 저장, 낙관적 갱신, 오류 처리, 인증이 없다. 붙일 자리는 `useReviewRows.ts` 의 `onChange` 와 `TablePage.tsx` 의 자료 읽기다.
- **배출량 계산.** 데모 화면의 계산은 대역이다. 카테고리를 고쳐도 값이 달라지지 않는다. 계산 실패도 대역이 일부러 내는 것이다(`&calcFail=`).
- **재추천의 처리.** 「재추천요청」 상태로 바뀌는 것까지다. 새 후보가 돌아오는 길이 없다.
- **검토 이력(누가·언제).** 펼친 행에 자리만 있다.
- **열 구성의 결정, 메뉴, 디자인.** 열은 띄워 보는 화면이 예로 정한 것이다. 열 너비 조절, 열 숨기기, 가로 스크롤, 머리글 고정(머리글은 스크롤 상자 밖에 있다)이 없다.
- **정렬된 채로 상태를 바꾸면 행이 자리를 옮긴다.** 상태 열로 정렬해 둔 채 한 행을 확정하면 그 행이 다른 자리로 간다. 막지 않았다. 막으려면 「정렬을 누른 순간의 차례를 굳혀 두고, 다시 누를 때만 새로 정렬한다」를 헤드리스 층(`useReviewTable.ts`)에 넣어야 하는데, 그러면 걸러 보기와 일괄 동작 뒤에 보이는 차례가 정렬 표시와 어긋난다. 어느 쪽이 맞는지는 화면 설계에서 정할 일이라 두었다.
- **상태로 걸러 보기는 화면에서 하나만 고른다.** 업무 로직은 여럿을 받는다(`RowFilter.statuses`).
- **접근성 점검, Chromium 밖의 브라우저, 픽셀 밀도 2.** `role="grid"` 의 구조(머리글 줄까지)와 이름표는 달았고 Chromium 의 접근성 트리로 확인했지만, 화면 읽기 프로그램으로 써 보지 않았다. 표 화면에서 초점을 받는 요소는 grid 가 아니라 그 안의 스크롤 상자(`rowgroup`)이고, 「지금 행」은 보조 기술에 알리지 않는다(`aria-activedescendant` 가 없다).
- **엑셀 올리기, 표에 직접 입력.**

## 기록

개발하며 남긴 글과 잰 값이다. **그때 경로는 옛 이름이다**(웹이 층 다섯으로 바뀌기 전). 아래 표로 지금 자리를 찾는다.

| 그때 | 지금 |
|---|---|
| `src/review-table/` | `src/widgets/review-table/` |
| `domain/` | `model/` |
| `headless/` | `hooks/` |
| `review-table/layers.test.ts`(`layers.test.ts`) | `src/app/guards/layers.test.ts` |
| `src/review-table-demo/` | `src/pages/demo-table/` |
| `review-table/index.ts` | `widgets/review-table/index.ts` |
| `review-table/domain/index.ts` | `widgets/review-table/model/index.ts` |
| `src/doc-viewer/domain/review.ts` | `src/widgets/doc-viewer/model/review.ts` |
| `?view=table`(`http://localhost:15173/?view=table`) | `/dev/table`(`http://localhost:15173/dev/table`) |
| `packages/` | 서버와 같이 쓰는 자리는 아직 없다 |

그때의 글:

- 그때 표의 입력은 판 1 이었고 배출량은 kgCO2e 였다(예시의 `"emission": 1800`·`"emission": 3000`). 지금은 판 2, tCO2eq 다(위 [입력의 꼴](#입력의-꼴)).
- 계산 실패를 따로 두기 전에는 이 경우가 `no_emission` 으로 뭉개져, 사람이 「값이 없는 행」과 「잠깐 실패한 행」을 가를 수 없었다.
- 머리글 줄을 grid 안에 넣기 전에는 머리글 줄이 grid 밖에 있었고 행 수와 순서에 들어 있지 않았다.
- 그때 「라우팅」도 안 한 것이었다. 그때 model 칸을 서버와 같이 쓰게 되면 「이 폴더를 통째로 `packages/` 로 옮길 수 있다」고 적었다.
- 그때 `layers.test.ts` 의 `ui` 줄에 새 UI 라이브러리의 이름을 더한다고 적었다(지금은 위 「화면을 다른 UI 라이브러리로 바꾸는 순서」의 5).

그때의 주소 표:

| 주소 | 무엇 |
|---|---|
| `?view=table&data=sample` | 손으로 쓴 예시 8행(`public/sample/review-table.json`). 일곱 상태가 다 있고 후보가 0·1·2·3개인 행이 있다 |
| `?view=table&data=fake&rows=5000` | 코드로 만든 가짜 5,000행(씨앗 고정, `src/review-table-demo/fakeRows.ts`). `rows` 로 행 수를 바꾼다 |
| `?view=table&data=local` | 실제 자료(아래처럼 변환해 두었을 때) |
| `&calcDelay=800` | 계산 대역이 0.8초 뒤에 답한다. 「재계산 대기」가 어떻게 보이는지 볼 때 |
| `&calcFail=1` | 계산 대역이 행마다 첫 계산을 실패한다(숫자는 실패할 횟수). 「계산하지 못했다」와 「다시 계산」을 볼 때. `&calcDelay=` 와 같이 주면 실패도 그만큼 늦게 온다 |

**실제 자료에 무엇이 있고 없는가**(148행, 후보 172개 기준. 그때 배출량 대역은 kgCO2e 였다):

| 표의 칸 | 어디에 있는가 | 얼마나 채워지는가 |
|---|---|---|
| 품목명, 단위, 예측 카테고리, 추천 계수(0~3개), 계산 기준, 상태 | 실행 결과 `rows.json` | 전부 |
| 계수의 이름·값·단위·출처 | 계수 표 `factors.jsonl` | 후보 172개 전부 |
| 후보별 매핑 이유, 신뢰도 | `rows.json` 에는 **없다.** 옆의 호출 기록 `calls.jsonl` 의 응답 글에 있다. 호출 기록에는 행 id 가 없어 품목명+단위로 잇는다(148행에 열쇠가 132가지라, 30행은 같은 열쇠를 나눠 쓴다. 이유는 계수 id 까지 맞는 것만 붙인다) | 후보 172개 중 154개. 나머지 18개는 호출 없이 기억에서 온 행이다 |
| 수량, 금액 | `rows.json` 에는 **없다.** 실행에 넣었던 내역 `scope3-examples/rows.synthetic.jsonl` 에 있다(전부 가상 내역) | 수량은 148행 중 129행 |
| 계산된 배출량 | **어디에도 없다**(계산 상태의 이름만 있다) | 변환이 대역으로 채운다: 수량 × 계수, 단위가 같을 때만(kg ↔ t 만 바꾼다). 후보 172개 중 54개만 값이 나온다 |

**잰 값: 많은 행에서.** 5,000행에서 DOM 에 있는 행은 멈춰 있을 때 29개, 스크롤하는 중에 많을 때 38개였다(화면 1400×900). 그려 본 적 없는 행은 접힌 높이(36px)로 어림했다.

잰 값(가짜 5,000행, Apple M3 Pro, 머리 없는 Chromium, 화면 1400×900·픽셀 밀도 1, **빌드한 것을 `vite preview` 로**, 5회의 중앙값. `pnpm --filter @esg/web measure:table` 로 다시 잰다):

| 동작 | 화면에 그려질 때까지 | 그중 React 의 계산 | 다시 그린 행 |
|---|---|---|---|
| 첫 그리기(주소를 연 때부터. 가짜 행 만들기와 입력 검증 포함) | 106ms (100~230) | | 29 |
| 스크롤 한 번(전체의 1/20씩) | 15ms (10~22) | | 38 |
| 정렬 | 16ms | 7ms | 29 |
| 걸러 보기(글자) | 17ms | 6ms | 29 |
| 한 행 펼치기 / 반영 | 17ms / 12ms | 1ms / 3ms | 1 |
| 일괄 반영(5,000행 대상, 3,625행 적용) | 16ms | 6ms | 18 |
| 일괄 최종 확정(5,000행 대상, 3,872행 적용) | 14ms | 5ms | 16 |

읽는 법: 「화면에 그려질 때까지」는 동작을 일으킨 때부터 다음 화면 그리기가 끝난 직후까지라, 값마다 한 프레임(약 17ms)까지의 기다림이 섞여 있다. 그래서 대부분 15ms 안팎으로 같게 나온다. 「React 의 계산」은 그 기다림을 뺀 것이다. 한 행을 바꾸면 그 행 하나만 다시 그린다. 일괄 동작은 5,000행을 다 바꾸지만 다시 그리는 것은 화면에 있던 행 가운데 바뀐 것뿐이다. 요구의 「조회·입력 3초 이내」와는 자릿수가 다르지만, **이 숫자에는 서버 왕복이 없다.** 재지 않은 것: 손으로 끄는 연속 스크롤(스무 번의 건너뛰기로만 쟀다), 펼친 행이 많을 때, 메모리, 느린 기계. 2,000행에서는 차이가 없었고(첫 그리기 100ms), 50,000행에서는 첫 그리기 212ms, 정렬 71ms, 일괄 52ms, 한 행 반영 33ms 였다(3회). 수치에 맞춰 코드를 다듬지 않았다. 행 창과 행 틀을 헤드리스 컴포넌트로 내린 뒤 같은 조건으로 다시 쟀을 때 「다시 그린 행」의 열은 전부 같았다(29 · 38 · 29 · 29 · 1 · 18 · 16). 시간의 열은 그때 다시 적지 않았다.

★ `tools/measure-table.ts` 는 지금도 바탕 주소 뒤에 `?view=table&data=fake…` 를 붙여 연다. 경로 `/` 는 `/greenwash` 로 넘어가고 옛 `?view=` 는 넘기지 않으므로(`src/app/router.tsx`), 화면 경로가 `/dev/table` 로 바뀐 뒤 이 스크립트를 다시 돌려 보지 않았다.

**고른 것과 까닭**(행 창과 행 틀. 그때의 표):

| 고른 것 | 까닭 | 버린 것 | 바꾸려면 |
|---|---|---|---|
| 행을 놓는 법은 하나: 흐름대로 쌓고 묶음을 한꺼번에 내린다 | 스크롤해도 이미 그린 행이 받는 값이 안 바뀐다. 펼친 행 아래가 재기 전에도 안 겹친다. 행 틀이 자리(`start`)를 몰라도 된다 | 행마다 `transform`(카드 화면이 전에 쓰던 법)도 받기: 길이 둘이 되고, 펼친 행 아래의 행들이 자리가 바뀔 때마다 다시 그려진다 | `RowStack.tsx` 의 묶음 `<div>` |
| 훅이 스크롤 요소의 ref 를 쥔다(뷰어의 훅은 ref 를 안 내주고 값으로만 말한다) | TanStack Virtual 이 스크롤 요소를 직접 지켜보고 「이 행이 보이게」도 스스로 스크롤한다. 값으로만 말하게 하려면 그 연결을 다시 써야 한다 | 뷰어처럼 `scrollRequest` 값으로: TanStack 을 거스른다 | `useRowWindow.ts`, `RowStack.tsx` |
| `RowStack` 이 `RowFrame` 을 직접 놓는다 | 화면이 `key` · `measureRef` · `data-index` 를 빠뜨릴 수 없다 | 화면이 행 틀을 하나씩 놓기 | `RowStack.tsx` |
| 행의 속은 그리는 함수로(`renderRow`) | 칸의 생김은 화면마다 통째로 다르다(표의 칸 줄, 카드) | 클래스 이름만 받기: 속을 못 바꾼다. 컴포넌트 타입 + 공용 props: `useCallback` 과 같은 약속이 필요하면서 덜 익숙하다 | `RowFrame.tsx` |
| 머리글 줄의 칸은 화면이 그리고, 줄 자체와 그것을 grid 안에 넣는 일은 `RowStack` 이 한다(`header`). 「걸러 본 결과가 전부 골라졌는가」만 훅의 값(`table.allSelected`)으로 | 머리글의 칸은 표 모양에만 있다(카드에는 없다). 행 수와 순서를 세는 접근성 구조는 `RowStack` 의 일이라 머리글 줄도 거기서 센다 | 헤드리스 `HeaderRow`(열을 돌며 화면의 함수를 부르는 껍데기만 남는다). 머리글 줄을 grid 밖에 두기(전의 꼴: 표의 행이 아니게 된다) | `ui/ReviewTable.tsx`, `RowStack.tsx`, `useReviewTable.ts` |
| 머리글 줄은 스크롤 상자 밖, grid 안에 둔다 | 스크롤 상자와 가상 스크롤이 그대로다. 스크롤 길이가 안 바뀌고 머리글은 스크롤해도 제자리에 있다 | 스크롤 상자 안에 넣고 위에 붙이기(sticky): grid·스크롤·초점이 한 요소라 뜻은 더 깔끔하지만, 스크롤 길이가 머리글만큼 늘고 가상 스크롤에 머리글 높이를 알려야 한다(어긋나면 끝에서 마지막 행이 잘린다) | `RowStack.tsx` 의 끝 |
| 펼친 높이가 스크롤 길이에 한두 프레임 늦게 들어오는 것은 그대로 둔다 | 사람 손이 닿는 틈이 아니다(CPU 를 6배 늦춰도 0.1초 남짓). 자동 조작이 펼치자마자 입력 칸에서 End 를 누를 때만 스크롤이 끝에 못 닿는다 | 다시 그려진 행을 그 그리기 안에서 다시 재기(`useLayoutEffect` → TanStack Virtual 의 `resizeItem`): 해 봤고 틈은 닫혔지만, 작은 창의 두 단계에서 화면 밖 여유분 행 하나가 한 번 더 그려졌고 행의 속이 스스로 높이를 바꾸는 경우는 못 닫았다. 스크롤 상자에 `overflow-anchor: none`(앞서 제안된 고침): 까닭이 스크롤 앵커링이 아니라 듣지 않았다 | `RowFrame.tsx`, `useRowWindow.ts` |
| `grid-template-columns` 는 모양으로 본다(화면에 둔다) | 열의 너비와 배치는 디자인이다. 카드에는 열이 없다 | 헤드리스가 열 너비를 인라인으로 | `ui/ReviewTable.tsx` 의 `template` |
| 스크롤 상자의 이름표 `data-testid="rt-scroll"` 를 `RowStack` 이 붙인다 | 두 화면 공통 동작 테스트와 측정 스크립트가 이 이름으로 찾는다. 화면마다 다시 붙이지 않는다 | 화면이 붙이기 | `RowStack.tsx` |

**새로 쓸 파일과 줄 수**(주석 포함. 행 창과 행 틀을 내리기 전과 뒤. 지금 줄 수는 서식 도구를 들인 뒤라 다르다):

| | 전 | 후 |
|---|---|---|
| `ui/ReviewTable.tsx` | 157줄. 이 가운데 구조가 약 40줄(스크롤 ref, 높이 상자, 묶음 내리기, 행마다 `measureRef` · `data-index` · `role` · 상태 속성 여덟, 키보드 가드, `memo`) | 139줄. 구조 0줄(`<RowStack …>` 한 줄과 `useCallback`, 머리글 줄의 칸) |
| `ui/RowDetail.tsx`, `Toolbar.tsx`, `format.ts`, `review-table.css` | 142 + 85 + 6 + 32줄 | 142 + 85 + 6 + 35줄(CSS 는 `overflow-y` 한 선언이 `RowStack` 으로 갔고, grid 의 높이를 묶는 규칙 하나가 늘었다) |
| 다시 쓰지 않는 것 | `domain/`, 훅 넷 | `domain/`, 훅 넷, `RowStack.tsx` 119줄, `RowFrame.tsx` 66줄(머리말의 설명 포함) |

실제로 해 본 것이 `review-table-demo/ReviewCards.tsx` 다. `ui/` 의 것을 하나도 가져오지 않고 공개 표면만 써서 카드 목록을 그렸고, 같은 동작 테스트 일곱이 표와 카드 둘 다에서 통과한다. 전에는 이 파일이 구조를 한 벌 더 썼다(186줄. 스크롤 ref, 높이, 카드마다 `transform`, `measureRef`, 키보드 가드, 상태 속성). 지금은 `<RowStack>` 한 줄이고 구조 코드가 없다(183줄. 줄 수가 거의 안 준 것은 카드가 받는 것을 하나씩 적은 props 타입 12줄이 생겨서다). 이 정리에서 카드 화면은 달라진 것이 있다: 행을 놓는 법이 표와 같아졌고(카드마다 `transform` → 묶음 한 번), 요소가 `ul` · `li` 에서 `div` 로 바뀌었고, `role` · `aria-rowcount` · `aria-rowindex` 가 생겼고, Ctrl 과 같이 누른 키를 이제 무시하고, 한 장을 바꾸면 그 한 장만 다시 그린다(전에는 화면의 21장 전부). 표 화면은 스크롤 상자에 인라인 `overflow-y: auto` 가 생긴 것(같은 선언이 CSS 에서 빠졌다) 말고는 DOM 과 동작이 그대로다.
