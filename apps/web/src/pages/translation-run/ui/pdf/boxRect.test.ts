// layout 상자 → 화면 자리(밴드 TRW6 ③ — 검증 권고 R10): 왼쪽 위 원점 · 배율 곱 · 쪽 크기 0 이면 그리지 않음.
import { describe, expect, it } from 'vitest';

import {
  WIDEN_SLACK,
  fitScale,
  pageBoxOf,
  screenRectOf,
  settleWidth,
} from './boxRect.ts';

describe('screenRectOf', () => {
  it('왼쪽 위 원점 · 포인트 × 배율(쪽 크기 비율 그대로)', () => {
    const page = { width: 600, height: 800 };
    expect(screenRectOf([60, 80, 300, 100], page, 1)).toEqual({
      left: 60,
      top: 80,
      width: 240,
      height: 20,
    });
    // 배율 1.5 — 쪽 너비에 대한 비율(60/600 = 10%)이 그려진 쪽(900)에서도 같다.
    const rect = screenRectOf([60, 80, 300, 100], page, 1.5)!;
    expect(rect.left / pageBoxOf(page, 1.5)!.width).toBeCloseTo(0.1);
    expect(rect.top / pageBoxOf(page, 1.5)!.height).toBeCloseTo(0.1);
  });

  it('쪽 크기를 못 찾으면(0) 상자·쪽 칸 null — 0 나눔 없음', () => {
    expect(screenRectOf([1, 2, 3, 4], { width: 0, height: 0 }, 1)).toBeNull();
    expect(screenRectOf([1, 2, 3, 4], { width: 600, height: 0 }, 1)).toBeNull();
    expect(pageBoxOf({ width: 0, height: 842 }, 1)).toBeNull();
  });
});

// 밴드 TRW6 ⑤(6c B1): 칸이 쪽보다 좁으면 칸 폭 ÷ 쪽 폭(0.01 내림), 넓으면 위끝 그대로, 모르면 위끝.
describe('fitScale', () => {
  it('좁은 칸 → 칸 폭 ÷ 쪽 폭(0.01 내림) · 그 배율의 쪽 폭은 칸 안', () => {
    const scale = fitScale(468, 595, 1);
    expect(scale).toBe(0.78);
    expect(
      pageBoxOf({ width: 595, height: 842 }, scale)!.width,
    ).toBeLessThanOrEqual(468);
  });
  it('넓은 칸 → 위끝 그대로(키우지 않음)', () => {
    expect(fitScale(900, 595, 1)).toBe(1);
  });
  it('칸 폭·쪽 폭을 모르면(0) 위끝', () => {
    expect(fitScale(0, 595, 1)).toBe(1);
    expect(fitScale(468, 0, 1)).toBe(1);
  });
  it('상자도 같은 배율로 준다(R10 셈 그대로)', () => {
    const scale = fitScale(300, 600, 1);
    expect(
      screenRectOf([60, 80, 300, 160], { width: 600, height: 800 }, scale),
    ).toEqual({
      left: 30,
      top: 40,
      width: 120,
      height: 40,
    });
  });
});

// 밴드 TRW13 A: 스크롤바 하나만큼(15) 다시 넓어진 폭은 무시 — 배율이 오가는 순환을 끊음. 줄어듦은 바로, 크게 넓어지면 받음.
describe('settleWidth', () => {
  it('줄어듦은 바로 받는다(쪽이 칸을 넘지 않게)', () => {
    expect(settleWidth(592, 577)).toBe(577);
    expect(settleWidth(592, 300)).toBe(300);
  });
  it('스크롤바 하나만큼(문턱 안) 넓어짐은 무시 → 같은 폭에 머묾', () => {
    expect(settleWidth(577, 592)).toBe(577);
    expect(settleWidth(577, 577 + WIDEN_SLACK)).toBe(577);
  });
  it('문턱을 넘게 넓어지면 받는다', () => {
    expect(settleWidth(577, 577 + WIDEN_SLACK + 1)).toBe(577 + WIDEN_SLACK + 1);
    expect(settleWidth(577, 900)).toBe(900);
  });
  it('처음(아직 잰 폭 0)은 그대로', () => {
    expect(settleWidth(0, 592)).toBe(592);
  });
  it('오가는 폭 562↔577 을 계속 넣어도 한 값에 가라앉음', () => {
    let held = 577;
    for (const measured of [562, 577, 562, 577, 562, 577])
      held = settleWidth(held, measured);
    expect(held).toBe(562);
  });
});
