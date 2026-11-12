// 옵션의 서버 크기 셈(밴드 TRP1 W3). 기대 수는 파이썬 json.dumps(…, ensure_ascii=False) 로 한 번 잰 값이다(시험은 파이썬을 부르지 않는다).
import { describe, expect, it } from 'vitest';

import { pyJson, pyJsonOctets } from './options.ts';

describe('pyJson — 파이썬 json.dumps(ensure_ascii=False) 꼴', () => {
  it('한글·escape·수가 섞인 값의 글과 바이트가 파이썬과 같다(214)', () => {
    const value = {
      company: {
        name: '가나다 주식회사',
        note: '줄\n바꿈\t탭 "따옴표" \\ /   \u0001',
      },
      pages: { start: 1, end: 12 },
      ratio: 0.1,
      big: 1e21,
      tiny: 0.00001,
      list: [1, '한', null, true],
    };
    expect(pyJson(value)).toBe(
      '{"company": {"name": "가나다 주식회사", "note": "줄\\n바꿈\\t탭 \\"따옴표\\" \\\\ /   \\u0001"}, "pages": {"start": 1, "end": 12}, "ratio": 0.1, "big": 1e+21, "tiny": 1e-05, "list": [1, "한", null, true]}',
    );
    expect(pyJsonOctets(value)).toBe(214);
  });

  it('구분자 공백만큼 JSON.stringify 보다 크다', () => {
    const value = { a: 1, b: [1, 2] };
    expect(pyJson(value)).toBe('{"a": 1, "b": [1, 2]}');
    expect(pyJsonOctets(value) - JSON.stringify(value).length).toBe(4);
  });

  it('값이 undefined 인 열쇠는 JSON.stringify 처럼 뺀다(null 로 세지 않는다)', () => {
    const value = { a: 1, gone: undefined, inner: { x: undefined, y: 'z' } };
    expect(pyJson(value)).toBe('{"a": 1, "inner": {"y": "z"}}');
    expect(JSON.parse(JSON.stringify(value))).toEqual({
      a: 1,
      inner: { y: 'z' },
    });
  });
});
