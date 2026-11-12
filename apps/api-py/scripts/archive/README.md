# scripts/archive — 닫힌 밴드의 자기검증 산출물

닫힌 밴드가 남긴 §4 자기검증(`section4-*.sh`), 심은 파손(`planted-breaks-*.sh`), 노드 id 목록(`*-nodeids-*.txt`), 일회성 검사기(`gm_check.py`)를 이름 그대로 옮겨 둔 자리다(밴드 AR1, `MARC-TICK-110`).

- **옮긴 뒤로는 돌리지 않는다.** 안의 `cd "$(dirname "$0")/…"` 와 사용 줄의 경로가 한 칸 어긋난다.
- 옮긴 것끼리 서로 부르는 것(예: `section4-GM.sh` → `gm_check.py`)도 돌리지 않는다.
- 그 밴드 때의 꼴로 돌리려면 그 밴드의 병합 커밋에서 꺼낸다: `git show <병합>:apps/api-py/scripts/<이름>`.
- 새 밴드의 §4 스크립트는 `scripts/` 에 두고, 밴드가 닫히면 테스트 감독이 묶어서 여기로 옮긴다.
