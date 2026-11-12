// @vitest-environment jsdom
// 중대성평가 IRO 처리 흐름 띠 + 칸 고름(밴드 IRA2 — 발주서 §3-1-3): 번호 마디 다섯 = 서버 묶음 label 차례 · 신뢰 출처 마디(번호 0) · 없는 key 마디는 aria-disabled·누를 수 없음 ·
//   마디 누름 → 그 묶음 칸 0 · 칸 고름 단추(컨트로버시 여섯 — 서버 label · 소문자 key) · 고친 칸 「● 고침」·마디 「고침」 · 짚은 칸 「고칠 곳 있음」 · 고정 상자 = config 글. 글은 지어낸 것이다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { MATERIALITY_SETTING_TEXT } from '../config/text.ts';
import { MaterialityFlowBand } from './MaterialityFlowBand.tsx';
import type { MaterialityFlowBandProps } from './MaterialityFlowBand.tsx';

afterEach(cleanup);

const w = MATERIALITY_SETTING_TEXT.flow;
/** 서버 GROUPS 의 칸 차례 사본(prompt_model_155.py) · label 은 지어낸 것. */
const group = (key: string, label: string, prompts: readonly string[]) => ({
  key,
  label,
  prompts: prompts.map((one, index) => ({
    key: one,
    label: `지어낸 칸 ${index + 1}`,
  })),
});
const GROUPS = [
  group('regulation', '지어낸 규제', [
    'regulation_system',
    'regulation_prefix',
    'regulation_input',
  ]),
  group('controversy', '지어낸 사건', [
    'keywords_system',
    'keywords_prefix',
    'keywords_input',
    'controversy_system',
    'controversy_prefix',
    'controversy_input',
  ]),
  group('impact', '지어낸 영향', ['impact_system', 'impact_input']),
  group('financial', '지어낸 재무', ['financial_system', 'financial_input']),
  group('pathway', '지어낸 경로', ['pathway_system', 'pathway_input']),
  group('whitelist', '지어낸 출처', [
    'whitelist_non_financial',
    'whitelist_financial',
  ]),
];
const KEYS = [
  'regulation',
  'controversy',
  'impact',
  'financial',
  'pathway',
  'whitelist',
];

function show(props: Partial<MaterialityFlowBandProps> = {}) {
  const onPick = vi.fn();
  const view = render(
    <MaterialityFlowBand
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

describe('중대성평가 IRO 처리 흐름 띠', () => {
  it('마디 = 번호 다섯(서버 묶음 label 차례) + 신뢰 출처(번호 없음) · 이름표 · 하는 일·빈도는 웹 글', () => {
    show();
    expect(nodes().map((one) => one.getAttribute('data-flow-key'))).toEqual(
      KEYS,
    );
    expect(nodes().map((one) => one.getAttribute('aria-label'))).toEqual([
      ...GROUPS.slice(0, 5).map((one, index) =>
        w.nodeLabel(index + 1, one.label, false),
      ),
      w.whitelistLabel('지어낸 출처', false),
    ]);
    expect(
      screen.getAllByTestId('flow-node-label').map((one) => one.textContent),
    ).toEqual(GROUPS.map((one) => one.label));
    expect(
      screen.getAllByTestId('flow-runs').map((one) => one.textContent),
    ).toEqual(Object.values(w.steps).map((step) => step.runs));
    // 번호 둥근 칸: 번호 마디 다섯만(신뢰 출처 마디는 이름만)
    expect(
      within(node('whitelist')).getByTestId('flow-node-name').textContent,
    ).toBe('지어낸 출처');
    expect(within(node('whitelist')).queryByTestId('flow-runs')).toBeNull();
    expect(within(node('whitelist')).getByText(w.whitelist.does)).toBeTruthy();
    expect(
      within(node('regulation')).getByTestId('flow-node-name').textContent,
    ).toBe('1지어낸 규제');
    for (const step of Object.values(w.steps))
      expect(screen.getByText(step.does)).toBeTruthy();
    expect(screen.getByRole('region', { name: w.title })).toBeTruthy();
  });

  it('고정 상자·끝 상자 = config 글 · 판 1028×288 · 선 여덟 + 점선 하나(신뢰 출처 → 마디 1)', () => {
    show();
    const fixed = (name: string) =>
      document.querySelector(`[data-flow-fixed="${name}"]`)!.textContent;
    expect(fixed('')).toBe(w.start.join(''));
    expect(fixed('out')).toBe(w.out.join(''));
    expect(fixed('end')).toBe(w.end.title + w.end.lines.join(''));
    const board = document.querySelector('svg[aria-hidden]')!;
    expect(board.getAttribute('viewBox')).toBe('0 0 1028 288');
    const paths = [...board.querySelectorAll('path[marker-end]')];
    expect(paths).toHaveLength(9);
    expect(
      paths
        .filter((one) => one.getAttribute('class')?.includes('dasharray'))
        .map((one) => one.getAttribute('d')),
    ).toEqual(['M163 220V206']);
    expect(node('whitelist').style.width).toBe('334px');
    expect(node('impact').style.top).toBe('16px');
  });

  it('응답에 없는 key 의 마디는 aria-disabled · 누를 수 없다(이름 「–」) — 마디 차례는 그대로', () => {
    const { onPick } = show({
      groups: GROUPS.filter(
        (one) => one.key !== 'impact' && one.key !== 'whitelist',
      ),
    });
    for (const key of ['impact', 'whitelist']) {
      const one = node(key);
      expect(one.disabled).toBe(true);
      expect(one.getAttribute('aria-disabled')).toBe('true');
      expect(one.getAttribute('aria-label')).toBeNull();
      expect(within(one).getByTestId('flow-node-label').textContent).toBe('–');
      fireEvent.click(one);
    }
    expect(onPick).not.toHaveBeenCalled();
    // 번호는 흐름 차례(3 영향 빠짐 → 4 재무는 서버 자리 2)
    fireEvent.click(node('financial'));
    expect(onPick).toHaveBeenCalledWith({ group: 2, prompt: 0 });
    expect(node('financial').getAttribute('aria-label')).toBe(
      w.nodeLabel(4, '지어낸 재무', false),
    );
  });

  it('마디 누름 → onPick({group, prompt: 0}) · 고른 묶음 마디만 aria-pressed(신뢰 출처 마디 → 서버 자리 5)', () => {
    const { onPick } = show({ picked: { group: 1, prompt: 3 } });
    expect(nodes().map((one) => one.getAttribute('aria-pressed'))).toEqual([
      'false',
      'true',
      'false',
      'false',
      'false',
      'false',
    ]);
    fireEvent.click(node('pathway'));
    expect(onPick).toHaveBeenLastCalledWith({ group: 4, prompt: 0 });
    fireEvent.click(node('whitelist'));
    expect(onPick).toHaveBeenLastCalledWith({ group: 5, prompt: 0 });
  });

  it('칸 고름: 머리 「단계 2 이름」 + 머리 빈도 · 단추 여섯(서버 label · 소문자 key, 서버 차례) → onPick({group, prompt: j})', () => {
    const { onPick } = show({ picked: { group: 1, prompt: 0 } });
    expect(picker().querySelector('p')!.textContent).toBe(
      w.stepHead(2, '지어낸 사건') + w.steps.controversy.head,
    );
    expect(
      promptButtons().map((one) => one.getAttribute('data-prompt-key')),
    ).toEqual(GROUPS[1]!.prompts.map((one) => one.key));
    expect(promptButtons()[3]!.textContent).toBe(
      '지어낸 칸 4controversy_system',
    );
    expect(
      promptButtons().map((one) => one.getAttribute('aria-pressed')),
    ).toEqual(['true', 'false', 'false', 'false', 'false', 'false']);
    fireEvent.click(promptButtons()[5]!);
    expect(onPick).toHaveBeenLastCalledWith({ group: 1, prompt: 5 });
    expect(picker().querySelectorAll('button[aria-expanded]')).toHaveLength(0);
  });

  it('신뢰 출처 칸 고름: 머리 「이름 · 곁 글」(단계 번호 0) · 칸 둘', () => {
    show({ picked: { group: 5, prompt: 1 } });
    expect(picker().querySelector('p')!.textContent).toBe(
      '지어낸 출처' + w.whitelist.head,
    );
    expect(promptButtons().map((one) => one.textContent)).toEqual([
      '지어낸 칸 1whitelist_non_financial',
      '지어낸 칸 2whitelist_financial',
    ]);
  });

  it('고친 칸 → 칸 단추 「● 고침」 · 그 마디 이름표 「, 고침」·꼬리 · 짚은 칸 → 칸 단추·마디 「고칠 곳 있음」(신뢰 출처 칸 → 신뢰 출처 마디)', () => {
    show({
      picked: { group: 0, prompt: 0 },
      edited: [
        { group: 0, prompt: 2 },
        { group: 5, prompt: 1 },
      ],
      refused: [{ group: 0, prompt: 2 }],
    });
    const regulation = node('regulation');
    expect(regulation.getAttribute('aria-label')).toBe(
      w.nodeLabel(1, '지어낸 규제', true),
    );
    expect(within(regulation).getByTestId('flow-edited').textContent).toBe(
      w.edited,
    );
    expect(within(regulation).getByTestId('slot-refused').textContent).toBe(
      w.refused,
    );
    expect(node('whitelist').getAttribute('aria-label')).toBe(
      w.whitelistLabel('지어낸 출처', true),
    );
    expect(within(node('whitelist')).getByTestId('flow-edited')).toBeTruthy();
    expect(within(node('controversy')).queryByTestId('flow-edited')).toBeNull();
    const [system, , input] = promptButtons();
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
