// S3-12 그룹별 배출계수 창의 칸 묶음(밴드 S3W4 ① — 발주서 §1-6 표·Q1·Q3~Q7). 순수 함수 — 글·표기 0(갈래 값·서버 글자·수만). 글은 pages 쪽이 고른다.
// 창의 자료는 이미 받은 결과의 줄이다(새 요청 0 — Q2). 추천은 파서가 들이지만 창은 아직 그리지 않는다(수정 칸은 뒤 밴드). FCF 는 읽기 전용 수다(sid:MARC-ENT-560 ①).
// C12 처리방법별 표(밴드 S3Q1 ② — S3-12c 보기만): 서버 treatments 의 줄을 그대로 옮긴다. 비중은 0~1 → % ×100 하나, 합계 줄은 서버가 준
//   shareTotal·줄 factor.value 그대로(웹이 셈하지 않는다). 칸이 없는 옛 결과·고친 줄은 null(지금 표).
import {
  SHEET_COLUMNS,
  cellOf,
  fcfPercent,
  fixedFactorOf,
  sourceKind,
} from './detail.ts';
import type { CellValue, ColumnId, SheetLayout, SourceCell } from './detail.ts';
import { parseNumber } from './number.ts';
import type { C12Treatment, C12Treatments, ResultRow } from './result.ts';

/** 창을 여는 칸의 차례(값 파일 ② — 표 열 차례가 아니다: C9-1 은 mode 가 앞 열이지만 inName). */
const OPENING_ORDER: readonly ColumnId[] = [
  'group',
  'inName',
  'inVehicle',
  'mode',
  'inEnergy',
];
/** 창이 없는 꼴. C15 는 inName 이 있어 차례만으로는 열리니 따로 막는다(보일 계수 칸이 없다). */
const NO_WINDOW: readonly SheetLayout[] = ['C15', 'generic'];

/** 그 꼴의 여는 칸. 없으면 null. leadColumn(제외 줄 앞 글)과 다른 함수다. */
export function openingColumn(layout: SheetLayout): ColumnId | null {
  if (NO_WINDOW.includes(layout)) return null;
  const columns = SHEET_COLUMNS[layout];
  return OPENING_ORDER.find((one) => columns.includes(one)) ?? null;
}

/** 그 칸이 창을 여는가. basic 줄은 창에 그릴 칸이 없고, 글이 빈 칸은 누를 글이 없다(C12 만 빼고 — 아래). */
export function opensFactorWindow(
  row: ResultRow,
  layout: SheetLayout,
  column: ColumnId,
): boolean {
  if (openingColumn(layout) !== column || row.detail.shape === 'basic')
    return false;
  // C12 만: 제품명이 빈 줄도 처리방법·계수가 있어 창에 그릴 것이 있다 — 누를 글은 화면이 「이름 없음」으로 채운다(S3Q2 · sid:MARC-ENT-599 · c3 11-11).
  if (layout === 'C12') return true;
  const cell = cellOf(row, column, null);
  return cell.type === 'text' && !!cell.text;
}

/** AI 가 만든 그룹인가(Q3 — group 단계가 ai 일 때만. 물러선 그룹 estimate·줄 origin 은 별이 아니다). */
export const isAiGroup = (row: ResultRow) =>
  row.detail.shape === 'purchase' && row.detail.groupOrigin === 'ai';

/** 기준단위: 구매 줄은 금액(글은 화면), 그 밖은 서버 글자(없으면 null). */
export type WindowBase =
  { kind: 'won' } | { kind: 'server'; unit: string | null };

export interface FactorWindow {
  aiGroup: boolean;
  base: WindowBase;
  /** 출처 칸: 구매 줄은 갈래 값(sourceKind), 그 밖과 고친 줄은 서버 글자(raw). */
  source: SourceCell;
  /** 서버 산식 글. 빈 글·없음·고친 줄은 null. */
  formula: string | null;
  /** 탄소기원 구분. 줄에 생물기원 칸이 없으면 null(섹션 없음 — Q4). fcf 는 %. */
  carbon: { fcf: number | null; note: string | null } | null;
  /** 배출계수 표의 줄. 계수가 없는 줄(에너지 factor null)은 null. value 는 상세 표 계수 칸과 같은 칸 값. */
  factor: { title: string | null; value: CellValue } | null;
  /** C12 처리방법별 표(S3Q1). 칸 없는 옛 결과·다른 kind·고친 줄은 null — 창은 위 factor 한 줄 표. */
  treatments: TreatmentTable | null;
}

/** 처리방법 한 줄. share 는 %(서버 0~1 × 100, 비중 없음 null), factor 는 처리방법 계수 칸 값(상세 표 계수 칸과 같은 꼴). */
export interface TreatmentLine {
  treatment: C12Treatment;
  share: number | null;
  factor: CellValue;
}

/**
 * 처리방법별 표(값 파일 ② — 5열 · 타이틀·출처는 첫 줄만). title 은 입력 제품명(빈 글은 null), code 는 서버 factor.code(Q8 — e6:
 * 제품명이 비면 코드 한 줄, 둘 다 없으면 「-」). total 은 합계 줄 — share 는 서버 shareTotal 의 %, factor 는 줄 가중 계수 칸.
 */
export interface TreatmentTable {
  title: string | null;
  code: string | null;
  lines: TreatmentLine[];
  total: { share: number | null; factor: CellValue };
}

const percentOf = (share: string | null) => {
  const value = parseNumber(share);
  return value === null ? null : value * 100;
};

function treatmentTable(
  treatments: C12Treatments,
  title: string | null,
  unit: string | null,
  weighted: CellValue,
): TreatmentTable {
  return {
    title,
    code: filled(treatments.code),
    lines: treatments.parts.map((part) => ({
      treatment: part.treatment,
      share: percentOf(part.share),
      factor: { type: 'number', value: parseNumber(part.factor), unit },
    })),
    total: { share: percentOf(treatments.shareTotal), factor: weighted },
  };
}

const filled = (text: string | null) => (text === '' ? null : text);

const rawSource = (text: string | null): SourceCell => ({
  type: 'text',
  text: filled(text),
  raw: true,
});

/** 줄 → 창 칸. basic 줄은 null. 고친 줄은 제목·값·출처가 한 벌로 사건 값이고, 산식은 옛 수가 박힌 글이라 뺀다(S3W3c C7). */
export function factorWindowOf(row: ResultRow): FactorWindow | null {
  const { detail } = row;
  if (detail.shape === 'basic') return null;
  const fixed = fixedFactorOf(row);
  const formula = fixed === null ? filled(row.formula) : null;
  const value = cellOf(row, 'factor', null);
  if (detail.shape === 'purchase')
    return {
      aiGroup: isAiGroup(row),
      base: { kind: 'won' },
      source:
        fixed === null ?
          { type: 'text', text: sourceKind(detail.factor.source) }
        : rawSource(fixed.source),
      formula,
      carbon: null,
      factor: { title: filled((fixed ?? detail.factor).title), value },
      treatments: null,
    };
  const { activity, factor } = detail;
  const treatment = detail.shape === 'activity' ? detail.treatment : null;
  return {
    aiGroup: false,
    base: {
      kind: 'server',
      unit: filled(activity.baseUnit ?? activity.unit),
    },
    source: rawSource((fixed ?? factor)?.source ?? null),
    formula,
    carbon:
      detail.hasBiogenic ?
        { fcf: fcfPercent(detail.fcf), note: filled(detail.biogenicNote) }
      : null,
    factor:
      fixed !== null ?
        { title: filled(fixed.title), value }
      : factor && { title: filled(factor.title) ?? treatment, value },
    treatments:
      (
        fixed === null &&
        detail.shape === 'energy' &&
        detail.treatments &&
        value.type === 'number'
      ) ?
        treatmentTable(
          detail.treatments,
          filled(row.input?.name ?? null),
          value.unit,
          value,
        )
      : null,
  };
}
