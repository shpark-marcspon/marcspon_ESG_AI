"""AI 온실가스 인벤토리. 지금 있는 것: Scope 1·2 와 Scope 3 의 순수 엔진, 흐름 셋, 저장 없는 경로 셋. 지도는 README.md.

engines/         엔진(순수). 흐름마다 폴더, 그 아래 판마다 폴더: scope12/engine_1/(esg-lab ts/kernel·ts/ghg-calc
                 를 옮김), scope3/llm_first_1/(esg-lab ts/scope3/src/domain), scope3/colab_157/(받은 Scope 3 코랩
                 MARC-ENT-157 의 C1·C2). Django·ninja·DB 를 모른다
                 (.importlinter 계약 다)
contracts/       계약: 결과 꼴 셋(scope12.result@2 · scope3.llm-first.result@2 · scope3.colab.result@1)의 TypedDict.
                 엔진을 모른다
tools/           판과 무관한 도구. tools/jsrepr.py 는 JS 문자열 흉내, tools/xlsx_reader.py 는 xlsx 바이트 → 읽힌 표
                 (xlsx 를 여는 것은 여기뿐), tools/scope3_sheets/ 는 읽힌 표의 값·계수 책 적재기·드롭다운·어긋남 검사
                 (순수. 저장도 경로도 없다)
flows/           흐름(순수): scope12.engine@1 · scope3.llm-first@1 · scope3.colab@157. 엔진과 계약을 잇는 것은 여기뿐.
                 등록은 apps.py 의 ready. Scope 3 의 기본은 scope3.colab@157(끼움 binding_157 — 실행기가 돌린다)
data/            패키지에 실린 기준정보 표(환산, GWP 세트 둘, 표본 계수 셋). 출처는 data/README.md. data/scope3/ 는
                 받은 Scope 3 빈 양식·계수 책 xlsx 둘(읽는 것은 service/utils/scope3_files.py)
data_loader.py   그 표를 읽는다(파일을 읽는 것은 여기뿐. 엔진 Scope 1·2 에 묶인 적재기)
api.py           라우터를 다시 내보내는 한 줄(config/api.py 가 여기서 들인다)
service/         경로와 그 꼴: apis/inventory.py · schemas/inventory.py · services/inventory.py
                 actions/scope3_shortlist.py 는 도메인을 넘는 조립이다(reference 의 Selector + 여기의 Service)
                 · */scope3_state.py 는 Scope 3 연도 상태·카테고리 잠금(S3K2a — 지금 결과는 읽을 때 셈)
                 · */scope3_edits.py 는 Scope 3 줄 덧판(S3K2b-1 — 실행에 매인 불변 사건, 새 실행에 안 따라옴)
                 · utils/scope3_factors.py 는 계수 수정의 셈(S3K2b-2 — 엔진 식을 다시 적음, AI 안 부름)
prompts/         Scope 3 의 템플릿(core 규약 prompts/<이름>/<판>.md)
tests/           순수 층 + 업무 층(test_api.py). tests/data 는 시험 자료(검산 사례, 가상 계수, 골든)

없는 것: models.py(저장하지 않는다), outputs/(엑셀 쓰기), 한국 지침의 계수 전량(reference 모듈), Scope 3 의
추천·파이프라인 경로와 임베딩(경로는 scope3/shortlist·scope3/classify 둘이 있다).
"""
