// @vitest-environment jsdom
// 줄 id · 줄 바탕 · 묶음 tbody(밴드 DT2, sid:MARC-ISSUE-415): rowId · rowTone · groupOf.
// ① 셋 다 없으면 BASE(989cc43f) 와 바이트까지 같은 DOM — 아래 BASE_DOM 은 편집 전 BASE 코드로 같은 자료를 그려 뽑은 innerHTML(두 번 뽑아 같음).
//   밴드 TA1(sid:MARC-ISSUE-600)이 묶음 칸 위 여백을 더함 — BASE_DOM 은 그 칸 class 한 자리만 갱신(다른 바이트 그대로).
// ② 칸마다 단위 ③ 「BatchTable 꼴」(지어낸 자료 — 영문번역 BatchTable 이 그리는 짜임을 이 셋으로 낼 수 있는가).
import { act, cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { useDataTable } from '../hooks/index.ts';
import type { DataTableColumnDef } from '../hooks/index.ts';
import { DataTable } from './DataTable.tsx';
import type { DataTableProps } from './DataTable.tsx';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** 지어낸 줄: 묶음(group) 안의 해(year). 묶음 첫 줄만 first. */
interface Line {
  id: string;
  group: string;
  first: boolean;
  size: number;
  year: string;
}
const LINES: Line[] = [
  { id: 'a1', group: 'A', first: true, size: 2, year: '2024' },
  { id: 'a2', group: 'A', first: false, size: 2, year: '2025' },
  { id: 'b1', group: 'B', first: true, size: 1, year: '2025' },
];
const COLUMNS: DataTableColumnDef<Line>[] = [
  { id: 'group', accessorKey: 'group', header: '묶음', enableSorting: false },
  { id: 'year', accessorKey: 'year', header: '해', meta: { align: 'right' } },
  { id: 'note', header: '비고', enableSorting: false, cell: () => '-' },
];
function Sample({
  data = LINES,
  ...props
}: Omit<DataTableProps<Line>, 'table'> & { data?: Line[] }) {
  const table = useDataTable({
    data,
    columns: COLUMNS,
    getRowId: (row) => row.id,
  });
  return <DataTable table={table} aria-label="표" {...props} />;
}
const groupSpan = (line: Line, columnId: string) =>
  columnId !== 'group' ? undefined
  : !line.first ? 0
  : line.size > 1 ? line.size
  : undefined;
const spanProps = {
  rowSpanOf: groupSpan,
  renderExpanded: (line: Line) =>
    line.id === 'a1' || line.id === 'b1' ? `식 ${line.id}` : null,
  rowAttrs: (line: Line) => ({
    'data-line': line.id,
    'data-first': line.first ? '' : undefined,
  }),
};

/** BASE(989cc43f) 의 innerHTML — 그냥 · rowSpanOf+renderExpanded+rowAttrs · loading 첫 그림 · 줄 0+empty. */
const BASE_DOM = {
  plain:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">묶음</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">해<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">A</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2024</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">A</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2025</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">B</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2025</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr></tbody></table></div>',
  span: '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">묶음</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">해<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr data-line="a1" data-first="" class=""><td rowspan="3" class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left align-top pt-[calc((theme(spacing.14)-1lh)/2)]">A</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2024</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr data-expanded-row=""><td colspan="2" class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary py-3">식 a1</td></tr><tr data-line="a2" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2025</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr data-line="b1" data-first="" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">B</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2025</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr data-expanded-row=""><td colspan="3" class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary py-3">식 b1</td></tr></tbody></table></div>',
  loading:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse" aria-busy="true"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">묶음</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">해<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr></tbody></table></div>',
  empty:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">묶음</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">해<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr><td colspan="3" class="p-0"><p>없음</p></td></tr></tbody></table></div>',
};

const bodies = () => [...document.querySelectorAll('tbody')];
const rowsOf = (body: Element) => [...body.querySelectorAll('tr')];
const allRows = () => bodies().flatMap(rowsOf);
const hasTone = (cell: Element) =>
  cell.className.split(/\s+/).includes('bg-background-secondary');
const SUBTLE_A1 = (line: Line) => (line.id === 'a1' ? 'subtle' : undefined);

describe('① 셋 다 없으면 BASE 와 바이트까지 같은 DOM', () => {
  it('그냥 표', () => {
    expect(render(<Sample />).container.innerHTML).toBe(BASE_DOM.plain);
  });

  it('rowSpanOf + renderExpanded + rowAttrs', () => {
    expect(render(<Sample {...spanProps} />).container.innerHTML).toBe(
      BASE_DOM.span,
    );
  });

  it('loading 첫 그림(막대 300ms 전)', () => {
    vi.useFakeTimers();
    expect(render(<Sample loading />).container.innerHTML).toBe(
      BASE_DOM.loading,
    );
  });

  it('줄 0 + empty', () => {
    expect(
      render(<Sample data={[]} empty={<p>없음</p>} />).container.innerHTML,
    ).toBe(BASE_DOM.empty);
  });

  it('rowId·rowTone 이 늘 undefined 여도 같다(그냥 · 묶음 자료)', () => {
    const none = { rowId: () => undefined, rowTone: () => undefined };
    expect(render(<Sample {...none} />).container.innerHTML).toBe(
      BASE_DOM.plain,
    );
    cleanup();
    expect(
      render(<Sample {...spanProps} {...none} />).container.innerHTML,
    ).toBe(BASE_DOM.span);
  });
});

describe('② rowId', () => {
  it('값 준 줄의 tr 에 id, undefined 줄은 id 속성 없음', () => {
    render(
      <Sample rowId={(line) => (line.first ? `x-${line.id}` : undefined)} />,
    );
    expect(allRows().map((row) => row.getAttribute('id'))).toEqual([
      'x-a1',
      null,
      'x-b1',
    ]);
  });

  it('펼침 줄 tr 에는 id 0', () => {
    render(
      <Sample
        rowId={(line) => `x-${line.id}`}
        renderExpanded={(line) => (line.id === 'a1' ? '식' : null)}
      />,
    );
    const rows = allRows();
    expect(rows[1]!.hasAttribute('data-expanded-row')).toBe(true);
    expect(rows[1]!.hasAttribute('id')).toBe(false);
    expect(document.querySelectorAll('[id]')).toHaveLength(3);
  });

  it('스켈레톤 줄·빈 줄 tr 에는 id 0', () => {
    vi.useFakeTimers();
    render(<Sample loading rowId={(line) => `x-${line.id}`} />);
    expect(allRows()).toHaveLength(5);
    expect(document.querySelectorAll('tr[id]')).toHaveLength(0);
    cleanup();
    render(<Sample data={[]} empty="없음" rowId={(line) => `x-${line.id}`} />);
    expect(allRows()).toHaveLength(1);
    expect(document.querySelectorAll('tr[id]')).toHaveLength(0);
  });

  it('onClickRow 와 같이 써도 tabIndex·aria-label 그대로', () => {
    render(
      <Sample
        rowId={(line) => `x-${line.id}`}
        onClickRow={vi.fn()}
        rowLabel={(line) => `${line.id} 열기`}
      />,
    );
    const first = allRows()[0]!;
    expect(first.id).toBe('x-a1');
    expect(first.getAttribute('tabindex')).toBe('0');
    expect(first.getAttribute('aria-label')).toBe('a1 열기');
  });
});

describe('② rowTone', () => {
  it("'subtle' 줄의 td 전부에 바탕, tr 에는 없음 · undefined 줄 td 에 없음", () => {
    render(<Sample rowTone={SUBTLE_A1} />);
    const [a1, a2, b1] = allRows();
    const cells = [...a1!.querySelectorAll('td')];
    expect(cells).toHaveLength(3);
    expect(cells.every(hasTone)).toBe(true);
    expect(a1!.className.split(/\s+/)).not.toContain('bg-background-secondary');
    for (const row of [a2!, b1!])
      expect([...row.querySelectorAll('td')].some(hasTone)).toBe(false);
  });

  it('rowSpan 칸은 시작 줄의 바탕(시작 줄 subtle → 있음, 아래 줄만 subtle → 없음)', () => {
    render(<Sample rowSpanOf={groupSpan} rowTone={SUBTLE_A1} />);
    let [a1, a2] = allRows();
    expect(a1!.querySelector('td')!.getAttribute('rowspan')).toBe('2');
    expect(hasTone(a1!.querySelector('td')!)).toBe(true);
    expect([...a2!.querySelectorAll('td')].some(hasTone)).toBe(false);
    cleanup();
    render(
      <Sample
        rowSpanOf={groupSpan}
        rowTone={(line) => (line.id === 'a2' ? 'subtle' : undefined)}
      />,
    );
    [a1, a2] = allRows();
    expect([...a1!.querySelectorAll('td')].some(hasTone)).toBe(false);
    expect([...a2!.querySelectorAll('td')].every(hasTone)).toBe(true);
  });

  it('펼침 줄 td 에는 바탕 없음', () => {
    render(
      <Sample
        rowTone={() => 'subtle'}
        renderExpanded={(line) => (line.id === 'a1' ? '식' : null)}
      />,
    );
    const expanded = allRows()[1]!;
    expect(expanded.hasAttribute('data-expanded-row')).toBe(true);
    expect(hasTone(expanded.querySelector('td')!)).toBe(false);
  });

  it("'subtle' 밖 글자는 타입 오류", () => {
    type Tone = ReturnType<NonNullable<DataTableProps<Line>['rowTone']>>;
    // @ts-expect-error — 닫힌 토큰
    const loud: Tone = 'loud';
    const subtle: Tone = 'subtle';
    expect([loud, subtle]).toHaveLength(2);
  });
});

describe('② groupOf', () => {
  const byGroup = (line: Line) => line.group;
  const summary = () =>
    bodies().map((body) => [
      body.getAttribute('data-group'),
      rowsOf(body).length,
    ]);

  it('이어진 같은 값 → tbody 하나 · A,A,B → tbody 둘(줄 2·1) · 머리 thead 그대로', () => {
    render(<Sample groupOf={() => 'all'} />);
    expect(summary()).toEqual([['all', 3]]);
    cleanup();
    render(<Sample groupOf={byGroup} />);
    expect(summary()).toEqual([
      ['A', 2],
      ['B', 1],
    ]);
    expect(document.querySelectorAll('thead')).toHaveLength(1);
    expect(screen.getAllByRole('columnheader')).toHaveLength(3);
  });

  it('떨어진 같은 값(A,B,A) → tbody 셋(합치지 않음, 줄 차례 그대로)', () => {
    render(
      <Sample data={[LINES[0]!, LINES[2]!, LINES[1]!]} groupOf={byGroup} />,
    );
    expect(summary()).toEqual([
      ['A', 1],
      ['B', 1],
      ['A', 1],
    ]);
    expect(
      allRows().map((row) => row.querySelector('td')!.textContent),
    ).toEqual(['A', 'B', 'A']);
  });

  it('펼침 줄은 그 데이터 줄과 같은 tbody', () => {
    render(
      <Sample
        groupOf={byGroup}
        renderExpanded={(line) => (line.id === 'a2' ? '식' : null)}
      />,
    );
    expect(summary()).toEqual([
      ['A', 3],
      ['B', 1],
    ]);
    const expanded = document.querySelector('[data-expanded-row]')!;
    const a2 = allRows()[1]!;
    expect(expanded.closest('tbody')).toBe(a2.closest('tbody'));
    expect(expanded.previousElementSibling).toBe(a2);
  });

  it('rowSpan 은 묶음 끝에서 자른다: A1 3·A2 0·B1 그냥 → A1 rowspan 2, B 첫 줄 칸 = 열 수, B 펼침 칸 colSpan = 열 수', () => {
    render(
      <Sample
        groupOf={byGroup}
        rowSpanOf={(line, columnId) =>
          columnId !== 'group' ? undefined
          : line.id === 'a1' ? 3
          : line.id === 'a2' ? 0
          : undefined
        }
        renderExpanded={(line) => (line.id === 'b1' ? '식 b1' : null)}
      />,
    );
    const [a, b] = bodies();
    const [a1, a2] = rowsOf(a!);
    const [b1, bExpanded] = rowsOf(b!);
    // 자름의 근거 둘을 한 번에(안 자르면 A1 rowspan 4 · B 펼침 colSpan 2). A2 의 0 칸은 표가 되살리지 않는다(쓰는 쪽 몫).
    expect({
      a1RowSpan: a1!.querySelector('td')!.getAttribute('rowspan'),
      bExpandedColSpan: bExpanded!.querySelector('td')!.getAttribute('colspan'),
    }).toEqual({ a1RowSpan: '2', bExpandedColSpan: '3' });
    expect(a2!.querySelectorAll('td')).toHaveLength(2);
    expect(b1!.querySelectorAll('td')).toHaveLength(3);
  });

  it('묶음 안 rowSpan + 펼침은 DT1 셈 그대로(rowspan 3, 펼침 칸 colSpan 2)', () => {
    render(
      <Sample
        groupOf={byGroup}
        rowSpanOf={groupSpan}
        renderExpanded={(line) => (line.id === 'a1' ? '식 a1' : null)}
      />,
    );
    const [a1, expanded] = rowsOf(bodies()[0]!);
    expect(a1!.querySelector('td')!.getAttribute('rowspan')).toBe('3');
    expect(expanded!.querySelector('td')!.getAttribute('colspan')).toBe('2');
  });

  it('loading → tbody 1 · data-group 0 · 스켈레톤 줄 5', () => {
    vi.useFakeTimers();
    render(<Sample loading groupOf={byGroup} />);
    expect(bodies()).toHaveLength(1);
    expect(document.querySelectorAll('[data-group]')).toHaveLength(0);
    expect(rowsOf(bodies()[0]!)).toHaveLength(5);
    act(() => vi.advanceTimersByTime(300));
    expect(rowsOf(bodies()[0]!)).toHaveLength(5);
  });

  it('줄 0 → tbody 1 · empty 칸 하나 · data-group 0', () => {
    render(<Sample data={[]} empty="없음" groupOf={byGroup} />);
    expect(bodies()).toHaveLength(1);
    expect(document.querySelectorAll('[data-group]')).toHaveLength(0);
    const cells = bodies()[0]!.querySelectorAll('td');
    expect(cells).toHaveLength(1);
    expect(cells[0]!.textContent).toBe('없음');
  });
});

/** 지어낸 「편」 줄 — BatchTable 이 그리는 짜임(묶음 줄 · 파트 줄 · 앞 회차 줄). first = 그 펼침의 첫 줄. */
interface Piece {
  key: string;
  kind: 'batch' | 'part' | 'earlier';
  batch: string;
  part?: string;
  round?: number;
  first?: boolean;
}
const PIECES: Piece[] = [
  { key: 'b1', kind: 'batch', batch: 'b1' },
  { key: 'b1/story', kind: 'part', batch: 'b1', part: 'story', first: true },
  {
    key: 'b1/story/1',
    kind: 'earlier',
    batch: 'b1',
    part: 'story',
    round: 1,
    first: true,
  },
  { key: 'b1/table', kind: 'part', batch: 'b1', part: 'table' },
  { key: 'b1/notes', kind: 'part', batch: 'b1', part: 'notes' },
  { key: 'b2', kind: 'batch', batch: 'b2' },
  {
    key: 'b2/story/1',
    kind: 'earlier',
    batch: 'b2',
    part: 'story',
    round: 1,
    first: true,
  },
];
const HEADS = ['file', 'part', 'style', 'uploader', 'started', 'state', 'next'];
const PIECE_COLUMNS: DataTableColumnDef<Piece>[] = HEADS.map((id) => ({
  id,
  header: `머리 ${id}`,
  enableSorting: false,
  cell: ({ row }) => {
    const piece = row.original;
    if (id === 'file' && piece.kind === 'batch' && piece.batch === 'b1')
      return (
        <button type="button" aria-controls="t-b1-parts">
          펴기
        </button>
      );
    // b1 파트 줄 · 파트 하나인 b2 는 묶음 줄에 그 파트의 회차 단추
    if (
      id === 'part' &&
      ((piece.kind === 'part' && piece.part === 'story') ||
        (piece.kind === 'batch' && piece.batch === 'b2'))
    )
      return (
        <button type="button" aria-controls={`t-${piece.batch}-story-rounds`}>
          회차
        </button>
      );
    return null;
  },
}));
function Pieces() {
  const table = useDataTable({
    data: PIECES,
    columns: PIECE_COLUMNS,
    getRowId: (piece) => piece.key,
  });
  return (
    <DataTable
      table={table}
      aria-label="묶음 표"
      groupOf={(piece) => piece.batch}
      rowTone={(piece) => (piece.kind === 'part' ? 'subtle' : undefined)}
      rowId={(piece) =>
        !piece.first ? undefined
        : piece.kind === 'part' ? `t-${piece.batch}-parts`
        : `t-${piece.batch}-${piece.part}-rounds`
      }
      rowAttrs={(piece) =>
        piece.kind === 'earlier' ?
          { 'data-earlier': String(piece.round) }
        : { 'data-row': piece.kind, 'data-part': piece.part }
      }
    />
  );
}
/** tbody 마다 [묶음 속성, [줄마다 이름(+#id)]] — 앞 회차 줄은 data-row 가 없어 data-earlier 로 센다(critic 1). */
const shapeOf = (groupAttribute: string) =>
  bodies().map((body) => [
    body.getAttribute(groupAttribute),
    rowsOf(body).map(
      (row) =>
        (row.dataset.row ??
          (row.hasAttribute('data-earlier') ? 'earlier' : '?')) +
        (row.id ? `#${row.id}` : ''),
    ),
  ]);

describe('③ BatchTable 꼴(지어낸 자료)', () => {
  it('묶음마다 tbody · 파트 첫 줄·앞 회차 첫 줄 id · 그리는 차례', () => {
    render(<Pieces />);
    expect(shapeOf('data-group')).toEqual([
      [
        'b1',
        [
          'batch',
          'part#t-b1-parts',
          'earlier#t-b1-story-rounds',
          'part',
          'part',
        ],
      ],
      ['b2', ['batch', 'earlier#t-b2-story-rounds']],
    ]);
  });

  it('단추의 aria-controls 대상이 그 tr 이고 같은 tbody 안', () => {
    render(<Pieces />);
    const buttons = [
      ...document.querySelectorAll<HTMLButtonElement>('button[aria-controls]'),
    ];
    expect(buttons).toHaveLength(3);
    for (const button of buttons) {
      const target = document.getElementById(
        button.getAttribute('aria-controls')!,
      );
      expect(target?.tagName).toBe('TR');
      expect(target!.closest('tbody')).toBe(button.closest('tbody'));
    }
  });

  it('part 줄 td 7 개 모두 바탕, batch·earlier 줄 td 0 개 · 줄마다 td 7', () => {
    render(<Pieces />);
    for (const row of allRows()) {
      const cells = [...row.querySelectorAll('td')];
      expect(cells).toHaveLength(7);
      expect(cells.filter(hasTone)).toHaveLength(
        row.dataset.row === 'part' ? 7 : 0,
      );
    }
  });
});
