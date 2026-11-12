"""표 한 개의 내부 표현과 머리글 추정."""

from dataclasses import dataclass, field

from .layout import is_dash, is_numeric, is_year

STATUS_OK = "ok"
STATUS_LOW = "low_confidence"
STATUS_FAILED = "failed"

METHOD_LINES = "lines"  # 괘선 기반: 행·열 경계를 괘선 토막에서 얻는다
METHOD_TEXT = "text"  # 글자 정렬 기반: 행·열 경계를 글자 위치에서 추정한다
METHOD_NONE = "none"  # 어느 전략도 격자를 만들지 못함 (status=failed)


@dataclass
class Table:
    bbox: list
    grid: list  # 행 목록, 각 행은 같은 길이의 문자열 목록. 빈 칸은 ""
    method: str
    status: str = STATUS_OK
    notes: list = field(default_factory=list)
    footnote_marks: list = field(default_factory=list)  # [{"row","col","mark"}] 숫자 셀에서 떼어 낸 각주 위첨자
    header: dict = field(default_factory=dict)
    # {(행, 열): 그 칸의 글을 이룬 조각, 글의 차례대로}. 산출에는 싣지 않는다 (글자 자리를 낼 때만 쓴다).
    cell_chunks: dict = field(default_factory=dict)

    @property
    def n_rows(self):
        return len(self.grid)

    @property
    def n_cols(self):
        return len(self.grid[0]) if self.grid else 0


def _is_data_number(text):
    return is_numeric(text) and not is_year(text)


def estimate_header(grid):
    """머리글 행·열을 추정한다. 근거 문자열을 함께 돌려준다 (추정이지 확정이 아니다).

    머리글 행 = 연도가 아닌 숫자 셀이 처음 나오는 행의 앞쪽 행들.
    머리글 열 = 본문 행에서 숫자·'-' 셀이 하나도 없는 왼쪽 열들.
    """
    if not grid:
        return {"rows": [], "cols": [], "basis": "empty"}
    first_data = next((i for i, r in enumerate(grid) if any(_is_data_number(c) for c in r)), None)
    if first_data is None:
        rows, basis = [0], "no_numeric_row"
        body = grid[1:]
    else:
        rows, basis = list(range(first_data)), "rows_before_first_numeric_row"
        # 값 행 바로 위의 「셀 하나뿐인 행」은 머리글이 아니라 본문 안의 소제목이다.
        while len(rows) > 1 and sum(1 for c in grid[rows[-1]] if c) <= 1:
            rows.pop()
        body = grid[len(rows) :]
    cols = []
    for j in range(len(grid[0])):
        if any(_is_data_number(r[j]) or is_dash(r[j]) for r in body):
            break
        cols.append(j)
    return {"rows": rows, "cols": cols, "basis": basis}


def prune_empty(grid, marks=()):
    """빈 행·빈 열을 없앤다. (격자, 옮겨진 marks) 를 돌려준다."""
    if not grid:
        return [], []
    keep_r = [i for i, r in enumerate(grid) if any(c for c in r)]
    keep_c = [j for j in range(len(grid[0])) if any(grid[i][j] for i in keep_r)]
    rmap = {old: new for new, old in enumerate(keep_r)}
    cmap = {old: new for new, old in enumerate(keep_c)}
    out = [[grid[i][j] for j in keep_c] for i in keep_r]
    moved = [
        {"row": rmap[m["row"]], "col": cmap[m["col"]], "mark": m["mark"]}
        for m in marks
        if m["row"] in rmap and m["col"] in cmap
    ]
    return out, moved


def pruned_index(grid):
    """`prune_empty` 가 남기는 행·열의 (옛 번호 → 새 번호) 둘."""
    if not grid:
        return {}, {}
    keep_r = [i for i, r in enumerate(grid) if any(c for c in r)]
    keep_c = [j for j in range(len(grid[0])) if any(grid[i][j] for i in keep_r)]
    return {old: new for new, old in enumerate(keep_r)}, {old: new for new, old in enumerate(keep_c)}
