// @vitest-environment jsdom
// 수치 칸(밴드 TRW0b, 발주서 §3-5): null → 「–」(단위 없이), 0 → 「0」+단위.
import { cleanup, render } from '@testing-library/react';
import { waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';
import { vi } from 'vitest';

import { StatTiles } from './StatTiles.tsx';

afterEach(cleanup);

describe('StatTiles', () => {
  it('null 은 「–」, 0 은 「0」 — 둘을 가른다', () => {
    render(
      <StatTiles
        items={[
          {
            key: 'fixed',
            label: '자동 수정한 페이지',
            value: null,
            unit: 'page',
            note: '돌리지 않음 · 검수가 멈춤',
          },
          {
            key: 'untranslated',
            label: '번역하지 못한 페이지',
            value: 0,
            unit: 'page',
          },
          { key: 'issues', label: '검수 이슈', value: 23, unit: 'count' },
        ]}
      />,
    );
    const tile = (key: string) =>
      document.querySelector(`[data-stat="${key}"]`)!;
    expect(
      tile('fixed').querySelector('[data-testid="stat-value"]')!.textContent,
    ).toBe('–');
    expect(tile('fixed').textContent).toBe(
      '자동 수정한 페이지–돌리지 않음 · 검수가 멈춤',
    );
    expect(
      tile('untranslated').querySelector('[data-testid="stat-value"]')!
        .textContent,
    ).toBe('0');
    expect(tile('untranslated').textContent).toBe('번역하지 못한 페이지0개');
    expect(tile('issues').textContent).toBe('검수 이슈23건');
  });
});

// 밴드 TRP4 ②-7: 칸 안 Card 에 gw-m-rise + 70ms 시차(li 에는 없음 — e2e 칸 높이 단언), 값은 CountUp(움직임 켬이면 0 에서).
describe('StatTiles 움직임(TRP4)', () => {
  const ITEMS = [
    { key: 'a', label: '가', value: 12, unit: 'page' as const },
    { key: 'b', label: '나', value: null, unit: 'page' as const },
    { key: 'c', label: '다', value: 3, unit: 'count' as const },
    { key: 'd', label: '라', value: 40, unit: 'count' as const },
  ];
  const value = (key: string) =>
    document.querySelector(`[data-stat="${key}"] [data-testid="stat-value"]`)!
      .textContent;
  afterEach(() => vi.unstubAllGlobals());

  it('ⓐ 칸마다 Card 에 gw-m-rise, --gw-m-delay 0·70·140·210ms, li 에는 gw-m-rise 없음', () => {
    render(<StatTiles items={ITEMS} />);
    const cards = [
      ...document.querySelectorAll('[data-stat] > *'),
    ] as HTMLElement[];
    expect(cards).toHaveLength(4);
    for (const card of cards)
      expect(card.classList.contains('gw-m-rise')).toBe(true);
    expect(
      cards.map((card) => card.style.getPropertyValue('--gw-m-delay')),
    ).toEqual(['0ms', '70ms', '140ms', '210ms']);
    for (const li of document.querySelectorAll('[data-stat]'))
      expect(li.classList.contains('gw-m-rise')).toBe(false);
  });

  it('ⓑ 움직임 켬: 처음 값은 0 → 끝 값으로, null 칸은 처음부터 「–」', async () => {
    vi.stubGlobal(
      'matchMedia',
      (query: string) =>
        ({
          matches: !query.includes('reduce'),
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as unknown as MediaQueryList,
    );
    render(<StatTiles items={ITEMS} />);
    expect(value('a')).toBe('0');
    expect(value('b')).toBe('–');
    await waitFor(() => expect(value('a')).toBe('12'));
    await waitFor(() => expect(value('d')).toBe('40'));
    expect(value('b')).toBe('–');
  });
});

// 밴드 TRW2(6c 10-26): A·B 견주기 칸(pair) — 「12 / 9」 + 단위 하나, 없는 쪽만 「–」, 둘 다 없으면 단위 없음. pair 없는 칸은 그대로.
describe('StatTiles A·B 견주기(TRW2)', () => {
  it('pair 는 value 대신 「A / B」, 「/」 는 tertiary', () => {
    render(
      <StatTiles
        items={[
          {
            key: 'issues',
            label: '검수 이슈 · A / B',
            value: null,
            unit: 'count',
            pair: { A: 12, B: 9 },
          },
          {
            key: 'misses',
            label: '용어집 미반영 · A / B',
            value: null,
            unit: 'count',
            pair: { A: null, B: 3 },
          },
          {
            key: 'none',
            label: '없음',
            value: null,
            unit: 'count',
            pair: { A: null, B: null },
          },
        ]}
      />,
    );
    const tile = (key: string) =>
      document.querySelector(`[data-stat="${key}"]`)!;
    const value = (key: string) =>
      tile(key).querySelector('[data-testid="stat-value"]')!.textContent;
    expect(value('issues')).toBe('12 / 9');
    expect(tile('issues').textContent).toBe('검수 이슈 · A / B12 / 9건');
    expect(tile('issues').querySelector('[data-style="B"]')!.textContent).toBe(
      '9',
    );
    expect(
      tile('issues')
        .querySelector('[data-style="A"]')!
        .nextElementSibling!.classList.contains('text-text-tertiary'),
    ).toBe(true);
    expect(value('misses')).toBe('– / 3');
    expect(tile('none').textContent).toBe('없음– / –');
  });
});

// 밴드 TRW8 ⑧: 읽는 중 칸(pending) — 값·메모 자리 SkeletonBar 둘 · 값 글 0 · 감쌈은 disabled·aria-busy 단추.
//   rise 는 처음 한 번: 값이 들어와도 Card 가 같은 요소(누를 칸) · 누를 것 없이 들어와 새로 붙으면 rise 0. pending 없는 칸 DOM 그대로.
describe('StatTiles 읽는 중 칸(TRW8 ⑧)', () => {
  const base = { label: '확인할 곳', unit: 'place' as const };
  const word = {
    key: 'translated',
    label: '번역한 페이지',
    value: 2,
    unit: 'page' as const,
  };
  const tile = (key: string) =>
    document.querySelector(`[data-stat="${key}"]`) as HTMLElement;
  /** 칸의 Card(단추로 감쌌으면 그 안). */
  const card = (key: string) =>
    tile(key).querySelector(':scope > button > *') ??
    tile(key).querySelector(':scope > *')!;

  it('pending → data-pending · 막대 둘 · 값 글 0 · disabled·aria-busy 단추(stat-open 0) · 다른 칸은 li > Card 그대로', () => {
    render(
      <StatTiles
        items={[word, { key: 'checks', ...base, value: null, pending: true }]}
        columns={5}
      />,
    );
    const checks = tile('checks');
    expect(checks.getAttribute('data-pending')).toBe('');
    expect(checks.querySelectorAll('[data-skeleton-bar]')).toHaveLength(2);
    expect(checks.querySelector('[data-testid="stat-value"]')).toBeNull();
    expect(checks.textContent).toBe('확인할 곳');
    const button = checks.querySelector('button')!;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(checks.querySelector('[data-testid="stat-open"]')).toBeNull();
    const plain = tile('translated');
    expect(plain.hasAttribute('data-pending')).toBe(false);
    expect(plain.querySelector('button')).toBeNull();
    expect(plain.firstElementChild!.className).toContain('gw-m-rise');
    expect(plain.querySelectorAll('[data-skeleton-bar]')).toHaveLength(0);
  });

  it('rise 한 번: pending → 값 + 누름이면 같은 Card 요소 · 값 글 · stat-open', () => {
    const { rerender } = render(
      <StatTiles
        items={[word, { key: 'checks', ...base, value: null, pending: true }]}
      />,
    );
    const li = tile('checks');
    const before = card('checks');
    expect(before.className).toContain('gw-m-rise');
    const plainCard = card('translated');
    const onOpen = vi.fn();
    rerender(
      <StatTiles
        items={[word, { key: 'checks', ...base, value: 3, onOpen }]}
      />,
    );
    expect(tile('checks')).toBe(li);
    expect(card('checks')).toBe(before);
    // 같은 Card 에서 rise 를 떼지 않는다(움직임 도중 끊기지 않게 — 검증 B2).
    expect(card('checks').className).toContain('gw-m-rise');
    expect(li.hasAttribute('data-pending')).toBe(false);
    expect(li.querySelector('[data-testid="stat-open"]')).toBeTruthy();
    expect(li.querySelector('[data-skeleton-bar]')).toBeNull();
    // 다른 칸은 그대로(같은 요소 · rise 그대로).
    expect(card('translated')).toBe(plainCard);
    expect(plainCard.className).toContain('gw-m-rise');
  });

  it('rise 한 번: pending → 누를 것 없는 값(「–」)이면 감쌈이 바뀌어 새 Card — rise 0', () => {
    const { rerender } = render(
      <StatTiles
        items={[{ key: 'checks', ...base, value: null, pending: true }]}
      />,
    );
    const before = card('checks');
    rerender(<StatTiles items={[{ key: 'checks', ...base, value: null }]} />);
    const after = card('checks');
    expect(after).not.toBe(before);
    expect(after.className).not.toContain('gw-m-rise');
    expect(
      tile('checks').querySelector('[data-testid="stat-value"]')!.textContent,
    ).toBe('–');
  });
});
