"""영문번역의 실행 묶음 carrier(RX1b — core/flows/carriers.py 의 RunCarrier). apps.py 가 CARRIERS 에 단다.

싣는 것: AI 설정 판(공통 꼴 SettingCarrier — 표 translation_ai_settings). 그 밖의 모듈 표 0(「묶음」은 options
batchId·part 의 투영 — 그대로 옮긴다, F8).
다시 쓰는 것: 재번역의 앞 실행 id retry.fromRunId — 자리 넷(★b 표 T1·T2·T4·T5)을 실행 지도로:

    options                         retry.fromRunId
    결과 translation.result@1        settings.retry.fromRunId
    단계 data translate              result.settings.retry.fromRunId       (결과 꼴의 사본)
    단계 data report                 results[].settings.retry.fromRunId    (결과 꼴의 사본 — digest 줄에는 없다)

referenced_runs 는 options 의 retry.fromRunId — 내보내기의 닫힘이 그 앞 실행을 끈다(같은 모듈 done 만 — Qb8).

★ 자기 models 를 import 하지 않는다(selectors·services 로만). 공개 메서드에서 dict.update(·.create( 꼴을 쓰지 않는다.
★ 옵션·결과·단계 data 에 행 id·판 이름 칸을 더하면 ID_FIELDS 와 tests/service/actions/test_bundle_carrier.py 의 고정
  표를 같이 고친다.
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Final, cast

from esgapi.core.flows.carriers import CarrierRefused, ColumnKind, IdMap, Rewritten, SettingCarrier
from esgapi.translation.contracts.shapes import RESULT_SHAPE
from esgapi.translation.service.selectors import ai_settings as setting_selectors
from esgapi.translation.service.services import ai_settings as setting_services

SETTINGS: Final = "translation_ai_settings"
RETRY: Final = "retry.fromRunId"
ID_FIELDS: Final[Mapping[str, tuple[str, ...]]] = {
    "options": (RETRY,),
    RESULT_SHAPE: (f"settings.{RETRY}",),
    "step:translate": (f"result.settings.{RETRY}",),
    "step:report": (f"results[].settings.{RETRY}",),
}


def _swap(value: object, parts: Sequence[str], ids: IdMap) -> object:
    """value 의 경로(parts — 목록은 `[]`)에 있는 정수 실행 id 를 새 id 로 바꾼 사본. 자리가 없으면 그대로."""
    if not parts or not isinstance(value, dict):
        return value
    fields = cast("dict[str, object]", value)
    head, rest = parts[0], parts[1:]
    key = head.removesuffix("[]")
    if key not in fields:
        return fields
    inner = fields[key]
    if head.endswith("[]"):
        if not isinstance(inner, list):
            return fields
        return {**fields, key: [_swap(item, rest, ids) for item in cast("list[object]", inner)]}
    if rest:
        return {**fields, key: _swap(inner, rest, ids)}
    if inner is None:
        return fields
    if isinstance(inner, int) and not isinstance(inner, bool):
        return {**fields, key: ids.run_id(inner)}
    # HD1 S1: 꾸민 값(글자·소수·bool·목록)을 그대로 싣지 않는다 — None(재시도 아님)만 그대로
    raise CarrierRefused(f"묶음의 {key} 가 정수 실행 id 가 아니다")


def _rewritten(place: str, value: object, ids: IdMap) -> object:
    for path in ID_FIELDS.get(place, ()):
        value = _swap(value, path.split("."), ids)
    return value


class TranslationCarrier:
    def __init__(self) -> None:
        self._settings = SettingCarrier(
            table=SETTINGS,
            shape=setting_selectors.AiSetting,
            read_settings=setting_selectors.ai_setting_detail,
            insert_setting=setting_services.import_setting,
        )

    def export_rows(
        self, company_id: int, run_ids: Collection[int], versions: Mapping[int, Mapping[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        return self._settings.export_rows(company_id, run_ids, versions)

    def referenced_runs(self, options: Mapping[str, object]) -> tuple[int, ...]:
        retry = options.get("retry")
        found = cast("dict[str, object]", retry).get("fromRunId") if isinstance(retry, dict) else None
        return (found,) if isinstance(found, int) and not isinstance(found, bool) else ()

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
        named = self._settings.rewrite(
            options=options, versions=versions, results=results, steps=steps, partials=partials, ids=ids
        )
        return Rewritten(
            options=cast("Mapping[str, object]", _rewritten("options", dict(options), ids)),
            versions=named.versions,
            results=tuple((shape, _rewritten(shape, body, ids)) for shape, body in results),
            steps=tuple((name, _rewritten(f"step:{name}", data, ids)) for name, data in steps),
            partials=tuple(partials),
        )

    def import_settings(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]]
    ) -> Mapping[int, tuple[int, str]]:
        return self._settings.import_settings(company_id, user_id, rows)

    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None:
        return None

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]:
        return self._settings.columns()

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {**self._settings.id_fields(), **ID_FIELDS}
