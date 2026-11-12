// RP-03 목차 셈(밴드 RPW1 ② 시험 S4 몫 — 발주서 §2-2): 단추 일곱의 셈 · 깊이 4 · key 보존 · 서버 규칙(부모가 앞, depth = 부모 + 1) ·
//   번호 · 머리 셈 · 칸 검사(코드 포인트) · 고친 줄 · 422 fields → 줄.
import { describe, expect, it } from 'vitest';

import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import {
  addChild,
  addSibling,
  addTop,
  ancestorsOf,
  bodyOf,
  changedKeys,
  countsOf,
  descendantsOf,
  edit,
  fieldsOf,
  freshKey,
  indent,
  isDirty,
  moveDown,
  moveUp,
  movesOf,
  numbersOf,
  outdent,
  problemsOf,
  randomKey,
  removeAt,
} from './tree.ts';
import type { KeyMaker } from './tree.ts';

/** 시험용 key 짓기 — n1, n2, … 차례로(한 번 낸 값은 다시 내지 않는다). */
const counter = (): KeyMaker => {
  let n = 0;
  return () => `n${(n += 1)}`;
};

const node = (
  key: string,
  parentKey: string | null,
  depth: number,
  title = `지어낸 ${key}`,
): OutlineNode => ({ key, parentKey, depth, title, requirement: '' });

/** a(1) ─ b(2) ─ c(3) · d(2) · e(1) */
const tree = (): OutlineNode[] => [
  node('a', null, 1),
  node('b', 'a', 2),
  node('c', 'b', 3),
  node('d', 'a', 2),
  node('e', null, 1),
];

const shape = (nodes: readonly OutlineNode[]) =>
  nodes.map((one) => `${one.key}:${one.parentKey ?? '-'}:${one.depth}`);

/** 서버 규칙(wire.py) — 부모가 앞, 뿌리 depth 1, 자식 = 부모 + 1, 깊이 4 까지, key 하나씩. */
function valid(nodes: readonly OutlineNode[]): boolean {
  const depth = new Map<string, number>();
  for (const one of nodes) {
    if (depth.has(one.key) || one.depth > 4) return false;
    if (one.parentKey === null) {
      if (one.depth !== 1) return false;
    } else if (depth.get(one.parentKey) !== one.depth - 1) return false;
    depth.set(one.key, one.depth);
  }
  return true;
}

describe('RP-03 목차 셈 — 단추', () => {
  it('대제목 더하기 — 끝에 depth 1, 새 key 하나(짓는 함수가 낸 값 · 지금 목록과 겹치면 다시 짓기)', () => {
    const [next, at] = addTop(tree(), '새 목차', counter());
    expect(at).toBe(5);
    expect(next[5]).toEqual(node('n1', null, 1, '새 목차'));
    const make = counter();
    expect(freshKey([node('n1', null, 1), node('n3', null, 1)], make)).toBe(
      'n2',
    );
    expect(freshKey([node('n1', null, 1), node('n3', null, 1)], make)).toBe(
      'n4',
    );
    expect(valid(next)).toBe(true);
  });

  it('지운 key 는 다시 쓰지 않는다 — 지운 뒤 더한 마디는 새 key(서버 목차 바뀜이 key 로 견줌, 검증 R4)', () => {
    const make = counter();
    let [nodes] = addTop([], '가', make);
    [nodes] = addTop(nodes, '나', make);
    [nodes] = addChild(nodes, 0, '다', make);
    expect(nodes.map((one) => one.key)).toEqual(['n1', 'n3', 'n2']);
    const removed = removeAt(nodes, 1);
    const [again] = addTop(removed, '라', make);
    expect(again.map((one) => one.key)).toEqual(['n1', 'n2', 'n4']);
    const [child] = addChild(removeAt(again, 1), 0, '마', make);
    expect(child.map((one) => one.key)).toEqual(['n1', 'n5', 'n4']);
  });

  it('기본 key 짓기 — 서버 key 꼴(^[a-z0-9][a-z0-9-]{0,39}$) · 지운 key 를 다시 내지 않음 · 겹치지 않음', () => {
    const pattern = /^[a-z0-9][a-z0-9-]{0,39}$/;
    const keys = new Set<string>();
    for (let i = 0; i < 200; i += 1) {
      const key = randomKey();
      expect(key).toMatch(pattern);
      keys.add(key);
    }
    expect(keys.size).toBe(200);
    const [one] = addTop([], '가');
    const gone = one[0]!.key;
    const [next] = addTop(removeAt(one, 0), '나');
    expect(next[0]!.key).toMatch(pattern);
    expect(next[0]!.key).not.toBe(gone);
  });

  it('아래 단계 더하기 — 그 마디 하위 끝에 depth + 1 · 소소(4)에서는 끔·그대로', () => {
    const [next, at] = addChild(tree(), 0, '새 목차', counter());
    expect(shape(next)).toEqual([
      'a:-:1',
      'b:a:2',
      'c:b:3',
      'd:a:2',
      'n1:a:2',
      'e:-:1',
    ]);
    expect(at).toBe(4);
    const deep = [...tree().slice(0, 3), node('f', 'c', 4)];
    expect(movesOf(deep, 3).addChild).toBe(false);
    expect(addChild(deep, 3, '새 목차')[0]).toEqual(deep);
    expect(movesOf(deep, 2).addChild).toBe(true);
  });

  it('위로·아래로 — 같은 부모 안에서 하위와 함께, 끝에서는 끔', () => {
    const [down, at] = moveDown(tree(), 1);
    expect(shape(down)).toEqual(['a:-:1', 'd:a:2', 'b:a:2', 'c:b:3', 'e:-:1']);
    expect(at).toBe(2);
    const [up, back] = moveUp(down, 2);
    expect(shape(up)).toEqual(shape(tree()));
    expect(back).toBe(1);
    expect(movesOf(tree(), 1).up).toBe(false);
    expect(movesOf(tree(), 3).down).toBe(false);
    const [roots] = moveUp(tree(), 4);
    expect(shape(roots)).toEqual(['e:-:1', 'a:-:1', 'b:a:2', 'c:b:3', 'd:a:2']);
    expect(valid(roots)).toBe(true);
  });

  it('한 단계 올리기 — 부모의 다음 형제(부모 하위 끝 뒤), 하위 depth 함께 · 뿌리에서는 끔', () => {
    const [next, at] = outdent(tree(), 1);
    expect(shape(next)).toEqual(['a:-:1', 'd:a:2', 'b:-:1', 'c:b:2', 'e:-:1']);
    expect(at).toBe(2);
    expect(valid(next)).toBe(true);
    expect(movesOf(tree(), 0).outdent).toBe(false);
  });

  it('한 단계 내리기 — 바로 앞 형제의 마지막 자식, 깊이 4 를 넘으면 끔 · 앞 형제 없으면 끔', () => {
    const [next, at] = indent(tree(), 3);
    expect(shape(next)).toEqual(['a:-:1', 'b:a:2', 'c:b:3', 'd:b:3', 'e:-:1']);
    expect(at).toBe(3);
    expect(valid(next)).toBe(true);
    expect(movesOf(tree(), 1).indent).toBe(false);
    const deep = [
      node('a', null, 1),
      node('b', null, 1),
      node('c', 'b', 2),
      node('d', 'c', 3),
      node('f', 'd', 4),
    ];
    expect(movesOf(deep, 1).indent).toBe(false);
    expect(indent(deep, 1)[0]).toEqual(deep);
  });

  it('지우기 — 하위와 함께, 하위 수', () => {
    expect(descendantsOf(tree(), 0)).toBe(3);
    expect(shape(removeAt(tree(), 0))).toEqual(['e:-:1']);
    expect(shape(removeAt(tree(), 2))).toEqual([
      'a:-:1',
      'b:a:2',
      'd:a:2',
      'e:-:1',
    ]);
  });

  it('key 는 고쳐도 바뀌지 않는다 — 이름·요구·위치·단계 고침 뒤 key 집합 그대로', () => {
    let nodes = tree();
    nodes = edit(nodes, 1, { title: '지어낸 고친 이름', requirement: '요구' });
    nodes = moveDown(nodes, 1)[0];
    nodes = outdent(nodes, 2)[0];
    nodes = indent(nodes, 2)[0];
    expect(nodes.map((one) => one.key).sort()).toEqual([
      'a',
      'b',
      'c',
      'd',
      'e',
    ]);
    expect(nodes.find((one) => one.key === 'b')!.title).toBe(
      '지어낸 고친 이름',
    );
    expect(valid(nodes)).toBe(true);
  });
});

describe('RP-03 목차 셈 — 보기·검사', () => {
  it('번호 · 부모 제목 · 머리 셈(단계마다 + 잎)', () => {
    expect(numbersOf(tree())).toEqual(['1', '1.1', '1.1.1', '1.2', '2']);
    expect(ancestorsOf(tree(), 2)).toEqual(['지어낸 a', '지어낸 b']);
    expect(countsOf(tree())).toEqual({ depths: [2, 2, 1, 0], leaves: 3 });
  });

  it('칸 검사 — 제목 1~200(앞뒤 공백 걷고, 코드 포인트) · 요구 2,000 까지 · 빈 목차·잎 151 은 tooMany', () => {
    const nodes = [
      node('a', null, 1, '  '),
      node('b', null, 1, '😀'.repeat(200)),
      node('c', null, 1, '😀'.repeat(201)),
      { ...node('d', null, 1), requirement: '😀'.repeat(2000) },
      { ...node('e', null, 1), requirement: '😀'.repeat(2001) },
    ];
    const { rows, tooMany } = problemsOf(nodes);
    expect([...rows]).toEqual([
      ['a', ['title']],
      ['c', ['title']],
      ['e', ['requirement']],
    ]);
    expect(tooMany).toBe(false);
    expect(problemsOf([]).tooMany).toBe(true);
    const many = Array.from({ length: 151 }, (_, i) => node(`k${i}`, null, 1));
    expect(problemsOf(many).tooMany).toBe(true);
    expect(problemsOf(many.slice(1)).tooMany).toBe(false);
  });

  it('보낼 본문 — 칸 다섯만, 제목 앞뒤 공백만 걷음', () => {
    const body = bodyOf([
      { ...node('a', null, 1, ' 지어낸 '), requirement: ' 요 ' },
    ]);
    expect(body).toEqual([
      {
        key: 'a',
        parentKey: null,
        depth: 1,
        title: '지어낸',
        requirement: ' 요 ',
      },
    ]);
  });

  it('고친 줄 — 새 마디·이름·차례·단계, 지운 것도 dirty', () => {
    const saved = tree();
    expect(isDirty(saved, tree())).toBe(false);
    expect([...changedKeys(saved, edit(saved, 1, { title: 'x' }))]).toEqual([
      'b',
    ]);
    expect([...changedKeys(saved, addTop(saved, 'x', counter())[0])]).toEqual([
      'n1',
    ]);
    expect([...changedKeys(saved, moveDown(saved, 1)[0])].sort()).toEqual([
      'b',
      'c',
      'd',
    ]);
    expect(isDirty(saved, removeAt(saved, 4))).toBe(true);
  });

  it('422 fields — nodes.<i>.title|requirement 은 보낸 i 번째 줄 key, 그 밖(구조·key·depth)은 whole', () => {
    const sent = tree();
    expect(
      fieldsOf(sent, { 'nodes.2.title': ['x'], 'nodes.4.requirement': ['y'] }),
    ).toEqual({
      rows: new Map([
        ['c', ['title']],
        ['e', ['requirement']],
      ]),
      whole: false,
    });
    expect(fieldsOf(sent, { nodes: ['x'] }).whole).toBe(true);
    expect(fieldsOf(sent, { 'nodes.1.depth': ['x'] }).whole).toBe(true);
    expect(fieldsOf(sent, { 'nodes.9.title': ['x'] }).whole).toBe(true);
  });
});

describe('RPW7 — 같은 단계 더하기 · 대제목 자리', () => {
  const list = () => [
    node('a', null, 1),
    node('b', 'a', 2),
    node('c', 'b', 3),
    node('d', 'c', 4),
    node('e', 'a', 2),
    node('f', null, 1),
  ];

  it('addSibling — 아래 단계 끝 바로 뒤 · 같은 부모·단계 · 번호', () => {
    const [next, at] = addSibling(list(), 1, '가상 새 줄', () => 'n1');
    expect(at).toBe(4);
    expect(next[4]).toEqual(node('n1', 'a', 2, '가상 새 줄'));
    expect(next.map((one) => one.key)).toEqual([
      'a',
      'b',
      'c',
      'd',
      'n1',
      'e',
      'f',
    ]);
    expect(numbersOf(next)[4]).toBe('1.2');
    expect(numbersOf(next)[5]).toBe('1.3');
  });

  it('addSibling — 소소 줄에서도 된다(단계 그대로)', () => {
    const [next, at] = addSibling(list(), 3, '가상 새 줄', () => 'n1');
    expect(at).toBe(4);
    expect(next[4]).toEqual(node('n1', 'c', 4, '가상 새 줄'));
  });

  it('addTop at — 그 자리에 · 없으면 끝', () => {
    const [next, at] = addTop(list(), '가상 새 줄', () => 'n1', 5);
    expect(at).toBe(5);
    expect(next.map((one) => one.key)).toEqual([
      'a',
      'b',
      'c',
      'd',
      'e',
      'n1',
      'f',
    ]);
    expect(addTop(list(), '가상 새 줄', () => 'n1')[1]).toBe(6);
  });
});
