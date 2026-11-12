# 기준정보의 자료 사본

이 폴더의 두 파일은 **esg-lab 의 적재 산출물에서 뽑은 사본**이다. 손으로 고치지 않는다. wheel 과 이미지에 실리고,
`manage.py import_factors`(인자 없이)가 이것을 DB 에 들인다. 순수 테스트의 고정물도 이것이다.

| 파일 | 무엇 | 줄·크기 | sha256 |
|---|---|---|---|
| `factors.kr.jsonl` | 계수 낱줄 가운데 출처 id 가 `kr-ets-` 또는 `gir-` 로 시작하는 것 | 600줄, 958,934 B | `301b2d927305e3ce7d9a53241fc740aeaa7e5efbccf6b3992103530ea9faaa10` |
| `mappings.kr-ets.json` | 조립용 대응표(부문·연료 이름·연료 상태·최소 산정등급) | 85,910 B | `c7aa189167060d2a49eb832156c8a367ec6f4660bc41e9accc580378907d77d2` (원본과 같다) |

## 어디서 왔나

- 원본: `esg-lab/data/factors/factors.jsonl`(10,754줄, 17,584,780 B, sha256 `63fa3d556b01bb5d8230f281813031684a4bda0e9c0b0bcb0add28cab8092445`)과
  `esg-lab/data/factors/mappings.kr-ets.json`
- esg-lab HEAD: `f1b2c77` (뽑은 날 2026-10-08)
- 뽑은 규칙(원본의 줄을 차례 그대로, 글자 그대로 옮긴다. 600줄 전부 원본의 줄과 바이트까지 같다):

  ```sh
  jq -c 'select((.source.id|startswith("kr-ets-")) or (.source.id|startswith("gir-")))' \
     esg-lab/data/factors/factors.jsonl > factors.kr.jsonl
  cp esg-lab/data/factors/mappings.kr-ets.json mappings.kr-ets.json
  ```

- 원본을 만든 것은 esg-lab 의 적재기(`py/factors`, PDF·HWPX 를 읽는다)다. **그 적재기는 여기로 옮기지 않았다.**
  원자료가 바뀌면 esg-lab 에서 다시 적재하고 이 사본을 위 명령으로 다시 뽑는다.
- 전체 jsonl(DEFRA·EPA·KEITI 포함 10,754줄)은 이 저장소에 없다. 들이려면 경로를 준다:
  `manage.py import_factors <factors.jsonl> [--mapping <json>] [--include-license …]`.

## 출처와 확인 일자

값은 낱줄의 `source{…}` 블록에 실려 있고(코드에 박지 않았다), 그 정본은 esg-lab 의 `py/factors/sources.py` 다.
아래는 사본에 실린 것을 그대로 옮긴 것이다.

| 출처 id | 낱줄 | 판 | 확인 일자 | 출처 URL |
|---|---|---|---|---|
| `kr-ets-byl12` | 108 | 환경부고시 제2025-64호 (2025-04-11 시행) | 2026-10-01 | https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000257748 |
| `kr-ets-byl11` | 55 | 같음 | 2026-10-01 | 같음 |
| `kr-ets-byl10` | 385 | 같음 | 2026-10-01 | 같음 |
| `kr-ets-byl06` | 12 | 같음 | 2026-10-02 | 같음 |
| `gir-2025` | 32 | 2025-12-18 공고 | 2026-10-01 | https://www.gir.go.kr/home/board/read.do?menuId=36&boardId=86&boardMasterId=2 |
| `gir-2024` | 8 | 2025-03-31 게시 | 2026-10-01 | https://www.gir.go.kr/home/board/read.do?menuId=36&boardId=82&boardMasterId=2 |

대응표의 `sources` 에는 낱줄이 없는 출처 하나가 더 있다: `kr-ets-byl05`(별표 5 최소 산정등급, 확인 일자 2026-10-02).

## ★ 이용 조건: 600줄 전부 `unverified` 다

**이 사본은 이용 조건을 확인하지 못한 자료이고, 그 상태로 wheel 과 이미지에 실린다.**

- GIR 공표 40줄: 게시물에 공공누리 표시가 없다. GIR 저작권정책은 그런 자료를 「담당자와 사전 협의 후 이용」 하라고 적는다
  (https://www.gir.go.kr/home/index.do?menuId=43, esg-lab 이 2026-10-01 에 확인).
- 고시 별표 560줄: 행정규칙(고시)의 별표다. 저작권법 제7조의 보호받지 못하는 저작물에 해당할 것으로 보이나
  esg-lab 의 작업에서 조문 원문을 열어 확인하지 않았다.
- 문면의 정본은 낱줄의 `license{…}`·`license_status` 이고 DB 의 `reference_sources` 로 들어가 API 의
  `licenseStatus`·`licenseNote` 로 늘 같이 나간다. 위 두 줄은 그 요약이다.
- 사본에는 `disputed`(KEITI 환경성적표지 평가계수 398줄)와 `ok`(DEFRA·EPA)가 없다.
- 상업 서비스에 싣기 전에 두 출처의 이용 조건을 확인해야 한다. 미결이다.
