// pipe 표 셈(밴드 TRW7 ① S1). 값은 전부 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import { pipeTableOf } from './pdfTable.ts';

describe('pipeTableOf', () => {
  it('머리 · 나눔 줄 · 몸 → 행·열', () => {
    expect(
      pipeTableOf(
        '| 구분 | 2025 |\n| --- | --- |\n| 배출량 | 1,200 |\n| 사용량 | 30 |',
      ),
    ).toEqual({
      head: ['구분', '2025'],
      rows: [
        ['배출량', '1,200'],
        ['사용량', '30'],
      ],
      cols: 2,
    });
  });

  it('정렬 표시(:---:)·앞뒤 빈 줄도 받는다', () => {
    expect(pipeTableOf('\n| a | b |\n|:---|---:|\n| 1 | 2 |\n')?.rows).toEqual([
      ['1', '2'],
    ]);
  });

  it('pipe 꼴이 아니면 null — 문단 · 나눔 줄 없음 · 한 줄 · 「|」로 끝나지 않는 줄', () => {
    expect(pipeTableOf('그냥 문단 글')).toBeNull();
    expect(pipeTableOf('| a | b |\n| 1 | 2 |')).toBeNull();
    expect(pipeTableOf('| a | b |')).toBeNull();
    expect(pipeTableOf('| a | b |\n| --- | --- |\n| 1 | 2')).toBeNull();
    // 검증 R1: 몸 안에 둘째 나눔 줄이 있으면 pipe 표 하나가 아니다.
    expect(
      pipeTableOf('| a | b |\n| --- | --- |\n| 1 | 2 |\n| --- | --- |'),
    ).toBeNull();
  });
});
