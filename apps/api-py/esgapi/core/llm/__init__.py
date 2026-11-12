"""LLM 호출 층. 여섯 AI 모듈이 공급사 SDK 를 직접 부르지 않고 여기를 거친다(esg-lab 의 ts/llm 을 옮긴 것).

    types.py      낱말: 꼬리표, 사용량, 중립 요청, 공급사의 답 6갈래, 호출 결과 7갈래, 도구·도구 호출 고리의 결과 3갈래
    client.py     LlmClient.call / dry_run, CallRequest · 도구 호출 고리 LlmClient.call_tools / dry_run_tools,
                  ToolCallRequest
    embedding.py  EmbeddingClient.embed / dry_run, 흐름이 받는 포트(EmbeddingPort). 낱말은 embedding_types.py
    config.py     모델 설정 파일(data/*.json) 읽기, 경로 풀기
    budget.py     비용 상한(누적은 기록의 싱크에서 읽는다)
    cost.py       비용 계산, 토큰 어림
    retry.py      같은 모델을 다시 부르는 설정
    throttle.py   호출 간격 조절(분당 요청 수)
    log.py        호출 기록 한 줄(CallRecord), 싱크의 프로토콜, 해시
    sinks/        기록이 가는 곳: memory, jsonl
    prompts.py    프롬프트 저장소(모듈/이름@판)
    schema.py     구조화 출력의 스키마를 공급사가 받는 꼴로
    providers/    공급사 어댑터: openai, anthropic, gemini, mock, 키 가리기(redact)
    errors.py     예외 셋(설정·프롬프트·실호출 조립)
    setup.py      ★ Django 를 아는 유일한 파일(관리 명령 말고): 설정(Config)에서 LlmClient 를 세운다
    data/         모델 ID·단가·한도의 자료(models.json 은 정본, models.synthetic.json 은 esg-lab 의 사본,
                  임베딩 가상 파일은 이 저장소 것. 출처는 data/README.md)

setup.py 를 뺀 전부가 Django·ninja·psycopg 를 모른다(purity.importlinter 가 지킨다).
그래서 이 파일은 아무것도 import 하지 않는다: 쓰는 쪽이 필요한 조각을 직접 import 한다.

    from esgapi.core.llm.client import CallRequest
    from esgapi.core.llm.types import Success, Tags

    request = CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(tenant, "core"))
    result = context.llm().call(request)   # 흐름의 단계: 실행기가 지은 클라이언트(RunContext.llm — 키·상한은 실행기)
    # 경로 mock 은 mock 실행기(LLM_RUN_MODE 기본)에만 있다. live 실행기에서는 모델 설정의 실제 경로(예: light-openai)
    if isinstance(result, Success): ...   # 그 밖의 여섯 갈래는 result.kind 로 가른다

시험·관리 명령은 `setup.build_client(settings, mock=True)` 로 모의 공급사를 싣는다. 서버 요청 길의 `setup.llm_client()`
는 실제 공급사 키를 싣지 않는다(LH2) — 실호출은 실행기와 관리 명령 llm_call(--limit-usd)뿐이다.
"""
