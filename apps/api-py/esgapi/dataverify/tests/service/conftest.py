"""service 시험의 공용 fixture: 흐름 시험(tests/flows/test_runs_dataverify.py)의 world 를 그대로 쓴다 — 가짜 저장소·
실행기 설정·호출 기록. 공급사는 그 파일의 scripted 로 모의(openai 자리의 MockProvider)만 끼운다."""

from esgapi.dataverify.tests.flows.test_runs_dataverify import world as world

__all__ = ["world"]
