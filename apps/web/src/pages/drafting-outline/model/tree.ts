// RP-03 목차 셈(밴드 RPW1 ② — 발주서 §2-2). 순수 함수 — React·화면·통신을 모른다.
// 목차는 평평한 마디 목록 하나로 쥔다(drafting.outline@1 nodes 꼴 그대로): 앞 차례(부모가 앞, 한 마디의 하위는 그 바로 뒤에 붙어 있다).
//   이동·단계 바꿈 뒤에도 depth·parentKey·차례가 서버 규칙(apps/api-py/esgapi/drafting/contracts/wire.py) 안에 머문다 —
//   뿌리는 depth 1, 자식은 부모 depth + 1, 깊이 4 까지.
// key 는 고쳐도 바뀌지 않는다(제목·요구·위치·단계 — 이어 받기 열쇠가 key + 내용 sha, 발주서 §1-4 ④). 새 마디만 freshKey 하나로 새 key(앞서 쓰인 적 없는 값 — 지운 key 를 다시 쓰지 않는다).
// 글자 수(제목·요구)는 코드 포인트로 센다(서버와 같게).
import { lengthOf } from '../../../entities/drafting/model/index.ts';
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';

/** 깊이 상한(대·중·소·소소). */
export const MAX_DEPTH = 4;
/** 마디 수 상한. */
export const MAX_NODES = 300;
/** 잎(초안 지을 목차) 수 상한. */
export const MAX_LEAVES = 150;
/** 제목 글자 수 상한(코드 포인트, 앞뒤 공백 걷은 뒤). */
export const TITLE_MAX = 200;
/** 요구 내용 글자 수 상한(코드 포인트 — 서버 값, §2-0 ⑫). */
export const REQUIREMENT_MAX = 2000;

/** 그 마디의 하위가 끝나는 자리(하위가 없으면 index + 1). */
export function subtreeEnd(
  nodes: readonly OutlineNode[],
  index: number,
): number {
  const depth = nodes[index]!.depth;
  let end = index + 1;
  while (end < nodes.length && nodes[end]!.depth > depth) end += 1;
  return end;
}

/** 하위 없는 마디인가. */
export const isLeaf = (nodes: readonly OutlineNode[], index: number) =>
  subtreeEnd(nodes, index) === index + 1;

/** key 짓는 함수(시험은 고정 차례를 주입한다). */
export type KeyMaker = () => string;

/** 기본 key — `n` + 무작위 16진 8자(서버 key 꼴 `^[a-z0-9][a-z0-9-]{0,39}$` 안).
 *  지운 마디의 key 를 새 마디가 다시 얻지 않게 무작위로 짓는다 — 서버 목차 바뀜(outline_changes)이 key 로 견주니(검증 R4). */
export const randomKey: KeyMaker = () =>
  `n${crypto.randomUUID().replace(/-/g, '').slice(0, 8).toLowerCase()}`;

/** 새 key — 짓는 함수가 낸 값 가운데 지금 목록과 겹치지 않는 첫 값(생성 함수는 이것 하나). */
export function freshKey(
  nodes: readonly OutlineNode[],
  make: KeyMaker = randomKey,
): string {
  const used = new Set(nodes.map((node) => node.key));
  let key = make();
  while (used.has(key)) key = make();
  return key;
}

/** 같은 부모 아래 바로 앞 형제의 자리(없으면 null). */
function previousSibling(
  nodes: readonly OutlineNode[],
  index: number,
): number | null {
  const node = nodes[index]!;
  for (let at = index - 1; at >= 0; at -= 1) {
    const other = nodes[at]!;
    if (other.depth < node.depth) return null;
    if (other.depth === node.depth) return at;
  }
  return null;
}

/** 같은 부모 아래 바로 뒤 형제의 자리(없으면 null). */
function nextSibling(
  nodes: readonly OutlineNode[],
  index: number,
): number | null {
  const end = subtreeEnd(nodes, index);
  const next = nodes[end];
  return next && next.depth === nodes[index]!.depth ? end : null;
}

/** 부모의 자리(뿌리면 null). */
function parentIndex(nodes: readonly OutlineNode[], index: number) {
  const key = nodes[index]!.parentKey;
  return key === null ? null : nodes.findIndex((node) => node.key === key);
}

/** 하위 가운데 가장 깊은 depth. */
export function deepestUnder(
  nodes: readonly OutlineNode[],
  index: number,
): number {
  let deepest = nodes[index]!.depth;
  for (let at = index + 1; at < subtreeEnd(nodes, index); at += 1)
    deepest = Math.max(deepest, nodes[at]!.depth);
  return deepest;
}

/** 그 줄에서 쓸 수 있는 단추(화면이 끄고 켠다). */
export interface Moves {
  addChild: boolean;
  up: boolean;
  down: boolean;
  outdent: boolean;
  indent: boolean;
}

export function movesOf(nodes: readonly OutlineNode[], index: number): Moves {
  const node = nodes[index]!;
  const before = previousSibling(nodes, index);
  return {
    addChild: node.depth < MAX_DEPTH,
    up: before !== null,
    down: nextSibling(nodes, index) !== null,
    outdent: node.depth > 1,
    indent: before !== null && deepestUnder(nodes, index) < MAX_DEPTH,
  };
}

const blank = (
  key: string,
  parentKey: string | null,
  depth: number,
  title: string,
): OutlineNode => ({ key, parentKey, depth, title, requirement: '' });

/** 대제목 하나를 더한다 — at 자리에(없으면 끝). [목록, 새 마디 자리]. */
export function addTop(
  nodes: readonly OutlineNode[],
  title: string,
  make: KeyMaker = randomKey,
  at: number = nodes.length,
): [OutlineNode[], number] {
  const top = blank(freshKey(nodes, make), null, 1, title);
  return [[...nodes.slice(0, at), top, ...nodes.slice(at)], at];
}

/** 그 마디의 하위 끝 바로 뒤에 같은 단계 마디를 더한다(같은 부모). [목록, 새 마디 자리]. */
export function addSibling(
  nodes: readonly OutlineNode[],
  index: number,
  title: string,
  make: KeyMaker = randomKey,
): [OutlineNode[], number] {
  const node = nodes[index]!;
  const end = subtreeEnd(nodes, index);
  const sibling = blank(
    freshKey(nodes, make),
    node.parentKey,
    node.depth,
    title,
  );
  return [[...nodes.slice(0, end), sibling, ...nodes.slice(end)], end];
}

/** 그 마디 아래 끝에 한 단계 아래 마디를 더한다(소소에서는 그대로). [목록, 새 마디 자리]. */
export function addChild(
  nodes: readonly OutlineNode[],
  index: number,
  title: string,
  make: KeyMaker = randomKey,
): [OutlineNode[], number] {
  const node = nodes[index]!;
  if (node.depth >= MAX_DEPTH) return [[...nodes], index];
  const end = subtreeEnd(nodes, index);
  const child = blank(freshKey(nodes, make), node.key, node.depth + 1, title);
  return [[...nodes.slice(0, end), child, ...nodes.slice(end)], end];
}

/** 순서·단계 바꿈 하나(moveUp·moveDown·outdent·indent 꼴) — [목록, 옮긴 자리]. */
export type Move = (
  nodes: readonly OutlineNode[],
  index: number,
) => [OutlineNode[], number];

/** 같은 부모 아래에서 한 칸 위로(하위와 함께). [목록, 옮긴 자리]. */
export function moveUp(
  nodes: readonly OutlineNode[],
  index: number,
): [OutlineNode[], number] {
  const before = previousSibling(nodes, index);
  if (before === null) return [[...nodes], index];
  const end = subtreeEnd(nodes, index);
  return [
    [
      ...nodes.slice(0, before),
      ...nodes.slice(index, end),
      ...nodes.slice(before, index),
      ...nodes.slice(end),
    ],
    before,
  ];
}

/** 같은 부모 아래에서 한 칸 아래로(하위와 함께). [목록, 옮긴 자리]. */
export function moveDown(
  nodes: readonly OutlineNode[],
  index: number,
): [OutlineNode[], number] {
  const after = nextSibling(nodes, index);
  if (after === null) return [[...nodes], index];
  const [moved] = moveUp(nodes, after);
  return [moved, index + (subtreeEnd(nodes, after) - after)];
}

/** 하위 전부의 depth 를 옮긴다. */
const shifted = (part: readonly OutlineNode[], by: number) =>
  part.map((node) => ({ ...node, depth: node.depth + by }));

/** 한 단계 올리기 — 부모의 다음 형제가 된다(부모의 하위 끝 뒤, 하위와 함께). [목록, 옮긴 자리]. */
export function outdent(
  nodes: readonly OutlineNode[],
  index: number,
): [OutlineNode[], number] {
  const parent = parentIndex(nodes, index);
  if (parent === null) return [[...nodes], index];
  const end = subtreeEnd(nodes, index);
  const parentEnd = subtreeEnd(nodes, parent);
  const part = shifted(nodes.slice(index, end), -1);
  part[0] = { ...part[0]!, parentKey: nodes[parent]!.parentKey };
  const rest = [...nodes.slice(0, index), ...nodes.slice(end)];
  const at = parentEnd - (end - index);
  return [[...rest.slice(0, at), ...part, ...rest.slice(at)], at];
}

/** 한 단계 내리기 — 바로 앞 형제의 마지막 자식이 된다(자리는 그대로, 깊이 4 를 넘으면 그대로). [목록, 자리]. */
export function indent(
  nodes: readonly OutlineNode[],
  index: number,
): [OutlineNode[], number] {
  const before = previousSibling(nodes, index);
  if (before === null || deepestUnder(nodes, index) >= MAX_DEPTH)
    return [[...nodes], index];
  const end = subtreeEnd(nodes, index);
  const part = shifted(nodes.slice(index, end), 1);
  part[0] = { ...part[0]!, parentKey: nodes[before]!.key };
  return [[...nodes.slice(0, index), ...part, ...nodes.slice(end)], index];
}

/** 그 마디를 하위와 함께 지운다. */
export function removeAt(
  nodes: readonly OutlineNode[],
  index: number,
): OutlineNode[] {
  return [...nodes.slice(0, index), ...nodes.slice(subtreeEnd(nodes, index))];
}

/** 하위 마디 수(그 마디 빼고). */
export const descendantsOf = (nodes: readonly OutlineNode[], index: number) =>
  subtreeEnd(nodes, index) - index - 1;

/** 그 마디의 제목·요구를 고친다(key·자리·단계는 그대로). */
export function edit(
  nodes: readonly OutlineNode[],
  index: number,
  patch: Partial<Pick<OutlineNode, 'title' | 'requirement'>>,
): OutlineNode[] {
  return nodes.map((node, at) => (at === index ? { ...node, ...patch } : node));
}

/** 줄 번호 「1.1.2」(앞 차례 셈). */
export function numbersOf(nodes: readonly OutlineNode[]): string[] {
  const counts: number[] = [];
  return nodes.map((node) => {
    counts.length = node.depth;
    counts[node.depth - 1] = (counts[node.depth - 1] ?? 0) + 1;
    return counts.slice(0, node.depth).join('.');
  });
}

/** 부모 제목들(뿌리부터, 자기 빼고). */
export function ancestorsOf(
  nodes: readonly OutlineNode[],
  index: number,
): string[] {
  const titles: string[] = [];
  let at = parentIndex(nodes, index);
  while (at !== null && at >= 0) {
    titles.unshift(nodes[at]!.title);
    at = parentIndex(nodes, at);
  }
  return titles;
}

/** 머리 셈: 단계마다 수 + 잎 수. */
export function countsOf(nodes: readonly OutlineNode[]) {
  const depths = [0, 0, 0, 0];
  for (const node of nodes) depths[node.depth - 1]! += 1;
  const leaves = nodes.filter((_, index) => isLeaf(nodes, index)).length;
  return { depths, leaves };
}

/** 칸 하나의 문제. */
export type FieldProblem = 'title' | 'requirement';

/** 목차 전체 검사 — 줄마다 칸 문제(key → 칸들) · 전체 문제(수 상한). 비었으면 저장할 수 있다. */
export function problemsOf(nodes: readonly OutlineNode[]) {
  const rows = new Map<string, FieldProblem[]>();
  for (const node of nodes) {
    const found: FieldProblem[] = [];
    const title = lengthOf(node.title.trim());
    if (title < 1 || title > TITLE_MAX) found.push('title');
    if (lengthOf(node.requirement) > REQUIREMENT_MAX) found.push('requirement');
    if (found.length > 0) rows.set(node.key, found);
  }
  const { leaves } = countsOf(nodes);
  const tooMany =
    nodes.length < 1 || nodes.length > MAX_NODES || leaves > MAX_LEAVES;
  return { rows, tooMany };
}

/** 보낼 본문(제목 앞뒤 공백만 걷음 — key·차례·단계는 그대로). */
export const bodyOf = (nodes: readonly OutlineNode[]): OutlineNode[] =>
  nodes.map(({ key, parentKey, depth, title, requirement }) => ({
    key,
    parentKey,
    depth,
    title: title.trim(),
    requirement,
  }));

/** 저장한 목차와 견주어 고친 줄의 key(새 마디·제목·요구·부모·단계·차례가 바뀐 줄). */
export function changedKeys(
  saved: readonly OutlineNode[],
  nodes: readonly OutlineNode[],
): Set<string> {
  const before = new Map(saved.map((node, at) => [node.key, { node, at }]));
  const changed = new Set<string>();
  nodes.forEach((node, at) => {
    const old = before.get(node.key);
    if (
      !old ||
      old.at !== at ||
      old.node.title !== node.title ||
      old.node.requirement !== node.requirement ||
      old.node.parentKey !== node.parentKey ||
      old.node.depth !== node.depth
    )
      changed.add(node.key);
  });
  return changed;
}

/** 저장 뒤와 다른가(지운 마디 포함). */
export const isDirty = (
  saved: readonly OutlineNode[],
  nodes: readonly OutlineNode[],
) => saved.length !== nodes.length || changedKeys(saved, nodes).size > 0;

/** 서버 422 fields 를 줄(key)·칸으로 — `nodes.<i>.<칸>` 은 보낸 본문의 i 번째 줄, 그 밖은 목차 위 한 줄(whole). */
export function fieldsOf(
  sent: readonly OutlineNode[],
  fields: Readonly<Record<string, readonly string[]>>,
) {
  const rows = new Map<string, FieldProblem[]>();
  let whole = false;
  for (const name of Object.keys(fields)) {
    const match = /^nodes\.(\d+)\.(title|requirement)$/.exec(name);
    const node = match ? sent[Number(match[1])] : undefined;
    if (!match || !node) {
      whole = true;
      continue;
    }
    rows.set(node.key, [
      ...(rows.get(node.key) ?? []),
      match[2] as FieldProblem,
    ]);
  }
  return { rows, whole };
}
