"""데모 스크립트(scripts/dataverify_edk_demo_xlsx.py — 밴드 DVX1 Q11)의 왕복: 지어낸 data dict → xlsx → 제품 읽개 → 같은
dict(정수 float → int · 「공시」 없음 정규화 뒤 — 발주서 Q5·Q6). 스크립트는 wheel 밖이라 경로에서 importlib 로 부른다.
파일을 쓰지 않는다(build 는 바이트를 낸다)."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from esgapi.dataverify.tools.edk_xlsx import EdkRead, read_edk

SCRIPT: Final = Path(__file__).resolve().parents[4] / "scripts" / "dataverify_edk_demo_xlsx.py"

DATA: Final[dict[str, list[dict[str, Any]]]] = {
    "환경": [
        {
            "ID": "E-001",
            "테마": "환경",
            "항목": "가상 직접 배출량",
            "대분류": "가상 온실가스",
            "중분류": "가상 직접",
            "소분류": "Scope 1",
            "입력 방식": "직접 입력",
            "단위": "tCO2eq",
            "values": {"2022": 12000, "2023": 12500.5, "2024": None},
            "핵심데이터": "Y",
            "메모": "가상 메모",
        },
        {
            "ID": 7,
            "테마": "환경",
            "항목": "가상 재생에너지 사용",
            "대분류": "가상 에너지",
            "중분류": None,
            "소분류": None,
            "입력 방식": "Yes/No",
            "단위": None,
            "values": {"2023": "Yes", "2024": "No"},
            "핵심데이터": "N",
            "메모": None,
        },
    ],
    "가상사회": [
        {
            "ID": "S-001",
            "테마": "가상사회",
            "항목": "가상 임직원",
            "대분류": "가상",
            "중분류": "가상",
            "소분류": "가상",
            "입력 방식": "직접 입력",
            "단위": "명",
            "values": {"2024": 10},
            "핵심데이터": "Y",
            "메모": None,
        }
    ],
}


def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dataverify_edk_demo_xlsx", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_demo_round_trips_to_the_same_target_theme_data() -> None:
    content, items, years = script().build(DATA)
    assert (items, years) == (3, 3)
    result = read_edk(content)
    assert isinstance(result, EdkRead), result
    expected = [
        {**item, "values": {y: item["values"].get(y) for y in ("2022", "2023", "2024")}} for item in DATA["환경"]
    ]
    assert result.data == {"환경": expected}
    assert (result.skipped_themes, result.skipped_items, result.ignored_columns) == (1, 1, 1)


def test_the_demo_is_the_same_bytes_for_the_same_data() -> None:
    assert script().build(DATA)[0] == script().build(DATA)[0]
