// S3-08 카드의 배출량 표기(밴드 S3W2a ① — 발주서 Q3). 자리수·단위 글자는 review-table model 한 곳(sid:MARC-ENT-272) — 사본을 두지 않는다.
// 화면 없는 표면(model/index.ts)만 들인다(index.ts 는 CSS·TanStack 이 따라온다). 문은 app/guards/layers.test.ts 가 pages/ghg-scope3 로 좁힌다.
import {
  EMISSION_UNIT,
  formatEmissionNumber,
} from '../../../widgets/review-table/model/index.ts';

export { EMISSION_UNIT };

/** 수 하나의 글자. 없으면 empty(「-」). */
export const emissionText = (value: number | null, empty: string): string =>
  value === null ? empty : formatEmissionNumber(value);
