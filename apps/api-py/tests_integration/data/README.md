# 통합 테스트의 고정물

`test_parser_flow.py` 가 읽는다. **숫자와 이름은 전부 지어낸 것이다**(실제 보고서의 값이 아니다. 공개 보고서의 사본도 아니다).

| 파일 | 무엇 |
|---|---|
| `ruled-table.cells.json` | 표의 칸(4행 × 4열)과 열의 x 좌표, 행의 높이. 손으로 적은 것이고 테스트의 기대값이 여기서 온다 |
| `ruled-table.pdf` | 위 JSON 에서 지은 PDF 한 쪽(2,260 B). sha256 `1c8ca620239b5b91c92c87930c8b34d3a99ffc1759b9e37276cb46648709829f` |

## 지은 명령

2026-10-08, 저장소 맨 위에서:

```
apps/api-py/scripts/section4-PY8c.sh --build-fixture
```

그 스크립트의 `build_fixture` 가 파서의 테스트 도구(`services/parser/tests/pdfbuild.py` 와 `tests/conftest.py` 의 `put`·`hline`.
표준 라이브러리만 쓴다)로 짓는다. 꼴은 `services/parser/tests/conftest.py` 의 `synthetic_ruled_page` 와 같다: 세로선 없이
칸마다 가로 토막만 있고, 0열의 둘째·셋째 행이 세로로 합쳐져 있다. 그 꼴이 pdfium 에서 표로 잡히는 것은 파서의
`tests/test_tables_synthetic.py` 가 잰다.

지은 결과는 결정적이다(PDF 의 `/ID` 가 내용의 md5 다. 시각·난수가 없다). `section4-PY8c.sh --pure` 가 임시 폴더에 다시 지어
sha256 이 커밋된 PDF 와 같은지 잰다. `cells.json` 을 고쳤으면 위 명령으로 PDF 를 다시 짓고 이 파일의 sha256 을 고친다.

## 무효 조건

- 표 하나, 쪽 하나다. 실제 보고서의 꼴(세로선, 여러 쪽, 그림으로 박힌 표)은 여기 없다.
- 통합 테스트의 `.py` 는 pdfbuild 를 import 하지 않는다(타입 표기가 없어 pyright strict 가 빨개진다). PDF 는 지어서 커밋해 둔다.
