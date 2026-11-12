"""모듈들이 같이 쓰는 순수 규칙. django·ninja·psycopg 를 import 하지 않는다(`.importlinter` 계약 다의 `esgapi.*.calc`).

decimal.py   십진 정확 연산 (coef, scale). inventory 와 reconcile 이 쓴다
guards.py    불리언을 정수 칸에서 거르는 것(reject_bool · NotBool)
ids.py       회사 id 의 꼴(is_company_id). core 의 토큰·세션·격리 매니저·저장소 키가 쓴다
ai_settings.py  모듈 공통 AI 설정의 받기·능력·sha·부품·모듈 선언·조합·판 규칙(꼴은 contracts/ai_setting_shapes.py)
"""
