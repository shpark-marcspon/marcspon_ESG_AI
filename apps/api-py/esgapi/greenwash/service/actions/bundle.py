"""그린워싱의 실행 묶음 carrier(RX1b — core/flows/carriers.py 의 RunCarrier). apps.py 가 CARRIERS 에 단다.

싣는 것: AI 설정 판(공통 꼴 SettingCarrier — 표 greenwash_ai_settings) · 검토(greenwash_reviews) · 표시
(greenwash_review_marks). 검토·표시는 selectors.review.bundle_review_rows 로 읽고 services.review 의 import_review →
import_marks 차례로 넣는다(표시 → 검토 복합 외래 키). 사람 칸은 싣지 않고 넣는 쪽이 때가 있는 칸만 --user 로 채운다.
판의 criteria.version 고침은 services.ai_settings.import_setting 한 곳이다(여기는 고치지 않는다).

재판단(GCB1 — 흐름 greenwash.rejudge@E0, 문서 없음): 표시의 근거 고침 칸(evidence_removed·evidence_added·
evidence_edited_at — 사람 칸 evidence_edited_by_user_id 는 싣지 않고 --user)과 재판단 칸(evidence_basis_run_id·
rejudge_run_ids — 실행 id)을 싣고, 받는 쪽에서 실행 지도로 다시 잇는다(지도 밖은 UnknownId → 넣기 통째 거절).
재판단 실행의 원 실행 id fromRunId 는 자리 셋을 실행 지도로 다시 쓴다:

    options                 fromRunId
    결과 greenwash.rejudge@1 fromRunId
    단계 data judge          results[].fromRunId     (colab 의 judge 단계도 이름이 같다 — 그 항목엔 열쇠가 없어 그대로)

referenced_runs 는 options 의 fromRunId — 재판단 실행을 고르면 내보내기의 닫힘이 원 실행을 끈다. 닫힘은 앞 방향만
따라가므로(core) 원 실행만 고르면 재판단 실행이 따라오지 않는다. 실린 표시가 묶음 밖 **done** 재판단 실행을 가리키면
내보내기를 거절하고(CarrierRefused — 기준 판단·count 가 바뀌므로), failed·도는 중 재판단 실행 id 는 내보낼 때 목록에서
뺀다(창·--runs 는 done 만 고르므로 그 실행은 실릴 길이 없다 — 마지막 상태 줄만 앞 done 기준이 된다. 감독 §8 Q-B1).

★ 자기 models 를 import 하지 않는다 — 읽기는 selectors, 쓰기는 services 로만
  (tests/service/actions/test_bundle_carrier.py 의 AST 시험이 지킨다). 공개 메서드에서 dict.update(·.create( 꼴을
  쓰지 않는다(core/tests/test_transaction_rules.py).
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Final, cast

from esgapi.core.flows.carriers import CarrierRefused, ColumnKind, IdMap, Rewritten, SettingCarrier
from esgapi.greenwash.service.selectors import ai_settings as setting_selectors
from esgapi.greenwash.service.selectors import review as review_selectors
from esgapi.greenwash.service.services import ai_settings as setting_services
from esgapi.greenwash.service.services import review as review_services
from esgapi.runs.service.selectors import runs as run_selectors

SETTINGS: Final = "greenwash_ai_settings"
REVIEWS: Final = "greenwash_reviews"
MARKS: Final = "greenwash_review_marks"
TIME_COLUMNS: Final = frozenset(
    {
        "confirmed_at",
        "level_edited_at",
        "reasons_edited_at",
        "fix_edited_at",
        "evidence_edited_at",
        "created_at",
        "updated_at",
    }
)
REJUDGES: Final = "rejudge_run_ids"
BASIS: Final = "evidence_basis_run_id"
FROM_RUN: Final = "fromRunId"
REJUDGE_RESULT: Final = "greenwash.rejudge@1"
ID_FIELDS: Final[Mapping[str, tuple[str, ...]]] = {
    "options": (FROM_RUN,),
    REJUDGE_RESULT: (FROM_RUN,),
    "step:judge": (f"results[].{FROM_RUN}",),
}


def _kinds(fields: Sequence[str]) -> dict[str, ColumnKind]:
    kinds: dict[str, ColumnKind] = {"runOldId": "id"}
    for name in fields:
        if name != "run_id":
            kinds[name] = "time" if name in TIME_COLUMNS else "plain"
    return kinds


def _carried(row: Mapping[str, object]) -> dict[str, object]:
    return {"runOldId": row["run_id"], **{name: value for name, value in row.items() if name != "run_id"}}


def _is_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _relinked(name: str, value: object, ids: IdMap) -> object:
    """표시의 재판단 칸(실행 id)을 받는 쪽 새 id 로. 그 밖 칸·null 은 그대로."""
    if value is None:
        return None
    if name == BASIS:
        return ids.run_id(cast("int", value))
    if name == REJUDGES:
        return [ids.run_id(run) for run in cast("list[int]", value)]
    return value


def _received(rows: Sequence[Mapping[str, object]], ids: IdMap) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "run_id": ids.run_id(int(str(row["runOldId"]))),
            **{k: _relinked(k, v, ids) for k, v in row.items() if k != "runOldId"},
        }
        for row in rows
    )


def _check_rejudges(row: Mapping[str, object]) -> None:
    """꾸민 묶음의 재판단 칸을 쓰기 앞에서 거절(받은 rows 만 — DB 0). rejudge_run_ids 는 null 이거나 겹침 없는 양의
    정수 목록, evidence_basis_run_id 는 null 이거나 그 행의 rejudge_run_ids 안."""
    rejudges = row.get(REJUDGES)
    if rejudges is not None:
        if not isinstance(rejudges, list) or not all(_is_id(run) for run in cast("list[object]", rejudges)):
            raise CarrierRefused("그린워싱 표시의 rejudge_run_ids 가 양의 정수 목록이 아니다")
        listed = cast("list[int]", rejudges)
        if len(set(listed)) != len(listed):
            raise CarrierRefused("그린워싱 표시의 rejudge_run_ids 에 같은 실행이 둘 이상이다")
    basis = row.get(BASIS)
    if basis is not None and (not _is_id(basis) or basis not in cast("list[int]", rejudges or [])):
        raise CarrierRefused("그린워싱 표시의 evidence_basis_run_id 가 그 표시의 재판단 실행이 아니다")


def _swap(value: object, parts: Sequence[str], ids: IdMap) -> object:
    """value 의 경로(parts — 목록은 `[]`)에 있는 정수 실행 id 를 새 id 로 바꾼 사본. 자리가 없으면 그대로(영문번역
    carrier 의 같은 이름 함수와 같은 꼴 — 남의 모듈을 import 하지 않으려 따로 둔다)."""
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
    if isinstance(inner, int) and not isinstance(inner, bool):
        return {**fields, key: ids.run_id(inner)}
    raise CarrierRefused(f"묶음의 {key} 가 정수 실행 id 가 아니다")  # 꾸민 값(null·글자·소수·bool·목록)


def _rewritten(place: str, value: object, ids: IdMap) -> object:
    for path in ID_FIELDS.get(place, ()):
        value = _swap(value, path.split("."), ids)
    return value


def _without_unfinished(
    company_id: int, carried: set[int], marks: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    """내보낼 표시의 재판단 칸을 묶음에 맞춘다(감독 GCB1 §8 Q-B1 (가)+(나)). 묶음 밖 재판단 실행 가운데 done 이 있으면
    거절(기준 판단·count 가 바뀐다), failed·도는 중(·그 회사에 없음)은 목록에서 뺀다(done 재판단의 count·기준 판단은
    그대로 — 마지막 상태 줄만 앞 done 기준). 다 빠지면 null. 기준(evidence_basis_run_id)을 빼야 하면 거절. 쿼리 =
    묶음 밖 재판단이 있을 때 실행 1."""
    outside = {run for mark in marks for run in cast("list[int] | None", mark[REJUDGES]) or [] if run not in carried}
    status = (
        {run: found.status for run, found in run_selectors.runs_of(company_id=company_id, run_ids=outside).items()}
        if outside
        else {}
    )
    out: list[dict[str, object]] = []
    for mark in marks:
        listed = cast("list[int] | None", mark[REJUDGES])
        if not listed or not set(listed) & outside:
            out.append(dict(mark))
            continue
        done = [run for run in listed if run in outside and status.get(run) == "done"]
        if done:
            raise CarrierRefused(
                f"그린워싱 실행 {mark['run_id']} 의 재판단 실행 {done} 이 묶음에 없다 — 그 재판단 실행을 함께 고르라"
            )
        kept = [run for run in listed if run not in outside]
        if mark[BASIS] is not None and mark[BASIS] not in kept:
            raise CarrierRefused(f"그린워싱 실행 {mark['run_id']} 의 근거 기준 재판단 실행이 묶음에 없다")
        out.append({**mark, REJUDGES: kept or None})
    return out


class GreenwashCarrier:
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
        settings = self._settings.export_rows(company_id, run_ids, versions)
        for row in settings[SETTINGS]:
            criteria = row["criteria"]
            if not isinstance(criteria, dict) or criteria.get("version") != row["name"]:  # pyright: ignore[reportUnknownMemberType]
                raise CarrierRefused(f"그린워싱 판 {row['oldId']} 의 criteria.version 이 판 이름과 다르다")
        found = review_selectors.bundle_review_rows(company_id=company_id, run_ids=run_ids)
        marks = _without_unfinished(company_id, set(run_ids), found.marks)
        return {
            **settings,
            REVIEWS: [_carried(row) for row in found.reviews],
            MARKS: [_carried(row) for row in marks],
        }

    def referenced_runs(self, options: Mapping[str, object]) -> tuple[int, ...]:
        found = options.get(FROM_RUN)
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
            options=cast("Mapping[str, object]", _rewritten("options", dict(named.options), ids)),
            versions=named.versions,
            results=tuple((shape, _rewritten(shape, body, ids)) for shape, body in named.results),
            steps=tuple((name, _rewritten(f"step:{name}", data, ids)) for name, data in named.steps),
            partials=tuple(named.partials),
        )

    def import_settings(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]]
    ) -> Mapping[int, tuple[int, str]]:
        return self._settings.import_settings(company_id, user_id, rows)

    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None:
        # HD1 S3: 꾸민 묶음의 겹침·검토 없는 표시·정수 아닌 item_index 는 쓰기 앞에서 거절(받은 rows 만 — DB 0).
        # 아니면 제약(models.py 의 검토 (회사, 실행) · 표시 (회사, 실행, 항목))이 IntegrityError 날것으로 터진다.
        reviewed = [row["runOldId"] for row in rows.get(REVIEWS, [])]
        if len(set(reviewed)) != len(reviewed):
            raise CarrierRefused("그린워싱 검토가 같은 실행에 둘 이상이다")
        marked: set[tuple[object, int]] = set()
        for row in rows.get(MARKS, []):
            index = row["item_index"]
            if not isinstance(index, int) or isinstance(index, bool):
                raise CarrierRefused("그린워싱 표시의 item_index 가 정수가 아니다")
            if row["runOldId"] not in reviewed:
                raise CarrierRefused("그린워싱 표시가 검토 없는 실행을 가리킨다")
            if (row["runOldId"], index) in marked:
                raise CarrierRefused("그린워싱 표시가 같은 실행·항목에 둘 이상이다")
            marked.add((row["runOldId"], index))
            _check_rejudges(row)
        reviews = _received(rows.get(REVIEWS, []), ids)
        marks = _received(rows.get(MARKS, []), ids)
        if not review_services.import_review(company_id=company_id, rows=reviews, user_id=user_id):
            raise CarrierRefused("받는 회사에 같은 실행의 그린워싱 검토가 이미 있다")
        review_services.import_marks(company_id=company_id, rows=marks, user_id=user_id)

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]:
        return {
            **self._settings.columns(),
            REVIEWS: _kinds(review_selectors.REVIEW_BUNDLE_FIELDS),
            MARKS: _kinds(review_selectors.MARK_BUNDLE_FIELDS),
        }

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {
            **self._settings.id_fields(),
            **ID_FIELDS,
            REVIEWS: ("runOldId",),
            MARKS: ("runOldId", BASIS, f"{REJUDGES}[]"),
        }
