# 패키지에 실린 기준정보 표

`POST /inventory/calc` 가 본문에 `tables` 를 받지 못했을 때 쓰는 표다. 이미지에 실린다(`data_loader.py` 가 읽는다).

세 파일은 esg-lab 저장소의 파일을 **글자 그대로 옮긴 사본**이다. 여기서 수치를 고치지 않는다. 고칠 일이 생기면 원본의 출처를 다시 확인하고 사본을 통째로 바꾼다.

| 파일 | 원본 (esg-lab `f1b2c77`) | sha256 | 내용 |
|---|---|---|---|
| `unit-conversions.json` | `data/ghg-calc/unit-conversions.json` | `b9835bb557ba773a6d78b2abdc58bf5ca3f4680a4269dbe66be6e1c1b5210d91` | 단위 환산 25쌍. 전부 정의값(SI 접두어, 1 L = 1 dm³, 1 kWh = 3.6 MJ, 1 t = 1000 kg) |
| `gwp-sets.json` | `data/ghg-calc/gwp-sets.json` | `b75d321bccf38899f6e6d71b6b9a0efbac16820ec8315c095844a40c3898a8ee` | GWP 세트 둘 |
| `factors.kr-ets-sample.json` | `data/ghg-calc/factors.kr-ets-sample.json` | `9d74c629cd45028f905dd38c18f3840d4a3c1d35175a4e4574f59ce774f0d135` | 표본 계수 셋(경유·도시가스(LNG) 고정연소, 구매 전력) |
| `ghg-pool-seed.json` | (이 저장소에서 지음 — 밴드 K1b-2a ④) | — | 온실가스 풀 씨앗: 나무와 잎마다 계수 묶음의 reference 낱줄 id·이름·단위 글자. **값 칸 0**(수치는 `seed_ghg_pool` 이 reference 적재본·`gwp-sets.json` 에서 읽는다). 낱줄 id 는 reference 조립기를 적재본에 돌려 뽑았다. 나무는 연료 = 배출활동, 그 아래 설비 종류 잎 하나(결정 MARC-ENT-676 — S12S1). `retired` 칸은 옛 씨앗(연료 = 잎 코드)의 노드 열쇠로 `retire_ghg_seed` 만 읽는다. 위 세 파일과 달리 esg-lab 사본이 아니다 |

`ghg-pool-seed.json` 에 넣지 않은 연료 7(조립기가 실패): 원유·코크스(CO2 국가 고유 낱줄 없음), 부생연료유1호·2호·도시가스(LPG)(별표 10 이름 대응 없음), 전기(발전기준)·전기(소비기준)(연소 아님 — 구매 전력 잎). 낱줄 id 가 조립기를 다시 돌린 것과 같은지는 `../tests/service/utils/test_ghg_pool_seed_ids.py` 가 잰다(K1b-2b).

사본을 만든 날: 2026-10-08 (`cp`). 원본과 같은지 확인: `shasum -a 256 *.json`.

## 수치의 출처

수치마다의 출처(제목, URL, 확인 일자, 원문의 자리)는 **각 파일 안의 `source` 칸**에 있다. 아래는 그것을 모아 적은 것이다. 확인 일자는 전부 **2026-10-01** 이고, 확인한 것은 esg-lab 의 작업이다(이 저장소에서 원문을 다시 열어 보지 않았다).

| 무엇 | 값 | 출처 |
|---|---|---|
| GWP 세트 `kr-ets-decree-annex2` | CO2 1, CH4 21, N2O 310 | 온실가스 배출권의 할당 및 거래에 관한 법률 시행령 별표 2. https://www.law.go.kr/LSW/flDownload.do?gubun=&flSeq=163672079&bylClsCd=110201 |
| GWP 세트 `ipcc-ar5-100y-kr-nid-2025` | CO2 1, CH4 28, N2O 265 | 2025 국가 온실가스 인벤토리(1990~2023) 보고서 표 1-9. https://www.gir.go.kr/home/board/read.do?menuId=36&boardId=90&boardMasterId=2 (IPCC AR5 원문이 아니라 국가 인벤토리 보고서의 표에서 읽은 값이다) |
| 표본 계수 셋 | 파일의 `factors[].calorific`·`emissionFactors`·`oxidationFactor` | 온실가스 배출권거래제의 배출량 보고 및 인증에 관한 지침 [환경부고시 제2025-64호] 별표 12·10·6. https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=2100000257748 |
| 단위 환산 | 파일의 `unitConversions[].factor` | 정의값이라 URL 이 없다(`source.kind` 가 `definition`) |

## 이 표가 아닌 것

- **표본이다.** 계수는 셋뿐이다. 한국 지침의 계수 전량과 「어느 배출원에 어느 계수 조합을 쓰는가」는 reference 모듈(밴드 PY5)의 일이다. 여기 없는 연료는 `factor_not_found` 로 실패한다(비슷한 계수로 대신하지 않는다).
- **가상 값이 없다.** 가상 계수와 가상 GWP 세트는 시험 자료(`../tests/data/examples/`)에만 있고 이미지에 실리지 않는다(`test_data_loader.py` 가 잰다).
- `$comment` 키는 원본에 있던 설명이다. 계산은 읽지 않는다.

## `scope3/` — 받은 Scope 3 xlsx 둘 (밴드 S3K1 · S3V1)

마크스폰에게 받은 파일에서 지은 사본이다. 위 JSON 표와 달리 `data_loader.py` 가 아니라 `service/utils/scope3_files.py` 가 바이트째 읽는다. 어느 사본이든 두 칸을 비웠다 — 문서 속성 `docProps/core.xml` 의 `lastModifiedBy`(`MARC-ENT-521`)와 `xl/workbook.xml` 의 `x15ac:absPath` 의 `url` 값(요소는 남김, `MARC-TICK-427` 노트). 손질은 zip 부품에서만 한다 — openpyxl 로 다시 저장하면 수식 칸의 엑셀 저장 값이 사라진다(엔진이 읽는 값). 짓는 법이 아래 표 밖으로 바뀌면 결정부터(`MARC-ENT-641`).

- **계수 책**(밴드 S3V1, `MARC-ENT-641`): 받은 `배출계수_통합_DB_v1.1`(2026-11-10)의 Scope 3 열 10시트만 남긴 것 — Scope 1·2 열 10시트(환율_참조 …)의 부품·workbook·rels·Content_Types·app.xml 제목을 걷고, 그 시트들만 쓰던 공유 글을 걷어 번호를 다시 매겼다. 남은 시트 부품은 공유 글 번호 말고 받은 그대로(calcChain·메모·서식 포함) — **예외 하나**: `에너지_C3` 에 v1.0(앞 판)의 「도시가스(LNG) · Nm³ · 0.19527 · 환경성적표지」 줄을 5행에 남겼다(아래 줄은 한 행씩 내리고 No. 는 v1.0 번호). v1.1 은 이 줄을 뺐는데, 빼면 Nm³ 가스 입력이 kg 계수에 발열량 환산 없이 걸린다 — 마크스폰 답(`MARC-ENT-649`)이 오면 따른다(결정 `MARC-ENT-654`). 앞 판(2026-10-13 받은 책 + 두 칸 비움, `6ab4b0b2…` → `f658e1a2…`)은 git 기록에 있다.
- **양식**(밴드 S3V1, `MARC-ENT-641`): 받은 `Scope3_템플릿_수정본_v2.2`(2026-10-22)에서 세 묶음만 고친 것 — ① 실재 기업명 → 「예시기업」(`MARC-ENT-655`: 공유 글 항목 하나 · 매핑검토 안내 문장에서 이름만 뺌 · 수식 칸 저장 값 다섯 — 매핑 줄은 남김) ② 운송 Spend 드롭다운 `배출계수_드롭다운!E3:E9` = 계수 책 `운송_Spend` 에 있는 일곱(받은 차례), E10:E19 빈 칸, 정의된 이름 `DD_TRANSPORT_SPEND` 을 `$E$3:$E$9` 로 ③ 위 두 칸 비움. `드롭다운_매핑검토` 의 안내 글(옛 운송 이름을 가리키는 줄)은 받은 그대로. 앞 판(v2.1, `73c4bded…` → `664d1c3b…`)은 git 기록에 있다.

| 파일 | 무엇 | sha256 (받은 원본 → 이 사본) |
|---|---|---|
| `scope3-template-v2.2.xlsx` | 빈 입력 양식 v2.2 — `GET /inventory/scope3/template` 이 그대로 낸다(내려받기 이름 `Scope3_템플릿_수정본_v2.2.xlsx`) | `654243beda187ea1da420fe5687d8c0c9a16201ad21946eb3192a13b6254d4cd` → `c51abfd6e023424b3194892afc2878b8a101ea355ce7c301874296301bbec42e` |
| `scope3-factor-book.xlsx` | 배출계수 책 v1.1 의 Scope 3 열 — 흐름 `scope3.colab@157` 이 실행마다 읽는다. 이용 조건은 확인 중 | `2947b451912ce1fd6389ee327aa4c002011bc7f23a0b955d89dbef84ac4b5371` → `2b76427c174a90d3f43ff7a5cc6032795924d9bd90eeda8ad5571874b59a036b` |
