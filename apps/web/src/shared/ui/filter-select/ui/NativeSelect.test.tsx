// @vitest-environment jsdom
// 기본 select 한 꼴(sid:MARC-ENT-430, 202 2번): 네이티브 select 그대로(역할 combobox) + selectLook 꼴 + 오른쪽 ▾.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { FilterSelect } from './FilterSelect.tsx';
import { NativeSelect } from './NativeSelect.tsx';
import { SELECT_CHEVRON, SELECT_LOOK, SELECT_MIN_WIDTH } from './selectLook.ts';

afterEach(cleanup);

const words = (classes: string) => classes.split(/\s+/);

function renderSelect(props: Partial<Parameters<typeof NativeSelect>[0]> = {}) {
  render(
    <NativeSelect aria-label="상태" defaultValue="a" {...props}>
      <option value="a">가</option>
      <option value="b">나</option>
    </NativeSelect>,
  );
  return screen.getByRole('combobox', { name: '상태' });
}

describe('NativeSelect 꼴(ENT-430)', () => {
  it('네이티브 select · OS 화살표 없음 · 오른쪽 40 · 꼴(높이 36·모서리 8·글 secondary)', () => {
    const select = renderSelect();
    expect(select.tagName).toBe('SELECT');
    expect(words(select.className)).toEqual(
      expect.arrayContaining([
        'appearance-none',
        'pr-10',
        'h-9',
        'rounded-component',
        'text-text-secondary',
        'w-full',
      ]),
    );
  });

  it('감싼 쪽 최소 140, className 은 감싼 쪽에 간다(w-full)', () => {
    const select = renderSelect();
    expect(words(select.parentElement!.className)).toContain('min-w-[140px]');
    cleanup();
    const wide = renderSelect({ className: 'w-full' });
    expect(words(wide.parentElement!.className)).toContain('w-full');
    expect(words(wide.className)).not.toContain('min-w-[140px]');
  });

  it('▾ 는 select 의 형제 svg — 숨김·오른쪽 끝 16·tertiary·16', () => {
    const select = renderSelect();
    const chevron = select.nextElementSibling!;
    expect(chevron.tagName.toLowerCase()).toBe('svg');
    expect(chevron.getAttribute('aria-hidden')).toBe('true');
    expect(words(chevron.getAttribute('class')!)).toEqual(
      expect.arrayContaining([
        'right-4',
        'text-text-tertiary',
        'size-4',
        'pointer-events-none',
      ]),
    );
  });

  it('id·aria-label·disabled 를 넘기고, 고르면 onChange 한 번', () => {
    const onChange = vi.fn();
    const select = renderSelect({ id: 'year', onChange }) as HTMLSelectElement;
    expect(select.id).toBe('year');
    fireEvent.change(select, { target: { value: 'b' } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(select.value).toBe('b');
    cleanup();
    const off = renderSelect({ disabled: true }) as HTMLSelectElement;
    expect(off.disabled).toBe(true);
    expect(words(off.className)).toEqual(
      expect.arrayContaining(['disabled:opacity-40']),
    );
  });

  it('FilterSelect 와 같은 꼴 상수(selectLook)를 쓴다', () => {
    const select = renderSelect();
    render(
      <FilterSelect
        aria-label="기간"
        value="a"
        options={[{ value: 'a', label: '가' }]}
        onChange={() => {}}
      />,
    );
    const trigger = screen.getByRole('button', { name: '기간' });
    const look = words(SELECT_LOOK);
    expect(words(select.className)).toEqual(
      expect.arrayContaining(look.filter((word) => word !== 'px-4')),
    );
    expect(words(trigger.className)).toEqual(expect.arrayContaining(look));
    expect(words(trigger.className)).toContain(SELECT_MIN_WIDTH);
    expect(words(select.parentElement!.className)).toContain(SELECT_MIN_WIDTH);
    for (const chevron of [
      select.nextElementSibling!,
      trigger.querySelector('svg')!,
    ])
      expect(words(chevron.getAttribute('class')!)).toEqual(
        expect.arrayContaining(words(SELECT_CHEVRON)),
      );
  });
});
