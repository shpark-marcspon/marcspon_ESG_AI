"""데이터 검증 코랩 셀 7 의 도구 스키마 상수 둘(읽기판 R/387-514) — Responses API 꼴, 코랩과 같은 JSON 값.

TOOLS_RESPONSES = 로컬 도구 여덟(function), TOOLS_RESPONSES_websearch = 호스티드 web_search 하나(인사이트 단계).
search_items 의 limit 기본 50 은 분배기의 기본 200 과 다르다(약점 3, 코랩 그대로). 부르는 곳은 DV1b·LT1 이다.
"""

from typing import Any, Final

TOOLS_RESPONSES_websearch: Final[list[dict[str, Any]]] = [
    {"type": "web_search", "search_context_size": "medium"}
]  ###################web_search tool 켜기

TOOLS_RESPONSES: Final[list[dict[str, Any]]] = [
    {
        "type": "function",
        "name": "value_of_by_name",
        "description": "Return numeric value for {대분류, 중분류, 소분류, 단위, year} from ESG JSON.",
        "parameters": {
            "type": "object",
            "properties": {
                "대분류": {"type": "string"},
                "중분류": {"type": "string"},
                "소분류": {"type": "string"},
                "단위": {"type": "string", "description": "예: tCO₂eq, TJ, kWh 등"},
                "year": {"type": "string", "description": "YYYY"},
            },
            "required": ["대분류", "중분류", "소분류", "단위", "year"],
        },
    },
    {
        "type": "function",
        "name": "sum_check",
        "description": "Check if a + b equals c within tolerance. Return {ok:boolean, diff:number}.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
                "c": {"type": "number"},
                "tolerance": {"type": "number"},
            },
            "required": ["a", "b", "c", "tolerance"],
        },
    },
    {
        "type": "function",
        "name": "sum_n_check",
        "description": "Check if sum(addends[]) equals target within tolerance. Return {ok:boolean, diff:number}.",
        "parameters": {
            "type": "object",
            "properties": {
                "addends": {"type": "array", "items": {"type": "number"}},
                "target": {"type": "number"},
                "tolerance": {"type": "number"},
            },
            "required": ["addends", "target", "tolerance"],
        },
    },
    {
        "type": "function",
        "name": "ratio_check",
        "description": "Check if d / e equals f within tolerance. Return {ok:boolean, diff:number}.",
        "parameters": {
            "type": "object",
            "properties": {
                "d": {"type": "number"},
                "e": {"type": "number"},
                "f": {"type": "number"},
                "tolerance": {"type": "number"},
            },
            "required": ["d", "e", "f", "tolerance"],
        },
    },
    {  # "배치형 복합툴”로 조회+검증을 1콜에 끝내기
        "type": "function",
        "name": "sum_check_by_name",
        "description": "Verify a+b≈total for multiple years in one call. 각 항목은 [대분류, 중분류, 소분류, 단위] 배열이다.",  # noqa: E501 — 코랩 글 그대로
        "parameters": {
            "type": "object",
            "properties": {
                "total": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "a": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "b": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "years": {"type": "array", "items": {"type": "string"}},
                "tolerance": {"type": "number"},
            },
            "required": ["total", "a", "b", "years", "tolerance"],
        },
    },
    {  # "배치형 복합툴”로 조회+검증을 1콜에 끝내기
        "type": "function",
        "name": "sum_n_check_by_names",
        "description": "Verify sum(addends)≈target for multiple years in one call. 각 항목은 [대분류, 중분류, 소분류, 단위] 배열이다.",  # noqa: E501 — 코랩 글 그대로
        "parameters": {
            "type": "object",
            "properties": {
                "addends": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                },
                "target": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "years": {"type": "array", "items": {"type": "string"}},
                "tolerance": {"type": "number"},
            },
            "required": ["addends", "target", "years", "tolerance"],
        },
    },
    {  # "배치형 복합툴”로 조회+검증을 1콜에 끝내기
        "type": "function",
        "name": "ratio_check_by_name",
        "description": "Verify numerator/denominator≈expected for multiple years in one call. 각 항목은 [대분류, 중분류, 소분류, 단위] 배열이다.",  # noqa: E501 — 코랩 글 그대로
        "parameters": {
            "type": "object",
            "properties": {
                "numerator": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "denominator": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "expected": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                "years": {"type": "array", "items": {"type": "string"}},
                "tolerance": {"type": "number"},
            },
            "required": ["numerator", "denominator", "expected", "years", "tolerance"],
        },
    },
    {  # “뭉터기로 검색” 전용 툴(페이지네이션)
        # 이렇게 하면 모델이 “온실가스 배출 전체 내역을 한 번에 200개” 같은 식으로 **큰 블록을 적은 스텝**으로 받아서 판단/규칙선정→바로 **배치검증 툴** 호출 흐름으로 갑니다.  # noqa: E501 — 코랩 글 그대로
        "type": "function",
        "name": "search_items",
        "description": "Bulk search items with optional filters and pagination.",
        "parameters": {
            "type": "object",
            "properties": {
                "대분류": {"type": "string"},
                "중분류": {"type": "string"},
                "소분류_contains": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "default": 50,
                },  # 🔽 200 → 50 모델이 search_items를 너무 크게/자주 호출하면 그게 곧바로 토큰 폭탄 → 연산량 폭탄
                "offset": {"type": "integer", "default": 0},
            },
        },
    },
]
