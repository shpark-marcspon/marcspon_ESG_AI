// Scope 3 카테고리 이름 한 벌을 글자로 박는다(밴드 S3T1 — 서버 scope3_state.CATEGORY_NAMES·run-log 단계 이름과 같은 글자).
// 마크스폰 용어(박세현 11-10): 임차 자산(C8·C13, 밴드 S3V1)·운송(C4·C9, 밴드 S3T1) 모두 업스트림·다운스트림.
import { describe, expect, it } from 'vitest';

import { S3_TEXT } from './text.ts';

describe('Scope 3 카테고리 이름', () => {
  it('C1~C15 열다섯 글자 그대로(서버 단계·run-log 는 C10 없음)', () => {
    expect(S3_TEXT.categories).toEqual({
      C1: '구매 상품 및 서비스',
      C2: '자본재',
      C3: '연료 및 에너지 활동',
      C4: '업스트림 운송 및 유통',
      C5: '사업장 발생 폐기물',
      C6: '출장',
      C7: '출퇴근',
      C8: '업스트림 임차 자산',
      C9: '다운스트림 운송 및 유통',
      C10: '판매된 제품의 가공',
      C11: '판매된 제품의 사용',
      C12: '판매된 제품의 폐기',
      C13: '다운스트림 임차 자산',
      C14: '프랜차이즈',
      C15: '투자',
    });
  });
});
