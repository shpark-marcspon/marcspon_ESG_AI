// 예시 요청 둘. 계약 타입으로 적어 둔 상수라, 요청의 칸이 바뀌면 typecheck 가 여기서 빨개진다.
// 열쇠(gwpSetId, fuel, sector …)는 docs/development.md 의 「손으로 따라가기」에 적힌 글자 그대로다. 서버에 「무엇을」 묻는가이지 값(계수·배출량)이 아니다.
// 지어낸 열쇠로는 떠 있는 서버에서 ok 가 나오지 않는다. 답의 값은 여기에 적지 않는다(서버가 준 대로 그린다).
import type { Schemas } from '../../shared/api/index.ts';

export const CALC_EXAMPLE: Schemas['CalcIn'] = {
  gwpSetId: 'kr-ets-decree-annex2',
  // 서버에서는 기본값이 있는 칸인데 생성된 타입은 필수로 낸다. 서버의 기본값을 그대로 적는다.
  groupBy: ['scope', 'sourceType'],
  rows: [
    {
      id: 'r1',
      orgUnit: 'site-1',
      period: '2025',
      sourceType: 'stationary_combustion',
      fuel: 'diesel',
      sector: 'manufacturing_construction',
      parameterTiers: { calorific: 2, co2: 2, nonCo2: 1, oxidation: 2 },
      amount: '1000',
      unit: 'L',
    },
  ],
};

export const SHORTLIST_EXAMPLE: Schemas['Scope3ShortlistIn'] = {
  row: { itemName: '노트북 구매', unit: '대' },
  category: 1,
  keywords: ['computer', 'laptop'],
};
