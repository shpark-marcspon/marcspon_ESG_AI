# inventory 의 프롬프트 템플릿

`esgapi.core.llm` 의 `PackagePromptStore` 가 `esgapi/<모듈>/prompts/<이름>/<판>.md` 로 읽는다. id 는 `모듈/이름@판` 이다.

| id | 파일 | 원본 (esg-lab) | 원본의 sha256 |
|---|---|---|---|
| `inventory/scope3-classify@1` | `scope3-classify/1.md` (23줄) | `ts/scope3/prompts/scope3/classify/1.md` | `3d3aaf5e90c14f5ee82da2acbd84dba513edb108ccebaab778295ad98cf2b158` |
| `inventory/scope3-recommend@1` | `scope3-recommend/1.md` (18줄) | `ts/scope3/prompts/scope3/recommend/1.md` | `48a0c743b771c580cf96cd76359157152fdc04a56bf7dbba68ebc4b2e9effebd` |

- 둘 다 esg-lab 의 것을 **본문 그대로** 옮긴 사본이다(`cp`. 한 글자도 고치지 않았다). esg-lab HEAD `f1b2c77`, 확인 일자 2026-10-08.
  `esgapi/inventory/tests/test_scope3_prompts.py` 가 이 폴더의 파일과 위 sha256 을 견준다.
- TS 에서의 id 는 `scope3/classify@1`·`scope3/recommend@1` 이었다. 여기서는 모듈 이름이 앞에 와야 해서 이름만 바뀌었다.
- 변수: 분류 `{{item_json}}`, 추천 `{{category}}`·`{{basis}}`·`{{item_json}}`·`{{candidates_json}}`.
  수량·금액·무게·거리·계수 값은 넣지 않는다(`calc/scope3/llm_steps.py`).
- 본문을 고치면 판을 올린다(`2.md`). 같은 판의 파일을 고치지 않는다(호출 기록이 판으로 프롬프트를 가리킨다).
- ★ 지금 이 템플릿으로 실제 공급사를 부르는 길은 없다. 경로는 `mock` 하나다(`inventory/services.py` 의 `SCOPE3_ROUTE`).

코랩 판 `scope3.colab@157`(`engines/scope3/colab_157/`)의 프롬프트. 원본은 받은 Scope 3 코랩의 읽기판
`received-derived/2026-10-15/Scope 3 코랩/Scope3_생물기원적용_.md`(`MARC-ENT-157`)이고, 줄 번호와 sha256 은 그 읽기판의 블록이다
(블록 = 그 줄들의 글자를 줄바꿈으로 이은 것). 본문은 코랩 f-문자열의 글자 그대로이고 변수만 `{{…}}` 로 바꿨다.

| id | 파일 | 원본 (읽기판 줄) | 원본 블록의 sha256 | 코랩 함수 |
|---|---|---|---|---|
| `inventory/scope3-colab-group-name@1` | `scope3-colab-group-name/1.md` (11줄) | user `:4598-4607` | `b961bdf0fc5c6ffcd66e9c3849a32f27e0c07c5cff7a5930deb996e77b904f27` | `_infer_group_name_llm`(`:4592`, `max_tokens=20`, system 없음) |
| `inventory/scope3-colab-naics-pick@1` | `scope3-colab-naics-pick/1.md` (39줄) | system `:2764-2765`, user `:2704-2740` | system `823913c991199455da46d70f5060e7f8ed5a7c2f83e37c0cf961edad0f22d9bf`, user `c006455285bd3ab813ea7f153fe416a47f310c987bf5d525fed63e112eeed4d8` | `translate_product_for_search_info`(`:2743`, `max_tokens=1024`) |

- C1·C2 길이 닿는 것은 이 둘뿐이다(호출 그래프는 밴드 보고 `band-reports/S3C-a-colab.md`). 변수: 그룹 이름 `{{product_text}}`,
  NAICS 고르기 `{{product}}`·`{{cleaned_product}}`·`{{allowed_text}}`. 수량·금액·계수 값은 넣지 않는다.

S3C-b1(지출·폐기물)이 더한 셋. 코랩 `_call_claude_json`(`:251`)으로 부르는 둘은 system 구획이 `:259` 의 글자 그대로
(`a2d11259da364a330555eb0bb33e6c986f4f895da81fa154f9fd7723dc3a781a`)이고, user 끝의 `{{json_retry}}` 는 첫 부름에서 빈 글,
2·3번째 부름에서 `:261` 의 덧붙임(`9ef1e65e06bab1d1877ab868133f75174efca6da5731ff926d8f67666bb579c0`, `llm.JSON_RETRY_SUFFIX`)이다.
코랩 f-문자열 안의 조건 조각(`{f"맥락: {context}" if context else ""}`)은 변수 하나로 받는다(값은 `units.py` 가 코랩 식대로 짓는다).

| id | 파일 | 원본 (읽기판 줄) | 원본 블록의 sha256 | 코랩 함수 |
|---|---|---|---|---|
| `inventory/scope3-colab-unit-factor@1` | `scope3-colab-unit-factor/1.md` (13줄) | user `:3817-3825` | `5784f592929fb3784be9a7a782b8c0763eb401b168dfffcc62f36167135f0c04` | `_ai_unit_conversion_factor`(`:3809`, `_call_claude_json(max_tokens=80)`) — 변수 `{{unit_raw}}`·`{{base_unit}}`·`{{context_line}}`·`{{json_retry}}` |
| `inventory/scope3-colab-unit-factor-simple@1` | `scope3-colab-unit-factor-simple/1.md` (2줄) | user `:3833-3835` | `3fcfcacb2926268a00ab95715e1aae6dd04b93fbe1f2b9371854e0e70850338f` | 같은 함수의 단순 프롬프트(`_call_claude_text(max_tokens=30, retries=2)`, system 없음) — 변수 `{{unit_raw}}`·`{{base_unit}}`·`{{context_part}}` |
| `inventory/scope3-colab-travel-mode@1` | `scope3-colab-travel-mode/1.md` (8줄) | user `:8525-8528` | `33f4a5bc087c0744f986a7e4a98e4834fa34ae4429e34f80c1a2c2547d3d2737` | `_ai_normalize_travel_mode`(`:8523`, `_call_claude_json(max_tokens=40)`) — 변수 `{{text}}`·`{{json_retry}}` |

- 공급사에 가는 글자(첫·2·3번째 user, system)가 코랩 f-문자열과 같은지는 `tests/engines/scope3/colab_157/test_llm_retry.py` 가 코랩 식을 그대로
  다시 짜서 견준다. 수량·금액·계수 값은 넣지 않는다(단위 글자·이동수단 글자만).

S3C-b2a(거리 길 — C4-1·C9-1, b2b 의 C6-1·C7 도 같은 다섯)가 더한 다섯. JSON 넷은 위 셋과 같이 system 구획(`:259`)과 user 끝
`{{json_retry}}` 를 둔다. 도시 정규화는 코랩이 `client.messages.create` 를 바로 부르는 자리라 system·재시도가 없다 — 코랩
f-문자열의 앞뒤 줄바꿈·들여쓰기는 읽개가 걷는다(user 구획 strip, 「코랩과 다른 자리」. 안쪽 줄의 들여쓰기는 그대로).
AI 실거리의 `{{mode_label}}` 은 `distance.py` 가 코랩 `:1582` 표대로 풀어 넣는다. 원본 줄은 `prompt = f"""` 줄부터 닫는 줄까지.

| id | 파일 | 원본 (읽기판 줄) | 원본 블록의 sha256 | 코랩 함수 |
|---|---|---|---|---|
| `inventory/scope3-colab-city-name@1` | `scope3-colab-city-name/1.md` (10줄) | user `:1046-1056` | `3adf977c2fed3850f650bf1a54000d1c3070ef29017b62192291eee2ba7aa9f3` | `normalize_city`(`:1044`, `max_tokens=20`, system·재시도 없음) — 변수 `{{city}}` |
| `inventory/scope3-colab-distance-straight@1` | `scope3-colab-distance-straight/1.md` (10줄) | user `:1602-1607` | `be1efbb5e3f3efa004afd362334e4b4827e1f5a68efa9648a11ddf44f0c50b74` | `_ai_estimate_straight_km`(`:1595`, `_call_claude_json(max_tokens=60)`) — 변수 `{{origin}}`·`{{dest}}`·`{{country_hint}}`·`{{json_retry}}` |
| `inventory/scope3-colab-distance-road@1` | `scope3-colab-distance-road/1.md` (11줄) | user `:1583-1589` | `3842bfb8526bfe12636637a4db806c359c8ec34b6e90d4814cc63228fce7184b` | `_ai_estimate_distance_km`(`:1577`, `_call_claude_json(max_tokens=60)`) — 변수 `{{origin}}`·`{{dest}}`·`{{mode_label}}`·`{{country_hint}}`·`{{json_retry}}` |
| `inventory/scope3-colab-airport@1` | `scope3-colab-airport/1.md` (12줄) | user `:1637-1644` | `68660e8633399c49ed3dac9a0addd89076af30e724c7facbd8f99f6fc07d5d17` | `_ai_nearest_airport`(`:1629`, `_call_claude_json(max_tokens=80)`) — 변수 `{{location}}`·`{{country_hint}}`·`{{json_retry}}` |
| `inventory/scope3-colab-transport-mode@1` | `scope3-colab-transport-mode/1.md` (9줄) | user `:7689-7693` | `6262dd97a894eecd3f8ffca700fa6ebd0e1f9c7c0a8c3984b747420dd68cabf8` | `_ai_infer_transport_mode`(`:7684`, `_call_claude_json(max_tokens=40)`) — 변수 `{{text}}`·`{{json_retry}}` |

- 공급사에 가는 글자는 `tests/engines/scope3/colab_157/test_distance.py`(D3)·`test_transport_mode.py` 가 코랩 f-문자열을 그대로
  다시 짜서 견준다. 넣는 값은 지명·운송 글자뿐이다(거리·무게·계수 값은 넣지 않는다).
