// EDK 정량 데이터 읽기(밴드 DV2a ①). 올린 파일·붙여 넣은 글을 dataverify.input@1 의 data 꼴로 읽고 미리 읽기 줄의 수를 센다.
// 꼴의 정본: apps/api-py/esgapi/dataverify/contracts/shapes.py(EdkItem·DataverifyInput, strict). 받은 것은 고치지 않는다(Q2 — data 만).
//   - 맨 위 = 객체(테마 이름 → 항목 목록). 배열·글자·수는 shape.
//   - 항목 = 객체, 열쇠 열하나 전부(EDK_KEYS). 값은 글자·수·null(참/거짓 0 — 파이썬 strict 는 bool 을 int 로 받지 않는다).
//     values = 객체(연도 글자 → 같은 값 꼴). 모르는 열쇠는 받는다(담당자 등, 값은 아무 JSON).
//   - 어디든 짝 없는 서로게이트가 든 글자(열쇠 포함)는 shape: 서버가 utf-8 로 적지 못한다(sid:MARC-ISSUE-340).
//   - 유한하지 않은 수(1e400 같은 글자를 JSON.parse 가 Infinity 로 읽음)는 shape: 보내면 null 로 바뀐다.
// 미리 읽기의 셈은 서버 흐름의 _scope(dataverify/flows/colab_156.py:382-390) 그대로: 테마 「환경」만, 핵심데이터 === 'Y' 정확히,
//   연도 = 그 항목들의 values 열쇠(겹침 없이 정렬). 「환경」이 빈 목록이면 0항목(경고는 서버 몫).
// 서버 입력 꼴(밴드 DV5, sid:MARC-ISSUE-435): 맨 위가 {schemaVersion: "dataverify.input@1", company, data} 이면 data 를 위와 똑같이 읽고,
//   company 는 칸마다 따로 본다(shapes.py Company 와 같은 판별 — 꼴 밖인 칸만 빼고 나머지를 싣는다). company 가 없거나 객체가 아니면 싣지 않는다.
// 열쇠 글자는 글자 코드로 짓는다(화면 글 밖 코드에 한국어 글자 0 — 발주서 §4-6. \u 꼴은 prettier 가 글자로 되돌린다). 뜻은 줄 끝 주석.
import { INPUT_SHAPE } from './options.ts';
import type { Company } from './options.ts';

/** 글자 코드 → 글(열쇠 짓기). */
export const k = (...codes: number[]) => String.fromCodePoint(...codes);

/** 검증하는 테마(코랩 셀 3). */
export const THEME_ENV = k(0xd658, 0xacbd); // 환경
/** 핵심데이터 칸의 열쇠와 「핵심」 값. */
export const KEY_FLAG = k(0xd575, 0xc2ec, 0xb370, 0xc774, 0xd130); // 핵심데이터
export const KEY_FLAG_YES = 'Y';
/** 연도 → 값 칸. */
export const VALUES_KEY = 'values';
/** 항목의 열쇠 열하나(shapes.py EdkItem 차례). */
export const EDK_KEYS = [
  'ID',
  k(0xd14c, 0xb9c8), // 테마
  k(0xd56d, 0xbaa9), // 항목
  k(0xb300, 0xbd84, 0xb958), // 대분류
  k(0xc911, 0xbd84, 0xb958), // 중분류
  k(0xc18c, 0xbd84, 0xb958), // 소분류
  k(0xc785, 0xb825, 0x20, 0xbc29, 0xc2dd), // 입력 방식
  k(0xb2e8, 0xc704), // 단위
  VALUES_KEY,
  KEY_FLAG,
  k(0xba54, 0xbaa8), // 메모
] as const;

export type EdkValue = string | number | null;
export type EdkItem = { readonly [key: string]: unknown };
/** 테마 이름 → 항목 목록(받은 그대로). */
export type EdkData = { readonly [theme: string]: readonly EdkItem[] };

export interface EdkPreview {
  /** 테마 수·항목 수(모든 테마). */
  themes: number;
  items: number;
  /** 테마 「환경」의 항목 수·그 가운데 핵심데이터 'Y' 수. */
  envItems: number;
  envKeyItems: number;
  /** 「환경」 항목들의 values 연도(겹침 없이, 오름차순). */
  years: readonly string[];
}

export type EdkRead =
  | {
      ok: true;
      data: EdkData;
      preview: EdkPreview;
      /** 서버 입력 꼴에서 읽은 회사 칸(꼴에 맞는 칸만). 데이터만 든 꼴이면 없다. */
      company?: Partial<Company>;
    }
  | { ok: false; kind: 'not_json' | 'shape' };

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const LONE_SURROGATE =
  /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;

/** 짝 없는 서로게이트가 없는 글자인가(서버가 utf-8 로 적을 수 있는가). */
export const isWellFormed = (text: string) => !LONE_SURROGATE.test(text);

/** 값 안 어디에도 짝 없는 서로게이트·유한하지 않은 수가 없는가(열쇠 포함). */
function isSendable(value: unknown): boolean {
  if (typeof value === 'string') return isWellFormed(value);
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(isSendable);
  if (isObject(value))
    return Object.entries(value).every(
      ([key, inner]) => isWellFormed(key) && isSendable(inner),
    );
  return true;
}

const isEdkValue = (value: unknown): value is EdkValue =>
  value === null || typeof value === 'string' || typeof value === 'number';

function isEdkItem(value: unknown): value is EdkItem {
  if (!isObject(value)) return false;
  for (const key of EDK_KEYS) {
    if (!(key in value)) return false;
    if (key === VALUES_KEY) continue;
    if (!isEdkValue(value[key])) return false;
  }
  const values = value[VALUES_KEY];
  return isObject(values) && Object.values(values).every(isEdkValue);
}

/** 읽은 JSON 값이 data 꼴인가. */
export function isEdkData(value: unknown): value is EdkData {
  return (
    isObject(value) &&
    isSendable(value) &&
    Object.values(value).every(
      (items) => Array.isArray(items) && items.every(isEdkItem),
    )
  );
}

/** 미리 읽기 셈(서버 _scope 와 같은 규칙). */
export function previewOf(data: EdkData): EdkPreview {
  const all = Object.values(data);
  const env = Object.hasOwn(data, THEME_ENV) ? data[THEME_ENV]! : [];
  const years = new Set<string>();
  for (const item of env)
    for (const year of Object.keys(item[VALUES_KEY] as Json)) years.add(year);
  return {
    themes: all.length,
    items: all.reduce((sum, items) => sum + items.length, 0),
    envItems: env.length,
    envKeyItems: env.filter((item) => item[KEY_FLAG] === KEY_FLAG_YES).length,
    years: [...years].sort(),
  };
}

const isText = (value: unknown): value is string =>
  typeof value === 'string' && isWellFormed(value);
const YEAR = /^[0-9]{4}$/;

/** 회사 칸 넷을 칸마다 본다(꼴 밖인 칸은 뺀다). */
function companyFrom(value: Json): Partial<Company> {
  const company: Partial<Company> = {};
  if (isText(value.name)) company.name = value.name;
  if (isText(value.sasbIndustry)) company.sasbIndustry = value.sasbIndustry;
  const topics = value.materialTopics;
  if (Array.isArray(topics) && topics.every(isText))
    company.materialTopics = topics;
  const year = value.reportingYear;
  if (typeof year === 'string' && YEAR.test(year)) company.reportingYear = year;
  return company;
}

/** 글 → data(서버 입력 꼴이면 그 data 와 company). JSON 이 아니면 not_json, 꼴이 아니면 shape. */
export function readEdk(text: string): EdkRead {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return { ok: false, kind: 'not_json' };
  }
  if (isObject(value) && value.schemaVersion === INPUT_SHAPE) {
    const data = value.data;
    if (!isEdkData(data)) return { ok: false, kind: 'shape' };
    const preview = previewOf(data);
    return isObject(value.company) ?
        { ok: true, data, preview, company: companyFrom(value.company) }
      : { ok: true, data, preview };
  }
  if (!isEdkData(value)) return { ok: false, kind: 'shape' };
  return { ok: true, data: value, preview: previewOf(value) };
}
