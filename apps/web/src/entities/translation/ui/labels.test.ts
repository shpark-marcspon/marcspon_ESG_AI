// 파트 상태 → 글(밴드 TRW0b, 발주서 §3-1·3-6): 화면 제목 세 갈래 글 · 남은 파트 줄 · 상태 한 덩이(목록 꼬리 — 디자인 e9) · 막은 까닭 글.
import { describe, expect, it } from 'vitest';

import { REJECTION_KEYS } from '../model/index.ts';
import { AT_1150, AT_1155, AT_1205, AT_1422 } from '../model/testing.ts';
import {
  partStatusLabel,
  rejectionText,
  remainingLine,
  screenTitle,
  summaryItems,
  tabLabel,
} from './labels.ts';

describe('labels', () => {
  it('화면 제목 세 갈래(판 글 그대로)', () => {
    expect(screenTitle(AT_1155)).toBe('번역 중이에요');
    expect(screenTitle(AT_1422)).toBe('번역이 끝났어요');
    expect(screenTitle(AT_1205)).toBe(
      '번역이 끝났어요 · 한 파트는 다시 해야 해요',
    );
  });

  it('「3파트 중 1파트 완료 · 2파트 진행 중」', () => {
    expect(remainingLine(AT_1155)).toBe('3파트 중 1파트 완료 · 2파트 진행 중');
    expect(remainingLine(AT_1150)).toBe('3파트 중 2파트 진행 중 · 1파트 대기');
  });

  it('묶음 셈 글: 「완료 2」·「실패 1」', () => {
    expect(summaryItems(AT_1205)).toEqual([
      { state: 'done', text: '완료 2' },
      { state: 'failed', text: '실패 1' },
    ]);
  });

  it('탭 상태 글', () => {
    expect(tabLabel('done')).toBe('완료');
    expect(tabLabel('failed_partial')).toBe('실패 · 일부 페이지');
    expect(tabLabel('queued')).toBe('대기');
  });

  it('상태 한 덩이: 진행 페이지·준비 · 목록 꼬리(분량 많음도 그 밖도 「실패」 — 밴드 TRW15, CEO 한도도 일반 실패) · 일부 페이지', () => {
    expect(partStatusLabel('running', undefined, { done: 20, total: 38 })).toBe(
      '진행 중 · 번역 20/38페이지',
    );
    expect(partStatusLabel('running')).toBe('진행 중 · 준비');
    // 밴드 TRW4: 「실패 · CEO 6페이지 넘음」은 뺐다 — 입력 화면이 막고, 서버가 그래도 거절하면 일반 실패.
    expect(partStatusLabel('failed', 'ceo_over_limit')).toBe('실패');
    expect(partStatusLabel('failed', 'too_large')).toBe('실패');
    expect(partStatusLabel('failed', 'over_budget')).toBe('실패');
    expect(partStatusLabel('failed', 'no_pages')).toBe('실패');
    expect(partStatusLabel('failed', 'bad_file')).toBe('실패');
    expect(partStatusLabel('failed')).toBe('실패');
    expect(partStatusLabel('failed_partial')).toBe('실패 · 일부 페이지');
    expect(partStatusLabel('done')).toBe('완료');
  });

  it('막은 까닭 다섯: 분량 둘은 같은 글, 그 밖(CEO 한도 포함 — 밴드 TRW4)은 일반 실패 글', () => {
    const joined = (key: (typeof REJECTION_KEYS)[number]) => {
      const { reason, guide } = rejectionText(key);
      return `${reason} ${guide}`;
    };
    expect(joined('too_large')).toBe(
      '분량이 많아 시작하지 않았어요. 페이지 범위를 줄여 새로 번역해 주세요.',
    );
    expect(joined('over_budget')).toBe(joined('too_large'));
    expect(joined('no_pages')).toBe(
      '이 파트를 시작하지 않았어요. 새 번역에서 페이지 범위와 파일을 확인해 주세요.',
    );
    expect(joined('bad_file')).toBe(joined('no_pages'));
    expect(joined('ceo_over_limit')).toBe(joined('no_pages'));
    expect(joined('ceo_over_limit')).not.toMatch(/CEO|넘음/);
    for (const key of REJECTION_KEYS) expect(joined(key)).not.toMatch(/비용/);
  });
});
