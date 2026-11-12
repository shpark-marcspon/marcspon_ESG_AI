"""AI 설정 판에 모델 설정 칸 하나 — greenwash_ai_settings.model_settings(jsonb NOT NULL). 밴드 AS2b ① (결정 MARC-ENT-353,
이슈 MARC-ISSUE-240).

칸은 판의 모델 설정 정규형(ai.model-settings@1 — core/calc/ai_settings.to_input(check_model_settings(…)))이다. 이행 전에
있던 행은 그때의 코드 값(그린워싱 판정 단계의 기본값 — flows/prompt_model_e0.JUDGE.default 를 받은 정규형)으로 채운다:
AddField 의 default 는 기존 행을 채우는 데만 쓰고 칸에 남기지 않는다(preserve_default=False — RunPython 0).
★ 상수는 이 파일 안의 글자다(코드 import 0) — 코드 값이 뒤에 바뀌어도 이행이 채운 값은 그대로다. 같은 값인지는
  tests/flows/test_prompt_model_e0.py 가 지금 코드 값과 견준다.
GRANT 그대로: 앱 역할에게 표 단위 SELECT·INSERT(새 칸도 든다)와 칸 단위 UPDATE (applied, applied_at) 뿐 — 새 칸은
UPDATE 권한 밖이다(판은 불변 행, 마이그레이션 0002). 이행은 주인 역할이 돈다.
★ 되돌림(0003 → 0002)은 칸을 지운다 — 저장한 모델 설정을 잃는다. 운영 DB 에서 하지 않는다(MARC-ISSUE-257 3번).
"""

from typing import Final

from django.db import migrations, models

MODEL_SETTINGS_BEFORE_AS2B: Final = {
    "steps": [
        {"key": "judge", "route": "light-openai-41", "temperature": 0.0, "webSearch": False, "maxOutputTokens": 1300}
    ]
}


class Migration(migrations.Migration):
    dependencies = [
        ("greenwash", "0002_ai_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="greenwashaisettingrow",
            name="model_settings",
            field=models.JSONField(default=MODEL_SETTINGS_BEFORE_AS2B),
            preserve_default=False,
        ),
    ]
