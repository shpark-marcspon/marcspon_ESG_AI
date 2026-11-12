// @vitest-environment jsdom
// 보고서 작성 처리 흐름 띠 + 칸 고름(밴드 RPA3 — 발주서 §3-1-3): 번호 마디 둘 = 서버 묶음 label 차례 · 없는 key 마디는 aria-disabled·누를 수 없음 ·
//   마디 누름 → 그 묶음 칸 0 · 칸 고름 단추(서버 label · 소문자 key) · 고친 칸 「● 고침」·마디 「고침」 · 짚은 칸 「고칠 곳 있음」 · 고정 상자·갈래 글 = config 글. 글은 지어낸 것이다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { DRAFTING_SETTING_TEXT } from '../config/text.ts';
import { DraftingFlowBand } from './DraftingFlowBand.tsx';
import type { DraftingFlowBandProps } from './DraftingFlowBand.tsx';

afterEach(cleanup);

const w = DRAFTING_SETTING_TEXT.flow;
/** 서버 GROUPS 의 칸 차례 사본(prompt_model_v2.py) · label 은 지어낸 것. */
const group = (key: string, label: string, prompts: readonly string[]) => ({
  key,
  label,
  prompts: prompts.map((one, index) => ({
    key: one,
    label: `지어낸 칸 ${index + 1}`,
  })),
});
const GROUPS = [
  group('map', '지어낸 붙이기', ['map_system', 'map_user']),
  group('draft', '지어낸 초안', ['draft_system', 'draft_user']),
];

function show(props: Partial<DraftingFlowBandProps> = {}) {
  const onPick = vi.fn();
  const view = render(
    <DraftingFlowBand
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
const node = (key: string) =>
  document.querySelector<HTMLButtonElement>(`[data-flow-key="${key}"]`)!;
const picker = () => screen.getByRole('group', { name: w.picker });
const promptButtons = () => [
  ...picker().querySelectorAll<HTMLButtonElement>('[data-prompt-key]'),
];

describe('보고서 작성 처리 흐름 띠', () => {
  it('마디 = 번호 둘(서버 묶음 label 차례) · 이름표 · 하는 일·빈도는 웹 글', () => {
    show();
    expect(nodes().map((one) => one.getAttribute('data-flow-key'))).toEqual([
      'map',
      'draft',
    ]);
    expect(nodes().map((one) => one.getAttribute('aria-label'))).toEqual([
      w.nodeLabel(1, '지어낸 붙이기', false),
      w.nodeLabel(2, '지어낸 초안', false),
    ]);
    expect(
      screen.getAllByTestId('flow-node-label').map((one) => one.textContent),
    ).toEqual(['지어낸 붙이기', '지어낸 초안']);
    expect(
      screen.getAllByTestId('flow-runs').map((one) => one.textContent),
    ).toEqual([w.steps.map.runs, w.steps.draft.runs]);
    expect(within(node('map')).getByTestId('flow-node-name').textContent).toBe(
      '1지어낸 붙이기',
    );
    for (const step of Object.values(w.steps))
      expect(screen.getByText(step.does)).toBeTruthy();
    expect(screen.getByRole('region', { name: w.title })).toBeTruthy();
  });

  it('시작·출처 확인·끝 상자와 갈래 글 = config 글 · 판 1028×172 · 선 넷 · 마디 190×112(시안 자리 — v195 띠 위 빈자리 뺌)', () => {
    show();
    const fixed = (name: string) =>
      document.querySelector(`[data-flow-fixed="${name}"]`)!.textContent;
    expect(fixed('')).toBe(w.start.join(''));
    expect(fixed('check')).toBe(w.check);
    expect(fixed('end')).toBe(w.end.title + w.end.lines.join(''));
    expect(document.querySelector('[data-flow-branch]')!.textContent).toBe(
      w.branch,
    );
    const board = document.querySelector('svg[aria-hidden]')!;
    expect(board.getAttribute('viewBox')).toBe('0 0 1028 172');
    expect(
      [...board.querySelectorAll('path[marker-end]')].map((one) =>
        one.getAttribute('d'),
      ),
    ).toEqual(['M110 56H146', 'M340 56H396', 'M590 56H646', 'M850 56H896']);
    expect(node('map').style.left).toBe('150px');
    expect(node('draft').style.left).toBe('400px');
    expect(node('draft').style.width).toBe('190px');
    expect(node('draft').style.height).toBe('112px');
    // 마디는 띠 맨 위, 상자는 선 y 56 에 가운데(캔버스 v195 · 밴드 RPW5 #8)
    expect([node('map').style.top, node('draft').style.top]).toEqual([
      '0px',
      '0px',
    ]);
    const top = (selector: string) =>
      (document.querySelector(selector) as HTMLElement).style.top;
    expect(
      [
        '[data-flow-fixed=""]',
        '[data-flow-fixed="check"]',
        '[data-flow-fixed="end"]',
        '[data-flow-branch]',
      ].map(top),
    ).toEqual(['34px', '24px', '22px', '130px']);
  });

  it('응답에 없는 key 의 마디는 aria-disabled · 누를 수 없다(이름 「–」) — 마디 차례는 그대로', () => {
    const { onPick } = show({ groups: [GROUPS[1]!] });
    const one = node('map');
    expect(one.disabled).toBe(true);
    expect(one.getAttribute('aria-disabled')).toBe('true');
    expect(one.getAttribute('aria-label')).toBeNull();
    expect(within(one).getByTestId('flow-node-label').textContent).toBe('–');
    fireEvent.click(one);
    expect(onPick).not.toHaveBeenCalled();
    // 번호는 흐름 차례(1 빠짐 → 2 초안은 서버 자리 0)
    fireEvent.click(node('draft'));
    expect(onPick).toHaveBeenCalledWith({ group: 0, prompt: 0 });
    expect(node('draft').getAttribute('aria-label')).toBe(
      w.nodeLabel(2, '지어낸 초안', false),
    );
  });

  it('마디 누름 → onPick({group, prompt: 0}) · 고른 묶음 마디만 aria-pressed', () => {
    const { onPick } = show({ picked: { group: 1, prompt: 1 } });
    expect(nodes().map((one) => one.getAttribute('aria-pressed'))).toEqual([
      'false',
      'true',
    ]);
    fireEvent.click(node('map'));
    expect(onPick).toHaveBeenLastCalledWith({ group: 0, prompt: 0 });
  });

  it('칸 고름: 머리 「단계 2 이름」 + 머리 빈도 · 단추 둘(서버 label · 소문자 key, 서버 차례) → onPick({group, prompt: j})', () => {
    const { onPick } = show({ picked: { group: 1, prompt: 0 } });
    expect(picker().querySelector('p')!.textContent).toBe(
      w.stepHead(2, '지어낸 초안') + w.steps.draft.head,
    );
    expect(promptButtons().map((one) => one.textContent)).toEqual([
      '지어낸 칸 1draft_system',
      '지어낸 칸 2draft_user',
    ]);
    expect(
      promptButtons().map((one) => one.getAttribute('aria-pressed')),
    ).toEqual(['true', 'false']);
    fireEvent.click(promptButtons()[1]!);
    expect(onPick).toHaveBeenLastCalledWith({ group: 1, prompt: 1 });
  });

  it('고친 칸 → 칸 단추 「● 고침」 · 그 마디 이름표 「, 고침」 · 짚은 칸 → 칸 단추·마디 「고칠 곳 있음」', () => {
    show({
      picked: { group: 1, prompt: 0 },
      edited: [{ group: 1, prompt: 1 }],
      refused: [{ group: 1, prompt: 1 }],
    });
    const draft = node('draft');
    expect(draft.getAttribute('aria-label')).toBe(
      w.nodeLabel(2, '지어낸 초안', true),
    );
    expect(within(draft).getByTestId('flow-edited').textContent).toBe(w.edited);
    expect(within(draft).getByTestId('slot-refused').textContent).toBe(
      w.refused,
    );
    expect(within(node('map')).queryByTestId('flow-edited')).toBeNull();
    const [system, input] = promptButtons();
    expect(within(system!).queryByTestId('flow-edited')).toBeNull();
    expect(within(system!).queryByTestId('slot-refused')).toBeNull();
    expect(within(input!).getByTestId('flow-edited').textContent).toBe(
      w.edited,
    );
    expect(within(input!).getByTestId('slot-refused').textContent).toBe(
      w.refused,
    );
  });

  it('inline 이면 겉 카드 0 · 소제목 h4(곁 글 small)', () => {
    show({ inline: true });
    const band = screen.getByTestId('flow-band');
    expect(band.className).not.toContain('rounded-dialog');
    expect(band.querySelector('h4')!.textContent).toBe(w.title + w.note);
  });
});
