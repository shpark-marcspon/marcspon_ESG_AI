// @vitest-environment jsdom
// 용어집 미반영 표 · 확인할 쪽 · 단계 줄 · 안내 줄(밴드 TRW0b, 발주서 §3-11): 줄 수 · 빈 꼴 · tone.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  SAMPLE_MISSES,
  SAMPLE_PAGES_TO_CHECK,
} from '../../../entities/translation/model/testing.ts';
import type { StatusLook } from '../../../entities/translation/ui/index.ts';
import { GlossaryMissTable } from './GlossaryMissTable.tsx';
import { PagesToCheck, ResultNotices, StepLine } from './PagesToCheck.tsx';

afterEach(cleanup);

// 번역·검수 칸은 배지 글과 변형(밴드 TRP2 TC2). 고정물 글에 시안 TR-04a 의 변형을 붙인다.
const LOOK_OF: Record<string, StatusLook> = {
  실패: 'orange',
  완료: 'success',
  검수함: 'success',
  '30페이지에서 멈춤': 'error',
  '돌리지 않음': 'grey',
};
const CHECK_ROWS = SAMPLE_PAGES_TO_CHECK.map((row) => ({
  ...row,
  translate: { text: row.translate, look: LOOK_OF[row.translate]! },
  review: { text: row.review, look: LOOK_OF[row.review]! },
}));

describe('GlossaryMissTable', () => {
  it('줄 수 = rows, 등장 「2회」, 빈 꼴이면 「모두 지켰어요」 글', () => {
    const { rerender } = render(<GlossaryMissTable rows={SAMPLE_MISSES} />);
    const rows = document.querySelectorAll('[data-row="miss"]');
    expect(rows).toHaveLength(2);
    // data-row 는 쪽 칸 글에 있다(밴드 TRP2 TC3). 줄 글은 그 위 tr.
    expect(rows[0]!.closest('tr')!.textContent).toBe(
      '9안전보건 관리Health and Safety Management2회',
    );
    expect(screen.queryByTestId('glossary-miss-empty')).toBeNull();
    rerender(<GlossaryMissTable rows={[]} />);
    expect(screen.getByTestId('glossary-miss-empty').textContent).toBe(
      TR_TEXT.glossaryMiss.empty,
    );
    expect(document.querySelectorAll('[data-row="miss"]')).toHaveLength(0);
  });
});

describe('PagesToCheck · StepLine · ResultNotices', () => {
  it('확인할 쪽: 줄 수, 없으면 그리지 않음', () => {
    const { rerender } = render(<PagesToCheck rows={CHECK_ROWS} />);
    expect(document.querySelectorAll('[data-row="check"]')).toHaveLength(3);
    rerender(<PagesToCheck rows={[]} />);
    expect(screen.queryByTestId('pages-to-check')).toBeNull();
  });

  it('시험 표본(확인할 페이지)도 단위는 「페이지」 — 「\\d쪽」·「앞 쪽」 0(밴드 TRW5)', () => {
    for (const row of SAMPLE_PAGES_TO_CHECK)
      for (const text of Object.values(row)) {
        expect(text).not.toMatch(/\d쪽|앞 쪽/);
      }
    expect(SAMPLE_PAGES_TO_CHECK.map((row) => row.review)).toContain(
      '30페이지에서 멈춤',
    );
  });

  it('단계 줄: 「단계」 + 단계마다 이름·글', () => {
    render(
      <StepLine
        steps={[
          { name: '번역', text: '2쪽 실패', look: 'orange' },
          { name: '용어집 반영 검사', text: '완료', look: 'success' },
        ]}
      />,
    );
    expect(screen.getByTestId('step-line').textContent).toBe(
      '단계번역 2쪽 실패·용어집 반영 검사 완료',
    );
  });

  it('안내 줄(TRP2 TC24): 검수 멈춤 error · 번역 못 한 쪽 important, 없으면 그리지 않음', () => {
    const { rerender } = render(
      <ResultNotices
        notices={[
          { tone: 'error', text: '검수가 30쪽에서 멈췄어요.' },
          { tone: 'important', text: '번역하지 못한 쪽이 2곳 있어요.' },
        ]}
      />,
    );
    const tones = [...document.querySelectorAll('[data-tone]')].map((n) =>
      n.getAttribute('data-tone'),
    );
    expect(tones).toEqual(['error', 'important']);
    rerender(<ResultNotices notices={[]} />);
    expect(screen.queryByTestId('result-notices')).toBeNull();
  });
});

// 밴드 TRP4 ②-10: TR-04a 안내 상자에 gw-m-rise.
describe('ResultNotices 움직임(TRP4)', () => {
  it('result-notices 에 gw-m-rise', () => {
    render(
      <ResultNotices
        notices={[
          { tone: 'important', text: '번역하지 못한 쪽이 1곳 있어요.' },
        ]}
      />,
    );
    expect(
      screen.getByTestId('result-notices').classList.contains('gw-m-rise'),
    ).toBe(true);
  });
});
