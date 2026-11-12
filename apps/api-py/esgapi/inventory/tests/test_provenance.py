"""값의 출처(provenance)의 갈래. esg-lab `ts/kernel/test/decimal.test.ts` 10건 가운데 이 1건이다.

나머지 9건(십진 커널)은 커널과 같이 `esgapi/core/tests/test_calc_decimal.py` 로 갔다(밴드 PY8a).
순수 층: DB 도 Django 도 쓰지 않는다.
"""

from esgapi.inventory.engines.scope12.engine_1.provenance import Cited, Definition, Provenance, Synthetic


def test_provenance_has_three_kinds() -> None:
    sources: list[Provenance] = [
        Cited(title="가상 출처 (synthetic)", url="https://example.invalid/", checked_on="2026-10-02"),
        Definition(note="1 t = 1000 kg"),
        Synthetic(note="테스트용 가상 값"),
    ]
    assert [source.kind for source in sources] == ["cited", "definition", "synthetic"]
