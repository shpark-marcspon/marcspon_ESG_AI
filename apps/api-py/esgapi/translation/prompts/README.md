# translation 프롬프트 — 출처

core.llm 템플릿은 봉투만 갖는다: `=== system ===\n{{system}}\n=== user ===\n{{user}}\n`(@1 — greenwash `prompts/detect/1.md`
꼴). 쪽 system 을 싣는 일곱 자리(`cell`·`table-batch`·`section`·`polish`·`editorial-qa`·`glossary-repair`·`korean-repair`)는
@2 `=== system cache ===\n{{system}}\n=== user ===\n{{user}}\n` 를 쓴다 — 같은 글에 캐시 표시만 더한다(core 가 system 구획에
`cache` 를 싣고 anthropic 어댑터가 `cache_control` 을 단다, MARC-ISSUE-213). 검수·자동수정 셋은 @1. @1 파일은 남긴다. 자리마다
어느 판을 쓰는지는 다리의 `PROMPT_VERSIONS` 가 정본이고, 실행의 `settings.promptIds` 가 그 판을 싣는다. 글의 정본은 `engines/colab_158/prompts.py` 이고, 엔진이 지은 글을 다리(`tools/llm_bridge.py`)가 변수 `system`·`user` 로
넘긴다(core `parse_template` 이 구획마다 strip 하므로 글을 템플릿 몸에 두면 앞뒤 빈 줄이 사라진다 — 봉투는 넘긴 글을
한 바이트도 바꾸지 않는다. `tests/engines/colab_158/test_prompts.py` 가 잰다).

원천: 받은 영문번역 코랩 보고서_AI번역_v3_1(`MARC-ENT-158`)의 읽기판(원본 sha1 `b7166107d162a7044159c618c31e3d93e28118c0`).
`R/<줄>` 은 그 읽기판의 줄이다.

## 자리 열(LLM 을 부르는 자리 — 코랩 호출 자리와 하나씩)

판: 아래 표의 `@1` 중 일곱(`review`·`autofix`·`autofix-korean` 밖)은 실행에서 `@2`(캐시 봉투)로 부른다.

| 프롬프트 id | 코랩 호출 자리 | system | user | max_tokens | 역할 |
|---|---|---|---|---|---|
| `translation/cell@1` | `_single_translate_fragment` R/2253 | 쪽 system(`page_system_prompt`) | `cell_user` R/2257 | 1024 | translate |
| `translation/table-batch@1` | `_batch_translate_json` R/2286 | 쪽 system + `TABLE_TRANSLATION_RULES` | `table_batch_user` R/2300 | 8192 | translate |
| `translation/section@1` | `_translate_general_section` R/2344 | 쪽 system | `section_user` R/2348 | 4096 | translate |
| `translation/polish@1` | `_editorial_polish_once` R/2514 | `polish_system` R/2509 | `polish_user` R/2518 | 4096 | translate |
| `translation/editorial-qa@1` | `_generic_editorial_quality_gate` R/2659 | `editorial_qa_system` R/2654 | `editorial_qa_user` R/2663 | 4096 | translate |
| `translation/glossary-repair@1` | `_repair_glossary_violations_once` R/3005 | 쪽 system | `glossary_repair_user` R/3009 | 4096 | translate |
| `translation/korean-repair@1` | `_repair_untranslated_korean_once` R/3131 | 쪽 system + `CRITICAL_REPAIR_MODE` | `korean_repair_user` R/3141 | 4096 | translate |
| `translation/review@1` | `review_page_pair` R/5325 | `QA_SYSTEM_PROMPT` 그대로 | `review_user` R/5277 | 4096 | review |
| `translation/autofix@1` | `_repair_page_with_part_qa_issues` R/6707 | `autofix_system` R/6665 | `autofix_user` R/6684 | 4096 | translate |
| `translation/autofix-korean@1` | `_repair_remaining_korean_page_once` R/6752 | `autofix_korean_system` R/6755 | `autofix_korean_user` R/6765 | 4096 | translate |

쪽 system = `build_system_prompt(회사 문체 + "\n\n" + TERMINOLOGY_NOTE + "\n\n" + 문체 A·B)`(R/3280-3286 — 셀 42·44 의 조립).

## 평 문자열 상수 열다섯 — sha256

sha256 = 읽기판의 그 셀 코드를 `ast.parse` 해 `NAME = """…"""` 대입 값을 `ast.literal_eval` 한 글의 UTF-8 sha256 이다(소스 줄을
이은 블록이 아니다 — 값은 `"""` 뒤 앞 줄바꿈을 품는다). **이 값은 읽기판에서 잰 것이다**(엔진 상수에서 잰 값이 아니다).
`apps/api-py/scripts/section4-TR1a.sh` 16단계가 실행 때 읽기판을 다시 읽어 읽기판 값·엔진 상수·이 표 셋이 같은지 본다.
바꾼 자리(이름 지움 등): 없음 — 열다섯 안에 실재 기업 이름·바꿈 표지가 없다(16단계·13단계).

| 상수 | 읽기판 자리 | 글자 수 | sha256 |
|---|---|---|---|
| `TERMINOLOGY_CONSISTENCY_PROMPT` | 셀 30 R/1153-1161 | 537 | `605b9de8ace60e6c7dc2a59470bb37d1d4c863675f5bfa5e9c0ca527082fe2b9` |
| `SUBJECT_PRONOUN_PROMPT` | 셀 31 R/1167-1188 | 1004 | `5b094ae60c8cd7e3df2175de7bc18adcf9c8c37d62f910d2452b8ffc31965a02` |
| `NUMBER_UNIT_PROMPT` | 셀 32 R/1198-1215 | 684 | `7e6740100efc07038356b2ff4061d2a327a1d30a3e98d33e4c1cc15f4557f24e` |
| `FRAGMENTARY_CONTENT_PROMPT` | 셀 33 R/1225-1258 | 1146 | `77a9dc10446e4f32dd2746b3eb0dcf2c2b91ea16b710ab7e70933928eae95436` |
| `OFFICIAL_REPORT_STYLE_PROMPT` | 셀 34 R/1268-1295 | 1414 | `59c24f56b54baaf67679a90440a5c908759daa8f063ab711a24a6623c584af4d` |
| `LEXICAL_GUARDRAILS_PROMPT` | 셀 34 R/1298-1334 | 1731 | `00a364817881d8a6a841a9536d4d320a050ac259193897d798f827137f837406` |
| `ANTI_MACHINE_TRANSLATION_PROMPT` | 셀 34 R/1337-1352 | 662 | `b759ff2a14b7895387a2384b5903c358545867c9df9818ed537c4b9179a28a5b` |
| `BILINGUAL_EDITORIAL_POLISH_PROMPT` | 셀 34 R/1355-1380 | 1295 | `e40b1a615800f44a39670afb8643414cff6f353939c9ee58a9a1d2b316fec7e0` |
| `GENERIC_EDITORIAL_QA_PROMPT` | 셀 34 R/1382-1432 | 1872 | `d33ef4b1ccb8d449fb069e8e598911ee5229f62144c5b26ed19df3e113250882` |
| `CEO_MESSAGE_TONE` | 셀 36 R/1518-1645 | 4812 | `70862462a9fbc458e149a08ec0647868fb32982da77847a851b6ba2dd19fc0c3` |
| `STORY_TONE` | 셀 36 R/1651-1722 | 2629 | `5a8d0a0bbbedd0055d84fd0b1cad37402d1724fd80df6e5ac12a329fcb60e57c` |
| `GENERAL_TONE` | 셀 36 R/1728-1807 | 2776 | `541cb20fc769b651db61c9a50815ae1f34ea225ccce483c6b40d6e8c088bbda8` |
| `STYLE_A_PROMPT` | 셀 41 R/1869-1876 | 335 | `c13c619a9d5b1777e7bd96670348ac8ae2a198c7f1b3e4f4ec9a5cfd2be3b903` |
| `STYLE_B_PROMPT` | 셀 41 R/1879-1896 | 864 | `5d81ea4f0031627b76263eb5f1414de19b30ada10f7c5183654c17e51eda7381` |
| `QA_SYSTEM_PROMPT` | 셀 60 R/5385-5432 | 2732 | `fadc5384d50f8f6156503d06363e78203a76f722be63b6271989561e5d88a9b1` |

## 함수 안의 평 문자열 일곱 — sha256(같은 정의, 16단계 밖 · 참고)

코랩은 함수 안의 지역 글자로 두었다 — 엔진은 같은 값을 모듈 상수로 둔다(이름은 엔진이 붙임).

| 상수 | 읽기판 자리 | 글자 수 | sha256 |
|---|---|---|---|
| `TERMINOLOGY_NOTE` | 셀 46 R/3257-3277 | 1721 | `015e4dbfeccf47419c349c4f5e685ac7d47c3ae332751977c1aba13ac61a8786` |
| `TABLE_TRANSLATION_RULES` | 셀 46 R/2289-2299 | 408 | `525e07f97b9aa87799cb67f1daf1baa42d3b093dc5e291d362b3cb7472712860` |
| `GLOSSARY_REPAIR_TABLE_RULE` | 셀 46 R/2994-2999 | 232 | `91c276fa1f20b384b68c28229c68a2c146fd5183160e334c492183e0e045bf8b` |
| `GLOSSARY_REPAIR_STRUCTURE_RULE` | 셀 46 R/2999-3003 | 207 | `e49898ea9c2460fa851e923a5924e5d2a8c4f4c489bf7744b5952b165c27fdc9` |
| `KOREAN_REPAIR_TABLE_RULE` | 셀 46 R/3118-3124 | 237 | `3ed714abef3a94c603251c037889df12c5323e2f2432d6a306e53d6065d8f8d1` |
| `KOREAN_REPAIR_STRUCTURE_RULE` | 셀 46 R/3124-3129 | 251 | `08f93d24869e6b32c1cec3028238cb85308077722995a2c427d88f8252a44878` |
| `CRITICAL_REPAIR_MODE` | 셀 46 R/3134-3140 | 206 | `c9a43bce307473092f626e883d9484f479f602e831269c97e1daba846340f3e2` |

## f-문자열 자리 — 러너 손셈(TR1-o 전 미검)

f-문자열은 `literal_eval` 이 안 된다. 엔진은 읽기판의 f-문자열 소스 조각을 글자째 옮겨 셀 전역이던 이름을 인자로 받는다.
같은 값을 넣었을 때 같은 글인지는 코랩과의 대조 도구(esg-lab TR1-o, `MARC-ENT-311`)가 잰다. 자리: `cell_user` R/2257,
`table_batch_user` R/2300, `section_user` R/2348, `polish_user` R/2518, `editorial_qa_user` R/2663, `glossary_repair_user`
R/3009, `korean_repair_user` R/3141, `review_user` R/5277, `autofix_system` R/6665, `autofix_user` R/6684,
`autofix_korean_system` R/6755, `autofix_korean_user` R/6765, `build_company_style_prompt` R/1975(셀 42), `base_system_prompt`
R/2034(셀 44 `BASE_SYSTEM_PROMPT`).

## 바꾼 자리(코랩과 다른 자리)

- 셀 전역이던 값을 인자로: `COMPANY_NAME`·`PREFERRED_SUBJECT`·`INDUSTRY_STANDARDS`(입력 company), `CURRENT_PART`(입력 part),
  `PEER_GROUP_STYLE_PROMPT`·`USE_PEER_GROUP_STYLE`(입력 peerGroupStyle — 없으면 null), 각 함수의 지역 이름.
- `BASE_SYSTEM_PROMPT` 는 함수 `base_system_prompt(industry_standards)` — 코랩은 셀 44 실행 때 `INDUSTRY_STANDARDS` 를 박는다.
- 셀 42 의 `"X" in globals()` 검사는 인자 유무로. `REFERENCE_CONTEXT` 는 늘 빈 글(참고 URL 긁기 0 — 코랩 기본
  `REFERENCE_URLS = []` 과 같은 결과).
- f-문자열 `{…}` 표현식 안의 따옴표는 ruff format 이 `'` → `"` 로 다듬었다. 나오는 글자는 같다.
- 옮기지 않은 것: `PEER_GROUP_STYLE_PROMPT` 의 코랩 값(고객사 맞춤 글 — 입력), `FIXED_TERMINOLOGY`(코랩에서 주석 처리 —
  「Fixed terminology …:」 머리 뒤가 비는 것은 그대로, W6).

무효 조건: 읽기판이 다시 뽑히면(원본 sha1 이 바뀌면) 위 sha256 과 줄 번호를 다시 잰다.
