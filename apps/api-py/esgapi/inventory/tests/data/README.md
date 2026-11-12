# 시험 자료

테스트만 읽는다. wheel 과 이미지에 실리지 않는다(`pyproject.toml` 의 `exclude = ["esgapi/**/tests"]`, `.dockerignore`).

## esg-lab 에서 옮긴 사본

글자 그대로 옮겼다(`cp`, 2026-10-08, esg-lab `f1b2c77`). 여기서 고치지 않는다.

| 파일 | 원본 | sha256 | 내용 |
|---|---|---|---|
| `handcalc-cases.json` | `data/ghg-calc/handcalc-cases.json` | `c606aa3d7eb2406197c086565acdfb13b9249880da867644d08943373e781d86` | 검산 사례 H01~H14. 기대값은 엔진과 따로 계산한 것이다(Python `decimal`, 유효숫자 80자리, 반올림 없음. 과정은 사례의 `working`). 사용량과 조직은 전부 가상이다 |
| `handcalc-assembly.json` | `data/ghg-calc/handcalc-assembly.json` | `94bfbc04f9166ef3759bae8d7f8a9c69cda800c3828be9c760b563a6c6232c7b` | 검산 재통과의 조립 조건(연소 둘, 구매 전력 하나)과 표본에 없는 조합의 사례 N01. 수치는 N01 의 기대값뿐이고 엔진·조합기와 따로 계산한 것이다(과정은 `working`). 사용량과 조직은 가상이다. `test_assembly_replay.py` 가 읽는다 |
| `examples/activity.synthetic.json` | `data/ghg-calc/examples/activity.synthetic.json` | `a8f80a27dc1c0c0e57f9cfd617a1a973706c0446ae1032f16530a5c5de28afb3` | 가상의 조직과 사용량 5행 |
| `examples/factors.synthetic.json` | `data/ghg-calc/examples/factors.synthetic.json` | `9cf6d3c5fd3150b892d7be21086adec27e361a84706acabbc9978c7b202a31e2` | **가상** 계수 다섯, 가상 GWP 세트 하나, 환산표. 실제 산정에 쓰면 안 된다(`source.kind` 가 `synthetic`) |

검산 사례 가운데 `synthetic: false` 인 것의 계수와 GWP 는 패키지 자료(`../../data/`)의 출처 있는 값이다. 출처와 확인 일자(2026-10-01)는 `../../data/README.md`.

## 골든

`golden/` 에 있다. esg-lab 의 TS 엔진이 낸 JSON 이다. 만든 명령은 `golden/README.md`.
