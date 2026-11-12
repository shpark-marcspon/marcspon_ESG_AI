"""모듈들이 같이 딛는 바닥. 업무 모듈(organization, user, inventory …)을 import 하지 않는다(`.importlinter` 계약 가).

    conf.py        Django 설정에 실린 우리 설정(Config)을 꺼낸다
    exceptions.py  오류의 꼴: ApplicationError 와 응답 본문
    schemas.py     모듈의 schemas.py 가 같이 쓰는 바닥(Strict, StrictIn, NotBool, ERROR_RESPONSES, BODY_ERROR_RESPONSES)
    models.py      공통 모델 바닥(BaseModel: created_at·updated_at)과 core 의 표 둘(LLM 호출 기록, 문서)
    calc/          모듈들이 같이 쓰는 순수 규칙: 십진 커널(decimal.py), 불리언 거름(guards.py),
                   문서·일감의 상태와 저장소 키(documents.py). django·ninja 를 모른다
    contracts/     모듈 공통 AI 설정 꼴(ai_setting_shapes.py — 프롬프트·모델 설정·부품). 받기·조합은 calc/ai_settings.py
    service/       문서 올리기와 상태 표: 경로(apis/)·요청/응답의 꼴(schemas/)·읽기(selectors/)·쓰기(services/).
                   워커의 일감 잡기·끝내기와 일감 표는 실행 층 runs 에 있다.
                   경로는 문서 올리기 셋이다(config/api.py 가 /documents 아래에 세션 인증을 꽂아 건다)
    tenancy/       세션의 꼴과 읽기, 세션을 요청에 붙이는 미들웨어(트랜잭션은 열지 않는다), 옛 RLS 마이그레이션 조각
    isolation/     회사 범위 표의 기본 매니저: 테넌트를 정하지 않은 조회를 DB 로 가기 전에 거절한다
    resources/     바깥 기술(LLM·파서·저장소·큐)을 부르는 자리
      ports/       갈아끼우는 것의 인터페이스. 포트 하나가 파일 하나다(llm.py, parser.py, storage.py)
      <포트>.py    포트의 구현. 포트 하나가 파일 하나다. 그 파일의 make(name) 이 구현을 고른다
      queue.py     큐에 넣는 갈고리(커밋 뒤에 일감의 쪽지를 브로커에 넣는다). 포트가 없다

Django app 이기도 하다(INSTALLED_APPS). 표는 둘이다: core_llm_call_logs, core_documents
(BaseModel 은 추상이라 표가 없다. 문서에 걸린 일감의 표 run_jobs 는 runs 의 것이다 — X1a).
"""
