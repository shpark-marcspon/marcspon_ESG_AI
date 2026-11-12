# Scope 3 의 시험 자료 (전부 가상)

★ 이 폴더의 계수·행·기억·보정 계수는 전부 **가상(synthetic)** 이다. 러너가 계산하기 쉬운 숫자로 지어냈고 실제 배출계수·
실제 거래·실제 환율이 아니다. 실제 계수 표(esg-lab `data/factors/factors.jsonl`)와 예제 148행은 저장소에 넣지 않았다
(`scope3_replay.py` 가 esg-lab 의 절대 경로에서 읽기만 한다).

| 파일 | 무엇 |
|---|---|
| `factors.synthetic.jsonl` | 가상 계수 37줄. 꼴은 esg-lab `schemas/factor.schema.json` 0.1(TS `FactorStore.load` 가 읽고, `reference` 의 `import_factors` 의 낱줄 꼴 검사도 지난다). 후보 34(`syn` 31 · `syn-d` 3 = disputed), 후보 아님 3(기체별 행 · 값 없는 행 · 범주 없는 행). **파일의 차례와 id 의 차례가 다르다**(`syn:ab` 가 `syn:a_b` 보다 앞 줄에 있다) |
| `examples/rows.synthetic.jsonl` | 가상 내역 34행(구매·자본재·운송·출장·통근, 표기만 다른 같은 품목, 전각·BMP 밖 글자가 든 품목명) |
| `examples/memory.synthetic.json` | 가상 확정 매핑 3건(이용 조건으로 빠지는 계수, 표에 없는 계수, 범주가 어긋난 계수) |
| `adjustments.synthetic.json` | 가상 보정 계수 1건(KRW → 2022 USD, 0.001) |
| `golden/{a-default,b-no-bigrams,c-lexical-v1,d-exclude-disputed}/rows.json` | **골든 G1**: esg-lab 의 TS CLI 가 위 자료로 낸 행별 판단 |
| `golden/a-default/user-texts.jsonl` | 설정 a 에서 모의 공급사가 받은 사용자 글자 54건(TS 의 호출 기록에서 뽑음) |
| `golden/unicode-samples.json` | 유니코드 표본 24개에 esg-lab 의 함수(Node 22)가 낸 글자 |
| `unicode-samples.input.json` · `unicode-samples.mts` | 그 표본과, esg-lab 의 함수를 부르는 스크립트 |
| `make-golden.sh` | 골든을 만든 명령. `--check` 는 다시 만들어 diff 0 을 본다 |

## 골든을 만든 것

- esg-lab HEAD `f1b2c77`, Node v22.23.1(유니코드 17.0), 만든 날 2026-10-08.
- 명령(설정 넷. `make-golden.sh` 가 그대로 돌린다):

  ```
  cd <esg-lab>/ts && pnpm -F scope3 exec tsx src/cli.ts eval <이 폴더>/examples --provider mock \
      --factors <이 폴더>/factors.synthetic.jsonl --out <임시> --log <임시>/calls.jsonl --store-bodies [설정]
    a-default            (없음: lexical-v2, 추린 수 25)
    b-no-bigrams         --no-bigrams
    c-lexical-v1         --shortlist-method lexical-v1
    d-exclude-disputed   --exclude-license disputed --shortlist 5 --adjustments <이 폴더>/adjustments.synthetic.json
  ```

- `--provider mock` 은 규칙 응답기다(공급사 호출 0). 분류는 낱말 규칙, 추천은 추린 목록의 앞 셋이라 **정확도는 뜻이 없다.**
  골든이 재는 것은 「같은 입력에 같은 판단·같은 후보·같은 순서를 내는가」다.
- esg-lab 의 파일은 고치지 않는다(`--out`·`--log` 는 임시 폴더). `report.json`(평가 지표)은 골든에 넣지 않았다.

## 읽는 법

- 점수(BM25)는 상대 오차 1e-12 안에서 견준다: V8 의 `Math.log` 와 파이썬의 `math.log`(플랫폼 libm)는 마지막 자리가 다를 수
  있다. id·순위·겹친 낱말·그 밖의 모든 값은 글자까지 같아야 한다(`scope3_catalog_support.compare_with_ts`).
- 모의 응답기는 영어 검색어를 내지 않는다(`keywords: []`). 검색어 경로는 단위 테스트와 §4 의 G3(실제 표)이 잰다.
- 규칙 응답기로 닿는 갈래는 다섯(추천됨, 기억 셋, 후보 없음)이다. 나머지 넷은 `test_scope3_pipeline.py` 가 심은 응답으로 잰다.
