// @vitest-environment jsdom
// AI 설정 판 열 부품(밴드 AD2R ② — 캔버스 v110 AD-02-CM ①). 지어낸 판 줄로 본다: 머리 52px, 고름(aria-pressed)·누름 → 열쇠,
// 편집 중 줄은 주황 테두리 + 날짜 꼬리 다음 주황 둘째 꼬리 글(꼬리표 없음 — GW3R A11), 구분선, 끝 자리, [새 버전] 은 끄면 aria-disabled 이고 누름 처리기가 돌지 않는다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { VersionColumn } from './VersionColumn.tsx';
import { ColumnItem } from './VersionColumn.tsx';
import type { VersionColumnRow } from './VersionColumn.tsx';

afterEach(cleanup);

const ROWS: VersionColumnRow[] = [
  {
    key: 'k2',
    name: '판 둘',
    badge: { label: '배지 둘', look: 'blue' },
    sum: '꼬리 둘',
    editing: true,
    editNote: '편집 글',
  },
  {
    key: 'k1',
    name: '판 하나',
    badge: { label: '배지 하나', look: 'success' },
  },
  {
    key: 'base',
    name: '바탕 판',
    badge: { label: '배지 바탕', look: 'grey' },
    divided: true,
  },
];

function setup(extra: Partial<Parameters<typeof VersionColumn>[0]> = {}) {
  const onSelect = vi.fn();
  render(
    <VersionColumn
      title="열 머리"
      rows={ROWS}
      selected="k1"
      onSelect={onSelect}
      {...extra}
    />,
  );
  return { onSelect, column: screen.getByRole('region', { name: '열 머리' }) };
}

const rowButton = (key: string) =>
  document.querySelector(`[data-version="${key}"]`)!.closest('button')!;

describe('VersionColumn', () => {
  it('머리 글·52px, 줄마다 이름·배지·꼬리 글, 고른 줄만 aria-pressed', () => {
    const { column } = setup();
    const heading = within(column).getByRole('heading', { level: 3 });
    expect(heading.textContent).toBe('열 머리');
    expect(heading.className.split(/\s+/)).toContain('h-[52px]');
    expect(
      ROWS.map((row) => rowButton(row.key).getAttribute('aria-pressed')),
    ).toEqual(['false', 'true', 'false']);
    expect(rowButton('k2').textContent).toBe('판 둘배지 둘꼬리 둘편집 글');
    expect(rowButton('k1').textContent).toBe('판 하나배지 하나');
  });

  it('누르면 그 줄의 열쇠로 onSelect', () => {
    const { onSelect } = setup();
    fireEvent.click(rowButton('base'));
    expect(onSelect).toHaveBeenCalledWith('base');
  });

  it('편집 중 줄은 주황 테두리 + 꼬리표 0 · 편집 글 하나(주황 진한 글), 구분선은 그 줄 앞에만', () => {
    setup();
    expect(document.querySelectorAll('[data-edit-tag]')).toHaveLength(0);
    const notes = document.querySelectorAll('[data-edit-note]');
    expect(notes).toHaveLength(1);
    expect(notes[0]!.textContent).toBe('편집 글');
    expect(notes[0]!.className.split(/\s+/)).toEqual(
      expect.arrayContaining([
        'text-support-orange-dark',
        'text-style-pre-caption-02',
      ]),
    );
    expect(rowButton('k2').contains(notes[0]!)).toBe(true);
    expect(rowButton('k2').className).toContain('border-support-orange');
    expect(rowButton('k2').getAttribute('data-editing')).toBe('true');
    expect(rowButton('k1').className).not.toContain('border-support-orange');
    expect(rowButton('base').closest('li')!.className).toContain('border-t');
    expect(rowButton('k1').closest('li')!.className).not.toContain('border-t');
  });

  it('[새 버전]: 끄면 aria-disabled·title, 눌러도 처리기가 돌지 않는다. 켜면 돈다', () => {
    const onClick = vi.fn();
    setup({
      newVersion: { label: '새 판', off: true, title: '설명', onClick },
    });
    const off = screen.getByRole('button', { name: '새 판' });
    expect(off.getAttribute('aria-disabled')).toBe('true');
    expect(off.getAttribute('title')).toBe('설명');
    fireEvent.click(off);
    expect(onClick).not.toHaveBeenCalled();
    cleanup();
    setup({ newVersion: { label: '새 판', off: false, onClick } });
    const on = screen.getByRole('button', { name: '새 판' });
    expect(on.getAttribute('aria-disabled')).toBeNull();
    fireEvent.click(on);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('시안 v148 꼴(GW3R B2~B4): 고른 줄 글 secondary · 열 머리 아래 선 quaternary·좌우 0 · [새 버전] 동그라미 20 안 아이콘 16', () => {
    const { column } = setup({
      newVersion: { label: '새 판', off: false },
    });
    const picked = rowButton('k1').className.split(/\s+/);
    expect(picked).toContain('text-text-secondary');
    expect(picked).not.toContain('text-text-primary');
    const head = within(column)
      .getByRole('heading', { level: 3 })
      .className.split(/\s+/);
    expect(head).toEqual(
      expect.arrayContaining(['border-border-quaternary', 'px-0']),
    );
    expect(head).not.toContain('border-border-tertiary');
    const circle = screen
      .getByRole('button', { name: '새 판' })
      .querySelector('span')!;
    expect(circle.className.split(/\s+/)).toContain('size-5');
    expect(circle.querySelector('svg')!.getAttribute('class')).toContain(
      'size-4',
    );
  });

  it('[새 버전]·끝 자리는 주면 그린다', () => {
    setup();
    expect(screen.queryByRole('button', { name: '새 판' })).toBeNull();
    cleanup();
    setup({ footer: <span data-testid="끝">끝 자리</span> });
    expect(screen.getByTestId('끝').closest('li')).not.toBeNull();
  });
});

// 밴드 LK2: 고정(읽기 전용) 줄은 이름 앞 14px 자물쇠(시안 v148 .a-item .lock) — aria-hidden 이라 버튼 이름은 그대로.
describe('ColumnItem locked', () => {
  const draw = (locked?: boolean) =>
    render(
      <ul>
        <ColumnItem
          selected={false}
          onSelect={() => {}}
          sum="꼬리"
          locked={locked}
        >
          지어낸 고정 줄
        </ColumnItem>
      </ul>,
    );

  it('locked → 이름 앞 svg 하나(aria-hidden · size-3.5 · text-text-tertiary), 버튼 이름 그대로', () => {
    draw(true);
    const item = screen.getByRole('button', { name: '지어낸 고정 줄꼬리' });
    const icons = item.querySelectorAll('svg');
    expect(icons).toHaveLength(1);
    const icon = icons[0]!;
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(icon.getAttribute('class')!.split(/\s+/)).toEqual(
      expect.arrayContaining(['size-3.5', 'shrink-0', 'text-text-tertiary']),
    );
    // 이름 앞(같은 칸 안 첫 자식)
    expect(icon.parentElement!.firstElementChild).toBe(icon);
    expect(icon.parentElement!.textContent).toBe('지어낸 고정 줄');
  });

  it('locked 없음 → svg 0', () => {
    draw();
    const item = screen.getByRole('button', { name: '지어낸 고정 줄꼬리' });
    expect(item.querySelectorAll('svg')).toHaveLength(0);
  });
});
