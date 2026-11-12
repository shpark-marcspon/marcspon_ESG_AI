import { EMISSION_UNIT, formatEmissionNumber } from '../model/index.ts';

/** 배출량을 화면에 적는 꼴(숫자 + 단위). 없으면 줄표. 자리수·단위 글자는 model/format.ts 한 곳에서 정한다. */
export function formatEmission(value: number | null): string {
  return value === null ? '—' : (
      `${formatEmissionNumber(value)} ${EMISSION_UNIT}`
    );
}
