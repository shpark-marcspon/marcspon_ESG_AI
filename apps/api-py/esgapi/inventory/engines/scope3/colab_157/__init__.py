"""Scope 3 코랩 흐름 `scope3.colab@157` 의 엔진 판(순수 — Django·DB·파일·네트워크·시계를 모른다).

출처: 받은 Scope 3 코랩 생물기원 적용판(`MARC-ENT-157`). 옮긴 원천은 읽기판
`received-derived/2026-10-15/Scope 3 코랩/Scope3_생물기원적용_.md` 하나(원본 노트북 sha1
`9801d39dab29837a9bbd157004bee61d723f8a0e`, 2026-10-15 대외·자료 트랙이 뽑음). 줄 번호(`:n`)는 그 읽기판의 것이다.
노트북 파일·실행 출력·받은 자료 파일은 옮기지 않았다. 1차 기준은 「코랩과 같게」(`MARC-ENT-196`) —
다르게 짠 자리는 밴드 보고 `band-reports/S3C-a-colab.md` 의 「코랩과 다른 자리」 표.

코랩 셀 → 이 파일:
    셀 5 `_to_numeric_ignore`, 셀 8·9 계수 책 읽기, 셀 26 보고연도 원화 열   → factor_book.py
    셀 7 Claude 부르기의 글 해석, 셀 20 `safe_json_loads`                     → llm.py
    셀 19 템플릿 시트 읽기, 셀 23 열 정리·시트 대응, 셀 24 읽기 패치          → template.py
    셀 20·22·23·26·27 의 C1·C2 셈(표준화·그룹·후보 순위·옛 추천·후처리)      → purchase.py
    `run_scope3_pipeline`·`process_new_template` 의 시트 갈래                 → pipeline.py
    결과 꼴 scope3.colab.result@1 의 dict                                      → serialize.py
    셀 20·21·22·23·27 의 규칙표·상수                                          → constants.py
    `pd.read_excel` 의 자리(우리 읽개의 `Workbook` → DataFrame)              → frames.py
    pandas 2.x 와 3.0.6 이 다르게 도는 자리                                   → pdcompat.py
    셀 8·25 지출·폐기물 계수 시트 셋(두 단 읽기)                              → factor_book.py
    셀 3·25·26·27 운송·출장 Spend 계수 찾기                                    → spend.py
    셀 8 폐기물 계수 찾기·처리방법·생물기원                                    → waste.py
    셀 20 무게 단위 환산과 AI 배수(`:3809`·`:3997`)                           → units.py
    셀 13·27 이동수단 정규화(`:1384`·`:8534`)                                  → travel_mode.py
    셀 23 회사별 매핑 폴백(`:6326`)                                            → company_mapping.py
    지출·폐기물·거리 줄 메타·산정 출처·월 합(`:5928`), C4/C9 거리 갈래(`:6008`) → activity.py
    바깥에 기대는 자리(생성 모델·지오코더)                                    → ports.py
    셀 11·12·13·15 거리 길(도시 정규화·지오코더·직선·AI 거리·공항, `:1044`~`:1709`) → distance.py
    셀 22·27 거리기반 운송(운송수단·무게·운송 계수 맵·표준화·셈, `:6435`~`:7780`) → transport.py
    셀 10·22·27 출장·통근 거리(표준화·셈·출장 계수 맵, `:438`~`:8859`)              → travel.py
    셀 8·20·24·25·27·29 에너지 계수 사슬·C3 계수·에너지 단위 환산, C3·C8·C13 표준화·셈
        (`:479`~`:9171` — S3C-c1a)                                                   → energy.py
    셀 8·24·28 판매제품 폐기(C12 표준화·코드 계수·생물기원 `:365`~`:9014`)·투자(C15 `:5610`) — S3C-c1b-1 → product.py
    셀 24·25·27 판매제품 사용(C11 `:6961`·`:7613`·`:8720`)·프랜차이즈(C14 `:5590`·`:7623`·`:8862`)와
        결과 후처리 차례(`:8878`) — S3C-c1b-2                                         → product.py·pipeline.py
    셀 23 결과 파일 쓰기(`:6205-6246`)·셀 27 결과 후처리 다시 쓰기(`:8878`)·셀 30 채운 템플릿(`:9178-9469`)의
        내용(시트·열·줄 값, 회색 칸 쓰기) — S3C-c2(바이트는 시험 덤프가 openpyxl 로)         → output_files.py

옮기는 규칙:
- 코랩은 뒤 셀이 앞 함수를 다시 정의한다. **마지막 정의가 이긴다.** 다만 `_ORIGINAL_*_FULL_FIX = globals().get(…)`
  처럼 그때의 옛 정의를 붙잡아 부르는 사슬이 있다: `:8428-8430`(옛 `get_spend_recommendations`
  `:3161`·`select_primary_spend_candidate` `:3204`·`search_spend_ef` `:2857`), `:8914`(옛 `process_new_template`
  `:5898`), `:6540`(옛 `read_template_sheet` `:2128`). 붙잡은 옛 함수는 그 판 그대로 옮기고, 새 판이 그것을 부르는
  자리도 그대로 둔다.
- **늦은 묶임**(개정 1 N3): 붙잡은 옛 함수 안의 전역 이름은 부를 때의 마지막 정의로 풀린다(예: 옛 `:3204` 가 부르는
  `search_spend_ef`·`get_spend_recommendations` 는 `:8449`·`:8433` 판). 옮길 때 옛 함수 본문의 부름도 마지막 판으로
  잇는다.
- 코랩의 전역 상태(`spend_db`·`FX_REFERENCE_YEAR`·`lru_cache`)는 실행 하나의 값(인자)으로, `print` 는 결과의 갈래로
  바꾼다.
- 옮긴 코랩 코드의 `astype(str)`·`.fillna(` 는 모두 `pdcompat` 도우미를 거친다(시험이 AST 로 문다).
- 판끼리 서로 모른다: `llm_first_1` 을 import 하지 않는다(간접도 — `.importlinter` 의
  `inventory-scope3-versions-apart`).
"""
