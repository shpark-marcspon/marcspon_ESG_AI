# dataverify 프롬프트 — 출처

core.llm 템플릿 셋은 봉투만 갖는다: `=== system ===\n{{system}}\n=== user ===\n{{user}}\n`(greenwash `prompts/detect/1.md` 꼴).
글의 정본은 `engines/colab_156/prompts.py` 의 템플릿 상수 여섯(`DEFAULT_TEXTS` — 자리 글자 `{기업명}` 등, AI 설정 판이
갈아 끼움, 밴드 DVA1)과 그것을 끼우는 함수 셋이고, 흐름이 그 글을 변수 `system`·`user` 로 넘긴다
(core `parse_template` 이 구획마다 strip 하므로 글을 템플릿 몸에 두면 앞뒤 빈 줄이 사라진다 — 봉투는 넘긴 글을
한 바이트도 바꾸지 않는다. `tests/engines/colab_156/test_prompts.py` 가 잰다).

| 프롬프트 id | 함수 | 원천(받은 데이터 검증 코랩, `MARC-ENT-156` 읽기판) | 블록 sha256(읽기판 줄을 `\n` 으로 이은 것) |
|---|---|---|---|
| `dataverify/plan@1` | `plan_prompt` | 셀 10(코랩1번 계산 Plan) R/835-910 | `e1c73fd0c0400f7103264b0010e734cd1dbdc01c6d2daaf3e590f870af08bd0a` |
| `dataverify/review@1` | `review_prompt` | 셀 14(코랩2번 계산 검토) R/1064-1191 | `1dbdd55392a00b16f8b3893944af146355c84bc688063ee9bbf214f93ca3b406` |
| `dataverify/insight@1` | `insight_prompt` | 셀 18(코랩3번 인사이트) R/1333-1433 | `985c0e1a6534bdc6f66038d90d899801a41367754241171b378c7367bd16ea2f` |

바꾼 자리(코랩과 다른 자리):

- 셀 전역이던 값을 인자로: USER 의 기업 정보 네 줄(`[기업명]`·`[SASB 산업분류]`·`[주요 중대토픽(Material Topics)]`·
  `[Reporting year]` — 중대토픽은 목록을 받아 「, 」로 잇는다), `SET_MAX_STEPS`(Plan·인사이트 12, 검토 `len(HINTS)*3`),
  `HINTS`, `data_split`(받은 dict 를 `json.dumps(…, ensure_ascii=False, separators=(',', ':'))` 로 — 코랩 그대로).
- 셀 14 SYSTEM 의 JSON 예시 `"values"` 의 수를 지어낸 1200·1300·1400 으로(실재 기업 값일 수 있어서 — 발주서 §1-3).
- 그 밖의 글자(셀 10 SYSTEM 의 「SASB 산업 특성(Engineering & Construction Services)」 박힌 글, 셀 14 의
  `CO2 = 123.4, CH4 = 5.6, N2O = 0.7, 합계(Scope 1) = 129.7` 예시 등)는 그대로다.

- `prompts.py` 의 f-문자열 `{…}` 표현식 안 코드는 ruff format 이 다듬었다(`{SET_MAX_STEPS-4}` → `{SET_MAX_STEPS - 4}`,
  `separators=(',', ':')` → `separators=(",", ":")`). 나오는 글자는 같다(시험은 렌더 결과
  sha256 을 고정하고, 코랩과의 바이트 견줌은 esg-lab `py/dvcolab` 이 한다 — `MARC-ENT-310`).

배포(`MARC-ENT-352` 2번): 엔진 글·받기 규칙·models.json 이 바뀌는 배포 전에 진행 중 데이터 검증 실행 0 을 확인한다(이 밴드
— DVA1 — 부터 워커가 판을 다시 지어 sha 가 다르면 `versions_mismatch` 로 끝난다. 실패한 실행은 이어 돌기가 아니라 새 실행으로).

무효 조건: 읽기판이 다시 뽑히면(원본 sha1 이 바뀌면) 위 sha256 과 줄 번호를 다시 잰다.
