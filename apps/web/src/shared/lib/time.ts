// 시각 글자(밴드 FW2 ①, sid:MARC-ISSUE-99 3 [N6]). 저장소는 ISO 8601 을 주고 화면이 꾸민다.
// 한국 시각(+09:00)으로 꾸민다: 서버의 확정 시각은 +09:00 이 붙은 ISO 이고(review_shapes.py), 실행 시각은 오프셋이 무엇이든
// 같은 순간을 한국 시각으로 옮긴다. 시험이 기계의 시간대에 기대지 않는다.
// 무효 조건: 한국 밖 사용자가 생겨 사용자 시간대로 보여야 하면 바꾼다.

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

/** ISO 8601 → 「2026-10-15 14:20」(한국 시각). 읽을 수 없으면 받은 글자 그대로. */
export function formatKst(iso: string): string {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return iso;
  const at = new Date(time + KST_OFFSET_MS);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${at.getUTCFullYear()}-${pad(at.getUTCMonth() + 1)}-${pad(at.getUTCDate())} ${pad(at.getUTCHours())}:${pad(at.getUTCMinutes())}`;
}

/** 「MM-DD」(한국 시각, 목록의 확정 표시). 읽을 수 없으면 받은 글자 그대로. */
export function formatKstMonthDay(iso: string): string {
  const full = formatKst(iso);
  return full === iso ? iso : full.slice(5, 10);
}

/** 「HH:MM」(한국 시각 — GW-04·05 의 「자동 저장됨 14:31」, 밴드 GW2R ②). 읽을 수 없으면 받은 글자 그대로. */
export function formatKstTime(iso: string): string {
  const full = formatKst(iso);
  return full === iso ? iso : full.slice(11, 16);
}

/** Date → +09:00 ISO 8601(초까지). 목 저장소가 서버처럼 시각을 지을 때 쓴다. */
export function toKstIso(date: Date): string {
  const at = new Date(date.getTime() + KST_OFFSET_MS);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${at.getUTCFullYear()}-${pad(at.getUTCMonth() + 1)}-${pad(at.getUTCDate())}T${pad(at.getUTCHours())}:${pad(at.getUTCMinutes())}:${pad(at.getUTCSeconds())}+09:00`;
}
