// 온실가스 움직임 지연 셈(밴드 DB3 — sid:MARC-TICK-538). 값: band-handoffs/DB3-motion-values.md(e6) ①·②·③ + 발주서 감독 판단 2·3·5.
//   자리마다 값 문서의 지연 · 지연 상한 400 · 「지연 + 길이」 ≤ 한 화면 상한 1,000(몇 번째 줄·장이든).
import { describe, expect, it } from 'vitest';

import {
  MOTION_DELAY_CAP,
  MOTION_MS,
  MOTION_SCREEN_CAP,
  cardRiseDelay,
  donutSweepDelay,
  siteGrowDelay,
  sourceGrowDelay,
  trendBarDelay,
} from './index.ts';

const upTo = (count: number) => Array.from({ length: count }, (_, at) => at);

describe('온실가스 움직임 지연', () => {
  it('카드 줄(감독 판단 2): 총 0 · Scope 1·2·3 = 40·80·120 · 사업장별 160 · 배출원별 160', () => {
    expect(upTo(6).map(cardRiseDelay)).toEqual([0, 40, 80, 120, 160, 160]);
  });

  it('도넛 120 · 3개년 막대 120·200·280 · 배출원별 막대 120·160·200', () => {
    expect(donutSweepDelay()).toBe(120);
    expect(upTo(3).map(trendBarDelay)).toEqual([120, 200, 280]);
    expect(upTo(3).map(sourceGrowDelay)).toEqual([120, 160, 200]);
  });

  it('사업장별 줄(감독 판단 3): 120 + 줄마다 40 · 「한 화면 상한 − 길이」 = 300 에서 멈춤', () => {
    expect(upTo(8).map(siteGrowDelay)).toEqual([
      120, 160, 200, 240, 280, 300, 300, 300,
    ]);
  });

  // 지연 상한 400 은 줄·장 차례 지연의 상한(e6 ①). 고른 해 말풍선 지연(감독 판단 5)은 밴드 DB4 에서 없앴다(올림·초점 때만, 지연 0).
  it('어느 자리든 지연 + 길이 ≤ 1,000(16번째 줄 넘어도 — Scope 3 카드는 ResultView.test) · 지연 ≤ 400', () => {
    const places: [string, (at: number) => number, number, number][] = [
      ['카드 줄', cardRiseDelay, MOTION_MS.rise, 6],
      ['도넛', donutSweepDelay, MOTION_MS.draw, 1],
      ['3개년 막대', trendBarDelay, MOTION_MS.draw, 3],
      ['사업장별 줄', siteGrowDelay, MOTION_MS.draw, 40],
      ['배출원별 칸', sourceGrowDelay, MOTION_MS.draw, 3],
    ];
    for (const [name, delayOf, duration, count] of places)
      for (const at of upTo(count)) {
        const delay = delayOf(at);
        expect([name, at, delay <= MOTION_DELAY_CAP]).toEqual([name, at, true]);
        expect([name, at, delay + duration <= MOTION_SCREEN_CAP]).toEqual([
          name,
          at,
          true,
        ]);
      }
  });
});
