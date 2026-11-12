# inventory — AI 온실가스 인벤토리

흐름 셋 `scope12.engine@1`(Scope 1·2 계산)·`scope3.llm-first@1`(Scope 3 의 LLM 먼저 분류·추천·계산)·`scope3.colab@157`(받은
Scope 3 코랩을 옮긴 판 — Scope 3 의 기본 흐름, 끼움 `flows/binding_157.py`)과 저장 없는 경로 셋(`POST /inventory/calc` · `/inventory/scope3/shortlist` · `/inventory/scope3/classify`)이 산다. 폴더는 엔진·계약·도구·흐름
축으로 나뉜다(`MARC-ENT-267`, 적용 `MARC-ENT-270`, 밴드 EN1).

Scope 3 실행(`POST /runs` 의 `inventory.scope3`)은 환경 스위치 `INVENTORY_SCOPE3_RUNS_ENABLED`(기본 꺼짐)가 켜져야 열린다 — 꺼져 있으면 400. 실행 시간 초과 고침 `MARC-ISSUE-499`·`MARC-ENT-527` 뒤 다시 본다.

Scope 3 연도 상태(`GET /inventory/scope3/years/{year}`)·카테고리 잠금(`POST·DELETE …/categories/{category}/lock`)은 밴드 S3K2a(`MARC-ENT-559`)다. 「지금 결과」는 저장하지 않고 읽을 때 셈한다 — 잠긴 카테고리는 핀 실행, 아니면 그 해 만든 차례 마지막 「실행 done + 결과 done」(`service/utils/scope3_state.py`). 표는 잠금 하나(`inventory_scope3_categories`). 대시보드의 Scope 3 칸(`total.scope3`·`sum`·`scope3Categories`)도 같은 재료로, Scope 1·2 설정과 따로 셈한다.

Scope 3 줄 덧판(`POST …/scope3/runs/{id}/categories/{category}/exclusions·restorations`·`GET …/edits·history`)은 밴드 S3K2b-1(`MARC-ENT-570`)이다. 편집은 (회사, 실행, 줄 rowId)에 매인 불변 사건이고(표 `inventory_scope3_row_edits`) 지금 상태는 가장 큰 id 사건이다. 새 실행에 옮겨 붙이지 않는다 — 옛 편집은 그 실행 히스토리에 남는다. 결과 GET 본문은 편집을 덮지 않는다(`service/*/scope3_edits.py`).

계수 수정(`POST …/scope3/runs/{id}/categories/{category}/factors`)은 밴드 S3K2b-2(`MARC-ENT-570`·`MARC-ENT-442`)다. AI 를 다시 부르지 않고 kind 별 식을 `service/utils/scope3_factors.py` 에 다시 적어 센다(엔진 import 0, 같은-계수 대조 시험이 엔진과 글자 같음을 지킨다). 같은 표에 사건 종류 `factor` 로 남고(0007) 지금 상태는 축 둘(제외·계수)이다. 고친 co2e 와 AI 원안은 사건에 있고 결과 본문은 그대로다.

추상화(엔진 인터페이스·베이스 클래스·플러그인·팩토리)는 세우지 않았다 — 판이 실제로 둘 이상 생긴 뒤 공통을 뽑는다.

## 지도

| 폴더 | 무엇이 사나 | 무엇을 import 해도 되나 | 지키는 기계 |
|---|---|---|---|
| `engines/` | 엔진. 흐름마다 폴더, 그 아래 판마다 폴더(`engines/<흐름>/<판>/`, 판 이름은 흐름 id 의 「이름@판」을 접은 것). `scope12/engine_1/`(esg-lab `ts/kernel`·`ts/ghg-calc` 를 옮긴 계산·집계·직렬화), `scope3/llm_first_1/`(esg-lab `ts/scope3/src/domain` 을 옮긴 범주·후보 추리기·LLM 단계·파이프라인·직렬화), `scope3/colab_157/`(받은 Scope 3 코랩 `MARC-ENT-157` 을 옮긴 템플릿·계수 책 읽기·C1·C2·지출·폐기물·거리 운송·출장·통근 셈(C6·C7 후처리는 시트 고리 뒤)·에너지 계수 사슬과 C3·C8·C13 셈(`energy.py` — S3C-c1a)·C12 판매제품 폐기·C15 투자 셈(`product.py` — S3C-c1b-1)·C11 판매제품 사용·C14 프랜차이즈 셈(결과 후처리 차례 하나 — `product.py` — S3C-c1b-2)·출력 파일 둘의 내용(`output_files.py` — S3C-c2)·직렬화 — pandas, 직선거리는 geographiclib 를 `distance.py` 하나만 부른다 `MARC-ENT-363`) | 자기 판 안, `tools/`, `esgapi.core` 의 순수 조각. 계약·출력·흐름·표면·`data_loader` 는 안 된다. 다른 흐름의 엔진은 간접으로도 안 된다 | `inventory-engine-not-contracts`, `inventory-engines-apart`(independence), 「다」(`pure-modules`). Scope 3 의 판마다 순수 검사 파일 하나: `llm_first_1` 은 `tests/test_scope3_is_pure.py`, `colab_157` 은 `tests/engines/scope3/colab_157/test_purity.py`(새 판은 저절로 걸리지 않는다). 같은 흐름의 판끼리는 `inventory-scope3-versions-apart`(independence) |
| `contracts/` | 계약: 결과 꼴 셋 `scope12.result@2`·`scope3.llm-first.result@2`·`scope3.colab.result@1` 의 TypedDict 와 검사기 `RESULT_SHAPES`(`shapes.py`). 셋 다 경로의 응답 꼴이고 그 이름이 OpenAPI components 이름이다(셋째는 `GET …/scope3/runs/{run_id}/result` — 줄 끝의 입력 칸 `input` 은 NotRequired 라 옛 결과도 같은 판, S3R2) | `pydantic`, 표준 라이브러리. 엔진·흐름·출력·표면은 안 된다(`tools/` 는 막히지 않는다) | `inventory-contracts-not-engines`, 「다」. 고정 스키마 `tests/test_flow_shapes.py`, 뼈대 `tests/contracts/test_shapes.py`, 두 벌 낱말 `tests/flows/test_vocab.py` |
| `tools/` | 판과 무관한 도구: `tools/jsrepr.py`(JS 문자열 흉내, 두 엔진이 같이 씀), `tools/xlsx_reader.py`(xlsx 바이트 → 읽힌 표. xlsx 를 여는 것은 여기뿐), `tools/scope3_sheets/`(받은 계수 책·템플릿의 읽힌 값·드롭다운·어긋남 검사. 지금은 시험만 부른다) | 표준 라이브러리, `tools/` 안, `esgapi.core.calc`. 엔진·계약·출력·흐름은 안 된다 | `inventory-tools-know-no-axis`, 「다」, `tests/test_s3sheets_is_pure.py`(허용 목록) |
| `flows/` | 흐름: `scope12_engine_1.py`(단계 `calculate`)·`scope3_llm_first_1.py`(단계 `pipeline`)·`scope3_colab_157.py`(단계 `calculate`), `registration.py`(`FLOWS`·`DEFAULTS`). 등록은 `apps.py` 의 `ready()` | 엔진·계약·도구 전부(둘을 잇는 자리). Service 와 남의 도메인은 안 된다 | 「다」, `tests/test_flows.py::test_flows_call_no_service`·`test_flow_declarations` |
| `service/`·`api.py` | 표면: 경로 셋(`service/apis/`), 요청 꼴과 경로 전용 응답 꼴(`service/schemas/`), 쓰임새(`service/services/`), 도메인을 넘는 조립(`service/actions/scope3_shortlist.py`) | 엔진·계약·`data_loader`. models 는 직접 안 된다, Service 는 남의 도메인을 안 된다 | 「라」·「바」, `tests/test_route_shapes.py`, `tests/test_route_bodies.py`(본문 바이트), `config/tests/test_api_contract.py`(OpenAPI = `generated/openapi.json`) |
| `prompts/` | Scope 3 의 템플릿 `scope3-classify/1.md`·`scope3-recommend/1.md`(프롬프트 id `scope3/classify@1`·`scope3/recommend@1`)과 코랩 판의 `scope3-colab-group-name/1.md`·`scope3-colab-naics-pick/1.md`(출처 표 `prompts/README.md`. 모두 core 규약 `esgapi/<모듈>/prompts/<이름>/<판>.md`라 자리를 옮길 수 없다) | — | `tests/test_scope3_prompts.py` |
| `data/`·`data_loader.py` | 패키지에 실린 기준정보 표(환산, GWP 세트 둘, 표본 계수 셋. 출처 `data/README.md`)와 그 적재기. 엔진 Scope 1·2 에 묶인 파일 읽기다 | 엔진 Scope 1·2 의 `tables`·`types` | 기계 없음(축 계약 밖). `tests/test_data_loader.py` 가 읽힌 값을 잰다 |
| `tests/` | 순수 층과 업무 층(`django_db`). `tests/engines/<흐름>/<판>/`·`tests/contracts/` 는 소스를 비추고, `tests/flows/` 는 두 축을 잇는 시험이다. `tests/data/` 는 시험 자료(검산 사례·가상 계수·골든·고정 스키마). `tests/scope3colab_dump.py` 는 코랩 대조(esg-lab `scope3colab run --engine-result`)에 줄 엔진 결과를 내는 스크립트다 | 무엇이든(시험 밖 코드가 시험을 들이는 것만 막힌다) | 「사」(`product-knows-no-tests`), `scripts/check_test_layout.py`(자리 규칙) |

| `models.py`·`migrations/`·`management/` | 온실가스 인덱스 풀·시설별 배출계수 풀(아래 「온실가스 풀」) — 표 넷과 `0001_ghg_pool`, 씨앗 명령 `seed_ghg_pool` | 모델은 `esgapi.core.models` 와 `service/utils/ghg_pool.py`(순수). 표를 여는 것은 `service/selectors`·`services` 의 `ghg_pool.py` 뿐 | 「나」·「바」, `core/tests/test_selector_scope.py`(GLOBAL_TABLES), `tests/test_models.py` |

출력(엑셀 등) 폴더 `outputs/` 는 없다. 엑셀을 쓰는 밴드가 세운다(아래 「다음 판 넣는 법」).

## 온실가스 풀(K1b-2a — 결정 MARC-ENT-463·469 3)

- **모든 고객사 공통 하나**: 표 넷(`ghg_index_nodes`·`ghg_factors`·`ghg_factor_versions`·`ghg_factor_gases`)에 회사 칸이 없다.
  쓰기는 운영 관리자만(`core/permissions.py` 의 `inventory_admin_ghg_*` 열둘 — 경로 `/inventory/admin/ghg-index/…`·
  `/admin/ghg-factors/…`·`/admin/ghg-options`). 고객사 사용자는 풀을 못 고친다(MARC-ENT-478 권장안).
- **나무 4단**: 배출범위 → 배출원 유형 → 배출활동 → 자산/시설(잎만 공통 시설 코드·1차 단위·툴팁). 「부모 단 = 자기 단 − 1」은
  services, 뿌리 = 범위·잎 칸은 DB CHECK. 지우기는 삭제 표시(잎이면 그 계수도).
- **계수 = 정체 + 판**: 고치기는 새 판(`version`+1). 판·가스 표는 앱 역할이 SELECT·INSERT 만 — 옛 판은 글자 그대로 남는다.
  회사 선택(K1b-2b)은 판을 잡는다. 잎마다 삭제 안 된 계수가 있으면 기본이 정확히 하나(지우면 남은 첫 행이 잇는다).
- **사용 중 판정은 자리만**: `nodes_in_use`·`factors_in_use` 는 지금 늘 빈 집합이다(회사 몫은 K1b-2b·S12a, sid:MARC-ISSUE-418).
- **씨앗**: `manage.py seed_ghg_pool [--gwp-set <id>] [--dry-run]`(기본 GWP 세트 `kr-ets-decree-annex2`). 씨앗 파일
  `data/ghg-pool-seed.json` 에는 낱줄 id·이름·단위 글자만 있다 — 값은 reference 낱줄의 `value_raw`(먼저 `import_factors`)와
  `data/gwp-sets.json` 에서 명령이 읽는다. 멱등(씨앗 열쇠가 있는 행은 건드리지 않는다). 범위는 engine_1 이 셈하는 것
  (Scope 1 고정연소 · Scope 2 외부에서 공급된 전기). 나무는 `Scope 1 > 고정연소 > <연료 22 = 배출활동> > <설비 종류 잎>` ·
  `Scope 2 > 간접배출 > 외부에서 공급된 전기 사용 > <설비 잎>`(결정 MARC-ENT-676) — 잎마다 계수 묶음(연료 잎은 부문 넷 ·
  전력 잎은 열하나, 합 99). 잎 이름 = 공통 시설 코드 이름(설비 종류 — 호기·대수는 사업장 세부시설명 몫).
  산화계수는 싣지 않는다(S12a 셈이 정한다).
- **옛 씨앗 지우기**: `manage.py retire_ghg_seed [--apply] [--plan <json>]`(S12S1). 씨앗 파일의 `retired`(옛 씨앗 — 연료 =
  잎 코드 — 의 노드 열쇠 26)를 센다. 기본은 셈만, `--apply` 는 잠근 뒤 다시 세어 전부 0 일 때만 삭제 표시로 지운다
  (옛 활동·잎·계수 + 다른 살아 있는 잎이 안 쓰는 옛 코드). 쓰는 회사 선택·잡은 판·덮어쓴 행·씨앗 밖 자식·씨앗 아닌 계수·
  고친 씨앗 계수·사업장 자산/시설이 쓰는 지울 옛 코드가 하나라도 있으면 `RETIRE=blocked`(지움 0 — 수를 들고 사용자).
  끝 줄 `RETIRE=nothing|ready|blocked|done`. 차례는 `retire_ghg_seed` → `--apply` → `seed_ghg_pool`.

## 규칙 세 줄

1. **엔진은 계약을 모른다** — `[importlinter:contract:inventory-engine-not-contracts]`(엔진 → 계약·출력·흐름·표면·`data_loader` 금지).
2. **계약은 엔진을 모른다** — `[importlinter:contract:inventory-contracts-not-engines]`(계약 → 엔진·흐름·출력·표면 금지).
3. **둘을 잇는 것은 흐름뿐이다** — 위 둘에 `inventory-tools-know-no-axis`(도구 → 엔진·계약·출력·흐름 금지)를 더해,
   엔진과 계약을 둘 다 들일 수 있는 자리는 `flows/` 와, 축 계약이 보지 않는 표면(`service/`·`api.py`)·`apps.py`·
   `data_loader.py` 다. 지금 둘을 실제로 함께 들이는 것은 흐름 밖에서는 표면뿐이다(아래 「규칙 밖 자리」). 엔진의 흐름끼리는
   `inventory-engines-apart`(independence, 간접 사슬도 문다)가, Scope 3 의 판끼리는 `inventory-scope3-versions-apart` 가 떼어 놓는다.

셋은 직접 import 만 본다(`allow_indirect_imports = True`). 무효 조건: `uv run lint-imports` 에서 이 계약 넷 가운데 하나라도
KEPT 가 아니면 위 문장은 거짓이다(판끼리 계약까지 다섯). 무는지는 `scripts/planted-breaks.sh`(30~33·40·46, 계약 id 로)가 잰다.

## 읽는 차례

`flows/registration.py` → `flows/scope12_engine_1.py`·`flows/scope3_llm_first_1.py`·`flows/scope3_colab_157.py` →
`contracts/shapes.py` → `engines/scope12/engine_1/calc.py` → `engines/scope3/llm_first_1/pipeline.py` →
`engines/scope3/colab_157/__init__.py`(코랩 셀 → 파일 표)·`pipeline.py` → `tools/`.

## 다음 판 넣는 법 (Scope 3 의 코랩 판 S3C-a 가 지난 길)

아래 `<판>` 은 흐름 id 의 「이름@판」을 접은 이름이다(흐름 id `scope3.colab@157` → `colab_157`). 흐름 id 의 판 표기는
받은 자료 출처 번호(`MARC-ENT-157`)다 — 이름 굳힘 노트 `ic5yc-…`(`sid:MARC-TICK-71`).

- **엔진**: `engines/scope3/<판>/` 를 새로 복사한다. `engines/scope3/llm_first_1/` 를 고치지 않는다.
  새 판도 `engines/scope3/` 아래에 두어야 `scope3` 꾸러미가 남는다(자리 규칙 — 납작하게 `engines/scope3_<판>/` 로
  두면 평평한 `tests/test_scope3_*.py` 열넷의 허용이 「필요 없는 허용」이 되어 자리 규칙이 빨개진다).
  같은 흐름의 판끼리도 서로 import 하지 않는다 — `.importlinter` 의 independence 계약
  `inventory-scope3-versions-apart` 의 modules 에 `esgapi.inventory.engines.scope3.<판>` 한 줄을 더한다(S3C-a 가 세움.
  계약 수는 그대로).
- **흐름**: `flows/scope3_<판>.py` 를 쓴다.
- **등록**: `registration.FLOWS` 에 더하고, 기본 흐름이 될 때 `DEFAULTS` 한 줄을 바꾼다(코랩 판은 S3C-c 에서).
- **시험**: `tests/engines/scope3/<판>/` 에 둔다. 새 시험 폴더마다 `__init__.py` 를 둔다(같은 이름 `test_calc.py` 가
  여럿이라 패키지가 아니면 수집이 부딪친다). 새 판의 순수 검사(파일·시계·네트워크 금지)는 판마다 파일 하나다
  (`tests/engines/scope3/<판>/test_purity.py` — 기존 시험을 parametrize 하면 기존 노드 id 가 바뀐다). 새 판이 계약에 낱말을 보태면
  `tests/flows/test_vocab.py` 의 `PAIRS` 에 짝을 더한다.
- **계약 판**: `@n` 은 엔진 판과 따로 움직인다. 결과 꼴이 바뀌면 `contracts/` 에 새 `@n` 꼴과 고정 스키마
  (`tests/data/flow-shapes/`)를 둔다. 같은 꼴이면 기존 계약을 그대로 쓴다.
- **출력**: 엑셀 쓰기는 `outputs/` 를 세우고 `.importlinter` 에 「출력 → 엔진·흐름 금지」 계약을 하나 더한다
  (그린워싱의 `greenwash-outputs-not-engine` 과 같은 꼴). 계약 수를 올리면 `reconcile/tests/test_tasks_registered.py` 도.
  Scope 3 코랩은 내용은 엔진(`colab_157/output_files.py`), 쓰기는 `outputs/` 를 세우는 밴드(지금은 시험 덤프의 쓰개 둘).

## 규칙 밖 자리

- **경로가 엔진을 바로 부른다**: 표면(`service/`)이 흐름을 거치지 않고 엔진을 import 한다 — import 문 21(services 14 ·
  schemas 4 · actions 3)에 `data_loader` 1 을 더해 22(밴드 EN1 의 BASE `e973637` 실측, 옮긴 뒤 같음). 계약으로 막지 않았다.
  경로가 흐름을 부르게 하는 것은 실행기 계열 후속이다. 무효 조건: 경로가 흐름을 부르게 되면 이 절을 지운다.
- **`data_loader.py`** 는 엔진 Scope 1·2 에 묶인 적재기인데 뿌리에 있다. `data/` 를 옮기면 패키지 자료 경로가 바뀌므로
  둘 다 두었다. 엔진은 이것을 들이지 못한다(규칙 1) — 표면이 표를 읽어 엔진에 값으로 넘긴다.

## 두 벌인 낱말

계약의 Literal 20개(`Gas`·`FactorGas`·`CalorificBasis`·`FacilityUse`·`FactorKind`·`SourceType`·`Scope`·`GroupKey`·
`SupportedCategory`·`Confidence`·`Basis`·`CandidateBasis`·`FallbackReason`·`LicenseStatus`·`NumberField`·`FailureKind`·
`ShortlistMethod`, 코랩 판의 `ColabOrigin`·`ColabStep`·`ColabMissing`)는 엔진의 것과 값·차례가 같다. 계약이 엔진을 import 하지 않으려고 다시 적었다(Literal 별칭은 스키마에
이름 없이 펼쳐지므로 결과 꼴 스키마는 바이트 그대로다). 지키는 기계: `tests/flows/test_vocab.py`(20쌍).

## 낡은 글이 남는 자리

- `tests/data/README.md` 4줄 — 시험 자료(바이트 0)의 출처 표. `data/ghg-calc/…` 는 esg-lab 쪽 출처 경로다.
- `prompts/README.md:14` 의 옛 경로(옮기기 전 Scope 3 엔진 폴더의 `llm_steps.py`) — 템플릿 자리(바이트 0)라 남겼다.
  지금 자리는 `engines/scope3/llm_first_1/llm_steps.py`.
- (끝남) `apps/api-py/scripts/readme_audit.py` 의 옛 폴더 줄과 백엔드 개발 글의 inventory 옛 경로는 README 밴드가 지금 자리로
  고쳤다. 백엔드 개발 글은 `docs/development.md` 로 옮겼다(뿌리 README.md 의 옛 글은 그 밴드의 다음 커밋이 걷는다).
