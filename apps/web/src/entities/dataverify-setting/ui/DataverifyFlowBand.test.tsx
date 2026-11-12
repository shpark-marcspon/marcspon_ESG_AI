// @vitest-environment jsdom
// 데이터 검증 처리 흐름 띠 + 칸 고름(밴드 DVA2 — 발주서 §3-1-3): 마디 셋 = 서버 묶음 label 차례 · 없는 key 마디는 aria-disabled·누를 수 없음 · 마디 누름 → 그 묶음 칸 0(지시 글) ·
//   칸 고름 단추 둘(서버 label · 소문자 key) · 고친 칸 「● 고침」·마디 「고침」 · 짚은 칸 「고칠 곳 있음」 · 고정 상자·갈래 글 = config 글. 글은 지어낸 것이다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { DATAVERIFY_SETTING_TEXT } from '../config/text.ts';
import { DataverifyFlowBand } from './DataverifyFlowBand.tsx';
import type { DataverifyFlowBandProps } from './DataverifyFlowBand.tsx';

afterEach(cleanup);

const w = DATAVERIFY_SETTING_TEXT.flow;
/** 서버 GROUPS 의 칸 차례 사본(prompt_model_156.py — 지시 글·입력 글) · label 은 지어낸 것. */
const group = (key: string, label: string) => ({
  key,
  label,
  prompts: [
    { key: `${key}_system`, label: '지어낸 지시' },
    { key: `${key}_user`, label: '지어낸 입력' },
  ],
});
const GROUPS = [
  group('plan', '지어낸 계획'),
  group('review', '지어낸 검토'),
  group('insight', '지어낸 통찰'),
];

function show(props: Partial<DataverifyFlowBandProps> = {}) {
  const onPick = vi.fn();
  const view = render(
    <DataverifyFlowBand
      groups={GROUPS}
      picked={{ group: 0, prompt: 0 }}
      edited={[]}
      refused={[]}
      onPick={onPick}
      words={w}
      {...props}
    />,
  );
  return { onPick, view };
}
const nodes = () => [
  ...document.querySelectorAll<HTMLButtonElement>('[data-flow-key]'),
];
const picker = () => screen.getByRole('group', { name: w.picker });
const promptButtons = () => [
  ...picker().querySelectorAll<HTMLButtonElement>('[data-prompt-key]'),
];

describe('데이터 검증 처리 흐름 띠', () => {
  it('마디 셋 = 서버 묶음 label 차례 · 이름표 「n. label 프롬프트 보기」 · 하는 일·빈도는 웹 글', () => {
    show();
    expect(nodes().map((node) => node.getAttribute('data-flow-key'))).toEqual([
      'plan',
      'review',
      'insight',
    ]);
    expect(nodes().map((node) => node.getAttribute('aria-label'))).toEqual(
      GROUPS.map((one, index) => w.nodeLabel(index + 1, one.label, false)),
    );
    expect(
      screen.getAllByTestId('flow-node-label').map((node) => node.textContent),
    ).toEqual(['지어낸 계획', '지어낸 검토', '지어낸 통찰']);
    expect(
      screen.getAllByTestId('flow-runs').map((node) => node.textContent),
    ).toEqual(Object.values(w.steps).map((step) => step.runs));
    for (const step of Object.values(w.steps))
      expect(screen.getByText(step.does)).toBeTruthy();
    expect(screen.getByRole('region', { name: w.title })).toBeTruthy();
  });

  it('고정 상자·마름모·갈래 글 셋·끝 상자 = config 글(시안 「처리 흐름」)', () => {
    show();
    const fixed = (name: string) =>
      document.querySelector(`[data-flow-fixed="${name}"]`)!.textContent;
    expect(fixed('')).toBe(w.start.join(''));
    expect(fixed('question')).toBe(w.question.join(''));
    expect(fixed('warn')).toBe(w.warn.join(''));
    expect(fixed('out')).toBe(w.out.join(''));
    expect(fixed('end')).toBe(w.end.title + w.end.lines.join(''));
    for (const text of [w.yes, w.no, w.skip])
      expect(screen.getByText(text)).toBeTruthy();
    const board = document.querySelector('svg[aria-hidden]')!;
    expect(board.getAttribute('viewBox')).toBe('0 0 1028 288');
  });

  it('응답에 없는 key 의 마디는 aria-disabled · 누를 수 없다(이름 「–」) — 마디 차례는 그대로', () => {
    const { onPick } = show({
      groups: GROUPS.filter((one) => one.key !== 'review'),
    });
    const review = document.querySelector<HTMLButtonElement>(
      '[data-flow-key="review"]',
    )!;
    expect(review.disabled).toBe(true);
    expect(review.getAttribute('aria-disabled')).toBe('true');
    expect(review.getAttribute('aria-label')).toBeNull();
    expect(within(review).getByTestId('flow-node-label').textContent).toBe('–');
    fireEvent.click(review);
    expect(onPick).not.toHaveBeenCalled();
    // 번호는 흐름 차례(2 검토 빠짐 → 3 인사이트는 서버 자리 1)
    const insight = document.querySelector('[data-flow-key="insight"]')!;
    expect(insight.getAttribute('aria-disabled')).toBeNull();
    fireEvent.click(insight);
    expect(onPick).toHaveBeenCalledWith({ group: 1, prompt: 0 });
    expect(insight.getAttribute('aria-label')).toBe(
      w.nodeLabel(3, '지어낸 통찰', false),
    );
  });

  it('마디 누름 → onPick({group, prompt: 0}) · 고른 묶음 마디만 aria-pressed', () => {
    const { onPick } = show({ picked: { group: 1, prompt: 1 } });
    expect(nodes().map((node) => node.getAttribute('aria-pressed'))).toEqual([
      'false',
      'true',
      'false',
    ]);
    fireEvent.click(nodes()[2]!);
    expect(onPick).toHaveBeenLastCalledWith({ group: 2, prompt: 0 });
    fireEvent.click(nodes()[0]!);
    expect(onPick).toHaveBeenLastCalledWith({ group: 0, prompt: 0 });
  });

  it('칸 고름: 머리 「단계 n 이름」 + 빈도 · 단추 둘(서버 label · 소문자 key) → onPick({group, prompt: j}) · 고른 칸 aria-pressed', () => {
    const { onPick } = show({ picked: { group: 1, prompt: 0 } });
    expect(picker().querySelector('p')!.textContent).toBe(
      w.stepHead(2, '지어낸 검토') + w.steps.review.runs,
    );
    expect(
      promptButtons().map((button) => button.getAttribute('data-prompt-key')),
    ).toEqual(['review_system', 'review_user']);
    expect(promptButtons().map((button) => button.textContent)).toEqual([
      '지어낸 지시review_system',
      '지어낸 입력review_user',
    ]);
    expect(
      promptButtons().map((button) => button.getAttribute('aria-pressed')),
    ).toEqual(['true', 'false']);
    fireEvent.click(promptButtons()[1]!);
    expect(onPick).toHaveBeenLastCalledWith({ group: 1, prompt: 1 });
    expect(picker().querySelectorAll('button[aria-expanded]')).toHaveLength(0);
  });

  it('고친 칸 → 칸 단추 「● 고침」 · 그 마디 이름표 「, 고침」·꼬리 · 짚은 칸 → 칸 단추·마디 「고칠 곳 있음」', () => {
    show({
      picked: { group: 2, prompt: 0 },
      edited: [{ group: 2, prompt: 1 }],
      refused: [{ group: 2, prompt: 1 }],
    });
    const insight = nodes()[2]!;
    expect(insight.getAttribute('aria-label')).toBe(
      w.nodeLabel(3, '지어낸 통찰', true),
    );
    expect(within(insight).getByTestId('flow-edited').textContent).toBe(
      w.edited,
    );
    expect(within(insight).getByTestId('slot-refused').textContent).toBe(
      w.refused,
    );
    const [system, user] = promptButtons();
    expect(within(system!).queryByTestId('flow-edited')).toBeNull();
    expect(within(system!).queryByTestId('slot-refused')).toBeNull();
    expect(within(user!).getByTestId('flow-edited').textContent).toBe(w.edited);
    expect(within(user!).getByTestId('slot-refused').textContent).toBe(
      w.refused,
    );
    expect(within(nodes()[0]!).queryByTestId('flow-edited')).toBeNull();
  });

  it('inline 이면 겉 카드 0 · 소제목 h4(곁 글 small)', () => {
    show({ inline: true });
    const band = screen.getByTestId('flow-band');
    expect(band.className).not.toContain('rounded-dialog');
    expect(band.querySelector('h4')!.textContent).toBe(w.title + w.note);
  });
});
