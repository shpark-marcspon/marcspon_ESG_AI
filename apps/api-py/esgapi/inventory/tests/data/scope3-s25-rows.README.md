# scope3-s25-rows.json — 2026-10-01 실측의 분류 결과(다듬은 사본)

`scope3_replay.py` 의 G3·G4 가 「앞선 실행의 분류 결과(범주, 영어 검색어, 어느 기반을 불렀는가)」로 쓴다.
생성 모델을 다시 부르지 않고 후보 추리기만 다시 재려는 것이다.

- 원본: esg-lab `out/measure-openai/scope3-s25/rows.json`(git 밖의 산출물, 196,942 B, 148행).
  sha256 `d883d82585b4cf5948a1c22d7e9976967ded86efe4d10b7a9aac9b398b016e90`
- 실측 일자: 2026-10-01(OpenAI 실호출의 결과다. 이 사본을 만들 때는 호출하지 않았다)
- esg-lab HEAD `f1b2c77`, 사본을 만든 날 2026-10-08
- 다듬은 명령(행마다 TS `PriorRow` 의 칸만 남긴다):

  ```
  jq '[.[] | {rowId, source, predictedCategory, keywords, shortlists: [.shortlists[] | {basis, total}]}]' \
      <esg-lab>/out/measure-openai/scope3-s25/rows.json > scope3-s25-rows.json
  ```

- 뺀 것: `itemName`·`unit`·`gold`·`status`·`picks`·`basis`·`failure`·`calcStatus`, `shortlists[]` 의 `method`·`shownIds`·
  `evidence`·`failure`. 품목명과 정답은 여기 없다(예제 148행은 esg-lab 에서 읽는다).
- 148행 가운데 추천 호출까지 간 행 118, 재현율의 분모 113(정답이 있고 기억에서 오지 않았고 추천 호출까지 간 행).
- 원본으로 돌린 TS `recall` 의 `recall.json` 과 이 사본으로 돌린 것은 `from`(입력 파일의 경로) 한 칸 말고 글자까지 같다
  (2026-10-08 확인: `diff <(jq 'del(.from)' …) <(jq 'del(.from)' …)` 가 비어 있음).
