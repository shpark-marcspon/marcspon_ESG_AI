"""inventory 의 테스트가 같이 쓰는 고정물.

★ 소켓 문지기(autouse `blocked_network`)는 뿌리 conftest(apps/api-py/conftest.py)의 것이다(밴드 PY3b 가 올림).
  이 폴더의 테스트는 인자 이름 `blocked_network` 로 그대로 받는다. `@pytest.mark.django_db` 가 없는 테스트가
  이름 풀이나 연결을 시도하면 NetworkBlockedError 가 나고 시도한 주소가 거기 적힌다.
  Scope 3 의 분류·추천 호출이 공급사에 닿지 않는다는 것을 말이 아니라 기계로 지킨다.
  무효 조건: `django_db`·`security` 표시가 있는 테스트에는 걸리지 않는다(DB 연결도 소켓이다).
  (PY7 은 core/tests 의 것을 import 했고, PY3b 병합 때 감독이 그 줄을 지웠다 — MARC-ISSUE-43 2번.)
"""
