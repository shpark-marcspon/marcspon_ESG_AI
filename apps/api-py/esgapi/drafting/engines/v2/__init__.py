"""원고작성 엔진 v2(밴드 RP2b, 결정 MARC-ENT-514 2번): 문장 나누기(sentences) · 블록 표지 재료(material) · S3 답 다듬기
(answers) · 블록·문장 출처 검사(checks) · 출처 상자(places) · draft 글과 표지 규칙(texts). S2(쪽 → 잎)는 v1 의 것을
그대로 쓴다(pages·mapping·prompts.outline_lines·render) — 호출 글 짓기는 v2 자리 `{페이지 글}` 을 끼우는
prompts(RPA4). 표준 라이브러리 + esgapi.drafting.engines.v1 만 — 뷰는 덕 타이핑."""
