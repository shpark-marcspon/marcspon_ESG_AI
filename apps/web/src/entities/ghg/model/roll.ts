// 온실가스 제목 숫자 굴림의 셈(밴드 DB4 — sid:MARC-TICK-543 · 발주서 §2-③ + 감독 판단 3). 화면 전용 순수 함수 — 타이머·상태 0.
//   공용 useCountUp 은 프레임마다 정수로 반올림해 끝 값도 정수가 된다(1,250.5 → 1,251 — DB3 값 문서 ②). 그래서 온실가스는 글자로 굴린다:
//   - 끝 글자(지금 화면이 그리는 문자열)에서 소수 자리 수와 쉼표 유무를 읽어, 굴리는 동안 모든 프레임을 같은 꼴로 적는다.
//   - 끝 프레임은 셈한 값이 아니라 그 끝 글자 그대로(바이트 같음).
//   - 0·음수·「-」·「<0.001」 같은 꼴 밖 글자는 굴리지 않는다(rollPlanOf → null).
//   길이·이징: 그리기 700ms(gw-m-grow·gw-m-sweep 와 같음) · cubic-bezier(0.22, 1, 0.36, 1)(motion.css 의 들어옴 이징).
//   지연 + 길이 ≤ 한 화면 상한 1,000 — 넘으면 길이를 줄인다(rollTiming).
import { MOTION_MS, MOTION_SCREEN_CAP } from './motion.ts';

/** 굴릴 수 있는 끝 글자의 꼴: 쉼표 묶음(1,234.5) 또는 쉼표 없는 수(1234.5). 앞 부호 없음. */
const GROUPED = /^[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?$/;
const PLAIN = /^[0-9]+(\.[0-9]+)?$/;

export interface RollPlan {
  /** 끝 글자(그대로 끝 프레임). */
  text: string;
  /** 끝 값(쉼표를 뺀 수). */
  value: number;
  /** 소수 자리 수(끝 글자 그대로). */
  places: number;
  /** 쉼표로 천 단위를 묶는가(끝 글자 그대로). */
  grouped: boolean;
}

/** 끝 글자를 굴릴 수 있으면 그 꼴, 아니면 null(0 이하·꼴 밖 — 바로 끝 글자). */
export function rollPlanOf(text: string): RollPlan | null {
  const grouped = GROUPED.test(text);
  if (!grouped && !PLAIN.test(text)) return null;
  const value = Number(text.replace(/,/g, ''));
  if (!Number.isFinite(value) || !(value > 0)) return null;
  const dot = text.indexOf('.');
  return {
    text,
    value,
    places: dot < 0 ? 0 : text.length - dot - 1,
    grouped,
  };
}

/** 정수부에 쉼표(세 자리마다). */
const group = (int: string) => int.replace(/\B(?=([0-9]{3})+(?![0-9]))/g, ',');

/** 진행 progress(0~1, 이징 뒤가 아니라 시간 몫)의 프레임 글자. 1 이상이면 끝 글자 그대로. */
export function rollFrame(plan: RollPlan, progress: number): string {
  if (progress >= 1) return plan.text;
  const eased = rollEase(Math.max(0, progress));
  // 끝 값을 넘지 않게(이징이 1 을 넘지 않지만 반올림이 끝 글자를 앞지르지 않게 한 번 더 누른다).
  const fixed = Math.min(plan.value * eased, plan.value).toFixed(plan.places);
  const [int = '0', frac] = fixed.split('.');
  const head = plan.grouped ? group(int) : int;
  return frac === undefined ? head : `${head}.${frac}`;
}

/** cubic-bezier(x1, y1, x2, y2) — 시간 몫 x 에서 값 몫 y(CSS 와 같은 셈: x 로 t 를 풀고 y(t)). */
function cubicBezier(x1: number, y1: number, x2: number, y2: number) {
  const at = (a: number, b: number, t: number) =>
    3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3;
  return (x: number): number => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    // x(t) 는 단조 증가(0 ≤ x1, x2 ≤ 1) — 이분법으로 푼다(40 번이면 1e-12 안).
    let low = 0;
    let high = 1;
    for (let step = 0; step < 40; step += 1) {
      const mid = (low + high) / 2;
      if (at(x1, x2, mid) < x) low = mid;
      else high = mid;
    }
    return at(y1, y2, (low + high) / 2);
  };
}

/** 그리기 이징(motion.css 의 cubic-bezier(0.22, 1, 0.36, 1) — DB3 값 문서 ①). */
export const rollEase = cubicBezier(0.22, 1, 0.36, 1);

/** 굴림 시작 지연과 길이(ms): 길이는 그리기 700, 지연 + 길이가 한 화면 상한 1,000 을 넘으면 길이를 줄인다. */
export function rollTiming(delay: number): { delay: number; duration: number } {
  const start = Math.max(0, Math.min(delay, MOTION_SCREEN_CAP));
  return {
    delay: start,
    duration: Math.max(0, Math.min(MOTION_MS.draw, MOTION_SCREEN_CAP - start)),
  };
}
