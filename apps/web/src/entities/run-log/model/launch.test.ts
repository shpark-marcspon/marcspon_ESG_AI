// 같이 시작·이어서 표시의 순수 함수(밴드 AD4P — 결정 MARC-ENT-405, e9 규칙 「묶음 둘 이상만」).
import { describe, expect, it } from 'vitest';

import { launchMark, resumedMark } from './index.ts';

const fields = (
  launchFirstRunId: number | null,
  launchIndex: number | null,
  launchSize: number | null,
) => ({ launchFirstRunId, launchIndex, launchSize });

describe('launchMark', () => {
  it('size 3 · index 2 · first 101 → {101, 2, 3}', () => {
    expect(launchMark(fields(101, 2, 3))).toEqual({
      first: 101,
      index: 2,
      size: 3,
    });
  });
  it('size 2 → 표시(경계)', () => {
    expect(launchMark(fields(101, 1, 2))).toEqual({
      first: 101,
      index: 1,
      size: 2,
    });
  });
  it('size 1 → null(혼자 시작한 실행은 표시 없음)', () => {
    expect(launchMark(fields(101, 1, 1))).toBeNull();
  });
  it('size null → null', () => {
    expect(launchMark(fields(101, 1, null))).toBeNull();
  });
  it('size 2 인데 index null·first null → null(어긋난 값은 표시 없음)', () => {
    expect(launchMark(fields(101, null, 2))).toBeNull();
    expect(launchMark(fields(null, 1, 2))).toBeNull();
  });
  it('모두 null → null', () => {
    expect(launchMark(fields(null, null, null))).toBeNull();
  });
});

describe('resumedMark', () => {
  it('88 → 88', () => {
    expect(resumedMark({ resumedFromRunId: 88 })).toBe(88);
  });
  it('null → null', () => {
    expect(resumedMark({ resumedFromRunId: null })).toBeNull();
  });
});
