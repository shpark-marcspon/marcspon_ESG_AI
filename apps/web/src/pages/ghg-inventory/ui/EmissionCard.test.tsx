// @vitest-environment jsdom
// 배출량 현황 카드 움직임(밴드 DB4 — sid:MARC-TICK-543 · 발주서 §2-②·③ · §3 시험 2~6 · 감독 판단 2·3). 값은 지어낸 값.
//   고리 쓸기 = 대시보드 도넛 꼴(mask 안 원 하나에 gw-m-sweep · 120ms · 바탕 고리 mask 밖) · 가운데 합 굴림(끝 글자 = BASE 바이트).
//   때: 첫 그림·연도 바꿈만 — 같은 해 다시 읽기(새 rows · 같은 해)·접고 펴기·접힌 채 해 바꿈 뒤 펴기에는 안 움직임.
//   jsdom 에는 matchMedia·rAF 시계가 없어 흉내 낸다(InventoryScreen.test 는 흉내 없이 — 끝 글자가 바로).
import { act } from 'react';

import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import type { EntryRows } from '../../../entities/ghg/model/index.ts';
import { EmissionCard } from './EmissionCard.tsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const words = GHG_TEXT.inventory.card;

function motionStubs({ reduce = false }: { reduce?: boolean } = {}) {
  const queue = new Map<number, FrameRequestCallback>();
  let next = 1;
  let now = 1000;
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches:
      reduce ? query.includes(': reduce') : query.includes('no-preference'),
    media: query,
    onchange: null,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent: () => false,
  }));
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    const id = next++;
    queue.set(id, callback);
    return id;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => queue.delete(id));
  const advance = (ms: number) =>
    act(() => {
      now += ms;
      const run = [...queue.values()];
      queue.clear();
      run.forEach((callback) => callback(now));
    });
  return {
    advance,
    pending: () => queue.size,
    finish: () => {
      for (let step = 0; step < 50; step += 1) advance(50);
    },
  };
}

/** BASE 씨앗과 같은 지어낸 rows(합 1234.565 + 0.004 → 표시 1234.57). */
const rowsOf = (
  year: number,
  [one, two]: [string, string] = ['1234.565', '0.004'],
): EntryRows => ({
  year,
  years: [year - 2, year - 1, year],
  decimals: 2,
  unit: 'tCO2-eq',
  configured: true,
  scopes: [
    {
      scopeId: '1',
      scopeName: '지어낸 범위 가',
      values: { [`${year}`]: one },
      rows: [],
    },
    {
      scopeId: '2',
      scopeName: '지어낸 범위 나',
      values: { [`${year}`]: two },
      rows: [],
    },
  ] as EntryRows['scopes'],
});

/** BASE 486bb14d 의 글자(DB4.out/base-text.txt). */
const BASE = {
  total: '1234.57',
  ring: '배출량 비율 지어낸 범위 가 1234.57 tCO2-eq, 지어낸 범위 나 0 tCO2-eq',
};

const total = () => screen.getByTestId('emission-total');
const ring = () => screen.getByTestId('emission-ring');
const sweep = () => ring().querySelector('mask [data-sweep]') as SVGElement;
const rolling = () => total().querySelector('[data-rolling]');
const toggle = (name: string) =>
  fireEvent.click(screen.getByRole('button', { name }));

describe('현황 카드 움직임(밴드 DB4)', () => {
  it('고리 쓸기: mask 안 원 하나에 gw-m-sweep(--gw-m-delay 120ms · --gw-m-round = 둘레 · dasharray 둘레) · 호는 mask 안 <g> 에 · 바탕 고리는 mask 밖(클래스 0)', () => {
    motionStubs();
    render(<EmissionCard rows={rowsOf(2026)} />);
    const masks = ring().querySelectorAll('mask');
    expect(masks).toHaveLength(1);
    const circle = sweep();
    expect(circle.getAttribute('class')).toBe('gw-m-sweep');
    expect(circle.style.getPropertyValue('--gw-m-delay')).toBe('120ms');
    const round = 2 * Math.PI * 52;
    expect(Number(circle.style.getPropertyValue('--gw-m-round'))).toBeCloseTo(
      round,
      6,
    );
    expect(Number(circle.getAttribute('stroke-dasharray'))).toBeCloseTo(
      round,
      6,
    );
    expect(circle.getAttribute('stroke')).toBe('white');
    const group = ring().querySelector('g[mask]')!;
    expect(group.getAttribute('mask')).toBe(`url(#${masks[0]!.id})`);
    expect(group.querySelectorAll('[data-scope]')).toHaveLength(2);
    const base = ring().querySelector(':scope > circle')!;
    expect(base.getAttribute('class')).not.toContain('gw-m-');
    expect(base.closest('g[mask]')).toBeNull();
    expect(ring().getAttribute('aria-label')).toBe(BASE.ring);
  });

  it('시험 2·3: 가운데 합이 0.00 에서 굴러 끝 글자 = BASE 바이트(소수 둘 · 쉼표 0) · 1,000ms 안에 끝 · 단위·「총배출량」은 처음부터 제자리', () => {
    const clock = motionStubs();
    render(<EmissionCard rows={rowsOf(2026)} />);
    const frame = () =>
      rolling()!.querySelector('[aria-hidden]:not(.invisible)')!.textContent;
    expect(frame()).toBe('0.00');
    expect(screen.getByTestId('emission-total-unit').textContent).toBe(
      'tCO2-eq',
    );
    expect(screen.getByTestId('emission-total-label').textContent).toBe(
      words.total,
    );
    clock.advance(16);
    clock.advance(400);
    expect(frame()).toMatch(/^[0-9]{1,4}\.[0-9]{2}$/);
    clock.advance(400); // 816 — 120 + 700 = 820 바로 전
    expect(rolling()).not.toBeNull();
    clock.advance(184); // 1,000
    expect(rolling()).toBeNull();
    expect(clock.pending()).toBe(0);
    expect(total().textContent).toBe(BASE.total);
    expect(total().getAttribute('aria-label')).toBe(BASE.total);
  });

  it('시험 4: 움직임 줄임이면 첫 그림부터 끝 글자 · 굴림 0 · rAF 0(쓸기 클래스는 CSS 가 no-preference 안에서만 — motion.test)', () => {
    const clock = motionStubs({ reduce: true });
    render(<EmissionCard rows={rowsOf(2026)} />);
    expect(rolling()).toBeNull();
    expect(clock.pending()).toBe(0);
    expect(total().textContent).toBe(BASE.total);
  });

  it('시험 5: 같은 해 다시 읽기(새 rows · 값 바뀜)엔 안 굴리고 바로 새 글자 · 같은 노드 · 해를 바꾸면 새 노드로 다시 굴림·쓸기', () => {
    const clock = motionStubs();
    const { rerender } = render(<EmissionCard rows={rowsOf(2026)} />);
    clock.finish();
    const before = ring();
    rerender(<EmissionCard rows={rowsOf(2026, ['10', '2.5'])} />);
    expect(rolling()).toBeNull();
    expect(total().textContent).toBe('12.5');
    expect(ring()).toBe(before);
    rerender(<EmissionCard rows={rowsOf(2025)} />);
    expect(ring()).not.toBe(before);
    expect(sweep().getAttribute('class')).toBe('gw-m-sweep');
    expect(rolling()).not.toBeNull();
    clock.finish();
    expect(total().textContent).toBe(BASE.total);
  });

  it('시험 5 · 감독 판단 2: 접고 펴면 쓸기·굴림 0 · 접힌 채 해가 바뀌어도 펼 때 0 · 그 뒤 펼친 채 해를 바꾸면 다시', () => {
    const clock = motionStubs();
    const { rerender } = render(<EmissionCard rows={rowsOf(2026)} />);
    toggle(words.collapse);
    clock.finish();
    toggle(words.expand);
    expect(sweep().getAttribute('class')).toBeNull();
    expect(sweep().style.getPropertyValue('--gw-m-delay')).toBe('');
    expect(rolling()).toBeNull();
    toggle(words.collapse);
    rerender(<EmissionCard rows={rowsOf(2025)} />);
    toggle(words.expand);
    expect(sweep().getAttribute('class')).toBeNull();
    expect(rolling()).toBeNull();
    expect(total().textContent).toBe(BASE.total);
    rerender(<EmissionCard rows={rowsOf(2024)} />);
    expect(sweep().getAttribute('class')).toBe('gw-m-sweep');
    expect(rolling()).not.toBeNull();
    clock.finish();
  });

  it('시험 6: 굴리는 동안 화면 읽기에는 끝 글자만(바깥 aria-label 그대로 · 프레임·깔개 aria-hidden · sr-only 하나) · 고리 aria-label BASE 그대로', () => {
    const clock = motionStubs();
    render(<EmissionCard rows={rowsOf(2026)} />);
    clock.advance(16);
    clock.advance(300);
    expect(total().getAttribute('aria-label')).toBe(BASE.total);
    const spoken = [...rolling()!.children].filter(
      (child) => child.getAttribute('aria-hidden') !== 'true',
    );
    expect(spoken.map((one) => one.className)).toEqual(['sr-only']);
    expect(spoken[0]!.textContent).toBe(BASE.total);
    expect(rolling()!.querySelector('.invisible')!.textContent).toBe(
      BASE.total,
    );
    expect(total().className).toContain('tabular-nums');
    expect(ring().getAttribute('aria-label')).toBe(BASE.ring);
    clock.finish();
  });

  it('줄임표 꼴(12자 이상)은 굴리지 않음 · 0 은 굴리지 않음', () => {
    motionStubs();
    render(<EmissionCard rows={rowsOf(2026, ['123456789.12', '0'])} />);
    expect(rolling()).toBeNull();
    expect(total().textContent).toBe('123456789.12');
    cleanup();
    render(<EmissionCard rows={rowsOf(2026, ['0', '0'])} />);
    expect(rolling()).toBeNull();
    expect(total().textContent).toBe('0');
  });
});

// 밴드 DB5(sid:MARC-TICK-544 — 발주서 §2-① · §3 ①③④ · 감독 판단 1): 범례 값 칸도 가운데 합과 같은 지연(120)·길이(700)·때(moving).
//   끝 글자 씨앗은 BASE 34681f54 에서 뜬 DB5.out/base-text.txt(지어낸 rows 12345.6 / 7 → 범례 「12345.6」「7」, 1234.565 / 0.004 → 「1234.57」「0」).
describe('현황 카드 범례 값 굴림(밴드 DB5)', () => {
  const BASE5 = {
    one: '12345.6',
    two: '7',
    li1: '지어낸 범위 가12345.6tCO2-eq',
    li2: '지어낸 범위 나7tCO2-eq',
    ring: '배출량 비율 지어낸 범위 가 12345.6 tCO2-eq, 지어낸 범위 나 7 tCO2-eq',
  };
  const two: [string, string] = ['12345.6', '7'];
  const value = (id: string) => screen.getByTestId(`emission-${id}-value`);
  const legendRolling = (id: string) =>
    value(id).querySelector('[data-rolling]');
  const frameOf = (node: Element) =>
    node.querySelector('[data-rolling] [aria-hidden]:not(.invisible)')
      ?.textContent ?? null;

  it('시험 ①: 범례 두 값이 가운데 합과 같은 때·지연(120 전엔 0)으로 굴러 같은 때 끝 · 끝 글자 = BASE 바이트 · 이름·단위는 처음부터 제자리', () => {
    const clock = motionStubs();
    render(<EmissionCard rows={rowsOf(2026, two)} />);
    expect(frameOf(value('1'))).toBe('0.0');
    expect(frameOf(value('2'))).toBe('0');
    expect(frameOf(total())).toBe('0.0');
    expect(screen.getByTestId('emission-1').textContent).toContain(
      '지어낸 범위 가',
    );
    clock.advance(16);
    clock.advance(110); // 첫 프레임에서 110ms — 120 전
    expect(frameOf(value('1'))).toBe('0.0');
    expect(frameOf(value('2'))).toBe('0');
    expect(frameOf(total())).toBe('0.0');
    clock.advance(200); // 310 — 셋 다 굴리는 중
    expect(frameOf(value('1'))).not.toBe('0.0');
    expect(frameOf(value('1'))).toMatch(/^[0-9]{1,5}\.[0-9]$/);
    expect(frameOf(total())).not.toBe('0.0');
    clock.advance(500); // 810 — 120 + 700 = 820 바로 전
    expect(legendRolling('1')).not.toBeNull();
    expect(legendRolling('2')).not.toBeNull();
    expect(rolling()).not.toBeNull();
    clock.advance(10); // 820
    expect(legendRolling('1')).toBeNull();
    expect(legendRolling('2')).toBeNull();
    expect(rolling()).toBeNull();
    expect(clock.pending()).toBe(0);
    expect(value('1').textContent).toBe(BASE5.one);
    expect(value('2').textContent).toBe(BASE5.two);
    expect(screen.getByTestId('emission-1').textContent).toBe(BASE5.li1);
    expect(screen.getByTestId('emission-2').textContent).toBe(BASE5.li2);
    expect(value('1').className).toContain('tabular-nums');
  });

  it('시험 ①: 접고 펴기·같은 해 같은 값 다시 그리기(검색 — base 그대로)·같은 해 값 바뀜엔 범례 안 굴림 · 해를 바꾸면 다시', () => {
    const clock = motionStubs();
    const { rerender } = render(<EmissionCard rows={rowsOf(2026, two)} />);
    clock.finish();
    rerender(<EmissionCard rows={rowsOf(2026, two)} />);
    expect(legendRolling('1')).toBeNull();
    rerender(<EmissionCard rows={rowsOf(2026, ['10', '2.5'])} />);
    expect(legendRolling('1')).toBeNull();
    expect(value('1').textContent).toBe('10');
    expect(value('2').textContent).toBe('2.5');
    toggle(words.collapse);
    toggle(words.expand);
    expect(legendRolling('1')).toBeNull();
    expect(legendRolling('2')).toBeNull();
    rerender(<EmissionCard rows={rowsOf(2025, two)} />);
    expect(legendRolling('1')).not.toBeNull();
    clock.finish();
    expect(value('1').textContent).toBe(BASE5.one);
  });

  it('시험 ⑥(DB4 검증 권고 1): 굴리는 도중 같은 해 글자가 바뀌면 굴림을 멈추고 바로 새 글자(다시 굴리지 않음 · rAF 0)', () => {
    const clock = motionStubs();
    const { rerender } = render(<EmissionCard rows={rowsOf(2026, two)} />);
    clock.advance(16);
    clock.advance(300);
    expect(legendRolling('1')).not.toBeNull();
    expect(rolling()).not.toBeNull();
    rerender(<EmissionCard rows={rowsOf(2026, ['20.5', '3'])} />);
    expect(legendRolling('1')).toBeNull();
    expect(legendRolling('2')).toBeNull();
    expect(rolling()).toBeNull();
    expect(value('1').textContent).toBe('20.5');
    expect(value('2').textContent).toBe('3');
    expect(total().textContent).toBe('23.5');
    clock.advance(16);
    expect(legendRolling('1')).toBeNull();
    expect(rolling()).toBeNull();
    expect(clock.pending()).toBe(0);
  });

  it('시험 ③: 움직임 줄임이면 범례도 첫 그림부터 끝 글자 · rAF 0', () => {
    const clock = motionStubs({ reduce: true });
    render(<EmissionCard rows={rowsOf(2026, two)} />);
    expect(legendRolling('1')).toBeNull();
    expect(legendRolling('2')).toBeNull();
    expect(clock.pending()).toBe(0);
    expect(value('1').textContent).toBe(BASE5.one);
    expect(value('2').textContent).toBe(BASE5.two);
  });

  it('시험 ④: 굴리는 동안 범례 값은 화면 읽기에 끝 글자만(프레임·깔개 aria-hidden · sr-only 하나) · 고리 aria-label BASE 그대로', () => {
    const clock = motionStubs();
    render(<EmissionCard rows={rowsOf(2026, two)} />);
    clock.advance(16);
    clock.advance(300);
    for (const [id, text] of [
      ['1', BASE5.one],
      ['2', BASE5.two],
    ] as const) {
      const spoken = [...legendRolling(id)!.children].filter(
        (child) => child.getAttribute('aria-hidden') !== 'true',
      );
      expect(spoken.map((one) => one.className)).toEqual(['sr-only']);
      expect(spoken[0]!.textContent).toBe(text);
      expect(legendRolling(id)!.querySelector('.invisible')!.textContent).toBe(
        text,
      );
    }
    expect(ring().getAttribute('aria-label')).toBe(BASE5.ring);
    clock.finish();
  });

  it('「-」·0 범례 칸은 첫 그림부터 제자리(굴림 0) · 0.004 → 「0」 도 제자리', () => {
    motionStubs();
    render(<EmissionCard rows={rowsOf(2026, ['0', '-'])} />);
    expect(legendRolling('1')).toBeNull();
    expect(legendRolling('2')).toBeNull();
    expect(value('1').textContent).toBe('0');
    expect(value('2').textContent).toBe('-');
    cleanup();
    render(<EmissionCard rows={rowsOf(2026)} />);
    expect(legendRolling('2')).toBeNull();
    expect(value('2').textContent).toBe('0');
    expect(legendRolling('1')).not.toBeNull();
  });
});
