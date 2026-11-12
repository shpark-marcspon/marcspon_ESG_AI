// RP-03 끌어 옮기기 셈(밴드 RPW7 §1-C). 순수 함수 — React·화면을 모른다. 끌린 줄의 parentKey·depth, 아래 단계 depth, 차례만 바뀐다.
// 자기 아래로 놓기는 구조로 불가능하다: 묶음을 먼저 빼고(restOf) 남은 줄 사이 틈(gap)만 센다. gap = rest[gap] 바로 앞(끝이면 rest.length).
// 틈의 단계 범위: 아래는 다음 줄 단계 — 다음 줄이 앞 줄의 자식인 틈에 얕게 넣으면 자식이 부모와 떨어져 「하위는 바로 뒤」(tree.ts 머리)가 깨진다.
//   위는 앞 줄 단계 + 1(깊이 4 까지). 네 단계를 넘으면 자동으로 맞추지 않고 놓아도 그대로(판 v197 「제자리로 돌아가요」).
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { MAX_DEPTH, deepestUnder, subtreeEnd } from './tree.ts';

/** 들여쓰기 한 칸(px) — 끌기 가로 거리를 단계로 바꾸는 단위. */
const STEP_PX = 16;

export type DropVerdict = 'same' | 'tooDeep' | 'ok';

/** 놓일 자리. */
export interface Drop {
  gap: number;
  depth: number;
  verdict: DropVerdict;
}

/** 묶음(그 줄 + 아래 단계)을 뺀 나머지. */
export const restOf = (nodes: readonly OutlineNode[], index: number) => [
  ...nodes.slice(0, index),
  ...nodes.slice(subtreeEnd(nodes, index)),
];

/** 손잡이가 늘 줄 왼쪽 끝이라 잡은 자리 기준 상대값으로 잰다 — 오른쪽 16px = 한 단계 아래. */
export const wantOf = (depth: number, dx: number) =>
  depth + Math.round(dx / STEP_PX);

export function dropOf(
  nodes: readonly OutlineNode[],
  index: number,
  gap: number,
  want: number,
): Drop {
  const rest = restOf(nodes, index);
  const low = rest[gap]?.depth ?? 1;
  const high = Math.min(MAX_DEPTH, (rest[gap - 1]?.depth ?? 0) + 1);
  const depth = Math.min(Math.max(want, low), high);
  const node = nodes[index]!;
  const height = deepestUnder(nodes, index) - node.depth;
  const verdict: DropVerdict =
    gap === index && depth === node.depth ? 'same'
    : depth + height > MAX_DEPTH ? 'tooDeep'
    : 'ok';
  return { gap, depth, verdict };
}

/** 그 자리에 놓는다(하위와 함께). `ok` 가 아니면 그대로. [목록, 옮긴 자리]. */
export function moveTo(
  nodes: readonly OutlineNode[],
  index: number,
  { gap, depth: want }: Pick<Drop, 'gap' | 'depth'>,
): [OutlineNode[], number] {
  const { depth, verdict } = dropOf(nodes, index, gap, want);
  // 범위 밖 단계를 맞춰 주는 것은 dropOf 뿐이다 — 여기서는 받은 값이 그 틈에 맞을 때만 옮긴다.
  if (verdict !== 'ok' || depth !== want) return [[...nodes], index];
  const rest = restOf(nodes, index);
  let parent: string | null = null;
  if (depth > 1)
    for (let at = gap - 1; at >= 0; at -= 1)
      if (rest[at]!.depth === depth - 1) {
        parent = rest[at]!.key;
        break;
      }
  const by = depth - nodes[index]!.depth;
  const part = nodes
    .slice(index, subtreeEnd(nodes, index))
    .map((one) => ({ ...one, depth: one.depth + by }));
  part[0] = { ...part[0]!, parentKey: parent };
  return [[...rest.slice(0, gap), ...part, ...rest.slice(gap)], gap];
}

/** 남은 줄 중심 y 가운데 포인터보다 위인 수 = 틈. 끌리는 묶음 줄은 mids 에 넣지 않는다. */
export const gapAt = (mids: readonly number[], y: number) =>
  mids.filter((mid) => mid < y).length;

/** 틈을 전체 목록 자리로 — 선이 그 줄 바로 앞에 선다. 제자리 틈은 끌리는 첫 줄 앞(판 「놓을 수 없는 자리」 예시). */
export const lineAt = (
  nodes: readonly OutlineNode[],
  index: number,
  gap: number,
) => (gap <= index ? gap : gap + subtreeEnd(nodes, index) - index);
