# pyright: basic
# ruff: noqa: S112, SIM118, UP006, UP035
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   try-except-continue(노트북 동작); in dict.keys(); typing.List 꼴; typing 의 옛 이름
"""쪽 입력 풀기, 문서 범위로 자르기, 파트별 묶기.

노트북(AI그린워싱 점검_E0의 사본.ipynb)의 셀 16·19 소스에서 기계로 뽑아 글자 그대로 옮겼다.
흠을 고치지 않는다(py/greenwash/README.md 의 「일부러 남긴 흠」). 원본 대조(tests/notebook_probe.py)가 같음을 잰다.
"""

from typing import Any, Dict, List, Tuple


def parse_pages(pages_input: Any) -> List[int]:
    """
    입력 예:
      - "3~5" / "3-5" / "3,4,5"
      - "3~5, 10~12, 30"
      - 엔터("") => []
      - 리스트 [3, "4", 5] => [3,4,5]
    """
    if pages_input is None:
        return []

    # 리스트 입력(테스트/내부 호출용)
    if isinstance(pages_input, list):
        out: List[int] = []
        for x in pages_input:
            try:
                out.append(int(str(x).strip()))
            except Exception:
                continue
        return sorted(set(out))

    # 문자열 입력(사용자 입력)
    if isinstance(pages_input, str):
        s = pages_input.strip()
        if s == "":
            return []

        result: List[int] = []
        parts = [p.strip() for p in s.split(",") if p.strip()]
        for part in parts:
            # "3-5"도 허용
            part = part.replace("-", "~")

            if "~" in part:
                try:
                    a, b = [x.strip() for x in part.split("~", 1)]
                    a_i, b_i = int(a), int(b)
                    lo, hi = (a_i, b_i) if a_i <= b_i else (b_i, a_i)
                    result.extend(range(lo, hi + 1))
                except Exception:
                    # 범위 파싱 실패는 무시
                    continue
            else:
                try:
                    result.append(int(part))
                except Exception:
                    continue

        return sorted(set(result))

    raise ValueError("페이지 입력은 리스트 또는 문자열이어야 합니다.")


def _clip_pages_to_doc_range(pages: List[int], total_pages: int) -> List[int]:
    if not pages or total_pages <= 0:
        return []
    out: List[int] = []
    for p in pages:
        try:
            pi = int(p)
        except Exception:
            continue
        if 1 <= pi <= total_pages:
            out.append(pi)
    return sorted(set(out))


def build_results_by_part(manual_results: List[dict], section_pages: Dict[str, List[int]]) -> Dict[str, List[dict]]:
    results_by_part = {k: [] for k in section_pages.keys()}
    for r in manual_results:
        p = r.get("page")
        for part, pages in section_pages.items():
            if p in pages:
                results_by_part[part].append(r)
    return results_by_part


def build_section_pages(
    ceo_input: Any, company_input: Any, climate_input: Any, total_pages: int
) -> Tuple[Dict[str, List[int]], List[int]]:
    """셀 16 의 1)·2): 파트 셋의 쪽 입력을 풀고 문서 범위로 잘라 `section_pages` 와 `manual_pages` 를 낸다.

    노트북은 `input()` 으로 받았다. 여기서는 인자로 받는다.
    """
    ceo_pages = parse_pages(ceo_input)
    company_pages = parse_pages(company_input)
    climate_pages = parse_pages(climate_input)

    _TOTAL_PAGES = total_pages

    if _TOTAL_PAGES > 0:
        ceo_pages = _clip_pages_to_doc_range(ceo_pages, _TOTAL_PAGES)
        company_pages = _clip_pages_to_doc_range(company_pages, _TOTAL_PAGES)
        climate_pages = _clip_pages_to_doc_range(climate_pages, _TOTAL_PAGES)

    section_pages: Dict[str, List[int]] = {
        "CEO 메시지": ceo_pages,
        "회사소개": company_pages,
        "기후/환경 토픽": climate_pages,
    }

    manual_pages: List[int] = sorted(set(ceo_pages + company_pages + climate_pages))
    return section_pages, manual_pages
