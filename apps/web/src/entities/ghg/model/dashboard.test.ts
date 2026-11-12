// 대시보드 판 셈(밴드 DB1 ② — model/dashboard.ts). Scope 3 표시 갈래 · 덮개 조건 · Scope 몫 · 사업장 막대(합 큰 차례·사업장 안 몫) · 몫 % 꼴.
// 밴드 DB2(sid:MARC-ENT-598 — e6 ①~⑤): 눈금 최대·step · 눈금 글 · 막대 높이 · 세 해 막대 칸 · 말풍선 위끝 · 전년 대비 갈래(half-up 경계 · 숨김 조건).
import { describe, expect, it } from 'vitest';

import {
  dashboardOut,
  fakeDashboard,
  fakeScope2OnlyDashboard,
} from '../api/testing.ts';
import {
  coveredOf,
  scope3MarkOf,
  scopeSharesOf,
  scopeValuesOf,
  sharePercent,
  siteBarsOf,
  trendBarHeight,
  trendOf,
  trendScaleOf,
  trendTicksOf,
  trendTipTop,
  yearChangeOf,
} from './index.ts';
import type { Dashboard, YearBoard } from './index.ts';

const board = (value: unknown) => value as Dashboard;

describe('대시보드 model', () => {
  it('Scope 3 표시: 결과 없음 → none(빠진 시트가 있어도 — 전부 실패한 해) · 값 + n>0 → missing · 그 밖 clean', () => {
    const total = fakeDashboard(2025).total;
    expect(
      scope3MarkOf({ ...total, scope3: null, scope3FailedSheets: 0 }),
    ).toEqual({ kind: 'none' });
    expect(
      scope3MarkOf({ ...total, scope3: null, scope3FailedSheets: 3 }),
    ).toEqual({ kind: 'none' });
    expect(scope3MarkOf({ ...total, scope3FailedSheets: 2 })).toEqual({
      kind: 'missing',
      sheets: 2,
    });
    expect(scope3MarkOf(total)).toEqual({ kind: 'clean' });
  });

  it('덮개: 미설정이고 Scope 3 결과도 없을 때만', () => {
    expect(coveredOf(board(dashboardOut(2025)))).toBe(true);
    const scope3Only = dashboardOut(2025, {
      total: { ...dashboardOut(2025).total, scope3: '4', sum: '4' },
    });
    expect(coveredOf(board(scope3Only))).toBe(false);
    expect(
      coveredOf(board(fakeDashboard(2025, { scope3: null, sum: '90' }))),
    ).toBe(false);
  });

  it('Scope 셋 값·몫: 뿌리 첫째·둘째 + total.scope3 · 없는 쪽 null·0 · 음수는 그림 0', () => {
    const full = board(fakeDashboard(2025));
    expect(scopeValuesOf(full)).toEqual(['60', '30', '10']);
    expect(scopeSharesOf(full)).toEqual([0.6, 0.3, 0.1]);
    const none = board(fakeDashboard(2025, { scope3: null, sum: '90' }));
    expect(scopeValuesOf(none)[2]).toBeNull();
    expect(scopeSharesOf(none)[2]).toBe(0);
    expect(scopeSharesOf(board(dashboardOut(2025)))).toEqual([0, 0, 0]);
    const negative = board(fakeDashboard(2025, { scope3: '-5' }));
    expect(scopeSharesOf(negative)[2]).toBe(0);
  });

  it('Scope 2 만 고른 회사(검증 B1): Scope 1 자리 null · Scope 2 자리 값 · 막대 조각 order 2 — 목록 차례가 아니라 scopeOrder', () => {
    const only = board(fakeScope2OnlyDashboard(2025));
    expect(scopeValuesOf(only)).toEqual([null, '30', null]);
    expect(scopeSharesOf(only)).toEqual([0, 1, 0]);
    expect(siteBarsOf(only)[0]!.parts).toEqual([
      { scopeId: '2', order: 2, share: 1 },
    ]);
  });

  it('사업장 막대: 합이 큰 차례 · 막대 안은 그 사업장 안 몫 · 값 없는 사업장은 sum null·몫 0', () => {
    const value = fakeDashboard(2025);
    value.bySite.push({
      siteId: '3',
      siteName: '제2공장',
      scopes: [
        { scopeId: '1', value: null },
        { scopeId: '2', value: null },
      ],
      scope3: null,
    });
    const bars = siteBarsOf(board(value));
    expect(bars.map((bar) => [bar.siteId, bar.sum])).toEqual([
      ['2', 70],
      ['1', 20],
      ['3', null],
    ]);
    expect(bars[0]!.parts.map((part) => part.share)).toEqual([
      50 / 70,
      20 / 70,
    ]);
    expect(bars[1]!.parts.map((part) => part.share)).toEqual([0.5, 0.5]);
    expect(bars[2]!.parts.map((part) => part.share)).toEqual([0, 0]);
  });

  it('몫 %: 정수 반올림 · 0 보다 크고 반올림 0 → below · 0 → 0 · null·글자 아님 → null', () => {
    expect(sharePercent('54.4')).toBe(54);
    expect(sharePercent('99.5')).toBe(100);
    expect(sharePercent('0.4')).toBe('below');
    expect(sharePercent('0.0')).toBe(0);
    expect(sharePercent(null)).toBeNull();
    expect(sharePercent('abc')).toBeNull();
  });

  it('눈금 최대: 4×step ≥ M 인 가장 작은 {1,2,2.5,5}×10^k · 없음은 빼고 0 은 넣음 · 전부 0·없음 → step 1', () => {
    expect(trendScaleOf([1000, 400, 120])).toEqual({ step: 250, max: 1000 });
    expect(trendScaleOf([1001])).toEqual({ step: 500, max: 2000 });
    expect(trendScaleOf([60, 0])).toEqual({ step: 20, max: 80 });
    expect(trendScaleOf([9])).toEqual({ step: 2.5, max: 10 });
    expect(trendScaleOf([4])).toEqual({ step: 1, max: 4 });
    expect(trendScaleOf([0.9])).toEqual({ step: 0.25, max: 1 });
    expect(trendScaleOf([0.3])).toEqual({ step: 0.1, max: 0.4 });
    expect(trendScaleOf([0, 0])).toEqual({ step: 1, max: 4 });
    expect(trendScaleOf([])).toEqual({ step: 1, max: 4 });
  });

  it('눈금 글: 위에서 아래로 최대·¾·½·¼·0 · 1,000 이상 ÷1,000 + 쉼표 + K · 그 아래는 step 소수 · 0 은 「0」', () => {
    expect(trendTicksOf({ step: 250000, max: 1000000 })).toEqual([
      '1,000K',
      '750K',
      '500K',
      '250K',
      '0',
    ]);
    expect(trendTicksOf({ step: 2500, max: 10000 })).toEqual([
      '10K',
      '7.5K',
      '5K',
      '2.5K',
      '0',
    ]);
    expect(trendTicksOf({ step: 250, max: 1000 })).toEqual([
      '1K',
      '750',
      '500',
      '250',
      '0',
    ]);
    expect(trendTicksOf({ step: 0.25, max: 1 })).toEqual([
      '1',
      '0.75',
      '0.5',
      '0.25',
      '0',
    ]);
    expect(trendTicksOf({ step: 0.1, max: 0.4 })).toEqual([
      '0.4',
      '0.3',
      '0.2',
      '0.1',
      '0',
    ]);
    expect(trendTicksOf({ step: 1, max: 4 })).toEqual([
      '4',
      '3',
      '2',
      '1',
      '0',
    ]);
  });

  it('막대 높이: 값 ÷ 최대 × 160 · 0 보다 크면 최소 2 · 0·음수 → 0', () => {
    const scale = { step: 250, max: 1000 };
    expect(trendBarHeight(1000, scale)).toBe(160);
    expect(trendBarHeight(500, scale)).toBe(80);
    expect(trendBarHeight(1, scale)).toBe(2);
    expect(trendBarHeight(0, scale)).toBe(0);
    expect(trendBarHeight(-5, scale)).toBe(0);
  });

  it('말풍선 위끝: 막대 꼭대기 · 그림 안으로 누름(0 ~ 161 − 높이)', () => {
    expect(trendTipTop(160)).toBe(0);
    expect(trendTipTop(80)).toBe(80);
    expect(trendTipTop(0)).toBe(161 - 49);
  });

  const ready = (value: unknown): YearBoard => ({
    kind: 'ready',
    board: board(value),
  });

  it('세 해 막대 칸: 차례 그대로 · 아직 안 옴/없음/값 · Scope 3 은 total.scope3 · 눈금은 있는 값만 · 0 은 값(높이 0)', () => {
    const trend = trendOf(
      [
        { year: 2023, board: { kind: 'loading' } },
        { year: 2024, board: ready(fakeDashboard(2024, { scope3: '0' })) },
        { year: 2025, board: ready(fakeDashboard(2025)) },
      ],
      2,
    );
    expect(trend.bars).toEqual([
      { year: 2023, kind: 'loading' },
      { year: 2024, kind: 'value', value: '0', height: 0 },
      { year: 2025, kind: 'value', value: '10', height: 160 },
    ]);
    expect(trend.ticks).toEqual(['10', '7.5', '5', '2.5', '0']);
    const empty = trendOf(
      [
        { year: 2023, board: { kind: 'none' } },
        { year: 2024, board: ready(dashboardOut(2024)) },
        { year: 2025, board: ready(fakeDashboard(2025)) },
      ],
      0,
    );
    expect(empty.bars.map((bar) => bar.kind)).toEqual([
      'none',
      'none',
      'value',
    ]);
    expect(empty.ticks[0]).toBe('80');
  });

  const total = (sum: string, patch: Record<string, unknown> = {}) =>
    board(fakeDashboard(2025, { sum, ...patch }));
  const prior = (sum: string | null, patch: Record<string, unknown> = {}) =>
    ready(fakeDashboard(2024, { sum, ...patch }));

  it('전년 대비: 증가·감소(크기만)·같음 · 크기에 half-up 소수 한 자리 · 방향은 반올림 전 부호(감독 판단 1)', () => {
    expect(yearChangeOf(total('110'), prior('100'))).toEqual({
      kind: 'up',
      percent: '10.0',
    });
    expect(yearChangeOf(total('80'), prior('120'))).toEqual({
      kind: 'down',
      percent: '33.3',
    });
    expect(yearChangeOf(total('100'), prior('100'))).toEqual({ kind: 'same' });
    // half-up 경계: +0.25% → 0.3 · +0.35% 는 부동소수 셈이면 (100.35−100)×10 = 3.4999… 로 0.3 이 되는 자리 — 글자 셈이라 0.4
    expect(yearChangeOf(total('100.25'), prior('100'))).toEqual({
      kind: 'up',
      percent: '0.3',
    });
    expect(yearChangeOf(total('100.35'), prior('100'))).toEqual({
      kind: 'up',
      percent: '0.4',
    });
    expect(yearChangeOf(total('9995'), prior('10000'))).toEqual({
      kind: 'down',
      percent: '0.1',
    });
    expect(yearChangeOf(total('9996'), prior('10000'))).toEqual({
      kind: 'same',
    });
    expect(yearChangeOf(total('100.04'), prior('100'))).toEqual({
      kind: 'same',
    });
  });

  it('전년 대비 숨김: 앞 해 아직 안 옴·없음 · 앞 해 합 null·0 · 고른 해/앞 해 Scope 3 결과 없음·시트 빠짐 · Scope 1·2 합 없음(판단 11)', () => {
    const hidden = { kind: 'hidden' };
    expect(yearChangeOf(total('100'), { kind: 'loading' })).toEqual(hidden);
    expect(yearChangeOf(total('100'), { kind: 'none' })).toEqual(hidden);
    expect(yearChangeOf(total('100'), prior(null))).toEqual(hidden);
    expect(yearChangeOf(total('100'), prior('0'))).toEqual(hidden);
    expect(yearChangeOf(total('100', { scope3: null }), prior('100'))).toEqual(
      hidden,
    );
    expect(yearChangeOf(total('100'), prior('100', { scope3: null }))).toEqual(
      hidden,
    );
    expect(
      yearChangeOf(total('100', { scope3FailedSheets: 1 }), prior('100')),
    ).toEqual(hidden);
    expect(
      yearChangeOf(total('100'), prior('100', { scope3FailedSheets: 2 })),
    ).toEqual(hidden);
    expect(yearChangeOf(total('100', { scope12: null }), prior('100'))).toEqual(
      hidden,
    );
    expect(yearChangeOf(total('100'), prior('100', { scope12: null }))).toEqual(
      hidden,
    );
    expect(yearChangeOf(total('100'), ready(dashboardOut(2024)))).toEqual(
      hidden,
    );
  });
});
