// 가치사슬 표 한 곳(밴드 IRW2 ② — 발주서 §1-3 「웹 한 함수」, Directive: 올리기·붙여 넣기 같은 규칙).
//   rowsFromServer(행) — POST /materiality/value-chain/read 의 ok 행(서버가 이미 머리·병합·물려받기·건너뜀·상한을 지났다)
//   rowsFromPaste(글) — 엑셀에서 복사한 글(탭·줄, Q13 따옴표 칸) → 서버 읽개와 같은 셈(apps/api-py/esgapi/materiality/tools/value_chain_xlsx.py
//     `_table`): 첫 줄이 열 이름 다섯이면 뗌 · 칸 수가 5 아닌 첫 줄(건너뛰기 전)의 칸 수 → columns · 밸류체인·이해관계자·활동이 다 빈 행
//     건너뜀(Q4 ④ — 칸이 다 공백뿐인 줄은 열 이름 줄을 떼기 전에 먼저 뗀다, IRW3) · 데이터 행 번호(건너뛴 행 안 셈) > 100 → too_many_rows · 글자 수 넘음 → too_long · 사업 부문이 빈 행만 바로 위 데이터 행의
//     사업 부문을, 사업 내용도 비었으면 그것도 물려받음(Q4 ③ — 감독 10-28 (나)).
//   두 길 다 밸류체인 글을 normalizeStage 로 서버 값(Q2)으로 바꾼다. 못 맞추면 행은 넣고 그 칸만 '' — 화면이 빨간 테두리와 표 위 글로 고르게 한다.
// 상한 여섯(글자 50·200·20·50·200 · 행 100)은 서버 읽개 MAX_CHARS·MAX_DATA_ROWS 와 같다(§4 가 두 곳을 grep 으로 견준다).
// 글자 수는 코드 포인트로 센다(서버 len() 과 같게 — 검증 2 m2). 무효 조건: 앞뒤 공백 떼기는 JS trim 이라 Python strip 과 조금 다르다
//   (U+FEFF 는 여기만, \x1c–\x1f·\x85 는 서버만 뗀다) — 그런 글자만 든 칸은 두 길에서 달리 셀 수 있다. 줄 끝은 \n · \r\n · \r 하나
//   (IRW3 — 옛 Mac 꼴), \u2028·\x85 는 줄 끝으로 보지 않는다.
// 다섯 칸이 다 빈 행(직접 입력의 빈 줄·[행 추가] 뒤 비운 줄)은 filledRows 가 뺀다 — input 짓기·밸류체인 검사가 같은 것을 본다(IRW3 Q2).
// 열 이름 다섯은 서버 HEADER 와 같은 글자 — 이 파일의 상수 한 곳(§4 한국어 줄 검사의 예외).
import { VALUE_CHAIN_STAGES, VALUE_CHAIN_STAGE_WORDS } from './wire.ts';
import type { ValueChainStage } from './wire.ts';

/** 열 이름 다섯(서버 HEADER 차례 — 사업 부문·사업 내용·밸류체인·이해관계자·관련 비즈니스 활동). */
export const VALUE_CHAIN_HEADER = [
  '사업 부문',
  '사업 내용',
  '밸류체인',
  '이해관계자',
  '관련 비즈니스 활동',
] as const;
/** 칸 글자 수(열 차례 — 서버 MAX_CHARS). */
export const VALUE_CHAIN_MAX_CHARS = [50, 200, 20, 50, 200] as const;
/** 데이터 행 상한(서버 MAX_DATA_ROWS). */
export const VALUE_CHAIN_MAX_ROWS = 100;

/** 열 열쇠(input@1 valueChain 원소의 열쇠 — 열 차례). */
export const VALUE_CHAIN_KEYS = [
  'business_unit',
  'business_unit_description',
  'value_chain_stage',
  'stakeholder',
  'business_activity',
] as const;
export type ValueChainKey = (typeof VALUE_CHAIN_KEYS)[number];

/** 표 한 행(밸류체인은 서버 값 셋 가운데 하나, 못 맞춘 칸은 ''). */
export interface ValueChainRow {
  business_unit: string;
  business_unit_description: string;
  value_chain_stage: ValueChainStage | '';
  stakeholder: string;
  business_activity: string;
}

/** 읽은 표 — 행은 1~100. */
export type ValueChainParsed =
  | { ok: true; rows: ValueChainRow[] }
  /** 붙여 넣은 표의 칸 수가 5가 아님(columns = 그 첫 줄의 칸 수). */
  | { ok: false; error: 'columns'; columns: number }
  /** 데이터 행이 100을 넘음(row = 101). */
  | { ok: false; error: 'too_many_rows'; row: number }
  /** 칸 글자 수 넘음(row = 데이터 행 번호, column = 0..4, max = 그 열의 상한). */
  | { ok: false; error: 'too_long'; row: number; column: number; max: number }
  /** 데이터 행이 없음(열 이름 줄뿐·다 빈 행). */
  | { ok: false; error: 'no_rows' };

/** 견줄 꼴 — 모든 공백 문자와 밑줄 `_`·붙임표 `-` 를 떼고 소문자(「자체 운영」·「Own  Operations」·「업 스트림」 — IRW3,
 *  「own_operations」·「own-operations」 — IRW15 ②). */
const stageKey = (text: string) => text.replace(/[\s_-]/g, '').toLowerCase();

/** 밸류체인 글 → 서버 값(공백·밑줄·붙임표·대소문자 무시 — 한국어 셋·코랩 영어 셋·단수 own operation). 못 맞추면 null. */
export function normalizeStage(text: string): ValueChainStage | null {
  const key = stageKey(text);
  if (key === '') return null;
  for (const stage of VALUE_CHAIN_STAGES)
    if (VALUE_CHAIN_STAGE_WORDS[stage].some((word) => stageKey(word) === key))
      return stage;
  return null;
}

/** 서버가 읽은 행(밸류체인은 파일 글 그대로) → 표 행. */
export function rowsFromServer(
  rows: readonly {
    business_unit: string;
    business_unit_description: string;
    value_chain_stage: string;
    stakeholder: string;
    business_activity: string;
  }[],
): ValueChainParsed {
  if (rows.length === 0) return { ok: false, error: 'no_rows' };
  if (rows.length > VALUE_CHAIN_MAX_ROWS)
    return { ok: false, error: 'too_many_rows', row: VALUE_CHAIN_MAX_ROWS + 1 };
  return {
    ok: true,
    rows: rows.map((row) => ({
      business_unit: row.business_unit,
      business_unit_description: row.business_unit_description,
      value_chain_stage: normalizeStage(row.value_chain_stage) ?? '',
      stakeholder: row.stakeholder,
      business_activity: row.business_activity,
    })),
  };
}

/** 줄 끝인가(\n, \r\n, \r) — 끝이면 그 길이, 아니면 0. */
function lineEnd(text: string, at: number): number {
  if (text[at] === '\n') return 1;
  if (text[at] === '\r') return text[at + 1] === '\n' ? 2 : 1;
  return 0;
}

/**
 * 따옴표 칸(Q13): at 이 「"」 이면 짝 따옴표까지 한 칸(`""` = `"`). 짝 따옴표 바로 뒤가 탭·줄 끝·글 끝이 아니거나 짝이 없으면 null
 * (그 칸은 따옴표째 글 그대로).
 */
function quotedCell(
  text: string,
  at: number,
): { value: string; next: number } | null {
  let value = '';
  let index = at + 1;
  while (index < text.length) {
    const char = text[index]!;
    if (char !== '"') {
      value += char;
      index += 1;
      continue;
    }
    if (text[index + 1] === '"') {
      value += '"';
      index += 2;
      continue;
    }
    const after = index + 1;
    if (after === text.length || text[after] === '\t' || lineEnd(text, after))
      return { value, next: after };
    return null;
  }
  return null;
}

/** 붙여 넣은 글 → 줄마다 칸(탭·줄, Q13 따옴표). 끝의 빈 줄은 뗀다. */
export function splitPaste(text: string): string[][] {
  const lines: string[][] = [];
  let cells: string[] = [];
  let index = 0;
  while (index <= text.length) {
    let value: string;
    const quoted = text[index] === '"' ? quotedCell(text, index) : null;
    if (quoted) {
      value = quoted.value;
      index = quoted.next;
    } else {
      let end = index;
      while (end < text.length && text[end] !== '\t' && !lineEnd(text, end))
        end += 1;
      value = text.slice(index, end);
      index = end;
    }
    cells.push(value);
    if (index >= text.length) {
      lines.push(cells);
      break;
    }
    if (text[index] === '\t') {
      index += 1;
      continue;
    }
    index += lineEnd(text, index);
    lines.push(cells);
    cells = [];
  }
  while (lines.length > 0) {
    const last = lines.at(-1)!;
    if (last.length === 1 && last[0] === '') lines.pop();
    else break;
  }
  return lines;
}

const isHeader = (cells: readonly string[]) =>
  cells.length === VALUE_CHAIN_HEADER.length &&
  cells.every((cell, index) => cell.trim() === VALUE_CHAIN_HEADER[index]);

/** 붙여 넣은 표 → 표 행(서버 읽개 `_table` 과 같은 셈 — 머리말). */
export function rowsFromPaste(text: string): ValueChainParsed {
  const lines = splitPaste(text).filter((cells) =>
    cells.some((cell) => cell.trim() !== ''),
  );
  if (lines.length > 0 && isHeader(lines[0]!)) lines.shift();
  const odd = lines.find((cells) => cells.length !== VALUE_CHAIN_HEADER.length);
  if (odd) return { ok: false, error: 'columns', columns: odd.length };
  const rows: ValueChainRow[] = [];
  for (const cells of lines) {
    if (cells.slice(2).every((cell) => cell.trim() === '')) continue;
    const row = rows.length + 1;
    if (row > VALUE_CHAIN_MAX_ROWS)
      return { ok: false, error: 'too_many_rows', row };
    const texts: string[] = [];
    for (const [column, cell] of cells.entries()) {
      const value = cell.trim();
      const max = VALUE_CHAIN_MAX_CHARS[column]!;
      if ([...value].length > max)
        return { ok: false, error: 'too_long', row, column, max };
      texts.push(value);
    }
    let [unit, description] = texts as [string, string];
    const above = rows.at(-1);
    if (above && unit === '') {
      unit = above.business_unit;
      description = description || above.business_unit_description;
    }
    rows.push({
      business_unit: unit,
      business_unit_description: description,
      value_chain_stage: normalizeStage(texts[2]!) ?? '',
      stakeholder: texts[3]!,
      business_activity: texts[4]!,
    });
  }
  return rows.length === 0 ?
      { ok: false, error: 'no_rows' }
    : { ok: true, rows };
}

/** 빈 행 하나([행 추가]). */
export const blankValueChainRow = (): ValueChainRow => ({
  business_unit: '',
  business_unit_description: '',
  value_chain_stage: '',
  stakeholder: '',
  business_activity: '',
});

/** 다섯 칸 가운데 하나라도 찬 행인가. */
const isFilled = (row: ValueChainRow) =>
  VALUE_CHAIN_KEYS.some((key) => row[key].trim() !== '');

/** 다섯 칸이 다 빈 행을 뺀 행(input 짓기·밸류체인 검사 — IRW3 Q2). */
export const filledRows = (rows: readonly ValueChainRow[]): ValueChainRow[] =>
  rows.filter(isFilled);

/** 밸류체인이 빈 행의 번호(다 빈 행은 뺌 · 번호는 화면 표의 「{n}행」 그대로 — 1부터). */
export const stagelessRows = (rows: readonly ValueChainRow[]): number[] =>
  rows.flatMap((row, index) =>
    isFilled(row) && row.value_chain_stage === '' ? [index + 1] : [],
  );

/** 사업 부문 서로 다른 값 수(빈 글 뺌 — 파일 칩 「사업 부문 m개」). */
export const businessUnitCount = (rows: readonly ValueChainRow[]): number =>
  new Set(rows.map((row) => row.business_unit).filter((unit) => unit !== ''))
    .size;
