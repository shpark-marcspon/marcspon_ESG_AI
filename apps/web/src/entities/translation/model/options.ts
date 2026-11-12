// 실행 옵션의 서버 크기 셈(밴드 TRP1 W3, sid:MARC-ISSUE-333 노트). 순수 함수만.
// dataverify/model/options.ts(밴드 DV2a ①)와 같은 셈을 베꼈다 — entities 끼리 가져오지 않는다(layers). 공통화는 후속.
// 서버는 options 전체를 파이썬 json.dumps(…, ensure_ascii=False) 의 기본 구분자(", "·": ")로 적은 UTF-8 바이트가
//   상한을 넘으면 400 이다(apps/api-py/esgapi/runs/service/actions/runs.py:253-256). JSON.stringify 길이는 구분자 공백만큼
//   적게 센다 — 그래서 여기서 파이썬 꼴로 다시 적어 잰다.
// 수는 서버가 받은 뒤 다시 적는 꼴: 정수값(|n| < 1e21)은 정수 글자, 그 밖(소수·1e21 이상)은 repr(float) —
//   가장 짧은 자리, 십진 지수가 -4 미만이거나 16 이상이면 지수꼴(지수 두 자리 이상 — 1e-05·1e+21), 아니면 소수꼴.
// 값이 undefined 인 열쇠는 JSON.stringify 처럼 뺀다(보내는 글에 없으니 서버도 세지 않는다 — 원본 pyJson 은 null 로 적음).
// 글자는 파이썬 escape 꼴: " \ 와 \b \f \n \r \t, 그 밖 0x20 아래는 \u00XX(/·U+2028 은 그대로 — JSON.stringify 와 같다).

/** 파이썬 repr(float) 꼴(유한한 수). */
function pyFloat(value: number): string {
  if (Object.is(value, -0)) return '-0.0';
  const sign = value < 0 ? '-' : '';
  const [mantissa, exp] = Math.abs(value).toExponential().split('e') as [
    string,
    string,
  ];
  const digits = mantissa.replace('.', '');
  const e = Number(exp);
  if (e < -4 || e >= 16) {
    const head =
      digits.length === 1 ? digits : `${digits[0]}.${digits.slice(1)}`;
    const power = String(Math.abs(e)).padStart(2, '0');
    return `${sign}${head}e${e < 0 ? '-' : '+'}${power}`;
  }
  if (e < 0) return `${sign}0.${'0'.repeat(-e - 1)}${digits}`;
  const whole = digits.slice(0, e + 1).padEnd(e + 1, '0');
  const fraction = digits.slice(e + 1);
  return `${sign}${whole}.${fraction === '' ? '0' : fraction}`;
}

/** 수가 서버에서 다시 적히는 꼴. */
function pyNumber(value: number): string {
  if (Number.isInteger(value) && Math.abs(value) < 1e21)
    return String(value === 0 ? 0 : value);
  return pyFloat(value);
}

const ESCAPES: Readonly<Record<string, string>> = {
  '"': '\\"',
  '\\': '\\\\',
  '\b': '\\b',
  '\f': '\\f',
  '\n': '\\n',
  '\r': '\\r',
  '\t': '\\t',
};

/** 파이썬 json 의 글자 꼴(ensure_ascii=False). */
function pyString(text: string): string {
  return `"${text.replace(
    // eslint-disable-next-line no-control-regex
    /["\\\u0000-\u001f]/g,
    (ch) =>
      ESCAPES[ch] ?? `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`,
  )}"`;
}

/** 파이썬 json.dumps(value, ensure_ascii=False) 의 글(기본 구분자). */
export function pyJson(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (value === true) return 'true';
  if (value === false) return 'false';
  if (typeof value === 'number') return pyNumber(value);
  if (typeof value === 'string') return pyString(value);
  if (Array.isArray(value)) return `[${value.map(pyJson).join(', ')}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .filter(([, inner]) => inner !== undefined) // JSON.stringify 처럼 뺀다(보내는 글에 없는 열쇠)
    .map(([key, inner]) => `${pyString(key)}: ${pyJson(inner)}`)
    .join(', ')}}`;
}

/** 서버가 재는 옵션 크기(UTF-8 바이트). */
export const pyJsonOctets = (value: unknown) =>
  new TextEncoder().encode(pyJson(value)).length;
