"""gunicorn 설정. 이미지의 CMD 가 `gunicorn -c gunicorn.conf.py esgapi.config.wsgi:application` 으로 읽는다."""

import os

from esgapi.core.observability.jsonlog import gunicorn_logging_config

# 듣는 포트는 환경 변수 PORT 에서(TS 뼈대의 api 와 같다).
bind = f"0.0.0.0:{os.environ['PORT']}"
# 일꾼 프로세스 둘. 일꾼 하나가 요청 하나를 처리한다(동기). 일꾼마다 DB 연결을 하나씩 쥔다.
workers = 2
# SIGTERM 을 받으면 새 요청을 받지 않고, 받던 요청을 이 시간(초)까지 마친 뒤 내려간다.
# compose 의 stop_grace_period(15초)보다 짧아야 강제 종료(SIGKILL) 전에 끝난다.
graceful_timeout = 10
# 일꾼이 이 시간(초) 동안 답이 없으면 죽이고 새로 띄운다.
timeout = 30
# 접근 기록은 미들웨어가 요청마다 한 줄로 낸다(로거 esgapi.access). 여기서 켜면 두 벌이다.
accesslog = None
# gunicorn 자신의 줄(뜨기·일꾼·신호·오류)도 표준 출력에 한 줄 JSON 으로 낸다.
logconfig_dict = gunicorn_logging_config()
# 제어 소켓(gunicornc 용)은 끈다. 우리는 gunicornc 를 쓰지 않고, 켜 두면 컨테이너 사용자의 HOME 에 소켓을 못 만들어
# 기동마다 ERROR 한 줄이 남는다(MARC-ISSUE-317).
control_socket_disable = True
