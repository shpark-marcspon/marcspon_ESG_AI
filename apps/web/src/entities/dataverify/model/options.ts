// 실행 옵션 dataverify.options@1 짓기와 크기 셈(밴드 DV2a ①, 발주서 §1-3 · Q3 (가)).
// 서버는 options 전체를 파이썬 json.dumps(…, ensure_ascii=False) 의 기본 구분자(", "·": ")로 적은 UTF-8 바이트가
//   256KiB 를 넘으면 400 INVALID_OPTIONS 다(apps/api-py/esgapi/runs/service/actions/runs.py:253-256·:352-354,
//   core/flows/binding.py:50). JSON.stringify 길이는 구분자 공백만큼 적게 센다 — 그래서 여기서 파이썬 꼴로 다시 적어 잰다.
// 수는 서버가 받은 뒤 다시 적는 꼴: 웹이 보내는 글은 JSON.stringify 라 정수값(|n| < 1e21)은 정수 글자로 가서 파이썬 int 로 읽히고
//   그대로 적힌다(원문 1200.0 도 1200 — Q11). 그 밖(소수·1e21 이상)은 파이썬 float 로 읽혀 repr(float) 로 적힌다:
//   가장 짧은 자리(JS 와 같은 셈), 십진 지수가 -4 미만이거나 16 이상이면 지수꼴(지수 두 자리 이상 — 1e-05·1e+21), 아니면 소수꼴.
// 글자는 파이썬 escape 꼴: " \ 와 \b \f \n \r \t, 그 밖 0x20 아래는 \u00XX(바이트 수는 JSON.stringify 와 같다).
import type { EdkData } from './edk.ts';
import type { InputSource } from './source.ts';

/** 실행 옵션 UTF-8 바이트 상한(서버 DOCUMENTLESS_OPTIONS_MAX_OCTETS). */
export const OPTIONS_MAX_OCTETS = 256 * 1024;
/** 입력 꼴 id(shapes.py INPUT_SHAPE). */
export const INPUT_SHAPE = 'dataverify.input@1';

export interface Company {
  name: string;
  sasbIndustry: string;
  materialTopics: readonly string[];
  /** YYYY. */
  reportingYear: string;
}

export interface DataverifyInput {
  schemaVersion: typeof INPUT_SHAPE;
  company: Company;
  data: EdkData;
}

/** 입력 하나(schemaVersion 이 첫 열쇠 — 서버 꼴의 차례). data 는 받은 그대로. */
export function buildInput(company: Company, data: EdkData): DataverifyInput {
  return {
    schemaVersion: INPUT_SHAPE,
    company: {
      name: company.name,
      sasbIndustry: company.sasbIndustry,
      materialTopics: [...company.materialTopics],
      reportingYear: company.reportingYear,
    },
    data,
  };
}

/** POST /runs 의 options: {input} 이나 {input, source}(출처가 있을 때 — 밴드 DV2b, DV1f options_shapes.py:65). */
export const buildOptions = (input: DataverifyInput, source?: InputSource) =>
  source === undefined ? { input } : { input, source };

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
export function pyNumber(value: number): string {
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
export function pyString(text: string): string {
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
  // 값이 undefined 인 열쇠는 JSON.stringify 가 빼고 보내니 서버 셈에도 없다(DV2a 가지 리뷰 후속).
  return `{${Object.entries(value as Record<string, unknown>)
    .filter(([, inner]) => inner !== undefined)
    .map(([key, inner]) => `${pyString(key)}: ${pyJson(inner)}`)
    .join(', ')}}`;
}

/** 서버가 재는 옵션 크기(UTF-8 바이트). */
export const pyJsonOctets = (value: unknown) =>
  new TextEncoder().encode(pyJson(value)).length;

/** 상한을 넘는가(넘으면 보내지 않는다 — 서버와 같은 「>」). */
export const isTooLarge = (options: unknown) =>
  pyJsonOctets(options) > OPTIONS_MAX_OCTETS;
