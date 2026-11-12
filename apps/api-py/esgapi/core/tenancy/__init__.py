"""테넌시: 세션을 읽어 요청에 붙인다(트랜잭션은 열지 않는다 — 쓰기는 service 의 블록).
테넌트는 DB 에 싣지 않는다(조회마다 조건으로 거른다 — selector 의 인자와 core/isolation 의 기본 매니저).

session.py     우리 세션의 꼴·규칙·서명·읽기, 역할(Role). 순수하다
context.py     미들웨어가 읽은 세션의 상태를 요청에 붙이고 꺼낸다
middleware.py  TenantMiddleware: 쿠키 → 세션 → 요청에 붙임(DB 에 닿지 않는다)
"""
