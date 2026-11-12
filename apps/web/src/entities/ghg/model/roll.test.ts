// 온실가스 제목 숫자 굴림 셈(밴드 DB4 — sid:MARC-TICK-543 · 발주서 §3 시험 2 · 감독 판단 3·4). 값은 지어낸 값.
//   시작 0 → 끝 값 · 각 프레임 소수 자리 = 끝 소수 자리 · 쉼표 꼴 = 끝 꼴 · 끝 프레임 = 주어진 끝 글자(바이트) · 지연 + 길이 ≤ 1,000.
import { describe, expect, it } from 'vitest';

import {
  MOTION_MS,
  MOTION_SCREEN_CAP,
  cardRiseDelay,
  donutSweepDelay,
  rollEase,
  rollFrame,
  rollPlanOf,
  rollTiming,
} from './index.ts';

const STEPS = Array.from({ length: 41 }, (_, at) => at / 40);
const placesOf = (text: string) =>
  text.includes('.') ? text.length - text.indexOf('.') - 1 : 0;

describe('제목 숫자 굴림 셈(DB4)', () => {
  it('굴릴 수 있는 꼴: 쉼표 묶음·쉼표 없음·정수 · 굴리지 않음: 0·음수·「-」·「<0.001」·빈 글·꼴 틀린 쉼표', () => {
    expect(rollPlanOf('12,345.679')).toEqual({
      text: '12,345.679',
      value: 12345.679,
      places: 3,
      grouped: true,
    });
    expect(rollPlanOf('1234.57')).toMatchObject({
      value: 1234.57,
      places: 2,
      grouped: false,
    });
    expect(rollPlanOf('60')).toMatchObject({ places: 0, grouped: false });
    for (const text of [
      '0',
      '0.0',
      '-5',
      '-',
      '<0.001',
      '>-0.001',
      '',
      '1,23',
      '12,34.5',
      '1.2.3',
    ])
      expect([text, rollPlanOf(text)]).toEqual([text, null]);
  });

  it('프레임: 0 에서 시작 · 끝 프레임은 주어진 끝 글자 그대로(바이트) · 모든 프레임이 끝과 같은 소수 자리·쉼표 꼴 · 끝 값을 넘지 않고 늘어남', () => {
    const cases = [
      '12,345.679',
      '1,250.5',
      '0.25',
      '98,765.432',
      '1234.57',
      '1,000,000',
      '7',
    ];
    for (const text of cases) {
      const plan = rollPlanOf(text)!;
      const frames = STEPS.map((step) => rollFrame(plan, step));
      expect([text, frames[0]]).toEqual([text, (0).toFixed(plan.places)]);
      expect([text, frames.at(-1)]).toEqual([text, text]);
      expect(rollFrame(plan, 1.5)).toBe(text);
      let before = -1;
      for (const frame of frames) {
        expect([text, frame, placesOf(frame)]).toEqual([
          text,
          frame,
          plan.places,
        ]);
        // 쉼표가 없는 끝이면 프레임에도 0 · 있으면 천 단위 묶음 꼴(4자리 이상 정수부)
        const int = frame.split('.')[0]!;
        if (!plan.grouped)
          expect([text, frame, int.includes(',')]).toEqual([
            text,
            frame,
            false,
          ]);
        else
          expect([text, frame, /^[0-9]{1,3}(,[0-9]{3})*$/.test(int)]).toEqual([
            text,
            frame,
            true,
          ]);
        const value = Number(frame.replace(/,/g, ''));
        expect(value).toBeGreaterThanOrEqual(before);
        expect(value).toBeLessThanOrEqual(plan.value);
        before = value;
      }
    }
  });

  it('끝 프레임은 셈 값이 아니라 끝 글자: 셈이 같은 수를 내도 글자를 그대로 돌려줌(반올림으로 바꾸지 않음)', () => {
    // 지어낸 끝 글자 — 소수 둘 · 정수 굴림이면 1,251 이 된다(공용 useCountUp 의 Math.round)
    const plan = rollPlanOf('1,250.5')!;
    expect(rollFrame(plan, 1)).toBe('1,250.5');
    expect(rollFrame(plan, 0.999)).toMatch(/^1,2[0-9]{2}\.[0-9]$/);
    expect(rollFrame(plan, 0.999)).not.toBe('1,251');
  });

  it('이징 = cubic-bezier(0.22, 1, 0.36, 1): 0 → 0 · 1 → 1 · 늘어남 · 반쯤에 이미 0.9 넘음(들어옴 이징)', () => {
    expect(rollEase(0)).toBe(0);
    expect(rollEase(1)).toBe(1);
    let before = 0;
    for (const step of STEPS) {
      const value = rollEase(step);
      expect(value).toBeGreaterThanOrEqual(before - 1e-9);
      before = value;
    }
    expect(rollEase(0.5)).toBeGreaterThan(0.9);
  });

  it('길이·지연: 여섯 자리(총 0 · Scope 40·80·120 · 도넛 가운데·인벤토리 120) 모두 700ms, 지연 + 길이 ≤ 1,000 · 늦은 지연은 길이를 줄임', () => {
    const delays = [
      cardRiseDelay(0),
      cardRiseDelay(1),
      cardRiseDelay(2),
      cardRiseDelay(3),
      donutSweepDelay(),
      donutSweepDelay(),
    ];
    expect(delays).toEqual([0, 40, 80, 120, 120, 120]);
    for (const delay of delays) {
      const timing = rollTiming(delay);
      expect(timing).toEqual({ delay, duration: MOTION_MS.draw });
      expect(timing.delay + timing.duration).toBeLessThanOrEqual(
        MOTION_SCREEN_CAP,
      );
    }
    expect(rollTiming(400)).toEqual({ delay: 400, duration: 600 });
    expect(rollTiming(2000)).toEqual({ delay: 1000, duration: 0 });
    for (let delay = 0; delay <= 1200; delay += 50) {
      const timing = rollTiming(delay);
      expect(timing.delay + timing.duration).toBeLessThanOrEqual(
        MOTION_SCREEN_CAP,
      );
    }
  });
});
