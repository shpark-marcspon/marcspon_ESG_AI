from django.apps import AppConfig


class MaterialityConfig(AppConfig):
    name = "esgapi.materiality"
    label = "materiality"

    def ready(self) -> None:
        # 흐름을 코어의 레지스트리에 단다. 코어는 materiality 를 모른다(.importlinter 계약 가) — 등록은 여기서만.
        # 전역 앱의 ready 에서만 단다: isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리도 ready 를 부른다(Django 5.2).
        from django.apps import apps as global_apps

        if self.apps is not global_apps:
            return
        from esgapi.core.flows.binding import BINDINGS, DOCUMENTLESS_OPTIONS_MAX_OCTETS
        from esgapi.core.flows.registry import REGISTRY
        from esgapi.materiality.flows import iro_155, registration
        from esgapi.materiality.flows.binding_155 import MaterialityBinding
        from esgapi.materiality.service.selectors.ai_settings import RunModelSource, RunSettingStore

        registration.register(REGISTRY)
        # 문서 없는 흐름(ND1) — 1부 → 2부 한 실행 하나만 끼운다(1부 단독 colab@155 는 REGISTRY 에만, IR3a 처분 ⑧).
        # 옵션 상한은 등록 인자다(코랩 크기 입력이 한글 설명·가치사슬로 16KiB 근처에 닿는다)
        # 판 읽기·모델 원천(IR4 ③)은 기본값 없이 꽂는다(빠지면 조용히 기본 판이 되는 길 0)
        BINDINGS.register_documentless(
            iro_155.FLOW_ID,
            MaterialityBinding(settings=RunSettingStore(), models=RunModelSource()),
            max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS,
        )
        from esgapi.materiality.service.selectors.run_extras import RunSettingExtras
        from esgapi.runs.extras import EXTRAS

        EXTRAS.register("materiality", RunSettingExtras())  # 운영 관리자 실행 기록의 AI 설정 칸
        from esgapi.core.flows.carriers import CARRIERS, SettingCarrier
        from esgapi.materiality.service.selectors.ai_settings import AiSetting, ai_setting_detail
        from esgapi.materiality.service.services.ai_settings import import_setting

        CARRIERS.register(  # 실행 묶음의 AI 설정 판(RX1b — 판 말고 실을 행·다시 쓸 id 0, ★b)
            "materiality",
            SettingCarrier(
                table="materiality_ai_settings",
                shape=AiSetting,
                read_settings=ai_setting_detail,
                insert_setting=import_setting,
            ),
        )
