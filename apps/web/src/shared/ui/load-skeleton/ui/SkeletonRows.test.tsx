// @vitest-environment jsdom
// 표 몸의 스켈레톤 줄(밴드 LD1 ②)과 막대(SkeletonBar): 첫 그림부터 줄 5·칸 = columns, 줄 높이 h-14(진짜 줄 56),
// 막대는 300ms 뒤(delayed) 또는 바로, 폭은 정해진 차례, 맞춤은 가운데 mx-auto·오른쪽 ml-auto. 막대는 움직임 없음·tertiary·aria-hidden.
import { act, cleanup, render } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SkeletonBar } from '../../skeleton-bar/index.ts';
import { SkeletonRows } from './SkeletonRows.tsx';
import type { SkeletonColumn } from './SkeletonRows.tsx';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const COLUMNS: SkeletonColumn[] = [
  {},
  { width: 112 },
  { width: [24, 32], align: 'right' },
  { width: [72, 88], align: 'center' },
];

const renderRows = (
  props: Partial<Parameters<typeof SkeletonRows>[0]> = {},
) => {
  const { container } = render(
    <table>
      <tbody>
        <SkeletonRows columns={COLUMNS} {...props} />
      </tbody>
    </table>,
  );
  return container.querySelector('tbody')!;
};
const barsOf = (body: Element) => [
  ...body.querySelectorAll<HTMLElement>('[data-skeleton-bar]'),
];

describe('SkeletonRows', () => {
  it('첫 그림부터 줄 5·칸 = columns, 줄은 aria-hidden, 칸은 진짜 칸과 같은 h-14·px-4·아래 선', () => {
    const body = renderRows();
    const rows = body.querySelectorAll('tr');
    expect(rows).toHaveLength(5);
    for (const row of rows) {
      expect(row.getAttribute('aria-hidden')).toBe('true');
      const cells = row.querySelectorAll('td');
      expect(cells).toHaveLength(4);
      expect(cells[0]!.className.split(/\s+/)).toEqual(
        expect.arrayContaining(['h-14', 'px-4', 'border-b']),
      );
    }
  });

  it('delayed(기본): 300ms 전 막대 0(줄은 있음), 300ms 뒤 칸마다 하나', () => {
    const body = renderRows();
    act(() => vi.advanceTimersByTime(299));
    expect(barsOf(body)).toHaveLength(0);
    expect(body.querySelectorAll('tr')).toHaveLength(5);
    act(() => vi.advanceTimersByTime(1));
    expect(barsOf(body)).toHaveLength(20);
    for (const row of body.querySelectorAll('tr'))
      for (const cell of row.querySelectorAll('td'))
        expect(cell.querySelectorAll('[data-skeleton-bar]')).toHaveLength(1);
  });

  it('delayed={false} 면 막대를 바로. rows 로 줄 수를 바꾼다', () => {
    const body = renderRows({ delayed: false, rows: 3 });
    expect(body.querySelectorAll('tr')).toHaveLength(3);
    expect(barsOf(body)).toHaveLength(12);
  });

  it('폭: long 은 줄마다 다름(정해진 값), 수는 고정, 짝은 줄마다 그 사이. 맞춤 가운데·오른쪽', () => {
    const body = renderRows({ delayed: false });
    const rows = [...body.querySelectorAll('tr')].map((row) => [
      ...row.querySelectorAll<HTMLElement>('[data-skeleton-bar]'),
    ]);
    expect(rows.map((bars) => bars[0]!.style.width)).toEqual([
      '66%',
      '54%',
      '78%',
      '60%',
      '72%',
    ]);
    expect(rows.map((bars) => bars[1]!.style.width)).toEqual(
      Array(5).fill('112px'),
    );
    expect(rows.map((bars) => bars[2]!.style.width)).toEqual([
      '28px',
      '24px',
      '32px',
      '26px',
      '30px',
    ]);
    const first = rows[0]!;
    expect(first[0]!.className).not.toMatch(/\b(ml-auto|mx-auto)\b/);
    expect(first[2]!.className.split(/\s+/)).toContain('ml-auto');
    expect(first[3]!.className.split(/\s+/)).toContain('mx-auto');
    expect(first[0]!.className.split(/\s+/)).toContain('h-3');
  });
});

describe('SkeletonBar', () => {
  it('움직임 클래스 없음 · bg-background-tertiary · 모서리 6 · max-w-full · aria-hidden', () => {
    const { container } = render(<SkeletonBar className="h-3 w-10" />);
    const bar = container.firstElementChild!;
    const classes = bar.className.split(/\s+/);
    expect(classes).toEqual(
      expect.arrayContaining([
        'bg-background-tertiary',
        'rounded-[6px]',
        'max-w-full',
        'h-3',
        'w-10',
      ]),
    );
    expect(bar.className).not.toMatch(/animate/);
    expect(bar.getAttribute('aria-hidden')).toBe('true');
  });

  it('block 이면 모서리 rounded-component 하나(6 은 달지 않는다)', () => {
    const { container } = render(<SkeletonBar shape="block" />);
    const classes = container.firstElementChild!.className.split(/\s+/);
    expect(classes).toContain('rounded-component');
    expect(classes).not.toContain('rounded-[6px]');
  });
});
