// 대시보드(S1) 응답 꼴과 그 판 셈(밴드 DB1 ② — 서버 GET /inventory/scope12/dashboard, sid:MARC-ENT-469·461, e6 표시 sid:MARC-ISSUE-599).
// 배출량은 서버 글자 그대로(tCO2-eq, 위치기반). 이 파일은 그림의 몫(도넛 조각·막대 길이)과 Scope 3 표시 갈래만 셈한다 — 합은 서버가 셈한다.
//   Scope 3 표시(e6): 결과 없음(total.scope3 null — 전부 실패한 해도) → 「Scope 3 결과 없음」만 · 값 있고 빠진 시트 n>0 → 「시트 n개 빠짐」 ·
//   그 밖 표시 없음(결과 화면 ResultView 와 같은 차례 — 합이 null 이면 「빠짐」 숨김).
// 밴드 DB2(sid:MARC-ENT-598 — sid:MARC-ENT-469 의 숨김 둘을 갈음): Scope 별 3개년 막대(눈금·막대 높이)와 총 배출량 「전년 대비」 갈래. 값 band-handoffs/DB2-figma-values.md(e6) ①~⑤.

export interface DashboardSource {
  nodeId: string;
  name: string;
  value: string;
  share: string | null;
}

export interface DashboardScope {
  scopeId: string;
  scopeName: string;
  /** 풀 뿌리 전체 가운데 몇째(1부터 — 1 = Scope 1 자리, 2 = Scope 2 자리). scopes 는 선택 잎 있는 뿌리만이라 목록 차례로 잡지 않는다(DB1 검증 B1). */
  scopeOrder: number;
  value: string | null;
  topSources: DashboardSource[];
}

export interface DashboardTotal {
  scope12: string | null;
  /** 1차 늘 null — 화면에 쓰지 않는다(시장기반 숨김, sid:MARC-ENT-461). */
  scope2Market: string | null;
  scope3: string | null;
  sum: string | null;
  scope3FailedSheets: number;
}

export interface DashboardSiteScope {
  scopeId: string;
  value: string | null;
}

export interface DashboardSite {
  siteId: string;
  siteName: string;
  scopes: DashboardSiteScope[];
  /** 1차 늘 null — 화면에 쓰지 않는다(사업장별 Scope 3 없음). */
  scope3: string | null;
}

export interface DashboardCategory {
  category: string;
  name: string;
  value: string;
  share: string | null;
}

/** Scope12DashboardOut. configured 거짓 = Scope 1·2 빈 상태(scopes 빔) — Scope 3 칸은 따로 셈해 온다. */
export interface Dashboard {
  year: number;
  configured: boolean;
  decimals: number;
  /** 1차 늘 위치기반 글자(서버 Literal — 화면은 쓰지 않는다). */
  basis: string;
  unit: string;
  complete: boolean;
  scopes: DashboardScope[];
  total: DashboardTotal;
  bySite: DashboardSite[];
  scope3Categories: DashboardCategory[];
}

/** Scope 3 표시 갈래(e6). */
export type Scope3Mark =
  { kind: 'none' } | { kind: 'missing'; sheets: number } | { kind: 'clean' };

export function scope3MarkOf(total: DashboardTotal): Scope3Mark {
  if (total.scope3 === null) return { kind: 'none' };
  return total.scope3FailedSheets > 0 ?
      { kind: 'missing', sheets: total.scope3FailedSheets }
    : { kind: 'clean' };
}

/** 그림에 쓰는 수(글자 → 수 — 그림 몫만, 표시 글은 글자 그대로). 수가 아니거나 음수면 0(조각·막대는 0 이상). */
export function drawn(value: string | null): number {
  if (value === null) return 0;
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

/** Scope 1·2 자리의 뿌리(scopeOrder 1·2 — 없으면 undefined). */
export function scopeAt(
  board: Dashboard,
  order: 1 | 2,
): DashboardScope | undefined {
  return board.scopes.find((scope) => scope.scopeOrder === order);
}

/** 판의 Scope 셋 값(Scope 1·2 = scopeOrder 1·2 뿌리, Scope 3 = total.scope3). 없으면 null. */
export function scopeValuesOf(
  board: Dashboard,
): [string | null, string | null, string | null] {
  return [
    scopeAt(board, 1)?.value ?? null,
    scopeAt(board, 2)?.value ?? null,
    board.total.scope3,
  ];
}

/** 0~1 몫 셋(Scope 1·2·3 차례 — 도넛 호 · 배출원 카드 몫 막대). 그림 수가 모두 0 이면 전부 0. */
export function scopeSharesOf(board: Dashboard): [number, number, number] {
  const amounts = scopeValuesOf(board).map(drawn);
  const whole = amounts.reduce((sum, amount) => sum + amount, 0);
  const share = (index: number) => (whole > 0 ? amounts[index]! / whole : 0);
  return [share(0), share(1), share(2)];
}

/** 몫 글자(서버 share — 소수 첫째 자리 퍼센트) → 판 꼴 정수 %. 0 보다 크고 반올림이 0 이면 'below'(「<1%」). 없으면 null. */
export function sharePercent(share: string | null): number | 'below' | null {
  if (share === null) return null;
  const value = Number(share);
  if (!Number.isFinite(value)) return null;
  const rounded = Math.round(value);
  return value > 0 && rounded === 0 ? 'below' : rounded;
}

export interface SiteBar {
  siteId: string;
  siteName: string;
  /** 그 사업장 Scope 합(그림 수 — 표시 반올림 전). 값 있는 Scope 가 없으면 null. */
  sum: number | null;
  /** 그 사업장 안 몫(합 = 1, 합 0 이면 전부 0). order = 그 뿌리의 scopeOrder(색 — 모르면 0). */
  parts: { scopeId: string; order: number; share: number }[];
}

/** 사업장별 막대(e6 값 파일 ② 판 2): 합이 큰 차례(같으면 서버 차례), 막대 안은 그 사업장 안 몫. 사업장별 Scope 3 은 1차 없음. */
export function siteBarsOf(board: Dashboard): SiteBar[] {
  const orderOf = new Map(
    board.scopes.map((scope) => [scope.scopeId, scope.scopeOrder]),
  );
  const bars = board.bySite.map((site, order) => {
    const known = site.scopes.filter((part) => part.value !== null);
    const sum =
      known.length === 0 ?
        null
      : known.reduce((total, part) => total + Number(part.value), 0);
    const whole = site.scopes.reduce(
      (total, part) => total + drawn(part.value),
      0,
    );
    return {
      order,
      siteId: site.siteId,
      siteName: site.siteName,
      sum,
      parts: site.scopes.map((part) => ({
        scopeId: part.scopeId,
        order: orderOf.get(part.scopeId) ?? 0,
        share: whole > 0 ? drawn(part.value) / whole : 0,
      })),
    };
  });
  bars.sort(
    (a, b) => (b.sum ?? -Infinity) - (a.sum ?? -Infinity) || a.order - b.order,
  );
  return bars.map((bar) => ({
    siteId: bar.siteId,
    siteName: bar.siteName,
    sum: bar.sum,
    parts: bar.parts,
  }));
}

/** 미설정 덮개(e6 값 파일 ③): 그 해 Scope 1·2 설정도 없고 Scope 3 결과도 없을 때만. */
export const coveredOf = (board: Dashboard): boolean =>
  !board.configured && board.total.scope3 === null;

/** 한 해 판(밴드 DB2 — 세 해를 따로 받는다, e6 ⑤). 아직 안 옴 · 없음(실패·거절 — 오류 띠 없음) · 받음. */
export type YearBoard =
  { kind: 'loading' } | { kind: 'none' } | { kind: 'ready'; board: Dashboard };

/** 막대 그림 높이(e6 ① — 눈금 최대 = 160px). */
export const TREND_HEIGHT = 160;
/** 0 보다 큰 값의 최소 막대 높이(e6 ① — 보이게). */
export const TREND_MIN_BAR = 2;

/** 눈금(e6 ① 「눈금 최대 고르는 법」): 칸 하나 step · 눈금 최대 = 4×step. */
export interface TrendScale {
  step: number;
  max: number;
}

const STEP_BASES = [1, 2, 2.5, 5] as const;

/** 있는 값들(없음은 빼고 0 은 넣음)의 가장 큰 값 M 에 대해 4×step ≥ M 인 가장 작은 {1,2,2.5,5}×10^k. M ≤ 0 이거나 값이 없으면 step 1. */
export function trendScaleOf(values: readonly number[]): TrendScale {
  const top = values.reduce((most, value) => Math.max(most, value), 0);
  if (!(top > 0) || !Number.isFinite(top)) return { step: 1, max: 4 };
  const start = Math.floor(Math.log10(top / 4)) - 1;
  for (let power = start; ; power += 1)
    for (const base of STEP_BASES) {
      // 10^k 를 글자로 세워 부동소수 꼬리를 피한다(0.1×3 꼴).
      const step = Number(`${base}e${power}`);
      if (step * 4 >= top) return { step, max: Number(`${base * 4}e${power}`) };
    }
}

/** step 의 소수 자리 수(0.25 → 2 · 250 → 0). */
function decimalsOf(step: number): number {
  const text = `${step}`;
  const exponent = /e-(\d+)$/.exec(text);
  if (exponent) {
    const mantissa = text.split('e')[0]!;
    return Number(exponent[1]) + (mantissa.split('.')[1]?.length ?? 0);
  }
  return text.split('.')[1]?.length ?? 0;
}

/** 눈금 글 다섯(위에서 아래로 최대 · ¾ · ½ · ¼ · 0 — e6 ①). 1,000 이상은 ÷1,000 + 쉼표 + 「K」, 그 아래는 step 만큼의 소수, 0 은 「0」. */
export function trendTicksOf(scale: TrendScale): string[] {
  const decimals = decimalsOf(scale.step);
  return [4, 3, 2, 1, 0].map((times) => {
    const value = Number((scale.step * times).toFixed(decimals));
    if (value === 0) return '0';
    if (value >= 1000)
      return `${(value / 1000).toLocaleString('en-US', { maximumFractionDigits: 3 })}K`;
    return value.toLocaleString('en-US', { maximumFractionDigits: decimals });
  });
}

/** 막대 높이 px(값 ÷ 눈금 최대 × 160). 0 이하는 0, 0 보다 크면 최소 2. */
export function trendBarHeight(value: number, scale: TrendScale): number {
  if (!(value > 0)) return 0;
  return Math.max(
    TREND_MIN_BAR,
    Math.min(TREND_HEIGHT, (value / scale.max) * TREND_HEIGHT),
  );
}

/** 말풍선 높이 px(e6 「추정」 2 — 안쪽 6 + 10px 줄 14 + 14px 줄 22.4 + 6, 실측으로 맞춤). */
export const TREND_TIP_HEIGHT = 49;

/** 말풍선 위끝(e6 ① 「자리」): 막대 꼭대기에 맞추고 그림(161) 위·아래 밖으로 나가지 않게 0~(161−말풍선 높이) 안으로 누른다. */
export function trendTipTop(height: number): number {
  return Math.max(
    0,
    Math.min(TREND_HEIGHT - height, TREND_HEIGHT + 1 - TREND_TIP_HEIGHT),
  );
}

/** 막대 칸 하나(e6 ③): 아직 안 옴 · 없음(막대·말풍선 0, 연도 글만) · 값(0 이면 높이 0, 말풍선 「0」). */
export type TrendBar =
  | { year: number; kind: 'loading' | 'none' }
  | { year: number; kind: 'value'; value: string; height: number };

export interface Trend {
  ticks: string[];
  /** 왼쪽부터 고른 해 −2 · −1 · 고른 해(e6 ① 「세 해와 강조」). */
  bars: TrendBar[];
}

/** 그 Scope(0·1·2 = Scope 1·2·3 — scopeValuesOf 자리)의 3개년 막대. years 는 왼쪽부터 −2 · −1 · 고른 해. 눈금은 있는 값만으로(e6 ③). */
export function trendOf(
  years: readonly { year: number; board: YearBoard }[],
  scope: 0 | 1 | 2,
): Trend {
  const read = years.map(({ year, board }) => {
    if (board.kind !== 'ready') return { year, kind: board.kind };
    const value = scopeValuesOf(board.board)[scope] ?? null;
    const number = value === null ? Number.NaN : Number(value);
    return Number.isFinite(number) ?
        { year, kind: 'value' as const, value: value!, number }
      : { year, kind: 'none' as const };
  });
  const scale = trendScaleOf(
    read.flatMap((bar) => (bar.kind === 'value' ? [bar.number] : [])),
  );
  return {
    ticks: trendTicksOf(scale),
    bars: read.map((bar) =>
      bar.kind === 'value' ?
        {
          year: bar.year,
          kind: 'value',
          value: bar.value,
          height: trendBarHeight(bar.number, scale),
        }
      : bar,
    ),
  };
}

/** 총 배출량 「전년 대비」 갈래(e6 ②). percent = 크기만, 소수 한 자리(half-up) 글자. */
export type YearChange =
  | { kind: 'hidden' }
  | { kind: 'same' }
  | { kind: 'up' | 'down'; percent: string };

/** 십진 글자 → 정수와 소수 자리(정확한 셈 — 부동소수 x.x5 가장자리를 피한다). 꼴이 아니면 null. */
function decimalOf(text: string): { digits: bigint; scale: number } | null {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text.trim());
  if (!match) return null;
  const fraction = match[3] ?? '';
  const digits = BigInt(`${match[2]}${fraction}`);
  return {
    digits: match[1] === '-' ? -digits : digits,
    scale: fraction.length,
  };
}

const TEN = BigInt(10);
const pow10 = (times: number) => TEN ** BigInt(times);

/** 두 해에서 같은 것을 센 합인가(e6 ② — Scope 3 결과 없음·시트 빠짐이면 비교가 거짓 · 감독 판단 11: Scope 1·2 합 없음도 같음). */
const comparable = (total: DashboardTotal): boolean =>
  total.scope12 !== null &&
  total.scope3 !== null &&
  total.scope3FailedSheets === 0;

/**
 * 고른 해 vs 앞 해 총합(서버 total.sum 글자 — 웹에서 다시 더하지 않는다). (고른 − 앞) ÷ 앞 × 100, 크기에 half-up 소수 한 자리.
 * 방향은 반올림 전 부호, 반올림한 크기가 0.0 이면 「같음」(감독 판단 1 — -0.05% → 0.1% 감소, -0.04% → 같음).
 * 숨김: 앞 해 아직 안 옴·없음 · 어느 쪽 합이 없음·꼴 아님 · 앞 해 합 0 이하 · 어느 해든 Scope 1·2 합 없음(판단 11)·Scope 3 결과 없음·시트 빠짐.
 */
export function yearChangeOf(current: Dashboard, prior: YearBoard): YearChange {
  if (prior.kind !== 'ready') return { kind: 'hidden' };
  const before = prior.board.total;
  if (!comparable(current.total) || !comparable(before))
    return { kind: 'hidden' };
  if (current.total.sum === null || before.sum === null)
    return { kind: 'hidden' };
  const now = decimalOf(current.total.sum);
  const was = decimalOf(before.sum);
  if (now === null || was === null || was.digits <= BigInt(0))
    return { kind: 'hidden' };
  const scale = Math.max(now.scale, was.scale);
  const a = now.digits * pow10(scale - now.scale);
  const b = was.digits * pow10(scale - was.scale);
  const diff = a - b;
  if (diff === BigInt(0)) return { kind: 'same' };
  const size = diff < BigInt(0) ? -diff : diff;
  // 십분율 tenths = round_half_up(size × 1000 ÷ b)
  const tenths = (size * BigInt(2000) + b) / (BigInt(2) * b);
  if (tenths === BigInt(0)) return { kind: 'same' };
  const percent = `${tenths / TEN}.${tenths % TEN}`;
  return { kind: diff > BigInt(0) ? 'up' : 'down', percent };
}
