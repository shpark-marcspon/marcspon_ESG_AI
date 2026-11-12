// @vitest-environment jsdom
// 영문번역 처리 흐름 띠 + 칸 고름(밴드 TRA1 — 발주서 §3-1-3): 마디 다섯 = 서버 묶음 label 차례 · 없는 key 마디는 누를 수 없음 · 마디 누름 → 그 묶음의 보이는 차례 첫 칸(TRA2 D1) · 번역 묶음 이어 붙임 안내(D8) ·
//   번역 묶음의 소묶음 셋(칸 아홉 다 듦 · 차례 = 시안) · 모르는 key 칸은 「그 밖」 · aria-expanded · 접힌 소묶음 「고침 n」 · 짚은 칸 「고칠 곳 있음」. 글은 지어낸 것이다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TRANSLATION_SETTING_TEXT } from '../config/text.ts';
import { TRANSLATE_SECTIONS } from '../model/index.ts';
import { TranslationFlowBand } from './TranslationFlowBand.tsx';
import type { TranslationFlowBandProps } from './TranslationFlowBand.tsx';

afterEach(cleanup);

const w = TRANSLATION_SETTING_TEXT.flow;
/** 서버 GROUPS 의 칸 차례 사본(prompt_model_158.py) — label 은 지어낸 것. */
const TRANSLATE_KEYS = [
  'tone_ceo_message',
  'tone_story',
  'tone_general',
  'style_a',
  'style_b',
  'style_rules',
  'subject_fragment_rules',
  'terminology_note',
  'table_rules',
];
const prompt = (key: string) => ({ key, label: `지어낸 ${key}` });
const GROUPS = [
  {
    key: 'translate',
    label: '지어낸 번역',
    prompts: TRANSLATE_KEYS.map(prompt),
  },
  { key: 'polish', label: '지어낸 윤문', prompts: [prompt('polish')] },
  {
    key: 'editorial_qa',
    label: '지어낸 QA',
    prompts: [prompt('editorial_qa')],
  },
  { key: 'review', label: '지어낸 검수', prompts: [prompt('review')] },
  {
    key: 'autofix',
    label: '지어낸 자동 수정',
    prompts: [prompt('autofix'), prompt('autofix_korean')],
  },
];

function show(props: Partial<TranslationFlowBandProps> = {}) {
  const onPick = vi.fn();
  const view = render(
    <TranslationFlowBand
      groups={GROUPS}
      picked={{ group: 0, prompt: 5 }}
      edited={[]}
      refused={[]}
      onPick={onPick}
      words={w}
      {...props}
    />,
  );
  return { onPick, view };
}
const nodes = () => [...document.querySelectorAll('[data-flow-key]')];
const sectionHeads = () =>
  screen
    .getByRole('group', { name: w.picker })
    .querySelectorAll('button[aria-expanded]');
const promptKeys = () =>
  [...document.querySelectorAll('[data-prompt-key]')].map((node) =>
    node.getAttribute('data-prompt-key'),
  );

describe('영문번역 처리 흐름 띠', () => {
  it('마디 다섯 = 서버 묶음 label 차례 · 이름표 「n. label 프롬프트 보기」 · 빈도 알약은 웹 글', () => {
    show();
    expect(nodes().map((node) => node.getAttribute('data-flow-key'))).toEqual([
      'translate',
      'polish',
      'editorial_qa',
      'review',
      'autofix',
    ]);
    expect(nodes().map((node) => node.getAttribute('aria-label'))).toEqual(
      GROUPS.map((group, index) => w.nodeLabel(index + 1, group.label, false)),
    );
    expect(
      screen.getAllByTestId('flow-runs').map((node) => node.textContent),
    ).toEqual(Object.values(w.steps).map((step) => step.runs));
    expect(screen.getByRole('region', { name: w.title })).toBeTruthy();
  });

  it('응답에 없는 key 의 마디는 누를 수 없다(disabled · 이름 「–」) — 마디 차례는 그대로', () => {
    const { onPick } = show({
      groups: GROUPS.filter((group) => group.key !== 'review'),
    });
    const review = document.querySelector<HTMLButtonElement>(
      '[data-flow-key="review"]',
    )!;
    expect(review.disabled).toBe(true);
    expect(review.getAttribute('aria-label')).toBeNull();
    expect(within(review).getByTestId('flow-node-label').textContent).toBe('–');
    fireEvent.click(review);
    expect(onPick).not.toHaveBeenCalled();
    // 마디 번호는 흐름 차례(4 검수 빠짐 → 5 자동 수정은 서버 자리 3)
    const autofix = document.querySelector('[data-flow-key="autofix"]')!;
    fireEvent.click(autofix);
    expect(onPick).toHaveBeenCalledWith({ group: 3, prompt: 0 });
    expect(autofix.getAttribute('aria-label')).toBe(
      w.nodeLabel(5, '지어낸 자동 수정', false),
    );
  });

  it('마디 누름 → onPick(그 묶음의 보이는 차례 첫 칸 — 번역은 style_rules) · 고른 묶음 마디만 aria-pressed', () => {
    const { onPick } = show();
    nodes().forEach((node) => fireEvent.click(node));
    expect(onPick.mock.calls.map(([at]) => at)).toEqual(
      GROUPS.map((_, group) => ({
        group,
        prompt: group === 0 ? TRANSLATE_KEYS.indexOf('style_rules') : 0,
      })),
    );
    expect(nodes().map((node) => node.getAttribute('aria-pressed'))).toEqual([
      'true',
      'false',
      'false',
      'false',
      'false',
    ]);
  });

  it('번역 소묶음 셋에 칸 아홉이 다 든다(셈 9) — 차례는 시안: 공통 넷 → 파트마다 셋 → 문체 둘', () => {
    expect(
      TRANSLATE_SECTIONS.flatMap((section) => section.prompts).sort(),
    ).toEqual([...TRANSLATE_KEYS].sort());
    show();
    const heads = [...sectionHeads()];
    expect(heads.map((head) => head.textContent)).toEqual([
      expect.stringContaining(w.sections.common.title),
      expect.stringContaining(w.sections.part.title),
      expect.stringContaining(w.sections.style.title),
    ]);
    // 처음에는 공통만 펼침(고른 칸 style_rules 도 공통) — 다 펼치면 아홉이 시안 차례
    expect(heads.map((head) => head.getAttribute('aria-expanded'))).toEqual([
      'true',
      'false',
      'false',
    ]);
    expect(heads[0]!.textContent).toContain(w.sectionCount(4, true));
    fireEvent.click(heads[1]!);
    fireEvent.click(heads[2]!);
    expect(promptKeys()).toEqual([
      'style_rules',
      'subject_fragment_rules',
      'terminology_note',
      'table_rules',
      'tone_ceo_message',
      'tone_story',
      'tone_general',
      'style_a',
      'style_b',
    ]);
    fireEvent.click(heads[0]!);
    expect(heads[0]!.getAttribute('aria-expanded')).toBe('false');
    expect(heads[0]!.textContent).toContain(w.sectionCount(4, false));
  });

  it('고른 칸이 든 소묶음은 펼침 · 칸 단추 누름 → onPick({group, prompt}) · 고른 칸 aria-pressed', () => {
    const { onPick } = show({ picked: { group: 0, prompt: 1 } });
    const heads = [...sectionHeads()];
    expect(heads.map((head) => head.getAttribute('aria-expanded'))).toEqual([
      'true',
      'true',
      'false',
    ]);
    const story = document.querySelector('[data-prompt-key="tone_story"]')!;
    expect(story.getAttribute('aria-pressed')).toBe('true');
    expect(story.textContent).toContain('지어낸 tone_story');
    fireEvent.click(
      document.querySelector('[data-prompt-key="terminology_note"]')!,
    );
    expect(onPick).toHaveBeenLastCalledWith({ group: 0, prompt: 7 });
    expect(
      screen.getByRole('group', { name: w.picker }).querySelector('p')!
        .textContent,
    ).toContain(w.stepHead(1, '지어낸 번역'));
  });

  it('모르는 key 칸은 끝 「그 밖」 · 소묶음 없는 묶음은 머리 줄 0 으로 서버 차례 그대로', () => {
    const groups = [
      {
        ...GROUPS[0]!,
        prompts: [...GROUPS[0]!.prompts, prompt('zz_new')],
      },
      ...GROUPS.slice(1),
    ];
    const { view } = show({ groups, picked: { group: 0, prompt: 9 } });
    const heads = [...sectionHeads()];
    expect(heads).toHaveLength(4);
    expect(heads[3]!.textContent).toContain(w.sections.other.title);
    expect(heads[3]!.getAttribute('aria-expanded')).toBe('true');
    expect(promptKeys()).toContain('zz_new');
    view.rerender(
      <TranslationFlowBand
        groups={groups}
        picked={{ group: 4, prompt: 1 }}
        edited={[]}
        refused={[]}
        onPick={vi.fn()}
        words={w}
      />,
    );
    expect(sectionHeads()).toHaveLength(0);
    expect(promptKeys()).toEqual(['autofix', 'autofix_korean']);
  });

  it('고친 칸 「● 고침」 · 접힌 소묶음 머리 「고침 n」 · 마디 이름표 「, 고침」 · 서버가 짚은 칸 「고칠 곳 있음」', () => {
    show({
      edited: [
        { group: 0, prompt: 0 },
        { group: 0, prompt: 2 },
        { group: 0, prompt: 5 },
      ],
      refused: [{ group: 0, prompt: 5 }],
    });
    const heads = [...sectionHeads()];
    // 파트마다 하나(접힘)에 고친 칸 둘
    expect(heads[1]!.getAttribute('aria-expanded')).toBe('false');
    expect(
      within(heads[1]! as HTMLElement).getByTestId('section-edited')
        .textContent,
    ).toBe(w.sectionEdited(2));
    expect(
      within(heads[2]! as HTMLElement).queryByTestId('section-edited'),
    ).toBeNull();
    const rules = document.querySelector('[data-prompt-key="style_rules"]')!;
    expect(
      within(rules as HTMLElement).getByTestId('flow-edited').textContent,
    ).toBe(w.edited);
    expect(
      within(rules as HTMLElement).getByTestId('slot-refused').textContent,
    ).toBe(w.refused);
    expect(
      document
        .querySelector('[data-flow-key="translate"]')!
        .getAttribute('aria-label'),
    ).toBe(`${w.nodeLabel(1, '지어낸 번역', true)}, ${w.refused}`);
    expect(
      within(
        document.querySelector('[data-flow-key="translate"]') as HTMLElement,
      ).getByTestId('slot-refused').textContent,
    ).toBe(w.refused);
  });

  it('refused 마디 접근 이름(이슈 476): 짚은 묶음 마디 이름에 「고칠 곳 있음」 · 고침 뒤 차례 · 짚음 0 이면 어느 마디에도 없음', () => {
    const marked = () =>
      nodes().filter((node) =>
        node.getAttribute('aria-label')?.includes(w.refused),
      );
    show({ refused: [{ group: 1, prompt: 0 }] });
    expect(
      screen.getByRole('button', {
        name: `${w.nodeLabel(2, '지어낸 윤문', false)}, ${w.refused}`,
      }),
    ).toBeTruthy();
    expect(marked()).toHaveLength(1);
    cleanup();
    // 같은 묶음이 고침 + 짚음: 「, 고침」 뒤 「, 고칠 곳 있음」
    show({
      edited: [{ group: 1, prompt: 0 }],
      refused: [{ group: 1, prompt: 0 }],
    });
    expect(
      screen.getByRole('button', {
        name: `${w.nodeLabel(2, '지어낸 윤문', true)}, ${w.refused}`,
      }),
    ).toBeTruthy();
    cleanup();
    // 고침만 있고 짚음 0
    show({ edited: [{ group: 1, prompt: 0 }] });
    expect(marked()).toHaveLength(0);
  });

  it('이어 붙임 안내 한 줄은 번역 묶음 칸 고름 머리 아래만(시안 .tr-lead 글) — 다른 묶음은 0', () => {
    show();
    const picker = screen.getByRole('group', { name: w.picker });
    const lead = within(picker).getByTestId('flow-lead');
    expect(lead.textContent).toBe(w.lead);
    expect(lead.previousElementSibling?.tagName).toBe('P');
    cleanup();
    show({ picked: { group: 1, prompt: 0 } });
    expect(screen.queryByTestId('flow-lead')).toBeNull();
  });
});
