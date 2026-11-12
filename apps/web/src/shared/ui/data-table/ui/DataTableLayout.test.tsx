// @vitest-environment jsdom
// 열 폭 고정(layout)과 스켈레톤 줄 수(skeletonRows) — 밴드 DT1 ②(J3·sid:MARC-ISSUE-374). 실제 칸 폭은 e2e/parts.spec.ts 가 잰다.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { useDataTable } from '../hooks/index.ts';
import type { DataTableColumnDef } from '../hooks/index.ts';
import { DataTable } from './DataTable.tsx';
import type { DataTableProps } from './DataTable.tsx';

afterEach(cleanup);

interface Item {
  id: string;
  name: string;
}
const DATA: Item[] = [
  { id: 'a', name: '가' },
  { id: 'b', name: '나' },
];
const COLUMNS: DataTableColumnDef<Item>[] = [
  { id: 'name', accessorKey: 'name', header: '이름' },
  { id: 'date', header: '날짜', cell: () => '-', meta: { width: 120 } },
  { id: 'state', header: '상태', cell: () => '-', meta: { width: 80 } },
];

function Sample({
  data = DATA,
  ...props
}: { data?: Item[] } & Omit<DataTableProps<Item>, 'table'>) {
  const table = useDataTable({
    data,
    columns: COLUMNS,
    getRowId: (row) => row.id,
  });
  return <DataTable table={table} aria-label="목록" {...props} />;
}

const colWidths = () =>
  [...screen.getByRole('table').querySelectorAll('colgroup > col')].map(
    (col) => (col as HTMLElement).style.width,
  );
const bodyRows = () =>
  screen.getAllByRole('rowgroup')[1]!.querySelectorAll('tr').length;

describe('layout', () => {
  it('fixed: table 에 table-fixed, 첫 자식 colgroup 의 col 수 = 열 수, meta.width 있는 col 만 width', () => {
    render(<Sample layout="fixed" />);
    const table = screen.getByRole('table');
    expect(table.className.split(/\s+/)).toContain('table-fixed');
    expect(table.firstElementChild!.tagName).toBe('COLGROUP');
    expect(colWidths()).toEqual(['', '120px', '80px']);
    // 진짜 칸은 줄바꿈(옆 칸을 덮지 않게)
    expect(screen.getAllByRole('cell')[0]!.className).toContain('break-words');
  });

  it('없음(auto): colgroup 0 · table-fixed 0 · 머리 칸 style.width 는 지금 그대로 · 칸에 break-words 0', () => {
    render(<Sample />);
    const table = screen.getByRole('table');
    expect(table.querySelector('colgroup')).toBeNull();
    expect(table.className.split(/\s+/)).not.toContain('table-fixed');
    expect(
      screen.getAllByRole('columnheader').map((th) => th.style.width),
    ).toEqual(['', '120px', '80px']);
    expect(screen.getAllByRole('cell')[0]!.className).not.toContain(
      'break-words',
    );
  });

  it('fixed: 로딩·빈·진짜 줄 셋에서 같은 colgroup', () => {
    const { rerender } = render(<Sample layout="fixed" loading />);
    const loading = colWidths();
    rerender(<Sample layout="fixed" data={[]} />);
    const empty = colWidths();
    rerender(<Sample layout="fixed" />);
    expect(loading).toEqual(['', '120px', '80px']);
    expect(empty).toEqual(loading);
    expect(colWidths()).toEqual(loading);
  });
});

describe('skeletonRows', () => {
  it('2 → 스켈레톤 줄 2, 없음 → 5', () => {
    const { unmount } = render(<Sample loading skeletonRows={2} />);
    expect(bodyRows()).toBe(2);
    unmount();
    render(<Sample loading />);
    expect(bodyRows()).toBe(5);
  });

  it.each([0, -1, 2.5, Number.NaN])('양의 정수가 아니면(%s) 기본 5', (rows) => {
    render(<Sample loading skeletonRows={rows} />);
    expect(bodyRows()).toBe(5);
  });

  it('로딩이 아니면 쓰지 않는다(진짜 줄 2)', () => {
    render(<Sample skeletonRows={7} />);
    expect(bodyRows()).toBe(2);
  });
});
