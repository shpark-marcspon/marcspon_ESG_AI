"""프롬프트 저장소. id 는 `모듈/이름@판` 이고 판을 빼면 거부한다(「최신」으로 흘러가지 않게).

템플릿 파일은 모듈의 것이다: `esgapi/<모듈>/prompts/<이름>/<판>.md`. 패키지 자료로 읽는다(이미지에 같이 실린다).
core 의 예시는 `esgapi/core/prompts/hello/1.md` = `core/hello@1`.

파일의 꼴:

    === system cache ===     캐시 대상인 고정 지침(용어집 등). 캐시하지 않는 system 보다 앞에 온다
    === system ===           캐시하지 않는 지침
    === user ===             하나뿐. system 구획들 뒤에 온다. 변수는 {{이름}}
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Protocol

from esgapi.core.llm.errors import PromptError
from esgapi.core.llm.log import sha256_text
from esgapi.core.llm.types import SystemSegment


@dataclass(frozen=True)
class PromptRef:
    module: str
    name: str
    version: int


@dataclass(frozen=True)
class PromptTemplate:
    ref: PromptRef
    id: str
    system: tuple[SystemSegment, ...]
    user: str
    # 템플릿 원문의 sha256. 호출 기록에 남겨 어떤 본문으로 불렀는지 추적한다.
    hash: str

    @property
    def version(self) -> int:
        return self.ref.version


@dataclass(frozen=True)
class RenderedPrompt:
    system: tuple[SystemSegment, ...]
    user: str


class PromptStore(Protocol):
    """지금은 파일이지만 나중에 DB 로 바꿀 수 있게 인터페이스 뒤에 둔다."""

    def get(self, ref: PromptRef) -> PromptTemplate: ...


_ID = re.compile(r"^([a-z0-9][a-z0-9-]*)/([a-z0-9][a-z0-9-]*)@([1-9][0-9]*)$")


def parse_prompt_id(prompt_id: str) -> PromptRef:
    match = _ID.fullmatch(prompt_id)
    if match is None:
        raise PromptError(f"프롬프트 id 형식이 틀렸다: {prompt_id} (모듈/이름@버전, 버전 필수)")
    return PromptRef(module=match[1], name=match[2], version=int(match[3]))


def format_prompt_id(ref: PromptRef) -> str:
    return f"{ref.module}/{ref.name}@{ref.version}"


_HEADER = re.compile(r"^=== (system|system cache|user) ===$")
_NEWLINE = re.compile(r"\r?\n")


def parse_template(ref: PromptRef, source: str) -> PromptTemplate:
    prompt_id = format_prompt_id(ref)
    sections: list[tuple[str, list[str]]] = []
    for line in _NEWLINE.split(source):
        header = _HEADER.fullmatch(line)
        if header is not None:
            sections.append((header[1], []))
        elif sections:
            sections[-1][1].append(line)
        elif line.strip() != "":
            raise PromptError(
                f"{prompt_id}: 구획 머리(=== system ===, === system cache ===, === user ===) 앞에 본문이 있다"
            )

    system: list[SystemSegment] = []
    user: str | None = None
    for header_name, lines in sections:
        text = "\n".join(lines).strip()
        if text == "":
            raise PromptError(f"{prompt_id}: {header_name} 구획이 비었다")
        if header_name == "user":
            if user is not None:
                raise PromptError(f"{prompt_id}: user 구획이 둘 이상이다")
            user = text
        else:
            if user is not None:
                raise PromptError(f"{prompt_id}: system 구획은 user 구획 앞에 와야 한다")
            cache = header_name == "system cache"
            # 캐시는 앞부분 일치로 걸리므로 캐시 구획 뒤에 비캐시 구획이 와도 되지만 그 반대는 뜻이 없다.
            if cache and any(not segment.cache for segment in system):
                raise PromptError(f"{prompt_id}: 캐시 구획은 캐시하지 않는 system 구획보다 앞에 와야 한다")
            system.append(SystemSegment(text=text, cache=cache))
    if user is None:
        raise PromptError(f"{prompt_id}: user 구획이 없다")

    return PromptTemplate(ref=ref, id=prompt_id, system=tuple(system), user=user, hash=sha256_text(source))


_VARIABLE = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


def _substitute(prompt_id: str, text: str, values: Mapping[str, str], used: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match[1]
        if name not in values:
            raise PromptError(f"{prompt_id}: 변수 {name} 의 값이 없다")
        used.add(name)
        return values[name]

    # 한 번만 훑는다: 넣은 값 안의 {{...}} 는 다시 치환하지 않는다.
    return _VARIABLE.sub(replace, text)


def render_prompt(template: PromptTemplate, values: Mapping[str, str] | None = None) -> RenderedPrompt:
    """변수를 치환한다. 값이 없는 변수와 템플릿에 없는 변수는 둘 다 오류다."""
    given = values or {}
    used: set[str] = set()
    system = tuple(
        SystemSegment(text=_substitute(template.id, segment.text, given, used), cache=segment.cache)
        for segment in template.system
    )
    user = _substitute(template.id, template.user, given, used)
    unused = [name for name in given if name not in used]
    if unused:
        raise PromptError(f"{template.id}: 템플릿에 없는 변수를 넘겼다: {', '.join(unused)}")
    return RenderedPrompt(system=system, user=user)


class FilePromptStore:
    """`<root>/<모듈>/<이름>/<판>.md` 에서 읽는다. 테스트와, 패키지 밖의 템플릿을 쓸 때."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def get(self, ref: PromptRef) -> PromptTemplate:
        path = self._root / ref.module / ref.name / f"{ref.version}.md"
        if not path.is_file():
            raise PromptError(f"프롬프트가 없다: {format_prompt_id(ref)} ({path})")
        return parse_template(ref, path.read_text(encoding="utf-8"))


class PackagePromptStore:
    """`<package>/<모듈>/prompts/<이름>/<판>.md` 를 패키지 자료로 읽는다. 기본 저장소다(package = esgapi)."""

    def __init__(self, package: str = "esgapi") -> None:
        self._package = package

    def get(self, ref: PromptRef) -> PromptTemplate:
        where = f"{self._package}/{ref.module}/prompts/{ref.name}/{ref.version}.md"
        try:
            # 모듈 이름은 id 의 정규식을 지난 것이라 점이 없다(남의 패키지를 가리키지 못한다).
            file = resources.files(f"{self._package}.{ref.module}").joinpath("prompts", ref.name, f"{ref.version}.md")
            if not file.is_file():
                raise FileNotFoundError(where)
            source = file.read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError, NotADirectoryError) as err:
            raise PromptError(f"프롬프트가 없다: {format_prompt_id(ref)} ({where})") from err
        return parse_template(ref, source)
