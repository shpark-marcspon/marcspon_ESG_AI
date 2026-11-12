// 밴드 FW2 ⓪: 새 점검 검사(파트 하나 이상). 수정본 대상 검사는 밴드 GW2R ① 에서 지웠다(v115 — 수정본 칸 뺌).
import { describe, expect, it } from 'vitest';

import { EMPTY_PARTS } from '../../../entities/greenwash/model/index.ts';
import { validateNewCheck } from './form.ts';

const uploaded = { pageCount: 60, hasText: true };

describe('validateNewCheck: 파트 하나 이상', () => {
  it('파트는 하나 이상이면 된다: 한 파트만 넣어도 사유 없음, 셋 다 비면 no_parts', () => {
    for (const key of ['ceo', 'company', 'climate'] as const)
      expect(
        validateNewCheck({
          uploaded,
          parts: { ...EMPTY_PARTS, [key]: [7] },
          partErrors: {},
        }),
        key,
      ).toEqual([]);
    expect(
      validateNewCheck({ uploaded, parts: EMPTY_PARTS, partErrors: {} }),
    ).toEqual([{ code: 'no_parts' }]);
  });
});
