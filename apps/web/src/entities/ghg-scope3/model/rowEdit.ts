// Scope 3 줄 제외·복구의 셈(밴드 S3W3b ① — 발주서 1-6). 순수 함수 — React·표기 0.
//   앞 글 열: 제외 줄의 「산정 제외 - 」를 붙일 열. 그리기만 한다 — 검색·정렬·셈은 서버 줄 값을 본다(cellOf 를 바꾸지 않는다).
//   고름: rowId 의 모음. rowId 는 「시트!엑셀 줄」이라 새 실행에도 같은 글자가 있고 다른 줄이다 — 실행이 바뀌면 화면이 고름을 비운다(sid:MARC-ENT-570).
//   한 단추 = 한 요청 = 한 사유: 섞어 고르면 단추마다 해당 줄만 보낸다. 요청은 카테고리 하나(시트가 달라도 된다).
import { SHEET_COLUMNS, TEXT_COLUMNS } from './detail.ts';
import type { ColumnId, SheetLayout } from './detail.ts';
import type { ResultRow } from './result.ts';

/** 한 요청의 줄 한도(서버 Scope3RowEditIn). */
export const ROW_EDIT_MAX = 2000;
/** 사유 한도(서버 Scope3RowEditIn — Scope 1·2 의 500 과 따로다). */
export const ROW_REASON_MAX = 300;
/** 히스토리 창 한 쪽. */
export const HISTORY_PAGE_SIZE = 20;

export type RowEditKind = 'exclude' | 'restore';

/** 제외 줄 앞 글을 붙이는 열: group → 표 차례의 첫 글 열 → row(글 열이 없는 표). */
export function leadColumn(layout: SheetLayout): ColumnId {
  const columns = SHEET_COLUMNS[layout];
  if (columns.includes('group')) return 'group';
  return columns.find((one) => TEXT_COLUMNS.includes(one)) ?? 'row';
}

/** 보낼 줄: 고른 줄 중 제외는 산정에 든 줄, 복구는 제외된 줄. */
export function rowsToSend(
  rows: readonly ResultRow[],
  chosen: ReadonlySet<string>,
  kind: RowEditKind,
): string[] {
  const out: string[] = [];
  for (const row of rows)
    if (
      row.rowId !== null &&
      chosen.has(row.rowId) &&
      (row.excluded ?? false) === (kind === 'restore')
    )
      out.push(row.rowId);
  return out;
}

/** 한 요청 한도를 넘는가 — 고른 수가 아니라 그 단추의 보낼 줄 수로 잰다. */
export const overRowLimit = (ids: readonly string[]) =>
  ids.length > ROW_EDIT_MAX;

/** 줄 id 만(rowId 가 없는 줄은 고르지 못한다). */
export const rowIdsOf = (rows: readonly ResultRow[]): string[] =>
  rows.flatMap((row) => (row.rowId === null ? [] : [row.rowId]));

/** 고름에 줄을 넣거나 뺀 새 모음. */
export function pick(
  chosen: ReadonlySet<string>,
  ids: readonly string[],
  on: boolean,
): Set<string> {
  const next = new Set(chosen);
  for (const id of ids) {
    if (on) next.add(id);
    else next.delete(id);
  }
  return next;
}

/** 머리 체크 상태: 그 쪽 줄이 다 골렸는가. */
export function pickState(
  chosen: ReadonlySet<string>,
  ids: readonly string[],
): boolean | 'indeterminate' {
  const count = ids.filter((id) => chosen.has(id)).length;
  if (count === 0) return false;
  return count === ids.length ? true : 'indeterminate';
}

/** 사유 검사 — 앞뒤 빈칸을 걷은 글 기준. 서버는 코드 포인트로 세므로 같게 센다. */
export function reasonFault(text: string): 'required' | 'tooLong' | null {
  const trimmed = text.trim();
  if (trimmed === '') return 'required';
  return [...trimmed].length > ROW_REASON_MAX ? 'tooLong' : null;
}
