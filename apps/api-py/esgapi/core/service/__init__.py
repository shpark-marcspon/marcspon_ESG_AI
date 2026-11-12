"""문서 올리기와 상태 표. 여섯 모듈이 같이 쓰는 바닥이라 core 에 있다(새 업무 모듈이 아니다).

    apis/documents.py       경로 함수 셋(`.importlinter` 계약 라가 `esgapi.*.service.apis` 로 무는 자리)
    schemas/documents.py    요청·응답의 꼴(JSON)
    services/documents.py   쓰기: 문서 만들기(행 + 서명된 올리기 주소), 올림 확인(저장소에 head → 행 갱신 → 일감 queued)
    selectors/documents.py  읽기: 문서와 그 일감들. 표의 행을 바깥에 내줄 꼴(Document·Job)로 바꾼다
워커의 일감 잡기·끝내기와 그 읽기(services/jobs.py·selectors/jobs.py)는 X1a 때 실행 층 runs 로 옮겼다.

큐에 넣는 자리(커밋 뒤에 일감의 쪽지를 브로커에 넣는다)는 esgapi/core/resources/queue.py 다.
순수 규칙(상태·전이·키·파일 이름·권한)은 esgapi/core/calc/documents.py, 표는 esgapi/core/models.py 의
DocumentRow(마이그레이션 0001 — 일감 표 JobRow 는 runs/models.py), 저장소는 esgapi/core/resources/ports/storage.py 의
포트다.

★ 서버는 파일 바이트를 받지 않는다: 클라이언트가 서명된 주소로 저장소에 직접 올린다.
★ 표에는 분해 결과의 본문을 두지 않는다(칸의 집합을 테스트가 못 박는다).
"""
