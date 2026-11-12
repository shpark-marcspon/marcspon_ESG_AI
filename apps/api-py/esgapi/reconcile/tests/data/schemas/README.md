# 스키마 사본 (시험 자료)

문서 분해 산출의 **정본 스키마 사본**이다. 읽는 쪽(`reconcile/calc/document.py`·`places.py`)이 읽는 칸의 표(`READ_FIELDS`)가
정본과 어긋나지 않는지 테스트(`test_document.py`·`test_places.py`)가 견주는 데만 쓴다. 런타임은 이 파일을 읽지 않는다
(wheel·이미지에 실리지 않는다: `esgapi/**/tests` 는 빠진다).

| 파일 | 원본 | sha256 |
|---|---|---|
| `document.schema.json` | `esg-lab/schemas/document.schema.json` (152줄) | `cbdb3e38ad5c07e7c6c930f9d4533799dd33a713ae8cf82e0f00ad473e77469b` |
| `char-places.schema.json` | `esg-lab/schemas/char-places.schema.json` (83줄) | `438ff9193d2a0d17be70acd8c67cbe1a327a3747cae5230b07c83c9116152955` |

- esg-lab HEAD `f1b2c77`, 확인 일자 2026-10-08. 글자 하나 고치지 않은 사본이다(`test_document.py` 가 sha256 을 본다).
- 정본이 바뀌면: 사본을 다시 가져오고 이 표의 sha256 과 테스트의 값을 같이 고친다. 읽는 칸이 어긋나면 테스트가 빨개진다.
- esg-app 의 파서(PD2)가 같은 스키마로 내보낸다. 두 저장소의 사본이 갈리는 것을 막는 장치는 아직 없다(다음 밴드 거리).
