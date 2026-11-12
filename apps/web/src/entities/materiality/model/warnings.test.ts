// 경고 줄(밴드 IRW1 ① — 발주서 §3-1-6 · 경고 문구 표).
import { describe, expect, it } from 'vitest';

import { warningViews } from './warnings.ts';

const w = (code: string, topic: string | null = null) => ({ code, topic });

describe('warningViews', () => {
  it('같은 code 는 한 줄 · n = 서로 다른 토픽 수 + topic null 줄마다 하나', () => {
    expect(
      warningViews([
        w('items_out_of_range', 'A'),
        w('items_out_of_range', 'A'),
        w('items_out_of_range', 'B'),
        w('items_out_of_range', null),
      ]),
    ).toEqual([{ line: 'items_out_of_range', count: 3 }]);
  });

  it('같은 토픽의 phase 둘은 하나(phase 는 화면 꼴에 없다)', () => {
    expect(
      warningViews([
        w('keywords_missing_for_topic', 'A'),
        w('keywords_missing_for_topic', 'A'),
      ]),
    ).toEqual([{ line: 'keywords_missing_for_topic', count: 1 }]);
  });

  it('줄 수로 세는 셋 · 표 차례 · 그 밖 여덟·모르는 code 는 묶어 끝 한 줄(줄 수)', () => {
    expect(
      warningViews([
        w('rows_dropped', 'A'),
        w('xlsx_cell_truncated', 'A'),
        w('xlsx_cell_truncated', 'A'),
        w('answer_truncated', 'A'),
        w('subtopic_key_unmatched'),
        w('code_from_later', 'B'),
        w('item_date_unreadable', 'A'),
        w('topic_name_mismatch', 'A'),
      ]),
    ).toEqual([
      { line: 'item_date_unreadable', count: 1 },
      { line: 'subtopic_key_unmatched', count: 1 },
      { line: 'answer_truncated', count: 1 },
      { line: 'xlsx_cell_truncated', count: 2 },
      { line: 'other', count: 3 },
    ]);
    expect(warningViews([])).toEqual([]);
  });
});
