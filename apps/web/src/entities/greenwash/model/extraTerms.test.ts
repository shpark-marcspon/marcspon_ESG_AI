// 단어 키(밴드 FW1b ②): 서버 term_key 와 같은 정규화. 추가 단어 판정(checkExtraTerm) 시험은 밴드 GW2R ② 에서 걷었다(검증 권고 R2).
import { describe, expect, it } from 'vitest';

import { termKey } from './extraTerms.ts';

describe('termKey: 노트북 normalize_term 뒤 공백을 모두 지운 키', () => {
  it.each([
    ['탄소 중립', '탄소중립'],
    ['탄소-중립', '탄소중립'],
    ['탄소 - 중립', '탄소중립'],
    ['탄소중립', '탄소중립'],
    ['  Green  ', 'green'],
    ['GREEN', 'green'],
    ['low_carbon', 'lowcarbon'],
    ['a/b·c•d∙e', 'abcde'],
    ['저탄소   공정', '저탄소공정'],
    ['eco', 'eco'],
    ['eco프리', 'eco프리'],
    ['-', ''],
    ['  ', ''],
  ] as const)('%j → %j', (raw, key) => {
    expect(termKey(raw)).toBe(key);
  });
});
