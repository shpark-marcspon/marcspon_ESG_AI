// @vitest-environment jsdom
// 목록 표의 열 너비와 누를 수 있는 줄의 이름(밴드 FW2 ②, sid:MARC-ISSUE-85 1). 기존 DataTable.test.tsx 는 그대로 두고 여기에 더한다.
import { cleanup, render, screen, within } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { useDataTable } from '../hooks/index.ts';
import type { DataTableColumnDef } from '../hooks/index.ts';
import { DataTable } from './DataTable.tsx';

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
  { id: 'name', accessorKey: 'name', header: '이름', meta: { width: 120 } },
  { id: 'rest', header: '나머지', cell: () => '-' },
  // 0·음수·숫자가 아닌 값은 버린다
  { id: 'bad', header: '틀림', cell: () => '-', meta: { width: 0 } },
];

function Sample({
  onClickRow,
  rowLabel,
  isRowClickable,
}: {
  onClickRow?: (row: Item) => void;
  rowLabel?: (row: Item) => string;
  isRowClickable?: (row: Item) => boolean;
}) {
  const table = useDataTable({
    data: DATA,
    columns: COLUMNS,
    getRowId: (row) => row.id,
  });
  return (
    <DataTable
      table={table}
      aria-label="목록"
      onClickRow={onClickRow}
      rowLabel={rowLabel}
      isRowClickable={isRowClickable}
    />
  );
}

describe('열 너비(meta.width)', () => {
  it('너비를 준 열의 머리 칸에만 width 가 붙는다', () => {
    render(<Sample />);
    const headers = screen.getAllByRole('columnheader');
    expect(headers.map((th) => th.style.width)).toEqual(['120px', '', '']);
  });
});

describe('누를 수 있는 줄의 이름(rowLabel)', () => {
  it('onClickRow 와 rowLabel 이 있으면 줄에 aria-label, 칸 안 이름으로 찾을 수 있다', () => {
    render(
      <Sample onClickRow={vi.fn()} rowLabel={(row) => `${row.name} 열기`} />,
    );
    const row = screen.getByRole('row', { name: '가 열기' });
    expect(within(row).getAllByRole('cell')[0]!.textContent).toBe('가');
  });

  it('누를 수 없는 줄에는 이름을 달지 않는다', () => {
    render(<Sample rowLabel={(row) => `${row.name} 열기`} />);
    expect(screen.queryByRole('row', { name: '가 열기' })).toBeNull();
  });
});

describe('줄마다 누를 수 있는지(isRowClickable)', () => {
  it('거짓인 줄은 초점·이름·hover 를 받지 않고 눌러도 부르지 않는다', () => {
    const onClickRow = vi.fn();
    render(
      <Sample
        onClickRow={onClickRow}
        rowLabel={(row) => `${row.name} 열기`}
        isRowClickable={(row) => row.id === 'a'}
      />,
    );
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((row) => row.getAttribute('tabindex'))).toEqual([
      '0',
      null,
    ]);
    expect(rows.map((row) => row.getAttribute('aria-label'))).toEqual([
      '가 열기',
      null,
    ]);
    expect(rows[1]!.className).not.toContain('cursor-pointer');
    within(rows[1]!).getAllByRole('cell')[0]!.click();
    rows[0]!.click();
    expect(onClickRow.mock.calls.map(([row]) => (row as Item).id)).toEqual([
      'a',
    ]);
  });
});
