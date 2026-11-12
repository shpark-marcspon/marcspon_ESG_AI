"""밴드 DVX1 Q11 의 데모 엑셀: 데이터 검증 입력의 data JSON(테마 → 항목 — 지어낸 가상 기업) → 지금 EDK 인벤토리 양식 꼴
xlsx. 머리·쓰기는 제품 도구 esgapi.dataverify.tools.edk_xlsx 의 것을 그대로 쓴다(양식 GET /dataverify/edk/template 와
한 자리 — 머리를 여기서 따로 적지 않는다). 사용(apps/api-py 에서):

    uv run --frozen python scripts/dataverify_edk_demo_xlsx.py <data.json> <out.xlsx>

연도 열은 모든 항목 values 열쇠의 합(오름차순), 행은 테마·항목의 JSON 차례, 「공시」는 빈 칸, 「작성 안내」 시트를 단다.
끝 줄 `ITEMS=<적은 항목 수> YEARS=<연도 열 수> BYTES=<파일 크기>`. wheel 밖 개발 도구다 — 저장소에 .xlsx 를 두지 않고
저장소 밖에 짓는다(같은 JSON 이면 같은 바이트). 받은 자료(received/)·실재 기업의 값은 넣지 않는다.
"""

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from esgapi.dataverify.tools.edk_xlsx import VALUES_KEY, row_of, workbook


def years_of(data: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    return sorted({str(year) for items in data.values() for item in items for year in item.get(VALUES_KEY, {})})


def build(data: Mapping[str, Sequence[Mapping[str, Any]]]) -> tuple[bytes, int, int]:
    """data → (xlsx 바이트, 항목 수, 연도 열 수)."""
    years = years_of(data)
    rows = [row_of(item, years) for items in data.values() for item in items]
    return workbook(years, rows, guide=True), len(rows), len(years)


def main(argv: Sequence[str]) -> int:
    if len(argv) != 2:
        print("사용: dataverify_edk_demo_xlsx.py <data.json> <out.xlsx>", file=sys.stderr)
        return 2
    source, target = Path(argv[0]), Path(argv[1])
    data = json.loads(source.read_text(encoding="utf-8"))
    content, items, years = build(data)
    target.write_bytes(content)
    print(f"ITEMS={items} YEARS={years} BYTES={len(content)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
