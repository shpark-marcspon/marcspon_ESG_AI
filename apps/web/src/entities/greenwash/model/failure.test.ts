// 밴드 GW2R ②(발주서 §3 A): 실패 갈래·[다시 실행] 여부(errorCode 하나로), 자동 저장 시각 꾸밈(한국 시각), 인식 실패 페이지 차례.
// (GW-03·04 글 꼴은 ui/text-fixes.test.tsx — model 은 config 를 가져오지 않는다.)
import { describe, expect, it } from 'vitest';

import { formatKstTime } from '../../../shared/lib/time.ts';
import { canRerun, failureKind } from './failure.ts';
import { failedPagesOf } from './result.ts';
import type { GreenwashResult } from './result.ts';

describe('failureKind · canRerun', () => {
  it.each([
    ['no_text_layer', 'no_text', false],
    ['setup_error', 'setup', false],
    ['step_error', 'general', true],
    ['attempts_exhausted', 'general', true],
    ['지어낸 모르는 code', 'general', true],
    [null, 'general', true],
    [undefined, 'general', true],
  ] as const)('%s → %s, [다시 실행] %s', (code, kind, rerun) => {
    expect(failureKind(code)).toBe(kind);
    expect(canRerun(code)).toBe(rerun);
  });
});

describe('formatKstTime: 「HH:MM」(한국 시각)', () => {
  it.each([
    ['2026-10-15T05:31:09.000Z', '14:31'],
    ['2026-10-15T14:31:59+09:00', '14:31'],
    ['2026-10-15T23:05:00+09:00', '23:05'],
    ['2026-10-15T15:05:00Z', '00:05'],
    ['읽을 수 없음', '읽을 수 없음'],
  ])('%s → %s', (iso, shown) => {
    expect(formatKstTime(iso)).toBe(shown);
  });
});

describe('failedPagesOf: 결과의 인식 실패 페이지(오름차순, 겹침 없음)', () => {
  const withPages = (pages: number[] | null) =>
    ({
      candidateStats:
        pages === null ? null : (
          { failedPages: pages.map((page) => ({ page, error: 'x' })) }
        ),
    }) as unknown as GreenwashResult;
  it('70·31·58·31 → 31·58·70, 비면 빈 목록, dry-run(null) 빈 목록', () => {
    expect(failedPagesOf(withPages([70, 31, 58, 31]))).toEqual([31, 58, 70]);
    expect(failedPagesOf(withPages([]))).toEqual([]);
    expect(failedPagesOf(withPages(null))).toEqual([]);
  });
});
