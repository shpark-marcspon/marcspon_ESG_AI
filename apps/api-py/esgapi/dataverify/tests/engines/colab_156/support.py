"""시험 공용: 지어낸 「환경」 항목 열둘(가상 이름·지어낸 수)과 결과를 글자로 바꾸는 `outcome`.

기대값은 각 시험에 손으로 적는다. 견주기는 결과를 json.dumps 로 바꿔 글자로 본다 — dict 의 값과 키 차례가 같고,
NaN 도 같은 글자라 같다고 본다. 예외는 (타입 이름, 글)로 본다.
같은 항목 열둘을 esg-lab `py/dvcolab/cases.py` 가 손으로 따로 적는다(esg-lab 은 esg-app 을 import 하지 않는다 — 코랩과의
견줌은 그쪽, MARC-ENT-310).
"""

import contextlib
import io
import json
from collections.abc import Callable
from typing import Any

S1 = ("온실가스 배출량", "직접 배출량", "Scope 1", "tCO2eq")
S1_TON = ("온실가스 배출량", "직접 배출량", "Scope 1", "ton")
S2 = ("온실가스 배출량", "간접 배출량", "Scope 2", "tCO2eq")
TOTAL = ("온실가스 배출량", "총 배출량", "Scope 1+2", "tCO2eq")
ENERGY = ("에너지", "총 에너지", "총 에너지 사용량", "TJ")
RENEW = ("에너지", "재생에너지", "재생에너지 사용량", "TJ")
RATIO = ("에너지", "재생에너지", "재생에너지 비율", "%")
WASTE = ("폐기물", "총 폐기물", "폐기물 발생량", "ton")
RECYCLED = ("폐기물", "처리 방법", "재활용량", "ton")
LANDFILL = ("폐기물", "처리 방법", "매립량", "ton")
WATER = ("용수", "취수", "총 취수량", "m3")
YEARS = ("2022", "2023", "2024")


def item(
    n: int, quad: tuple[str, str, str, str], values: dict[str, Any], key: str = "", memo: str = ""
) -> dict[str, Any]:
    대, 중, 소, 단위 = quad
    return {
        "ID": f"E-{n:03d}",
        "테마": "환경",
        "항목": f"가상 항목 {n}",
        "대분류": 대,
        "중분류": 중,
        "소분류": 소,
        "입력 방식": "직접 입력",
        "단위": 단위,
        "values": values,
        "핵심데이터": key,
        "메모": memo,
    }


def environment() -> list[dict[str, Any]]:
    """지어낸 「환경」 항목 열둘. 값에 수·쉼표 글자·N/A·빈 글·null·빈칸 낀 글이 섞이고, 같은 대·중·소에 단위가 둘이고
    (S1·S1_TON), 같은 네 칸이 둘이다(다섯째가 첫째와 같다 — 약점 6)."""
    return [
        item(1, S1, {"2022": 1200, "2023": "1,250", "2024": 1300.5}, key="Y"),
        item(2, S2, {"2022": 300, "2023": " 12 ", "2024": "N/A"}),
        item(3, TOTAL, {"2022": 1500, "2023": 1262, "2024": 1605}, key="Y", memo="가상 메모"),
        item(4, S1_TON, {"2022": 9, "2023": 8, "2024": 7}),
        item(5, S1, {"2022": 99999, "2023": 99999, "2024": 99999}),
        item(6, ENERGY, {"2022": 100, "2023": 0, "2024": "100"}, key="Y"),
        item(7, RENEW, {"2022": 25, "2023": 5, "2024": ""}),
        item(8, RATIO, {"2022": 0.25, "2023": 1.0, "2024": 25}),
        item(9, WASTE, {"2022": None, "2023": "abc", "2024": 50}, key="Y"),
        item(10, RECYCLED, {"2022": 10, "2023": 20, "2024": "nan"}),
        item(11, LANDFILL, {"2022": 5, "2023": "inf", "2024": 25}),
        item(12, WATER, {"2022": "1,234", "2023": "1 234", "2024": "12,34"}),
    ]


def data() -> dict[str, Any]:
    return {"환경": environment()}


def outcome(call: Callable[[], Any]) -> tuple[str, str]:
    """("ok", 결과의 json) 또는 ("raise", "<타입>: <글>")."""
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            value = call()
        except Exception as error:  # 예외도 견줄 값이다
            return ("raise", f"{type(error).__name__}: {error}")
    return ("ok", json.dumps(value, ensure_ascii=False))
