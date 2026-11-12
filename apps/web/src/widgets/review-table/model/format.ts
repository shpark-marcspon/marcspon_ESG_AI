// 배출량의 표기. 단위 글자와 자리수는 여기 한 곳에서만 정한다(sid:MARC-ENT-272). 화면(ui/format.ts)과 띄워 보는 화면의 열(pages/demo-table/columns.tsx)이 가져다 쓴다.
// 값은 받은 그대로 두고 반올림은 글자로 적을 때만 한다. 표기가 바뀌면 이 파일만 고친다.
// 화면 없는 표면(model/index.ts)에 둔다: Intl 은 패키지도 DOM 도 아니라 node 에서도 돈다.

/**
 * 배출량의 단위 글자. 백엔드 Scope 3 결과의 단위 칸(unit) 값 그대로다(model/unit.test.ts 가 백엔드 스키마와 맞춰 본다).
 * 검토 표 입력 맨 위의 unit 리터럴도 이 글자다(model/input.ts).
 */
export const EMISSION_UNIT = 'tCO2eq';

/** 소수 셋째 자리까지(1 kg 해상도). 끝의 0 은 뺀다(1.8). */
export const EMISSION_FRACTION_DIGITS = 3;

/** 이 자리수로 적으면 0 이 되는 0 아닌 값의 글자. 0 이 아닌데 「0」으로 보이지 않게 한다. */
export const EMISSION_BELOW_SHOWN = '<0.001';

const number = new Intl.NumberFormat('ko', {
  maximumFractionDigits: EMISSION_FRACTION_DIGITS,
});
const smallest = 10 ** -EMISSION_FRACTION_DIGITS / 2;

/**
 * 배출량 숫자만(단위 없이). 표의 숫자 칸이 쓴다.
 * 0 보다 크고 0.0005 미만은 「<0.001」. 음수 쪽도 같은 까닭으로 「>-0.001」(「-0」을 내지 않는다).
 */
export function formatEmissionNumber(value: number): string {
  if (value !== 0 && Math.abs(value) < smallest)
    return value > 0 ? EMISSION_BELOW_SHOWN : (
        `>-${EMISSION_BELOW_SHOWN.slice(1)}`
      );
  return number.format(value);
}
