// 고객사 인덱스 선택(S17)의 꼴과 셈(밴드 W12-0b2 ① — 서버 K1b-2b, sid:MARC-ENT-469 3·4, sid:MARC-ISSUE-426 트리·선택 줄). React·DOM·통신을 모른다.
//   - 꼴: 서버 IndexTreeOut·IndexTreeNodeOut 그대로(응답 id 는 글자, 잎만 칸 셋 facilityCodeId·hasFactor·hasData — 위 단은 null).
//   - 트리 엮기: 서버는 평평한 nodes(서버 차례)·parentId. 부모가 목록에 없는 줄은 뿌리(서버 rollup 과 같음), 차례는 서버 것 그대로.
//   - 고를 수 있는 잎(서버 selectable): availableCount > 0 이고 hasFactor. J1 — 처음 읽을 때 selected 였던 잎은 그 둘이 거짓이어도
//     저장 전까지 해제·다시 고르기가 된다(서버가 새로 고르는 잎만 거른다 — K1b-2b 넘김 :92).
//   - 위 단 체크 상태는 서버 selected 가 아니라 잎에서 셈한다(고를 수 있는 잎 기준). 저장 본문은 잎만(서버 차례).
//   - 연도: 올해(Asia/Seoul)부터 내림 다섯 해(감독 처분 Q5 — 서버는 1990~올해, 회사 기준연도 칸이 없다).
import type { PoolLevel } from './pool.ts';

export interface SelectionNode {
  id: string;
  level: PoolLevel;
  /** 잎은 시설 코드 이름. */
  name: string;
  parentId: string | null;
  /** 잎만, 그 밖은 null. */
  facilityCodeId: string | null;
  /** 이 회사 인벤토리 켠 사업장의 그 코드 시설 수(위 단은 아래 합). */
  availableCount: number;
  /** 잎은 숨기지 않은 선택이 있음, 위 단은 아래 고를 수 있는 잎이 다 골라짐(화면은 쓰지 않는다 — parentState). */
  selected: boolean;
  /** 잎만 — 기본 배출계수가 있음. 위 단 null. */
  hasFactor: boolean | null;
  /** 잎만 — 이 해 입력값이 있음(지금 늘 거짓 — S12a). 위 단 null. */
  hasData: boolean | null;
}

export interface SelectionTree {
  year: number;
  nodes: SelectionNode[];
}

/** 저장 답(IndexSelectionSaveOut). */
export interface SelectionSaved {
  selected: number;
  hiddenWithData: number;
}

/** 엮은 트리: 뿌리·자식(서버 차례)·id 찾기. */
export interface WovenTree {
  roots: SelectionNode[];
  childrenOf(id: string): SelectionNode[];
  byId: ReadonlyMap<string, SelectionNode>;
  /** 잎 전부(서버 차례). */
  leaves: SelectionNode[];
}

const LEAF: PoolLevel = 'facility';

export const isLeaf = (node: SelectionNode) => node.level === LEAF;

/** 평평한 nodes → 트리. 부모가 목록에 없는 줄은 뿌리. 차례는 서버 차례 그대로(다시 줄 세우지 않는다). */
export function weave(nodes: readonly SelectionNode[]): WovenTree {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map<string, SelectionNode[]>();
  const roots: SelectionNode[] = [];
  for (const node of nodes) {
    if (node.parentId !== null && byId.has(node.parentId)) {
      const list = children.get(node.parentId) ?? [];
      list.push(node);
      children.set(node.parentId, list);
    } else roots.push(node);
  }
  return {
    roots,
    childrenOf: (id) => children.get(id) ?? [],
    byId,
    leaves: nodes.filter(isLeaf),
  };
}

/**
 * 잎을 나무 차례로(뿌리부터 자식 차례대로 깊이 먼저 — GX2 S12-05 「선택한 인덱스」 표). 서버 평평한 차례(leaves)와 다를 수 있다
 * (늦게 더한 잎이 끝에 오는 꼴). 저장 본문은 그대로 leaves(서버 차례)를 쓴다.
 */
export function treeLeaves(tree: WovenTree): SelectionNode[] {
  const out: SelectionNode[] = [];
  const seen = new Set<string>();
  const walk = (node: SelectionNode) => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    if (isLeaf(node)) out.push(node);
    for (const child of tree.childrenOf(node.id)) walk(child);
  };
  for (const root of tree.roots) walk(root);
  return out;
}

/** 열 넷: 열 1 = 뿌리, 열 n = 고른 길 n−1 번째의 자식. 길이 끊기면 그 뒤 열은 빈다. */
export function treeColumns(
  tree: WovenTree,
  path: readonly string[],
): SelectionNode[][] {
  return [0, 1, 2, 3].map((index) => {
    if (index === 0) return tree.roots;
    const parent = path[index - 1];
    return parent === undefined ? [] : tree.childrenOf(parent);
  });
}

/** 처음 고름: 고른 길을 왼쪽부터 각 열의 첫 항목으로 잇는다(잎 열까지는 가지 않는다 — 셋째 열까지). 없어진 id 는 거기서 첫 항목. */
export function treePath(tree: WovenTree, path: readonly string[]): string[] {
  const out: string[] = [];
  let following = true;
  for (let index = 0; index < 3; index += 1) {
    const column = treeColumns(tree, out)[index]!;
    const kept =
      following ? column.find((node) => node.id === path[index]) : undefined;
    const next = kept ?? column[0];
    if (!next || isLeaf(next)) return out;
    if (!kept) following = false;
    out.push(next.id);
  }
  return out;
}

/** 서버 selectable: 기본 계수가 있는 잎(S12-05 — 이 회사에 자산/시설이 없어도 고른다, sid:MARC-ENT-644). */
export const selectable = (node: SelectionNode) =>
  isLeaf(node) && node.hasFactor === true;

/** 처음 읽을 때 고른 잎(J1 — 저장 전까지 못 고를 잎이어도 다시 고를 수 있다). */
export const initialChosen = (nodes: readonly SelectionNode[]) =>
  new Set(
    nodes.filter((node) => isLeaf(node) && node.selected).map((n) => n.id),
  );

/** 체크할 수 있는가: 고를 수 있는 잎이거나, 처음 고른 잎(J1). */
export const choosable = (node: SelectionNode, initial: ReadonlySet<string>) =>
  selectable(node) || (isLeaf(node) && initial.has(node.id));

/** 못 고르는 까닭(체크 흐림 글) — 기본 계수 없음 하나(S12-05: 시설 0 은 까닭 아님). 고를 수 있으면 null. */
export function blockedReason(
  node: SelectionNode,
  initial: ReadonlySet<string>,
): 'noFactor' | null {
  if (!isLeaf(node) || choosable(node, initial)) return null;
  return 'noFactor';
}

/** 그 노드 아래 잎(자신이 잎이면 자신). */
export function leavesUnder(tree: WovenTree, id: string): SelectionNode[] {
  const node = tree.byId.get(id);
  if (!node) return [];
  if (isLeaf(node)) return [node];
  return tree.childrenOf(id).flatMap((child) => leavesUnder(tree, child.id));
}

export type CheckState = 'all' | 'some' | 'none';

/**
 * 위 단 체크 상태 — 잎에서 셈한다. 「전부」 = 아래 고를 수 있는 잎이 하나 이상이고 다 골라짐(J1 의 이미 고른 못 고를 잎은 셈에 들지 않음).
 * 「일부」 = 그 밖에 골라진 잎이 하나라도 있음. 잎 자신은 골라짐 = 전부.
 */
export function parentState(
  tree: WovenTree,
  id: string,
  chosen: ReadonlySet<string>,
): CheckState {
  const leaves = leavesUnder(tree, id);
  const able = leaves.filter(selectable);
  if (able.length > 0 && able.every((leaf) => chosen.has(leaf.id)))
    return 'all';
  return leaves.some((leaf) => chosen.has(leaf.id)) ? 'some' : 'none';
}

/**
 * 위 단 체크 누름: 「전부」(또는 고를 수 있는 잎 0)면 아래 잎 전부 해제, 아니면 아래 고를 수 있는 잎 전부를 더한다(이미 고른 것은 그대로).
 * 검색 중에는 보이는 트리(weave(filterTree(…)))를 넘긴다 — 바뀌는 잎은 보이는(검색에 맞는) 잎뿐, 숨은 잎의 고름은 그대로(sid:MARC-ISSUE-468 R4·M1).
 */
export function toggleParent(
  tree: WovenTree,
  id: string,
  chosen: ReadonlySet<string>,
): Set<string> {
  const next = new Set(chosen);
  const leaves = leavesUnder(tree, id);
  // 아래 고를 수 있는 잎이 없으면(J1 잎만 골라짐 — 검증 R3) 누름은 해제다(더할 잎이 없어 아무 일도 안 일어나지 않게).
  if (parentState(tree, id, chosen) === 'all' || !leaves.some(selectable))
    for (const leaf of leaves) next.delete(leaf.id);
  else for (const leaf of leaves.filter(selectable)) next.add(leaf.id);
  return next;
}

/** 위 단 체크를 누를 수 있는가: 아래 고를 수 있는 잎이나 골라진 잎이 하나라도 있음 — 둘 다 0 이면 흐림(sid:MARC-ISSUE-468 R5·M4). */
export function parentCheckable(
  tree: WovenTree,
  id: string,
  chosen: ReadonlySet<string>,
): boolean {
  return leavesUnder(tree, id).some(
    (leaf) => selectable(leaf) || chosen.has(leaf.id),
  );
}

/** 잎 체크 누름: 골라져 있으면 뺌, 아니면 체크할 수 있을 때만 더함. */
export function toggleLeaf(
  node: SelectionNode,
  chosen: ReadonlySet<string>,
  initial: ReadonlySet<string>,
): Set<string> {
  const next = new Set(chosen);
  if (next.has(node.id)) next.delete(node.id);
  else if (choosable(node, initial)) next.add(node.id);
  return next;
}

/** 저장 본문의 잎 id(서버 차례, 잎만 — 위 단 id 는 싣지 않는다). 정수 바꿈은 어댑터(toRequestId). */
export function selectionBody(
  tree: WovenTree,
  chosen: ReadonlySet<string>,
): string[] {
  return tree.leaves.filter((leaf) => chosen.has(leaf.id)).map((n) => n.id);
}

/** 다시 읽은 트리에 없는 잎 id 를 고른 것에서 뺀다(sid:MARC-ISSUE-459 M4 꼴). */
export function pruneChosen(
  tree: WovenTree,
  chosen: ReadonlySet<string>,
): Set<string> {
  return new Set(
    [...chosen].filter((id) => {
      const node = tree.byId.get(id);
      return node !== undefined && isLeaf(node);
    }),
  );
}

/** 처음 고른 잎 가운데 뺀 것 중 hasData 참인 잎(저장 전 경고 — 「n개」). */
export function droppedWithData(
  tree: WovenTree,
  before: ReadonlySet<string>,
  after: ReadonlySet<string>,
): SelectionNode[] {
  return tree.leaves.filter(
    (leaf) =>
      before.has(leaf.id) && !after.has(leaf.id) && leaf.hasData === true,
  );
}

/** 같은 고름인가(바꾼 것이 있는지 — 나가기 확인). */
export const sameChosen = (a: ReadonlySet<string>, b: ReadonlySet<string>) =>
  a.size === b.size && [...a].every((id) => b.has(id));

/** 그 노드의 조상부터 자신까지(뿌리 → 노드). */
export function pathTo(tree: WovenTree, id: string): SelectionNode[] {
  const out: SelectionNode[] = [];
  const seen = new Set<string>();
  let node = tree.byId.get(id);
  while (node && !seen.has(node.id)) {
    seen.add(node.id);
    out.unshift(node);
    node = node.parentId === null ? undefined : tree.byId.get(node.parentId);
  }
  return out;
}

/** 4단 이름 부분 일치(대소문자 무시) — 맞는 항목과 그 조상만 남긴다(서버 차례). 빈 글이면 그대로. */
export function filterTree(
  nodes: readonly SelectionNode[],
  q: string,
): SelectionNode[] {
  const text = q.trim().toLowerCase();
  if (text === '') return [...nodes];
  const tree = weave(nodes);
  const keep = new Set<string>();
  for (const node of nodes)
    if (node.name.toLowerCase().includes(text))
      for (const up of pathTo(tree, node.id)) keep.add(up.id);
  return nodes.filter((node) => keep.has(node.id));
}

/** 올해(Asia/Seoul). */
export function seoulYear(today: Date): number {
  const text = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
  }).format(today);
  return Number(text);
}

/** 고를 수 있는 연도: 올해부터 내림 다섯 해(Q5). */
export function yearsOf(today: Date): number[] {
  const year = seoulYear(today);
  return [0, 1, 2, 3, 4].map((back) => year - back);
}

/** 처음 고른 해(주소에 없음·범위 밖일 때): 전년도(Asia/Seoul) — Scope 3 와 같은 규칙(sid:MARC-ENT-578). 범위(yearsOf)는 그대로 올해부터라 늘 그 안. */
export function defaultYearOf(today: Date): number {
  return seoulYear(today) - 1;
}

/** 주소의 연도가 고를 수 있는 해면 그 해, 아니면(없음·범위 밖) null — 부르는 쪽이 전년도(defaultYearOf)로 replace. */
export const yearIn = (
  year: number | undefined,
  years: readonly number[],
): number | null => (year !== undefined && years.includes(year) ? year : null);
