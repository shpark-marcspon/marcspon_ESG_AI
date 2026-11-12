"""흐름: 모듈 안에서 판(이름@판)이 다른 처리를 「이름 붙은 단계의 차례」로 돌리는 틀. 순수(django·ninja·psycopg 0).

    types.py     값의 꼴: OutputFile·StepOutput·StepContext·FlowStep·Flow·FlowOutput·FlowRun·FlowEvents·오류 넷
    registry.py  make_flow(선언과 이름 검사)·FlowRegistry·REGISTRY(프로세스에 하나)
    run.py       run_flow: 단계를 차례로 돌리고, 단계 k 부터 이어 돌고, 사건을 내고, 끝 산출물을 검사한다
    binding.py   끼움(RunBinding)과 BINDINGS: 실행기가 실행 행의 문서·옵션에서 흐름의 입력·어댑터를 짓는 포트

core 는 업무 모듈을 모른다(.importlinter 계약 가, core/tests/test_flows_core_names.py). 흐름의 코드는 각 모듈의
flows/ 에 있고, 등록은 그 모듈의 AppConfig.ready() 에서 한다. 저장·큐·재실행 정책은 여기 없다(실행기 esgapi/runs 의 일).
"""
