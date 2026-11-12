// RP-03 끌어 옮기기 셈(밴드 RPW7 §1-C·§2 + critic 3). 지어낸 값만.
import { describe, expect, it } from 'vitest';

import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { dropOf, gapAt, lineAt, moveTo, restOf, wantOf } from './drop.ts';
import { isDirty, numbersOf, subtreeEnd } from './tree.ts';

const node = (
  key: string,
  parentKey: string | null,
  depth: number,
  requirement = '',
): OutlineNode => ({
  key,
  parentKey,
  depth,
  title: `가상 ${key}`,
  requirement,
});

/** 줄 11개: 1 · 1.1 · 1.1.1 · 1.1.2 · 1.1.2.1 · 1.2 · 2 · 2.1 · 2.2 · 2.3 · 3. */
const tree = () => [
  node('a', null, 1),
  node('b', 'a', 2),
  node('c', 'b', 3),
  node('d', 'b', 3, '가상 요구 d'),
  node('e', 'd', 4, '가상 요구 e'),
  node('f', 'a', 2),
  node('g', null, 1),
  node('h', 'g', 2),
  node('i', 'g', 2),
  node('j', 'g', 2),
  node('k', null, 1),
];
const keysOf = (nodes: readonly OutlineNode[]) => nodes.map((one) => one.key);
const IDX = {
  a: 0,
  b: 1,
  c: 2,
  d: 3,
  e: 4,
  f: 5,
  g: 6,
  h: 7,
  i: 8,
  j: 9,
  k: 10,
};

describe('dropOf — 틈의 단계 범위', () => {
  it('자식이 뒤따르는 틈은 단계가 그 자식과 앞 줄 + 1 사이로 묶인다', () => {
    // k 를 뺀 rest 에서 b 와 c 사이(gap 2): 다음 줄 c(3)가 앞 줄 b(2)의 자식 — 3 하나로 고정.
    for (const want of [1, 2, 3, 4])
      expect(dropOf(tree(), IDX.k, 2, want).depth).toBe(3);
  });

  it('맨 앞 틈 = 1 하나 · 끝 틈 = 1 ~ 앞 줄 + 1', () => {
    expect(dropOf(tree(), IDX.k, 0, 4).depth).toBe(1);
    const nodes = tree();
    const end = restOf(nodes, IDX.c).length; // 끝 앞 줄 k(1)
    expect(dropOf(nodes, IDX.c, end, 1).depth).toBe(1);
    expect(dropOf(nodes, IDX.c, end, 2).depth).toBe(2);
    expect(dropOf(nodes, IDX.c, end, 4).depth).toBe(2);
  });

  it('깊이 4 를 넘는 틈은 4 까지', () => {
    // e(4) 뒤, 다음 줄 f(2): 2 ~ 4.
    expect(dropOf(tree(), IDX.k, 5, 9).depth).toBe(4);
    expect(dropOf(tree(), IDX.k, 5, 1).depth).toBe(2);
  });

  it('제자리·같은 단계 = same · 제자리·다른 단계 = ok', () => {
    expect(dropOf(tree(), IDX.h, IDX.h, 2).verdict).toBe('same');
    expect(dropOf(tree(), IDX.i, IDX.i, 3)).toEqual({
      gap: IDX.i,
      depth: 3,
      verdict: 'ok',
    });
  });

  it('아래 단계까지 네 단계를 넘으면 tooDeep(묶음 높이를 센다)', () => {
    // d(3, 아래 1)를 c 아래로 — 제자리 틈, 단계 4 → 4 + 1 > 4.
    expect(dropOf(tree(), IDX.d, IDX.d, 4)).toEqual({
      gap: IDX.d,
      depth: 4,
      verdict: 'tooDeep',
    });
    // 같은 자리·아래 없는 c 는 같은 깊이 4 도 괜찮다 — 틈이 b(2) 뒤라 단계 3 까지.
    expect(dropOf(tree(), IDX.c, 2, 3).verdict).toBe('same');
  });
});

describe('wantOf — 잡은 자리 기준 상대값', () => {
  it('±16 = 한 단계 · +8 = 한 단계(반올림) · −8 = 그대로 · 0 = 그대로', () => {
    expect(wantOf(2, 16)).toBe(3);
    expect(wantOf(2, -16)).toBe(1);
    expect(wantOf(2, 8)).toBe(3);
    expect(wantOf(2, -8)).toBe(2);
    expect(wantOf(2, 0)).toBe(2);
    expect(wantOf(2, 7)).toBe(2);
  });
});

describe('moveTo', () => {
  it('판 예시 ⓐ 꼴 — 2.3 을 1.1.2.1 과 1.2 사이로, 오른쪽 16px → 1.1 아래 1.1.3', () => {
    const nodes = tree();
    const gap = keysOf(restOf(nodes, IDX.j)).indexOf('f');
    const drop = dropOf(nodes, IDX.j, gap, wantOf(2, 16));
    expect(drop).toEqual({ gap, depth: 3, verdict: 'ok' });
    const [next, at] = moveTo(nodes, IDX.j, drop);
    expect(next[at]).toMatchObject({ key: 'j', parentKey: 'b', depth: 3 });
    expect(numbersOf(next)[at]).toBe('1.1.3');
  });

  it('판 예시 ⓑ 꼴 — 1.1.2 를 제자리에서 오른쪽 16px → tooDeep · 놓아도 그대로', () => {
    const nodes = tree();
    const drop = dropOf(nodes, IDX.d, IDX.d, wantOf(3, 16));
    expect(drop.verdict).toBe('tooDeep');
    const [next, at] = moveTo(nodes, IDX.d, drop);
    expect(next).toEqual(nodes);
    expect(at).toBe(IDX.d);
  });

  it('묶음 째 — 아래 단계 깊이·parentKey·key·요구 함께', () => {
    const nodes = tree();
    const gap = restOf(nodes, IDX.d).length; // 맨 끝, k(1) 뒤
    const [next, at] = moveTo(nodes, IDX.d, { gap, depth: 2 });
    expect(keysOf(next).slice(at)).toEqual(['d', 'e']);
    expect(next[at]).toEqual({
      ...nodes[IDX.d],
      parentKey: 'k',
      depth: 2,
    });
    expect(next[at + 1]).toEqual({ ...nodes[IDX.e], depth: 3 });
  });

  it('맨 위 대제목으로 — parentKey null', () => {
    const [next, at] = moveTo(tree(), IDX.h, { gap: 0, depth: 1 });
    expect(at).toBe(0);
    expect(next[0]).toMatchObject({ key: 'h', parentKey: null, depth: 1 });
  });

  it('범위 밖 단계는 맞추지 않고 그대로(맞추는 것은 dropOf 뿐)', () => {
    const nodes = tree();
    // k 를 뺀 gap 2 는 단계 3 하나뿐 — 1 을 주면 그대로.
    const [next, at] = moveTo(nodes, IDX.k, { gap: 2, depth: 1 });
    expect(next).toEqual(nodes);
    expect(at).toBe(IDX.k);
  });

  it('불변식 — 모든 줄 × 모든 틈 × 단계 1~4', () => {
    const nodes = tree();
    const keys = [...keysOf(nodes)].sort();
    for (let index = 0; index < nodes.length; index += 1) {
      const rest = restOf(nodes, index);
      for (let gap = 0; gap <= rest.length; gap += 1)
        for (let depth = 1; depth <= 4; depth += 1) {
          const [next] = moveTo(nodes, index, { gap, depth });
          const label = `${nodes[index]!.key} gap ${gap} depth ${depth}`;
          // ① 첫 줄 단계 1
          expect(next[0]!.depth, label).toBe(1);
          next.forEach((one, at) => {
            // ⑤ parentKey = 앞으로 처음 만나는 depth−1 줄의 key(뿌리 null)
            let parent: string | null = null;
            for (let back = at - 1; back >= 0 && one.depth > 1; back -= 1)
              if (next[back]!.depth === one.depth - 1) {
                parent = next[back]!.key;
                break;
              }
            expect(one.parentKey, `${label} ⑤ ${one.key}`).toBe(parent);
            // ② 부모가 앞, depth = 부모 + 1 ≤ 4
            expect(one.depth, label).toBeLessThanOrEqual(4);
            if (one.parentKey !== null) {
              const up = next.findIndex((n) => n.key === one.parentKey);
              expect(up, label).toBeLessThan(at);
              expect(one.depth, label).toBe(next[up]!.depth + 1);
            }
          });
          // ③ key 집합 같음
          expect([...keysOf(next)].sort(), label).toEqual(keys);
          // ④ tooDeep 이면 입력과 같음
          const drop = dropOf(nodes, index, gap, depth);
          if (drop.verdict === 'tooDeep') expect(next, label).toEqual(nodes);
        }
    }
  });

  it('왕복 — 옮겼다 되돌리면 isDirty false · 제자리는 애초에 그대로', () => {
    const saved = tree();
    const gap = restOf(saved, IDX.j).length;
    const [moved, at] = moveTo(saved, IDX.j, { gap, depth: 2 });
    expect(isDirty(saved, moved)).toBe(true);
    const back = keysOf(restOf(moved, at)).indexOf('k');
    const [restored] = moveTo(moved, at, { gap: back, depth: 2 });
    expect(isDirty(saved, restored)).toBe(false);
    const [same] = moveTo(saved, IDX.h, { gap: IDX.h, depth: 2 });
    expect(isDirty(saved, same)).toBe(false);
  });
});

describe('gapAt · lineAt', () => {
  it('gapAt — 중심이 포인터보다 위인 줄 수(경계는 아래 줄로 세지 않음)', () => {
    const mids = [10, 30, 50];
    expect(gapAt(mids, 0)).toBe(0);
    expect(gapAt(mids, 10)).toBe(0);
    expect(gapAt(mids, 11)).toBe(1);
    expect(gapAt(mids, 50)).toBe(2);
    expect(gapAt(mids, 99)).toBe(3);
    expect(gapAt([], 5)).toBe(0);
  });

  it('lineAt — 끌리는 묶음 앞은 그대로 · 뒤는 묶음만큼 밀림 · 제자리는 끌리는 첫 줄 앞 · 끝', () => {
    const nodes = tree();
    const size = subtreeEnd(nodes, IDX.d) - IDX.d; // d·e 둘
    expect(lineAt(nodes, IDX.d, 1)).toBe(1);
    expect(lineAt(nodes, IDX.d, IDX.d)).toBe(IDX.d);
    expect(lineAt(nodes, IDX.d, IDX.d + 1)).toBe(IDX.d + 1 + size);
    expect(lineAt(nodes, IDX.d, restOf(nodes, IDX.d).length)).toBe(
      nodes.length,
    );
  });
});
