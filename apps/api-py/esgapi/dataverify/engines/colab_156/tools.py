"""데이터 검증 코랩(MARC-ENT-156) 셀 7 「#2.tool설정」의 로컬 도구 여덟과 도우미 `_val`·`_safe_float`(읽기판 R/126-374).

함수 이름·인자 이름과 차례·반환 dict 의 키 차례·셈은 코랩 그대로다(약점까지 — 발주서 §1-4·처분 ⑦). 코랩과 다른 자리:
- 디버그 print 를 지웠다. 단 R/137 의 print 는 정의 안 된 이름 `e` 를 불러 NameError 를 내므로(약점 1), 그 줄을 같은
  글의 `raise NameError(...)` 로 바꿨다 — 지우면 약점 1 이 고쳐진다. 분배기(dispatch)가 내는 error 글이 같다.
- `_val` 의 return 뒤 디버그 줄(죽은 코드, 약점 2)을 지웠다.
- 전역 캐시 `_value_cache`(약점 5 — 데이터 정체가 열쇠에 없어 입력마다 손으로 비웠다) 대신 실행마다 하나 만드는
  `ValueCache` 를 키워드 인자 `cache` 로 받는다. 열쇠·값·첫 일치 하나만 보는 동작(약점 6)은 그대로다.
- 타입 주석. 값은 모델이 준 JSON 이라 Any 다.
- 밴드 DV16(MARC-ENT-685): 검사 셋의 diff 를 `DIFF_DECIMALS`(9) 자리에서 반올림한 값으로 판정·기록한다(코랩은 판정은
  날 값, 기록은 10·6 자리). 허용 오차는 분배기가 실행 값(0.0)만 넘긴다.
이 폴더(engines/colab_156)는 고치지 않는다 — 다음 판은 engines/<판>/ 을 새로 만든다.
"""

from collections.abc import Mapping, Sequence
from typing import Any

CacheKey = tuple[Any, Any, Any, Any, str]


DIFF_DECIMALS = 9
"""합계·부분합·비율의 차이(diff)를 이 자리에서 반올림한 값으로 판정하고 기록한다(밴드 DV16, MARC-ENT-685 — 판정 허용
오차 0). 0.1 + 0.2 - 0.3 같은 2진 부동소수 잡음(1e-16 꼴)이 「어긋남」이 되지 않게 하려는 것뿐이다 — 보고서 값은 소수
9자리보다 잘게 적히지 않으므로 실제 차이는 지워지지 않는다. 비율은 퍼센트 포인트 그대로 같은 자리에서 반올림한다."""


class ValueCache(dict[CacheKey, dict[str, Any]]):
    """value_of_by_name 의 캐시: (대분류, 중분류, 소분류, 단위, str(연도)) → 돌려준 dict.

    실행(입력 하나)마다 새로 만든다."""


# ========= 로컬 툴 구현 =========
def tool_sum_check(a: Any, b: Any, c: Any, tolerance: Any) -> dict[str, Any]:
    """
    Check if a + b equals c within tolerance.
    Returns consistent JSON with ok/status/diff/explanation.
    """
    try:
        aa, bb, cc = float(a), float(b), float(c)
    except (TypeError, ValueError):
        raise NameError("name 'e' is not defined")  # noqa: B904 — 코랩 R/137 의 print(f"…{e}") 가 내는 예외(약점 1)
        return {
            "ok": False,
            "status": "FAIL",
            "diff": None,
            "note": "non-numeric",
            "explanation": "Input values are not numeric.",
        }

    diff = round((aa + bb) - cc, DIFF_DECIMALS)
    ok = abs(diff) <= tolerance
    status = "OK" if ok else "FAIL"
    explanation = (
        f"Sum({aa} + {bb}) - Target({cc}) = {diff:.6f} → {'within' if ok else 'exceeds'} tolerance ({tolerance})."
    )

    return {"ok": ok, "status": status, "diff": diff, "explanation": explanation}


def tool_sum_n_check(addends: Any, target: Any, tolerance: Any) -> dict[str, Any]:
    """
    Check if sum(addends[]) equals target within tolerance.
    Returns detailed JSON with ok/status/diff/explanation.
    """
    try:
        nums = [float(x) for x in addends]
        tgt = float(target)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "status": "FAIL",
            "diff": None,
            "note": "non-numeric",
            "explanation": "Input values are not numeric.",
        }

    diff = round(sum(nums) - tgt, DIFF_DECIMALS)
    ok = abs(diff) <= tolerance
    status = "OK" if ok else "FAIL"
    explanation = f"Sum({nums}) - Target({tgt}) = {diff:.6f} → {'within' if ok else 'exceeds'} tolerance ({tolerance})."

    return {"ok": ok, "status": status, "diff": diff, "explanation": explanation}


def tool_ratio_check(d: Any, e: Any, f: Any, tolerance: Any) -> dict[str, Any]:
    """
    Compare % ratio:
      calc_pct = (d/e) * 100
      expected_pct = f (또는 f*100)
    expected f가 0~1이면 비율로 보고 ×100 변환.
    expected f가 1보다 크면 백분율로 간주.
    """
    # 1) 숫자 변환
    try:
        dd, ee, ff = float(d), float(e), float(f)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "status": "FAIL",
            "diff": None,
            "note": "non-numeric",
            "explanation": "Input values are not numeric.",
        }

    # 2) 분모 체크
    if abs(ee) < 1e-15:
        return {
            "ok": False,
            "status": "FAIL",
            "diff": None,
            "note": "division by zero",
            "explanation": "Cannot divide by zero.",
        }

    # 3) 계산된 비율(%)  ← 반드시 % 스케일로
    calc_pct = (dd / ee) * 100.0

    # 4) 기대값 f 스케일 정규화
    #    f가 0~1이면 "비율", 1 이상이면 "이미 %"(약점 4 — 1.0 도 100%)
    if 0.0 <= ff <= 1.0:  # noqa: SIM108 — 코랩 꼴 그대로
        expected_pct = ff * 100.0
    else:
        expected_pct = ff

    # 5) diff (퍼센트 포인트)
    diff = round(calc_pct - expected_pct, DIFF_DECIMALS)
    ok = abs(diff) <= tolerance
    status = "OK" if ok else "FAIL"

    explanation = (
        f"Ratio = {dd}/{ee} × 100 = {calc_pct:.4f}%, "
        f"Expected ≈ {expected_pct:.4f}%, "
        f"Diff = {diff:.4f} → "
        f"{'within' if ok else 'exceeds'} tolerance ({tolerance} p.p.)."
    )

    return {"ok": ok, "status": status, "diff": diff, "explanation": explanation}


# ====== "배치형 복합툴”로 조회+검증을 1콜에 끝내기 ======
def _val(data_obj: Mapping[str, Any], quad: Sequence[Any], y: Any, *, cache: ValueCache) -> Any:
    대, 중, 소, 단위 = quad
    return tool_value_of_by_name(data_obj, 대, 중, 소, 단위, y, cache=cache).get("value")


def tool_sum_check_by_name(
    data_obj: Mapping[str, Any], total: Any, a: Any, b: Any, years: Any, tolerance: Any, *, cache: ValueCache
) -> dict[str, Any]:
    # total, a, b가 길이 4짜리 튜플이어야 한다는 것만 기억
    results: list[dict[str, Any]] = []
    for y in years:
        v_a = _val(data_obj, a, y, cache=cache)
        v_b = _val(data_obj, b, y, cache=cache)
        v_total = _val(data_obj, total, y, cache=cache)

        out = tool_sum_check(v_a, v_b, v_total, tolerance)
        results.append({"year": y, **out})
    return {"results": results}


def tool_sum_n_check_by_names(
    data_obj: Mapping[str, Any], addends: Any, target: Any, years: Any, tolerance: Any, *, cache: ValueCache
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for y in years:
        # addends 안의 각 quad, target quad이 (대,중,소,단위) 형식이어야 함.
        nums = [_val(data_obj, t, y, cache=cache) for t in addends]
        tgt = _val(data_obj, target, y, cache=cache)
        out = tool_sum_n_check(nums, tgt, tolerance)
        results.append({"year": y, **out})
    return {"results": results}


def tool_ratio_check_by_name(
    data_obj: Mapping[str, Any],
    numerator: Any,
    denominator: Any,
    expected: Any,
    years: Any,
    tolerance: Any,
    *,
    cache: ValueCache,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for y in years:
        out = tool_ratio_check(
            _val(data_obj, numerator, y, cache=cache),
            _val(data_obj, denominator, y, cache=cache),
            _val(data_obj, expected, y, cache=cache),
            tolerance,
        )
        results.append({"year": y, **out})
    return {"results": results}


# ========= 캐시로 “같은 값 재조회” 차단 =========
# 같은 (대/중/소, 연도)면 캐시에서 즉시 반환 → 툴스텝 급감.
def _safe_float(v: Any) -> float | None:
    if isinstance(v, str):
        v = v.replace(",", "").replace(" ", "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tool_value_of_by_name(
    data_obj: Mapping[str, Any], 대분류: Any, 중분류: Any, 소분류: Any, 단위: Any, year: Any, *, cache: ValueCache
) -> dict[str, Any]:
    """
    ESG JSON에서 대·중·소 분류, 단위, 연도로 값을 조회.
    - 캐시 사용
    - 숫자 변환 실패 시 "N/A"로 반환 (중복 정의 제거용 최소 수정)
    - (대분류, 중분류, 소분류, 단위, 연도) 조합이 유일키라고 가정.
       같은 대/중/소라도 단위가 다르면 서로 다른 항목으로 취급됨.
    """
    key = (대분류, 중분류, 소분류, 단위, str(year))
    if key in cache:
        return cache[key]

    for _, theme_list in data_obj.items():
        for rec in theme_list:
            if (
                rec.get("대분류") == 대분류
                and rec.get("중분류") == 중분류
                and rec.get("소분류") == 소분류
                and rec.get("단위") == 단위
            ):
                raw = rec.get("values", {}).get(str(year))
                if raw in (None, "", "N/A"):
                    res: dict[str, Any] = {"value": "N/A"}
                else:
                    num = _safe_float(raw)
                    res = {"value": num if num is not None else "N/A"}
                cache[key] = res
                return res

    res = {"value": "N/A"}
    cache[key] = res
    return res


# ========= “뭉터기로 검색” 전용 툴(페이지네이션) =========
def tool_search_items(
    data_obj: Mapping[str, Any],
    대분류: Any = None,
    중분류: Any = None,
    소분류_contains: Any = None,
    limit: Any = 50,
    offset: Any = 0,
) -> dict[str, Any]:
    """
    대/중분류 정확일치, 소분류 부분검색으로 대량 조회.
    values는 연도-값 맵 그대로 넘김(필요 시 특정 연도만 걸러낼 수도 있음).
    """
    items: list[dict[str, Any]] = []
    for _, theme_list in data_obj.items():
        for rec in theme_list:
            if 대분류 and rec.get("대분류") != 대분류:
                continue
            if 중분류 and rec.get("중분류") != 중분류:
                continue
            if 소분류_contains and (소분류_contains not in rec.get("소분류", "")):
                continue
            items.append(
                {
                    "대분류": rec.get("대분류"),
                    "중분류": rec.get("중분류"),
                    "소분류": rec.get("소분류"),
                    "단위": rec.get("단위"),
                    "values": rec.get("values", {}),
                    "메모": rec.get("메모", ""),  # 메모에 적힌 내용 또는 "" (없으면 빈 문자열)
                    "핵심데이터": rec.get("핵심데이터", ""),  # "Y" 또는 "" (없으면 빈 문자열)
                }
            )
    total = len(items)
    return {"total": total, "items": items[offset : offset + limit], "limit": limit, "offset": offset}
