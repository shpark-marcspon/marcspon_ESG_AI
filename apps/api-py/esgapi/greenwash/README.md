# greenwash — 그린워싱 점검

흐름 `greenwash.colab@E0`: 마크스폰 Colab 노트북을 옮긴 esg-lab GW1 을 단계 여섯(extract → index → judge → wordcount →
locate → report)으로 끊어 돈다. 폴더는 축 다섯으로 나뉜다(`MARC-ENT-267`, 밴드 GX1).

흐름 `greenwash.rewrite@R1`: 대체표현. E0 의 결과(`greenwash.result@1`)를 받아 High·Mid 문장의 `exampleSentence` 를
채운 사본과 엑셀을 낸다(단계 둘 rewrite → report, `MARC-ENT-277`·`MARC-ENT-278`, 밴드 RW1). E0 뒤에 따로 부르는 흐름이다.
답 꼴은 구조화 출력(schema `rewrite` — items 배열, 항목마다 i·example_sentence)이
강제한다(`MARC-ENT-279`, 밴드 RW2). 프롬프트는 판 4(`greenwash/rewrite@4`, 값은 원문 것까지 모두 빈칸 — `MARC-ENT-309`,
밴드 RW4)이고 뒤 검사 셋이 붙는다 — 원문에 없는 평가어가 든 답은 그 문장 null(경고 `commentary`), 종결 어미가 원문과 다른
답은 그대로 쓰고 경고 `ending_mismatch`(`MARC-ENT-288`, 밴드 RW3), 빈칸 밖에 숫자가 남은 답은 그대로 쓰고 경고
`value_outside_blank`(Scope·ISO 이름 속 숫자는 뺌, `MARC-ENT-309`, 밴드 RW4). 모델은 gpt-6-luna(경로 `light-openai`,
temperature 없음 — `MARC-ENT-314`, 밴드 RW4 ②)로 E0 의 gpt-4.1-mini(`light-openai-41`)와 다르다.

추상화(엔진 인터페이스·플러그인·전략 패턴)는 세우지 않았다 — 판이 둘 이상 실제로 생긴 뒤 공통을 뽑는다.

## 지도

| 폴더 | 무엇이 사나 | 기계가 막는 것(greenwash 안, 계약 이름) | 지금 지키는 꼴(막는 기계 없음) | 그 밖의 기계 |
|---|---|---|---|---|
| `engines/e0/` | 엔진 E0 판: GW1 사본 열(`checker`·`chunking`·`dryrun`·`heuristics`·`parts`·`pdftext`·`ports`·`prompts`·`retrieval`·`wordcount`)과 사본 아닌 둘(`gw1.py` 꼴 있는 겉·추가 단어 키, `result.py` GW1 결과 조립) | → `contracts`·`outputs`·`flows`·`service`·`api` (`greenwash-engine-not-contracts`), → django·ninja·psycopg (「다」) | `engines` 안만 들인다. `tools` 를 들이는 것은 막히지 않는다 | `tests/test_copy_ast.py`(사본 아홉의 AST sha256, 허용 이름 `E0_NOT_COPIES`) |
| `contracts/` | 밖으로 나가는 꼴: `shapes.py`(result@1)·`review_shapes.py`(review@2 — 굳힌 판, 고침 edits)·`compare_shapes.py`(compare@1)·`terms_shapes.py`(terms-default)·`criteria_shapes.py`(criteria@1 — 판정 기준표)·`options_shapes.py`(options@1 — `POST /runs` 의 options, openapi 밖)·`checks_shapes.py`(checks@1 — 목록 줄)·`ai_setting_shapes.py`(ai-settings@2·ai-setting@3·ai-setting-default@3 — AI 설정 판, G2c2·AS3a-2·G2d), snake → camel 사상 `wire.py` | → `engines`·`flows`·`outputs`·`service` (`greenwash-contracts-not-engine`), → django·ninja·psycopg (「다」) | `contracts` 안만 들인다. `tools`·`api` 를 들이는 것은 막히지 않는다 | 고정 스키마 `tests/data/flow-shapes/`·`tests/contracts/` |
| `tools/` | 판 무관 도구: `textnorm`(정규화)·`pdftext_pypdf`(읽개 하나)·`pdfium_locate`·`coordinates`(문장 위치)·`llm_bridge`(core.llm 대화 호출 `LlmTextCall`)·`ports`(포트 Protocol 셋과 자리 꼴) | → `engines`·`contracts`·`outputs`·`flows` (`greenwash-tools-know-no-axis`), → django·ninja·psycopg (「다」) | `tools` 안만 들인다. `service`·`api` 를 들이는 것은 막히지 않는다 | `tests/flows/test_boundary.py`(SDK·환경 변수·파일·소켓) |
| `outputs/` | 결과 꼴에서만 짓는 것: `xlsx.py`(엑셀)·`compare.py`(수정본 비교) | → `engines`·`flows` (`greenwash-outputs-not-engine`), → django·ninja·psycopg (「다」) | `contracts`·`tools` 만 들인다. `service`·`api` 를 들이는 것은 막히지 않는다 | `test_boundary` |
| `flows/` | 흐름: `colab_e0.py`(단계 여섯, 어댑터 꼴 `GreenwashAdapters`, E0 에 묶인 구현 `LlmChatBridge`·`PROMPT_IDS`·`CHAT_ROUTE`·`MAX_OUTPUT_TOKENS`·`TiktokenCounter`·`PDF_TEXT`·`DEFAULT_TERMS`), `criteria_e0.py`(E0 판정 프롬프트의 고정 틀 + 기준표 조립·받기·판 묶음 값), `rewrite_r1.py`(대체표현, 단계 둘, `RewriteBridge`·`BLANK`·`BATCH_SIZE`), `registration.py`(`FLOWS`·`DEFAULTS`), `binding_e0.py`(끼움 `GreenwashBinding` — 옵션 받기·쪽 배열 → 노트북 글자·어댑터·판 묶음, 밴드 G1b. 둘째 꼴 `versions_with`·`inputs_with` 와 판 읽기 포트 `AiSettingStore` — G2c2) | → django·ninja·psycopg (「다」) | 축 넷을 다 들일 수 있다(엔진과 계약을 잇는 자리) | `test_boundary`, `tests/flows/test_registration.py` |
| `prompts/` | core.llm 템플릿 넷 `greenwash/{detect,eval,repair,low-only}@1`(E0 의 봉투)과 `greenwash/rewrite@{1,2,3,4}`(대체표현, 글이 템플릿 본문. 흐름은 판 4 를 쓰고 판 1·2·3 은 판 기록) | — | — | `tests/flows/test_colab_e0.py`(렌더·대조 B), `tests/engines/e0/test_prompts.py`(종류 넷의 id), `tests/flows/test_rewrite_r1.py`(rewrite 의 바이트 sha256) |
| `models.py`·`migrations/` | 검토 표 둘 `greenwash_reviews`·`greenwash_review_marks`(밴드 G1b — 아래 「검토 표」)와 AI 설정 판 `greenwash_ai_settings`(밴드 G2c2 — 아래 「AI 설정 판」) | 남의 모듈이 직접 들이기 (「나」) | `run_id` 는 외래 키가 아니다(`MARC-ENT-210` (1)) | `tests/security/test_greenwash.py`·`test_owner.py`·`test_same_company_foreign_keys.py` |
| `service/selectors/`·`services/` | 검토 표 읽기(`review.py` — 잠금·목록 줄 묶음 읽기 포함)·쓰기(`review.py`), AI 설정 판 읽기(`ai_settings.py` — 실행기의 판 읽기 `RunSettingStore` 포함)·저장/적용(`ai_settings.py`) | → 남의 도메인 (「바」) | 회사 조건 `for_company` | `core/tests/test_selector_scope.py`·`isolation/test_static_rules.py`·`test_transaction_rules.py` |
| `service/actions/` | runs·core·user 를 엮는 자리: `review.py`(결과·검토 GET·PUT, 감사 셋)·`report.py`(엑셀 보고서, 감사 download)·`checks.py`(목록 줄)·`ai_settings.py`(AI 설정 판 일곱 — 첫 문장 권한, 감사 setting_change) | — | 감사는 업무 블록의 마지막 문장 | `tests/service/apis/` |
| `service/`·`api.py` | 표면: 경로 일곱(`/greenwash`)과 AI 설정 판 일곱(`/ai-settings/greenwash` — 둘째 라우터 `ai_settings_router`), 아래 「경로」 | → models 직접 (「라」) | `contracts`·`flows`·`service/actions` 만 들인다. `engines` 를 직접 들이는 것은 막히지 않는다(밴드 GX1 의 손 검사만 쟀다) | `config/tests/test_api_contract.py` |

## 경로

| 경로 | 몸 | 꼴 | 오류 |
|---|---|---|---|
| `POST /runs {module:"greenwash", documentId, options}` | runs(끼움 `GreenwashBinding` — G1b) | 옵션 `greenwash.options@1` | 400 `INVALID_OPTIONS`(끼움의 한국어 한 문장) |
| `GET /greenwash/runs/{id}/result` | `actions/review.run_result` | `greenwash.result@1`(실행 결과 그대로) | 404 · 409 `RUN_NOT_DONE` |
| `GET /greenwash/runs/{id}/review` | `actions/review.review_state` | `greenwash.review@2`(표시 marks + 고침 edits, AI 원본은 결과 GET) | 404 · 409 `RUN_NOT_DONE`·`NO_REVIEW` |
| `PUT /greenwash/runs/{id}/review` | `actions/review.put_review` | 본문 `GreenwashReviewUpdate`(marks·edits) → review@2 | 404 · 409 `RUN_NOT_DONE`·`NO_REVIEW`·`REVIEW_LOCKED` · 400 `INVALID_REVIEW` |
| `GET /greenwash/checks` | `actions/checks.checks` | `greenwash.checks@1` | 401·403 |
| `GET /greenwash/runs/{id}/report?confirmed=` | `actions/report.report`(G1b-2a) | xlsx 한 파일(`attachment; filename="greenwash-report.xlsx"`) | 404 · 409 `RUN_NOT_DONE`·`NO_REPORT`·`NOT_CONFIRMED` |
| `GET /greenwash/compare` | 501(`MARC-ENT-354` 1 — 1차에 문서 비교 없음) | compare@1 | 404 · 501 |
| `GET /greenwash/terms/default` | 엔진 상수 | `GreenwashDefaultTerms` | — |
| `GET /ai-settings/greenwash?companyId=&limit=&offset=` | `actions/ai_settings.setting_list` | `greenwash.ai-settings@2` | 400 `COMPANY_AMBIGUOUS` · 404 `COMPANY_NOT_FOUND` |
| `GET /ai-settings/greenwash/default` | `actions/ai_settings.default_setting` | `greenwash.ai-setting-default@3` | — |
| `GET /ai-settings/greenwash/default/prompt-model` | `actions/ai_settings.default_prompt_model` | `ai.prompt-model@3`(core 꼴 — DB 0) | — |
| `GET /ai-settings/greenwash/{setting_id}?companyId=` | `actions/ai_settings.setting_detail` | `greenwash.ai-setting@3` | 404 `NOT_FOUND`(남의 판 같은 몸) · 숫자 아닌 id 422 |
| `GET /ai-settings/greenwash/{setting_id}/prompt-model?companyId=` | `actions/ai_settings.prompt_model` | `ai.prompt-model@3`(core 꼴) | 404 `NOT_FOUND` · 409 `AI_SETTING_UNUSABLE` · 숫자 아닌 id 422 |
| `POST /ai-settings/greenwash?companyId=` | `actions/ai_settings.save_setting` | 본문 `GreenwashAiSettingCreate` → ai-setting@3(201) | 400 `CRITERIA_*`·`AI_MODEL_*`·`AI_PROMPT_*`·`TERMS_*`(+ `fields`) · 409 `NAME_CONFLICT` · 422 |
| `PUT /ai-settings/greenwash/applied?companyId=` | `actions/ai_settings.apply_setting` | 본문 `GreenwashAiSettingApply`(id null = 기본 판) → ai-settings@2 | 404 `NOT_FOUND` · 409 `AI_SETTING_UNUSABLE` · 422 |

`/greenwash` 의 권한은 전부 고객사 사용자(`CUSTOMER`), `/ai-settings/greenwash` 일곱은 운영 관리자(`OPERATOR` — Bearer,
`companyId` 로 고른 회사). 운영 관리자의 그린워싱 읽기는 `MARC-ISSUE-178` 이 연다. 글자 층이 없는 PDF 의 실행은
extract 에서 `failed`·`errorCode no_text_layer`(`core.flows.types.NoTextLayer`). 개발 서버의 실행은 실행기가 모의 공급사만 실어
(키 없음) index 의 임베딩에서 `failed`·`setup_error` 로 끝난다 — 실호출은 `MARC-ENT-262` 승인 뒤.

## 검토 표

- `greenwash_reviews`(실행마다 한 행: `state` pending·in_review·confirmed, 확정 때·사람)와 `greenwash_review_marks`(문장마다
  한 행: `item_index`, `decision` adopted·excluded·NULL, 제외 사유). unique 는 `(company_id, run_id)`·`(company_id, run_id,
  item_index)`. 표시 → 검토는 같은 회사 복합 외래 키(NOT DEFERRABLE).
- `run_id` 는 BigInt 이고 외래 키가 아니다(`MARC-ENT-210` (1)). 같은 회사는 쓰는 길(actions 가 세션의 회사로 실행을 먼저
  찾는다)이 지킨다.
- DELETE 없음: 앱 역할의 GRANT 는 SELECT·INSERT·UPDATE. 표시 지우기 = `decision`·사유를 NULL 로 UPDATE. 응답·목록 줄의
  셈·감사는 `decision IS NOT NULL` 행만 본다.
- PUT 은 검토 행을 `FOR UPDATE` 로 잡고 한 블록 안에서 갈아 넣는다. 만들기 경합은 세이브포인트 안 INSERT 의
  IntegrityError 를 받는다 — 어긴 제약이 `greenwash_reviews_company_run_uniq` 일 때만 넘기고 다른 제약·이름 모름은 다시
  던진다(G1b-2a, `MARC-ISSUE-220` (2)). 감사는 adopt·exclude·confirm(`MARC-ENT-295` — 확정의 없음→채택은 줄 0, 사유 글은
  싣지 않음, 사유만 바꾼 제외는 줄 0 — `MARC-ISSUE-220` (1) 처분).
- 검토 고침(밴드 G1b-3, `MARC-ENT-354` 6 — 꼴 `greenwash.review@2`, 마이그레이션 0004): 표시 표 같은 행에 칸 아홉 —
  등급·판정 사유·수정 방향 × (값·때·사람). 칸마다 셋 다 NULL(고침 없음 = AI 그대로) 또는 셋 다 값(CHECK 넷, 등급은
  High·Mid·Low). AI 원본은 결과(`run_results`, 불변)에만 있다. PUT 의 `edits` 는 생략이면 그대로, 목록이면 갈아 넣기 —
  앞뒤 공백을 지우고 AI 와 같은 칸은 null 로 접은 뒤 센다(그 뒤 고침이 있으면 pending → in_review). 칸마다 때·사람은 그
  칸 값이 바뀐 PUT 에서만 바뀐다. 고침만 바꾼 PUT 은 감사 0 줄(새 action 없음 — 처분 Q2 (나)). 되돌림 0004 → 0003 은 고친
  값을 잃는다.
- 실행 묶음(RX1b carrier `service/actions/bundle.py`, 명령 `export_runs`·`import_runs`): 판·검토·표시를 싣는다. 표시는
  고침 칸 셋과 근거 고침(`evidence_removed`·`evidence_added`·`evidence_edited_at`)·재판단 칸(`evidence_basis_run_id`·
  `rejudge_run_ids` — 받는 쪽 새 실행 id 로 다시 잇는다)까지(GCB1, `MARC-ISSUE-616`). 사람 칸은 싣지 않고 때가 있는 칸만
  `--user`. 재판단 실행(`greenwash.rejudge@E0`)의 `fromRunId`(options·결과·judge 단계 data)도 새 원 실행 id 로 바꾼다.
  ★ 재판단 실행을 고르면 닫힘이 원 실행을 끌어오지만 반대로는 아니다(닫힘은 앞 실행만 따라간다 — core). 원 실행만
  고르고 그 표시가 묶음 밖 **done** 재판단 실행을 가리키면 내보내기를 거절한다(종료 1, 글에 원 실행 id 와 빠진 재판단
  실행 id — 기준 판단·count 가 바뀌므로). 창(`--module greenwash --from --to`)은 같은 모듈이라 기간 안이면 함께 잡힌다.
  **뺌**: 창·`--runs` 는 done 만 고르므로 failed·도는 중 재판단 실행은 실릴 길이 없다 — 그 id 는 내보낼 때
  `rejudge_run_ids` 에서 뺀다(다 빠지면 null). done 재판단의 count·기준 판단은 그대로이고, 받는 쪽의 마지막 상태 줄만 앞
  done 기준이 된다(감독 GCB1 §8 Q-B1 (가)+(나)).

## 엑셀 보고서

밴드 G1b-2a(`MARC-ENT-356` — `MARC-ENT-243` 갈음). `GET /greenwash/runs/{id}/report` 는 끝난 비 dry-run E0 실행
(`actions/report.E0_FLOW` = `flows.colab_e0.FLOW_ID`)의 결과에서 xlsx 한 파일을 늘 다시 짓는다(저장된 출력 파일은 읽지
않는다). `confirmed=true` 면 확정된 검토의 채택 문장만 싣고 「요약」을 그것으로 다시 센다(파트는 결과 `parts` 전부, 빈
파트 0 줄), 「설정」 끝에 판 줄. 「앞 버전 비교」 시트와 `compareBase` 쿼리는 없다(보내면 무시). 요약 파트 차례는 결과
`parts` 차례 — `run_results.body` 는 jsonb 라 `counts.byPart` 차례가 DB 왕복에서 바뀌어 build 앞에서 다시 놓는다.
200 마다 감사 download 한 줄(`greenwash_report_downloaded`, target `report`·실행 id·파일 이름, 확정본은 「· 확정본」) —
바이트를 지은 뒤·응답 앞, 거절·build 예외는 줄 0. 확정본의 등급·사유·수정 방향은 검토에서 고친 값(없으면 AI)이고
「문장」 끝에 칸 넷(고침·AI 등급·AI 사유·AI 수정 방향 — 고친 칸만 AI 값), 「요약」은 고친 등급으로 다시 세고 「설정」의
판 줄 앞에 「고친 문장」 줄(G1b-3). 미확정 보고서(`confirmed=false`)와 흐름 엑셀은 AI 값 그대로, 칸 넷 없음.
응답은 `X-Content-Type-Options: nosniff` 를 단다(G1b-2b, `MARC-ISSUE-255` — 문서 내려받기와 같은 꼴). `extraTerms` 칸이
없는 옛 꼴(G1c 앞) 결과는 추가 단어 없음으로 짓는다(build 앞의 사본에 `extraTerms: []` — 500 아님).

## AI 설정 판

밴드 G2c2(결정 `MARC-ENT-341`·`244`·`312`)에서 시작. 판 = 이름(`title`, AS3a-2) + 판정 기준표(greenwash.criteria@1,
15줄) + 판정 단계의 모델 설정(AS2b) + 프롬프트 넷의 글·칸 메모(없으면 코드 글 — AS3a-2) + 메모(0~200자). 의심 단어·처리
값은 판 밖(E0 상수 — AD-02 의 그 구성은 1차 읽기 전용).

- 표 `greenwash_ai_settings`: 회사별 **불변 행**(저장 = 새 행, 지우기·고쳐 쓰기 없음). 이름은 서버가 회사 안에서
  `v1`, `v2`, … 로 매기고 받은 `criteria.version` 을 덮는다. 회사마다 적용 판은 많아야 하나(부분 unique). 앱 역할의
  GRANT 는 SELECT·INSERT 와 칸 단위 `UPDATE (applied, applied_at)` 뿐 — 적용 바꾸기는 `QuerySet.update` 둘이다.
- 기본 판(코랩 원본, `colab-2026-01-15-v1`)은 표에 행이 없다. 적용 판이 없으면 곧 기본 판. 상태는 응답에서 센다:
  applied(지금) · past(적용했던) · testing(한 번도).
- **실행은 만들 때의 판을 박는다**: `versions = {aiSetting, evalPromptSha256, aiSettingId, modelSettingsSha256, flow}`(끼움의
  `versions_with` — 그 회사의 지금 적용 판, sha 는 만들 때 다시 지은 값). 실행기는 끼움의 `inputs_with` 로 **그 id 의 판**을
  읽어(그 뒤 적용을 바꿔도 만든 때의 판) 다시 지은 sha 가 다르거나 판이 없거나 지금 받기 규칙으로 다시 지을 수 없으면
  실행 실패(`error_code versions_mismatch` — core `RunVersionsMismatch`, 결정 `MARC-ENT-352`. 조용히 기본 판으로 가지
  않는다). `aiSettingId` 가 None 이거나 열쇠가 없으면(G1b 때 만든 실행) 기준표 없는 지금 길 —
  요청·결과가 기준표 이전과 바이트 같다.
- 실행기 쪽은 `core/flows/binding.py` 의 둘째 꼴 `RunFactsBinding`(`isinstance` 갈래 — 다른 끼움은 옛 꼴 그대로).
  끼움의 판 읽기 `store` 는 기본값 없이 받는다(`apps.py` 가 `RunSettingStore()` 를 꽂는다 — 권한 없는 입구).
- dry-run(서버는 돌지 않는다 — 비용 어림)은 엔진이 기본 프롬프트로 세므로, 기준표가 있으면 judge 가 판정 몫만
  `(고친 EVAL − 기본 EVAL) × eval 요청 수` 로 보정한다(`colab_e0.adjusted_dry_run`, 표지는 judge 산출 `eval_prompt_adjustment`
  — 결과 꼴 그대로).
- 감사: 저장 `ai_setting_created`·적용 `ai_setting_applied`(action `setting_change`, target_kind `ai_setting`), 업무 블록
  뒤. 같은 판 다시 적용·거절은 줄 0.
- 이어 돌기(X1b-2b)는 이어 돈 실행에 앞 실행의 `versions` 를 물려준다(지금 적용 판으로 다시 짓지 않음 — R4).
- **못 받는 저장 판**(밴드 G2c3 — 결정 `MARC-ENT-352`): 배포로 받기 규칙이 좁아져 저장 판이 지금 `accept_criteria` 에 맞지
  않으면 409 `AI_SETTING_UNUSABLE` 이 두 자리에서 난다 — 그 판이 적용된 회사의 `POST /runs`(끼움의 `versions_with` 가
  core `RunVersionsRejected` — 실행·단계 행 0, 감사 0)와 그 판의 `PUT …/applied`(쓰기·감사 0, 이미 적용된 그 판을 다시
  보내도). 글에는 판 이름만 싣는다(기준 글·회사 id 0). 출구: 기본 판으로 되돌리기(`{id: null}` — 늘 됨) 또는 기준표를
  고쳐 새로 저장해 적용. 목록·한 판 응답에는 막힘 표시가 없다(받기 규칙을 실제로 좁히는 밴드의 몫).
- **배포 때 진행 중 실행**(`MARC-ENT-352`): 판정 틀·`PROMPT_VERSION`·받기 규칙이 바뀌는 배포 뒤에는 그 전에 만든 실행이
  `failed`·`versions_mismatch` 로 끝난다(저장 판·기본 판 같게 — 만들 때의 sha 와 다르다). **models.json 의 경로→모델
  짝·모델 상한·판정 단계의 허용 경로·기본값이 바뀌는 배포도 같다**(모델 설정 sha — AS2b). 배포 전에 진행 중 그린워싱
  실행이 0 인지 보거나 끝날 때까지 기다린다. 그렇게 실패한 실행은 **새 실행**으로 다시 돌린다(이어 돌기는 앞 `versions` 를
  물려받아 또 실패한다). **프롬프트 글 받기 규칙(core 상한)이 좁아지는 배포도 같다**(AS3a-2). 그리고 AS3a-2 를 처음 올릴
  때 **새 웹 + 옛 워커**면 열쇠 `promptsSha256` 이 있는 실행을 옛 워커가 모르는 열쇠로 지나쳐 코드 글로 돈다(257-5 — 판정
  글을 고친 판은 기준표 sha 와 달라 `versions_mismatch`, 판정 글을 그대로 둔 판은 조용히 코드 글) — 워커를 먼저 올리거나
  그동안 실행 접수를 멈춘다. **G2d ③ 도 같다**: 새 웹 + 옛 워커면 열쇠 `termsSha256` 이 있는 실행을 옛 워커가 코드 목록
  (`GREEN_TERMS`)으로 센다(조용히) — 워커를 먼저 올린다. 단어 받기 규칙(`terms_e0` 상한)이 좁아지는 배포도 진행 중 실행은
  `versions_mismatch`.
- **프롬프트·모델 읽기**(밴드 AS2a — 결정 `MARC-ENT-350`·`353`): `…/default/prompt-model`·`…/{id}/prompt-model` 이 core 꼴
  `ai.prompt-model@1`(AS1)로 판정 단계 하나(`judge`)의 프롬프트 넷 전문·sha 와 모델 칸·고를 수 있는 경로를 준다. 단계
  명세·허용 경로(openai 둘)·프롬프트 표는 `flows/prompt_model_e0.py` 한 곳이고, eval 글은 실행과 같은 길(`eval_pack` +
  `judged_prompt_version(SCAN_CONFIG)`)로 지어 sha 가 그 판의 `evalPromptSha256` 과 같다. 모델 칸은 저장 판이면 그 판의
  저장 값(AS2b), 기본 판이면 명세의 기본값이고 `editable.model` 은 true. 못 받는 저장 판(기준표나 모델 설정)은 판 상세
  200 인데 이 경로만 409 `AI_SETTING_UNUSABLE`(모델 설정이면 모델 문장 — 둘 다 안 맞으면 기준표 문장, 차례는 적용과 같이
  기준표 → 모델). 모의 경로 0.
- **AI 설정 판의 프롬프트 칸**(밴드 AS3a-1 — 결정 `MARC-ENT-381`·`384`·`385`, 이슈 `MARC-ISSUE-257`): prompt-model 은
  `ai.prompt-model@3` 다(밴드 AP1b — 결정 `MARC-ENT-399`, 이슈 `MARC-ISSUE-280`: 모듈 선언 `prompt_model_e0.MODULE_SPEC`
  을 core `compose` 가 조립 — 모델 칸 `models[]`·프롬프트 묶음 `promptGroups[]`, 설정에서 빠진 고르지 않은 경로는 500 이
  아니라 `unavailableRoutes`). 칸 넷의 이름은 서버 글(문장 찾기·판정·수정 방향 다듬기·Low 문장 설명), 칸마다 `memo`(저장 글 없는
  판은 `DEFAULT_MEMOS`)·`defaultText`(엔진 기본 글 — 기준표로 지은 판정 글이 아니다, 웹은 이 글을 보내 되돌림)·`isDefault`·
  `outputSection`(기본 글의 마지막 `[출력(JSON` 부터 끝)·`outputKept`(절이 바이트 그대로 남았나 — false 는 경고, 저장은 안
  막음)와 판 밖 `limits`(core 받기 상한)·`fixed`(읽기 전용 코드 값 둘 — 파트 = `binding_e0.PARTS` × `colab_e0.PART_ORDER`,
  처리 값 다섯 = `colab_e0.scan_cfg()` 의 칸, `fixed_groups()` 가 부를 때 짓는다)를 싣는다. 프롬프트 글의 받기·sha·크기는
  core `check_prompts`·`prompts_sha256`·`prompts_size` 하나이고 그린워싱은 `prompt_model_e0.LAYOUT`(판정 단계 하나·칸 넷)만
  넘긴다. 저장(본문 `prompts`)·실행은 AS3a-2 — 이 밴드는 보기만이라 `editable.prompts` 는 false(AS3a-2 가 true).
- **판의 프롬프트 글·판 이름**(밴드 AS3a-2 — 결정 `MARC-ENT-381`·`384`·`387`, 이슈 `MARC-ISSUE-257`): **한 번 저장 = 판
  하나** — `POST` 본문 하나에 이름 `title`(strip 뒤 1~40자, 겹침 허용 — 판 번호 `name` 은 서버의 `v<n>` 그대로)·
  `criteria`(빠지거나 null 이면 기본 기준표)·`modelSettings`·`prompts`(ai.prompts@1, 빠지거나 null 이면 코드 글)·`memo` 를
  싣는다. 프롬프트만 따로 저장하는 경로는 없다. 받기 차례는 꼴(422) → 기준표 → 모델 → 프롬프트(400 `AI_PROMPT_*` 와
  `fields` `{"prompts.steps.<i>.prompts.<j>.text|memo": [문장]}`) — 하나라도 거절이면 행 0·감사 0. 칸 `prompts`(jsonb
  NULL)·`title`(varchar(40) NULL)은 마이그레이션 0005(CHECK 셋 — 크기 둘·이름 하나, 받기가 먼저 막는 마지막 그물). 저장 칸은
  받은 정규형(글 바이트 그대로·칸 메모 strip)이고 코드 글과 같은 글을 보내도 접지 않는다(NULL 은 「보내지 않음」뿐).
  `evalPromptSha256` 은 실제로 쓸 EVAL 의 sha — 저장 글이 있으면 그 글이고, 그때 기준표는 받기·저장만 되고 실행 글에 쓰이지
  않는다(373). 판 꼴은 `@2`(`title` — 옛 판 null, 화면은 「v<n>」만), 기본 판·목록 `default` 의 `title` 은 서버 글
  `DEFAULT_TITLE`(「기본 설정」). 적용·prompt-model·`POST /runs` 는 저장 글을 지금 받기로 다시 받아 안 맞으면 409
  `AI_SETTING_UNUSABLE`.
  실행(③): 저장 글 판으로 만든 실행만 `versions` 에 `promptsSha256`(core `prompts_sha256` — 메모는 품지 않음)을 싣고
  `evalPromptSha256` 은 저장 EVAL 글의 sha 다(코드 글 판·기본 판은 열쇠 없음 — versions 바이트 그대로). 워커의
  `inputs_with` 는 「저장 글 있음 ⇔ 열쇠 있음」을 모델 대조보다 먼저 보고(기본 판에 열쇠가 있어도 예외), 저장 글을 다시 받아
  두 sha 를 견준다 — 어긋나거나 거절이면 `versions_mismatch`(호출 0), 같으면 `inputs.prompts = colab_e0.pack_from(…)` 로
  judge 가 다리를 `with_pack(저장 묶음)` 으로 바꿔 낀다(넷 다 저장 글로 부른다 — 기준표 묶음보다 앞). 다리가 아닌 대화
  포트에 기본과 다른 묶음이면 쪽 루프 밖 `TypeError`, dry-run 에 저장 글이면 `ValueError`(서버 실행은 dry-run 이 아니다).
  감사 `changed_fields` 는 `criteria`·`memo`·`model_settings`·`prompts`. layout 은 `colab_e0.LAYOUT` 하나다
  (`prompt_model_e0.LAYOUT` 은 그것 — 워커의 `binding_e0` 는 `prompt_model_e0` 을 들이지 않는다).
- **판의 대상 단어**(밴드 G2d — 결정 `MARC-ENT-394`, 이슈 `MARC-ISSUE-246`): `POST` 본문 `terms`(`{text, enabled}` 목록,
  빠지거나 null 이면 코드 기본 목록 `GREEN_TERMS` 37)를 같은 한 번 저장에 싣는다. 판 「대상 단어」는 **의심 낱말 빈도 목록
  하나만** 바꾼다 — 판정할 문장을 고르는 환경 신호(`heuristics.DEFAULT_ENV_KEYWORDS`)는 코드 고정이고 실행 옵션
  `extraTerms` 만 닿는다(G1c 그대로). 받기는 `flows/terms_e0.accept_terms`(만들 때와 워커가 같은 함수): 꼴(422 — 목록
  1000·글 200·칸 빠짐·모르는 칸·bool 아닌 enabled, 짝 없는 서로게이트도 꼴이 먼저) → 기준표 → 모델 → 프롬프트 → 단어(400
  `TERMS_TEXT`(strip 뒤 1~30자·괄호·따옴표·제어·보이지 않는 글자 0·비교 키에 글자·숫자) · `TERMS_DUPLICATE`(비교 키
  `gw1.term_key` 겹침, fields 는 뒤 것) · `TERMS_COUNT`(켠 것·끈 것 합 100 넘음) · `TERMS_NONE_ENABLED`, `fields`
  `terms.<i>.text`·`terms`). 칸 `terms`(jsonb NULL, 마이그레이션 0006 — CHECK `octet_length(terms::text) <= 16384`, 받기
  최악 약 15,200 바이트)는 받은 정규형(text strip·받은 차례)이고 기본 목록과 같은 목록을 보내도 NULL 로 접지 않는다. 판 꼴
  `@3`(`terms`, 기본 판은 늘 null — 글자는 `GET /greenwash/terms/default`), 목록 `ai-settings@2` 그대로. 감사
  `changed_fields` 는 다섯(`… prompts`·`terms`). 적용은 단어를 지금 받기로 다시 받아 안 맞으면 409 `AI_SETTING_UNUSABLE`
  (prompt-model 은 단어를 보지 않는다).
  실행(③): 끼움의 `versions_with` 가 단어 칸 있는 판이면 다시 받아 `termsSha256 = terms_sha256(켠 낱말)` 을 박고(거절이면
  실행 만들기 409 — 차례 기준표 → 모델 → 프롬프트 → 단어), 칸 없는 판·기본 판은 열쇠 없음(versions 바이트 그대로).
  `inputs_with` 는 「칸 있음 ⇔ 열쇠 있음」(기본 판에 열쇠도)·다시 받기 거절·sha 다름이면 `versions_mismatch`(호출 0, 모델
  열쇠 없는 옛 실행 갈래도), 같으면 `inputs.terms = 켠 낱말` — **켠 낱말이 `GREEN_TERMS` 와 차례까지 같으면 None(접기)**:
  판 없는 실행과 결과·메시지·엑셀이 같다. 빈도 목록 = 판 켠 낱말(판 차례) 뒤에 `extraTerms` 가운데 비교 키가 판 낱말에 없는
  것(받은 차례 — 판에서 끈 기본 낱말도 extra 로 넣으면 센다). `extraTerms` 는 지금처럼 환경 신호에도 간다. 결과
  `result@1` 의 `terms`(NotRequired, extraTerms 바로 뒤 — 빈도에 센 낱말 전체)는 판 단어로 센 실행에만 있고, 엑셀 「설정」
  은 그때만 「추가 단어」 뒤에 「대상 단어」 줄. 빈도 표의 「추가」 표시는 늘 `GREEN_TERMS` 기준(W4). 기본 판·칸 없는 판의
  실행은 바닥 기준물 `tests/data/g2d-baseline/`(②-0)과 바이트까지 같다(`scripts/g2d_baseline.py --check`).
- **판의 모델 설정**(밴드 AS2b — 결정 `MARC-ENT-353`): 칸 `model_settings`(jsonb NOT NULL, 마이그레이션 0003 — 그 전 행은
  그때의 코드 값으로 채움)에 판정 단계의 모델 설정 정규형(`to_input(check_model_settings(…))` — null 0)을 둔다. `POST` 의
  `modelSettings` 가 빠지면 코드 값, 있으면 `prompt_model_e0.accept_model`(core 받기 한 겹)로 받는다 — 받기 거절 400
  `AI_MODEL_*`(NaN·Infinity 는 `AI_MODEL_TEMPERATURE_RANGE`), 꼴 틀림(`true`·`"5"`·`webSearch: 0` — core 입력 꼴이 strict)
  422, 둘 다 행 0·감사 0. **모델 설정만 바꿔도 새 판**이다(행 불변 — 칸 UPDATE 권한 없음). 판 응답에는 모델 칸이 없고
  prompt-model 로만 본다. 적용(`PUT …/applied`)도 저장 값을 지금 설정으로 다시 받아 안 맞으면 409.
  받기·sha 의 원천은 `selectors.RunModelSource` 하나다(저장·적용·조회·실행기가 같이 본다): 설정은 `LLM_MODELS_FILE` 이
  있으면 그 파일, 없으면 패키지 models.json(실행 클라이언트와 같은 셈), 명세는 `prompt_model_e0.STEPS`. 설정은 한 번 읽어
  프로세스 끝까지 쥔다 — **설정 파일을 바꾸면 웹·워커 둘 다 재시작**.
  적용(실행): 끼움의 `versions_with` 가 저장 값을 지금 설정으로 다시 받아 `modelSettingsSha256` 을 박고(거절이면 실행
  만들기 409), `inputs_with` 가 워커에서 다시 받아 거절이거나 sha 가 다르면 `versions_mismatch`(호출 0), 같으면 judge 의
  다리를 `with_model(경로, temperature, 출력 상한)` 으로 바꿔 낀다 — 받은 judge 단계가 기본값과 같으면 바꾸지 않는다
  (이행된 옛 행·기본값으로 저장한 판의 요청은 AS2b 앞과 바이트 같다). 열쇠가 없는 옛 실행은 모델 대조 없이 지금 길.
- 목록·적용 잠금은 기준표 칸을 읽지 않는다(머리 꼴 — G2c3). 목록 한 쪽은 문 하나다(나누면 READ COMMITTED 에서 한 응답
  안의 total·적용 판과 줄 상태가 어긋날 수 있다).

## G1b-2 로 넘긴 것

보고서는 G1b-2a 가 채웠다(위 「엑셀 보고서」). 문서 비교 `GET /greenwash/compare` 는 1차에 없다(`MARC-ENT-354` 1 — 501
그대로, 짝 계산 `outputs/compare.py` 는 둔다). 대체표현 잇기는 서버 길을 짓지 않는다(`MARC-ENT-354` 8). 좌표 엔진은
G1b-2b 가 꽂았다(`MARC-ISSUE-98` (4)): 끼움 `adapters()` 가 부를 때마다(실행의 시도마다) 새 `PdfiumCoordinates` 를 짓고,
locate 단계가 끝에(예외에도) 닫고 셈(`stats()` — 찾은 단·None 갈래·예외 종류·문서 연 횟수)을 단계 data 의 `stats` 에
싣는다. 실행기는 어댑터를 닫지 않는다(`runs/tasks.py`). pdfium 은 스레드에 안전하지 않다 — 인스턴스를 나누지 않는다.
dry-run 은 닫기만(data 그대로). 이어 돌기(`resumeFromRunId`)는 끝난 locate 단계의 data(`stats` 포함)를 그대로 옮기고
좌표를 다시 부르지 않는다. 목록 줄의 `reportYear`·`previousDocumentId` 는 문서 칸(`PATCH /documents/{id}`, G1b-2a),
`pageCount` 는 그대로 실행 결과에서. 목록 줄은 G1b-2b 부터 묶음 읽기다(`MARC-ISSUE-219`): 단계·결과·문서를 runs 의
`step_rows_of`·`results_of`, core 의 `documents_of` 로 한 번씩 읽어 쿼리 수가 실행 수와 무관한 상수(9)다. 실행은 새 것
먼저 `RUNS_MAX`(1000)까지 — 넘으면 `truncated: true`(페이지네이션은 후속). 실행 줄의 `failedPageCount` 는 끝난 실행
결과 `candidateStats.failedPages` 의 수(같은 묶음 본문 — 쿼리 더 없음), dry-run·끝나지 않음·결과 없음은 null.

## 규칙 세 줄

1. **엔진은 계약을 모른다** — `[importlinter:contract:greenwash-engine-not-contracts]`(엔진 → 계약·출력·흐름·표면 금지).
2. **계약은 엔진을 모른다** — `[importlinter:contract:greenwash-contracts-not-engine]`(계약 → 엔진·흐름·출력·표면 금지).
3. **둘을 잇는 것은 흐름뿐이다** — 위 둘에 `greenwash-tools-know-no-axis`(도구 → 엔진·계약·출력·흐름 금지)와
   `greenwash-outputs-not-engine`(출력 → 엔진·흐름 금지)를 더해, 엔진과 계약을 둘 다 들일 수 있는 자리가 `flows/`(와
   표면)만 남는다. 넷 다 직접 import 만 본다(`allow_indirect_imports = True`) — 흐름을 거친 간접 길은 막지 않는다.
   무효 조건: 표면(`service`·`api.py`)이 엔진을 직접 들이는 것은 계약이 없어 막히지 않는다.

## 읽는 차례

`flows/registration.py` → `flows/colab_e0.py`(단계 여섯) → `contracts/shapes.py` → `engines/e0/checker.py` → `tools/`.
`flows/rewrite_r1.py`(대체표현)는 E0 뒤에 읽는다.

## 다음 판 넣는 법

- **엔진**: `engines/e1/` 를 새로 복사한다. `engines/e0/` 를 고치지 않는다. AST 고정 파일을 판마다 하나 둔다.
- **흐름**: `flows/colab_e1.py` 를 쓴다. 자기 `GreenwashAdapters`·`LlmChatBridge`(같은 이름, 다른 모듈)·`PDF_TEXT`·
  `CHAT_ROUTE` 를 둔다. 노트북 프롬프트 넷 검사처럼 판의 프롬프트를 아는 판단은 그 판의 흐름에 두고,
  `tools/llm_bridge.LlmTextCall` 은 「프롬프트 id + system·user 글 → core.llm」만 안다.
- **등록**: `registration.FLOWS` 에 더하고 `DEFAULTS` 한 줄을 바꾼다.
- **시험**: `tests/engines/e1/` 에 둔다(자리 규칙 `scripts/check_test_layout.py`).
- **계약 판**: `@n` 은 엔진 판과 따로 움직인다. 꼴을 바꾸면 `contracts/` 에 새 판 꼴을 만들고 고정 스키마를 더한다.
- **PDF 읽개**: 판이 고른다(`colab_e0.PDF_TEXT`). 읽개를 바꾸는 판은 `tools/coordinates.py` 의 찾기 상수
  (`HEAD_KEEP_MIN`·`READBACK_EXTRA_MAX`·`MAX_SENTENCE_CHARS`·`MAX_LINES`)를 다시 잰다(`MARC-ENT-267`).
- **엑셀의 추가 단어**: `outputs/xlsx.build(result, *, added_terms, adopted=None)` 는 엔진을 모른다. 흐름이
  `frequency_extras(result["extraTerms"])` 로 지어 넘긴다.

## 프롬프트 두 자리

- 글의 정본은 `engines/e0/prompts.py`(노트북 글, AST 고정)다. 저장 글이 있는 AI 설정 판(AS3a-2)의 실행은 그 판의
  글 넷을 쓴다(정본은 판 행의 `prompts` 칸 — 엔진 글은 그대로, judge 가 `with_pack` 으로 갈아 끼운다. 「AI 설정 판」).
- `prompts/<종류>/1.md` 는 core.llm 의 봉투다: 넷 다 `=== system ===\n{{system}}\n=== user ===\n{{user}}` 이고 글은
  변수로 넘긴다(노트북 글에 `{{` 가 있다). 자리는 core 규약(`esgapi/<모듈>/prompts/<이름>/<판>.md`)이 정해 옮길 수 없다.
- 한계(E0 의 봉투 넷에만): 호출 기록의 프롬프트 id(`greenwash/detect@1` 등)로는 E0·E1 을 가르지 못한다. 글 안의
  `[PromptVersion: …]` 와 태그로 가른다.
- rewrite(`greenwash/rewrite@4`)의 글은 템플릿 본문이 정본이다(글에 `{{` 가 없다. 초안 `rewrite-prompt-draft-4.md` 그대로,
  `MARC-ENT-309`. 판 3 `rewrite@3` 은 `rewrite-prompt-draft-3.md`, `MARC-ENT-288`. 판 2 `rewrite@2` 는 `rewrite-prompt-draft-2.md`, `MARC-ENT-279`. 판 1 `rewrite@1` 은
  `rewrite-prompt-draft-1.md`, `MARC-ENT-278`). 바이트를 `tests/flows/test_rewrite_r1.py`
  가 sha256 으로 고정하고, 호출 기록의 템플릿 sha256 이 글을 가른다.
- 판정(EVAL) 글은 실행마다 고정 틀(`flows/criteria_e0.py`) + 판정 기준표(`greenwash.criteria@1`, 15줄 — 켜기·끄기, 기준
  글, 대상 키워드 낱말)로 조립한다(밴드 G2c-1, `MARC-ENT-312`·`MARC-ENT-329`). 기본 판 기준표의 조립 글은 엔진 글과
  바이트가 같다(`tests/flows/test_criteria_e0.py` 의 `test_the_default_criteria_build_the_engine_text_byte_for_byte`).
  기준표가 없는 실행은 지금 길 그대로다(`test_criteria_flow.py` — 골든 메시지·대조 B). 어느 기준표로 판정했는지는 실행
  판 묶음의 `aiSetting`(과 `evalPromptSha256`)으로 잇는다 — `colab_e0.run_versions`(판 글자를 judge 와 같은 길로),
  부르는 자리는 그린워싱 끼움(G1b).

## 낡은 경로가 남는 자리

옮기기 전 경로를 부르는 글이 남아 있다. 고치면 고정 스키마·`generated/openapi.json` 이 바뀌어 밴드 GX1 에서 남겼다.
GX1 이 같은 까닭(rename 유사도)으로 남긴 모듈 머리 글(`contracts/wire.py`·`contracts/terms_shapes.py`·
`engines/e0/gw1.py`·`engines/e0/result.py`·`tools/textnorm.py`)은 밴드 GX2 가 지금 자리로 고쳤다.

1. 고정 스키마 `tests/data/flow-shapes/terms/greenwash.terms-default.schema.json` 과 `openapi.json` 의 description
   `calc/wordcount.normalize_term`(원천 `contracts/terms_shapes.py` 의 클래스 docstring).
2. `openapi.json` 의 description `flows/review_shapes.py`(원천 `service/apis/greenwash.py` 의 review 경로 docstring).
   `contracts/shapes.py` 의 `ExtraTerms` 별칭 docstring `flows/colab.accept_extra_terms` 는 밴드 GX1 발주서 §1-3(스키마·
   OpenAPI description 이 될 수 있는 클래스·칸·별칭 docstring 은 0줄)을 따라 남겼다. 이 글은 `generated/openapi.json`·
   고정 스키마(`tests/data/`)에는 나오지 않는다(GX1 HEAD 에서 grep 0) — 고쳐도 계약 바이트는 바뀌지 않았을 것이다.

무효 조건: 계약 판을 올리는 밴드가 1·2 의 글을 고치면 그 줄을 지운다.
