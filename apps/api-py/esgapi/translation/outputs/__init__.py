"""코랩 판 colab_158 의 Word(밴드 TR1b). 결과(또는 코랩과 같은 원시 입력)에서 Word 바이트를 짓는다 — 파일·이름 짓기 0.

출처: 받은 영문번역 코랩 보고서_AI번역_v3_1(MARC-ENT-158)의 읽기판
`received-derived/2026-10-15/영문번역 코랩/보고서_AI번역_v3_1.md`. 코드의 `R/<줄>` 은 그 읽기판의 줄이다. 서식 상수·글
규칙은 코랩대로(MARC-ENT-297 — 약점 포함). 판이 바뀌면 이 파일들을 고치지 않고 새 파일을 짓는다.

python-docx 를 import 하는 것은 docx_* 파일과 readback 뿐이다(tests/test_docx_imports.py). 엔진에서 아는 것은
`engines.colab_158.review_rules` 하나(tests/test_axes.py).

코랩 셀 → 이 꾸러미:

| 셀 | 무엇 | 파일 |
|---|---|---|
| 54·55·67 | 병기 txt → Word(`translated_to_docx` — 함수 24) | docx_bilingual.py |
| (54·63 의 `except`) | 짓다 실패한 갈래 | failures.py |
| 62(도우미 일곱)·63(v2) | 검수 Word(`build_qa_docx` v2 — 셀 62 의 v1 둘은 셀 63 이 덮어 옮기지 않음) | docx_qa.py |
| 55·65·67(고르기) | 결과 → 지을 Word·안 지은 까닭(처분 ⑨) | files.py |
| — | Word 바이트 → 읽기 JSON(대조·시험의 정본 하나) | readback.py |
| — | 대조 명령(TR1-o — 코랩 원시 입력 → Word + 읽기 JSON) | word_dump.py |
"""
