"""그린워싱 점검. 흐름 greenwash.colab@E0 — 마크스폰 Colab 노트북을 옮긴 esg-lab GW1 을 단계 여섯으로 끊어 돈다.

축 다섯(MARC-ENT-267). 자세한 지도와 규칙은 README.md.
engines/e0/  엔진: GW1 사본 열(AST 고정, checker.py 의 GL1 꼭지 밖은 고치지 않는다) + gw1.py·result.py
contracts/   계약: result@1·review@2·compare@1·terms-default 꼴과 snake → camel 사상(wire)
tools/       판 무관 도구: 정규화, PDF 읽개, pdfium 좌표, core.llm 대화 호출, 포트
outputs/     출력: 결과 꼴에서만 짓는 엑셀·수정본 비교
flows/       흐름: colab_e0.py(단계 여섯·어댑터 꼴·E0 묶인 구현), registration.py — 엔진과 계약을 잇는 유일한 자리
prompts/     core.llm 템플릿 넷(greenwash/{detect,eval,repair,low-only}@1 — 노트북 글을 변수로 넘긴다)
apps.py      ready() 가 흐름을 전역 레지스트리에 달고 기본 흐름으로 정한다
"""
