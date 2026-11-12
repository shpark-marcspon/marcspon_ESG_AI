"""실행 묶음(RX1a — runbundle 앱의 export_runs·import_runs)이 모듈의 행을 싣고 넣는 포트(carrier)와 그 등록부.
순수(표준 라이브러리만 — django·ninja·psycopg 0).

실행 넷·문서·LLM 기록은 core·runs 가 싣는다. 모듈이 자기 표에 둔 행(검토·판)과 options·결과 본문 속의 id 는 모듈만
안다. runbundle 은 업무 모듈을 import 하지 못하므로(.importlinter 계약 카) 모듈이 흐름 곁에 carrier 를 단다:

    CARRIERS.register("greenwash", GreenwashCarrier())    # 모듈의 AppConfig.ready() — BINDINGS.register 곁

    export_rows(company_id, run_ids, versions)   그 실행들에 딸린 모듈 행 {표: [행…]}. versions 는 실행 id → 실행 행의
                                                 versions(판 행을 고르는 재료)
    referenced_runs(options)                     options 가 가리키는 같은 회사 실행 id(영문번역 retry.fromRunId 등).
                                                 내보내기의 닫힘(Q8)이 더한다
    rewrite(options=, versions=, results=, steps=, partials=, ids=)
                                                 넣을 때: options·versions·결과 본문·단계 data·partial 속의 옛 id·판
                                                 이름을 지도로 바꾼 값(RX1b). 길이·이름·차례는 받은 것과 같고,
                                                 id_fields() 밖 자리는 바이트 그대로다(runbundle 이 견준다)
    import_settings(company_id, user_id, rows)   넣을 때 판 행을 새 판(적용 안 함)으로 넣고
                                                 옛 판 id → (새 판 id, 새 이름)
    import_rows(company_id, user_id, rows, ids)  넣을 때 그 밖의 모듈 행
    columns()                                    모듈 표 → 칸 → 꼴("id"|"time"|"plain"). runbundle 이 내보낼 때·넣을 때
                                                 (쓰기 앞) 이 선언으로 행을 검사하고 time 칸을 풀어 넘긴다(RX1b Qb7)
    id_fields()                                  분모: 자리(모듈 표·"options"·"versions"·결과 꼴·"step:<이름>"·
                                                 "partial:<이름>") → id·판 이름을 품은 칸 경로(점, 목록은 `[]`)

★ 끼움(BINDINGS)이 있는 모듈은 carrier 를 반드시 단다(실을 행이 없으면 NO_ROWS). 없으면 그 모듈의 실행은 내보내기·넣기
  둘 다 거절된다(닫힌 기본 — runbundle 이 가른다).
★ versions 의 공통 열쇠 aiSettingId(core/calc/ai_settings.py)는 carrier 가 아니라 runbundle 이 **그 모듈의** 판 지도로
  다시 쓴다. carrier 는 모듈 열쇠 aiSetting(판 이름)만 바꾼다. 판 지도는 모듈마다 따로다(판 표는 id 순번이 따로 — RX1b).
★ 지도(IdMap)에 없는 옛 id 는 UnknownId 다 — 묶음 밖 id 를 조용히 그대로 두지 않는다. carrier 가 넣기를 못 하면(판 이름
  다시 시도가 다함 등) CarrierRefused — runbundle 이 둘 다 통째 거절로 바꾼다.
★ SettingCarrier: 판 표 하나를 싣는 공통 꼴(순수). 모듈은 판 dataclass·읽기·넣기 함수만 꽂는다(RX1b Qb5).
"""

import dataclasses
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol, TypeGuard, cast

type ColumnKind = Literal["id", "time", "plain"]


class CarrierRegistryError(Exception):
    """등록이 틀렸다(같은 모듈에 두 번)."""


class UnknownId(Exception):
    """지도에 없는 옛 id 다(묶음 밖을 가리킨다). 넣기는 통째 거절한다."""


class CarrierRefused(Exception):
    """carrier 가 그 묶음을 넣지 못한다(판 이름 다시 시도가 다함·판 행이 없음 등). 넣기는 통째 거절한다."""


@dataclass(frozen=True, slots=True)
class IdMap:
    """묶음의 옛 id → 받는 DB 의 새 id. 지도 넷: 실행·문서·AI 설정 판(id·이름). 판 둘은 **그 모듈의 것만** 담는다."""

    run: Mapping[int, int]
    document: Mapping[int, int]
    ai_setting: Mapping[int, int]
    ai_setting_name: Mapping[int, str] = field(default_factory=dict[int, str])

    @staticmethod
    def _find(what: str, table: Mapping[int, int], old: int) -> int:
        try:
            return table[old]
        except KeyError:
            raise UnknownId(f"{what} {old} 이 묶음의 지도에 없다") from None

    def run_id(self, old: int) -> int:
        return self._find("실행", self.run, old)

    def document_id(self, old: int) -> int:
        return self._find("문서", self.document, old)

    def ai_setting_id(self, old: int) -> int:
        return self._find("AI 설정 판", self.ai_setting, old)

    def ai_setting_name_of(self, old: int) -> str:
        try:
            return self.ai_setting_name[old]
        except KeyError:
            raise UnknownId(f"AI 설정 판 {old} 이 묶음의 지도에 없다") from None


@dataclass(frozen=True, slots=True)
class Rewritten:
    """carrier 가 다시 쓴 값. 차례·길이·이름은 받은 것과 같다(결과는 (꼴, 본문), 단계는 (이름, data), partial 은
    (이름, partial))."""

    options: Mapping[str, object]
    versions: Mapping[str, object]
    results: tuple[tuple[str, object], ...]
    steps: tuple[tuple[str, object], ...]
    partials: tuple[tuple[str, object], ...]


class RunCarrier(Protocol):
    def export_rows(
        self, company_id: int, run_ids: Collection[int], versions: Mapping[int, Mapping[str, object]]
    ) -> dict[str, list[dict[str, object]]]: ...

    def referenced_runs(self, options: Mapping[str, object]) -> tuple[int, ...]: ...

    def rewrite(
        self,
        *,
        options: Mapping[str, object],
        versions: Mapping[str, object],
        results: Sequence[tuple[str, object]],
        steps: Sequence[tuple[str, object]],
        partials: Sequence[tuple[str, object]],
        ids: IdMap,
    ) -> Rewritten: ...

    def import_settings(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]]
    ) -> Mapping[int, tuple[int, str]]: ...

    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None: ...

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]: ...

    def id_fields(self) -> Mapping[str, tuple[str, ...]]: ...


class NoRows:
    """실을 행도 다시 쓸 id 도 없는 모듈의 carrier."""

    def export_rows(
        self, company_id: int, run_ids: Collection[int], versions: Mapping[int, Mapping[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        return {}

    def referenced_runs(self, options: Mapping[str, object]) -> tuple[int, ...]:
        return ()

    def rewrite(
        self,
        *,
        options: Mapping[str, object],
        versions: Mapping[str, object],
        results: Sequence[tuple[str, object]],
        steps: Sequence[tuple[str, object]],
        partials: Sequence[tuple[str, object]],
        ids: IdMap,
    ) -> Rewritten:
        return Rewritten(
            options=options, versions=versions, results=tuple(results), steps=tuple(steps), partials=tuple(partials)
        )

    def import_settings(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]]
    ) -> Mapping[int, tuple[int, str]]:
        return {}

    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None:
        return None

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]:
        return {}

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {}


NO_ROWS: Final = NoRows()

AI_SETTING_ID: Final = "aiSettingId"
AI_SETTING: Final = "aiSetting"
SETTING_DROP: Final = frozenset({"id", "created_by_user_id", "created_at", "applied", "applied_at"})
"""판 dataclass 칸 가운데 싣지 않는 것 — id 는 oldId 로, 사람·때·적용은 받는 쪽이 새로 정한다(RX1b Qb1·Qb4)."""


@dataclass(frozen=True, slots=True)
class SettingCarrier:
    """AI 설정 판 표 하나를 싣는 공통 carrier(RX1b Qb5 — 순수, 모듈은 함수만 꽂는다).

    table           판 표 이름(묶음의 modules.<모듈>.<표>)
    shape           판 dataclass(selectors 의 AiSetting) — 칸에서 SETTING_DROP 을 뺀 것을 싣는다
    read_settings   (company_id=, setting_id=) → 판 dataclass(없으면 그 밖의 값) — 모듈 selector
    insert_setting  (company_id, *, row, user_id) → (새 id, 새 이름) | 그 밖의 값(이름 경합 다함) — 모듈 service.
                    row 는 실은 칸 그대로(받기를 다시 거치지 않는다 — MARC-ENT-442), 적용 안 함·다음 v<n>

    export_rows   실행들의 versions aiSettingId(정수) 판을 한 번씩(Qb2 — 기본 판은 0)
    rewrite       versions aiSetting 만 새 이름으로(aiSettingId 가 정수이고 aiSetting 이 있을 때만) — 그 밖은
                  받은 그대로
    """

    table: str
    shape: type
    read_settings: Callable[..., object]
    insert_setting: Callable[..., object]

    def _carried(self) -> tuple[str, ...]:
        return tuple(f.name for f in dataclasses.fields(self.shape) if f.name not in SETTING_DROP)

    def export_rows(
        self, company_id: int, run_ids: Collection[int], versions: Mapping[int, Mapping[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        olds = sorted({old for v in versions.values() if (old := _setting_id(v.get(AI_SETTING_ID))) is not None})
        rows: list[dict[str, object]] = []
        for old in olds:
            found = self.read_settings(company_id=company_id, setting_id=old)
            if not isinstance(found, self.shape):
                raise CarrierRefused(f"실행이 가리키는 판 {old} 을 그 회사에서 읽지 못했다")
            rows.append({"oldId": old, **{name: getattr(found, name) for name in self._carried()}})
        return {self.table: rows}

    def referenced_runs(self, options: Mapping[str, object]) -> tuple[int, ...]:
        return ()

    def rewrite(
        self,
        *,
        options: Mapping[str, object],
        versions: Mapping[str, object],
        results: Sequence[tuple[str, object]],
        steps: Sequence[tuple[str, object]],
        partials: Sequence[tuple[str, object]],
        ids: IdMap,
    ) -> Rewritten:
        old = _setting_id(versions.get(AI_SETTING_ID))
        named = (
            versions
            if old is None or AI_SETTING not in versions
            else {**versions, AI_SETTING: ids.ai_setting_name_of(old)}
        )
        return Rewritten(
            options=options, versions=named, results=tuple(results), steps=tuple(steps), partials=tuple(partials)
        )

    def import_settings(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]]
    ) -> Mapping[int, tuple[int, str]]:
        found: dict[int, tuple[int, str]] = {}
        carried = self._carried()
        for row in rows.get(self.table, []):
            old = _setting_id(row.get("oldId"))
            if old is None or old in found:
                raise CarrierRefused(f"{self.table} 의 oldId 가 틀렸거나 겹친다")
            made = self.insert_setting(company_id, row={name: row[name] for name in carried}, user_id=user_id)
            if not _is_made(made):
                raise CarrierRefused(f"{self.table} 에 판을 넣지 못했다(이름 다시 시도가 다함)")
            found[old] = made
        return found

    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None:
        return None

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]:
        kinds: dict[str, ColumnKind] = {"oldId": "id"}
        for name in self._carried():
            kinds[name] = "plain"
        return {self.table: kinds}

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {self.table: ("oldId",), "versions": (AI_SETTING_ID, AI_SETTING)}


def _setting_id(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _is_made(value: object) -> TypeGuard[tuple[int, str]]:
    if not isinstance(value, tuple):
        return False
    pair = cast("tuple[object, ...]", value)
    return len(pair) == 2 and _setting_id(pair[0]) is not None and isinstance(pair[1], str)


class CarrierRegistry:
    """모듈 id → carrier. 프로세스에 하나(CARRIERS). 시험은 새 것을 지어 runbundle 에 인자로 넘긴다."""

    def __init__(self) -> None:
        self._carriers: dict[str, RunCarrier] = {}

    def register(self, module: str, carrier: RunCarrier) -> None:
        """같은 모듈에 두 번 달면 CarrierRegistryError(같은 객체여도 — REGISTRY.register 와 같은 규칙)."""
        if module in self._carriers:
            raise CarrierRegistryError(f"모듈 {module} 의 carrier 가 이미 있다")
        self._carriers[module] = carrier

    def get(self, module: str) -> RunCarrier | None:
        """그 모듈의 carrier. 없으면 None(그 모듈의 실행은 묶음에 싣지도 넣지도 못한다)."""
        return self._carriers.get(module)

    def modules(self) -> tuple[str, ...]:
        """carrier 가 달린 모듈(단 차례)."""
        return tuple(self._carriers)


CARRIERS: Final = CarrierRegistry()
"""프로세스에 하나. 각 모듈의 AppConfig.ready() 가 끼움을 달 때 같이 단다(RX1a 뒤 0 — 모듈 넷은 RX1b)."""
