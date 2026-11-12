// Scope 3 「그 해의 지금 결과」의 꼴(밴드 S3W3a ① — 서버 GET /inventory/scope3/years/{year}·…/runs/{id}/edits·history).
// 서버는 수정·제외를 결과 본문에 덮지 않고 사건으로 쥔다(sid:MARC-ENT-570). 글자 칸은 서버 글자 그대로 — 수로 바꾸는 곳은 parseNumber 하나.
// id 는 글자다(실행 id 도 — /runs 의 수 id 와 다르다, 나갈 때만 api 가 수로 바꾼다).
// 합이 둘이다: 카드는 서버 합(Decimal, currentCards), 상세 표는 덧씌운 줄(overlayResult → sumOf float). 같다는 뜻은 표기가 같음이다(글자·=== 대조 금지).
import { CATEGORIES } from './category.ts';
import type { CategoryId } from './category.ts';
import { parseNumber } from './number.ts';
import { BIOGENIC_CARDS, sumOf } from './result.ts';
import type {
  ResultCard,
  ResultRow,
  ResultSheet,
  Scope3Done,
} from './result.ts';
import type { RunStatus } from './run.ts';

/** 계수를 고른 갈래: applied = AI 원안으로 되돌림 · recommended = 추천 순위 · custom = 직접 입력. */
export const FACTOR_CHOICES = ['applied', 'recommended', 'custom'] as const;
export type FactorChoice = (typeof FACTOR_CHOICES)[number];

/** 사건 갈래(히스토리). */
export const EDIT_KINDS = ['exclude', 'restore', 'factor'] as const;
export type EditKind = (typeof EDIT_KINDS)[number];

export interface EditPerson {
  id: string;
  /** 지금 이름. 잠근 사람은 못 찾으면 빈 글자다. */
  name: string;
}

/** 사건 때 뜬 AI 원안. */
export interface RowFactorAi {
  title: string | null;
  value: string | null;
  source: string | null;
  co2e: string | null;
}

/** 줄의 지금 계수 상태. */
export interface RowFactor {
  choice: FactorChoice;
  rank: number | null;
  title: string | null;
  value: string | null;
  source: string | null;
  unit: string | null;
  co2e: string | null;
  biogenicCo2e: string | null;
  ai: RowFactorAi;
}

/** 사건이 있는 줄의 지금 상태. factor 는 계수 사건이 없으면 null. */
export interface RowEdit {
  rowId: string;
  category: CategoryId;
  excluded: boolean;
  factor: RowFactor | null;
  editedAt: string;
  editedBy: EditPerson | null;
}

/** 그 실행의 사건 덧판. 다른 실행에는 붙지 않는다(sid:MARC-ENT-570). */
export interface RunEdits {
  runId: string;
  rows: RowEdit[];
}

export interface EditHistoryLine {
  id: string;
  rowId: string;
  category: CategoryId;
  kind: EditKind;
  reason: string;
  at: string;
  by: EditPerson | null;
  batchId: string | null;
  factor: RowFactor | null;
}

export interface EditHistoryPage {
  count: number;
  totalPages: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrevious: boolean;
  lines: EditHistoryLine[];
}

/** 카테고리의 지금 결과. total 은 서버 합 글자(제외 뺌·고친 값 듦). */
export interface YearCurrent {
  runId: string;
  total: string | null;
  sheets: number;
  failedSheets: number;
}

export interface YearCategory {
  category: CategoryId;
  /** 그 해 기준 실행이 없고 안 잠겼으면 null. */
  current: YearCurrent | null;
  locked: boolean;
  lockedAt: string | null;
  lockedBy: EditPerson | null;
  editedRows: number;
}

export interface Scope3Year {
  year: number;
  baseRunId: string | null;
  /** 파서만 잡는다 — 화면은 아직 쓰지 않는다. */
  latest: { runId: string; status: RunStatus } | null;
  categories: YearCategory[];
  /** 다시 올리면 사라지는 고친 행 수(sid:MARC-ENT-570 경고). */
  editedRowsUnlocked: number;
}

/** 쓰기 답. category 로 화면을 덮지 않는다 — 새 실행이 동시에 기준이 되면 옛 값이다(S3K2b-1 리뷰 L3). */
export interface RowEditResult {
  category: YearCategory;
  rows: RowEdit[];
}

/** 계수 고르기 입력 — 갈래 유니온. 어댑터가 서버 몸 다섯 키로 편다. */
export type RowFactorInput = { rowId: string; reason: string } & (
  | { choice: 'applied' }
  | { choice: 'recommended'; rank: number }
  | {
      choice: 'custom';
      custom: { title: string; value: string; source: string };
    }
);

/** 줄 하나에 그 실행의 사건을 덧씌운다(서버 _line_value·co2e_of). applied 는 본문 그대로, rowId 없는 줄도 본문 그대로. */
function overlayRow(row: ResultRow, edit: RowEdit | undefined): ResultRow {
  if (edit === undefined) return row;
  const factor = edit.factor;
  const fixed = factor !== null && factor.choice !== 'applied';
  return {
    ...row,
    ...(edit.excluded ? { excluded: true } : {}),
    ...(factor !== null ? { factorEdit: factor } : {}),
    ...(fixed ?
      { co2e: factor.co2e, biogenic: factor.biogenicCo2e, edited: true }
    : {}),
  };
}

/**
 * 결과 본문 + 그 실행의 덧판 → 지금 줄(본문은 고치기 전 그대로라 화면이 덧씌운다). 짝은 rowId + 카테고리(서버 excluded_of·co2e_of).
 * edits 는 그 실행의 것만 넘긴다 — 다른 실행의 사건은 붙지 않는다(sid:MARC-ENT-570).
 */
export function overlayResult(done: Scope3Done, edits: RunEdits): Scope3Done {
  const found = new Map(
    edits.rows.map((row) => [`${row.category} ${row.rowId}`, row]),
  );
  const sheets = done.sheets.map((sheet): ResultSheet => {
    if (sheet.status !== 'processed') return sheet;
    const head = sheet.category.replace(/^Category/, 'C');
    return {
      ...sheet,
      rows: sheet.rows.map((row) =>
        row.rowId === null ?
          row
        : overlayRow(row, found.get(`${head} ${row.rowId}`)),
      ),
    };
  });
  return { ...done, sheets };
}

/** 지금 결과 실행들(서로 다른 값만, 처음 나온 차례). */
export function currentRunIds(year: Scope3Year): string[] {
  return [
    ...new Set(year.categories.flatMap((one) => one.current?.runId ?? [])),
  ];
}

/** 카드 한 장 + 그 카테고리의 연도 상태(C10 은 null). */
export interface CurrentCard extends ResultCard {
  state: YearCategory | null;
}

/**
 * 연도 상태 → 카드 15. total·sheets·failedSheets 는 서버 값 그대로(글자 → parseNumber 한 곳), 생물기원 합만 연도 상태에 칸이 없어
 * 그 카테고리 지금 결과 실행의 덧씌운 줄에서 센다. doneOf 는 덧씌운 결과를 준다.
 */
export function currentCards(
  year: Scope3Year,
  doneOf: (runId: string) => Scope3Done | undefined,
): CurrentCard[] {
  return CATEGORIES.map((category): CurrentCard => {
    const hasBiogenic = BIOGENIC_CARDS.includes(category.id);
    const state =
      year.categories.find((one) => one.category === category.id) ?? null;
    const current = state?.current ?? null;
    const base = {
      id: category.id,
      number: category.number,
      off: category.disabled,
      hasBiogenic,
      state,
    };
    if (category.disabled || current === null)
      return {
        ...base,
        total: null,
        biogenic: null,
        sheets: 0,
        failedSheets: 0,
      };
    const name = `Category${category.number}`;
    const rows = (doneOf(current.runId)?.sheets ?? []).flatMap((sheet) =>
      sheet.status === 'processed' && sheet.category === name ?
        sheet.rows.filter((row) => !row.excluded)
      : [],
    );
    return {
      ...base,
      total: parseNumber(current.total),
      biogenic: hasBiogenic ? sumOf(rows.map((row) => row.biogenic)) : null,
      sheets: current.sheets,
      failedSheets: current.failedSheets,
    };
  });
}

/** Scope 3 총합(서버 카테고리 합들의 합). 값이 하나도 없으면 null. ×÷ 0(sid:MARC-ENT-264). */
export const currentTotal = (year: Scope3Year): number | null =>
  sumOf(year.categories.map((one) => one.current?.total ?? null));

/** 지금 결과의 실패 시트 수. */
export const currentFailedSheets = (year: Scope3Year): number =>
  year.categories.reduce(
    (sum, one) => sum + (one.current?.failedSheets ?? 0),
    0,
  );
