// Scope 3 상세 표(S3-09·S3-10)의 칸 글자(밴드 S3W2b ② — 발주서 §1-5 「수 표기」). 표기 상수는 이 파일 한 곳.
//   - 배출량·생물기원: emission.ts(review-table 표기 — sid:MARC-ENT-272). 단위는 머리에 EMISSION_UNIT. ×·÷ 0(sid:MARC-ENT-264).
//   - 비율: 소수 한 자리 고정 + %. FCF: 소수 한 자리까지·끝 0 뺌 + %(표·창 같음 — S3W4 재확인 3). 수는 model 이 낸 % 값(shareOf·fcfPercent).
//   - 계수: 소수 열 자리까지·끝 0 뺌·지수 없이 + 서버 단위 글자 그대로(ENT-272 밖, 값 파일 V9).
//   - 금액·수량·거리·인원 등: 묶음 쉼표·소수 넷째 자리까지·끝 0 뺌·지수 없이 + 서버 단위 글자(있으면, 값 파일 V9).
//   - 출처(raw — 서버 시트 이름)·수단 칸·창 산식은 웹이 글로 바꾼다(GX1 M-1·M-3·L-4·L-5 — 엔진 글은 그대로, sid:MARC-ENT-442).
// 머리 글은 config/text.ts(시트마다 다른 글은 시트별 글이 이긴다).
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  SORT_COLUMNS,
  parseNumber,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  CellValue,
  ColumnId,
  SheetLayout,
  WindowBase,
} from '../../../entities/ghg-scope3/model/index.ts';
import { EMISSION_UNIT, emissionText } from './emission.ts';

const words = S3_TEXT.detail;
const EMPTY = S3_TEXT.result.empty;
const SOURCE_BOOKS: Readonly<Record<string, string>> = words.sourceBooks;
const SOURCE_SHEETS: Readonly<Record<string, string>> = words.sourceSheets;
const MODES: Readonly<Record<string, string>> = words.modeLabels;

/** 서버 출처 글(시트 이름 — raw) → 화면 글(GX1 M-3·L-5). 표에 없는 글(직접 입력한 출처 등)은 그대로. */
export function rawSourceText(text: string): string {
  const sheet = text.trim();
  if (Object.hasOwn(SOURCE_SHEETS, sheet)) return SOURCE_SHEETS[sheet]!;
  if (sheet.startsWith(words.sourcePurchasePrefix)) return SOURCE_BOOKS.usepa!;
  return text;
}

/** 수단 칸: 서버 정규화 코드 → 이름표. 표에 없으면 「기타」(GX1 M-1 · 값 파일 ④ — 코드를 내지 않는다). */
const modeText = (value: string) =>
  Object.hasOwn(MODES, value) ? MODES[value]! : words.modeOther;

/** 산식 줄의 숫자 자취 앞머리(「= 9.1e+06 × …」 — 수·부호·nan·inf 로 시작하는 마디). */
const NUMBER_TRACE = /^[-+]?(?:\d|\.\d|nan\b|inf)/i;

/** 창 산식 글: 「=」 마디 중 숫자 자취가 시작되는 마디부터 뺀다(수식 글만 — GX1 L-4, Figma 29209:30726). */
export function formulaText(formula: string): string {
  const parts = formula.split(' = ');
  const cut = parts.findIndex(
    (part, index) => index > 0 && NUMBER_TRACE.test(part.trim()),
  );
  return (cut < 0 ? parts : parts.slice(0, cut)).join(' = ').trim();
}

const PERCENT = new Intl.NumberFormat('ko-KR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const FCF = new Intl.NumberFormat('ko-KR', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});
const FACTOR = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 10,
  useGrouping: true,
});
const AMOUNT = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 4,
  useGrouping: true,
});

/** 배출량 단위가 머리에 붙는 열. */
const EMISSION_COLUMNS: readonly ColumnId[] = ['co2e', 'biogenic'];

/** 머리 글: 시트별 글 → 공통 글. 배출량 열은 끝에 단위. */
export function headerOf(layout: SheetLayout, column: ColumnId): string {
  const bySheet: Partial<Record<ColumnId, string>> =
    layout === 'generic' ? {} : words.sheetColumns[layout];
  const name = bySheet[column] ?? words.columns[column];
  return EMISSION_COLUMNS.includes(column) ? `${name}(${EMISSION_UNIT})` : name;
}

/** 칸 하나의 글자. 값이 없으면 「-」. */
export function cellText(cell: CellValue, column: ColumnId): string {
  if (cell.type === 'text') {
    if (cell.text === null) return EMPTY;
    if (column === 'source')
      return cell.raw ?
          rawSourceText(cell.text)
        : (SOURCE_BOOKS[cell.text] ?? EMPTY);
    if (column === 'mode') return modeText(cell.text);
    return cell.text;
  }
  const { value, unit } = cell;
  if (value === null) return EMPTY;
  if (EMISSION_COLUMNS.includes(column)) return emissionText(value, EMPTY);
  if (column === 'share') return `${PERCENT.format(value)}%`;
  if (column === 'fcf') return `${FCF.format(value)}%`;
  const number = (column === 'factor' ? FACTOR : AMOUNT).format(value);
  return unit === null || unit === '' ? number : `${number} ${unit}`;
}

/** 창의 기준단위 글(구매 줄은 [Figma] 「원」, 그 밖은 서버 글자). 없으면 null. */
export const baseUnitText = (base: WindowBase) =>
  base.kind === 'won' ? words.factorWindow.won : base.unit;

/** 창의 FCF 글: 표 칸과 같은 표기. 없으면 「-」. 0 은 「0%」. */
export const fcfText = (percent: number | null) =>
  percent === null ? EMPTY : `${FCF.format(percent)}%`;

const SHARE = new Intl.NumberFormat('ko-KR', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});
/** C12 처리방법 비중(S3Q1 값 파일 ② — 소수 둘째 자리까지·끝 0 뺌 + %). 수는 model 이 낸 %. 없으면 「-」. */
export const treatmentShareText = (percent: number | null) =>
  percent === null ? EMPTY : `${SHARE.format(percent)}%`;

/** 계수 단위의 분모가 창 머리 「kg CO2e /기준단위」의 기준단위와 같은가. 구매 줄은 KRW = 원. */
function sameBase(unit: string, base: WindowBase) {
  if (!unit.startsWith('kgCO2')) return false;
  const denominator = unit.slice(unit.indexOf('/') + 1);
  return denominator === (base.kind === 'won' ? 'KRW' : base.unit);
}

/**
 * 창의 계수 칸: 머리가 단위를 말해 주면 수만. 분모가 머리와 다르면 서버 단위를 남긴다(C5 변환 실패 줄은 기준단위가 입력 단위 그대로·빈 글이다 — units.py convert_weight_to_kg 끝 줄).
 * 표 계수 칸은 cellText 그대로.
 */
export const windowFactorText = (cell: CellValue, base: WindowBase) =>
  cell.type === 'number' && cell.unit !== null && sameBase(cell.unit, base) ?
    cellText({ ...cell, unit: null }, 'factor')
  : cellText(cell, 'factor');

/** 직접입력 표 머리: 그 줄 계수 단위의 분모가 기준단위와 같으면 창 머리 그대로, 다르면 서버 단위 글자(단위 입력 칸이 없다 — S3W3c2). */
export const customFactorHead = (unit: string | null, base: WindowBase) =>
  unit !== null && !sameBase(unit, base) ?
    S3_TEXT.detail.factorEdit.columnFactorUnit(unit)
  : words.factorWindow.columnFactor(baseUnitText(base));

/** 계수 글자 → 창·히스토리 표기(값이 없으면 「-」). */
export const factorNumberText = (value: string | null) =>
  cellText({ type: 'number', value: parseNumber(value), unit: null }, 'factor');

/** 수 칸(오른쪽 맞춤·정렬). 행·글자·출처 칸은 왼쪽. */
export const isNumberColumn = (column: ColumnId) =>
  SORT_COLUMNS.includes(column);
