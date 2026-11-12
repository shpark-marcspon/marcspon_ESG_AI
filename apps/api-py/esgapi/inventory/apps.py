from django.apps import AppConfig

from esgapi.core.conf import app_config


def scope3_runs_enabled() -> bool:
    """Scope 3 코랩 실행을 받는가(환경 변수 INVENTORY_SCOPE3_RUNS_ENABLED — Config 로만 읽는다, MARC-ISSUE-499)."""
    return app_config().inventory_scope3_runs_enabled


class InventoryConfig(AppConfig):
    name = "esgapi.inventory"
    label = "inventory"

    def ready(self) -> None:
        # 흐름을 코어의 레지스트리에 단다. 코어는 inventory 를 모른다(.importlinter 계약 가) — 등록은 여기서만.
        # 전역 앱의 ready 에서만 단다: isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리도 ready 를 부른다(Django 5.2).
        from django.apps import apps as global_apps

        if self.apps is not global_apps:
            return
        from esgapi.core.flows.registry import REGISTRY
        from esgapi.inventory.flows import registration

        registration.register(REGISTRY)
        from esgapi.core.flows.binding import BINDINGS
        from esgapi.core.flows.carriers import CARRIERS, NO_ROWS
        from esgapi.inventory.flows.binding_157 import FLOW_ID, Scope3ColabBinding
        from esgapi.inventory.service.utils import scope3_files

        # Scope 3 코랩 흐름의 끼움(밴드 S3K1) — 계수 책 바이트와 실행 스위치 포트를 꽂는다(끼움은 파일·설정을 모른다)
        BINDINGS.register(
            FLOW_ID, Scope3ColabBinding(factor_book=scope3_files.FACTOR_BOOK, runs_enabled=scope3_runs_enabled)
        )
        # S3K2a: inventory_scope3_categories(잠금 핀)도 싣지 않는다 — 핀은 실행 id 라 옮기면 어긋남, 가져온 뒤 다시 잠금
        # S3K2b: inventory_scope3_row_edits 도 싣지 않는다 — 실행 id 에 매여 옮기면 어긋남(570: 새 실행에 안 따라옴)
        CARRIERS.register("inventory.scope3", NO_ROWS)  # 실행 묶음: 실을 모듈 행·다시 쓸 id 0(options 는 reportYear 뿐)
