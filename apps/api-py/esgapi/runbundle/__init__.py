"""실행 묶음(RX1a, MARC-ENT-440): 한 회사의 끝난 실행을 zip 하나로 내보내고(export_runs) 다른 DB 의 회사에 새 id 로
넣는다(import_runs). 모델 0 — runs·core·organization·user 는 selectors·services 로만, 모듈은 등록부 CARRIERS 로만 닿는다
(.importlinter 계약 카).

    calc/bundle.py   묶음 꼴 esg.run-bundle@1: 머리·행의 칸·JSON 값·zip 항목(순수)
    calc/idmap.py    옛 id → 새 id 지도와 열쇠 짓기, versions 의 aiSettingId 다시 쓰기(순수)
    calc/gate.py     받는 쪽의 문(Q5): 흐름·꼴·단계, 칸, 마이그레이션 잎(순수)
    service/actions  export·import_(블록·차례)·_pg(날 SQL 두 문장)
    management       export_runs·import_runs(운영자 명령 — 화면·경로 0)
"""
