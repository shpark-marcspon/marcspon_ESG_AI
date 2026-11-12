// @vitest-environment jsdom
// 화면 뼈대 머리 줄 제목 굵기(GW3R A1 — 시안 「관리자」 900): 쓰는 자리 font-black(토큰 표는 그대로 — 로그인과 같은 꼴).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from './AppShell.tsx';

afterEach(cleanup);

describe('AppShell 머리 줄 제목', () => {
  it('h1 은 nanum-display-01 + font-black(900)', () => {
    render(<AppShell menu={[]} menuLabel="지어낸 메뉴" title="지어낸 제목" />);
    const h1 = screen.getByRole('heading', { level: 1, name: '지어낸 제목' });
    expect(h1.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['text-style-nanum-display-01', 'font-black']),
    );
  });
});

// 하위 줄(밴드 LN1, sid:MARC-ENT-441 · 시안 AD-02_r3 .a-subnav): 부모 li 안 ul · 꺼짐 · 고름.
const SUB_MENU = [
  { id: 'a', label: '가 항목' },
  {
    id: 'p',
    label: '부모 항목',
    childrenLabel: '지어낸 하위 묶음',
    children: [
      { id: 'p-on', label: '켜진 하위' },
      { id: 'p-off', label: '꺼진 하위', disabled: true },
      { id: 'p-link', label: '링크 하위', href: '/x' },
    ],
  },
] as const;

const navOf = () => screen.getByRole('navigation', { name: '지어낸 메뉴' });
const currentLabels = () =>
  [...navOf().querySelectorAll('[aria-current="page"]')].map(
    (node) => node.textContent,
  );

describe('AppShell 하위 줄(밴드 LN1)', () => {
  it('하위 줄은 부모 li 안의 ul(aria-label = childrenLabel)로 늘 펼쳐 그린다 · 시안 값 클래스', () => {
    render(<AppShell menu={SUB_MENU} menuLabel="지어낸 메뉴" title="제목" />);
    const group = screen.getByRole('list', { name: '지어낸 하위 묶음' });
    const parent = screen.getByRole('button', { name: '부모 항목' });
    expect(group.parentElement).toBe(parent.parentElement);
    expect(group.parentElement?.tagName).toBe('LI');
    expect(
      [...group.querySelectorAll(':scope > li')].map((li) => li.textContent),
    ).toEqual(['켜진 하위', '꺼진 하위', '링크 하위']);
    expect(group.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['bg-[#111315]', 'py-1.5']),
    );
    const sub = screen.getByRole('button', { name: '켜진 하위' });
    expect(sub.querySelector('svg')).toBeNull();
    expect(sub.className.split(/\s+/)).toEqual(
      expect.arrayContaining([
        'min-h-[32px]',
        'px-3',
        'py-1.5',
        'justify-start',
        'text-left',
        'text-style-pre-caption-03',
        'text-text-secondary-inverse',
      ]),
    );
    expect(screen.getByRole('link', { name: '링크 하위' })).toHaveProperty(
      'tagName',
      'A',
    );
  });

  it('꺼진 하위 줄: aria-disabled · opacity-40 · 누름 0 · Tab 에 남음(button)', () => {
    const onSelect = vi.fn();
    render(
      <AppShell
        menu={SUB_MENU}
        menuLabel="지어낸 메뉴"
        title="제목"
        onSelect={onSelect}
      />,
    );
    const off = screen.getByRole('button', { name: '꺼진 하위' });
    expect(off.getAttribute('aria-disabled')).toBe('true');
    expect(off.hasAttribute('disabled')).toBe(false);
    expect(off.className.split(/\s+/)).toContain('opacity-40');
    fireEvent.click(off);
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '켜진 하위' }));
    expect(onSelect).toHaveBeenCalledExactlyOnceWith('p-on');
  });

  it('currentId 가 하위 줄이면 그 줄과 부모만 aria-current(형제·다른 항목 0) — 하위 줄은 흰 글 700, 부모는 막대', () => {
    render(
      <AppShell
        menu={SUB_MENU}
        currentId="p-on"
        menuLabel="지어낸 메뉴"
        title="제목"
      />,
    );
    expect(currentLabels()).toEqual(['부모 항목', '켜진 하위']);
    const sub = screen.getByRole('button', { name: '켜진 하위' });
    expect(sub.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['font-bold', 'text-text-primary-inverse']),
    );
    expect(sub.className).not.toContain('border-r-support-orange');
    expect(
      screen.getByRole('button', { name: '부모 항목' }).className.split(/\s+/),
    ).toEqual(
      expect.arrayContaining(['border-r-support-orange', 'text-orange-400']),
    );
  });

  it('currentId 가 부모면 부모만 aria-current(하위 줄 0)', () => {
    render(
      <AppShell
        menu={SUB_MENU}
        currentId="p"
        menuLabel="지어낸 메뉴"
        title="제목"
      />,
    );
    expect(currentLabels()).toEqual(['부모 항목']);
  });

  it('children 없는 메뉴는 하위 ul 을 그리지 않는다(nav 안 ul 하나, li 는 항목 수)', () => {
    render(
      <AppShell
        menu={[
          { id: 'a', label: '가' },
          { id: 'b', label: '나', disabled: true },
          { id: 'c', label: '다', children: [] },
        ]}
        currentId="a"
        menuLabel="지어낸 메뉴"
        title="제목"
      />,
    );
    expect(navOf().querySelectorAll('ul')).toHaveLength(1);
    expect(navOf().querySelectorAll('li')).toHaveLength(3);
    expect(currentLabels()).toEqual(['가']);
  });
});

// 맨 아래 줄(밴드 WS2, sid:MARC-ISSUE-371 L18 · 시안 admin-r1.css margin-top:auto).
describe('AppShell 맨 아래 줄(pinBottom)', () => {
  it('pinBottom 항목은 메뉴 ul 의 마지막 li 그대로 mt-auto, ul 은 flex-1 — 다른 li 는 클래스 없음', () => {
    render(
      <AppShell
        menu={[
          { id: 'a', label: '가' },
          { id: 'b', label: '나' },
          { id: 'z', label: '맨 아래', pinBottom: true },
        ]}
        menuLabel="지어낸 메뉴"
        title="제목"
      />,
    );
    const list = navOf().querySelector('ul')!;
    expect(list.className.split(/\s+/)).toContain('flex-1');
    const items = [...list.querySelectorAll(':scope > li')];
    expect(items.map((li) => li.textContent)).toEqual(['가', '나', '맨 아래']);
    expect(items.at(-1)!.className).toBe('mt-auto');
    expect(items.slice(0, -1).map((li) => li.hasAttribute('class'))).toEqual([
      false,
      false,
    ]);
  });

  it('pinBottom 없는 메뉴는 그대로: ul 클래스 m-0 flex list-none flex-col p-0, li 에 class 없음', () => {
    render(
      <AppShell
        menu={[
          { id: 'a', label: '가' },
          { id: 'b', label: '나', pinBottom: false },
        ]}
        menuLabel="지어낸 메뉴"
        title="제목"
      />,
    );
    const list = navOf().querySelector('ul')!;
    expect(list.className).toBe('m-0 flex list-none flex-col p-0');
    expect(
      [...list.querySelectorAll(':scope > li')].map((li) =>
        li.hasAttribute('class'),
      ),
    ).toEqual([false, false]);
  });
});
