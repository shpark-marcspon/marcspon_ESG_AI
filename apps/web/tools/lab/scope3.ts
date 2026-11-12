// 카테고리 분류·계수 추천 실측의 산출물 → 검토 표의 입력.
//
// 읽는 것(전부 git 밖. tools/convert-table.ts 가 경로를 정한다):
//   rows        실행 결과의 행: 품목명, 단위, 예측 카테고리, 추천 계수 id(0~3개), 계산 기준, 상태
//   factors     계수 표: 이름, 값, 단위, 출처
//   calls       (선택) 호출 기록. 후보별 매핑 이유와 신뢰도, 분류 이유가 여기에만 있다. 행 id 가 없어 품목명+단위로 잇는다
//   sourceRows  (선택) 실행에 넣었던 내역. 수량과 금액이 여기에만 있다
// ★ 실행 결과의 행에는 정답(gold)이 붙어 있다. 아래 스키마가 그 필드를 읽지 않으므로 표의 입력에 실리지 않는다.
// ★ 배출량은 자료 어디에도 없다. 여기서 「수량 × 계수」로 채우되 단위가 같을 때만 계산한다(kg ↔ t 만 바꾼다). 대역이다.
//   계수는 kgCO2e/단위라 곱은 kgCO2e 이고, 표의 입력은 tCO2eq 라 마지막에 한 번 ÷1000 한다(sid:MARC-ENT-264).
import { z } from 'zod';

import type { TableInputJson } from '../../src/widgets/review-table/model/index.ts';

export const labRowSchema = z.object({
  rowId: z.string(),
  itemName: z.string(),
  unit: z.string().nullable(),
  status: z.string(),
  predictedCategory: z.union([z.number(), z.string()]).nullable(),
  picks: z.array(z.string()),
  basis: z.object({ used: z.string() }).nullable(),
  calcStatus: z.string(),
});
export type LabRow = z.infer<typeof labRowSchema>;

export const labFactorSchema = z.object({
  id: z.string(),
  name: z.object({ original: z.string(), ko: z.string().nullable() }),
  value: z.number().nullable(),
  unit: z.string(),
  unit_denominator: z.string().nullable(),
  source: z.object({ name: z.string() }),
});
export type LabFactor = z.infer<typeof labFactorSchema>;

/** 호출 기록 한 줄에서 쓰는 부분. */
export const labCallSchema = z.object({
  promptId: z.string(),
  body: z.object({
    request: z.object({ user: z.array(z.object({ text: z.string() })) }),
    responseText: z.string().optional(),
  }),
});
export type LabCall = z.infer<typeof labCallSchema>;

export const labSourceRowSchema = z.object({
  row_id: z.string(),
  quantity: z.string().nullable().optional(),
  amount: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
});
export type LabSourceRow = z.infer<typeof labSourceRowSchema>;

const CATEGORY_LABEL: Record<string, string> = {
  '1': '1 구매한 제품과 서비스',
  '2': '2 자본재',
  '4': '4 업스트림 운송',
  '6': '6 출장',
  '7': '7 통근',
  '9': '9 다운스트림 운송',
  other: '기타',
};
const PROCESSING_LABEL: Record<string, string> = {
  recommended: '결과 생성',
  classification_failed: '분류 실패',
  unsupported_category: '대상 밖 카테고리',
  no_suitable_factor: '맞는 계수 없음',
  no_candidates: '후보 없음',
};
const BASIS_LABEL: Record<string, string> = {
  activity: '활동(물량)',
  spend: '금액',
  distance: '거리',
};

/** 호출 기록을 행에 잇는 열쇠. 실행이 품목명을 다듬어 보냈을 수 있어 빈칸과 대소문자를 무시한다. */
const joinKey = (itemName: string, unit: string | null) =>
  `${itemName.replace(/\s+/g, '').toLowerCase()}|${unit ?? ''}`;

interface Reasons {
  categoryNote?: string;
  picks: Map<
    string,
    { reason?: string; confidence?: 'high' | 'medium' | 'low' }
  >;
}

function reasonsByItem(calls: readonly LabCall[]): Map<string, Reasons> {
  const byItem = new Map<string, Reasons>();
  for (const call of calls) {
    const text = call.body.request.user.map((part) => part.text).join('\n');
    const item = /ITEM_JSON: (\{.*\})/.exec(text)?.[1];
    if (!item || !call.body.responseText) continue;
    let request: { item_name?: string; unit?: string | null };
    let answer: {
      reason?: string;
      picks?: { factor_id: string; reason?: string; confidence?: string }[];
    };
    try {
      request = JSON.parse(item);
      answer = JSON.parse(call.body.responseText);
    } catch {
      continue; // 잘린 응답 등
    }
    if (!request.item_name) continue;
    const key = joinKey(request.item_name, request.unit ?? null);
    const entry: Reasons = byItem.get(key) ?? { picks: new Map() };
    if (call.promptId.startsWith('scope3/classify') && answer.reason)
      entry.categoryNote = answer.reason;
    for (const pick of answer.picks ?? []) {
      const confidence =
        (
          pick.confidence === 'high' ||
          pick.confidence === 'medium' ||
          pick.confidence === 'low'
        ) ?
          pick.confidence
        : undefined;
      entry.picks.set(pick.factor_id, {
        ...(pick.reason ? { reason: pick.reason } : {}),
        ...(confidence ? { confidence } : {}),
      });
    }
    byItem.set(key, entry);
  }
  return byItem;
}

/**
 * 대역 계산: 수량 × 계수 ÷ 1000(tCO2eq). 행의 단위와 계수의 분모 단위가 같을 때만. kg 과 t(tonnes)만 서로 바꾼다. 그 밖에는 null.
 * kg 에서 0.1 로 자른 뒤 톤으로 나눈다 — 톤에서 소수 한 자리로 자르면 작은 값이 0 이 된다.
 */
export function standInEmission(
  quantity: number | null,
  unit: string | null,
  factor: LabFactor,
): number | null {
  if (
    quantity === null ||
    unit === null ||
    factor.value === null ||
    factor.unit_denominator === null
  )
    return null;
  const normal = (name: string) =>
    name.toLowerCase() === 'tonnes' || name.toLowerCase() === 'tonne' ?
      't'
    : name.toLowerCase();
  const from = normal(unit);
  const to = normal(factor.unit_denominator);
  const scale =
    from === to ? 1
    : from === 'kg' && to === 't' ? 0.001
    : from === 't' && to === 'kg' ? 1000
    : null;
  if (scale === null) return null;
  return Math.round(quantity * scale * factor.value * 10) / 10 / 1000;
}

export interface Scope3Result {
  input: TableInputJson;
  /** 세어 둔 것. 변환 스크립트가 찍는다. */
  counts: {
    rows: number;
    candidates: number;
    withReason: number;
    withEmission: number;
    unknownFactors: number;
    rowsWithQuantity: number;
  };
}

export function buildTableInput(
  rows: readonly LabRow[],
  factors: ReadonlyMap<string, LabFactor>,
  calls: readonly LabCall[] = [],
  sourceRows: readonly LabSourceRow[] = [],
): Scope3Result {
  const reasons = reasonsByItem(calls);
  const sources = new Map(sourceRows.map((row) => [row.row_id, row]));
  const counts = {
    rows: rows.length,
    candidates: 0,
    withReason: 0,
    withEmission: 0,
    unknownFactors: 0,
    rowsWithQuantity: 0,
  };
  const toNumber = (text: string | null | undefined) =>
    (
      text === null ||
      text === undefined ||
      text === '' ||
      Number.isNaN(Number(text))
    ) ?
      null
    : Number(text);

  const tableRows: TableInputJson['rows'] = rows.map((row) => {
    const source = sources.get(row.rowId);
    const quantity = toNumber(source?.quantity);
    if (quantity !== null) counts.rowsWithQuantity += 1;
    const found = reasons.get(joinKey(row.itemName, row.unit));

    const candidates = row.picks.flatMap((id) => {
      const factor = factors.get(id);
      if (!factor) {
        counts.unknownFactors += 1;
        return [];
      }
      const why = found?.picks.get(id);
      const emission = standInEmission(quantity, row.unit, factor);
      counts.candidates += 1;
      if (why?.reason) counts.withReason += 1;
      if (emission !== null) counts.withEmission += 1;
      return [
        {
          id,
          factorName: factor.name.ko ?? factor.name.original,
          factorValue: factor.value,
          factorUnit: factor.unit,
          source: factor.source.name,
          ...why,
          emission,
        },
      ];
    });

    return {
      id: row.rowId,
      raw: {
        itemName: row.itemName,
        quantity,
        unit: row.unit,
        amount: toNumber(source?.amount),
        currency: source?.currency ?? null,
        basis:
          row.basis ? (BASIS_LABEL[row.basis.used] ?? row.basis.used) : null,
        calcStatus: row.calcStatus,
      },
      processing: PROCESSING_LABEL[row.status] ?? row.status,
      ai: {
        category:
          row.predictedCategory === null ?
            null
          : (CATEGORY_LABEL[String(row.predictedCategory)] ??
            String(row.predictedCategory)),
        ...(found?.categoryNote ? { categoryNote: found.categoryNote } : {}),
        candidates,
      },
      review: { status: 'pending' as const },
    };
  });

  return {
    input: {
      version: 2,
      unit: 'tCO2eq',
      notice:
        `가상 내역 ${rows.length}행의 분류·추천 실행 결과다. 배출량(tCO2eq)은 대역 계산(수량 × 계수 ÷ 1000, 단위가 같을 때만)이고 실제 산정값이 아니다: ` +
        `후보 ${counts.candidates}개 중 ${counts.withEmission}개만 값이 있다. 매핑 이유·신뢰도는 호출 기록에서 이은 것이라 후보 ${counts.candidates}개 중 ${counts.withReason}개에만 있다.`,
      categories: Object.values(CATEGORY_LABEL),
      rows: tableRows,
    },
    counts,
  };
}
