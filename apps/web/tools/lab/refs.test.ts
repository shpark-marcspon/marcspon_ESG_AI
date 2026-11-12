import { describe, expect, it } from 'vitest';

import { parseRef, scanNumbers } from './refs.ts';

describe('parseRef', () => {
  it('표의 칸', () => {
    expect(parseRef('p59-t1:r3c1')).toEqual({
      ok: true,
      ref: {
        kind: 'cell',
        page: 59,
        tableId: 'p59-t1',
        row: 3,
        col: 1,
        nth: null,
      },
    });
  });
  it('칸 안의 n번째 숫자', () => {
    expect(parseRef('p41-t3:r7c3#n2')).toEqual({
      ok: true,
      ref: {
        kind: 'cell',
        page: 41,
        tableId: 'p41-t3',
        row: 7,
        col: 3,
        nth: 2,
      },
    });
  });
  it('문단의 n번째 숫자', () => {
    expect(parseRef('p2-b6#n1')).toEqual({
      ok: true,
      ref: { kind: 'block', page: 2, blockId: 'p2-b6', nth: 1 },
    });
  });
  it('잘못된 꼴은 오류로 돌려준다', () => {
    for (const bad of [
      '',
      'p2-b6',
      'p2-b6#n',
      'p59-t1',
      'p59-t1:r3',
      'p59-t1:c1r3',
      'x59-t1:r3c1',
      'p59-t1:r3c1#n2 ',
      'p2-b6#n0',
      'p59-t1:r3c1#n0',
      'p2-b6#n1#n2',
    ]) {
      const result = parseRef(bad);
      expect(result.ok, `"${bad}"`).toBe(false);
    }
  });
});

describe('scanNumbers', () => {
  it('천 단위 쉼표와 소수를 한 숫자로, 연도도 숫자로 센다', () => {
    expect(scanNumbers('2024년 배출량은 1,234.5톤, 비율 12%')).toEqual([
      { body: '2024', start: 0, end: 4 },
      { body: '1,234.5', start: 11, end: 18 },
      // 끝 자리는 숫자 뒤의 % 까지다(몸통 body 에는 넣지 않는다).
      { body: '12', start: 24, end: 27 },
    ]);
  });
  it('끝 자리: 뒤의 % 와 %p 는 넣고, 앞의 부호와 뒤의 단위 글자는 넣지 않는다', () => {
    const text = '-3.5%p 늘어 59,498명';
    expect(
      scanNumbers(text).map((token) => text.slice(token.start, token.end)),
    ).toEqual(['3.5%p', '59,498']);
  });
  it('숫자가 없으면 빈 목록', () => {
    expect(scanNumbers('없음')).toEqual([]);
  });
});
