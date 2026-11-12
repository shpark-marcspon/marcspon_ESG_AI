// @vitest-environment jsdom
// RP-00 작성 안내(밴드 RPW6 — 발주서 §2, sid:MARC-ENT-530). translation-intro 시험 꼴. jsdom 은 tailwind 를 셈하지 않아 클래스·role·aria·차례로 잰다.
//   ⓐ 제목 h2 · 소개 h3 brand · 글은 판 RP-00_r1 그대로(판 글자를 시험에 한 번 더 적어 DR_TEXT 와 맞댄다) ⓑ 작성 과정 Step 셋(판과 같음)
//   ⓒ 표 둘(줄 2·3, 열 너비 215·167px 셈값) ⓓ 안내 기본 톤 ⓔ [시작하기] md 알약 solidBlack → onStart ⓕ 그리는 동안 요청 0 · 넘김 0.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { IntroScreen } from './IntroScreen.tsx';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const words = DR_TEXT.intro;

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

const screenText = () =>
  document.querySelector('[data-screen="drafting-intro"]')!.textContent!;

describe('IntroScreen (RP-00)', () => {
  it('ⓐ 제목 h2 = 「보고서 작성」, 소개 h3 은 text-text-brand · 글은 판 그대로', () => {
    draw();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      '보고서 작성',
    );
    const heading = screen.getByRole('heading', {
      level: 3,
      name: '보고서 작성이란',
    });
    expect(heading.classList.contains('text-text-brand')).toBe(true);
    for (const text of [...words.lead, words.hint])
      expect(screenText()).toContain(text);
    expect(words.hint).toBe(
      '시작하기 버튼을 눌러 보고서 프로젝트를 만들어 보세요.',
    );
  });

  it('ⓑ 「작성 과정」 목록의 Step 셋 — 판 RP-00 의 차례·이름 그대로', () => {
    draw();
    const items = within(
      screen.getByRole('list', { name: '작성 과정' }),
    ).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items.map((item) => item.querySelector('b')!.textContent)).toEqual([
      'Step 1',
      'Step 2',
      'Step 3',
    ]);
    expect(
      items.map((item) => item.querySelector('strong')!.textContent),
    ).toEqual(['전년도 보고서', '목차 설정', '개조식 초안']);
    // 과정 이름은 RP-02~04 STEP 띠와 같은 낱말이다.
    expect(words.flow.map((step) => step.title)).toEqual([
      ...DR_TEXT.steps.items,
    ]);
    for (const step of words.flow) expect(screenText()).toContain(step.body);
  });

  it('ⓒ 「올리는 것」 몸 줄 2 · 「받는 것」 3 · 첫 머리 칸 215px, 「넣기」 167px', () => {
    draw();
    const give = bodyRows('올리는 것');
    expect(give).toHaveLength(2);
    expect(give.map((row) => row.querySelector('td')!.textContent)).toEqual([
      '전년도 보고서 PDF',
      '목차',
    ]);
    // 밴드 WT1(sid:MARC-ENT-625, 시안 v233 RP-00): 설명 칸 「텍스트 선택이 가능한 PDF」.
    expect(give[0]!.querySelectorAll('td')[1]!.textContent).toBe(
      '텍스트 선택이 가능한 PDF 예요. 텍스트가 없는 그림 PDF 는 읽지 못해요',
    );
    const get = bodyRows('받는 것');
    expect(get).toHaveLength(3);
    expect(get.map((row) => row.querySelector('td')!.textContent)).toEqual([
      '개조식 초안',
      '원문 보기',
      '내려받기',
    ]);
    const giveHeads = within(
      screen.getByRole('table', { name: '올리는 것' }),
    ).getAllByRole('columnheader');
    expect(giveHeads.map((head) => head.textContent)).toEqual([
      '항목',
      '설명',
      '넣기',
    ]);
    expect(giveHeads[0]!.style.width).toBe('215px');
    expect(giveHeads[2]!.style.width).toBe('167px');
    const getHeads = within(
      screen.getByRole('table', { name: '받는 것' }),
    ).getAllByRole('columnheader');
    expect(getHeads.map((head) => head.textContent)).toEqual(['결과', '설명']);
    expect(getHeads[0]!.style.width).toBe('215px');
    // 판 글이 코드 사실과 맞다: 요구 내용 2,000자(REQUIREMENT_MAX) · 네 단계(outline.depths).
    expect(screenText()).toContain('요구 내용을 2,000자까지');
    expect(DR_TEXT.outline.depths).toHaveLength(4);
  });

  it('ⓓ intro-info 는 기본 톤이고 글은 판 그대로(RP-04 안내와 같은 글)', () => {
    draw();
    const info = screen.getByTestId('intro-info');
    expect(info.getAttribute('data-tone')).toBe('default');
    expect(info.textContent).toBe(words.info);
    expect(words.info).toBe(DR_TEXT.result.guide);
  });

  it('ⓔ [시작하기]는 h-9·rounded-full·bg-button-black, 누르면 onStart 한 번', () => {
    const { onStart } = draw();
    const start = screen.getByRole('button', { name: '시작하기' });
    for (const name of ['h-9', 'rounded-full', 'bg-button-black'])
      expect(start.classList.contains(name), name).toBe(true);
    expect(onStart).not.toHaveBeenCalled();
    fireEvent.click(start);
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it('ⓕ 그리는 동안 요청 0 · 스스로 넘기지 않는다(onStart 0)', () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    const { onStart } = draw();
    expect(fetch).not.toHaveBeenCalled();
    expect(onStart).not.toHaveBeenCalled();
  });
});
