// Scope 3 결과의 화면 꼴과 카드 셈(밴드 S3W2a ① — 발주서 §1-5·§1-6). 순수 함수 — 표기(자리수·단위)는 화면이 한다(sid:MARC-ENT-272). 수만 낸다.
// co2e 는 이미 tCO2eq 다. 나누거나 곱하지 않는다(sid:MARC-ENT-264). 합계 칸은 서버에 없어 웹이 더한다.
// 시트의 error·거절의 detail 은 파일 내용이 섞일 수 있어 이 꼴에 싣지 않는다(화면 0).
// 밴드 S3W2b ①: 줄은 상세 표가 쓰는 칸을 kind 별 판별 유니온(detail)으로 더 싣고, 시트는 이름(sheet)과 empty 를 갖는다.
//   카드는 실패 있음 하나 대신 시트 수 둘(계산된 시트·실패한 시트 — 발주서 Q3).
// 밴드 S3W2c ①: 줄은 템플릿 줄의 입력 칸(input — sid:MARC-ENT-539, openapi ColabRowInputJson)을 detail 밖에 싣는다(basic 줄도).
import { CATEGORIES } from './category.ts';
import type { CategoryId } from './category.ts';
import type { RowFactor } from './current.ts';
import { parseNumber } from './number.ts';

/** 줄 kind 열넷(openapi ColabRowJson·ColabActivityRowJson·ColabEnergyRowJson 의 kind). */
export const ACTIVITY_KINDS = [
  'transport_spend',
  'travel_spend',
  'waste',
  'transport_distance',
  'travel_distance',
  'commute',
] as const;
export type ActivityKind = (typeof ACTIVITY_KINDS)[number];
export const ENERGY_KINDS = [
  'fuel_energy',
  'leased_asset',
  'leased_out_asset',
  'product_use',
  'product_eol',
  'franchise',
  'investment',
] as const;
export type EnergyKind = (typeof ENERGY_KINDS)[number];
export const ROW_KINDS = [
  'purchase',
  ...ACTIVITY_KINDS,
  ...ENERGY_KINDS,
] as const;
export type RowKind = (typeof ROW_KINDS)[number];

/** 줄의 출처 갈래(estimate 면 화면이 「추정」을 단다 — 발주서 Q9). */
export type RowOrigin = 'rule' | 'ai' | 'estimate';

/**
 * 계수 칸(서버 글자 그대로). source 는 구매 줄이면 서버 코드(detail 의 sourceKind 가 갈래 값으로 바꾸고 글은 화면이 고른다),
 * 활동·에너지 줄이면 서버가 붙인 출처 글 factor.sourceText(책 머리 「출처:」·C3 줄 비고 — 밴드 S3Q1), 그 칸이 없으면 factor.sheet 글자다
 * (계수 책 시트 이름 — 고친 뒤의 출처와 같은 글자, S3W3c C5 ④).
 */
export interface FactorCells {
  title: string | null;
  value: string | null;
  unit: string | null;
  source: string | null;
}

/** 구매 줄의 추천 하나(서버 글자 그대로). 배열 자리가 곧 순위다(1부터 — 서버가 items[rank-1] 로 고른다). */
export interface RowRecommendation {
  title: string;
  value: string | null;
  expectedCo2e: string | null;
}

/** 활동량 칸(서버 글자 그대로 — 단위도 서버 글자). */
export interface AmountCells {
  value: string | null;
  unit: string | null;
  baseValue: string | null;
  baseUnit: string | null;
}

/** 거리 줄의 칸. km 는 셈에 쓴 편도 거리, roundTrip 은 왕복계수(곱하지 않는다 — 감독 C0 처분). */
export interface DistanceCells {
  km: string | null;
  roundTrip: string | null;
  people: string | null;
  trips: string | null;
  workdays: string | null;
}

export interface InvestmentCells {
  share: string | null;
  scope1: string | null;
  scope2: string | null;
}

/** C12 처리방법 셋(openapi C12Treatment — 서버 차례, 「기타」 없음). */
export const C12_TREATMENTS = ['매립', '소각', '재활용'] as const;
export type C12Treatment = (typeof C12_TREATMENTS)[number];
export const C12_BRANCHES = ['code', 'name', 'average'] as const;
export type C12Branch = (typeof C12_BRANCHES)[number];

/** C12 처리방법 하나(서버 글자 그대로 — share 는 0~1 글자, %는 model 셈). */
export interface C12TreatmentPart {
  treatment: C12Treatment;
  share: string | null;
  factor: string | null;
  used: boolean;
}

/**
 * C12 줄의 처리방법별 값(밴드 S3Q1 — openapi ColabC12TreatmentsJson). 보기만(수정은 2차, sid:MARC-ENT-579).
 * shareTotal 은 서버가 준 used 비중 합(웹이 셈하지 않는다), 가중 배출계수는 줄의 factor.value 다. code 는 줄의 factor.code(창 타이틀 둘째 줄).
 */
export interface C12Treatments {
  branch: C12Branch;
  shareTotal: string | null;
  parts: C12TreatmentPart[];
  code: string | null;
}

/**
 * 상세 표가 쓰는 줄 칸 — kind 별 판별 유니온. 모르는 kind·꼴 틀린 칸이면 basic(행·배출량만 — 화면 전체를 죽이지 않는다).
 * fcf 는 생물기원 칸의 화석탄소비율(0~1 글자 그대로 — %는 화면 셈).
 * hasBiogenic 은 줄에 생물기원 칸이 있는가(칸 값이 다 null 이어도 참), biogenicNote 는 그 칸의 note(서버 글자 그대로 — 밴드 S3W4 Q4).
 */
export type RowDetail =
  | { shape: 'basic' }
  | {
      shape: 'purchase';
      kind: 'purchase';
      groupName: string;
      /** originSteps 의 group 단계 origin(단계에 ai 가 하나라도 있으면 ai — 밴드 S3W4 Q3). 단계가 없으면 null. 줄 origin 은 계수 출처라 별을 가르지 못한다. */
      groupOrigin: RowOrigin | null;
      spendKrw: string | null;
      factor: FactorCells;
      /** 서버 차례 그대로. 값이 null 인 자리도 남긴다. 꼴이 틀리면 빈 배열. */
      recommendations: RowRecommendation[];
    }
  | {
      shape: 'activity';
      kind: ActivityKind;
      activity: AmountCells;
      factor: FactorCells;
      treatment: string | null;
      mode: string | null;
      distance: DistanceCells | null;
      fcf: string | null;
      hasBiogenic: boolean;
      biogenicNote: string | null;
    }
  | {
      shape: 'energy';
      kind: EnergyKind;
      activity: AmountCells;
      factor: FactorCells | null;
      buildingTotal: string | null;
      years: string | null;
      investment: InvestmentCells | null;
      fcf: string | null;
      hasBiogenic: boolean;
      biogenicNote: string | null;
      /** C12(product_eol)의 처리방법별 값(S3Q1). 옛 결과(칸 없음)·꼴 틀림·다른 kind 면 없음 — 창은 지금 표 그대로. */
      treatments?: C12Treatments | null;
    };

/**
 * 입력 칸 열여섯(openapi ColabRowInputJson 의 키 — 닫힘). 수 칸도 서버 글자 그대로(「13.0」 꼴 — 수 셈은 parseNumber 한 곳).
 * useMonths(S3R3 — C11 평균사용기간(개월))만 서버 꼴에서 NotRequired 다: S3R3 앞(키 열다섯)에 저장된 결과는 없으면 null 로 읽는다.
 */
export const INPUT_KEYS = [
  'country',
  'site',
  'name',
  'vehicle',
  'energy',
  'people',
  'buildingArea',
  'usedArea',
  'buildingPeople',
  'ownPeople',
  'productCount',
  'sales',
  'weight',
  'weightUnit',
  'stores',
  'useMonths',
] as const;
export type InputKey = (typeof INPUT_KEYS)[number];
/** 서버 꼴에서 빠져도 되는 입력 키(openapi ColabRowInputJson 의 required 밖 — 감독 처분 S3R3 Q3). */
export const OPTIONAL_INPUT_KEYS: readonly InputKey[] = ['useMonths'];
/** 줄의 입력 칸(값은 글이거나 null — 그 시트에 원천 열이 없거나 칸이 비면 null). */
export type RowInput = Record<InputKey, string | null>;

/** 줄 하나. co2e·biogenic 은 카드가 쓰는 칸(서버 글자 그대로), 나머지는 상세 표 칸. */
export interface ResultRow {
  /** 「시트!엑셀줄」(#n 이 붙을 수 있음). 꼴이 틀리면 null(화면 「-」). */
  rowId: string | null;
  co2e: string | null;
  biogenic: string | null;
  origin: RowOrigin | null;
  /** 서버 산식 글(코랩 「계산식」 — 빈 글일 수 있다, 수로 바꾸지 않는다). 글이 아니면 null(밴드 S3W4 ①). */
  formula: string | null;
  detail: RowDetail;
  /**
   * 입력 칸(S3W2c Q1). 옛 결과(칸 없음)·null·꼴 틀림이면 null — 상세 표의 입력 열은 빈 칸(다시 셈하지 않는다, sid:MARC-ENT-539).
   */
  input: RowInput | null;
  /** 지금 결과 덧씌움(S3W3a — overlayResult 만 채운다): 산정에서 빠진 줄. 합에서 빠지고 표에는 남는다. */
  excluded?: boolean;
  /** 지금 결과 덧씌움: co2e·biogenic 이 계수 사건의 값인 줄(applied 는 안 든다). */
  edited?: boolean;
  /** 지금 결과 덧씌움: 그 줄의 계수 사건(applied 도 — 지금 고름을 읽는 자리). 표 칸이 고친 값을 보는 것은 edited 줄뿐이다. */
  factorEdit?: RowFactor;
}

/** 시트 갈래 중 화면이 가르는 것. not_target·not_yet_supported·모르는 갈래는 other(합·상세에 넣지 않는다). */
export type ResultSheet =
  | { status: 'processed'; sheet: string; category: string; rows: ResultRow[] }
  | { status: 'failed'; sheet: string; category: string }
  | { status: 'empty'; sheet: string; category: string }
  | { status: 'other' };

export interface Scope3Done {
  status: 'done';
  sheets: ResultSheet[];
  /** 프롬프트 id → 갈래(success·failed:<kind> …) → 부른 수. */
  llmCalls: Record<string, Record<string, number>>;
}

export const REJECT_REASONS = [
  'reader_problem',
  'factor_book',
  'legacy_template',
] as const;
export type RejectReason = (typeof REJECT_REASONS)[number];

export interface Scope3Rejected {
  status: 'rejected';
  reason: RejectReason;
}

export type Scope3Result = Scope3Done | Scope3Rejected;

export interface ResultCard {
  id: CategoryId;
  /** 1~15. */
  number: number;
  /** 1차에서 계산하지 않음(C10 — sid:MARC-ENT-315). */
  off: boolean;
  /** 줄 co2e 합(tCO2eq). 수가 하나도 없으면 null. */
  total: number | null;
  /** 생물기원 합을 보이는 카드인가(C5·C12). */
  hasBiogenic: boolean;
  /** 생물기원 합(tCO2eq). 수가 하나도 없으면 null. */
  biogenic: number | null;
  /** 이 카테고리의 계산된(processed) 시트 수. */
  sheets: number;
  /** 이 카테고리의 실패한 시트 수(일부 실패면 sheets > 0 — 발주서 Q3). */
  failedSheets: number;
}

export interface ResultSummary {
  cards: ResultCard[];
  /** 실패한 시트 수. */
  failedSheets: number;
  /** 실패한 AI 호출 수(failed: 로 시작하는 갈래 합). */
  failedLlmCalls: number;
}

/** 생물기원 합을 보이는 카테고리(엑셀 biogenicCategories 와 같다 — xlsxLabels.test.ts). */
export const BIOGENIC_CARDS: readonly CategoryId[] = ['C5', 'C12'];

/** 수 글자들의 합. 수가 하나도 없으면 null. */
export function sumOf(texts: readonly (string | null)[]): number | null {
  let total: number | null = null;
  for (const text of texts) {
    const value = parseNumber(text);
    if (value !== null) total = (total ?? 0) + value;
  }
  return total;
}

/** done 결과 → 카드 15·실패 수. 한 카테고리에 시트가 여럿이면 모두 더한다. */
export function summarize(done: Scope3Done): ResultSummary {
  const cards = CATEGORIES.map((category): ResultCard => {
    const name = `Category${category.number}`;
    const hasBiogenic = BIOGENIC_CARDS.includes(category.id);
    const base = {
      id: category.id,
      number: category.number,
      hasBiogenic,
    };
    if (category.disabled)
      return {
        ...base,
        off: true,
        total: null,
        biogenic: null,
        sheets: 0,
        failedSheets: 0,
      };
    const rows: ResultRow[] = [];
    let sheets = 0;
    let failedSheets = 0;
    for (const sheet of done.sheets) {
      if (sheet.status === 'other' || sheet.category !== name) continue;
      if (sheet.status === 'failed') failedSheets += 1;
      else if (sheet.status === 'processed') {
        sheets += 1;
        rows.push(...sheet.rows);
      }
    }
    return {
      ...base,
      off: false,
      total: sumOf(rows.map((row) => row.co2e)),
      biogenic: hasBiogenic ? sumOf(rows.map((row) => row.biogenic)) : null,
      sheets,
      failedSheets,
    };
  });
  let failedLlmCalls = 0;
  for (const counts of Object.values(done.llmCalls))
    for (const [via, count] of Object.entries(counts))
      if (via.startsWith('failed:')) failedLlmCalls += count;
  return {
    cards,
    failedSheets: done.sheets.filter((sheet) => sheet.status === 'failed')
      .length,
    failedLlmCalls,
  };
}
