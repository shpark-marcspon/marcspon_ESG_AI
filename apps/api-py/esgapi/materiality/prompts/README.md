# materiality 프롬프트 — 출처

글의 정본은 `engines/colab_155/prompts.py`(함수·상수)와 `engines/colab_155/whitelists.py`(규제 system [8] 판 셋)다.
엔진 글 칸 열일곱은 `engines/colab_155/texts.py` 의 `PromptTexts`(AI 설정 판 칸은 그중 열넷 — 1부 가변 입력 셋은 늘 기본 글, 밴드 IRA3)이고 기본 글 `DEFAULT_TEXTS` 는 위 상수에서
짓는다(가변 글 = f-문자열 몸을 자리 글자로 바꾼 날 글 `*_USER_RAW`, 규제 system = 판을 뗀 틀 `REGULATION_SYSTEM_TEMPLATE` —
그 렌더가 아래 지문과 같은 글을 낸다). 저장 판은 이 글을 갈음할 뿐 이 파일의 지문은 기본 글의 것이다.
호출마다 (system, user 접두, user 가변) 셋을 돌려준다(코랩 셀 8 러너의 input 세 메시지).

core.llm 템플릿 셋은 봉투만 갖는다: `=== system ===\n{{system}}\n=== user ===\n{{user}}\n`(dataverify `prompts/` 꼴). core
`parse_template` 이 user 구획 둘을 거절하고(`core/llm/prompts.py`) 요청의 user 가 하나라서, 흐름(`flows/colab_155.py`)이
변수 `system` 에 system 글을, `user` 에 접두 + `USER_JOIN`(`"\n\n"`) + 가변을 넘긴다(IR1b 처분 ② 가 — 코랩은 user
메시지 둘). 봉투는 넘긴 글을 한 바이트도 바꾸지 않는다(구획 strip 은 템플릿 몸에만, 치환은 한 번만 — 값 안의 `{{` 그대로).

| 프롬프트 id | system | user 접두 · 가변 |
|---|---|---|
| `materiality/regulation@1` | `regulation_system(판)` | `REGULATION_USER_PREFIX` · `regulation_user` |
| `materiality/keywords@1` | `KEYWORDS_SYSTEM` | `KEYWORDS_USER_PREFIX` · `keywords_user` |
| `materiality/controversy@1` | `CONTROVERSY_SYSTEM` | `CONTROVERSY_USER_PREFIX` · `controversy_user` |

## 원천 블록(받은 중대성평가 IRO 코랩, `MARC-ENT-155` 읽기판)

블록 sha256 은 읽기판 줄을 `\n` 으로 이은 것이다. `scripts/section4-IR1a.sh` 7단계가 실행 때 읽기판에서 다시 재어 견준다.

| 이름 | 파일 | 원천 | 블록 sha256 |
|---|---|---|---|
| `regulation_system` | prompts.py | 셀 17 system_prompt R/413-728 | `c8eee757af4b082c00ad4d15f21a2f47755b709f76aa38e3d1115505e61d7a30` |
| `REGULATION_USER_PREFIX` | prompts.py | 셀 17 SPECIFIC_USER_PREFIX R/733-756 | `22f3013caa3b7295d980d7e2259d582f0da66a2fa30625524b32cd5b0ac62a7e` |
| `regulation_user` | prompts.py | 셀 17 build_specific_user_prompt R/758-768 | `209ecf017a8aaaf7a0804e3e4dd687dbb7dd92f2f10c7aaa2b15f426425e1459` |
| `KEYWORDS_SYSTEM` | prompts.py | 셀 20 system_prompt R/827-833 | `bc60012e0ba4a709ec0943913f098e7c3afc71c4c602bc110e9743424ccc517a` |
| `KEYWORDS_USER_PREFIX` | prompts.py | 셀 20 USER_PREFIX R/835-857 | `812c54ea50e500a10b411572dfece49943adb7d04a23b814e647d9985ef4b698` |
| `keywords_user` | prompts.py | 셀 20 build_user_prompt R/859-866 | `49d21656e53a5fad05266560d852c82c642df77b06398524b966258b29b30736` |
| `CONTROVERSY_SYSTEM` | prompts.py | 셀 22 system_prompt R/966-1047 | `67804adb69e27a2e3c091c09f2313bf1ddc6e9216beb9cbbd8f7163e81f8e137` |
| `CONTROVERSY_USER_PREFIX` | prompts.py | 셀 22 SPECIFIC_USER_PREFIX R/1051-1057 | `666629da25925a682ebd6c3416e8a53f6dd96e6681f932df3b237e3d722f35b1` |
| `controversy_user` | prompts.py | 셀 22 build_specific_user_prompt R/1060-1072 | `18995d585b26aea0e6b421f583a04d4bb551a6bef8566ee9fc9a006aa34d5d25` |
| `WHITELIST_COLAB17` | whitelists.py | 셀 17 [8](대조 전용) R/573-652 | `3134b7cd80386ae681c5cb59fa4590ad3df78a1eaffa34c335a03e0598f4698a` |
| `WHITELIST_CELL71` | whitelists.py | 셀 71 금융권 R/3677-3752 | `5830251560e35e936badcd88938fc399393427dccb790b0a8fd0bbd626f024a5` |
| `WHITELIST_CELL73` | whitelists.py | 셀 73 비금융권 R/3764-3843 | `79b3371aa262416c481c3ed64e2a3cd62b18f6eed51a9c470489aeca4cb470e6` |

## 바꾼 자리(코랩과 다른 자리)

- 셀 전역이던 값을 인자로 받는다: 셀 20 가변 글의 `topics`, 셀 17·22 의 `industry_text`·`industry`·`location`·`main_language`.
- 규제 system 은 `_REGULATION_SYSTEM_HEAD`(R/414-572) + [8] 판 + `_REGULATION_SYSTEM_TAIL`(R/653-728) 을 dedent 한다(셀 69
  「[8] 에 붙여넣어 변경」의 흉내). 셀 17 현행 판을 끼우면 코랩 system_prompt 와 바이트 같다. 고르는 판은 sector 로
  셀 71·73(발주서 처분 ⑥ 가) — 셀 17 현행 판은 코랩 예시 실행용이라 대조 전용.
- 셀 73 의 머리 지시 주석과 빈 줄(R/3762-3763)은 프롬프트 글이 아니라 뺐다.
- 그 밖의 글자(약점 W3 `{{`·W4 들여쓰기·W5 괄호 오타 포함)는 그대로다. 함수 서명만 ruff format 이 줄을 나눴다(글은 같다).

## 낸 글 지문

`tests/engines/colab_155/test_prompts.py` 의 지어낸 입력(산업 1개·3개)으로 낸 글의 sha256. 값은 이 판의 엔진이 낸 글에서
쟀고, 그 글이 코랩과 바이트 같음은 section4 7단계(COLAB_DIFF=0)가 같은 꼴의 입력으로 보인다.

| 글 | sha256 |
|---|---|
| `regulation_system[colab17]` | `3859b782af101572ce36ea1e6181aa60093b4fa5cc9a4016d676aeb0c8b25d6f` |
| `regulation_system[cell71]` | `b1d93f58597a5b392ae532289fab4244fd2804b6616c1ab2496d2833eeb66c6e` |
| `regulation_system[cell73]` | `5829e289872cc8e5ae45041261f1dfc01fe246674def2ccd2286722172228686` |
| `REGULATION_USER_PREFIX` | `a745effeed072b9c9ac899ea6d5203f7f232b9e26d499f804bce2cf8b73c94c4` |
| `regulation_user[1]` | `4722711fca8e3f926d182966472657b94fe08cef3722b0a6260356455560892e` |
| `regulation_user[3]` | `f5c5e203472e18495f087f13c1eade9470fc3354a648e1960e8f27699332919c` |
| `KEYWORDS_SYSTEM` | `626b487269656c22a7f753bae6feed24f55b4ab0e6814d49f0f6ad121ac69d49` |
| `KEYWORDS_USER_PREFIX` | `2f3f3c7334fc076f5796a86ddcded5ecaa75c3c1afd73ee4460e4f6596d7184b` |
| `keywords_user[1]` | `2ea154d10cfdf49d5a48cc45540113857b2ebbe3004232ec6bbcbb78d0329a40` |
| `keywords_user[3]` | `675fb57b78f6bbdadb9bf4183ce5b693edff96212b4e6eb19b87495562591c4f` |
| `CONTROVERSY_SYSTEM` | `1d5604d6121fa94c841a71cb3639d8d19b1ab40443bede82a953d6257133a602` |
| `CONTROVERSY_USER_PREFIX` | `cbf5ee359424c709c0b6280993c347450de4425aa64ca1a1541b5c13859372d7` |
| `controversy_user[1]` | `5fa1b72514356fba7476218061640eff6c2c3ff13860f9dd08e1738541230c7a` |
| `controversy_user[3]` | `66b199e56f7ab9a8c391368e504c15a70ab373f5d0a305937051bc54c6e0b715` |

무효 조건: 읽기판이 다시 뽑히면(원본 sha1 이 바뀌면) 위 블록 sha256 과 줄 번호를 다시 잰다.

## 2부(밴드 IR2a — 셀 46·50·55, `MARC-ENT-425` ②)

글의 정본은 `engines/colab_155/part2_prompts.py`(상수·함수), 토픽별 글과 Pathway 입력 표는 `engines/colab_155/part2_render.py`
다. 호출마다 (system, user) 둘이다(코랩 2부 러너 `subtopic_impactdef_prompt` 의 input 두 메시지 — user 하나라 봉투에
그대로 맞는다). 봉투 `prompts/{impact,financial,pathway}/1.md` 는 1부와 같은 꼴이다(경계 ③).

| 프롬프트 id | system | user |
|---|---|---|
| `materiality/impact@1` | `IMPACT_SYSTEM` | `impact_user` |
| `materiality/financial@1` | `FINANCIAL_SYSTEM` | `financial_user` |
| `materiality/pathway@1` | `PATHWAY_SYSTEM` | `pathway_user`(입력 표 = `part2_render.pathway_table`) |

### 원천 블록(읽기판, 블록 sha256 은 줄을 `\n` 으로 이은 것)

| 이름 | 원천 | 블록 sha256 |
|---|---|---|
| `IMPACT_SYSTEM` | 셀 46 system_prompt_subtopic_impact R/2146-2271 | `71c82595977ef872e76affbfa30e8a2af9ea532fc81dd75450da9df8bd5a1357` |
| `impact_user` | 셀 46 user_input R/2304-2327 | `4e28433192250da8ccaf0df89fd439f00f437dd5fd084f845251836e3f38af98` |
| `FINANCIAL_SYSTEM` | 셀 50 system_prompt_subtopic_impact R/2418-2581 | `6f1fb931884d80ca7836303910cce4def1324190a43cabf2c1bea5855abd51c3` |
| `financial_user` | 셀 50 user_input R/2624-2646 | `ab1f4653194f0b6a318e3a8ac98adb95cb0b2247a85529c525ae8e535772442d` |
| `PATHWAY_SYSTEM` | 셀 55 system_prompt_fin_impact_pathway R/3003-3106 | `d3e51b719d8ca4bd7ac563372523cb07b19138a5c772fcdc5afb91f715af953a` |
| `pathway_user` | 셀 55 user_input R/3141-3154 | `7587e3503638f6ff2a130ba387764ce204f4ce87a1d8db5fbea64fd581b18f3c` |
| (JSON 절의 본) | 셀 50 [FINAL OUTPUT — JSON ONLY] R/2527-2580 | `6aad501cb7e9d1e1212c1d17b623cb177b608f8fb3e0bcc64f8fa2ae011dee73` |

### 바꾼 자리(출력 형식 절만 — 그 밖의 글자는 그대로, `scripts/section4-IR2a.sh` 7단계 ①이 읽기판에서 다시 견준다)

| 이름 | 바꾼 자리 | 새 조각 sha256 |
|---|---|---|
| `IMPACT_SYSTEM` | R/2153 「…하나의 테이블로 정리하는 것이다.」 → `_IMPACT_SYSTEM_GOAL`(셀 50 R/2425 의 같은 문장 「…하나의 결과로 정리하는 것이다.」 — 감독 Q3, sha256 `33aefb82bd8f7bfddd625df7e4c13ce3e911822a2942576bf7c12cf861f49a09`) · R/2214-2215(Step E 의 `제목: …<br>…` 형식 두 줄) 지움 · R/2225-2270([최종 Output Format]·[Length Constraint]·[컬럼별 작성 규칙]·[HTML 사용 규칙]) → `_IMPACT_SYSTEM_JSON`(셀 50 JSON 절 꼴, `impact_type` 긍정·부정, `value_chain_activities` 한 줄, [작성 규칙] = 셀 46 [Length Constraint] 에서 「row·테이블」 낱말만 바꿈, 첫 줄에 셀 46 R/2227 출력 언어 문장 「답변은 반드시 **한국어**로 작성한다.」를 「- 」 꼴로 — 감독 처분 ⑤) | `721459ffc4e829a958c2803989ef9586fb2c000b1d8f7effda79a56ad874c36d` |
| `FINANCIAL_SYSTEM` | R/2545(risk_type 줄) 뒤에 `_FINANCIAL_VALUE_CHAIN` 한 줄 | `0b89a5d45fe1592e6b8be90dbeb08aff2f3f8253dc3e92cb6e920667fcf2d2b7` |
| `PATHWAY_SYSTEM` | R/3099-3105([형식 규칙], 표 머리 줄 포함) → `_PATHWAY_SYSTEM_JSON`(pathways 꼴, 「불릿 없이 문장」·「A, B, C 한 줄」·HTML 금지·[1]…[N] 남김) | `e31617607528fa92fcad8b5dac83572989918e4d61a45ebefeba9e071e63c91b` |
| `impact_user`·`financial_user`·`pathway_user` | 글자 0 — 셀 전역을 인자로 받고, 컨트로버시·규제 자리에 contracts 의 셀 50 꼴 글(셀 46 의 `.strip()` 은 그 글에 걸린다), `{fin_impact}` 에 표 | — |

남는 「row/컬럼/표」 낱말(Step C 「하나의 row」, Step E 「[컨트로버시/규제/정책] 컬럼 규칙을 따른다」)은 셀 50 이 JSON 절과 함께
그대로 둔 선례대로 둔다.

### 낸 글 지문(2부 — 1부 표와 칸 수를 달리해 `tests/engines/colab_155/test_prompts.py` 가 1부 표만 읽는다)

| 글 | 셀 | sha256 |
|---|---|---|
| `IMPACT_SYSTEM` | 46 | `3f32db36d5b7f336ffc5c9b7c8de5516024cffd357fecec4891b26c52852a53c` |
| `FINANCIAL_SYSTEM` | 50 | `a1cccc7a73bc9c45628987e3c8a31d38dc94a64fdc0dc8a997ed9eef1408c09c` |
| `PATHWAY_SYSTEM` | 55 | `6807a731a4c61f945b08c464c6237c5a6714d97d6bdd131a519c3e185d118eea` |

배포(`MARC-ENT-352` 2번): 엔진 글·받기 규칙·models.json 이 바뀌는 배포 전에 진행 중 중대성평가 실행 0 을 확인한다(이 밴드
— IR4 — 부터 워커가 판을 다시 지어 sha 가 다르면 `versions_mismatch` 로 끝난다. 실패한 실행은 이어 돌기가 아니라 새 실행으로).

무효 조건: 읽기판이 다시 뽑히면 위 블록 sha256 과 줄 번호를 다시 잰다.
