# services/parser — 문서 파서

PDF 를 받아 섹션·문단·표의 JSON(`document.json`)과 글자 자리(`char-places.json`)로 분해해 돌려주는 서비스다.
DB 에 닿지 않고 상태가 없다. LLM 과 OCR 을 쓰지 않는다. 호스트에 포트를 열지 않는다(컨테이너 안에서 8000).

PDF 를 읽는 것은 **pypdfium2 하나**다. 분해기(`docparse/`)는 **esg-app 이 정본**이다(밴드 PX, `MARC-TICK-121`, 2026-10-16).
처음에는 esg-lab `py/docparse` 의 커밋 `2e2c2c4`(가지 `band/PD1`)에서 pdfium 엔진만 남겨 가져온 사본이었다(밴드 PD2, `MARC-TICK-55`, 2026-10-08).
esg-lab `2e2c2c4` 와 분해 산출이 같음은 검증 트랙의 대조(PB1)가 지킨다(아래 「어디서 가져왔나」).

```
app.py            HTTP 머리. POST /parse(본문이 PDF 바이트), GET /healthz
docparse/         분해기 (아래 「어디서 가져왔나」)
  engine/           PDF 엔진 이음매. pdfium_engine.py 하나
schemas/          산출의 스키마 둘 (esg-lab 에서 옮겨 온 것. schemas/README.md)
tests/            분해기와 새 약속의 테스트. pdfbuild.py 가 테스트용 PDF 를 표준 라이브러리만으로 짓는다
test_app.py       /healthz 와 옛 약속이 걷혔다는 것(415)의 테스트
scripts/          post_pdf.py(컨테이너 안에서 PDF 를 보낸다), s4_tools.py·planted.py(scripts/section4-PD2.sh 가 부른다)
```

## 부르는 법 (HTTP)

### 본문이 PDF 바이트

```
POST /parse?file_name=<UTF-8 percent-encoding 한 이름>[&layout=2[&charts=1]]
Content-Type: application/pdf
<PDF 바이트>

200 {"document": <document.json>, "charPlaces": <char-places.json>}
```

- `file_name` 은 선택이다(기본 `upload.pdf`). 푼 글자가 `document.source.file_name` 과 `charPlaces.source.file_name` 에 그대로 든다. 1~255자(푼 뒤의 글자 수), 경로 구분자(`/`, `\`)·`..`·제어 글자는 안 된다. 쿼리의 `+` 는 공백으로 읽는다(더하기 글자는 `%2B`).
- `source.sha256` 은 받은 바이트의 해시다.
- 두 산출은 내보내기 전에 `schemas/` 의 스키마로 검사한다. `charPlaces` 는 **늘 있다**(`null` 이나 키 없음으로 오지 않는다).
- 표 전략은 `auto`, 겹쳐 그린 글 거르기는 끔으로 고정이다. HTTP 로 바꿀 수 없다.
- `layout` 은 선택이다(분해 판, 아래 「분해 판」). 없으면 1 이고 그 산출은 `layout=1` 과 바이트까지 같다. `1`·`2` 밖이거나 두 번 오면
  422 `bad_layout`. 그 밖의 모르는 쿼리는 무시한다.
- `charts=1` 은 선택이다(밴드 CHL1, 판 2 에만): 셋째 키 `chartLabels`(`schemas/chart-labels.schema.json`, 도표와 도표 속 숫자의 값·눈금·범주·계열 라벨)를 더 싣는다. 같은 자식이 같은 열린 PDF 로 낸다. 그 밖의 값·두 번·판 2 가 아님은 422 `bad_charts`. 없으면 봉투는 키 둘 그대로다.
- 글자 층이 없는 쪽은 거절이 아니라 200 이고 그 쪽의 `text_layer` 가 `"none"` 이다.
- CLI `python -m docparse parse <pdf> --out <폴더> --places` 가 쓰는 두 파일과 JSON 값으로 같다.

거절은 갈래로 나뉘고 본문은 늘 `{"detail": {"code", "message"}}` 다. **4xx 는 다시 해도 같다, 5xx 는 다시 해 볼 만하다.**
밴드 PX(결함 D4)에서 같은 입력이면 늘 같은 실패(`parse_failed`·`output_schema_invalid`)를 500 에서 422 로 옮겼다. 부르는 쪽(api-py)은 4xx 를
`rejected`(다시 하지 않음), 5xx·끊김·시간 초과를 `unavailable`(다시 함)로 가른다.

| 상태 | code | 언제 |
|---:|---|---|
| 413 | `too_large` | 본문이 `MAX_SOURCE_BYTES`(기본 50 MiB)를 넘는다. 다 받기 전에, 넘는 순간 끊는다 |
| 413 | `too_many_pages` | 쪽 수가 `MAX_PAGES` 를 넘는다. 암호를 확인하며 여는 자리에서 세고 분해하지 않는다 |
| 415 | `unsupported_media_type` | Content-Type 이 `application/pdf` 가 아니다(옛 약속의 `application/json` 도 여기다) |
| 422 | `empty_body` | 본문이 0 바이트다 |
| 422 | `bad_file_name` | 위의 이름 규칙에 어긋나거나 UTF-8 로 풀 수 없다 |
| 422 | `bad_layout` | `layout` 이 `1`·`2` 가 아니거나 두 번 왔다(밴드 TRD1) |
| 422 | `bad_charts` | `charts` 가 `1` 이 아니거나 두 번 왔거나 판이 2 가 아니다(밴드 CHL1) |
| 422 | `not_a_pdf` | pdfium 이 열지 못한다 |
| 422 | `password_protected` | 암호가 걸려 있다 |
| 422 | `parse_timeout` | 분해가 `PARSE_TIMEOUT_SECONDS` 안에 끝나지 않았다. 그 자식 프로세스를 죽였다 |
| 422 | `output_schema_invalid` | 산출이 스키마에 맞지 않거나 글자 자리가 없다. 내보내지 않는다. 같은 입력이면 늘 같아 4xx 지만 코드 결함이라 기록(stderr)에 줄을 남긴다 |
| 422 | `parse_failed` | 분해 규칙 안에서 예외가 났다(같은 바이트면 늘 같다). 본문에 문서의 글과 트레이스백을 싣지 않는다 |
| 500 | `worker_died` | 분해하던 자식 프로세스가 답 없이 죽었거나 메모리가 모자랐다(잠깐의 문제일 수 있다) |
| 503 | `busy` | 분해를 기다리는 요청이 `MAX_QUEUE` 건이다. 줄을 서지 않고 바로 거절한다 |

### 상한 (결함 D4, 밴드 PX)

넷 다 환경 변수다. 0 이하나 숫자가 아닌 값이면 서비스가 뜨지 않는다(조용히 「상한 없음」이 되지 않게).

| 변수 | 기본값 | 넘으면 | 근거 |
|---|---:|---|---|
| `MAX_SOURCE_BYTES` | 52,428,800 (50 MiB) | 413 `too_large` | 밴드 PD2 |
| `MAX_PAGES` | 1,000 | 413 `too_many_pages` | 어림. 실제 공시 보고서가 들어가게 넉넉히(감독 처분: 최소 400쪽. 공개 보고서 A 는 173쪽) |
| `MAX_QUEUE` | 8 | 503 `busy` | 어림. 부르는 쪽 worker-py 의 동시성 2(compose)보다 넉넉히. 도는 한 건은 세지 않는다 |
| `PARSE_TIMEOUT_SECONDS` | 180 | 422 `parse_timeout` | 감독 처분(2026-10-16): 실제 보고서가 컨테이너에서 69초 걸린 기록(아래)이 있어 넉넉히. 차례 「파서 180 < api-py `PARSER_TIMEOUT_MS` 210초 < Celery soft 240 < hard 300」 — 파서가 먼저 끊는다 |

- 시간 상한은 자식 한 건이 도는 시간이다(줄에서 기다린 시간은 세지 않는다). 부르는 쪽의 제한 시간은 기다린 시간까지 센다.
- 잰 값: 합성 문서(쪽마다 글 41줄 + 괘선 표 하나)는 호스트에서 200쪽 4.3초, 400쪽 9.3초였다(2026-10-16, 1분 부하 약 6).
  실제 보고서는 더 무겁다: 173쪽 21 MB 짜리 공개 보고서 하나가 이 컨테이너에서 69초 걸렸다(2026-10-08, 다른 일이 같이 도는 기계에서 한 번 잰 값).

### 분해 안의 상한 (밴드 PX2)

괘선 묶음 하나(표 후보)의 크기 상한이다. 넘으면 **그 묶음만** 괘선 기반을 포기한다: 표도 실패 표시도 내지 않고, 그 글자는
글자 정렬 기반 표나 글 블록으로 간다. 쪽의 `notes` 에 `lines_table_skipped:too_many_cells:<칸 수>`·`lines_table_skipped:too_many_rules:<토막 수>`
가 남는다. 같은 쪽의 다른 표와 문서의 나머지는 그대로다. 둘 다 환경 변수이고 0 이하나 숫자가 아니면 import 때 죽는다.

| 변수 | 기본값 | 세는 것 | 근거 |
|---|---:|---|---|
| `PARSER_MAX_TABLE_CELLS` | 20,000 | x·y 경계로 세운 격자 후보의 칸 수 | 공개 보고서 여덟(2026-10-16 잼)의 최대 1,739 의 열 배 남짓. 상한 바로 아래인 200×100 온 폭 괘선 표 한 쪽이 호스트에서 약 1초 |
| `PARSER_MAX_TABLE_RULES` | 5,000 | 묶음 안 괘선 토막(가로+세로) 수 | 같은 여덟의 최대 594 의 여덟 배 남짓. 쪽마다의 그리기 항목 상한 `MAX_RULE_SEGMENTS` 8,000 보다 작다 |

같은 밴드에서 산출을 바꾸지 않고 최악 비용을 줄인 것: 괘선 표의 「값 행이 쌓인 구간」 고리(띠² × 조각 → 조각), 덮음 검사(칸 × 괘선 →
칸 × 그 높이의 괘선), 위첨자 붙이기(숫자 조각 수의 제곱 → 오른쪽 끝 근처만), 읽는 차례(재귀 → 스택. 상자 1000 개의 계단에서
`RecursionError` 였다). 200×100 표 한 쪽이 45초에서 1초로 줄었다. 재현과 수는 `tests/test_worst_case.py` 머리말.

### 옛 약속은 걷었다

주소를 받아 파서가 내려받던 옛 약속(`application/json` 의 `{"sourceUrl"}` → `{pageCount, pages}`, pypdf)은 밴드 PX(2026-10-16)에서 걷었다.
아무 http(s) 를 내려받는 길이라 SSRF 였고, 부르던 TS worker 는 먼저 걷혀 부르는 쪽이 0 이었다. `pypdf` 의존성도 같이 뺐다. 이제 415 다.

### 한 번에 한 건, 자식 프로세스 하나

pdfium 은 스레드에 안전하지 않다(pypdfium2 README 「Incompatibility with Threading」: "PDFium is inherently not thread-safe."
설치된 5.14.0 의 `METADATA` 에서 읽음, 2026-10-08. 자세한 절은 <https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading>).

- 분해 한 건은 **자식 프로세스 하나**에서 돈다(밴드 PX). 여는 것·암호와 쪽 수 확인·분해·스키마 검사가 다 자식 안이다.
  PDF 는 한 번만 연다: 암호·쪽 수를 본 문서를 그대로 분해에 넘긴다(`docparse.document.parse_opened_places`, 밴드 PX2).
  서비스 프로세스는 pdfium 을 열지 않으므로, pdfium 이 죽거나 메모리를 다 써도 서비스는 살아 있고(500 `worker_died`)
  시간 상한을 넘은 분해는 밖에서 죽일 수 있다(422 `parse_timeout`). 스레드는 밖에서 멈출 수 없어 이 길을 골랐다.
- 자식은 `multiprocessing` 의 forkserver 로 띄운다: 이 모듈(`app`)을 미리 읽어 둔 스레드 없는 서버 프로세스를 갈라 쓴다.
  건마다 띄우는 비용은 호스트에서 약 4 ms(spawn 이면 import 를 다시 해 약 250 ms. 2026-10-16 잼). 첫 건은 서버를 띄우느라 약 0.3초 더 든다.
- 자식을 띄우고 기다리는 것은 일꾼이 **하나뿐인 실행기**다. 그래서 한 번에 한 건이고, 자식도 한 번에 하나다.
- 차례는 이벤트 루프에서 기다린다. 기다리는 요청이 스레드를 쥐지 않으므로 분해가 돌거나 요청이 쌓여 있어도 `/healthz` 는 바로 답한다.
- 자리(도는 것 + 줄)는 실행기의 일이 끝날 때 돌려준다. 부르는 쪽이 끊어도 이미 도는 자식은 끝까지(또는 시간 상한까지) 돈다.
- uvicorn worker 는 하나다. 늘리면 worker 마다 일꾼이 하나씩 생겨 자식이 그만큼 함께 돈다(메모리가 그만큼 든다).

## 명령줄

```bash
cd services/parser
uv run --frozen python -m docparse parse <pdf> --out <폴더> [--places] [--pages 3,10-12] [--strategy auto|lines|text] [--layout 1|2] [--render]
uv run --frozen python -m docparse render <pdf> --out <폴더> [--pages ...] [--dpi 200]
PARSER_REPORTS_DIR=<공개 보고서 PDF 폴더> uv run --frozen python -m docparse score --gold <정답 표 폴더> [--layout 1|2] [--json <파일>]
```

### 분해 판 (`layout`, 밴드 TRD1)

판은 분해 동작의 묶음 번호다. **1(기본)** 은 바뀌지 않는 판이다 — 그린워싱(`MARC-ENT-442`, 1차 코랩 그대로)이 쓰고, 산출은 판 인자를 주지 않을
때와 바이트까지 같다(PB1 기준선 `tests/baseline/synthetic.sha256.json`). 1 을 바꾸려면 그린워싱 감독의 동의와 그린워싱 말뭉치 앞/뒤 대조가 따로
든다. **2** 는 번역 판(영문번역 입력, `MARC-ENT-471`)이다: 블록마다 쪽의 띠 `region`(body·header·footer)과 내용 해시 키 `key`, `parser.layout: 2`
를 싣는다. 손질마다 따로 켜는 인자는 두지 않고 다음 손질은 3 으로 올린다. 판 2 의 고정값은 `tests/baseline/layout2.sha256.json`.
Python `parse_pdf(..., layout=2)`·명령줄 `--layout 2`·HTTP `?layout=2` 가 같은 산출이다.
`key` 는 쪽·글 블록 "text"|표 "table"·본문(글 또는 칸 격자)의 해시라 쪽 범위 분해·상자 흔들림에 같다(밴드 TRD2 — 블록 `kind` 는 넣지 않는다).
판 2 는 막대 도표·연표의 그리기(글 없는 채움 막대 줄, 모든 글 행에 닿는 곡선 + 빈 칸)가 세운 표를 빼고 그 글자를 글 블록으로 둔다. 쪽 `notes` 에
`figure_table_dropped:<method>:<상자>` 가 남는다(밴드 TRD3, 문턱은 `docparse/tables.py` 의 `FIGURE_*`).
★ 이 폴더의 소스·스키마·의존(`docparse/**/*.py`·`schemas/*.json`·`app.py`·`pyproject.toml`·`uv.lock`)을 고치는 밴드는 주석만 바꿔도 같은 커밋에서 `apps/api-py/esgapi/core/documents/contract.py` 의 `EPOCH_PARSER_SHA` 갱신 + `EPOCH` +1 을 한다(core 문서 산출물의 열쇠 — 그 두 줄이 그 밴드의 알림 줄, `MARC-ENT-514`).

공개 보고서 PDF 와 정답 표는 저장소에 없다. `PARSER_REPORTS_DIR`·`PARSER_GOLD_DIR` 로 가리킨다. 두 변수가 없어도 import 와 `parse` 는 되고,
그 경로를 쓰는 함수가 불릴 때 `docparse.config.MissingPathError` 로 실패한다.

## 어디서 가져왔나

**옮겨 온 자리(역사)**: 처음 가져온 것은 esg-lab 의 커밋 `2e2c2c4` 의 `py/docparse/` 다. 아래 표는 가져올 때(밴드 PD2, 2026-10-08)의 것이다.
「다른 줄」은 그때 `diff` 의 −/+ 줄 수다. 정본이 된 뒤(밴드 PX)로는 docparse/ 를 여기서 고치므로 이 표는 다시 세지 않는다.

| 파일 | 원본 줄 수 | 다른 줄 (−/+) | 무엇이 다른가 |
|---|---:|---:|---|
| `layout.py` `tables.py` `tables_lines.py` `tables_text.py` `table_model.py` `blocks.py` `sections.py` `reading_order.py` `charplaces.py` | 341·57·327·204·86·45·48·66·100 | 0/0 | 분해 규칙과 문턱값. 그대로 |
| `engine/types.py` `engine/pdfium_engine.py` | 66·843 | 0/0 | 엔진. 그대로 |
| `__init__.py` `__main__.py` `document.py` `render.py` `compare.py` | 2·5·180·24·150 | 0/0 | 그대로 (`engine=` 인자의 자리는 남아 있고 `None`·`"pdfium"` 만 받는다) |
| `score.py` | 117 | 1/1 | 오류 글 속의 환경 변수 이름 |
| `engine/__init__.py` | 28 | 17/13 | 엔진 하나, `DEFAULT_ENGINE = "pdfium"`, `--engine` 인자를 다는 함수 없음 |
| `config.py` | 26 | 8/27 | 스키마는 패키지 곁 `schemas/`, 보고서·정답 폴더는 환경 변수. 없으면 `MissingPathError` |
| `cli.py` | 284 | 172/5 | `parse`·`score`·`render` 만. `--engine` 없음 |

`parser.name` 은 `"docparse"`, `parser.version` 은 `"0.1.0"` 그대로다(스키마가 이름을 못 박고, 바꾸면 골든과 달라진다).

**가져오지 않은 것**: `engine/pymupdf_engine.py`, `enginediff.py`(두 엔진 견주기), `tagpages.py`·`placecheck.py`(PDF 를 고쳐 쓰는 도구)와 그 CLI 명령.
**아직 안 가져온 것**(다음 밴드): 도표 쪽 모듈 `chartcand.py`·`tagtext.py` 와 CLI `chartcands`·`tagtargets`·`tagtext`. `charts.py`·`places.py` 는 밴드 CHL1 이 esg-lab `eab56dc` 에서 규칙 그대로 옮겼다(포맷·린트·타입 표기만, 명령줄은 `parse --layout 2 --charts`).

**정본은 esg-app 이고 esg-lab 을 따라가지 않는다.** esg-lab 의 `py/docparse` 가 바뀌어도 여기로 옮기지 않는다.
분해 산출이 esg-lab `2e2c2c4` 와 같음을 지키는 것은 줄 글자 견주기가 아니라 검증 트랙의 대조(PB1: 기준선 동결, 추적 안 대조 (a)·추적 밖 대조 (b))다.
뿌리 `scripts/section4-PD2.sh` 의 「위 표를 다시 센다」는 사본이던 때의 장치라 정본이 된 뒤로는 무효다(닫힌 밴드의 기록으로 남긴다).

**「출처 가르기」**: `engine/pdfium_engine.py` 의 줄·스팬·낱말·그리기 항목·책갈피·음영 상자는 밴드 PD1 에서 동작 명세만 보고 다시 쓴 것이다
(파일 안의 `CLEANROOM(PD1)` 자리. 명세 `band-handoffs/PD1-cleanroom-spec.md`, 경위 `MARC-ISSUE-39` 의 노트, 보고 `band-reports/PD1-pdfium-engine.md`).
그 한계(문턱값을 다른 엔진의 산출을 재서 정했다는 것)는 정본이 된 뒤에도 그대로다.

## 골든: 네 공개 보고서

골든은 esg-lab `2e2c2c4` 를 저장소 밖에 풀어 `--engine pdfium` 으로 낸 산출이다. 이 분해기의 산출(호스트 CLI, 컨테이너 HTTP)을 JSON 값으로 견준다.
밴드 PD2 때는 `scripts/section4-PD2.sh` 가 견줬고, 정본이 된 뒤로는 검증 트랙의 대조(PB1)가 이 자리를 맡는다.
골든·공개 보고서·정답 표는 저장소에 넣지 않는다. 골든은 esg-lab `2e2c2c4` 와 pypdfium2 5.14.0 에 묶여 있다: 둘 중 하나가 바뀌면 「같다」는 다시 재야 한다.
`scripts/verify.sh` 는 네 문서를 재지 않는다.

## 테스트

```bash
uv run --project services/parser --frozen pytest -q services/parser                 # 원본 없이 도는 것 (verify.sh 가 돈다)
PARSER_REPORTS_DIR=... PARSER_GOLD_DIR=... uv run --project services/parser --frozen pytest -q services/parser -m reports   # 정답 표 15개의 하한
```

- 테스트용 PDF 는 `tests/pdfbuild.py` 가 PDF 연산자를 직접 써서 짓는다(표준 라이브러리만). **글꼴 파일을 심지 않는다.**
  라틴 글은 표준 Helvetica 를 이름으로만 가리키고(너비는 Adobe AFM 값), 한글은 글꼴 파일 없는 Type0 + ToUnicode 다. 암호는 RC4 40비트다.
- 그래서 못 짓는 것이 있다: 심은 글꼴에 기대는 상자 값, 합자(ﬁ)의 ToUnicode, `TJ` 자간. 이것들은 네 문서 골든만이 지킨다.
- 글꼴을 심지 않은 Helvetica 의 글자 상자는 pdfium 이 고르는 대체 글꼴에 달려 있다. 맥 휠과 리눅스 휠에서 **글자의 걸음(원점에서 다음 원점까지)은 같고 상자가 다르다**:
  세로는 라틴 글자 전부가 다르고(위 0.04em, 아래 0.013em), 가로는 글리프가 걸음보다 넓게 그려지는 글자(`/ A \ ^ _ f k r`)의 오른쪽 끝이 다르다(크기 8 에서 `f` 가 0.28pt).
  2026-10-08 에 152자를 견줬다: 124자가 달랐고 전부 라틴, 한글 글꼴로 쓴 28자의 상자는 같았다.
  단위 테스트는 이 값들에 기대지 않는다(세로는 「바닥선이 상자 안에 있다」까지, 오른쪽 끝은 여유를 두고 본다). 리눅스 컨테이너에서 한 번 돌려 200개가 통과했다(`verify.sh` 는 호스트에서만 돌린다).
- `reports` 표식의 테스트는 원본·정답이 없으면 건너뛰지 않고 실패한다(「못 쟀다」는 통과가 아니다).

## 의존성과 라이선스 (기록. 법적 판단이 아니다)

**리눅스 이미지(`python:3.13.9-slim-bookworm`, arm64) 안의 `/app/.venv` 에서 본 것**이다(`importlib.metadata`, 2026-10-08). 실행 의존성 21개 전부다(밴드 PX 가 pypdf 를 빼서 지금은 20개). dev 의존성(pytest, httpx)은 이미지에 없다.

| 이름 | 판 | METADATA 의 License | dist-info 의 `licenses/` |
|---|---|---|---|
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0, dependency licenses | `LICENSES/Apache-2.0.txt`, `BSD-3-Clause.txt`, `CC-BY-4.0.txt` 와 `data/linux_arm64/BUILD_LICENSES/` 의 15개: abseil, agg23, fast_float, freetype, icu, lcms, libjpeg_turbo(.ijg, .md), libopenjpeg, libpng, llvm-libc, pdfium-binaries, pdfium, simdutf, zlib |
| jsonschema | 4.26.0 | MIT | `COPYING` |
| jsonschema-specifications | 2025.9.1 | MIT | `COPYING` |
| referencing | 0.37.0 | MIT | `COPYING` |
| rpds-py | 2026.6.3 | MIT | `LICENSE` |
| attrs | 26.1.0 | MIT | `LICENSE` |
| fastapi 0.142.2 · starlette 1.7.0 · uvicorn 0.54.0 · pydantic 2.13.5 · pydantic_core 2.46.5 · anyio 4.15.1 · h11 0.16.0 · click 8.5.0 · idna 3.20 · annotated-types 0.8.0 · annotated-doc 0.0.5 · typing-inspection 0.4.4 · typing_extensions 4.16.0 · opentelemetry-api 1.45.0 | | MIT (fastapi, pydantic, pydantic_core, anyio, h11, annotated-types, annotated-doc, typing-inspection) · BSD-3-Clause (starlette, uvicorn, click, idna) · PSF-2.0 (typing_extensions) · Apache-2.0 (opentelemetry-api) | 저마다 `LICENSE` 류 하나 |

pypdfium2 의 `licenses/` 안에서 낱말 「GPL」·「General Public」 이 든 줄은 11줄이다: `icu.txt` 9줄(472~520줄. 빌드 도구에 붙은 고지와 그 「special exception」 문단), `llvm-libc.txt` 2줄(216·219줄. Apache-2.0 의 LLVM 예외 조항이 GPLv2 를 말하는 자리).
**읽은 것은 여기까지다.** 이 줄들이 납품물에 어떤 의무를 지우는지는 판단하지 않았다(`MARC-ISSUE-40` 9번).
품은 pdfium 의 판은 호스트(macOS arm64)와 이미지(리눅스 arm64)에서 같다: 156.0.8076.0.

테스트용 PDF 에 심긴 글꼴은 없다(`tests/pdfbuild.py` 는 글꼴 파일을 싣지 않는다).
