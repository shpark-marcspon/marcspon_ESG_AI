"""Scope 3 의 순수 규칙: 범주·단위 차원·묶음 키·계산·검토 전이·후보 추리기(lexical-v1, lexical-v2)·파이프라인.

esg-lab `ts/scope3/src/domain/`(HEAD f1b2c77)의 동작을 옮긴 것이다(파일을 복사하지 않았다).
Django·DB·파일·시계·난수·네트워크를 모른다. 계수는 값으로 받고(`catalog`), 생성 모델은 포트(`ports.LlmGateway`)로
받는다.

옮기지 않은 것: 임베딩 갈래(`cosine`·`rank_by_embedding`·방식 `embedding`·`hybrid`), 파일 기억, jsonl 카탈로그,
평가 도구.
"""
