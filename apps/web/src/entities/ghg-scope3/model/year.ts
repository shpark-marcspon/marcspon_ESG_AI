// Scope 3 보고연도(밴드 S3W1 ① — 발주서 Q4). RPT-21 §3.3 「보고연도 선택, 기본값은 전년도」.
// 고를 수 있는 해는 전년도부터 내림 다섯 해 [추정 — 범위 근거 없음, 보고 물을 거리]. Scope 1·2 자리(entities/ghg 의 yearsOf — 올해부터)와
//   기본값이 달라 같이 쓰지 않고 셈을 옮겨 적었다(칸끼리 가져오지 않는다).

const SEOUL_OFFSET_MS = 9 * 60 * 60 * 1000;

/** 서울 시각의 올해(UTC+9 — 서머타임 없음. 글자를 수로 바꾸지 않으려고 시각을 옮겨 센다). */
export function seoulYear(today: Date): number {
  return new Date(today.getTime() + SEOUL_OFFSET_MS).getUTCFullYear();
}

/** 고를 수 있는 보고연도: 전년도부터 내림 다섯 해. 첫 값이 기본값이다. */
export function yearsOf(today: Date): number[] {
  const last = seoulYear(today) - 1;
  return [0, 1, 2, 3, 4].map((back) => last - back);
}

/** 주소의 연도가 고를 수 있는 해면 그 해, 아니면(없음·범위 밖) null — 부르는 쪽이 기본값(전년도)으로 replace. */
export const yearIn = (
  year: number | undefined,
  years: readonly number[],
): number | null => (year !== undefined && years.includes(year) ? year : null);
