// (밴드 FS1 ③: new-check.test.ts 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ⓪: 단어 키(서버 term_key 와 같게). 추가 단어 판정 차례 시험은 밴드 GW2R ② 에서 걷었다(검증 권고 R2 — 화면이 추가 단어를 받지 않는다).
import { describe, expect, it } from 'vitest';

import { termKey } from './extraTerms.ts';

describe('단어 키 = 서버 term_key', () => {
  it('비교 키는 서버 term_key 와 같은 꼴: normalize_term(소문자·구분 글자 공백·공백 접기) 뒤 공백 지움', () => {
    expect(termKey('  Tanso-Jungrip  ')).toBe('tansojungrip');
    expect(termKey('탄소 / 중립')).toBe('탄소중립');
    expect(termKey('A·B•C∙D_E')).toBe('abcde');
  });
});
