// 경고 줄(밴드 IRW1 ① — 발주서 §2-1 「경고 문구 표」). result@2.warnings → 결과 화면 안내 한 줄씩. 글은 문구 표(IR_TEXT.warnings)가
//   갈래 열쇠로 고르고 n 을 끼운다. 서버 message 는 화면 꼴에 없다(거울이 버린다).
// 같은 code 는 토픽마다 되풀이돼도 한 줄. n = 서로 다른 topic 수 + topic null 줄은 줄마다 하나(같은 토픽의 phase 둘은 하나).
//   subtopic_key_unmatched·answer_truncated·xlsx_cell_truncated 는 줄 수. 표의 일곱 밖(여덟·모르는 code)은 묶어 한 줄(n = 줄 수).
// 차례는 표대로, 묶음은 끝.
import type { Warning } from './result.ts';

export type WarningLine =
  | 'item_date_unreadable'
  | 'items_out_of_range'
  | 'subtopic_autofilled'
  | 'subtopic_key_unmatched'
  | 'keywords_missing_for_topic'
  | 'answer_truncated'
  | 'xlsx_cell_truncated'
  | 'other';

/** 표의 일곱(차례). */
export const WARNING_LINES: readonly Exclude<WarningLine, 'other'>[] = [
  'item_date_unreadable',
  'items_out_of_range',
  'subtopic_autofilled',
  'subtopic_key_unmatched',
  'keywords_missing_for_topic',
  'answer_truncated',
  'xlsx_cell_truncated',
];

/** 줄 수로 세는 code. */
const BY_ROW: ReadonlySet<string> = new Set([
  'subtopic_key_unmatched',
  'answer_truncated',
  'xlsx_cell_truncated',
]);

export interface WarningView {
  line: WarningLine;
  count: number;
}

export function warningViews(warnings: readonly Warning[]): WarningView[] {
  const known = new Set<string>(WARNING_LINES);
  const out: WarningView[] = [];
  for (const line of WARNING_LINES) {
    const rows = warnings.filter((w) => w.code === line);
    if (rows.length === 0) continue;
    const count =
      BY_ROW.has(line) ?
        rows.length
      : new Set(rows.filter((w) => w.topic !== null).map((w) => w.topic)).size +
        rows.filter((w) => w.topic === null).length;
    out.push({ line, count });
  }
  const other = warnings.filter((w) => !known.has(w.code)).length;
  if (other > 0) out.push({ line: 'other', count: other });
  return out;
}
