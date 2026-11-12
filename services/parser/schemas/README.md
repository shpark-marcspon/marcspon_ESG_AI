# schemas — 분해 산출의 스키마

esg-app 이 정본이다(밴드 PX, 2026-10-16). 처음에는 esg-lab 의 스키마 둘을 **글자 그대로** 가져온 사본이었고, 아래 표는
그때 옮겨 온 자리(역사)다. esg-lab 이 바뀌어도 따라가지 않는다. 스키마를 고치면 `schema_version` 과 아래 sha256 을 같이 고친다.
`docparse/config.py` 가 이 폴더에서 읽고, `app.py` 는 산출을 내보내기 전에 이 둘로 검사한다.

| 파일 | 원본 경로 (esg-lab) | 원본 커밋 | 크기 | sha256 |
|---|---|---|---:|---|
| `document.schema.json` | `schemas/document.schema.json` | `2e2c2c4` | 6,679 B | `cbdb3e38ad5c07e7c6c930f9d4533799dd33a713ae8cf82e0f00ad473e77469b` |
| `char-places.schema.json` | `schemas/char-places.schema.json` | `2e2c2c4` | 4,576 B | `438ff9193d2a0d17be70acd8c67cbe1a327a3747cae5230b07c83c9116152955` |

확인 일자: 2026-10-08 (`git -C esg-lab show 2e2c2c4:schemas/<파일> | shasum -a 256`). esg-lab main(`f1b2c77`)과 `2e2c2c4` 사이에 `schemas/` 변경은 없다.

## 지금 판 (밴드 TRD1, 2026-10-28)

선택 칸만 더했다(필수 칸·enum 은 그대로): document `parser.layout`(const 2)·`blocks[].region`(body|header|footer)·`blocks[].key`,
char-places `parser.layout`(const 2). 셋 다 번역 판 `layout=2` 산출에만 실리고 기본 판(1)의 산출 바이트는 그대로라
`schema_version`(`"0.1"`)은 올리지 않았다(올리면 기본 판 산출이 바뀐다 — 발주서 TRD1 §1.1).

| 파일 | 크기 | sha256 |
|---|---:|---|
| `document.schema.json` | 7,127 B | `92eda2aa54470964ddc3a6cce941c7b0db20d35df5e89ccf7fcbd25bdd0520bf` |
| `char-places.schema.json` | 4,708 B | `5212aa467c3a33c9676dad1f918e225474a1908367f0c3277eb84cbd0934dcb0` |

`tests/test_packaging.py` 가 두 파일의 sha256 을 「지금 판」 값과 견준다.

## 도표 라벨 (밴드 CHL1, 2026-11-10)

`chart-labels.schema.json` 은 esg-lab `schemas/chart-labels.schema.json`(커밋 `eab56dc`)을 글자 그대로 옮겼다. 판 2 의 `charts=1` 산출에만 쓴다.

| 파일 | 크기 | sha256 |
|---|---:|---|
| `chart-labels.schema.json` | 3,572 B | `f2b7a3f437ef10a4d3aa9b606997635bec222e48ece9e13fe43d864b96b8c3f4` |
