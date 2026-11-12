"""runs 의 순수 규칙. django·ninja·psycopg 를 import 하지 않는다(`.importlinter` 계약 다의 `esgapi.*.calc`).

keys.py      실행의 파일을 저장소의 어느 키에 두는가
claims.py    실행을 잡아도 되는가와 시도 상한의 셈(진행 없이 끝난 시도만 센다)
deadline.py  협조 마감(시도를 스스로 접는 때)과 그 신호 RunYield
errors.py    실행이 failed 로 끝날 때의 error_code 와 사람에게 보일 글(고정 표)
"""
