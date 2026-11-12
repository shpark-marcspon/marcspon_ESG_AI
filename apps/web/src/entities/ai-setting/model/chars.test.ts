// AI 설정 글 셈(밴드 AD2W ③④ — 서버와 같은 셈). 코드포인트·Python strip·판 이름 strip(pydantic) 의 차이를 줄마다 본다.
import { describe, expect, it } from 'vitest';

import { codepoints, isBlank, pyStrip, titleStrip } from './chars.ts';

/** python3 -c "print([hex(c) for c in range(0x110000) if chr(c).isspace()])" 의 답(★K 실측 — 29자). */
const PY_SPACES = [
  0x9, 0xa, 0xb, 0xc, 0xd, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680,
  0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
  0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
].map((code) => String.fromCodePoint(code));

/** U+FEFF(JS trim 만 공백으로 친다). 글로 두면 보이지 않아 코드포인트로. */
const BOM = String.fromCodePoint(0xfeff);

describe('codepoints — Python len', () => {
  it('4바이트 글자(이모지·한자 확장 B) 8000자 = 8000(UTF-16 길이 16000 이 아니다)', () => {
    const text = '😀𠀀'.repeat(4000);
    expect(text.length).toBe(16000);
    expect(codepoints(text)).toBe(8000);
  });

  it('짝 없는 서로게이트도 하나, 빈 글 0', () => {
    expect(codepoints('가\ud800나')).toBe(3);
    expect(codepoints('')).toBe(0);
  });
});

describe('pyStrip — Python str.strip()', () => {
  it('Python 공백 29자를 전부 앞뒤에서 뗀다(안쪽은 둔다)', () => {
    expect(PY_SPACES).toHaveLength(29);
    for (const space of PY_SPACES)
      expect(
        pyStrip(`${space}가${space}나${space}`),
        space.codePointAt(0)!.toString(16),
      ).toBe(`가${space}나`);
    expect(pyStrip(PY_SPACES.join(''))).toBe('');
  });

  it('JS trim 과 다른 자리: U+001C·U+0085 만 글이면 빈 글, U+FEFF 는 남긴다', () => {
    expect(pyStrip('\u001c')).toBe('');
    expect('\u001c'.trim()).toBe('\u001c');
    expect(pyStrip('\u0085가')).toBe('가');
    expect('\u0085가'.trim()).toBe('\u0085가');
    expect(pyStrip(`${BOM}가`)).toBe(`${BOM}가`);
    expect(`${BOM}가`.trim()).toBe('가');
  });
});

describe('titleStrip — 판 이름(pydantic strip_whitespace)', () => {
  it('Python 공백에서 U+001C~U+001F 넷만 남기고(25자) 뗀다', () => {
    for (const space of PY_SPACES) {
      const code = space.codePointAt(0)!;
      const kept = code >= 0x1c && code <= 0x1f;
      expect(titleStrip(`${space}가`), space.codePointAt(0)!.toString(16)).toBe(
        kept ? `${space}가` : '가',
      );
    }
  });

  it('「\\x1c + 40자」는 41자(서버 422 와 같은 셈), pyStrip 으로는 40자', () => {
    const title = `\u001c${'가'.repeat(40)}`;
    expect(codepoints(titleStrip(title))).toBe(41);
    expect(codepoints(pyStrip(title))).toBe(40);
  });
});

describe('isBlank — 서버 빈 글(Python strip 뒤 없음)', () => {
  it('\\x1c 만 글 = 빈 글(JS trim 이면 빈 글이 아님), U+FEFF 만 글은 빈 글이 아님', () => {
    expect(isBlank('\u001c')).toBe(true);
    expect(isBlank('\u001c\u0085 \n')).toBe(true);
    expect(isBlank('\ufeff')).toBe(false);
    expect(isBlank('가')).toBe(false);
    expect(isBlank('')).toBe(true);
  });
});
