from django.apps import AppConfig


class DataverifyConfig(AppConfig):
    name = "esgapi.dataverify"
    label = "dataverify"

    def ready(self) -> None:
        # 흐름을 코어의 레지스트리에 단다. 코어는 dataverify 를 모른다(.importlinter 계약 가) — 등록은 여기서만.
        # 전역 앱의 ready 에서만 단다: isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리도 ready 를 부른다(Django 5.2).
        from django.apps import apps as global_apps

        if self.apps is not global_apps:
            return
        from esgapi.core.flows.binding import BINDINGS, DOCUMENTLESS_OPTIONS_MAX_OCTETS
        from esgapi.core.flows.registry import REGISTRY
        from esgapi.dataverify.flows import colab_156, registration
        from esgapi.dataverify.flows.binding_156 import DataverifyBinding
        from esgapi.dataverify.service.selectors.ai_settings import RunModelSource, RunSettingStore

        registration.register(REGISTRY)
        # 문서 없는 흐름(ND1) — 옵션 상한은 등록 인자다(EDK 입력 한 건이 다른 흐름의 16KiB 를 넘는다)
        # 판 읽기·모델 원천(DVA1 ③)은 기본값 없이 꽂는다(빠지면 조용히 기본 판이 되는 길 0)
        BINDINGS.register_documentless(
            colab_156.FLOW_ID,
            DataverifyBinding(settings=RunSettingStore(), models=RunModelSource()),
            max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS,
        )
        from esgapi.dataverify.service.selectors.run_extras import RunSettingExtras
        from esgapi.runs.extras import EXTRAS

        EXTRAS.register("dataverify", RunSettingExtras())  # 운영 관리자 실행 기록의 AI 설정 칸
        from esgapi.core.flows.carriers import CARRIERS, SettingCarrier
        from esgapi.dataverify.service.selectors.ai_settings import AiSetting, ai_setting_detail
        from esgapi.dataverify.service.services.ai_settings import import_setting

        CARRIERS.register(  # 실행 묶음의 AI 설정 판(RX1b — 판 말고 실을 행·다시 쓸 id 0, ★b)
            "dataverify",
            SettingCarrier(
                table="dataverify_ai_settings",
                shape=AiSetting,
                read_settings=ai_setting_detail,
                insert_setting=import_setting,
            ),
        )
