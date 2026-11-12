// @vitest-environment jsdom
// 대상 단어 카드(밴드 AS3b ① — 발주서 §3-3): 추가(끝·「추가」 꼬리표·Enter) · 고르기 → [삭제] · 전체 고르기 · 스위치 · 입력 오류 글 · 아래 줄(D2)
//   · 켠 것 0 글(D4 — 카드 밖 아래) · readOnly 면 입력·단추·스위치 꺼짐 · 서버가 짚은 줄 빨강. 낱말은 지어낸 것이다.
import { useState } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { GREENWASH_SETTING_TEXT } from '../config/text.ts';
import type { TermsDraft } from '../model/index.ts';
import { TermsCard } from './TermsCard.tsx';

afterEach(cleanup);

const t = GREENWASH_SETTING_TEXT.terms;

const BASE: TermsDraft = [
  { text: '지어낸 초록', enabled: true },
  { text: '지어낸 푸름', enabled: true },
  { text: '지어낸 숲', enabled: false },
];

function Harness({
  base = BASE,
  readOnly = false,
  refused = {},
  onChange = () => {},
}: {
  base?: TermsDraft;
  readOnly?: boolean;
  refused?: Readonly<Record<string, readonly string[]>>;
  onChange?(next: TermsDraft): void;
}) {
  const [draft, setDraft] = useState(base);
  return (
    <TermsCard
      base={base}
      draft={draft}
      readOnly={readOnly}
      refused={refused}
      words={t}
      onChange={(next) => {
        setDraft(next);
        onChange(next);
      }}
    />
  );
}

const words = () =>
  [...document.querySelectorAll('tbody tr')].map((row) =>
    row.getAttribute('data-term'),
  );
const input = () => screen.getByRole('textbox', { name: t.input });
const button = (name: string) => screen.getByRole('button', { name });
const foot = () => screen.getByTestId('terms-foot').textContent;

describe('대상 단어 카드', () => {
  it('처음: 줄 셋·스위치 사용 그대로·아래 줄 「3개 · 사용 2개」·고침 꼬리표 0·「추가」 꼬리표 0', () => {
    render(<Harness />);
    expect(words()).toEqual(['지어낸 초록', '지어낸 푸름', '지어낸 숲']);
    expect(
      screen
        .getAllByRole('switch')
        .map((one) => one.getAttribute('aria-checked')),
    ).toEqual(['true', 'true', 'false']);
    expect(foot()).toBe('3개 · 사용 2개');
    expect(screen.queryByTestId('terms-edited')).toBeNull();
    expect(screen.queryByTestId('terms-added-tag')).toBeNull();
    expect(screen.queryByTestId('terms-none-enabled')).toBeNull();
    expect(input().getAttribute('placeholder')).toBe(t.placeholder);
  });

  it('[추가]·Enter: 끝에 더함(trim)·주황 줄 + 「추가」 꼬리표·고침 꼬리표·아래 줄 「새로 더한 n개는 저장 전이에요」, 입력 칸 비움', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.change(input(), { target: { value: '  지어낸 새말  ' } });
    fireEvent.click(button(t.add));
    fireEvent.change(input(), { target: { value: '지어낸 둘째말' } });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(words()).toEqual([
      '지어낸 초록',
      '지어낸 푸름',
      '지어낸 숲',
      '지어낸 새말',
      '지어낸 둘째말',
    ]);
    expect(onChange).toHaveBeenCalledTimes(2);
    const added = document.querySelector('tr[data-term="지어낸 새말"]')!;
    expect(added.hasAttribute('data-added')).toBe(true);
    expect(
      within(added as HTMLElement).getByTestId('terms-added-tag').textContent,
    ).toBe(t.addedTag);
    expect(screen.getByTestId('terms-edited').textContent).toBe(t.edited(2));
    expect(foot()).toBe('5개 · 사용 4개 · 새로 더한 2개는 저장 전이에요');
    expect((input() as HTMLInputElement).value).toBe('');
  });

  it('입력 오류: 칸 아래 빨강 한 줄(D1 넷), 추가 0 — 고쳐 쓰면 걷힘', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const cases: [string, string][] = [
      ['', t.problem.length],
      ['가'.repeat(31), t.problem.length],
      ['지어(낸', t.problem.chars],
      ['지어낸-초록', t.problem.duplicate],
    ];
    for (const [value, line] of cases) {
      fireEvent.change(input(), { target: { value } });
      fireEvent.keyDown(input(), { key: 'Enter' });
      expect(screen.getByTestId('terms-problem').textContent, value).toBe(line);
      expect(input().getAttribute('aria-invalid')).toBe('true');
      // 오류 줄이 칸의 설명으로 이어진다(이슈 329 L2)
      expect(input().getAttribute('aria-describedby')).toBe(
        screen.getByTestId('terms-problem').id,
      );
    }
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(input(), { target: { value: '지어낸' } });
    expect(screen.queryByTestId('terms-problem')).toBeNull();
    expect(input().hasAttribute('aria-describedby')).toBe(false);
  });

  it('100개면 「100개까지」 글', () => {
    const full: TermsDraft = Array.from({ length: 100 }, (_, index) => ({
      text: `지어낸말${index}`,
      enabled: true,
    }));
    render(<Harness base={full} />);
    fireEvent.change(input(), { target: { value: '지어낸 백하나' } });
    fireEvent.click(button(t.add));
    expect(screen.getByTestId('terms-problem').textContent).toBe(
      t.problem.count,
    );
  });

  it('고르기 → [삭제]: 고른 줄만 지움·고름 비움, 고른 것 없으면 [삭제] 꺼짐 · 전체 고르기', () => {
    render(<Harness />);
    expect(button(t.remove).hasAttribute('disabled')).toBe(true);
    fireEvent.click(
      screen.getByRole('checkbox', { name: t.pick('지어낸 푸름') }),
    );
    expect(button(t.remove).hasAttribute('disabled')).toBe(false);
    fireEvent.click(button(t.remove));
    expect(words()).toEqual(['지어낸 초록', '지어낸 숲']);
    expect(screen.getByTestId('terms-edited').textContent).toBe(t.edited(1));
    expect(button(t.remove).hasAttribute('disabled')).toBe(true);
    const all = screen.getByRole('checkbox', { name: t.selectAll });
    fireEvent.click(all);
    expect(all.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(button(t.remove));
    expect(words()).toEqual([]);
  });

  it('스위치: 사용 바꿈 · 켠 것 0 이면 카드 밖 아래 글(D4)', () => {
    render(<Harness />);
    fireEvent.click(
      screen.getByRole('switch', { name: t.switchLabel('지어낸 숲') }),
    );
    expect(foot()).toBe('3개 · 사용 3개');
    expect(screen.getByTestId('terms-edited').textContent).toBe(t.edited(1));
    for (const word of ['지어낸 초록', '지어낸 푸름', '지어낸 숲'])
      fireEvent.click(
        screen.getByRole('switch', { name: t.switchLabel(word) }),
      );
    expect(foot()).toBe('3개 · 사용 0개');
    const none = screen.getByTestId('terms-none-enabled');
    expect(none.textContent).toBe(t.noneEnabled);
    expect(screen.getByTestId('terms-card').contains(none)).toBe(false);
  });

  it('readOnly: 입력·[추가]·[삭제]·고르기·스위치 다 꺼짐, Enter 도 추가 0', () => {
    const onChange = vi.fn();
    render(<Harness readOnly onChange={onChange} />);
    expect((input() as HTMLInputElement).disabled).toBe(true);
    expect(button(t.add).hasAttribute('disabled')).toBe(true);
    expect(button(t.remove).hasAttribute('disabled')).toBe(true);
    for (const one of [
      ...screen.getAllByRole('switch'),
      ...screen.getAllByRole('checkbox'),
    ])
      expect(one.hasAttribute('disabled')).toBe(true);
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('서버가 짚은 자리: terms.<i>.text → 그 줄 빨강 + 글, terms → 카드 안 아래 글', () => {
    render(
      <Harness
        refused={{
          'terms.1.text': [t.refused.TERMS_DUPLICATE],
          terms: [t.refused.TERMS_COUNT],
        }}
      />,
    );
    const row = document.querySelector('tr[data-term="지어낸 푸름"]')!;
    expect(row.hasAttribute('data-refused')).toBe(true);
    expect(
      within(row as HTMLElement).getByTestId('terms-row-refused').textContent,
    ).toBe(t.refused.TERMS_DUPLICATE);
    expect(document.querySelectorAll('tr[data-refused]')).toHaveLength(1);
    expect(screen.getByTestId('terms-refused').textContent).toBe(
      t.refused.TERMS_COUNT,
    );
  });

  it('판을 바꾸면(base 가 바뀜) 고름·입력 글·오류를 비운다', () => {
    const props = {
      readOnly: false,
      refused: {},
      words: t,
      onChange: () => {},
    };
    const other: TermsDraft = [{ text: '지어낸 다른 판 말', enabled: true }];
    const view = render(<TermsCard base={BASE} draft={BASE} {...props} />);
    fireEvent.click(
      screen.getByRole('checkbox', { name: t.pick('지어낸 초록') }),
    );
    fireEvent.change(input(), { target: { value: '지어(낸' } });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(screen.getByTestId('terms-problem')).toBeTruthy();
    view.rerender(<TermsCard base={other} draft={other} {...props} />);
    expect((input() as HTMLInputElement).value).toBe('');
    expect(screen.queryByTestId('terms-problem')).toBeNull();
    view.rerender(<TermsCard base={BASE} draft={BASE} {...props} />);
    expect(
      screen
        .getByRole('checkbox', { name: t.pick('지어낸 초록') })
        .getAttribute('aria-checked'),
    ).toBe('false');
  });
});
