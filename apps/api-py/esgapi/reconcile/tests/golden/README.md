# 골든: 같은 입력에서 TS = 파이썬

`reconcile/calc` 가 esg-lab `ts/reconcile` 과 **같은 값 후보를 같은 ID·같은 글자 자리·같은 상자로** 내는지 잰다.
건수가 아니라 구획 전체의 값 일치다.

| 파일 | 무엇 |
|---|---|
| `dump.mts` | TS 쪽 덤프. esg-lab 의 `src/index.ts`·`domain/kinds.ts`·`compare/render.ts` 를 불러 문서 하나의 구획을 JSON 으로 낸다. esg-lab 의 자리는 환경 변수 `ESG_LAB` |
| `make-golden.sh [--input <폴더>] [--out <폴더>]` | 네 보고서 + 지은 문서의 TS 덤프를 `apps/api-py/.lab-golden/ts/`(git 밖)에 만든다 |
| `dump.py` · `dump_places.py` | 파이썬 쪽 덤프(같은 꼴의 JSON 값). 숫자 뽑기 일곱 구획 · 상자 한 구획 |
| `check_lab.py [--input <폴더>] [--ts <폴더>] [--digest <파일>] [--write-digest]` | 둘을 값으로 견주고 건수·해시를 digest 와 대조한다. 입력이 없거나 sha256 이 다르면 건너뛰지 않고 실패한다 |
| `lab-digest.json` · `lab-digest.places.json` | 문서마다 입력의 sha256, 구획마다 건수와 해시(숫자 뽑기 / 상자). 입력은 esg-lab 의 밴드 C1 산출(**pymupdf 엔진**), 값 후보 합 8,773 |
| `lab-digest.pdfium.json` · `lab-digest.pdfium.places.json` | 같은 꼴. 입력은 esg-app 의 파서(`services/parser`, **pdfium 엔진**)가 같은 네 PDF 에서 낸 산출, 값 후보 합 8,755 |
| `synthetic/` | 지은 문서: `build.py`(만드는 스크립트) → `document.json` · `char-places.json` · `cases.json`, 그리고 그 TS 덤프 전문 `ts-dump.json` |

## 구획

`facts`(값 후보 전부) · `nonValues`(값 아님: 자리·원문·갈래) · `grids`(격자의 머리글·상태·본문 중간 머리글·제목 후보(기본과 `own`)·단위 줄) ·
`failed`(격자를 못 세운 표와 글자 없는 쪽) · `kinds`(ID → 종류) · `count`(갈래별 수) · `masks`(블록마다 `maskText`, 비지 않은 칸마다 `cellText`) ·
`places`(값 후보마다 `locatePlace`, 값 아님마다 `placeOfWhere`). 지은 문서에는 `dec`(십진 도우미)와 `notation`(표기 규칙의 낱개 본보기 400)이 더 있다.

## 값으로 견주고, 해시는 한쪽에서 낸다

JS 의 `JSON.stringify(1.0)` 은 `1`, 파이썬은 `1.0` 이다. 그래서 글자가 아니라 **값**으로 견준다(`dump.first_difference`).
해시는 양쪽을 같은 정규화로 낸다: TS 덤프도 파이썬이 읽어 들인 뒤 `dump.canonical`(키 가나다순, 정수인 실수는 정수로)로 다시 적어 sha256 을 낸다.

## 만든 기록

- 2026-10-08, esg-lab HEAD `f1b2c77`(작업 트리 깨끗함), node v22.23.1(유니코드 17.0), Python 3.13.5(유니코드 15.1.0).
- 명령: `make-golden.sh` → `uv run python -m esgapi.reconcile.tests.golden.check_lab --write-digest` → `… check_lab`.
- 지은 문서를 고쳤으면: `uv run python -m esgapi.reconcile.tests.golden.synthetic.build` → `make-golden.sh` →
  `.lab-golden/ts/synthetic.json` 을 `synthetic/ts-dump.json` 으로 옮기고 → `check_lab --write-digest`.

### pdfium 산출의 digest (밴드 PY8c)

- 2026-10-08, esg-app 의 파서 `services/parser`(docparse 0.1.0, pypdfium2 5.14.0 · pdfium 156.0.8076.0, Python 3.13.5),
  esg-lab HEAD `f1b2c77`(작업 트리 깨끗함), node v22.23.1(유니코드 17.0).
- 명령(저장소 맨 위에서. `OUT` 은 절대 경로 `$PWD/apps/api-py/.lab-golden/pdfium`, `REPORTS` 는 원문 PDF 의 폴더 `prework/reports`):
  1. 문서 넷마다 `uv run --directory services/parser --frozen python -m docparse parse "$REPORTS/<문서>.pdf" --places --out "$OUT/<문서>"`
  2. `apps/api-py/esgapi/reconcile/tests/golden/make-golden.sh --input apps/api-py/.lab-golden/pdfium --out apps/api-py/.lab-golden/ts-pdfium`
  3. `(cd apps/api-py && uv run --frozen python -m esgapi.reconcile.tests.golden.check_lab --input .lab-golden/pdfium --ts .lab-golden/ts-pdfium --digest esgapi/reconcile/tests/golden/lab-digest.pdfium.json --write-digest)`
  4. 같은 명령에서 `--write-digest` 만 빼고 견주기. 한꺼번에 되재는 것은 `apps/api-py/scripts/section4-PY8c.sh --pure`.
- 결과: 문서 넷 × 구획 여덟 = 32/32 가 TS 와 값 전체 일치. 값 후보 2,938 · 1,292 · 2,049 · 2,476 = 8,755, 상자 8,755/8,755.
- 원문 PDF 의 sha256(분해 산출의 `source.sha256` 에도 실린다): `kb_2025_kor` `34836150…bf67132` · `kb_2025_databook_kor` `c75dbe00…b4eaac` ·
  `samsung_2026_kor` `ec7e5f81…344954` · `cosmax_2025_kor` `9e86eb92…24aa0c`.

## 입력과 무효 조건

네 보고서의 입력은 **git 밖**이다: `esg-lab/out/band-C1/places/<문서>/document.json` · `char-places.json`
(문서 넷: `kb_2025_kor` · `kb_2025_databook_kor` · `samsung_2026_kor` · `cosmax_2025_kor`. 2026-10-05 밴드 C1 의 산출, **pymupdf 엔진**).
없어졌으면 다시 만든다: esg-lab `py/docparse` 의 `parse --places` 를 원문 PDF(`prework/reports/`)에. 산출이 달라지면 sha256 이 달라 `check_lab` 이 실패한다.

- 네 문서의 일치는 `check_lab` 을 돌린 그날 그 산출에 대해서만 잰 것이다(두 엔진의 산출 모두). main 의 게이트(`verify.sh`)는 지은 문서만 되잰다.
- esg-app 의 파서(pdfium)가 낸 문서 모델로도 쟀다(2026-10-08, 위 「pdfium 산출의 digest」. 값 후보 수가 다르다: 삼성전자 2,049, 합 8,755).
  그 입력도 **git 밖**이다(`apps/api-py/.lab-golden/pdfium/`, 원문 PDF 는 `prework/reports/`). 없으면 위 명령 1 로 다시 만든다.
  파서나 pypdfium2 의 판이 바뀌어 산출이 달라지면 sha256 이 달라 `check_lab` 이 실패한다(그때는 다시 재고 digest 를 새로 쓴다).
- 「같다」는 그 네 문서에서의 말이다. 다른 PDF 에서 TS 와 같은지는 재지 않았다.
- 네 문서에는 언어 차이를 드러낼 글자가 0 이다. 그쪽의 「같다」는 지은 문서 하나에 기댄다.
- 문서와 숫자는(지은 문서의 것은) 전부 지어낸 것이다. 네 보고서의 산출과 덤프는 저장소에 넣지 않는다(건수와 해시만).
