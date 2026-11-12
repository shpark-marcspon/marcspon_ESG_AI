# AP1b ①-0 바닥 기준물

바닥 main `57f8adb4` 코드로 `scripts/ap1b_baseline.py` 가 뽑은 갈래 아홉(짓는 함수는 `tests/flows/ap1b_baseline.py`, 판 고정값은 `g2d-baseline/fixtures.json`). 그린워싱 prompt-model·versions 를 core 부품(`compose`·`ai_versions`)으로 갈아탄 뒤에도 versions 는 이것과 바이트(열쇠 차례째)가 같아야 하고, @3 몸은 @2 몸과 뜻이 같아야 한다(밴드 AP1b, `MARC-ENT-399`). 파일은 고치지 않고 `--check` 로 대조한다.

- `versions-<갈래>.json` = 끼움 `versions_with` 의 dict. **v1~v3 = `g2d-baseline` a~c 의 versions 와 같다**(같은 판·같은 길).
- `prompt-model-v2-<갈래>.json` = BASE `prompt_model` 의 `ai.prompt-model@2` 몸.
- `--check`: v1~v6 은 지금 코드로 다시 지어 바이트 대조, p1~p3 는 파일 sha256 만 아래 표와 대조.
- **p1~p3 는 다시 뽑지 않는다** — models.json·엔진 글이 바뀌어 `test_prompt_model_e0_v3.py` 의 뜻 같음 시험(3-3-1)이 빨개지면, 그 밴드가 p1~p3 와 그 시험을 지우고(AP1c 앞당김) AP1b 보고(`band-reports/AP1b.md`)의 표를 인용한다.
- GPW2(sid:MARC-TICK-389)에서 p1~p3 의 label 글만 고침(「쪽당 후보 문장」→「페이지당 후보 문장」, 「쪽 글자」→「페이지 글자」) — 뜻 같음 시험 유지, 감독 판단 10-29. 아래 표의 p1~p3 sha 는 고친 뒤 값.

| 파일 | sha256 | 갈래 |
|---|---|---|
| `versions-v1-default.json` | `eb6c3c8e43460bb0ee2fa0c078c1c146f9dc733cfa2dff49caf0fd4dd5c29aaf` | 기본 판 |
| `versions-v2-saved-code-text.json` | `d1b7b75b322e22295659c6e2c91c3c2dffbd363225ad1151eb874d6fe4e07887` | 저장 판·코드 글·단어 칸 없음 |
| `versions-v3-saved-text.json` | `4fd5012059d5cb98b047899a44cc5d8daff8c2560f13237a58fed7f6e05e3e6e` | 저장 글 |
| `versions-v4-saved-terms.json` | `a936ca05f8fadc92096ded9cc754856d4d41d6acab50c8a4b530d752ca20272e` | 단어 칸(켠 낱말 ≠ 기본) |
| `versions-v5-saved-text-terms.json` | `65bc2029d770f8e8358be13d6b20702986616b8a57e6914272de7191e36cc64b` | 저장 글 + 단어 칸 |
| `versions-v6-saved-terms-folded.json` | `3b2f771498e7794c55bad7da9842a4bc65eb386b425bab5d92880acc6591d409` | 단어 칸 = 기본 목록(접기) |
| `prompt-model-v2-p1-default.json` | `107d5946ed9e32008a08535161c522d26f3d401aa5cb9f2dc79d22361774b58f` | 기본 판 |
| `prompt-model-v2-p2-saved-model.json` | `1fe10890517139a7fd8d509727eba611fec4b485a3d3ddb0f89ababcdc18704a` | 모델 바꾼 판 |
| `prompt-model-v2-p3-saved-text.json` | `741e3a268f862180b351c4ef90c873df3e061163b67ae06dfd5fb3d515c882b7` | 모델 바꾼 판 + 저장 글 |
