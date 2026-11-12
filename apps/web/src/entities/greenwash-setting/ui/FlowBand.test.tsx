// @vitest-environment jsdom
// 처리 흐름 띠(밴드 AS3b ② — 발주서 §3-4): 마디 key == 서버 칸 key(사본 픽스처) · 이름 = 넘긴 label · 누름 → onPick · 고친 칸 「고침」·이름표
//   · 서버가 짚은 칸 표시 · 고른 마디 하나만 aria-pressed · 없는 key 마디는 누를 수 없음. 글은 지어낸 것이다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { GREENWASH_SETTING_TEXT } from '../config/text.ts';
import { FlowBand } from './FlowBand.tsx';
import type { FlowBandProps } from './FlowBand.tsx';

afterEach(cleanup);

const w = GREENWASH_SETTING_TEXT.flow;
/** 서버 PROMPT_IDS 사본. */
const SERVER_PROMPT_IDS = ['detect', 'eval', 'repair', 'low_only'];
const LABELS = ['지어낸 찾기', '지어낸 판정', '지어낸 고치기', '지어낸 낮음'];
const GROUPS = [
  {
    key: 'judge',
    prompts: SERVER_PROMPT_IDS.map((key, index) => ({
      key,
      label: LABELS[index]!,
    })),
  },
];

function show(props: Partial<FlowBandProps> = {}) {
  const onPick = vi.fn();
  render(
    <FlowBand
      groups={GROUPS}
      picked={{ group: 0, prompt: 0 }}
      edited={[]}
      refused={[]}
      onPick={onPick}
      words={w}
      {...props}
    />,
  );
  return onPick;
}
const nodes = () => [...document.querySelectorAll('[data-flow-key]')];

describe('처리 흐름 띠', () => {
  it('마디 넷 = 서버 칸 key 차례, 이름표 「n. label 프롬프트 보기」(label 은 넘긴 것)', () => {
    show();
    expect(nodes().map((node) => node.getAttribute('data-flow-key'))).toEqual(
      SERVER_PROMPT_IDS,
    );
    expect(nodes().map((node) => node.getAttribute('aria-label'))).toEqual(
      LABELS.map((label, index) => w.nodeLabel(index + 1, label, false)),
    );
    expect(screen.getByRole('region', { name: w.title })).toBeTruthy();
  });

  it('누름 → onPick(그 칸 자리) · 고른 마디 하나만 aria-pressed', () => {
    const onPick = show({ picked: { group: 0, prompt: 1 } });
    expect(nodes().map((node) => node.getAttribute('aria-pressed'))).toEqual([
      'false',
      'true',
      'false',
      'false',
    ]);
    fireEvent.click(
      screen.getByRole('button', {
        name: w.nodeLabel(3, '지어낸 고치기', false),
      }),
    );
    expect(onPick).toHaveBeenCalledWith({ group: 0, prompt: 2 });
  });

  it('고친 칸: 「● 고침」·이름표 「, 고침」 — 그 마디만', () => {
    show({ edited: [{ group: 0, prompt: 3 }] });
    const low = screen.getByRole('button', {
      name: w.nodeLabel(4, '지어낸 낮음', true),
    });
    expect(within(low).getByTestId('flow-edited').textContent).toBe(w.edited);
    expect(screen.getAllByTestId('flow-edited')).toHaveLength(1);
  });

  it('이름은 한 줄 말줄임 칸(min-w-0 · truncate) — 전체 이름은 title 과 이름표에 남는다(밴드 GP4)', () => {
    show({ edited: [{ group: 0, prompt: 0 }] });
    const label = within(
      screen.getByRole('button', { name: w.nodeLabel(1, '지어낸 찾기', true) }),
    ).getByTestId('flow-node-label');
    expect(label.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['min-w-0', 'truncate']),
    );
    expect(label.getAttribute('title')).toBe('지어낸 찾기');
    expect(label.textContent).toBe('지어낸 찾기');
  });

  it('서버가 짚은 칸 → 그 마디에 slot-refused 표시', () => {
    show({ refused: [{ group: 0, prompt: 1 }] });
    const marks = screen.getAllByTestId('slot-refused');
    expect(marks).toHaveLength(1);
    expect(
      marks[0]!.closest('[data-flow-key]')!.getAttribute('data-flow-key'),
    ).toBe('eval');
    expect(marks[0]!.textContent).toBe(w.refused);
    // 이름표가 안의 글을 덮으니 그 마디의 접근 이름에 「고칠 곳 있음」이 들어 있다(이슈 329 L1)
    expect(
      screen.getByRole('button', {
        name: `${w.nodeLabel(2, LABELS[1]!, false)}, ${w.refused}`,
      }),
    ).toBeTruthy();
    expect(
      nodes().filter((node) =>
        node.getAttribute('aria-label')!.includes(w.refused),
      ),
    ).toHaveLength(1);
  });

  it('응답에 없는 key 의 마디는 꺼짐 — 눌러도 onPick 0', () => {
    const onPick = show({
      groups: [
        { key: 'judge', prompts: [{ key: 'eval', label: '지어낸 판정' }] },
      ],
    });
    const detect = document.querySelector(
      '[data-flow-key="detect"]',
    ) as HTMLButtonElement;
    expect(detect.disabled).toBe(true);
    fireEvent.click(detect);
    expect(onPick).not.toHaveBeenCalled();
  });
});

// 밴드 PF1(T1): inline 이면 겉 카드 꼴 0 · h4 소제목(시안 .a-sub), 없으면 지금 꼴 — 띠 이름표·마디 누름은 둘 다 그대로.
describe('처리 흐름 띠 inline(PF1)', () => {
  const CARD = ['rounded-dialog', 'bg-background-primary', 'p-8'];
  const band = () => screen.getByRole('region', { name: w.title });
  const classes = (element: Element) => element.className.split(/\s+/);

  it('inline 없음 → 따로 카드 꼴 · 제목 h3', () => {
    show();
    expect(classes(band())).toEqual(expect.arrayContaining(CARD));
    expect(
      within(band()).getByRole('heading', { level: 3, name: w.title }),
    ).toBeTruthy();
    expect(within(band()).queryByRole('heading', { level: 4 })).toBeNull();
  });

  it('inline → 카드 꼴 0 · h4 소제목 700 14 primary + note 400 12 tertiary 왼쪽 6', () => {
    show({ inline: true });
    for (const one of CARD) expect(classes(band())).not.toContain(one);
    expect(within(band()).queryByRole('heading', { level: 3 })).toBeNull();
    const head = within(band()).getByRole('heading', { level: 4 });
    expect(classes(head)).toEqual(
      expect.arrayContaining(['text-style-pre-body-04', 'text-text-primary']),
    );
    const note = head.querySelector('small')!;
    expect(note.textContent).toBe(w.note);
    expect(classes(note)).toEqual(
      expect.arrayContaining([
        'ml-1.5',
        'text-style-pre-caption-03',
        'text-text-tertiary',
      ]),
    );
  });

  it('inline 이어도 마디 이름표·누름 → onPick 그대로', () => {
    const onPick = show({ inline: true });
    expect(nodes().map((node) => node.getAttribute('aria-label'))).toEqual(
      LABELS.map((label, index) => w.nodeLabel(index + 1, label, false)),
    );
    fireEvent.click(
      within(band()).getByRole('button', {
        name: w.nodeLabel(3, LABELS[2]!, false),
      }),
    );
    expect(onPick).toHaveBeenCalledWith({ group: 0, prompt: 2 });
  });
});
