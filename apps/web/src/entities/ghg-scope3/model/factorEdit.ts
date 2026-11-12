// Scope 3 줄 계수 수정의 셈(밴드 S3W3c2 ① — 발주서 1-5·1-6, 처분 C1·C8·C10·C11·C12). 순수 함수 — React·글·표기 0(갈래 값·서버 글자·수만).
//   값 규칙은 서버 check_factor_body 를 따른다: 십진 글자(부호·쉼표·지수·빈칸 거절) · 소수 10자리 안 · 유한 · 0 초과 · 제목·출처 걷고 1~200 코드 포인트.
//   수로 바꾸는 곳은 parseNumber 하나(그 밖 수 변환 0). 보내는 제목·출처는 걷고, 값은 입력 글자 그대로(서버가 repr(float) 로 저장 — 돌아온 글자와 다르다).
//   같은 고름(C10)은 연 때 얼린 줄 사진으로 판정한다. 값 검사보다 먼저 — 같으면 요청 0.
//   추천 순위는 서버 배열 자리 + 1 이다(C12 처분 — 값 null 을 거른 뒤 번호를 매기지 않는다).
import type { RowFactorInput } from './current.ts';
import { parseNumber } from './number.ts';
import type { ResultRow, RowRecommendation } from './result.ts';

/** 직접 입력 제목·출처 한도(서버 SCOPE3_FACTOR_TEXT_MAX). */
export const FACTOR_TEXT_MAX = 200;
/** 직접 입력 값의 소수 자리 한도(서버 VALUE_DECIMALS). */
export const FACTOR_DECIMALS = 10;
/** 추천 순위 끝(서버 FACTOR_RANK_LAST — 그 뒤 자리는 고를 수 없다). */
export const FACTOR_RANK_LAST = 4;

const DECIMAL = /^[0-9]+(?:\.([0-9]+))?$/;

export type FactorValueFault = 'required' | 'notPositive' | 'decimals';
export type FactorTextFault = 'required' | 'tooLong';

/** 값 칸 검사. 빈 칸(빈칸만 포함) → required · 꼴 틀림·0 이하·무한 → notPositive · 소수 11자리 이상 → decimals. */
export function factorValueFault(text: string): FactorValueFault | null {
  if (text.trim() === '') return 'required';
  const found = DECIMAL.exec(text);
  if (found === null) return 'notPositive';
  if ((found[1] ?? '').length > FACTOR_DECIMALS) return 'decimals';
  const value = parseNumber(text);
  return value === null || value <= 0 ? 'notPositive' : null;
}

/** 제목·출처 칸 검사 — 걷은 글의 코드 포인트 수(서버 len). */
export function factorTextFault(text: string): FactorTextFault | null {
  const trimmed = text.trim();
  if (trimmed === '') return 'required';
  return [...trimmed].length > FACTOR_TEXT_MAX ? 'tooLong' : null;
}

/** 직접 입력 칸 셋(입력 글자 그대로). */
export interface FactorCustomDraft {
  title: string;
  value: string;
  source: string;
}
export type FactorCustomField = keyof FactorCustomDraft;
/** 화면 차례(첫 틀린 칸에 초점). */
export const FACTOR_CUSTOM_FIELDS: readonly FactorCustomField[] = [
  'title',
  'value',
  'source',
];

export type FactorCustomFaults = Partial<
  Record<FactorCustomField, FactorValueFault | FactorTextFault>
>;

/** 직접 입력 셋의 문제(없으면 빈 객체). */
export function customFaults(draft: FactorCustomDraft): FactorCustomFaults {
  const faults: FactorCustomFaults = {};
  const title = factorTextFault(draft.title);
  const value = factorValueFault(draft.value);
  const source = factorTextFault(draft.source);
  if (title) faults.title = title;
  if (value) faults.value = value;
  if (source) faults.source = source;
  return faults;
}

/** 라디오 고름. */
export type FactorPick =
  | { choice: 'applied' }
  | { choice: 'recommended'; rank: number }
  | { choice: 'custom' };

/** 추천 하나를 고를 수 있는가: 값이 수이고 순위가 1~4(서버 _recommended·RANK_BAD). rank = 배열 자리 + 1. */
export const recommendable = (item: RowRecommendation, rank: number) =>
  rank >= 1 && rank <= FACTOR_RANK_LAST && parseNumber(item.value) !== null;

/** 그 줄의 추천(구매 줄만, 서버 차례). 그 밖 꼴은 빈 배열(C5·C12 추천 없음 — sid:MARC-ENT-560). */
export const recommendationsOf = (
  row: ResultRow,
): readonly RowRecommendation[] =>
  row.detail.shape === 'purchase' ? row.detail.recommendations : [];

/** 처음 라디오: 사건 없음·applied → 적용, recommended → 그 순위, custom → 직접입력(C1). */
export function initialPick(row: ResultRow): FactorPick {
  const now = row.factorEdit;
  if (now === undefined || now.choice === 'applied')
    return { choice: 'applied' };
  if (now.choice === 'recommended' && now.rank !== null)
    return { choice: 'recommended', rank: now.rank };
  if (now.choice === 'custom') return { choice: 'custom' };
  return { choice: 'applied' };
}

/** 지수 꼴 글자를 십진 글자로 편다(toFixed(10) 끝 0 걷음). 1e21 이상은 toFixed 가 지수를 내므로 그대로 둔다. 수가 아니면 받은 글자. */
export function decimalText(text: string | null): string {
  const value = parseNumber(text);
  if (value === null) return text ?? '';
  if (Math.abs(value) >= 1e21) return text ?? '';
  const fixed = value.toFixed(FACTOR_DECIMALS);
  return fixed.includes('.') ?
      fixed.replace(/0+$/, '').replace(/\.$/, '')
    : fixed;
}

/** 처음 직접 입력 칸: 지금 고름이 custom 이면 그 값(값은 십진 글자로), 아니면 빈 칸. */
export function initialCustom(row: ResultRow): FactorCustomDraft {
  const now = row.factorEdit;
  if (now === undefined || now.choice !== 'custom')
    return { title: '', value: '', source: '' };
  return {
    title: now.title ?? '',
    value: decimalText(now.value),
    source: now.source ?? '',
  };
}

/**
 * 같은 고름인가(C10 — 서버 same_choice 를 얼린 사진으로). 사건이 없으면 지금은 AI 원안이다.
 * custom 은 걷은 제목·출처와 parseNumber 값(서버는 repr(float) 끼리 — 같은 수면 같은 글자).
 */
export function sameFactorPick(
  row: ResultRow,
  pick: FactorPick,
  draft: FactorCustomDraft,
): boolean {
  const now = row.factorEdit;
  if (now === undefined || now.choice === 'applied')
    return pick.choice === 'applied';
  if (pick.choice === 'applied') return false;
  if (pick.choice === 'recommended')
    return now.choice === 'recommended' && now.rank === pick.rank;
  if (now.choice !== 'custom') return false;
  const value = parseNumber(draft.value);
  return (
    value !== null &&
    value === parseNumber(now.value) &&
    draft.title.trim() === now.title &&
    draft.source.trim() === now.source
  );
}

/** 보낼 입력. 제목·출처는 걷고 값은 입력 글자 그대로. */
export function factorInput(
  rowId: string,
  pick: FactorPick,
  draft: FactorCustomDraft,
  reason: string,
): RowFactorInput {
  if (pick.choice === 'recommended')
    return { rowId, reason, choice: 'recommended', rank: pick.rank };
  if (pick.choice === 'custom')
    return {
      rowId,
      reason,
      choice: 'custom',
      custom: {
        title: draft.title.trim(),
        value: draft.value,
        source: draft.source.trim(),
      },
    };
  return { rowId, reason, choice: 'applied' };
}

/**
 * [수정]을 막는 까닭(값 파일 ③ — 겹치면 하나만, 잠김 → C12 → 계수 없음 → 보낼 줄·실행 없음).
 * C12 는 줄 kind(서버와 같은 재료 — 시트 이름 아님). 계수 없음은 factor·unit 이 null 인 줄(서버 editable 이 늘 거짓 — C8).
 */
export type FactorBlock = 'locked' | 'c12' | 'noFactor' | 'noTarget';

export function factorBlock(
  row: ResultRow,
  { locked, seen }: { locked: boolean; seen: string | null },
): FactorBlock | null {
  if (locked) return 'locked';
  const { detail } = row;
  if (detail.shape !== 'basic' && detail.kind === 'product_eol') return 'c12';
  if (
    detail.shape === 'basic' ||
    detail.factor === null ||
    detail.factor.unit === null
  )
    return 'noFactor';
  if (row.rowId === null || seen === null) return 'noTarget';
  return null;
}

/** AI 원안만 남긴 줄(적용 칸 — C1: 칸은 AI 원안이고 라디오가 지금 고름을 말한다). */
export const aiRowOf = (row: ResultRow): ResultRow =>
  row.edited ? { ...row, edited: false } : row;
