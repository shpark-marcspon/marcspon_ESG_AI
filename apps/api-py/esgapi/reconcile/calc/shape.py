"""읽는 쪽의 꼴 검사. 바깥에서 온 JSON 값(dict·list)이 「우리가 읽는 칸」을 갖췄는지 본다.

TS 는 zod 로 한다(`adapters/files.ts:61-88`, `compare/places-cli.ts:17-23`). 여기서는 작은 꼴 표 하나로 한다:
같은 표에서 **검사**와 **읽는 칸의 목록**(`read_fields` — 계약 테스트가 정본 스키마와 견주는 재료)이 둘 다 나온다.
zod 의 `z.object` 처럼 모르는 칸은 지나친다(있어도 된다).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

Json = Any  # json.loads 가 내는 값


@dataclass(frozen=True, slots=True)
class Str:
    pass


@dataclass(frozen=True, slots=True)
class Int:
    pass


@dataclass(frozen=True, slots=True)
class Num:
    pass


@dataclass(frozen=True, slots=True)
class Const:
    value: str


@dataclass(frozen=True, slots=True)
class Enum:
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Arr:
    item: "Shape"
    length: int | None = None  # 꼭 이 길이여야 한다 (bbox 는 4)
    min_length: int = 0


@dataclass(frozen=True, slots=True)
class Field:
    shape: "Shape"
    required: bool = True


@dataclass(frozen=True, slots=True)
class Obj:
    fields: Mapping[str, Field]


Shape = Str | Int | Num | Const | Enum | Arr | Obj


@dataclass(frozen=True, slots=True)
class ReadField:
    """읽는 칸 하나. `path` 는 `tables[].header.rows[]` 꼴이다."""

    path: str
    type: Literal["string", "integer", "number", "array", "object"]
    required: bool  # 부모 객체가 있을 때 이 칸이 꼭 있어야 하는가
    enum: tuple[str, ...] | None = None  # 값이 이 가운데 하나여야 한다 (const 는 값 하나짜리)
    length: int | None = None
    min_length: int = 0


@dataclass(frozen=True, slots=True)
class ShapeProblem:
    where: str  # 틀린 자리 (`blocks[3].bbox`)
    problem: str  # 무엇이 틀렸나


def read_fields(shape: Obj) -> tuple[ReadField, ...]:
    """꼴 표를 납작하게 편 것."""
    out: list[ReadField] = []

    def walk(path: str, shape: Shape, required: bool) -> None:
        match shape:
            case Str():
                out.append(ReadField(path, "string", required))
            case Int():
                out.append(ReadField(path, "integer", required))
            case Num():
                out.append(ReadField(path, "number", required))
            case Const(value):
                out.append(ReadField(path, "string", required, enum=(value,)))
            case Enum(values):
                out.append(ReadField(path, "string", required, enum=values))
            case Arr(item, length, min_length):
                out.append(ReadField(path, "array", required, length=length, min_length=min_length))
                walk(f"{path}[]", item, True)
            case Obj(fields):
                if path != "":
                    out.append(ReadField(path, "object", required))
                for name, field in fields.items():
                    walk(f"{path}.{name}" if path else name, field.shape, field.required)

    walk("", shape, True)
    return tuple(out)


def _is_int(value: Json) -> bool:
    """zod 의 `z.number().int()`: JSON 의 `3` 과 `3.0` 을 둘 다 정수로 본다(JS 에는 둘의 구분이 없다)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value) and value.is_integer())


def _is_num(value: Json) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value))


def check(value: Json, shape: Shape, where: str = "") -> ShapeProblem | None:
    """첫 번째로 틀린 자리 하나. 다 맞으면 None."""
    here = where or "(맨 위)"
    match shape:
        case Str():
            return None if isinstance(value, str) else ShapeProblem(here, "글자여야 한다")
        case Int():
            return None if _is_int(value) else ShapeProblem(here, "정수여야 한다")
        case Num():
            return None if _is_num(value) else ShapeProblem(here, "수여야 한다")
        case Const(expected):
            return None if value == expected else ShapeProblem(here, f"{expected!r} 여야 한다")
        case Enum(values):
            ok = isinstance(value, str) and value in values
            return None if ok else ShapeProblem(here, f"{' | '.join(values)} 가운데 하나여야 한다")
        case Arr(item, length, min_length):
            if not isinstance(value, list):
                return ShapeProblem(here, "목록이어야 한다")
            items = cast("Sequence[Json]", value)
            if length is not None and len(items) != length:
                return ShapeProblem(here, f"길이가 {length} 이어야 한다(받은 것 {len(items)})")
            if len(items) < min_length:
                return ShapeProblem(here, f"길이가 {min_length} 이상이어야 한다(받은 것 {len(items)})")
            for index, element in enumerate(items):
                problem = check(element, item, f"{where}[{index}]")
                if problem is not None:
                    return problem
            return None
        case Obj(fields):
            if not isinstance(value, dict):
                return ShapeProblem(here, "객체여야 한다")
            entries = cast("Mapping[str, Json]", value)
            for name, field in fields.items():
                path = f"{where}.{name}" if where else name
                if name not in entries:
                    if field.required:
                        return ShapeProblem(path, "칸이 없다")
                    continue
                problem = check(entries[name], field.shape, path)
                if problem is not None:
                    return problem
            return None


def as_int(value: Json) -> int:
    """`check` 가 정수로 본 값을 int 로. `3.0` 은 3 이 된다.

    (원문 숫자를 읽는 자리가 아니다: 쪽 번호·행 번호·순번이다)
    """
    return math.trunc(value)
