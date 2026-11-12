# 문서 뷰어 (widgets/doc-viewer)

PDF 쪽을 그리고, 그 위에 강조 상자를 얹고, 옆의 항목 목록과 서로 잇는 화면 부품이다. 항목을 누르면 그 쪽의 그 상자로 가고, 상자를 누르면 그 항목이 골라진다. 항목마다 검토 상태(검토대기 → 확정 / 반려)가 있다.

**부품은 서버를 부르지 않는다.** 자료를 받아 그릴 뿐이고, 서버(`apps/api-py`)에 잇는 것은 쓰는 화면의 일이다. 데모 화면(`/dev/viewer`)은 정적 JSON 파일을 읽고, 검토 상태는 화면 안에만 있어 새로 고치면 사라진다. 부품은 「위치가 적힌 자료」를 입력으로 받을 뿐, 그 자료가 어느 기능의 결과인지 모른다. 그린워싱 검토 화면(`src/pages/greenwash-review/`)도 이 부품을 쓴다.

여기 쓴 도구와 폴더 나눔은 연습용으로 고른 것이다. 정해진 스택이나 컨벤션이 아니다. 고른 것마다 바꾸는 법을 [아래](#고른-것과-바꾸는-법)에, 고른 까닭과 잰 값을 [기록](#기록)에 적었다.

경로는 `apps/web/` 기준이다. 폴더 규칙(층 다섯, 칸)은 [`../README.md`](../README.md) 에 있다.

## 띄우는 법

필요한 것: Node 22.22.2 이상(`apps/web/package.json` 의 `engines`. node 가 `.ts` 를 바로 돌리는 기능이 22.18 부터이고, 부품 테스트가 쓰는 jsdom 30 이 22.22.2 부터를 요구한다), pnpm 10(뿌리 `package.json` 의 `packageManager`). Docker 는 필요 없다.

```sh
pnpm install --frozen-lockfile
pnpm --filter @esg/web dev        # 서버가 뜬다. 브라우저로 http://localhost:15173/dev/viewer 에 간다. 포트가 겹치면 WEB_PORT=15273 pnpm --filter @esg/web dev
```

`dev` 는 먼저 `tools/prepare.ts` 를 돌려 예시 PDF 둘을 코드로 만들고(`public/sample/`), pdf.js 의 부속 파일을 `public/pdfjs/` 에 복사한다(둘 다 `.gitignore` 되어 있다). 저장소에는 PDF 가 없다. 데모 경로(`/dev/*`)는 개발 서버이거나 `VITE_DEMOS=1` 로 빌드했을 때만 있다(`src/app/router.tsx`).

화면 위의 「자료」에서 고른다.

- **예시: 두 문서 대조** — 문서 둘을 나란히. 항목 여섯 개. 세 번째 쪽은 쪽 자체가 90도 돌아간 PDF 다.
- **예시: 문장 강조(가짜 자료)** — 문서 하나. ★ 「의심 문장」을 찾아낸 것이 아니다. 문장 몇 개를 손으로 골라 강조만 해 본 것이고, 검출 로직은 어디에도 없다. 넷째 항목은 두 줄에 걸친 문장이다(줄마다 상자 하나, 둘이 한 강조).

써 볼 것: 항목 누르기, 상자 누르기(같은 자리에 겹친 상자는 `×2` 처럼 개수가 붙고, 누를 때마다 다음 항목으로 돈다), 항목에 마우스만 올려 보기(그 상자가 진해진다), 위 띠의 「강조」에서 보기 방식 셋 바꿔 보기, 왼쪽 위 범례의 종류를 눌러 끄고 켜기, <kbd>j</kbd>·<kbd>k</kbd> 로 다음·이전 항목, 확대·축소·폭 맞춤·회전, 「좁힌 자리로 보기」 끄기, 사유 없이 반려해 보기. 보기 방식과 범례는 [아래](#강조의-보기-방식과-범례)에 적었다.

## 실제 자료를 붙이는 법

실제 PDF 와 그것을 분해·대조한 산출물이 따로 있을 때, 그것을 뷰어 입력으로 바꿔 띄운다. 자료는 환경 변수가 가리키는 곳에서 읽고, 바꾼 결과는 `VIEWER_DATA_DIR` 에 쓴다. **저장소에는 아무것도 남기지 않는다.**

단계는 둘이다. 먼저 문서를 분해하는 쪽에서 **글자 자리**(`char-places.json`)를 낸다. 칸·숫자·문장의 좁은 상자가 여기서 나온다. 이것은 분해 도구의 일이고 이 저장소 밖에서 돈다(그 저장소의 `py/` 에서).

```sh
# 1. 글자 자리 내기 (문서를 분해하는 저장소의 py/ 에서. 문서마다 한 번. 문서 하나에 2~8초)
#    --places 를 주면 document.json 곁에 char-places.json 이 하나 더 나온다. --out 은 그 저장소 밖의 폴더로 준다(있던 산출물을 덮어쓰지 않게).
uv run python -m docparse parse <PDF 폴더>/<문서 이름>.pdf --out <글자 자리 폴더>/parse-<문서 이름> --places
```

```sh
# 2. 뷰어 입력으로 바꾸기 (이 저장소에서)
export VIEWER_DATA_DIR=~/viewer-data            # 바꾼 자료를 둘 폴더. 저장소 밖을 권한다. 절대 경로로 준다(상대 경로는 apps/web 기준으로 읽힌다)
export ESG_LAB_OUT=<산출물 폴더>                 # parse-<문서 이름>/document.json 과 대조 실행의 outcome.json 이 있는 곳
export ESG_REPORTS=<PDF 폴더>                    # <문서 이름>.pdf 가 있는 곳
export VIEWER_PLACES=<글자 자리 폴더>             # 1 에서 --out 으로 준 폴더의 부모. parse-<문서 이름>/char-places.json 을 읽는다. 안 주면 ESG_LAB_OUT 에서 찾는다
export VIEWER_DOC_A=<문서 이름> VIEWER_DOC_B=<문서 이름>
export VIEWER_RUN=<대조 실행의 폴더>              # ESG_LAB_OUT 아래의 경로
export VIEWER_EXAM=<시험지 폴더>                  # (선택) ESG_LAB_OUT 아래의 경로. 판정이 오류를 심은 사본에 대해 난 경우

pnpm --filter @esg/web convert     # a.pdf, b.pdf, reconcile.json, sentences.json, index.json, places-report.json 을 VIEWER_DATA_DIR 에 쓴다
pnpm --filter @esg/web dev         # 같은 셸에서(VIEWER_DATA_DIR 를 읽는다). /dev/viewer 의 「자료」에 「실제 자료: …」 둘이 더 보인다
```

- `convert` 의 출력에 문서마다 글자 자리 파일을 읽었는지, 강조 가운데 몇 개가 칸·숫자의 상자를 얻었는지가 나온다.
- **글자 자리 파일이 없으면** 멈추지 않고, 좁은 상자 없이 표·문단 전체 상자만 넣는다. 화면의 알림과 `convert` 의 출력에 그렇게 적힌다. PDF 의 글자를 뒤져 자리를 짐작하지 않는다(까닭은 [기록](#기록)).
- **글자 자리와 `document.json` 이 서로 다른 PDF 의 것이면**(두 파일의 `source.sha256` 이 다르면) `convert` 가 멈춘다. 그대로 쓰면 상자가 엉뚱한 글자를 가리킨다.
- **`ESG_REPORTS` 의 PDF 가 `document.json` 을 낸 그 파일이 아니면**(파일의 sha256 이 `source.sha256` 과 다르면. 같은 이름의 다른 판) `convert` 가 멈추고 아무것도 쓰지 않는다. 결과 폴더도 만들지 않는다. PDF 가 없을 때도 같다. `source.sha256` 은 분해 도구가 PDF 파일을 통째로 읽어 낸 해시다(`tools/lab/load.ts` 의 `assertSamePdf`).
- `VIEWER_DATA_DIR` 를 안 주면 `apps/web/.local-data/` 에 쓴다. `.gitignore` 와 `.dockerignore` 에 들어 있지만, 저장소 밖에 두는 편이 실수할 틈이 적다.
- 개발 서버가 그 폴더를 `/local/` 주소로 내준다(`vite.config.ts` 의 `localData`). JSON 과 PDF 만 준다.
- 화면에 보일 문서 이름은 `VIEWER_TITLE_A`, `VIEWER_TITLE_B` 로 준다(기본은 「문서 A」「문서 B」). 문서 이름을 코드에 적지 않으려고 환경 변수로 받는다.
- `apps/web/scripts/verify.sh` 의 마지막 단계가 `apps/web` 아래에 PDF·실제 자료 폴더의 파일·200KB 넘는 JSON 이 들지 않았는지 본다(`apps/api-py` 는 보지 않는다. 거기는 공개 배출계수 사본과 골든을 일부러 품는다).

두 문서 대조 자료에서 알아 둘 것:

- 항목 = 판정 하나(두 자리의 값이 일치/불일치) 또는 짝을 못 찾은 자리 하나. 짝지어지지 않은 표의 칸 같은 나머지 「확인 못 함」은 수천 개라 목록에 넣지 않고 화면 위 알림에 개수만 적는다.
- 판정이 오류를 심은 시험지에 대해 난 것이면, 불일치 항목이 PDF 화면에서는 같은 값으로 보인다(PDF 는 원본이다). 항목에 「판정이 본 값 / PDF 원문의 값」을 같이 적는다.
- 문장 강조 자료는 실제 문서로 만들어도 **가짜**다. 숫자가 든 문단을 일곱째마다 하나씩 고르고, 그 안에서 숫자가 든 첫 문장 하나를 강조할 뿐이다(`tools/lab/sentences.ts`). 여러 줄에 걸친 문장은 줄마다 상자 하나다.

## 입력 계약

뷰어가 받는 것은 이 꼴의 값 하나다. 타입과 검증은 `src/widgets/doc-viewer/model/contract.ts`, 손으로 쓴 예시는 `public/sample/compare.json`.

```jsonc
{
  "version": 1,
  "notice": "화면 위에 띠로 보일 알림(선택)",
  "documents": [                       // 하나면 한 문서 배치, 둘이면 나란히
    { "id": "a", "title": "보일 이름(선택)", "url": "sample/sample-a.pdf",
      "pages": [{ "width": 595, "height": 842 }] }   // 쪽별 크기. pages[0] 이 1쪽
  ],
  "highlights": [
    { "id": "1-a", "documentId": "a", "page": 1,     // 쪽은 1부터
      "box": [72, 200, 522, 320],                    // 확실한 범위(표 전체, 문단 전체)
      "innerBoxes": [[372, 230, 522, 260]],          // (선택) 그 안에서 좁힌 자리의 상자들(칸, 숫자 하나, 문장 하나). 여러 줄에 걸치면 줄마다 하나
      "kind": "match",                               // 종류. 뷰어는 뜻을 모른다. 색을 가르고, 범례에서 켜고 끌 뿐이다
      "text": "1,234" }                              // (선택) 그 자리의 글자. 마우스를 올리면 보인다
  ],
  "items": [
    { "id": "1", "title": "제목", "detail": "덧붙는 글(선택)",
      "highlightIds": ["1-a", "1-b"],                // 문서 하나 또는 둘에 걸친다
      "review": { "status": "pending" } }            // pending | confirmed | rejected(+ reason)
  ],
  "kinds": [{ "kind": "match", "label": "일치", "color": "#15803d" }]   // (선택) 종류별 이름과 색
}
```

- **좌표**: `[왼쪽, 위, 오른쪽, 아래]`, 단위는 PDF 포인트(1/72 인치), 원점은 쪽의 **왼쪽 위**, y 는 아래로 자란다. 쪽이 화면에 바로 놓였을 때의 자리다(PDF 에 쪽 회전이 적혀 있으면 돌린 뒤의 자리). `pages` 의 크기도 같은 기준이다. PyMuPDF 의 `page.rect` 기준 좌표와 같다.
- 화면 자리는 `좌표 × 배율` 이다. 뒤집지 않는다(`src/widgets/doc-viewer/model/geometry.ts`).
- 검증은 두 단계다. 꼴(zod)이 맞는지 본 뒤, 서로 가리키는 것이 실제로 있는지 본다: 없는 문서·없는 쪽을 가리키는 강조, 쪽 밖으로 나가는 상자, 없는 강조를 가리키는 항목, 겹치는 id. 틀린 곳을 전부 모아 문장으로 돌려준다.
- **좁힌 자리는 상자 여럿일 수 있다(`innerBoxes`).** 글자 범위가 두 줄에 걸치면 상자가 둘이다. 상자가 여럿이어도 강조는 하나다: 같이 골라지고, 같이 가리켜지고, 어느 상자를 눌러도 같은 항목이 골라진다. 상자는 전부 그 강조의 쪽(`page`) 위에 있어야 한다(쪽을 넘는 강조는 강조 둘로 나눠 한 항목에 묶는다).
- **예전 꼴도 그대로 받는다.** 상자 하나를 `"innerBox": [..]` 로 적은 자료는 `innerBoxes: [[..]]` 와 같은 뜻으로 읽힌다(`contract.ts` 의 `innerBoxesOf` 가 둘을 하나로 읽는다). 둘을 같이 주면 거부한다. `innerBoxes` 는 비어 있으면 안 된다(없으면 필드를 뺀다).
- **자료를 만드는 쪽이 좁힌 자리를 넣는다.** 뷰어가 PDF 글자를 뒤지는 로직을 품으면 「위치를 입력으로 받는 부품」이 아니게 된다. 그 좌표는 문서를 분해하는 쪽(글자 하나하나의 좌표를 아는 쪽)이 낸다. 뷰어는 상자가 어디서 왔는지 모른다.

## 부품을 다른 화면에서 쓰는 법

`src/pages/demo-viewer/App.tsx` 가 「쓰는 쪽」의 예다. 필요한 것은 셋이다. 폴더 밖에서는 공개 표면(`src/widgets/doc-viewer/index.ts`)으로만 가져다 쓴다.

```tsx
import { DocumentViewer, parseViewerInput, useReviews } from "../../widgets/doc-viewer/index.ts";
import type { ViewerInput } from "../../widgets/doc-viewer/index.ts";
import { openPdf } from "../../widgets/doc-viewer/pdfjs.ts";       // pdf.js 구현은 따로 가져온다(아래 「세 층」)

function Screen({ raw }: { raw: unknown }) {          // raw: 어디선가 가져온 자료
  const parsed = parseViewerInput(raw);
  if (!parsed.ok) return <pre>{parsed.errors.join("\n")}</pre>;
  return <Review input={parsed.input} />;
}
function Review({ input }: { input: ViewerInput }) {
  const reviews = useReviews(input.items);            // 검토 상태를 든다. 서버를 붙일 자리가 여기다
  return <DocumentViewer input={input} openPdf={openPdf} reviews={reviews.states} onReview={reviews.apply} />;
}
```

- 강조의 보기 방식은 선택 입력 `highlightMode`(`"outline"` | `"selected"` | `"fill"`)로 준다. 안 주면 `"outline"`(옅게)이다. 입력 자료(JSON)에는 보기 방식이 없다. 자료가 아니라 화면의 선택이라서다.
- 부모가 높이를 줘야 한다(부품은 `height: 100%` 다).
- `openPdf` 는 그릴 때마다 새 함수여도 된다(`openPdf={(url) => …}`). PDF 를 다시 여는 까닭은 주소(`url`)가 바뀌는 것 하나다(`hooks/usePdf.ts`). 그래서 같은 주소를 다른 여는 함수로 다시 열게 하려면 부품의 `key` 를 바꿔 새로 만든다.
- `public/pdfjs/` 가 같이 배포되어야 한다(`tools/prepare.ts` 가 만든다). 없으면 한글 글꼴이 깨지고 일부 그림이 안 나온다.
- 서버를 붙일 때 바뀌는 곳: 자료를 가져오는 곳(`App.tsx` 의 `fetch`)과 `src/widgets/doc-viewer/hooks/useReviews.ts` 의 `apply`. 전이 규칙(`src/widgets/doc-viewer/model/review.ts`)은 순수 함수라 그대로 쓰고, 서버도 같은 규칙을 검사해야 한다.

## 세 층

뷰어는 `src/widgets/doc-viewer/` 한 폴더에 있고, 검토 표(`src/widgets/review-table/`)와 같은 꼴로 칸 셋이다. 화면을 통째로 바꿔도 앞의 두 칸은 그대로 쓴다.

```
model/     업무 로직. 순수 TypeScript(zod 만). React 도 DOM 도 pdf.js 도 모른다
   ↑       입력 계약, 좌표 셈, 검토 전이, 무엇을 그릴지(isDrawn), 같은 자리의 강조 묶기, 고를 항목 정하기, 종류의 색과 이름
hooks/     상태와 동작. 모양(색·선·글꼴)을 모른다. 두 가지가 있다
   ↑         훅            마크업이 없다. 상태를 들고 「무엇을, 어디로」를 정한다
   │                       useDocViewer(고르기·가리키기·종류 켜고 끄기·j/k·겹친 상자 돌기·문서 칸이 갈 곳)
   │                       usePaneView(배율·회전·지금 쪽·그릴 쪽들·쪽 이동), usePdf, useReviews, useReviewDraft
   │         모양 없는 컴포넌트   구조(DOM)와 자리(인라인 style)와 상태 표시(data-*)는 갖고, 색·선·글꼴은 없다
   │                       PageStack(스크롤 상자·쪽 쌓기·보이는 쪽만), PageCanvas, HighlightOverlay(강조 조각을 제자리에)
ui/        화면. 바꿔 끼우는 층. 목록, 범례, 도구 줄, 안내 글, 그리고 강조의 모양(viewer.css)
```

- **import 는 한 방향이다**(`model` ← `hooks` ← `ui`). 칸끼리는 서로의 `index.ts` 로 가져다 쓴다. 구조 규칙 시험 `src/app/guards/layers.test.ts` 가 파일을 글자로 읽어 지킨다(이 부품의 규칙은 그 파일의 `SLICES` 의 `widgets/doc-viewer` 줄).
- **폴더 밖에서 들어오는 문은 셋이다**(같은 파일의 `DOORS`). `index.ts`(화면에서 쓰는 것 전부), `model/index.ts`(화면 없는 표면. node 에서 도는 `tools/` 의 변환 스크립트가 쓴다. `index.ts` 는 화면과 CSS 를 같이 내보내 node 가 읽지 못한다), `pdfjs.ts`(pdf.js 로 PDF 를 여는 구현. 번들러의 `?url` 과 워커를 써서 node 와 jsdom 이 읽지 못해 `index.ts` 에 넣지 않았다). pdfjs-dist 를 가져오는 파일은 `pdfjs.ts` 하나다.
- **훅과 컴포넌트의 선(스크롤).** 훅은 요소를 읽거나 쓰지 않는다(하나만 예외다: `useDocViewer` 의 `onKeyDown` 이 키 이벤트의 대상이 글자 입력 칸인지 본다). `usePaneView` 는 「이 높이로 가라」(쪽 이동, 배율을 바꾼 뒤 보던 자리 지키기)를, `useDocViewer` 는 「이 상자가 보이게 가라」를 값으로 내놓고, `PageStack` 이 자기 스크롤 상자의 크기를 읽어 옮긴 뒤 훅에 알린다. 스크롤 상자를 읽고 쓰는 곳은 `PageStack.tsx` 한 파일이다. 그래서 「어디로 가는가」는 화면 없이 테스트하고(`usePaneView.test.ts`), 「갔는가」는 컴포넌트 테스트가 본다(`components.test.tsx`).
- **`hooks/` 칸의 규칙은 「모양을 모른다」다.** CSS 를 가져오지 않고, `style` 에 색·배경·테두리·글꼴을 적지 않는다. 자리(`position`, `top`, `width` …)는 적는다. 글자로 읽는 검사라 한계가 있다(변수로 건너온 값 같은 것은 못 잡는다. `layers.test.ts` 머리말에 잡는 것과 못 잡는 것의 목록).
- 검토 표와 다른 곳: 뷰어는 쪽 쌓기와 강조 얹기가 DOM 구조에 묶여 있어 훅만으로는 화면마다 다시 써야 할 것이 많이 남는다. 그래서 모양 없는 컴포넌트를 `hooks/` 에 두었다. 검토 표도 지금은 모양 없는 컴포넌트(`RowStack`·`RowFrame`)를 같은 칸에 둔다.

**각 층을 바꾸는 법**

| 바꾸려는 것 | 고칠 곳 | 그대로 두는 것 |
|---|---|---|
| 색, 선, 채움, 글꼴, 칸의 배치 | `ui/viewer.css` | 나머지 전부 |
| 목록·범례·도구 줄의 생김과 구조 | `ui/` 의 세 파일 | `model/`, `hooks/` |
| 화면 전체를 다른 UI 라이브러리로 | `ui/` 를 새로 쓴다(아래) | `model/`, `hooks/`, `pdfjs.ts` |
| 고르기·가리키기·키보드의 규칙 | `hooks/useDocViewer.ts` (+ 그 테스트) | `ui/` (훅이 돌려주는 값의 꼴이 그대로면) |
| 배율의 단계, 쪽 이동의 규칙 | `hooks/usePaneView.ts` | `ui/` |
| 무엇을 그릴지, 강조를 묶는 법, 좌표 셈 | `model/` | `hooks/`, `ui/` |
| PDF 라이브러리 | `pdfjs.ts`, `hooks/PageCanvas.tsx` | `PdfHandle`(`hooks/pdfBackend.ts`)의 꼴을 맞추면 나머지 전부 |

**화면을 다른 UI 라이브러리로 바꿀 때.** 새로 쓰는 것은 `ui/` 의 넷이다: `DocumentViewer.tsx`, `ItemList.tsx`, `PdfPane.tsx`, `viewer.css`. 이 넷에는 `useState` 가 하나도 없다(목록을 고른 항목으로 스크롤하는 `useEffect` 하나가 있다). 그대로 두는 것은 `model/`, `hooks/`, `pdfjs.ts`, 그리고 훅·헤드리스 컴포넌트·구조 규칙의 테스트다. `ui/` 를 지우고 갈아 끼울 때는 공개 표면 `index.ts` 의 끝 두 줄(`DocumentViewer` 와 그 타입을 내보내는 줄)도 새 화면을 가리키게 고친다(그 줄이 `viewer.css` 를 같이 싣는다). `ui/DocumentViewer.test.tsx` 는 본 화면의 클래스 이름(`.dv-*`)으로 요소를 찾으므로 화면과 같이 바뀐다. 클래스 이름 없이 이름표(`data-*`, `aria-label`)로만 보는 테스트는 `src/pages/demo-viewer/behavior.test.tsx` 다. 새 화면을 그 파일의 `SCREENS` 에 한 줄 더하면 같은 동작 테스트를 받는다(요구하는 이름표는 그 파일 머리말에 있다).

실제로 갈아 끼워 본 것이 `src/pages/demo-viewer/CompactViewer.tsx` + `compact.css` 다. 목록이 한 줄짜리이고 오른쪽에 있으며, 검토 단추가 목록 아래 칸에 있고, 쪽 위 강조가 상자가 아니라 형광펜과 밑줄이다. `ui/` 의 것을 하나도 쓰지 않는다. 주소에 `?screen=compact` 를 붙이면 뜬다(예: `http://localhost:15173/dev/viewer?data=sample/compare.json&screen=compact`). 위 띠에서 자료나 보기 방식을 바꾸면 주소의 `data` 와 `mode` 만 고쳐 쓰고 나머지 인자는 그대로 둔다(`src/shared/lib/address.ts` 의 `withParams`). 그래서 새로 고쳐도 둘째 화면이다. 증명용이고 제품이 아니다.

**헤드리스 컴포넌트에 모양을 입히는 법.** 길이 셋이고, 전부 안 줘도 상자는 제자리에 놓이고 눌린다.

```tsx
<PageStack
  pane={pane}                                   // usePaneView(doc.pages) 가 돌려준 것을 통째로
  reveal={viewer.revealFor(doc.id)}             // 「이 상자가 보이게 가라」
  classNames={{ scroller: "my-scroller", stack: "my-stack", page: "my-page" }}
  renderPage={(pageNumber, page) => (
    <>
      <PageCanvas pdf={pdf} pageNumber={pageNumber} scale={pane.scale} rotation={pane.rotation} className="my-canvas" />
      <HighlightOverlay
        highlights={viewer.highlightsOn(doc.id, pageNumber)} page={page} scale={pane.scale} rotation={pane.rotation}
        draw={viewer.draw} onPick={viewer.pick}
        classNames={{ layer: "my-layer", group: "my-group", context: "my-context" }}   // 1) 판·틀·context 의 클래스 이름
        pieceProps={(group) => ({ className: "my-piece", style: { color: colorOf(group.kind) }, title: "…" })}   // 2) 조각마다의 className·style·title
        renderCount={(count) => <span className="my-count">{count}</span>}             // 3) 겹친 개수 딱지
      />
    </>
  )}
/>
```

- CSS 는 헤드리스 컴포넌트가 붙이는 표시를 보고 쓴다: 판의 `data-mode`(`outline` | `selected` | `fill`), 조각의 `data-selected`·`data-pointed`·`data-narrowed`. 보기 방식 셋의 차이는 전부 화면의 CSS 가 `data-mode` 를 보고 낸다(무엇을 그릴지는 `model` 의 `isDrawn`, 어떻게 보일지는 `ui`).
- 한 강조의 조각들은 틀(`group`) 하나 안에 든다. 「한 조각에 마우스를 올리면 다른 줄의 조각도 같이」는 CSS 의 `.틀:hover .조각` 으로 낸다.
- `pieceProps` 의 `style` 은 자리와 크기를 덮어쓰지 못한다(컴포넌트가 뒤에 펼친다). 종류의 색처럼 자료에서 오는 값을 넣는 길이다. 본 화면은 `color` 로 넣고 CSS 가 `currentColor` 로 받는다.
- **스크롤 상자의 높이는 쓰는 쪽이 정한다**(`classNames.scroller` 로. 본 화면은 `flex: 1; min-height: 0`). 정하지 않으면 상자가 쪽을 다 쌓은 높이만큼 늘어나 쪽을 전부 그린다.
- 조각을 통째로 그리는 함수(render prop)는 받지 않는다. 자리·표시·누르기·Tab 순서를 쓰는 쪽이 다시 붙여야 해서다. `<button>` 이 아닌 요소로 그려야 하면 `HighlightOverlay.tsx` 를 고친다.

## 폴더와 읽는 차례

```
apps/web/
  src/
    widgets/doc-viewer/          문서 뷰어. 밖에서는 index.ts(화면용), model/index.ts(화면 없는 표면), pdfjs.ts 로만 들어온다
      index.ts                   공개 표면
      pdfjs.ts                   PdfHandle 의 구현. pdf.js 를 부르는 유일한 곳
      model/
        contract.ts              입력 계약: 타입, 검증                              ← 1
        geometry.ts              쪽 좌표 → 화면 좌표, 쪽 쌓기, 보이는 쪽 셈하기       ← 2
        review.ts                검토 상태의 전이 규칙(순수 함수)                    ← 3
        highlightMode.ts         강조의 보기 방식 셋과 「이 상자를 그리는가」
        highlightGroups.ts       강조 하나를 어느 상자(들)로 그리는가, 같은 자리의 강조 묶기
        selection.ts             상자를 눌렀을 때·키보드로 옮길 때 고를 항목
        kinds.ts                 종류 → 색과 이름(입력이 안 준 종류의 기본 색)
        testing.ts               테스트가 쓰는 자료
      hooks/
        useDocViewer.ts          뷰어 하나의 상태와 동작. 머리말에 「화면이 할 일」        ← 4
        usePaneView.ts           문서 칸 하나의 배율·회전·지금 쪽. 머리말에 훅과 컴포넌트의 선  ← 5
        PageStack.tsx            스크롤 상자와 쪽 쌓기(모양 없는 컴포넌트). 스크롤은 여기서만  ← 6
        HighlightOverlay.tsx     쪽 위의 강조 조각들(모양 없는 컴포넌트). 머리말에 모양을 입히는 길  ← 7
        PageCanvas.tsx           쪽 하나를 캔버스에
        usePdf.ts, useReviews.ts, useReviewDraft.ts   PDF 열기, 검토 상태(서버를 붙일 자리), 반려 사유 입력
        pdfBackend.ts            뷰어가 PDF 라이브러리에 바라는 것(인터페이스)
      ui/
        DocumentViewer.tsx       화면의 맨 위: 범례, 안내 글, 목록, 문서 칸                ← 8
        PdfPane.tsx              문서 칸: 도구 줄 + 헤드리스 컴포넌트에 모양 입히기         ← 9
        ItemList.tsx             항목 목록, 확정·반려 단추
        viewer.css               모양. 클래스는 전부 dv- 로 시작한다
    pages/demo-viewer/           띄워 보는 화면(App.tsx — 부품을 쓰는 쪽의 예), 둘째 화면(CompactViewer.tsx, compact.css), 두 화면 공통 동작 테스트(behavior.test.tsx)  ← 10
    app/guards/layers.test.ts    구조 규칙 시험(층·문·칸. 이 부품의 규칙 포함)
    shared/lib/address.ts        주소의 인자 고쳐 쓰기(바꾸는 것만 바꾸고 나머지는 둔다). 띄워 보는 화면 둘이 같이 쓴다
  tools/                       node 가 .ts 를 바로 돌린다(빌드 없음)
    prepare.ts                 예시 PDF 만들기 + pdf.js 부속 파일 복사
    sample-layout.ts, pdf-writer.ts   예시 PDF 의 내용과, PDF 를 글자로 써내는 코드
    sample-places.ts           예시 PDF 의 문단에서 글자 자리 만들기(두 줄 문장 예시의 상자가 여기서 나온다)
    sample.test.ts             예시 자료가 계약에 맞고 예시 PDF 와 같은 자리를 가리키는지
    convert.ts                 실제 자료 → 뷰어 입력
    lab/load.ts                환경 변수가 가리키는 실제 자료 읽기(글자 자리의 해시 견주기, PDF 파일의 해시 견주기 포함)
    lab/model.ts               읽어 들이는 산출물의 꼴(zod)
    lab/refs.ts                자리 표기 읽기(p59-t1:r3c1, p2-b6#n1)와 글 안의 숫자 세기
    lab/places.ts              글자 자리(char-places.json) 읽기, 글자 범위 → 줄마다 상자
    lab/reconcile.ts           대조 결과 → 항목과 강조
    lab/sentences.ts           문장 강조(가짜): 문장 가르기, 문장 하나를 줄마다 상자로
    measure-places.ts          강조가 상자를 얻었는지 세기, 사본이 원본과 어긋났는지 보기
    measure-ink.ts             상자가 화면에 그려진 글자 위에 놓였는지 캔버스의 픽셀로 재기
    measure-open.ts, measure-hover.ts, capture.ts   그 밖의 측정과 화면 캡처
    browser.ts                 위의 것들이 같이 쓰는 것(머리 없는 브라우저 띄우기)
  e2e/viewer.spec.ts           실제 브라우저 테스트(문서 뷰어)
  e2e/viewer-compact.spec.ts   실제 브라우저 테스트(둘째 화면에서도 강조가 제자리에 놓이는지)
  e2e/address.spec.ts          실제 브라우저 테스트(띠에서 자료·보기 방식·화면을 바꿔도 주소의 다른 인자가 남는지. 뷰어와 검토 표)
  e2e/fresh-build.spec.ts      브라우저 테스트가 띄운 빌드가 이번 실행에서 만들어진 것인지
  scripts/verify.sh            한 번에 확인
```

테스트는 코드 옆에 있다(`*.test.ts`, `*.test.tsx`). 층마다 보는 것이 다르다.

- 훅 테스트(`hooks/useDocViewer.test.ts`, `usePaneView.test.ts`, `smallHooks.test.ts`): 화면 없이 훅만 불러 규칙을 본다. 「다른 항목을 고르면 초점으로 가리킨 것을 지운다」, 「마우스가 초점보다 먼저」, 「꺼진 종류여도 고른 것·가리킨 것은 그린다」, 「겹친 상자를 누를 때마다 돈다」, 「확대해도 보던 자리」가 여기 있다.
- 헤드리스 컴포넌트 테스트(`hooks/components.test.tsx`): 클래스 이름도 CSS 도 없이 그려, 쪽과 조각이 제자리에 놓이고 누르기가 훅에 닿고 `data-*` 가 맞는지 본다.
- 부품 테스트(`ui/DocumentViewer.test.tsx`): jsdom 에서 가짜 PDF 로 본 화면의 「무엇이 골라지고 어느 쪽으로 가는가」와 「어느 상자가 그려지고 어떤 표시(고름·가리킴)가 붙는가」를 본다.
- 두 화면 공통 동작 테스트(`pages/demo-viewer/behavior.test.tsx`): 같은 테스트를 본 화면과 둘째 화면에 그대로 돌린다.
- 브라우저 테스트(`e2e/`): 진짜 Chromium 에서 「상자가 놓인 자리의 캔버스 픽셀이 PDF 에 칠해 둔 색인가」와 「옅게 방식에서 고르지 않은 상자의 한가운데가 쪽의 원래 그림 그대로인가(채움이 없는가)」를 본다. jsdom 은 CSS 를 그리지 않으므로 채움이 있고 없음은 브라우저 테스트만 안다.

## 확인하는 법

```sh
apps/web/scripts/verify.sh     # 설치 → 타입 검사 → 린트 → 서식 검사 → 단위·부품 테스트 → 빌드 → 데모 빠짐 → 브라우저 받기 → 브라우저 테스트 → apps/web 아래에 PDF·실제 자료가 없는지
```

단계마다 `EXIT=0`, 끝에 `VERIFY=PASS` 가 나오면 된다. 실제 자료 없이 돈다. 브라우저 테스트는 포트 15174 를 잠깐 쓴다(`WEB_TEST_PORT` 로 바꾼다). 처음 돌릴 때 머리 없는 Chromium 을 내려받는다(사용자 캐시 폴더에).

브라우저 테스트만 돌릴 때:

```sh
pnpm --filter @esg/web test:browser                                   # 전부
pnpm --filter @esg/web exec playwright test e2e/viewer.spec.ts        # 파일 하나
```

어느 쪽이든 Playwright 가 미리보기 서버를 띄우기 전에 **지금 코드를 빌드한다**(`playwright.config.ts` 의 `webServer.command`). 따로 `build` 를 먼저 돌릴 필요가 없고, 낡은 `dist` 를 시험하는 일이 없다. `verify.sh` 는 빌드 단계가 따로 있어 두 번 빌드한다.

## 고른 것과 바꾸는 법

까닭과 버린 것은 [기록](#기록)의 표에 있다(그때의 경로로). 여기는 지금 바꿀 자리만 적는다.

| 자리 | 지금 | 바꾸려면 |
|---|---|---|
| 빌드 | Vite + React + TypeScript(판은 `apps/web/package.json`) | `vite.config.ts`, `index.html` |
| PDF 그리기 | pdf.js 직접(`pdfjs-dist`) | `src/widgets/doc-viewer/pdfjs.ts` 와 `src/widgets/doc-viewer/hooks/PageCanvas.tsx` 둘. 뷰어의 나머지는 `PdfHandle`(`hooks/pdfBackend.ts`)만 안다 |
| 보이는 쪽만 그리기 | 스크롤 위치로 셈한다(`visiblePageRange`) | `model/geometry.ts` 의 `visiblePageRange` 와 `hooks/usePaneView.ts` |
| 입력 검증 | zod | `model/contract.ts` |
| 상태 | React 의 `useState` 만. 전부 `hooks/` 의 훅 안에 있다 | `hooks/useDocViewer.ts`, `usePaneView.ts`, `useReviews.ts` |
| 칸 나눔 | `model` / `hooks`(훅 + 모양 없는 컴포넌트) / `ui`, 한 방향 import | [위의 「세 층」](#세-층) |
| 헤드리스 컴포넌트의 자리 잡기 | 인라인 `style` | `hooks/PageStack.tsx`, `HighlightOverlay.tsx` |
| 헤드리스 컴포넌트에 모양을 여는 길 | 클래스 이름 + 조각마다의 `pieceProps` + 딱지를 그리는 함수 | `hooks/HighlightOverlay.tsx` 머리말 |
| 좁은 상자의 출처 | 문서를 분해하는 쪽이 낸 글자 자리(`char-places.json`)를 변환이 읽는다 | `tools/lab/places.ts`, `tools/lab/reconcile.ts` 의 `placeOf` |
| 글자 자리가 없을 때 | 좁은 상자 없이 표·문단 전체만. 알림에 적는다 | `tools/lab/load.ts` 의 `loadSide`(없으면 `places` 가 비어 온다) |
| 글자 범위 → 상자의 셈 | 분해 저장소의 셈을 옮겨 적은 사본(`spanBoxes`) | `tools/lab/places.ts` 머리말에 원본의 경로와 커밋. 어긋났는지는 `measure:places` 가 본다([아래](#글자-자리)) |
| 강조 하나에 상자 여럿 | 계약에 `innerBoxes`(배열). 화면에서는 틀 하나(`.dv-group`) 안에 줄마다 단추 하나 | `model/contract.ts`, `model/highlightGroups.ts` 의 `shapeOf`, `hooks/HighlightOverlay.tsx` |
| 여러 상자인 강조로 갈 때의 스크롤 | 조각들을 전부 감싼 상자의 윗변을 「보는 줄」에, 가로는 그 가운데를 화면 가운데에 | `hooks/useDocViewer.ts` 의 `revealFor`(어느 상자로), `hooks/PageStack.tsx` 의 「강조로 가기」(가는 것), `model/highlightGroups.ts` 의 `unionBox` |
| 강조의 보기 방식 | 부품의 입력값 하나(`highlightMode`), 기본은 옅게 | `model/highlightMode.ts` 머리말에 지울 곳을 적었다 |
| 종류 켜고 끄기 | 범례가 곧 단추. 꺼진 종류의 항목은 목록에서 흐리게 | `hooks/useDocViewer.ts` 의 `hiddenKinds`·`kindHidden`, `ui/ItemList.tsx` 의 `data-kind-hidden` |
| 항목을 가리키면 진해지기 | 마우스를 올리거나 초점이 간 항목을 뷰어의 상태로 든다 | `hooks/useDocViewer.ts` 의 `pointed`, `ui/viewer.css` 의 `data-pointed` |
| 스타일 | 화면 층의 CSS 한 파일. 모양만 있다(자리는 헤드리스 컴포넌트가 갖는다). 이 부품은 Tailwind 와 EDK 키트를 쓰지 않는다 | `src/widgets/doc-viewer/ui/viewer.css`. 클래스는 전부 `dv-` 로 시작한다 |
| 단위·부품 테스트 | vitest + jsdom + Testing Library | `vitest.config.ts` |
| 브라우저 테스트 | Playwright (머리 없는 Chromium) | `playwright.config.ts`, `e2e/` |
| 예시 PDF | PDF 를 글자 그대로 써내는 코드 | `tools/pdf-writer.ts` |
| 스크립트 실행 | node 가 `.ts` 를 바로 읽는다 | 그래서 이 패키지의 상대 경로 import 에는 전부 `.ts`·`.tsx` 를 적는다(`tsconfig.json`) |

## 강조의 보기 방식과 범례

상자가 수십 개 깔린 쪽에서 전부 채우면 표의 숫자가 가려진다. 그래서 보기 방식을 셋 두고 견주어 보게 했다. **셋 다 두는 것이 결론이 아니다.** 써 보고 하나로 굳히면 나머지를 지운다.

| 방식 | 주소 | 그리는 것 | 누를 수 있는가 |
|---|---|---|---|
| 옅게(기본값) | `?mode=outline` 또는 안 적음 | 고른 항목의 상자와 가리킨(마우스를 올린) 상자만 채운다. 나머지는 채움 없이 옅은 테두리만 | 전부 |
| 고른 것만 | `?mode=selected` | 고른 항목의 상자, 그리고 목록에서 가리킨 항목의 상자만 | 그려진 것만. 고르지 않은 상자는 없으므로 문서에서 눌러 고를 수 없다. 왼쪽에 그 안내가 뜬다 |
| 전체 채움 | `?mode=fill` | 모든 상자를 채운다(처음의 모양) | 전부 |

주소는 `/dev/viewer` 뒤에 붙인다(예: `/dev/viewer?mode=fill`).

- **조작이 놓인 자리.** 보기 방식은 띄워 보는 화면의 위 띠(「강조」)에 있다. 견주려고 둔 것이라 굳으면 사라진다. 범례(종류 켜고 끄기)와 「좁힌 자리로 보기」는 뷰어 부품 안(왼쪽 위)에 있다. 그 둘은 부품의 것이다.
- **범례.** 종류를 누르면 그 종류의 상자가 숨고, 다시 누르면 나온다. 뷰어는 종류의 뜻을 모른다(어느 종류도 특별하지 않다). 꺼진 종류의 항목은 목록에서 흐려질 뿐 남아 있고, <kbd>j</kbd>·<kbd>k</kbd> 도 그대로 밟는다.
- **늘 보이는 것.** 고른 항목의 상자와 목록에서 가리킨 항목의 상자는 종류가 꺼져 있어도, 「고른 것만」에서도 보인다. 사람이 방금 짚은 것이 안 보이면 안 되기 때문이다. 이 규칙은 함수 하나다(`highlightMode.ts` 의 `isDrawn`).
- **가리키기.** 목록의 항목에 마우스를 올리거나 키보드 초점이 가면 그 항목의 상자가 진해진다. 고르지도 스크롤하지도 않는다(그 상자가 화면 밖 쪽에 있으면 보이지 않는다. 보려면 누른다). 다른 항목을 고르면(<kbd>j</kbd>·<kbd>k</kbd>, 상자 누르기) 초점으로 가리키던 것은 지워진다.
- **겹친 상자.** 그릴 것을 먼저 추린 뒤에 같은 자리끼리 묶는다. 그래서 겹친 개수(`×n`)와 누를 때 도는 항목은 지금 그려진 것만 센다. 종류 하나를 끄면 남은 종류의 항목만 돈다.

모양에 대해: 상자의 선은 상자 바깥에 긋는다(`outline`, 1px 띄워서). 상자가 글자에 딱 붙어 있어 안쪽에 그으면 첫 글자와 끝 글자를 깎는다. 고른 것과 가리킨 것은 선이 바깥으로만 굵어진다(안으로 굵어지면 두세 글자짜리 숫자가 안 읽힌다). 겹친 개수 딱지는 상자의 오른쪽 바깥에 뜬다. 색과 굵기는 읽을 수 있을 만큼만 맞춘 것이고 정한 것이 아니다.

가리킬 때의 비용을 잰 값은 [기록](#기록)에 있다.

하나로 굳힐 때 지울 곳은 `src/widgets/doc-viewer/model/highlightMode.ts` 의 머리말에 있다(그 파일의 목록과 가지, `viewer.css` 의 「보기 방식」 구획, `DocumentViewer` 의 입력과 안내 글, `App.tsx` 의 조작).

## 글자 자리

칸 하나·숫자 하나·문장 하나의 상자(`innerBoxes`)는 **문서를 분해할 때 나온 글자 좌표**에서 온다. 분해 도구가 `document.json` 곁에 `char-places.json` 을 내고(`parse --places`), 변환이 그것을 읽는다. 뷰어는 PDF 의 글자를 읽지 않는다.

- 꼴: 그릇마다 하나. 그릇은 글 블록(`p3-b2`)이거나 표의 칸(`p3-t1:r2c4`)이다. 그릇의 글에서 글자마다 가로 범위가, 줄 토막마다 세로 범위가 있다. 자리의 단위는 JavaScript 문자열의 자리 그대로다(UTF-16).
- 변환이 하는 일: 자리 표기에서 그릇과 글자 범위를 정하고(`tools/lab/reconcile.ts` 의 `resolveTarget`), 그 범위의 글자 상자를 줄마다 묶는다(`tools/lab/places.ts` 의 `spanBoxes`). 표의 칸은 칸의 글 전체, `#n` 은 그 숫자의 글자 범위(뒤에 붙은 `%` 까지), 문장은 문장의 글자 범위다.
- 화면에서는 좁은 상자를 그리고, 골라진 강조가 든 표·문단 전체(`box`)를 점선으로 같이 그린다. 왼쪽의 「좁힌 자리로 보기」를 끄면 표·문단 상자만 남는다.

글자 자리와 잉크를 잰 값(2026-10-05)은 [기록](#기록)에 있다.

다시 재는 법(측정 스크립트는 따로 띄운 개발 서버에 붙는다. `tools/browser.ts` 의 `baseUrl`):

```sh
pnpm --filter @esg/web measure:places                                   # 꼴별로 상자를 얻은 수, 못 얻은 까닭 (convert 가 남긴 places-report.json 을 읽는다)
WEB_PORT=<띄운 포트> pnpm --filter @esg/web measure:ink --data local/reconcile.json --scale 1.5    # 화면의 잉크와 상자의 틈 (서버가 떠 있어야 한다)
WEB_PORT=<띄운 포트> pnpm --filter @esg/web capture --data local/reconcile.json --items v1,v2 --scale 1.5 --out <저장소 밖 폴더>   # 눈으로 볼 그림
```

★ 화면을 여는 측정 스크립트(`measure:ink`·`measure:open`·`measure:hover`·`capture`)는 `baseUrl` 뒤에 `?data=…` 를 붙여 연다. `baseUrl` 의 기본은 `http://localhost:<WEB_PORT>/` 이고, 경로 `/` 는 `/greenwash` 로 넘어간다(`src/app/router.tsx`). 그래서 이 스크립트 넷은 지금 그대로는 뷰어(`/dev/viewer`)를 열지 못한다. 화면 경로가 `/dev/viewer` 로 바뀐 뒤 다시 돌려 보지 않았다.

**사본이 둘 있다.** 다른 저장소의 코드를 import 할 수 없어 옮겨 적은 것이다. 원본의 경로와 커밋은 각 파일의 머리말에 있다.

- `tools/lab/refs.ts` 의 숫자 정규식: `#n`(n번째 숫자)이 글의 어느 글자 범위인지를 대조 쪽과 똑같이 세려고.
- `tools/lab/places.ts` 의 `spanBoxes`: 글자 범위 → 줄마다 상자.

원본이 바뀌면 여기도 바꿔야 한다. 이 저장소의 테스트는 원본을 볼 수 없으므로(`verify.sh` 는 실제 자료 없이 돈다), 어긋났는지는 실제 자료로 본다: 대조 쪽이 값 후보마다 낸 글자 범위와 상자(`fact-places.json`)를 주면 `measure:places` 가 값 후보 전부에서 견주고, 하나라도 다르면 종료 코드 1 이다.

```sh
# 대조 쪽 저장소의 ts/ 에서, 문서마다: fact-places.json 을 <폴더>/<문서 이름>/ 에 쓴다
pnpm -s -F reconcile exec tsx src/compare/places-cli.ts fact-places --doc <document.json> --places <char-places.json> --out <폴더>/<문서 이름>
# 이 저장소에서 (convert 때와 같은 환경 변수에 더해)
VIEWER_FACTS=<폴더> pnpm --filter @esg/web measure:places
```

닿지 않는 것(전부 좌표를 내는 쪽의 한계이고, 여기서 고치지 않는다):

- **글자 층이 없는 쪽**(그림만 있는 쪽)과 **그림으로 박힌 표**: 분해된 자료에 그 글자가 없다. 강조할 자리 자체가 자료에 없으므로 목록에도 나오지 않는다.
- 격자를 세우지 못한 표: 칸이 없어 칸의 상자도 없다.
- 줄 끝에서 끊긴 숫자: 분해가 줄을 이을 때 빈칸을 끼워 두 숫자로 읽힌다. 각각 상자는 나오지만 한 숫자로 묶이지 않는다.
- 같은 글자가 PDF 의 같은 자리에 두 번 그려진 곳: 값 후보가 둘 생기고 상자가 겹친다.
- 쪽이 돌아가 있거나 보이는 영역(CropBox)이 어긋난 실제 PDF 에서 글자 자리의 좌표와 pdf.js 의 그림이 맞는지는 재지 못했다(쪽 회전은 코드로 만든 예시 PDF 로만 봤고, 그 쪽에는 좁은 상자가 없다).
- 칸의 상자는 칸의 경계가 아니라 **칸 안의 글자 범위**다.

문장의 경계(가짜 자료에서만 쓴다): 마침표·물음표·느낌표 뒤에 공백이 오거나 글이 끝나는 자리. 소수점에서는 가르지 않는다. 줄바꿈으로는 가르지 않는다(분해된 글에 줄바꿈이 없다). 「No. 3」 같은 줄임말에서 잘리고, 마침표 없는 글머리표 문장들은 한 문장이 된다. 검출이 아니라 예시를 고르는 규칙이다.

## 안 한 것

- **서버 연결.** 부품은 자료 가져오기, 검토 상태 저장, 오류 처리, 인증을 하지 않는다. 붙일 자리는 위 「부품을 다른 화면에서 쓰는 법」에 적었다.
- **메뉴, 디자인 체계.** 데모 화면은 하나고 자료는 주소의 `?data=` 로 고른다. 색과 글꼴은 정한 것이 아니다.
- **항목이 수천 개일 때.** 목록을 전부 그린다. 276개까지 써 봤다. 걸러 보기와 정렬도 없다.
- **쪽 번호 표시의 기준.** 화면 위에서 3분의 1 지점의 줄에 걸린 쪽을 「지금 쪽」으로 친다(강조로 갈 때 상자를 놓는 줄과 같다. `geometry.ts` 의 `FOCUS_LINE`). 그래서 골라진 상자가 쪽의 맨 아래에 있어도 그 쪽의 번호가 보인다. 문서의 맨 끝이나 맨 처음이라 그 줄에 상자를 놓지 못할 때는 한 쪽 어긋날 수 있다.
- **글자 선택과 찾기.** PDF 의 글자 층을 화면에 얹지 않았다(쪽은 그림으로만 보인다).
- **쪽 그림 미리 만들어 두기, 섬네일.** 확대·축소할 때마다 보이는 쪽을 다시 그린다.
- **접근성 점검.** 상자와 항목은 단추라 Tab 으로 갈 수 있지만, 화면 읽기 프로그램으로 써 보지 않았다.
- **Chromium 밖의 브라우저.** Safari, Firefox 에서 돌려 보지 않았다.
- **의심 문장 검출.** 문장 강조 자료는 가짜다.

## 기록

개발하며 남긴 글과 잰 값이다. **그때 경로는 옛 이름이다**(웹이 층 다섯으로 바뀌기 전). 아래 표로 지금 자리를 찾는다.

| 그때 | 지금 |
|---|---|
| `src/doc-viewer/` | `src/widgets/doc-viewer/` |
| `domain/` | `model/` |
| `headless/` | `hooks/` |
| `src/doc-viewer/layers.test.ts` | `src/app/guards/layers.test.ts` |
| `src/doc-viewer-demo/` | `src/pages/demo-viewer/` |
| `src/App.tsx` | `src/pages/demo-viewer/App.tsx` |
| `main.tsx`, `app.css` | `src/main.tsx`, `src/app/styles/app.css` |
| `styles/` | `src/app/styles/` |
| `edk-kit/` | `src/app/guards/kit-imports.test.ts`, `src/app/guards/kit-typecheck.tsx` |
| `src/address.ts` | `src/shared/lib/address.ts` |
| `src/sample.test.ts`(`sample.test.ts`) | `tools/sample.test.ts` |
| `review-table/`, `review-table-demo/`, `test-support/` | `src/widgets/review-table/`, `src/pages/demo-table/`, `src/shared/lib/testing/` |
| `http://localhost:15173/`(`?data=`·`?screen=`·`?mode=`) | `http://localhost:15173/dev/viewer`(같은 인자) |
| `packages/core` | 없다(TS 서버 뼈대와 같이 걷혔다) |

그때의 글:

- 처음 권했던 꼴과 다른 점 하나: 「강조에 글자를 주면 뷰어가 칸을 찾는다」가 아니라, 자료를 만드는 쪽이 좁힌 자리를 넣는다. 쪽을 넘는 강조에 대해서는 실제 자료에서 문단 하나·칸 하나가 한 쪽 안이라 그런 일이 없었다.
- 글자 자리가 없을 때 PDF 의 글자를 뒤져 자리를 짐작하지 않는다 — 전에는 그렇게 했고, 문단 속 숫자 셋 중 하나가 밀렸다(아래 「잰 값」).
- `openPdf` 에 그릴 때마다 새 함수를 넘기면, 전에는 PDF 를 끝없이 다시 열었다.
- 검토 표와 다른 곳: 그때 검토 표의 헤드리스 층은 훅뿐이라 「마크업 파일(.tsx)이 없다」가 규칙이었다. 뷰어는 모양 없는 컴포넌트를 두고 규칙을 「모양을 모른다」로 바꿨다.
- 화면을 다른 UI 라이브러리로 바꿀 때 새로 쓰는 `ui/` 의 넷: `DocumentViewer.tsx`(70줄), `ItemList.tsx`(97줄), `PdfPane.tsx`(108줄), `viewer.css`(285줄). 정리 전에는 같은 일을 하려면 부품 다섯(649줄)과 CSS(299줄)를 상태와 스크롤 다루기까지 다시 써야 했다. 갈아 끼워 본 둘째 화면은 `src/doc-viewer-demo/CompactViewer.tsx`(179줄) + `compact.css`(42줄), `HighlightOverlay.tsx` 는 96줄이었다. 지금 줄 수는 서식 도구(Prettier)를 들인 뒤라 다르다.
- 브라우저 테스트가 지금 코드를 빌드하게 하기 전에는 `test:browser` 만 돌리면 앞서 만든 `dist` 를 그대로 띄웠다. 값은 실행마다 빌드 한 번(이 기계에서 0.5~0.6초)이었다. 처음 내려받는 Chromium 은 약 100MB 였다.
- 그때 `verify.sh` 의 단계 글: 설치 → 타입 검사 → 린트(ESLint, 오류만 막는다) → 포맷 검사(Prettier) → 단위·부품 테스트 → 빌드 → 브라우저 받기 → 브라우저 테스트 → apps/web 아래에 PDF·실제 자료가 없는지. 지금은 빌드 뒤에 데모 빠짐(`scripts/check-no-demos.sh`)이 더 있다.
- 그때 「라우팅」은 안 한 것이었다(화면은 하나, `?data=`). 「컨테이너와 compose」도 안 한 것이었다: web 은 compose 에 들어 있지 않고 `pnpm --filter @esg/web build` 의 결과(`apps/web/dist/`)는 정적 파일이다 — 지금은 api-py 가 빌드 결과를 낼 수 있다(`WEB_DIST_DIR`, `apps/api-py/esgapi/config/settings/base.py`).

**고른 것과 바꾸는 법**(그때의 표. 까닭과 버린 것):

| 자리 | 지금 | 고른 까닭 | 버린 것 | 바꾸려면 |
|---|---|---|---|---|
| 빌드 | Vite 8 + React 18.3.1 + TypeScript 5.6.3 | 정적 파일로 빌드된다. 설정이 한 파일이다 | | `vite.config.ts`, `index.html` |
| PDF 그리기 | pdf.js 직접 (`pdfjs-dist` 6.4.299) | 쪽의 크기와 회전을 어차피 pdf.js 의 것으로 다룬다. 보이는 쪽만 그리기는 어느 쪽이든 직접 짜야 한다. 의존성이 하나 적다 | react-pdf 11: pdf.js 를 감싼 것이라 그리는 속도와 메모리는 같았고(아래), 앱 JS 가 gzip 약 60KB 크고, pdf.js 판을 6.3.289 로 못박아 워커와 판이 어긋날 길이 하나 더 생긴다 | `src/doc-viewer/pdfjs.ts` 와 `src/doc-viewer/headless/PageCanvas.tsx` 둘. 뷰어의 나머지는 `PdfHandle`(`headless/pdfBackend.ts`)만 안다. react-pdf 로 가면 `PageCanvas` 를 `<Page>` 로 갈고 `usePdf` 를 `<Document>` 로 감싼다 |
| 보이는 쪽만 그리기 | 스크롤 위치로 셈한다(`visiblePageRange`) | 순수 함수라 테스트하기 쉽고, 쪽 크기를 입력이 미리 주므로 스크롤 길이가 처음부터 맞다 | IntersectionObserver: 쪽마다 관찰자를 달아야 하고 jsdom 에 없다. 가상 스크롤 라이브러리: 쪽 높이가 미리 정해져 있어 필요 없다 | `domain/geometry.ts` 의 `visiblePageRange` 와 `headless/usePaneView.ts` |
| 입력 검증 | zod 4.6.5 | `packages/core` 가 이미 같은 판을 쓴다 | 손으로 쓴 검사 | `domain/contract.ts` |
| 상태 | React 의 `useState` 만. 전부 헤드리스 층의 훅 안에 있다 | 들고 있을 것이 「골라진 항목」과 「검토 상태」, 문서 칸의 배율과 스크롤 위치뿐이다 | 상태 관리 라이브러리, 데이터 패칭 라이브러리 | `headless/useDocViewer.ts`, `usePaneView.ts`, `useReviews.ts` |
| 층 나눔 | `domain` / `headless`(훅 + 모양 없는 컴포넌트) / `ui`, 한 방향 import | 화면을 바꿔도 상태·규칙·스크롤·강조 얹기가 남는다. 검토 표와 같은 꼴이다 | 훅만 빼기: 쪽 쌓기와 강조 얹기를 화면마다 다시 쓴다. 헤드리스 UI 라이브러리 들이기: 뷰어에 맞는 것이 없고 의존성이 는다 | [위의 「세 층」](#세-층) |
| 헤드리스 컴포넌트의 자리 잡기 | 인라인 `style` | 「헤드리스는 CSS 를 가져오지 않는다」를 글자로 지킬 수 있고, CSS 를 빼도 제자리에 놓인다 | 구조용 CSS 파일을 따로 두기: 쓰는 쪽이 그 파일을 꼭 같이 실어야 한다 | `headless/PageStack.tsx`, `HighlightOverlay.tsx` |
| 헤드리스 컴포넌트에 모양을 여는 길 | 클래스 이름 + 조각마다의 `pieceProps` + 딱지를 그리는 함수 | 지금의 CSS 가 `data-*`·`:hover`·`:has` 로 요소들의 관계에서 모양을 낸다. 클래스 이름만 받으면 그대로 쓸 수 있다 | 조각을 통째로 그리는 함수: 자리·표시·누르기를 쓰는 쪽이 다시 붙인다. CSS 변수: 색은 되지만 선의 꼴이나 딱지의 구조는 못 바꾼다 | `headless/HighlightOverlay.tsx` 머리말 |
| 좁은 상자의 출처 | 문서를 분해하는 쪽이 낸 글자 자리(`char-places.json`)를 변환이 읽는다 | 글자마다의 좌표라 어림이 없다. 문단 속 숫자도 그 숫자만 덮는다 | PDF 의 글자 층에서 값을 찾아 짐작하기(전에 하던 것. 문단 속 숫자 36개 중 12개가 밀렸다. 지웠다) | `tools/lab/places.ts`, `tools/lab/reconcile.ts` 의 `placeOf` |
| 글자 자리가 없을 때 | 좁은 상자 없이 표·문단 전체만. 알림에 적는다 | 틀린 자리를 가리키느니 넓게 가리킨다. 짐작 코드를 남기면 두 길을 다 지켜야 한다 | 예전 짐작으로 돌아가기 | `tools/lab/load.ts` 의 `loadSide`(없으면 `places` 가 비어 온다) |
| 글자 범위 → 상자의 셈 | 분해 저장소의 셈을 옮겨 적은 사본(`spanBoxes`) | 저장소가 달라 import 할 수 없다. 문장 강조처럼 「값 후보가 아닌 아무 글자 범위」에도 이 셈이 필요하다 | 변환 때 그쪽 스크립트를 불러 숫자의 상자만 받기: 변환이 그쪽 도구에 묶이고, 문장에는 못 쓴다 | `tools/lab/places.ts` 머리말에 원본의 경로와 커밋. 어긋났는지는 `measure:places` 가 본다([아래](#글자-자리)) |
| 강조 하나에 상자 여럿 | 계약에 `innerBoxes`(배열). 화면에서는 틀 하나(`.dv-group`) 안에 줄마다 단추 하나 | 고르기·가리키기·겹친 개수가 「강조」 단위로 남는다 | 줄마다 강조를 따로 만들기: 겹친 개수와 누를 때 도는 항목이 줄 수만큼 불어난다. 조각을 감싼 큰 상자 하나: 앞뒤 문장을 덮는다 | `domain/contract.ts`, `domain/highlightGroups.ts` 의 `shapeOf`, `headless/HighlightOverlay.tsx` |
| 여러 상자인 강조로 갈 때의 스크롤 | 조각들을 전부 감싼 상자의 윗변을 「보는 줄」에, 가로는 그 가운데를 화면 가운데에 | 첫 줄이 보이고, 문장 전체의 가운데가 화면 가운데에 온다. 감싼 상자가 문서 칸보다 넓으면(좁은 창에서 배율 3) 양 끝의 조각은 화면 밖에 남는다 | 첫 조각만으로 재기: 줄 끝에서 시작하는 문장은 오른쪽 끝만 보인다 | `headless/useDocViewer.ts` 의 `revealFor`(어느 상자로), `headless/PageStack.tsx` 의 「강조로 가기」(가는 것), `domain/highlightGroups.ts` 의 `unionBox` |
| 강조의 보기 방식 | 부품의 입력값 하나(`highlightMode`), 기본은 옅게 | 셋을 띄워 놓고 견주려고. 굳히면 지우기 쉽게 한 곳에 모았다 | 입력 자료(JSON)에 넣기: 자료가 화면의 선택을 품게 된다. 부품 안의 상태로 두기: 쓰는 쪽이 정하지 못한다 | `domain/highlightMode.ts` 머리말에 지울 곳을 적었다 |
| 종류 켜고 끄기 | 범례가 곧 단추. 꺼진 종류의 항목은 목록에서 흐리게 | 뷰어는 종류의 뜻을 모른다. 입력이 준 종류를 켜고 끌 뿐이다 | 항목을 목록에서 숨기기: <kbd>j</kbd>·<kbd>k</kbd> 가 안 보이는 항목을 밟고 항목 수가 달라진다. 그대로 두기: 상자가 왜 안 보이는지 알 수 없다 | `headless/useDocViewer.ts` 의 `hiddenKinds`·`kindHidden`, `ui/ItemList.tsx` 의 `data-kind-hidden` |
| 항목을 가리키면 진해지기 | 마우스를 올리거나 초점이 간 항목을 뷰어의 상태로 든다 | 눌러야만 보이면 훑어보기가 느리다 | CSS 만으로: 목록과 문서가 다른 나무라 `:hover` 가 닿지 않는다 | `headless/useDocViewer.ts` 의 `pointed`, `ui/viewer.css` 의 `data-pointed` |
| 스타일 | 화면 층의 CSS 한 파일. 모양만 있다(자리는 헤드리스 컴포넌트가 갖는다) | 모양은 읽을 수 있을 만큼만 | CSS 틀, UI 라이브러리(apps/web 에는 Tailwind v3 과 EDK 키트가 들어 있지만 이 부품은 쓰지 않는다) | `src/doc-viewer/ui/viewer.css`. 클래스는 전부 `dv-` 로 시작한다 |
| 단위·부품 테스트 | vitest + jsdom + Testing Library | 뼈대가 vitest 를 쓴다. 부품 테스트만 jsdom | | `vitest.config.ts` |
| 브라우저 테스트 | Playwright (머리 없는 Chromium) | 캔버스의 픽셀을 읽어야 해서 진짜 브라우저가 필요하다. 상태를 물어 기다리는 API 가 있고, 미리보기 서버를 스스로 띄우고 내린다 | vitest 의 브라우저 모드: 결국 Playwright 를 깔아야 하고 설정이 한 겹 더 는다 | `playwright.config.ts`, `e2e/` |
| 예시 PDF | PDF 를 글자 그대로 써내는 코드 80줄 | 저장소에 PDF 를 넣지 않는다. 테스트가 「어디에 무엇이 그려져 있는지」를 정확히 안다 | pdf-lib: 의존성 하나. 영문·숫자와 사각형만 그리면 되어 필요 없다 | `tools/pdf-writer.ts` |
| 스크립트 실행 | node 가 `.ts` 를 바로 읽는다(Node 22.18 부터 되는 기능) | 빌드도 도구도 없다 | tsx | 그래서 이 패키지의 상대 경로 import 에는 전부 `.ts`·`.tsx` 를 적는다(`tsconfig.json`) |

**잰 값: pdf.js 직접과 react-pdf.** pdf.js 직접 사용과 react-pdf 를 같은 최소 앱 둘로 견준 값(112쪽·595×842pt 문서, 보이는 쪽만 그리기, Apple M3 Pro, 머리 없는 Chromium 153, 화면 1280×900·픽셀 밀도 1, 5회 중앙값. 저장소 밖에서 한 번 잰 것이다):

| | pdf.js 직접 | react-pdf |
|---|---|---|
| 첫 쪽이 그려지기까지 | 241~270ms (두 번 재서 범위가 겹친다) | 227~334ms |
| JS 힙, 끝 쪽까지 스크롤한 뒤 | 7.7MB | 8.6MB |
| 앱 JS (gzip) | 196KB | 257KB |
| 워커 (gzip) | 374KB | 374KB |

이 뷰어 자체로 같은 문서 둘(112쪽, 79쪽)을 나란히 열었을 때(화면 1900×1000·픽셀 밀도 1, `vite preview`, 5회): 첫 쪽 299ms(267~517), JS 힙 7.6MB → 끝 쪽까지 간 뒤 13.0MB(10.3~15.2), 만들어져 있는 캔버스 6개(문서마다 보이는 쪽과 앞뒤 한 쪽). `pnpm --filter @esg/web measure:open --data local/reconcile.json` 으로 다시 잰다. **캔버스의 픽셀 메모리(JS 힙 밖)와 픽셀 밀도 2 인 화면은 재지 않았다.** 빌드 결과는 앱 JS 759KB(gzip 230KB. 검토 표를 더한 뒤에는 872KB, gzip 262KB, 보기 방식과 계산 실패를 더한 뒤에는 877KB, gzip 264KB, React 18 로 내리고 린트·포맷을 들인 뒤에는 806.70 kB, gzip 244.15 kB. 빌드가 찍는 값), 워커 1.26MB, 그리고 `pdfjs/` 부속 파일 3.9MB(필요한 것만 그때그때 내려받는다).

**잰 값: 가리킬 때의 비용.** 가리킬 때의 비용(실제 문서 둘의 대조 자료, 항목 276개, 두 문서 칸을 상자가 가장 많은 쪽에 두어 DOM 에 상자 281개, Apple M3 Pro, 머리 없는 Chromium, 화면 1900×1000·픽셀 밀도 1, **빌드한 것을 `vite preview` 로**, 항목에서 항목으로 마우스를 200번 옮긴 평균의 5회 중앙값. `pnpm --filter @esg/web measure:hover --data local/reconcile.json` 으로 다시 잰다): 옮기기 한 번에 브라우저가 쓴 시간(스크립트 + 스타일 + 배치)이 옅게 1.84ms(1.79~1.88), 전체 채움 1.86ms, 고른 것만 1.45ms. 한 프레임(약 16.7ms) 안이다. 그 한 번에 React 는 목록 276항목과 그려진 쪽의 상자 전부를 다시 계산하지만, DOM 에서 실제로 바뀌는 상자는 둘이다(뗀 것 하나, 올린 것 하나). 재지 않은 것: 화면에 색을 칠하는 시간(페인트), CPU 제한을 건 느린 기계, 픽셀 밀도 2, 항목이 수천 개일 때(목록 전체를 다시 계산하므로 항목 수에 비례해 는다).

**잰 값: 글자 자리**(실제 문서 둘의 대조 한 실행, 강조 432개: 표의 칸 394, 칸 안의 n번째 숫자 2, 문단 속 n번째 숫자 36. 2026-10-05):

| | 강조 | 상자를 얻음 | 상자 안의 PDF 글자가 값과 같음 | 다름 | 못 얻음 |
|---|---|---|---|---|---|
| 전에: PDF 의 글자 층에서 짐작 — 표의 칸(칸 안의 숫자 포함) | 396 | 391 | 391 | 0 | 5 |
| 전에: 짐작 — 문단 속 숫자 | 36 | 36 | 24 | **12** | 0 |
| 지금: 글자 자리 — 표의 칸(칸 안의 숫자 포함) | 396 | 396 | 396 | 0 | 0 |
| 지금: 글자 자리 — 문단 속 숫자 | 36 | 36 | 36 | 0 | 0 |

- 세는 법: 뷰어 입력(`reconcile.json`)의 상자마다, PDF 의 글자를 다른 도구(PyMuPDF)로 따로 읽어 가운데점이 상자 안에 든 글자를 왼쪽부터 잇고, 그것이 강조의 값(뒤의 `%` 는 있어도 없어도 같다고 본다)과 같은지 본다. 두 줄 다 같은 법으로 셌다. 「전에」는 짐작 코드를 지우기 직전의 트리로 다시 낸 것이다. 이 셈은 저장소 밖의 스크립트로 했다(이 저장소에는 Python 이 없다).
- **한계: 글자 자리의 좌표도, 이 확인도 같은 도구가 읽은 글자 상자에서 나온다.** 그래서 따로 화면에서 쟀다. 432개 전부를 골라 가며 상자 안의 잉크(바탕색과 다른 픽셀)를 캔버스에서 읽으면(`measure:ink`, 배율 1.5): 잉크가 없는 상자 0, 상자의 왼쪽 변에서 글자까지 0.7pt(중앙값. 최소 -0.1, 최대 1.4), 오른쪽 0.0pt(-0.3 ~ 0.6), 위 2.0pt(1.3 ~ 2.9), 아래 0.8pt(-0.3 ~ 2.4). 음수는 잉크가 변을 그만큼 넘었다는 뜻이다(재는 격자가 0.67pt 다). 숫자 바로 뒤에 글자가 붙은 자리(「19.7조」 꼴)에서는 상자의 오른쪽 변이 다음 글자에 닿을 듯 붙는다. 곧 **가로는 글자에 붙고, 세로는 글자보다 위로 2pt·아래로 1pt 쯤 넉넉하다**(글자 자리의 세로가 글자의 잉크가 아니라 글꼴의 줄 높이라서다). 잉크가 「그 글자」인지는 이 수치가 말하지 못한다. 그것은 눈으로 본다(`capture`).
- 문장 강조(가짜) 25문장: 한 줄 15, 두 줄 6, 세 줄 4(상자 39개). 같은 법으로 잉크가 없는 상자 0.
- 「이 저장소에는 Python 이 없다」는 그때의 글이다. 지금은 `apps/api-py` 가 있다.

2026-10-05 에 두 문서로 돌린 결과: 값 후보 2,938개와 1,292개 전부에서 글자 범위와 상자가 같았다(다른 것 0). 줄 끝에서 끊긴 숫자는 이번 자료에서는 못 봤다. 쪽이 돌아가 있거나 CropBox 가 어긋난 실제 PDF 는 그런 문서가 없었다.
