"""읽기. 실행 묶음(RX1a — runbundle 앱의 export_runs)이 싣는 LLM 호출 기록의 행
(표 core_llm_call_logs). 쓰지 않는다.

    rows_of_runs(company_id, run_ids)   그 회사의 줄 가운데 run_id 가 run_ids 안인 것, id 뺀 칸 전부(id 오름). 한 쿼리

회사 범위는 LlmCallLogRow.for_company(company_id) 하나다 — 남의 회사 줄은 같은 run_id 값이어도 안 실린다(run_id 는 외래
키가 아니다 — core/models.py). 본문 칸은 표에 없다(공시 전 고객 데이터 — 싣지 않는 것이 아니라 없다).
무효 조건: run_ids 가 수만이 되면 run_id__in 이 psycopg 매개 상한(65,535)에 닿는다(내보내기 상한 --max-runs 기본 200).
"""

from collections.abc import Collection

from esgapi.core.models import LlmCallLogRow


def rows_of_runs(*, company_id: int, run_ids: Collection[int]) -> list[dict[str, object]]:
    """칸 이름(attname) → 값. company_id·run_id 칸은 그대로 싣는다(지우고 바꾸는 것은 부르는 쪽 — 묶음의 꼴)."""
    if not run_ids:
        return []
    rows = LlmCallLogRow.for_company(company_id).filter(run_id__in=run_ids).order_by("id").values()
    return [{name: value for name, value in row.items() if name != "id"} for row in rows]
