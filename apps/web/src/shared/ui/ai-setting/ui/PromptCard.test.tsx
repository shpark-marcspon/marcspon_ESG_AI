// @vitest-environment jsdom
// AI 설정 단계 카드(시안 v148 — GW3R A9·A12·B10~B15): 둘레 상자 0 · 라벨 칸 셋 · 이름 16/700 · KEY 알약 대문자 · 글 칸 12 ·
// ⚠ 출력절 띠(글 칸 위 · 머리 글 + outputNote, role 없음 — 디자인 74 · IRW8) · 메모 두 줄 글 칸.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PromptCard } from './PromptCard.tsx';
import type { PromptCardProps } from './PromptCard.tsx';

afterEach(cleanup);

const PROPS: PromptCardProps = {
  title: '지어낸 단계',
  tag: 'detect',
  edited: null,
  readOnly: false,
  stepLabel: '단계',
  textLabel: '프롬프트',
  text: '지어낸 글',
  textCount: '5 / 8000자',
  textError: null,
  outputNote: '지어낸 출력절 안내',
  outputLost: null,
  untouched: null,
  memoLabel: '메모',
  memo: '지어낸 메모',
  memoCount: '6 / 500자',
  memoError: null,
  memoNote: '지어낸 메모 안내',
};

function setup() {
  render(<PromptCard {...PROPS} />);
  return screen.getByRole('region', { name: '지어낸 단계' });
}

const words = (element: Element) => element.className.split(/\s+/);

/** 출력절 띠(testid 몸 줄 → 두 줄 묶음 → 띠). */
const band = () =>
  screen.getByTestId('output-note').parentElement!.parentElement!;

describe('PromptCard 꼴', () => {
  it('둘레 상자 0 · 라벨 칸 셋(단계·프롬프트·메모)', () => {
    const card = setup();
    expect(card.getAttribute('data-card')).toBe('prompt-slot');
    expect(words(card)).not.toContain('border');
    expect(words(card)).not.toContain('rounded-component');
    const labels = [...card.querySelectorAll('span.w-40')];
    expect(labels.map((node) => node.textContent)).toEqual([
      '단계',
      '프롬프트',
      '메모',
    ]);
    for (const label of labels)
      expect(words(label)).toEqual(
        expect.arrayContaining([
          'bg-support-grey-subtle',
          'text-style-pre-body-05',
          'text-text-tertiary',
        ]),
      );
  });

  it('이름 h4 pre-body-01 · KEY 알약(대문자·바탕·모서리 4), 글자는 그대로', () => {
    const card = setup();
    expect(words(card.querySelector('h4')!)).toContain(
      'text-style-pre-body-01',
    );
    const key = screen.getByTestId('slot-key');
    expect(key.textContent).toBe('detect');
    expect(words(key)).toEqual(
      expect.arrayContaining([
        'uppercase',
        'bg-background-secondary',
        'rounded-control',
      ]),
    );
  });

  it('lowerKey 면 KEY 알약 uppercase 0(글자 그대로) — 밴드 TRA2 D10', () => {
    render(<PromptCard {...PROPS} lowerKey />);
    const key = screen.getByTestId('slot-key');
    expect(key.textContent).toBe('detect');
    expect(words(key)).not.toContain('uppercase');
  });

  it('note(밴드 DVA2 K1): 없거나 null → 안내 줄 0 · 있으면 글 칸 아래 한 줄(role 없음, 흐린 글)', () => {
    setup();
    expect(screen.queryByTestId('prompt-note')).toBeNull();
    cleanup();
    render(<PromptCard {...PROPS} note={null} />);
    expect(screen.queryByTestId('prompt-note')).toBeNull();
    cleanup();
    render(<PromptCard {...PROPS} note="지어낸 자리 안내" />);
    const notes = screen.getAllByTestId('prompt-note');
    expect(notes).toHaveLength(1);
    expect(notes[0]!.textContent).toBe('지어낸 자리 안내');
    expect(notes[0]!.getAttribute('role')).toBeNull();
    expect(words(notes[0]!)).toContain('text-text-tertiary');
  });

  it('outputNote null → 노란 안내 상자 0 — 밴드 TRA2 D4', () => {
    render(<PromptCard {...PROPS} outputNote={null} />);
    expect(screen.queryByTestId('output-note')).toBeNull();
    expect(
      screen.getByRole('textbox', { name: '지어낸 단계 프롬프트' }),
    ).toBeTruthy();
  });

  it('글 칸 12px 16px · ⚠ 출력절 띠(role 없음, svg 하나, 몸 줄 글 = outputNote)', () => {
    setup();
    const text = screen.getByRole('textbox', { name: '지어낸 단계 프롬프트' });
    expect(words(text)).toEqual(
      expect.arrayContaining(['px-4', 'py-3', 'font-body']),
    );
    expect(words(band())).toEqual(
      expect.arrayContaining([
        'bg-support-warning-subtle',
        'rounded-component',
        'px-4',
        'py-3',
      ]),
    );
    const note = screen.getByTestId('output-note');
    expect(words(note)).toEqual(
      expect.arrayContaining(['text-style-pre-med-04', 'text-text-secondary']),
    );
    expect(band().getAttribute('role')).toBeNull();
    expect(band().querySelectorAll('svg')).toHaveLength(1);
    expect(note.textContent).toBe('지어낸 출력절 안내');
  });

  it('N1 머리 글 「출력 형식 절은 고치지 마세요」 — 띠 안에 하나(pre-body-05 · primary)', () => {
    setup();
    const heads = screen.getAllByText('출력 형식 절은 고치지 마세요');
    expect(heads).toHaveLength(1);
    expect(band().contains(heads[0]!)).toBe(true);
    expect(words(heads[0]!)).toEqual(
      expect.arrayContaining(['text-style-pre-body-05', 'text-text-primary']),
    );
  });

  it('N2 띠는 칸 이름 줄 다음 · 글 칸 textarea 앞(DOM 차례)', () => {
    setup();
    const text = screen.getByRole('textbox', { name: '지어낸 단계 프롬프트' });
    const label = screen.getByText('프롬프트', { selector: 'span' });
    expect(
      band().compareDocumentPosition(text) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      label.compareDocumentPosition(band()) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('N3 outputNote null → 글 칸 줄 값 칸 자식이 BASE 와 같음(textarea · 줄 묶음 둘, 띠·머리 글 0)', () => {
    render(<PromptCard {...PROPS} outputNote={null} />);
    const text = screen.getByRole('textbox', { name: '지어낸 단계 프롬프트' });
    const kids = [...text.parentElement!.children];
    expect(kids).toHaveLength(2);
    expect(kids[0]).toBe(text);
    expect(kids[1]!.querySelector('[data-testid="text-count"]')).toBeTruthy();
    expect(screen.queryByText('출력 형식 절은 고치지 마세요')).toBeNull();
  });

  it('메모는 두 줄 글 칸(최소 64 · 좌우 16)', () => {
    setup();
    const memo = screen.getByRole('textbox', { name: '지어낸 단계 메모' });
    expect(memo.tagName).toBe('TEXTAREA');
    expect(memo.getAttribute('rows')).toBe('2');
    expect(words(memo)).toEqual(expect.arrayContaining(['min-h-16', 'px-4']));
    expect(words(memo)).not.toContain('min-h-20');
  });
});

// 밴드 LK2 §7 B14: ⚠ 출력절 안내 아이콘 색 support-warning-accent.
describe('PromptCard ⚠ 아이콘 색(LK2 B14)', () => {
  it('출력절 안내 상자의 아이콘은 text-support-warning-accent', () => {
    setup();
    const icon = band().querySelector('svg')!;
    expect(icon.getAttribute('class')!.split(/\s+/)).toEqual(
      expect.arrayContaining(['text-support-warning-accent', 'size-5']),
    );
    expect(icon.getAttribute('class')).not.toContain('text-support-orange');
  });
});

// 밴드 PF1(T2): flow 를 주면 단계 줄 묶음 바로 앞(같은 부모)에 그린다, 안 주면 없음.
describe('PromptCard 처리 흐름 자리(PF1)', () => {
  it('flow 있음 → 줄 묶음 바로 앞 형제 · 없음 → 앞 형제 0', () => {
    render(
      <div data-testid="outer">
        <PromptCard {...PROPS} flow={<p data-testid="flow">지어낸 흐름</p>} />
      </div>,
    );
    const card = screen.getByRole('region', { name: '지어낸 단계' });
    const flow = screen.getByTestId('flow');
    expect(flow.parentElement).toBe(screen.getByTestId('outer'));
    expect(card.previousElementSibling).toBe(flow);
    expect(card.contains(flow)).toBe(false);
    cleanup();
    const plain = setup();
    expect(plain.previousElementSibling).toBeNull();
    expect(screen.queryByTestId('flow')).toBeNull();
  });
});
