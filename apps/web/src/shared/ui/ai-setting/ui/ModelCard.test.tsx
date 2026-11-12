// @vitest-environment jsdom
// AI 설정 모델 카드(시안 v148 .e-formrows — GW3R B9): 줄마다 라벨 칸(160·옅은 회색·500 14 tertiary·좌우 24) | 값 칸, 고르기는 공용 NativeSelect.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import { ModelCard } from './ModelCard.tsx';
import type { ModelCardRow } from './ModelCard.tsx';

afterEach(cleanup);

const ROW: ModelCardRow = {
  key: 'slot',
  route: {
    label: '모델',
    value: 'b',
    name: '지어낸 모델 나',
    options: [
      { value: 'a', label: '지어낸 모델 가' },
      { value: 'b', label: '지어낸 모델 나' },
    ],
  },
  temperature: { label: '온도', value: '0.3' },
  maxOutputTokens: { label: '상한', value: '2000' },
};

function setup(readOnly = false) {
  render(
    <ModelCard
      title="지어낸 카드"
      note="지어낸 곁 글"
      rows={[ROW]}
      readOnly={readOnly}
    />,
  );
  return screen.getByRole('region', { name: '지어낸 카드' });
}

const words = (element: Element) => element.className.split(/\s+/);

describe('ModelCard 꼴(B9)', () => {
  it('dl[data-step] 안 줄 셋 — dt 라벨 칸 꼴, 차례 모델 → 온도 → 상한', () => {
    const card = setup();
    const row = card.querySelector('[data-step="slot"]')!;
    expect(row.tagName).toBe('DL');
    const labels = [...row.querySelectorAll('dt')];
    expect(labels.map((dt) => dt.textContent)).toEqual([
      '모델',
      '온도',
      '상한',
    ]);
    for (const dt of labels)
      expect(words(dt)).toEqual(
        expect.arrayContaining([
          'w-40',
          'bg-support-grey-subtle',
          'text-style-pre-body-05',
          'text-text-tertiary',
          'px-6',
        ]),
      );
  });

  it('고르기는 NativeSelect 꼴(appearance-none · secondary), 머리 h4 다음 형제가 곁 글', () => {
    const card = setup();
    const select = screen.getByRole('combobox', { name: '모델' });
    expect(words(select)).toEqual(
      expect.arrayContaining(['appearance-none', 'text-text-secondary']),
    );
    expect(words(select)).not.toContain('text-text-primary');
    expect(card.querySelector('h4')!.nextElementSibling!.textContent).toBe(
      '지어낸 곁 글',
    );
  });

  it('readOnly 면 고칠 칸 0, 값은 글', () => {
    const card = setup(true);
    expect(card.querySelectorAll('select, input')).toHaveLength(0);
    expect(card.querySelector('[data-value="route"]')!.textContent).toBe(
      '지어낸 모델 나',
    );
  });
});

// 밴드 LK2 §7 B9: 수 칸(온도·상한) 폭 80(w-20).
describe('ModelCard 수 칸 폭(LK2 B9)', () => {
  it('온도·상한 글 칸은 w-20(w-full 아님)', () => {
    setup();
    for (const name of ['온도', '상한']) {
      const input = screen.getByRole('textbox', { name });
      expect(words(input)).toContain('w-20');
      expect(words(input)).not.toContain('w-full');
    }
  });
});

// AV1 검증 R4: 「…에 쓰여요」 줄(dd)도 dl 안이라 앞에 dt 이름이 하나 있다 — 보이는 꼴 0(sr-only).
describe('ModelCard 쓰는 곳 줄의 dt(AV1 R4)', () => {
  it('uses 가 있으면 model-uses dd 앞에 sr-only dt 하나(기본 PARTS_TEXT.modelUses, usesLabel 로 바꾼다)', () => {
    const view = render(
      <ModelCard
        title="지어낸 카드"
        rows={[{ ...ROW, uses: '지어낸 묶음에 쓰여요' }]}
        readOnly
      />,
    );
    const dd = screen.getByTestId('model-uses');
    const dt = dd.previousElementSibling!;
    expect(dt.tagName).toBe('DT');
    expect(words(dt)).toEqual(['sr-only']);
    expect(dt.textContent).toBe(PARTS_TEXT.modelUses);
    expect(dd.parentElement!.querySelectorAll('dt')).toHaveLength(1);
    view.rerender(
      <ModelCard
        title="지어낸 카드"
        rows={[{ ...ROW, uses: '지어낸 묶음에 쓰여요' }]}
        readOnly
        usesLabel="지어낸 이름"
      />,
    );
    expect(
      screen.getByTestId('model-uses').previousElementSibling!.textContent,
    ).toBe('지어낸 이름');
  });

  it('uses 가 없으면 dt 도 dd 도 없다', () => {
    setup(true);
    expect(screen.queryByTestId('model-uses')).toBeNull();
    expect(screen.queryByText(PARTS_TEXT.modelUses)).toBeNull();
  });
});

// 밴드 IRA2 K3: temperature 가 없는 줄은 그 줄(dt·dd) 통째 0 — 다른 두 줄의 꼴·차례는 그대로, 같은 카드의 다른 칸은 그대로.
describe('ModelCard temperature 없는 줄(IRA2 K3)', () => {
  it('temperature 없으면 줄 둘(모델 → 상한) · 온도 라벨·값·글 칸 0, 옆 칸은 줄 셋 그대로', () => {
    const hidden: ModelCardRow = {
      key: 'hidden',
      route: ROW.route,
      maxOutputTokens: ROW.maxOutputTokens,
    };
    render(
      <ModelCard
        title="지어낸 카드"
        rows={[ROW, hidden]}
        readOnly={false}
        onTemperature={() => {}}
      />,
    );
    const card = screen.getByRole('region', { name: '지어낸 카드' });
    const row = card.querySelector('[data-step="hidden"]')!;
    expect([...row.querySelectorAll('dt')].map((dt) => dt.textContent)).toEqual(
      ['모델', '상한'],
    );
    expect(row.querySelector('[data-value="temperature"]')).toBeNull();
    expect(row.querySelectorAll('input')).toHaveLength(1);
    expect(row.textContent).not.toContain('온도');
    const kept = card.querySelector('[data-step="slot"]')!;
    expect(
      [...kept.querySelectorAll('dt')].map((dt) => dt.textContent),
    ).toEqual(['모델', '온도', '상한']);
  });
});
