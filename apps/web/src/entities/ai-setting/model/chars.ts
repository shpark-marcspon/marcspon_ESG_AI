// AI 설정 글 셈(밴드 AD2W ③④ — 서버와 같은 셈, 감독 노트 sid:MARC-TICK-72 10-22). 순수 함수만 있다.
//   - 글 수 = 코드포인트(Python len — 4바이트 글자도 하나, UTF-16 길이가 아니다).
//   - 빈 글·칸 메모 = Python str.strip() 뒤(apps/api-py core/calc/ai_settings.py `_check_prompt_step`). 떼는 글자는 Python str.isspace() 가 참인 29자:
//       python3 -c "print([hex(c) for c in range(0x110000) if chr(c).isspace()])"
//     JS String.prototype.trim(·\s)과 다르다 — Python 만 U+001C~U+001F·U+0085 를 떼고, JS 만 U+FEFF 를 뗀다.
//   - 판 이름 = pydantic strip_whitespace 뒤(apps/api-py greenwash/service/apis/ai_settings.py `title`) — Unicode White_Space 25자.
//     Python strip 과 달리 U+001C~U+001F 는 남긴다(critic R1 실측, pydantic 2.13.5). 판 메모는 떼지 않는다(서버도 생 코드포인트).

/** Python str.isspace() 가 참인 글자 29개(★K 실측 — Python 3.15.0, 서버 3.13 과 White_Space 표 같음). 코드포인트로 적는다(보이지 않는 글자를 글로 두지 않음). */
const PY_SPACE = [
  0x9, 0xa, 0xb, 0xc, 0xd, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680,
  0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
  0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
].map((code) => String.fromCodePoint(code));
/** pydantic strip_whitespace 가 떼는 글자 25개(Python 공백에서 U+001C~U+001F 를 뺀 것). */
/** U+001C~U+001F(정보 구분 글자 넷 — Python 만 공백으로 친다). */
const isSeparator = (one: string) => {
  const code = one.codePointAt(0)!;
  return code >= 0x1c && code <= 0x1f;
};
const TITLE_SPACE = PY_SPACE.filter((one) => !isSeparator(one));

const stripWith = (spaces: readonly string[]) => (text: string) => {
  let start = 0;
  let end = text.length;
  while (start < end && spaces.includes(text[start]!)) start++;
  while (end > start && spaces.includes(text[end - 1]!)) end--;
  return text.slice(start, end);
};

/** 코드포인트 수(Python len). 짝 없는 서로게이트도 하나. */
export const codepoints = (text: string) => [...text].length;

/** Python str.strip()(인자 없음)과 같은 글. */
export const pyStrip = stripWith(PY_SPACE);

/** 판 이름의 서버 셈(pydantic strip_whitespace)과 같은 글. */
export const titleStrip = stripWith(TITLE_SPACE);

/** Python 셈으로 빈 글인가(strip 뒤 아무것도 없음 — 서버 ai_prompt_text_empty). */
export const isBlank = (text: string) => pyStrip(text) === '';
