"""inventory 의 흐름(순수 — .importlinter 계약 다). 엔진(engines/)의 바깥 입구를 부르고 있는 serializer 로
옮기기만 한다.

    scope12_engine_1.py    Scope 1·2 흐름 scope12.engine@1(단계 calculate) — calculate_raw → aggregate → output_to_dict
    scope3_llm_first_1.py  Scope 3 의 LLM 먼저 흐름 scope3.llm-first@1(단계 pipeline) — run_pipeline 을 부르고
                           engines/scope3/llm_first_1/serialize.py 로 조립
    scope3_colab_157.py    Scope 3 의 코랩 흐름 scope3.colab@157(단계 calculate) — 템플릿 바이트를 읽개로 읽고
                           engines/scope3/colab_157 의 run 과 serialize.py. 기본 흐름이 아니다(S3C-c 가 바꾼다)
    registration.py        FLOWS·DEFAULTS·register(registry). 등록은 apps.py 의 ready() 에서만

파일 이름은 흐름 id 의 「이름@판」을 접은 것이다(engine@1 → engine_1). 결과 꼴은 contracts/shapes.py 에 있다.
흐름 id·결과 꼴 id 의 글자는 흐름 파일·registration.py·contracts/shapes.py 에만 있다(감독 노트로 굳은 이름).
엔진과 계약을 잇는 것은 흐름뿐이다(.importlinter 인벤토리 축 「자」). 흐름은 Service 를 부르지 않는다
(지금 경로도 흐름을 부르지 않는다 — 동작 0).
"""
