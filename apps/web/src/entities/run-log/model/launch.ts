// 같이 시작·이어서 표시의 순수 함수(밴드 AD4P — AD-04 표·AD-04a 상세, 결정 MARC-ENT-405, 서버 LK1 다섯 칸). React·DOM·통신을 모른다.
//   - 같이 시작: launchSize·launchIndex·launchFirstRunId 셋이 다 수이고 launchSize 가 2 이상일 때만(e9 규칙). 1·null·어긋난 값은 표시 없음 — 실패로 보지 않는다.
//   - 이어서: resumedFromRunId 가 수면 그 값. 모듈을 가리지 않는다(감독 답 Q2).
import type { RunLogRow } from './run.ts';

type LaunchFields = Pick<
  RunLogRow,
  'launchFirstRunId' | 'launchIndex' | 'launchSize'
>;

/** 같이 시작 묶음의 자리(첫 실행 id · 몇째 · 모두 몇). */
export interface LaunchMark {
  first: number;
  index: number;
  size: number;
}

/** 같이 시작 표시(묶음이 둘 이상일 때만). 아니면 null. */
export function launchMark(row: LaunchFields): LaunchMark | null {
  const { launchFirstRunId: first, launchIndex: index, launchSize: size } = row;
  if (
    typeof first !== 'number' ||
    typeof index !== 'number' ||
    typeof size !== 'number' ||
    size < 2
  )
    return null;
  return { first, index, size };
}

/** 이어서 돌린 앞 실행 id. 없으면 null. */
export function resumedMark(
  row: Pick<RunLogRow, 'resumedFromRunId'>,
): number | null {
  return typeof row.resumedFromRunId === 'number' ? row.resumedFromRunId : null;
}
