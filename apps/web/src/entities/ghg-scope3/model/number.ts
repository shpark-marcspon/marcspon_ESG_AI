// Scope 3 결과의 수 글자 → 수(밴드 S3W2a ① — 발주서 §1-5 표). 서버는 Decimal 이 아니라 float 의 repr 왕복 글자를 주고 지수 꼴(1e-05)도 온다.
// 표기(formatEmissionNumber)는 number 만 받으므로 글자를 수로 바꾸는 곳을 여기 한 곳으로 둔다. repr 왕복이라 값이 정확히 같다.

const NUMBER_TEXT = /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/;

/** 수 글자만 수로. 그 밖(null·빈 글자·nan·inf)은 null(화면 「-」). -0 은 0 으로 맞춘다(표기가 「-0」을 내지 않게). */
export function parseNumber(text: string | null): number | null {
  if (text === null || !NUMBER_TEXT.test(text)) return null;
  const value = Number(text);
  if (!Number.isFinite(value)) return null;
  return value === 0 ? 0 : value;
}
