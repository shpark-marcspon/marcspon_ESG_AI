"""시험용 AI 설정 판 포트(flows/binding_e0.AiSettingStore) 둘 — 순수(DB 0). 판·기준 글은 지어낸 것이다.

DefaultOnlyStore()           어느 회사든 적용 판 없음(기본 판), get 은 늘 없음 — G1b 때의 시험이 그대로 돈다
FakeStore(saved, applied)    회사 → 판 목록·적용 판 id 를 손으로 든 것. 부른 것을 calls 에 적는다
"""

from dataclasses import dataclass, field

from esgapi.greenwash.flows.binding_e0 import DefaultSetting, SavedSetting, SettingNotFound


class DefaultOnlyStore:
    def applied(self, company_id: int) -> SavedSetting | DefaultSetting:
        return DefaultSetting()

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound:
        return SettingNotFound(setting_id)


@dataclass
class FakeStore:
    saved: dict[int, list[SavedSetting]] = field(default_factory=dict[int, list[SavedSetting]])
    applied_id: dict[int, int] = field(default_factory=dict[int, int])
    calls: list[tuple[str, int, int | None]] = field(default_factory=list[tuple[str, int, int | None]])

    def applied(self, company_id: int) -> SavedSetting | DefaultSetting:
        self.calls.append(("applied", company_id, None))
        wanted = self.applied_id.get(company_id)
        found = next((s for s in self.saved.get(company_id, []) if s.id == wanted), None)
        return DefaultSetting() if found is None else found

    def get(self, company_id: int, setting_id: int) -> SavedSetting | SettingNotFound:
        self.calls.append(("get", company_id, setting_id))
        found = next((s for s in self.saved.get(company_id, []) if s.id == setting_id), None)
        return SettingNotFound(setting_id) if found is None else found
