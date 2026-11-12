# scripts/archive — 닫힌 밴드의 자기검증 산출물

닫힌 밴드가 남긴 §4 자기검증(`section4-*.sh`)과 심은 파손(`planted-breaks-*.sh`)을 이름 그대로 옮겨 둔 자리다(밴드 AR2, `MARC-TICK-138`. 뜻은 `apps/api-py/scripts/archive/README.md` 와 같다).

- **옮긴 뒤로는 돌리지 않는다.** 안의 `cd "$(dirname "$0")/…"` 와 사용 줄의 경로가 한 칸 어긋난다.
- 그 밴드 때의 꼴로 돌리려면 그 밴드의 병합 커밋에서 꺼낸다: `git show <병합>:services/parser/scripts/<이름>`.
- 살아 있는 도구(`parser_baseline.py`·`planted.py`·`s4_tools.py`·`post_pdf.py`)는 `scripts/` 에 남는다.
