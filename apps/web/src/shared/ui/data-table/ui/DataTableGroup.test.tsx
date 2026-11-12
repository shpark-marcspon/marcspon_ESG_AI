// @vitest-environment jsdom
// 묶음 줄(밴드 DT1 ③, sid:MARC-ISSUE-384): rowSpanOf · renderExpanded · rowAttrs. 실제 칸 높이는 e2e/parts.spec.ts(table-span)가 잰다.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { useDataTable } from '../hooks/index.ts';
import type { DataTableColumnDef } from '../hooks/index.ts';
import { DataTable } from './DataTable.tsx';
import type { DataTableProps } from './DataTable.tsx';

afterEach(cleanup);

/** 지어낸 줄: 묶음(group) 안의 해(year). 묶음 첫 줄만 first. */
interface Line {
  id: string;
  group: string;
  size: number;
  first: boolean;
  year: string;
}
const LINES: Line[] = [
  { id: 'a1', group: 'A', size: 2, first: true, year: '2024' },
  { id: 'a2', group: 'A', size: 2, first: false, year: '2025' },
  { id: 'b1', group: 'B', size: 1, first: true, year: '2025' },
];
const COLUMNS: DataTableColumnDef<Line>[] = [
  { id: 'group', accessorKey: 'group', header: '묶음', enableSorting: false },
  { id: 'year', accessorKey: 'year', header: '해', enableSorting: false },
  { id: 'note', header: '비고', enableSorting: false, cell: () => '-' },
];
/** 묶음 열만 수를 돌려준다(묶음이 하나뿐인 b 는 그냥 칸). */
const groupSpan = (line: Line, columnId: string) =>
  columnId !== 'group' ? undefined
  : !line.first ? 0
  : line.size > 1 ? line.size
  : undefined;

function Sample(props: Omit<DataTableProps<Line>, 'table'>) {
  const table = useDataTable({
    data: LINES,
    columns: COLUMNS,
    getRowId: (row) => row.id,
  });
  return <DataTable table={table} aria-label="묶음 표" {...props} />;
}

const bodyRows = () => [
  ...screen.getAllByRole('rowgroup')[1]!.querySelectorAll('tr'),
];

describe('rowSpanOf', () => {
  it('2 → 첫 줄 칸 rowSpan 2·align-top, 둘째 줄은 그 칸 없음 · 1 은 그냥', () => {
    render(<Sample rowSpanOf={groupSpan} />);
    const [a1, a2, b1] = bodyRows();
    const first = a1!.querySelectorAll('td');
    expect(first).toHaveLength(3);
    expect(first[0]!.getAttribute('rowspan')).toBe('2');
    expect(first[0]!.className.split(/\s+/)).toContain('align-top');
    expect(a2!.querySelectorAll('td')).toHaveLength(2);
    expect(a2!.querySelector('td')!.textContent).toBe('2025');
    const b = b1!.querySelectorAll('td');
    expect(b).toHaveLength(3);
    expect(b[0]!.hasAttribute('rowspan')).toBe(false);
    expect(b[0]!.className.split(/\s+/)).not.toContain('align-top');
  });

  it('묶음 칸만 위 여백 (h-14 − 1lh) / 2(밴드 TA1 — 첫 줄 = 옆 한 줄 칸 글 높이) · 그냥 칸·펼침 칸(py-3)은 없음', () => {
    const top = 'pt-[calc((theme(spacing.14)-1lh)/2)]';
    render(
      <Sample
        rowSpanOf={groupSpan}
        renderExpanded={(line) => (line.id === 'b1' ? '식 b1' : null)}
      />,
    );
    const [a1, a2, b1, open] = bodyRows();
    const classes = (cell: Element) => cell.className.split(/\s+/);
    const [span, ...rest] = a1!.querySelectorAll('td');
    expect(classes(span!)).toEqual(expect.arrayContaining(['align-top', top]));
    for (const cell of [
      ...rest,
      ...a2!.querySelectorAll('td'),
      ...b1!.querySelectorAll('td'),
    ])
      expect(classes(cell)).not.toContain(top);
    const expanded = open!.querySelector('td')!;
    expect(classes(expanded)).toContain('py-3');
    expect(classes(expanded)).not.toContain(top);
  });

  it('0 이상 정수가 아닌 값(-1·1.5·NaN)은 1', () => {
    render(
      <Sample rowSpanOf={(line) => (line.id === 'a1' ? -1 : Number.NaN)} />,
    );
    for (const row of bodyRows())
      expect(row.querySelectorAll('td[rowspan]')).toHaveLength(0);
  });
});

describe('renderExpanded', () => {
  const openA1 = (line: Line) => (line.id === 'a1' ? <span>식 a1</span> : null);

  it('span 안 펼침 줄 하나 → rowSpan 3, 펼침 칸 colSpan = 열 수 − 덮인 열 수(3 − 1)', () => {
    render(<Sample rowSpanOf={groupSpan} renderExpanded={openA1} />);
    const rows = bodyRows();
    expect(rows).toHaveLength(4);
    expect(rows[0]!.querySelector('td')!.getAttribute('rowspan')).toBe('3');
    const expanded = rows[1]!;
    expect(expanded.hasAttribute('data-expanded-row')).toBe(true);
    const cell = expanded.querySelectorAll('td');
    expect(cell).toHaveLength(1);
    expect(cell[0]!.getAttribute('colspan')).toBe('2');
    expect(cell[0]!.className.split(/\s+/)).toContain('py-3');
    expect(cell[0]!.textContent).toBe('식 a1');
  });

  it('span 마지막 줄의 펼침 줄도 덮는다 · span 밖 줄의 펼침 칸은 열 전부', () => {
    render(
      <Sample
        rowSpanOf={groupSpan}
        renderExpanded={(line) =>
          line.id === 'a2' || line.id === 'b1' ? `식 ${line.id}` : null
        }
      />,
    );
    const rows = bodyRows();
    expect(rows.map((row) => row.hasAttribute('data-expanded-row'))).toEqual([
      false,
      false,
      true,
      false,
      true,
    ]);
    expect(rows[0]!.querySelector('td')!.getAttribute('rowspan')).toBe('3');
    expect(rows[2]!.querySelector('td')!.getAttribute('colspan')).toBe('2');
    expect(rows[4]!.querySelector('td')!.getAttribute('colspan')).toBe('3');
  });

  it('펼침 줄은 누를 수 있는 줄이 아니다(onClickRow 가 있어도 tabIndex 0 없음, 눌러도 안 부름)', () => {
    const onClickRow = vi.fn();
    render(<Sample renderExpanded={openA1} onClickRow={onClickRow} />);
    const expanded = bodyRows()[1]!;
    expect(expanded.hasAttribute('tabindex')).toBe(false);
    fireEvent.click(expanded.querySelector('td')!);
    expect(onClickRow).not.toHaveBeenCalled();
    expect(bodyRows()[0]!.getAttribute('tabindex')).toBe('0');
  });
});

describe('묶음 칸 1(밴드 DVW1)', () => {
  /** b 도 묶음 칸 1 로 밝힌다. */
  const spanOne = (line: Line, columnId: string) =>
    columnId !== 'group' ? undefined
    : line.first ? line.size
    : 0;

  it('묶음 칸 1 + 펼침 → 그 칸 rowSpan 2·align-top, 펼침 칸 colSpan = 열 수 − 1 · 펼치지 않으면 rowspan 없이 align-top', () => {
    const { rerender } = render(<Sample rowSpanOf={spanOne} />);
    const closed = bodyRows()[2]!.querySelector('td')!;
    expect(closed.hasAttribute('rowspan')).toBe(false);
    expect(closed.className.split(/\s+/)).toContain('align-top');
    rerender(
      <Sample
        rowSpanOf={spanOne}
        renderExpanded={(line) => (line.id === 'b1' ? '식 b1' : null)}
      />,
    );
    const rows = bodyRows();
    expect(rows).toHaveLength(4);
    const first = rows[2]!.querySelector('td')!;
    expect(first.getAttribute('rowspan')).toBe('2');
    expect(first.className.split(/\s+/)).toContain('align-top');
    expect(rows[3]!.hasAttribute('data-expanded-row')).toBe(true);
    expect(rows[3]!.querySelector('td')!.getAttribute('colspan')).toBe('2');
  });

  it('그냥 칸(undefined) + 펼침 → rowspan·align-top 없이, 펼침 칸은 열 전부', () => {
    render(
      <Sample
        rowSpanOf={() => undefined}
        renderExpanded={(line) => (line.id === 'b1' ? '식 b1' : null)}
      />,
    );
    const rows = bodyRows();
    expect(rows).toHaveLength(4);
    for (const cell of rows[2]!.querySelectorAll('td')) {
      expect(cell.hasAttribute('rowspan')).toBe(false);
      expect(cell.className).not.toContain('align-top');
    }
    expect(rows[3]!.querySelector('td')!.getAttribute('colspan')).toBe('3');
  });
});

describe('rowAttrs', () => {
  it('data-* 가 데이터 줄 tr 에(undefined 는 달지 않음), 펼침 줄에는 data-expanded-row 하나', () => {
    render(
      <Sample
        rowAttrs={(line) => ({
          'data-testid': 'span-row',
          'data-group': line.group,
          'data-first': line.first ? '' : undefined,
        })}
        renderExpanded={(line) => (line.id === 'b1' ? '식' : null)}
      />,
    );
    const rows = bodyRows();
    expect(rows.map((row) => row.getAttribute('data-group'))).toEqual([
      'A',
      'A',
      'B',
      null,
    ]);
    expect(screen.getAllByTestId('span-row')).toHaveLength(3);
    expect(rows.map((row) => row.hasAttribute('data-first'))).toEqual([
      true,
      false,
      true,
      false,
    ]);
    expect([...rows[3]!.attributes].map((attribute) => attribute.name)).toEqual(
      ['data-expanded-row'],
    );
  });

  it('data-* 가 아닌 키는 타입 오류', () => {
    type Attrs = ReturnType<NonNullable<DataTableProps<Line>['rowAttrs']>>;
    const attrs = (): Attrs => ({
      'data-line': '1',
      // @ts-expect-error — data-* 만
      title: '안 됨',
    });
    expect(attrs()['data-line']).toBe('1');
  });
});

describe('셋 다 없으면 지금 DOM 그대로', () => {
  it('줄마다 tr 하나·칸 = 열 수 · rowspan·colspan·data-expanded-row·align-top 0', () => {
    render(<Sample />);
    const rows = bodyRows();
    expect(rows).toHaveLength(3);
    for (const row of rows) {
      expect(row.querySelectorAll('td')).toHaveLength(3);
      // class 는 BASE 에도 빈 값으로 있다(cn(false))
      expect(
        [...row.attributes]
          .map((attribute) => attribute.name)
          .filter((name) => name !== 'class'),
      ).toEqual([]);
      for (const cell of row.querySelectorAll('td')) {
        expect(cell.hasAttribute('rowspan')).toBe(false);
        expect(cell.hasAttribute('colspan')).toBe(false);
        expect(cell.className).not.toContain('align-top');
      }
    }
  });

  // 정렬과 rowSpan(문서 — 개발 경고는 두지 않는다): 표는 받은 줄 차례대로 묶는다. 정렬을 켜면 묶음 첫 줄이 다른 자리로 가 묶음이 깨지므로
  // rowSpan 표는 열마다 enableSorting false 로 둔다. 이 시험은 「표가 줄 차례를 스스로 바꾸지 않는다」를 잡는다.
  it('rowSpan 표는 정렬을 끈다: enableSorting false 면 머리 칸에 정렬 단추·aria-sort 0, 줄은 받은 차례 그대로', () => {
    render(<Sample rowSpanOf={groupSpan} />);
    for (const header of screen.getAllByRole('columnheader')) {
      expect(header.querySelector('button')).toBeNull();
      expect(header.hasAttribute('aria-sort')).toBe(false);
    }
    expect(bodyRows().map((row) => row.querySelectorAll('td').length)).toEqual([
      3, 2, 3,
    ]);
  });
});
