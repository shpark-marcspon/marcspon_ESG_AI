# 골든: TS 엔진이 낸 출력

esg-lab 의 계산 엔진(`ts/ghg-calc` 의 `src/cli.ts calc`)을 **esg-lab `f1b2c77`** 에서 돌려 받아 적은 것이다(2026-10-08, node v22.23.1). 파이썬으로 옮긴 엔진이 같은 입력에서 **글자까지 같은** 출력을 내는지 견준다(`../../test_golden.py`, `../../test_api.py`).

## 다시 만드는 법

```sh
ESG_LAB=<esg-lab 저장소의 경로> apps/api-py/esgapi/inventory/tests/data/golden/make-golden.sh            # 이 폴더에 덮어쓴다
ESG_LAB=<…> apps/api-py/esgapi/inventory/tests/data/golden/make-golden.sh /tmp/golden-again               # 다른 폴더에
diff -r --exclude=inputs --exclude='*.sh' --exclude='*.py' --exclude=README.md <이 폴더> /tmp/golden-again   # 같으면 출력이 없다
```

esg-lab 의 파일은 고치지 않는다(읽고 실행만 한다). 입력(활동 데이터 파일)은 `make_inputs.py` 가 시험 자료의 사본에서 만들어 `inputs/` 에 둔다.

## 무엇이 들어 있나

`<표>` 는 CLI 의 `--factors` 다. **가상** = `examples/factors.synthetic.json`, **패키지** = `unit-conversions.json` + `gwp-sets.json` + `factors.kr-ets-sample.json`(이 순서), **전부** = 패키지 + 가상. CLI 는 준 파일들을 이어 붙인 뒤 검사한다.

| 골든 | 입력 | 표 | 종료 코드 | 누가 견주나 | 무엇을 재나 |
|---|---|---|---|---|---|
| `a-example.json` | esg-lab 의 `examples/activity.synthetic.json` | 가상 | 0 | 순수, 엔드포인트 | (가) esg-lab 의 예제 그대로 |
| `b-handcalc.kr-ets-decree-annex2.json` | `inputs/handcalc.kr-ets-decree-annex2.activity.json` (H01·03·04·06·10·12·13) | 전부 | 0 | 순수, 엔드포인트 | (나) 검산 사례. CLI 는 실행마다 GWP 세트 하나라 세트마다 파일이 하나다 |
| `b-handcalc.ipcc-ar5-100y-kr-nid-2025.json` | `inputs/handcalc.ipcc-ar5-100y-kr-nid-2025.activity.json` (H02·05·07) | 전부 | 0 | 순수, 엔드포인트 | (나) |
| `b-handcalc.synthetic-gwp.json` | `inputs/handcalc.synthetic-gwp.activity.json` (H08·09·11·14) | 전부 | 0 | 순수, 엔드포인트 | (나) |
| `b2-package-default.json` | `inputs/package-default.activity.json` (H01·03·04·06·12·13) | 패키지 | 0 | 순수, 엔드포인트(**`tables` 없이**) | 패키지에 실린 표와 그 순서가 CLI 에 준 것과 같은가 |
| `c-unknown-source.json` | `inputs/unknown-source.activity.json` | 가상 | 1 | 순수만 | (다) 모르는 배출원 유형 행(`scope`·`sourceType` 이 null, 묶음 이름 `"null"`). 엔드포인트는 이 행을 400 으로 막는다 |
| `d-failed-row.json` | `inputs/failed-row.activity.json` | 가상 | 1 | 순수, 엔드포인트 | (라) HTTP 로 닿는 실패 행(없는 연료 → `factor_not_found`) |
| `e-ordering.json` | `inputs/ordering.activity.json`, `--group-by orgUnit,period,scope,sourceType` | 가상 | 0 | 순수, 엔드포인트 | 묶음의 순서(JS 의 문자열 비교는 UTF-16 코드 단위 순이다: 이모지가 전각 엔 기호보다 앞) |
| `f-invalid-tables.stderr.txt` | `inputs/invalid-tables.json` 을 `--factors` 로 | (틀린 표) | 2 | 순수 | 표 검사의 문제 문장 58줄(표준 오류). 문장 끝의 받은 값이 `JSON.stringify` 꼴인가 |

(가)~(라)는 발주서가 정한 넷이고, `b2`·`e`·`f` 는 이 밴드가 더했다.

JSON 골든은 CLI 의 표준 출력 그대로다: `JSON.stringify(값, null, 2)` 와 줄바꿈 하나. 파이썬 쪽은 `json.dumps(값, ensure_ascii=False, indent=2) + "\n"` 으로 적어 견준다.

## 읽는 법

- 골든이 재는 것은 **이 입력들에서** 두 엔진이 같다는 것이다. 다른 입력에서도 같다는 증명이 아니다. 그쪽은 속성 테스트(`test_property.py`)와 검산 사례(`test_handcalc.py`)가 다른 각도에서 본다.
- 골든은 TS 엔진이 **옳다**는 증거가 아니다. 값이 옳은지는 검산 사례(엔진과 따로 계산한 기대값)가 잰다.
