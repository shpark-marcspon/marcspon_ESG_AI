# 골든: TS 조립기가 낸 답

`*.request.json` 은 조립 조건, `*.expected.json` 은 **esg-lab 의 TS 조립기(`ts/factor-assembly`)가 그 조건으로 찍은
표준 출력 그대로**다. `test_golden.py`(순수)와 `test_api.py`(DB·HTTP 를 거쳐)가 파이썬 쪽의 답이 이것과 전체
일치하는지 본다. 손으로 고치지 않는다. 테스트 폴더라 wheel 과 이미지에 실리지 않는다.

- esg-lab HEAD `f1b2c77`, 만든 날 2026-10-08, Node 22.23.1
- 읽은 자료: `esg-lab/data/factors/factors.jsonl`(sha256 `63fa3d55…2445`), `mappings.kr-ets.json`(sha256 `c7aa1891…77d2`)
- 만든 명령(`esg-lab/ts/factor-assembly` 에서. 표준 출력만 낸다. esg-lab 에 쓰는 것이 없다):

  ```sh
  pnpm -s tsx src/cli.ts assemble             diesel-manufacturing-tier2.request.json > diesel-manufacturing-tier2.expected.json
  pnpm -s tsx src/cli.ts assemble             lng-commercial-tier2.request.json       > lng-commercial-tier2.expected.json
  pnpm -s tsx src/cli.ts assemble-electricity electricity-table69.request.json        > electricity-table69.expected.json
  pnpm -s tsx src/cli.ts assemble-electricity electricity-gir2025-co2e.request.json   > electricity-gir2025-co2e.expected.json
  ```

| 이름 | 조건 | 본다 |
|---|---|---|
| `diesel-manufacturing-tier2` | 경유, 고정연소, 제조업·건설업, 전부 Tier 2 | 추정 대응이 없는 조립 |
| `lng-commercial-tier2` | 도시가스(LNG), 상업·공공, 전부 Tier 2 | 추정 대응 둘(연료 상태, 별표 10 의 이름) |
| `electricity-table69` | 구매 전력, 지침 별표 6 <표-69>, 기체별 | CO2·CH4·N2O 셋 |
| `electricity-gir2025-co2e` | 구매 전력, GIR 2025 공표, 2023년 단년, 소비단, ’06 IPCC, CO2e | `year`, CO2e 에 든 GWP 의 글 |

무효 조건: 그 HEAD 의 TS 와 그날의 계수 표로 찍은 사진이다. TS 쪽이나 계수 표가 바뀌면 다시 찍어야 하고,
다시 찍지 않으면 테스트는 「옛 TS 와 같다」만 말한다. 넷은 성공한 조립뿐이다(실패 갈래의 골든은 없다).
