// @vitest-environment jsdom
// TR-00 번역 안내(밴드 TRP3 — 발주서 §3, sid:MARC-ENT-435). jsdom 은 tailwind 를 셈하지 않아 클래스·role·aria·차례로 잰다(계산 색은 e2e).
//   ⓐ 제목 h2 · 소개 h3 brand ⓑ 과정 목록 셋 ⓒ 표 둘(줄 5·4, 열 너비 215·167px 셈값) ⓓ 안내 기본 톤 ⓔ [시작하기] md 알약 solidBlack → onStart.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { IntroScreen } from './IntroScreen.tsx';

afterEach(cleanup);

const words = TR_TEXT.intro;

function draw() {
  const onStart = vi.fn();
  render(<IntroScreen onStart={onStart} />);
  return { onStart };
}

/** 표 몸 줄(머리 줄 뺌). */
const bodyRows = (name: string) =>
  within(screen.getByRole('table', { name }))
    .getAllByRole('row')
    .filter((row) => row.closest('tbody') !== null);

describe('IntroScreen (TR-00)', () => {
  it('ⓐ 제목 h2 = 「영문번역」, 소개 h3 은 text-text-brand · 글은 판 그대로', () => {
    draw();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      words.title,
    );
    const heading = screen.getByRole('heading', {
      level: 3,
      name: words.heading,
    });
    expect(heading.classList.contains('text-text-brand')).toBe(true);
    const screenText = document.querySelector(
      '[data-screen="translation-intro"]',
    )!.textContent!;
    for (const text of [...words.lead, words.hint])
      expect(screenText).toContain(text);
  });

  it('ⓑ 「번역 과정」 목록의 항목 셋(차례 Step 1~3)', () => {
    draw();
    const items = within(
      screen.getByRole('list', { name: words.flowTitle }),
    ).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(
      items.map((item) => item.querySelector('strong')!.textContent),
    ).toEqual(words.flow.map((step) => step.title));
  });

  it('ⓒ 「올리는 것」 몸 줄 5 · 「받는 것」 4 · 첫 머리 칸 215px, 「넣기」 167px', () => {
    draw();
    expect(bodyRows(words.give.title)).toHaveLength(5);
    expect(bodyRows(words.get.title)).toHaveLength(4);
    const giveHeads = within(
      screen.getByRole('table', { name: words.give.title }),
    ).getAllByRole('columnheader');
    expect(giveHeads.map((head) => head.textContent)).toEqual([
      ...words.give.head,
    ]);
    expect(giveHeads[0]!.style.width).toBe('215px');
    expect(giveHeads[2]!.style.width).toBe('167px');
    const getHeads = within(
      screen.getByRole('table', { name: words.get.title }),
    ).getAllByRole('columnheader');
    expect(getHeads.map((head) => head.textContent)).toEqual([
      ...words.get.head,
    ]);
    expect(getHeads[0]!.style.width).toBe('215px');
  });

  it('ⓓ intro-info 는 기본 톤이고 글은 TR_TEXT.intro.info', () => {
    draw();
    const info = screen.getByTestId('intro-info');
    expect(info.getAttribute('data-tone')).toBe('default');
    expect(info.textContent).toBe(words.info);
  });

  it('ⓔ [시작하기]는 h-9·rounded-full·bg-button-black, 누르면 onStart 한 번', () => {
    const { onStart } = draw();
    const start = screen.getByRole('button', { name: words.start });
    for (const name of ['h-9', 'rounded-full', 'bg-button-black'])
      expect(start.classList.contains(name), name).toBe(true);
    fireEvent.click(start);
    expect(onStart).toHaveBeenCalledTimes(1);
  });
});
