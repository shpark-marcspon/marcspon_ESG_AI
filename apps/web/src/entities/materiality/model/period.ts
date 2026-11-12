// 리서치 기간 보기(밴드 IRW1 ① — 발주서 §2-1). scope.dateRange 를 서버 문법(apps/api-py/esgapi/materiality/contracts/wire.py:763-766
//   DATE_RANGE — 「YYYY-MM-DD~YYYY-MM-DD」·「YYYY-MM-DD~오늘까지」, 전체가 맞아야 함)으로 읽어 「시작 ~ 끝」.
// 「오늘까지」의 날은 실행이 돌기 시작한 날(한국 시각) — 실행기가 처리를 잡은 뒤 끼움의 inputs 가 today() 를 읽는다
//   (★D: runs/tasks.py 의 bare.inputs ← flows/binding_155.py:120-121). 그래서 startedAt(없으면 createdAt)의 한국 날짜다.
// 읽지 못하면 원문 그대로(raw).
import { formatKst } from '../../../shared/lib/time.ts';
import { UNTIL_TODAY } from './wire.ts';

export type Period =
  { kind: 'range'; start: string; end: string } | { kind: 'raw'; text: string };

const DAY = '[0-9]{4}-[0-9]{2}-[0-9]{2}';
const DATE_RANGE = new RegExp(
  `^\\s*(${DAY})\\s*~\\s*(${DAY}|${UNTIL_TODAY})\\s*$`,
);

/** ISO 시각 → 한국 날짜 「YYYY-MM-DD」. 읽지 못하면 null. */
export function kstDay(iso: string | null): string | null {
  if (iso === null) return null;
  const full = formatKst(iso);
  return full === iso ? null : full.slice(0, 10);
}

/** dateRange → 기간. day = 「오늘까지」의 날(startedAt·createdAt 의 한국 날짜 — 없으면 원문). */
export function periodOf(dateRange: string, day: string | null): Period {
  const match = DATE_RANGE.exec(dateRange);
  if (match === null) return { kind: 'raw', text: dateRange };
  const [, start, end] = match;
  if (end === UNTIL_TODAY)
    return day === null ?
        { kind: 'raw', text: dateRange }
      : { kind: 'range', start: start!, end: day };
  return { kind: 'range', start: start!, end: end! };
}

/** 실행의 「오늘까지」 날: startedAt, 없으면 createdAt 의 한국 날짜. */
export const runDay = (run: {
  startedAt: string | null;
  createdAt: string;
}): string | null => kstDay(run.startedAt) ?? kstDay(run.createdAt);
