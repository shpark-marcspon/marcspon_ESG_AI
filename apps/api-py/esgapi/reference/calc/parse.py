"""대응표 JSON(`mappings.kr-ets.json` 을 푼 dict) → `AssemblyMapping`.

꼴 검사는 Pydantic 이 한다(django-ninja 가 이미 데려온 의존성이다. 새로 들인 것이 없다). 조립이 읽지 않는 칸
(`sources`, `schema_version`, `domestic_raw`, `codes_raw`, `evidence`)은 버린다. 읽는 칸이 빠졌거나 꼴이 다르면
`MappingShapeError` 다(빈 대응표로 접지 않는다).
"""

from pydantic import TypeAdapter, ValidationError

from esgapi.reference.calc.types import AssemblyMapping

_ADAPTER: TypeAdapter[AssemblyMapping] = TypeAdapter(AssemblyMapping)


class MappingShapeError(ValueError):
    """대응표의 꼴이 다르다. 어느 칸이 왜 틀렸는지를 문장에 싣는다."""


def mapping_from_json(body: object) -> AssemblyMapping:
    try:
        return _ADAPTER.validate_python(body)
    except ValidationError as err:
        where = "; ".join(f"{'.'.join(str(part) for part in e['loc'])} ({e['type']})" for e in err.errors()[:5])
        raise MappingShapeError(f"대응표의 꼴이 다르다: {where}") from err
