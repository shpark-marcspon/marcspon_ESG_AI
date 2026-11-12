// 새 점검 폼 검사 사유 코드와 실행 진행 모델(밴드 FW1b ①).
import { describe, expect, it } from 'vitest';

import {
  MAX_PAGE_COUNT,
  parsePageRange,
} from '../../../entities/greenwash/model/index.ts';
import { EMPTY_PARTS } from '../../../entities/greenwash/model/index.ts';
import { validateNewCheck } from './form.ts';

const doc = (pageCount: number, hasText = true) => ({ pageCount, hasText });

describe('validateNewCheck', () => {
  it('파일 없음', () => {
    expect(
      validateNewCheck({ uploaded: null, parts: EMPTY_PARTS, partErrors: {} }),
    ).toEqual([{ code: 'no_file' }]);
  });

  it('글자 없는 PDF', () => {
    expect(
      validateNewCheck({
        uploaded: doc(24, false),
        parts: { ...EMPTY_PARTS, ceo: [1] },
        partErrors: {},
      }),
    ).toEqual([{ code: 'no_text' }]);
  });

  it('300쪽 초과(300 은 된다)', () => {
    expect(MAX_PAGE_COUNT).toBe(300);
    expect(
      validateNewCheck({
        uploaded: doc(320),
        parts: { ...EMPTY_PARTS, ceo: [1] },
        partErrors: {},
      }),
    ).toEqual([{ code: 'too_many_pages', pageCount: 320, max: 300 }]);
    expect(
      validateNewCheck({
        uploaded: doc(300),
        parts: { ...EMPTY_PARTS, ceo: [1] },
        partErrors: {},
      }),
    ).toEqual([]);
  });

  it('쪽 범위 오류는 파트마다 낸다', () => {
    const over = parsePageRange('150', 139);
    const error = over.ok ? null : over.error;
    expect(
      validateNewCheck({
        uploaded: doc(139),
        parts: { ...EMPTY_PARTS, ceo: [4, 5] },
        partErrors: { ceo: null, climate: error },
      }),
    ).toEqual([{ code: 'page_range', part: 'climate', error }]);
  });

  it('세 파트가 모두 비었음', () => {
    expect(
      validateNewCheck({
        uploaded: doc(60),
        parts: EMPTY_PARTS,
        partErrors: {},
      }),
    ).toEqual([{ code: 'no_parts' }]);
  });

  it('다 맞으면 사유 없음', () => {
    expect(
      validateNewCheck({
        uploaded: doc(60),
        parts: { ...EMPTY_PARTS, climate: [3, 4] },
        partErrors: { climate: null },
      }),
    ).toEqual([]);
  });
});
