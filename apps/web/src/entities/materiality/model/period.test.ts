// 리서치 기간(밴드 IRW1 ① — 발주서 §3-1-7, ★D).
import { describe, expect, it } from 'vitest';

import { kstDay, periodOf, runDay } from './period.ts';

describe('periodOf', () => {
  it('「시작~끝」·「시작~오늘까지」(그날)·공백 · 못 읽으면 원문', () => {
    expect(periodOf('2024-01-01~2024-12-31', '2026-10-19')).toEqual({
      kind: 'range',
      start: '2024-01-01',
      end: '2024-12-31',
    });
    expect(periodOf(' 2025-01-01 ~ 오늘까지 ', '2026-10-19')).toEqual({
      kind: 'range',
      start: '2025-01-01',
      end: '2026-10-19',
    });
    expect(periodOf('2025-01-01~오늘까지', null)).toEqual({
      kind: 'raw',
      text: '2025-01-01~오늘까지',
    });
    expect(periodOf('작년부터', '2026-10-19')).toEqual({
      kind: 'raw',
      text: '작년부터',
    });
  });

  it('「오늘까지」의 날은 startedAt(없으면 createdAt)의 한국 날짜', () => {
    expect(kstDay('2026-10-19T15:30:00Z')).toBe('2026-10-20');
    expect(kstDay('x')).toBeNull();
    expect(
      runDay({
        startedAt: '2026-10-19T23:59:00+09:00',
        createdAt: '2026-10-18T10:00:00+09:00',
      }),
    ).toBe('2026-10-19');
    expect(
      runDay({ startedAt: null, createdAt: '2026-10-18T10:00:00+09:00' }),
    ).toBe('2026-10-18');
  });
});
