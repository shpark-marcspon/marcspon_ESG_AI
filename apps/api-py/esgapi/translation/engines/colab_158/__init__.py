"""영문번역 코랩 엔진 판 colab_158(밴드 TR1a). 받은 코랩을 코랩대로 옮긴다 — 약점까지(MARC-ENT-297).

출처: 받은 영문번역 코랩 보고서_AI번역_v3_1(MARC-ENT-158)의 읽기판
`received-derived/2026-10-15/영문번역 코랩/보고서_AI번역_v3_1.md`(원본 sha1 b7166107d162a7044159c618c31e3d93e28118c0,
2026-10-15 뽑음). 코드의 `R/<줄>` 은 그 읽기판의 줄이다. 읽기판이 다시 뽑히면 줄 번호와 프롬프트 sha 를 다시 잰다.

이 판은 고치지 않는다 — 다음 판은 `engines/<판>/` 을 새로 짓는다(MARC-ENT-270). 순수하다: 파일·시계·난수·네트워크·
Django·pydantic·core·계약·도구를 import 하지 않는다(tests/engines/colab_158/test_purity.py). LLM 은 ports.py 로만.

코랩 셀 → 이 파일:

| 셀 | 무엇 | 파일 |
|---|---|---|
| 7 | 구조 태그 복원, Word 표 칸 → pipe 표(글 몫), txt·md 갈래 | structured.py |
| 14·15·57 | 용어집 접기·정확 매칭·결정적 위반 검사·반영 검사 | glossary.py |
| 17·18 | `[PAGE n]` 나누기·같은 쪽 합치기(파일 대신 글) | pages.py |
| 46(표) | 셀 46 판 표 도우미·느슨한 JSON·표 조각 모으기·재조립 | tables.py |
| 46(판정) | 상수·한국어 잔존·태그·pipe 시그니처·제목 본문 가르기·쪽 게이트·must_apply·구획 | gates.py |
| 52 | 국문 병기 | bilingual.py |
| 58·65·67(결정적) | 병기 걷기·이슈 거름·쪽 내용 고르기·설명문 걷기·직접 치환 | review_rules.py |
| 30~44·46·58·60·67(글) | 프롬프트 상수·조립 함수·자리마다 user 글 함수 | prompts.py |
| — | LLM 포트(엔진의 바깥 하나) | ports.py |
| 46 | 칸·표 묶음·구획 번역, 윤문, 범용 QA, 용어집·한국어 게이트, 쪽 번역(A/B) | translate.py |
| 58 | `review_page_pair` | review.py |
| 67 | 이슈 기반 자동수정 | autofix.py |
| 7·49·52·57·65·67 | 흐름 몸(파일 왕복 그대로) → `TranslationRun` | pipeline.py · records.py |
| 50 | 실패 쪽만 다시(`retry` — 고른 쪽 번역 뒤 셀 52~67) | pipeline.py |
| (49·46·65·67 의 호출 자리) | 호출 계획 — 입력 → 부를 수 있는 호출의 위끝(처분 ⑬, 공급사 0) | plan.py |

마지막 정의가 이긴다: `build_glossary_text` 는 셀 11(R/335)을 셀 15(R/487)가 덮는다. `_escape_md_cell` 은 판이 둘이다 —
셀 7 판(R/185, 연속 줄바꿈·빈칸 접음)은 structured.escape_md_cell_docx(docx 읽기), 셀 46 판(R/2164, 접지 않음)은
tables.escape_md_cell(표 재조립). 셀 62 의 QA Word 함수는 셀 63 이 덮는다(TR1b).
"""
