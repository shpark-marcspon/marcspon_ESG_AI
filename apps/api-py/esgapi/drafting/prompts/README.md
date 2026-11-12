# drafting 프롬프트 — 글 자리와 지문

글의 정본은 `engines/v1/texts.py` 의 `PromptTexts` 칸 넷과 기본 글 `DEFAULT_TEXTS` 다(밴드 RP1 처분 ③ 가). 우리가 쓴 글이고
받은 자료(PRD 읽기판)의 글은 옮기지 않았다. AI 설정 판(밴드 RPA1)은 이 칸을 갈음할 뿐 엔진·흐름은 그대로다 — 이 파일의
지문은 기본 글의 것이다. v1 글을 덮어쓰지 않는다. 고침은 `engines/<다음 판>/` 이나 AI 설정 판으로 한다.

core.llm 템플릿 둘(`map/1.md`·`draft/1.md`)은 봉투만 갖는다: `=== system ===\n{{system}}\n=== user ===\n{{user}}\n`
(materiality·dataverify `prompts/` 꼴). 흐름(`flows/draft_v2.py`)이 `engines/v1/prompts.py` 로 지은 (system, user) 를 변수
`system`·`user` 에 넘기고, 봉투는 넘긴 글을 한 바이트도 바꾸지 않는다. 칸 안의 자리(`{목차}`·`{쪽 글}`·`{제목 경로}`·
`{요구 내용}`)는 `prompts.render` 가 한 번에 끼운다(끼운 값을 다시 훑지 않는다, `str.format` 0). 재료 자리는 v1 은 `{쪽 글}`·
v2 는 `{페이지 글}` 이다.

| 프롬프트 id | 단계 | system 칸 | user 칸 |
|---|---|---|---|
| `drafting/map@1` | S2 쪽 → 목차 잎 | `map_system` | `map_user`(`{목차}`·`{쪽 글}`) |
| `drafting/draft@1` | S3 잎마다 개조식 | `draft_system` | `draft_user`(`{제목 경로}`·`{요구 내용}`·`{쪽 글}`) |

## 기본 글 지문

sha256 은 칸 글을 UTF-8 로 잰 것이다(`hashlib.sha256(DEFAULT_TEXTS.<칸>.encode()).hexdigest()`).
`tests/engines/v1/test_prompts.py` 가 이 표와 코드가 같은지 본다.

| 칸 | sha256 |
|---|---|
| `map_system` | `a45ead559c8833bbe383150bd41770ac04ae241f2a2b65b5d496d5af54a9717b` |
| `map_user` | `30dcbb3abafdc92e3e4dcf3c853bb6cce00f80c8bf08ccd57d0c116c17472ff2` |
| `draft_system` | `decb6a286aa6d25c72b2053043629b021c3e786e63b2aeff5d2d6c4496fecf42` |
| `draft_user` | `5419593845f83fb951979b776fb3179288a6451ca6492ccce76cbf8019f849dc` |

## v2 (밴드 RP2b — `drafting.draft@v2`)

글의 정본은 `engines/v2/texts.py` 다. 칸 넷의 꼴은 v1 그대로이고 `map_user` 는 v1 에서 자리·머리 글자만 다르다(`[페이지
글]`·`{페이지 글}` — RPA4), `map_system` 은 RPQ1 에서 v1 글에 요구 내용 대조 한 줄을 더했고, draft 칸 둘은 새 글이다(S3 재료 = 블록·문장 표지 글 —
`engines/v2/material.py`). 표지 뜻·0부터 번호·답 꼴(`sources[{block, s}]`)의 규칙 `MARKER_RULES` 와 출력 언어·문체 규칙
`WRITING_RULES`(RPQ1)는 칸 밖 고정 꼬리로, 흐름(`flows/draft_v2.draft_request`)이 draft system 칸 글 뒤에 이 차례로 빈 줄
하나씩 두고 붙인다(RPA1 이 칸을 갈음해도 남는다). 봉투 `draft/2.md` 는 `draft/1.md` 와 같은 바이트다.
RPA4 에서 v2 글의 「쪽」을 「페이지」로 바꿨다(map 칸 둘·`MARKER_RULES` — 뜻 0 바뀜). 같은 밴드 경계 ③ 에서 `map_system` 의
대조 줄을 세웠다(페이지 전체 주제가 달라도 목표·수치 문단이 있으면 고름 · 빈 목록은 그런 문단이 없을 때만 — 실호출에서
1페이지 인사말의 감축 목표를 놓쳐서). 재료 자리 `{페이지 글}` 은 v2 자기
슬롯이고 끼움은 `engines/v2/prompts.py` 다(v1 끼움은 이 자리를 모른다 — `render` 는 모르는 자리를 그대로 둔다).
글 판은 `TEXTS_VERSION`(`drafting-texts@3` — `@1` 은 RPQ1 글, `@2` 는 RPA4 글, `@3` 은 RPS2 가 `MARKER_RULES` 끝에 「표 숫자는 표 id·행」 줄을 더함) — versions 열쇠 `texts` 로 실행에 박힌다. 칸 넷·꼬리 둘 중 하나라도 바꾸면 판을
올린다(핀 `TEXTS_PINS`, `tests/engines/v2/test_texts.py`).
AI 설정 판(밴드 RPA1 — `flows/prompt_model_v2.py`, 표 `drafting_ai_settings`)은 이 칸 넷을 회사별 저장 글로 갈음할 뿐
이 파일의 지문은 기본 글의 것이다.

| 프롬프트 id | 단계 | system | user 칸 |
|---|---|---|---|
| `drafting/map@1` | S2 쪽 → 목차 잎 | `map_system` | `map_user`(`{목차}`·`{페이지 글}`) |
| `drafting/draft@2` | S3 잎마다 개조식(블록·문장 근거) | `draft_system` + 빈 줄 + `MARKER_RULES` + 빈 줄 + `WRITING_RULES` | `draft_user`(`{제목 경로}`·`{요구 내용}`·`{페이지 글}` = 재료) |

`tests/engines/v2/test_texts.py` 가 이 표와 코드가 같은지 본다(위 v1 표와 줄 꼴이 달라 섞이지 않는다).

| v2 칸 | sha256 |
|---|---|
| v2 `map_system` | `0ddf5cfa1b8cf8f82b9c3c3ac3c12225fb9686e6e5cd778fc5b1e007f6af0b6c` |
| v2 `map_user` | `2de66ebf219813da3f9b382451efbe45c8bff1090373a46357704a11a5e696a5` |
| v2 `draft_system` | `fd800423dafcba437957f28f7faf2e7c33a6d2bb4a145180c0c2eeb1f954775e` |
| v2 `draft_user` | `7daeeb60de373acaf2f4749d6e238ce6def34e3d92be73cee4253fcd96a29ba8` |
| v2 `MARKER_RULES` | `89bf99b3172eaaf316ef0422aa82ec5e75e0a818e97a55baca3841d9d0abe914` |
| v2 `WRITING_RULES` | `2aa9bdf49db994f8b23a96b8db89acf33d62f3d313519ef24ba34ce9f11fc0e2` |
