"""경로 시험의 공용 fixture: 흐름 시험(tests/flows/test_runs_drafting.py)의 world 를 그대로 쓴다 — 가짜 저장소·실행기
설정·호출 기록·대본 모의 공급사(openai 자리의 MockProvider)."""

from esgapi.drafting.tests.flows.test_runs_drafting import world as world

__all__ = ["world"]
