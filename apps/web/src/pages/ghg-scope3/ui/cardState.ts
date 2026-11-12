// 카드 하나의 갈래(밴드 S3W2b ② — 발주서 Q3). 목록 카드(ResultView)와 상세 머리(CategoryDetail)가 같이 쓴다.
//   off(C10) · failed(실패 시트만 있고 계산된 시트 0 — 「계산 실패」) · empty(합 없음) · value.
//   partial: 계산된 시트와 실패 시트가 같이 있으면 합을 보이고 둘째 줄 「시트 n개 계산 실패」.
import type { ResultCard } from '../../../entities/ghg-scope3/model/index.ts';

export type CardKind = 'off' | 'failed' | 'empty' | 'value';

export function cardState(card: ResultCard): {
  kind: CardKind;
  partial: boolean;
} {
  if (card.off) return { kind: 'off', partial: false };
  if (card.failedSheets > 0 && card.sheets === 0)
    return { kind: 'failed', partial: false };
  return {
    kind: card.total === null ? 'empty' : 'value',
    partial: card.failedSheets > 0,
  };
}
