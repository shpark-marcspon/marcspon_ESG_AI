// 온실가스 화면 움직임의 지연 셈(밴드 DB3 — sid:MARC-TICK-538). 값: band-handoffs/DB3-motion-values.md(e6) ①·②·③ + 발주서 감독 판단 2·3·5.
//   밴드 DB4: 고른 해 말풍선도 올림·초점 때만(지연 없음 — 사용자 11-08) → 말풍선 지연 셈(trendTipDelay)을 없앴다.
//   움직임 자체는 shared/ui/motion 의 CSS 클래스(gw-m-*)가 한다 — 여기는 차례 → 지연 ms 만(타이머·상태 0).
//   길이는 motion.css 의 숫자 그대로 옮겨 적는다(공용 변수를 세우지 않음 — sid:MARC-ISSUE-364).

/** 길이 ms(motion.css 의 클래스 값 — e6 ①). */
export const MOTION_MS = {
  /** gw-m-fade */
  fade: 220,
  /** gw-m-rise */
  rise: 420,
  /** gw-m-grow · gw-m-grow-y · gw-m-sweep */
  draw: 700,
} as const;
/** 줄 지연 간격(e6 ①). */
export const MOTION_STAGGER = 40;
/** 지연 상한(e6 ① — 몇 장이든 마지막 지연이 이것을 넘지 않음). */
export const MOTION_DELAY_CAP = 400;
/** 한 화면 총 길이 상한(e6 ① — 첫 그림 시작부터 마지막 움직임 끝까지). */
export const MOTION_SCREEN_CAP = 1000;

/** 그림(도넛·막대) 시작 지연(e6 ② — 120ms 뒤). */
const DRAW_START = 120;
/** 3개년 막대 칸 사이(e6 ② — 칸마다 80ms). */
const TREND_STEP = 80;
/** 카드 줄 판 지연 상한(e6 ② — 판마다 40ms, 최대 160ms). */
const CARD_CAP = 160;

/** 지연이 길이와 더해 한 화면 상한을 넘지 않게, 그리고 지연 상한을 넘지 않게 누른다. */
const capped = (delay: number, duration: number): number =>
  Math.min(delay, MOTION_DELAY_CAP, MOTION_SCREEN_CAP - duration);

/** 대시보드 카드 줄(감독 판단 2): 0 총 배출량 · 1~3 Scope 카드 · 4 사업장별 · 5 배출원별 → 0·40·80·120·160·160. */
export const cardRiseDelay = (order: number): number =>
  capped(Math.min(order * MOTION_STAGGER, CARD_CAP), MOTION_MS.rise);

/** 도넛 쓸기(e6 ② — 120ms 뒤). */
export const donutSweepDelay = (): number => capped(DRAW_START, MOTION_MS.draw);

/** 3개년 막대(e6 ② — 120 + 칸마다 80: 왼쪽부터 120·200·280). */
export const trendBarDelay = (column: number): number =>
  capped(DRAW_START + column * TREND_STEP, MOTION_MS.draw);

/** 사업장별 몫 막대 줄(e6 ② 120 + 줄마다 40 · 감독 판단 3: 「한 화면 상한 − 길이」= 300 에서 멈춤). */
export const siteGrowDelay = (row: number): number =>
  capped(DRAW_START + row * MOTION_STAGGER, MOTION_MS.draw);

/** 배출원별 몫 막대(e6 ② — 120 + Scope 칸마다 40: 120·160·200). */
export const sourceGrowDelay = (column: number): number =>
  capped(DRAW_START + column * MOTION_STAGGER, MOTION_MS.draw);
