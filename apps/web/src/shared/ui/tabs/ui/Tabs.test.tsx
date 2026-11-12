// @vitest-environment jsdom
// 탭 감싸개(밴드 AV2, 344 SB2·SB3): 키트 tabs 위에 box 칸 글자 tertiary, line 목록 1px·칸 최소 96·가운데를 덧붙인다.
// 역할(tablist·tab)·화살표 이동·onValueChange 는 키트(Radix) 것이 그대로 산다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { Tabs, TabsContent, TabsList, TabsTrigger } from './Tabs.tsx';
import type { TabsProps } from './Tabs.tsx';

afterEach(cleanup);

function Sample({
  listClassName,
  triggerClassName,
  ...props
}: Partial<TabsProps> & { listClassName?: string; triggerClassName?: string }) {
  return (
    <Tabs defaultValue="b" {...props}>
      <TabsList aria-label="보기" className={listClassName}>
        <TabsTrigger value="a" className={triggerClassName}>
          전체
        </TabsTrigger>
        <TabsTrigger value="b">높음</TabsTrigger>
        <TabsTrigger value="c">낮음</TabsTrigger>
      </TabsList>
      <TabsContent value="a">가 내용</TabsContent>
      <TabsContent value="b">나 내용</TabsContent>
      <TabsContent value="c">다 내용</TabsContent>
    </Tabs>
  );
}

const classesOf = (element: Element) =>
  (element.getAttribute('class') ?? '').split(/\s+/);

describe('탭 감싸개', () => {
  it('box: 안 고른 칸 글자는 tertiary(quaternary 아님), 목록은 키트 box 그대로', () => {
    render(<Sample variant="box" />);
    const idle = screen.getByRole('tab', { name: '전체' });
    expect(idle.getAttribute('data-state')).toBe('inactive');
    expect(classesOf(idle)).toContain('text-text-tertiary');
    expect(classesOf(idle)).not.toContain('text-text-quaternary');
    expect(classesOf(idle)).toContain(
      'data-[state=active]:text-text-primary-inverse',
    );
    const list = classesOf(screen.getByRole('tablist'));
    for (const name of ['h-8', 'w-fit', 'bg-background-secondary', 'p-1'])
      expect(list).toContain(name);
    expect(list).not.toContain('border-b');
  });

  it('line: 목록 밑줄 1px(border-b-2 아님), 칸은 min-w-24·-mb-px·justify-center, 고른 칸 밑줄 2px 그대로', () => {
    render(<Sample variant="line" />);
    const list = classesOf(screen.getByRole('tablist'));
    expect(list).toContain('border-b');
    expect(list).not.toContain('border-b-2');
    for (const tab of screen.getAllByRole('tab')) {
      const classes = classesOf(tab);
      for (const name of ['min-w-24', '-mb-px', 'justify-center', 'border-b-2'])
        expect(classes).toContain(name);
      expect(classes).not.toContain('-mb-0.5');
    }
  });

  it('variant 를 안 주면 line', () => {
    render(<Sample />);
    expect(classesOf(screen.getByRole('tablist'))).toContain('border-b');
    expect(classesOf(screen.getByRole('tab', { name: '전체' }))).toContain(
      'min-w-24',
    );
  });

  it('tablist·tab 역할, ←→ 로 칸을 옮긴다(초점이 고른다)', async () => {
    render(<Sample />);
    expect(screen.getByRole('tablist').getAttribute('aria-label')).toBe('보기');
    expect(screen.getAllByRole('tab')).toHaveLength(3);
    const picked = screen.getByRole('tab', { name: '높음' });
    expect(picked.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tabpanel').textContent).toBe('나 내용');
    picked.focus();
    // radix 는 다음 틱에 초점을 옮기고 초점이 고른다(자동 활성)
    fireEvent.keyDown(picked, { key: 'ArrowRight' });
    await waitFor(() =>
      expect(
        screen.getByRole('tab', { name: '낮음' }).getAttribute('aria-selected'),
      ).toBe('true'),
    );
    fireEvent.keyDown(screen.getByRole('tab', { name: '낮음' }), {
      key: 'ArrowLeft',
    });
    await waitFor(() =>
      expect(picked.getAttribute('aria-selected')).toBe('true'),
    );
  });

  it('칸을 누르면 onValueChange 가 한 번 불린다', () => {
    const onValueChange = vi.fn();
    render(<Sample onValueChange={onValueChange} />);
    fireEvent.mouseDown(screen.getByRole('tab', { name: '전체' }));
    expect(onValueChange).toHaveBeenCalledTimes(1);
    expect(onValueChange).toHaveBeenCalledWith('a');
    expect(screen.getByRole('tabpanel').textContent).toBe('가 내용');
  });

  it('쓰는 쪽 className 이 이긴다', () => {
    render(
      <Sample
        variant="line"
        listClassName="border-b-0"
        triggerClassName="min-w-0"
      />,
    );
    const list = classesOf(screen.getByRole('tablist'));
    expect(list).toContain('border-b-0');
    expect(list).not.toContain('border-b');
    const tab = classesOf(screen.getByRole('tab', { name: '전체' }));
    expect(tab).toContain('min-w-0');
    expect(tab).not.toContain('min-w-24');
  });
});
