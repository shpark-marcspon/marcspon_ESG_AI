# 모델 설정 자료

`models.json` 은 이 저장소가 정본이다(2026-10-16 `sid:MARC-ENT-249`, 밴드 GM1). 수치는 공식 문서를 열어 확인한 것만, 출처 키와 확인일과 함께 고친다. `models.synthetic.json` 은 여전히 esg-lab 의 사본이고, `models.embedding.synthetic.json` 은 이 저장소의 가상 파일이다.

| 파일 | 원본 | 확인 일자 | 무엇 |
|---|---|---|---|
| `models.json` | 없음(정본. 2026-10-16 까지는 `esg-lab/data/llm/models.json` 의 사본) | 2026-10-01 (`checkedOn`) | 실제 모델의 ID·단가(USD/100만 토큰)·한도·경로. 수치마다의 출처 URL 은 파일 안 `sources`(29개)와 모델의 `sourceRefs` 에 있다 |
| `models.synthetic.json` | `esg-lab/data/llm/models.synthetic.json` | 2026-10-01 (`checkedOn`) | 테스트와 모의 공급사 전용 가상 모델. 단가와 한도는 실제 값이 아니다(계산하기 쉽게 지어낸 수) |
| `models.embedding.synthetic.json` | 없음(이 저장소의 가상 파일, 밴드 L1 `MARC-TICK-85`) | 2026-10-15 (`checkedOn`) | 모의 공급사 전용 가상 임베딩 모델 하나(`mock-embedding-gw1-synthetic`, 경로 `mock-gw1`). 차원 256 은 esg-lab GW1 의 모의 임베딩과 같게 둔 것이고, 단가와 한도는 실제 값이 아니다 |

- 내력: 2026-10-16 까지는 esg-lab 사본이었다(PY3 `MARC-TICK-49`, 2026-10-08 에 뜸. sha256 은 `band-reports/PY3-core-llm.md`). 그 뒤로는 이 파일만 고치고 esg-lab 판은 따라 고치지 않는다.
- 단가의 출처 문서: <https://platform.claude.com/docs/en/about-claude/pricing> · <https://developers.openai.com/api/docs/pricing> · <https://ai.google.dev/gemini-api/docs/pricing> (머리 `checkedOn` 2026-10-01 에 확인. 그 뒤 더하거나 고친 항목은 그 항목의 notes 에 확인일이 있다 — `gpt-4.1-mini` 2026-10-16, `gpt-4.1` 2026-10-19, `gpt-4o` 2026-10-23).
- `tokenEstimate.cjkCharsPerToken`(한글·한자 1자 = 1토큰)은 **출처 없는 가정**이다(파일 안 `tokenEstimate.cjkBasis`). dry-run 과 캐시 최소 길이 경고에만 쓰이고 과금 근거가 아니다.
- **모델별 temperature**(2026-10-16 확인, 밴드 LT1 `MARC-TICK-136`). 이 자료에는 칸이 없고, 받지 않는 것은 호출 층 `core/llm/client.py` 의 `TEMPERATURE_UNSUPPORTED_PROVIDERS`·`TEMPERATURE_UNSUPPORTED_MODELS` 가 거른다(값을 주면 경로의 모델이 전부 받아야 하고, 아니면 공급사를 부르기 전에 `LlmConfigError`).
  - `gpt-6-luna`·`gpt-6.1-sol`: 받지 않음. 'When reasoning effort is not `none`, remove `temperature`, `top_p`, and `top_logprobs`.' (<https://developers.openai.com/api/docs/guides/latest-model>). 어댑터는 reasoning 을 보내지 않아 기본 강도(medium)가 걸리고, `gpt-6.1-sol` 은 `none` 을 받지 않는다.
  - `gpt-4.1-mini`: 받음(추론 모델이 아니다). 범위 'between 0 and 2' (설치된 openai 3.26.0 의 `types/responses/response_create_params.py`).
  - Anthropic 공급사 전부(`claude-haiku-4-5`·`claude-sonnet-4-6`): 싣지 않음. 설치된 anthropic 1.11.0 에 temperature 인자가 없어 extra_body 없이는 실을 수 없다. API 참조(<https://platform.claude.com/docs/en/api/messages/create>)에는 `temperature`(0.0~1.0, 기본 1.0)가 Deprecated 로 남아 있다: 'Models released after Claude Opus 4.6 do not support setting temperature. A value of 1.0 will be accepted for backwards compatibility, all other values will be rejected with a 400 error.' Haiku 4.5 는 받는다(<https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide>). Sonnet 4.6 이 'Opus 4.6 뒤' 에 드는지는 못 확인. extra_body 로 싣지 않기로 했다(감독 처분).
  - `gemini-3.1-flash-lite`·`gemini-3.5-flash-lite`: 받아서 싣는다(`GenerateContentConfig.temperature`). 다만 'For all Gemini 3 models, we strongly recommend keeping the temperature parameter at its default value of `1.0`' 이고 1.0 아래는 'may lead to unexpected behavior, such as looping or degraded performance' (<https://ai.google.dev/gemini-api/docs/gemini-3>). 값을 거부하지는 않는다.
- **`hostedToolPricing`**(밴드 TL1 `MARC-TICK-180`): 공급사가 실행하는 도구의 건당 요금(USD / 호출 1건). 지금은 `webSearchPerCall`(OpenAI 내장 `web_search`) 하나이고 `gpt-4.1`·`gpt-4o` 에만 있다. 이 칸이 없는 모델에 web_search 를 실으면 호출 층(`client.py` 의 `call_tools`·`dry_run_tools`)이 공급사를 부르기 전에 거부한다. 도구 호출 고리를 지나는 모델은 `client.py` 의 `TOOL_MODELS`(비추론 모델 허용 목록 — 지금 `gpt-4.1`·`gpt-4o`)가 정한다. `gpt-4o`(경로 `standard-openai-4o`)는 중대성평가 1부 코랩의 모델이다(밴드 IR1b, `MARC-ENT-425`) — 2027-01-14 퇴역(2026-10-23 확인, 같은 표 'GPT-4o (`gpt-4o-2024-08-06`, `gpt-4o-2024-11-20`)', 권장 대체 `gpt-6-luna`, `MARC-ISSUE-188`).
- **`gpt-4.1` 은 2027-01-14 퇴역**(2026-10-19 확인, <https://developers.openai.com/api/docs/deprecations>, 권장 대체 `gpt-6-luna`). 1차는 받은 코랩대로 쓰고 사업 종료(2027-02-02) 전에 바꾼다(`MARC-ENT-305`). 같은 표에 `gpt-4.1-mini` 도 같은 날 퇴역으로 있다(그 항목의 lifecycle 은 아직 고치지 않았다 — `MARC-ISSUE-188`).
- `embeddingModels`·`embeddingRoutes` 도 이 파일에 있다. 임베딩 호출 길(`core/llm/embedding.py` 의 `EmbeddingClient`)이 경로로 찾아 쓴다.
- 단가가 바뀌면 공식 문서를 열어 확인하고, 이 파일의 그 항목 notes 에 확인일과 출처를 같이 적는다.
