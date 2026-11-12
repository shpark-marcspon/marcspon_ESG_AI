"""관측: 요청과 일감의 식별자를 로그까지 나르고, 로그를 한 줄 JSON 으로 낸다.

    context.py     request ID 와 일감의 id 를 싣는 자리(contextvars). 순수: 표준 라이브러리만
    jsonlog.py     한 줄 JSON 포매터와 logging 설정(Django·gunicorn·워커가 같이 쓴다).
                   순수: 표준 라이브러리와 context 만
    middleware.py  request ID 를 받거나 지어 응답 헤더에 싣고, 요청마다 접근 줄 하나를 낸다. django 를 안다

celery 를 들이지 않는다(워커의 신호는 config/celery.py 가 건다).
"""
