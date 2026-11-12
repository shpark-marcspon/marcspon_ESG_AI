"""실행 층. 흐름(모듈)을 모르는 공통 자리다(MARC-ENT-210 (1)): 문서 하나를 모듈의 흐름으로 돌리는 실행의 경로와 꼴.

    service/apis/runs.py     경로 넷(config/api.py 가 /runs 아래에 세션 인증을 꽂아 건다). 아직 몸이 없고 501 을 낸다
    service/schemas/runs.py  요청·응답의 꼴(JSON)

★ core 를 딛고 업무 모듈(organization·user·inventory·reference·reconcile·greenwash)을 import 하지 않는다
  (`.importlinter` 계약 차). 회사 FK 는 core 처럼 글자 참조("organization.Company")로 둔다.
★ 다른 앱은 runs 로 FK·마이그레이션 의존을 두지 않는다(MARC-ENT-210 (1) — 그린워싱 검토 표의 run_id 는 FK 가 아닌
  BigInt 다).
"""
