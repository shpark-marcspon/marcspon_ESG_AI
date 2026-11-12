"""이미 있는 회사마다 본사 하나(데이터 이전). 밴드 K1b-1 ①(결정 MARC-ENT-469, 감독 판단 4).

회사마다 삭제 안 된 본사가 없으면 — 삭제 안 된 「본사」 이름 사업장이 있으면 그 행을 본사로 올리고(인벤토리 켬),
없으면 「본사」·인벤토리 켬·본사로 하나 만든다. 이미 본사가 있는 회사는 그대로다(두 번 돌려도 하나).
새 회사의 본사는 seed_company 가 services 의 ensure_headquarters 로 세운다 — 규칙이 같다(시험이 견준다).
역사 모델로 돈다(코드의 모델·매니저를 import 하지 않는다 — 이 문면이 적용된 DB 의 규칙으로 남는다).

되돌림(0003 → 0002)은 본사 표시만 걷는다 — 행은 지우지 않는다(앱 역할에 DELETE 가 없는 것과 같은 뜻. 만든 「본사」 행은
보통 사업장으로 남는다).
"""

from typing import Any

from django.db import migrations

HEADQUARTERS_NAME = "본사"  # 문면에 굳힌다(services 의 HEADQUARTERS_NAME 과 같아야 한다 — 시험이 견준다)


def seed_headquarters(apps: Any, schema_editor: Any) -> None:
    company_model = apps.get_model("organization", "Company")
    site_model = apps.get_model("organization", "Site")
    for company_id in company_model.objects.order_by("id").values_list("id", flat=True):
        alive = site_model.objects.filter(company_id=company_id, deleted_at__isnull=True)
        if alive.filter(is_headquarters=True).exists():
            continue
        named = alive.filter(name=HEADQUARTERS_NAME).order_by("id").first()
        if named is not None:
            named.is_headquarters = True
            named.inventory_enabled = True
            named.save(update_fields=["is_headquarters", "inventory_enabled", "updated_at"])
        else:
            site_model.objects.create(
                company_id=company_id, name=HEADQUARTERS_NAME, is_headquarters=True, inventory_enabled=True
            )


def unmark_headquarters(apps: Any, schema_editor: Any) -> None:
    site_model = apps.get_model("organization", "Site")
    site_model.objects.filter(is_headquarters=True).update(is_headquarters=False)


class Migration(migrations.Migration):
    dependencies = [
        ("organization", "0002_branches_facilities"),
    ]

    operations = [
        migrations.RunPython(seed_headquarters, unmark_headquarters),
    ]
