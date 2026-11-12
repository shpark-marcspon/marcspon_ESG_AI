// ★ 대역이다. 실제 배출량 계산이 아니다.
// 배출량 계산은 서버의 일(결정적 계산)이고, 검토 표는 계산 함수를 밖에서 받는다. 이 파일은 그 자리에 끼워 둔 대역이다.
// 하는 일: 고른 후보에 이미 붙어 온 계산 결과를 돌려준다. 카테고리를 고쳐도 값이 달라지지 않는다(진짜 계산은 달라질 수 있다).
// 받은 값(tCO2eq) 그대로 돌려준다. 다시 나누지 않는다 — 후보의 값은 이미 톤이다(두 번 나누면 1000배 작아진다).
import type { Calculate } from '../../widgets/review-table/index.ts';

export const standInCalculate: Calculate = ({ candidate }) =>
  candidate?.emission ?? null;

/**
 * 실패하는 대역. 행마다 처음 times 번의 계산을 거부하고, 그 뒤에는 inner 에 맡긴다(?calcFail=횟수).
 * 「계산하지 못했다」가 어떻게 보이는지, 다시 계산하면 풀리는지 볼 때 쓴다. 1 이면 첫 계산만 실패한다.
 * delayMs 를 주면 실패도 그만큼 늦게 온다(「재계산 대기 → 계산 실패」를 보려고).
 */
export function failingStandIn(
  times: number,
  inner: Calculate = standInCalculate,
  delayMs = 0,
): Calculate {
  const calls = new Map<string, number>();
  return (request) => {
    const count = (calls.get(request.row.id) ?? 0) + 1;
    calls.set(request.row.id, count);
    if (count > times) return inner(request);
    const failure = new Error('계산 대역이 일부러 실패했다');
    if (delayMs <= 0) return Promise.reject(failure);
    return new Promise((_resolve, reject) =>
      setTimeout(() => reject(failure), delayMs),
    );
  };
}

/** 답이 늦게 오는 대역. 「재계산 대기」가 화면에서 어떻게 보이는지 볼 때 쓴다(?calcDelay=밀리초). */
export function delayedStandIn(delayMs: number): Calculate {
  return (request) =>
    new Promise((resolve) =>
      setTimeout(
        () => resolve(standInCalculate(request) as number | null),
        delayMs,
      ),
    );
}
