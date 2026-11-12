// RP-03a 목차 붙여넣기 — 붙여 넣은 글 해석·넣기·셈(밴드 RPW9 §1-B, 결정 MARC-ENT-557). 순수 함수 — React·화면·통신을 모른다.
// 줄 하나: 앞 들여쓰기 폭 → 번호 머리(번호가 들여쓰기를 이김) → 요구 나눔(탭 · 「요구:」) → 다음 줄 「요구:」 는 앞 목차의 요구로 이음.
//   단계 판정(다섯째 단계)은 맞추기 전 날 단계로, 맞춤은 받아들인 줄만(앞 줄 + 1 까지) — 못 읽은 줄은 그 줄만 빠지고 아래 줄은 앞 줄 아래로 붙는다.
// 행 번호는 붙여 넣은 글의 행(빈 줄도 센다). 글자 수는 코드 포인트(서버 len 과 같게). 한도 값은 tree.ts 의 상수 그대로.
import { lengthOf } from '../../../entities/drafting/model/index.ts';
import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import {
  MAX_DEPTH,
  MAX_LEAVES,
  MAX_NODES,
  REQUIREMENT_MAX,
  TITLE_MAX,
  countsOf,
  freshKey,
} from './tree.ts';
import type { KeyMaker } from './tree.ts';

/** 못 읽은 까닭. */
export type BadReason = 'tooDeep' | 'titleLong' | 'requirementLong' | 'noTitle';

/** 읽은 목차 줄 하나(depth 는 맞춘 뒤 1~4). */
export interface PasteRow {
  line: number;
  depth: number;
  title: string;
  requirement: string;
}

/** 못 읽은 줄 하나. */
export interface PasteBad {
  line: number;
  reason: BadReason;
}

/** 해석 결과 — 빈 글과 「읽었는데 0줄」을 가른다. */
export type PasteRead =
  { kind: 'empty' } | { kind: 'read'; rows: PasteRow[]; bad: PasteBad[] };

/** 넣는 법. */
export type PasteHow = 'append' | 'replace';

/** 앞 들여쓰기 한 글자의 폭 — 탭 4 · 전각 공백 2 · 그 밖 1. */
const widthOf = (char: string) =>
  char === '\t' ? 4
  : char === '　' ? 2
  : 1;

/** 끝 점 있는 번호(`1.` `1.1.` `1.환경`). */
const DOTTED = /^(\d{1,3}(?:\.\d{1,3})*)\.(?!\d)/;
/** 끝 점 없는 번호 — 두 마디 이상, 뒤는 공백·끝(`1.1 재무`). */
const BARE = /^(\d{1,3}(?:\.\d{1,3})+)(?=\s|$)/;
/** 「요구:」 표지(낱말 앞은 줄 머리나 공백). */
const MARK = /(^|\s)요구\s*[:：]/;
const MARK_HEAD = /^요구\s*[:：]/;

/** 한 줄을 쪼갠 것(판정 전). */
interface Item {
  line: number;
  width: number;
  /** 번호 단계(번호가 없으면 null). */
  numbered: number | null;
  title: string;
  requirement: string;
}

/** 줄 하나 → 폭·번호·제목·요구. 이음 줄(번호 없음 · 제목 몫 빔 · 「요구:」 로 나뉨)이면 continuation. */
function splitLine(raw: string, line: number) {
  let width = 0;
  let at = 0;
  while (at < raw.length && /\s/.test(raw[at]!)) {
    width += widthOf(raw[at]!);
    at += 1;
  }
  let rest = raw.slice(at);
  let numbered: number | null = null;
  const number = DOTTED.exec(rest) ?? BARE.exec(rest);
  if (number) {
    numbered = number[1]!.split('.').length;
    // 번호를 먼저 뗀다 — 워드 다단계 목록 꼴 「1.\t환경」 의 탭은 요구 칸 나눔이 아니다.
    rest = rest.slice(number[0].length).replace(/^\s+/, '');
  }
  let title: string;
  let requirement = '';
  let marked = false;
  const tab = rest.indexOf('\t');
  if (tab >= 0) {
    title = rest.slice(0, tab);
    requirement = rest
      .slice(tab + 1)
      .split('\t')
      .map((cell) => cell.trim())
      .filter((cell) => cell.length > 0)
      .join(' ');
    if (MARK_HEAD.test(requirement)) {
      requirement = requirement.replace(MARK_HEAD, '');
      marked = true;
    }
  } else {
    const mark = MARK.exec(rest);
    if (mark) {
      title = rest.slice(0, mark.index);
      requirement = rest.slice(mark.index + mark[0].length);
      marked = true;
    } else title = rest;
  }
  title = title.trim();
  requirement = requirement.trim();
  const item: Item = { line, width, numbered, title, requirement };
  return {
    item,
    continuation: numbered === null && title.length === 0 && marked,
  };
}

/** 첫 걸림 하나(맞추기 전 날 단계로). */
function verdictOf(item: Item, depth: number): BadReason | null {
  if (depth > MAX_DEPTH) return 'tooDeep';
  const title = lengthOf(item.title);
  if (title === 0) return 'noTitle';
  if (title > TITLE_MAX) return 'titleLong';
  if (lengthOf(item.requirement) > REQUIREMENT_MAX) return 'requirementLong';
  return null;
}

/** 붙여 넣은 글 → 읽은 줄 · 못 읽은 줄. */
export function parsePaste(text: string): PasteRead {
  if (text.trim().length === 0) return { kind: 'empty' };
  const items: Item[] = [];
  const bad: PasteBad[] = [];
  text.split(/\r\n|\r|\n/).forEach((raw, index) => {
    if (raw.trim().length === 0) return;
    const { item, continuation } = splitLine(raw, index + 1);
    if (!continuation) return void items.push(item);
    // 다음 줄 요구 — 들여쓰기와 무관하게 바로 앞 목차 줄의 요구로.
    const before = items[items.length - 1];
    if (!before) return void bad.push({ line: item.line, reason: 'noTitle' });
    before.requirement =
      before.requirement ?
        `${before.requirement}\n${item.requirement}`
      : item.requirement;
  });

  const rows: PasteRow[] = [];
  /** 받아들인 줄의 (폭, 날 단계). */
  const stack: { width: number; depth: number }[] = [];
  for (const item of items) {
    while (stack.length > 0 && stack[stack.length - 1]!.width > item.width)
      stack.pop();
    const top = stack[stack.length - 1];
    const indented =
      !top ? 1
      : top.width === item.width ? top.depth
      : top.depth + 1;
    const depth = item.numbered ?? indented;
    const reason = verdictOf(item, depth);
    if (reason !== null) {
      bad.push({ line: item.line, reason });
      continue;
    }
    if (top && top.width === item.width) stack.pop();
    stack.push({ width: item.width, depth });
    const before = rows[rows.length - 1];
    rows.push({
      line: item.line,
      depth: before ? Math.min(depth, before.depth + 1) : 1,
      title: item.title,
      requirement: item.requirement,
    });
  }
  bad.sort((a, b) => a.line - b.line);
  return { kind: 'read', rows, bad };
}

/** 새 줄 가운데 잎(바로 뒤 줄이 더 깊지 않음) 수. */
const leavesOf = (rows: readonly PasteRow[]) =>
  rows.filter((row, at) => (rows[at + 1]?.depth ?? 0) <= row.depth).length;

/** 미리보기 머리 셈과 한도. 붙이기 = 지금 + 새, 바꾸기 = 새만. */
export function pasteCounts(
  nodes: readonly OutlineNode[],
  rows: readonly PasteRow[],
  how: PasteHow,
) {
  const leaves = leavesOf(rows);
  const total =
    how === 'append' ?
      {
        nodes: nodes.length + rows.length,
        leaves: countsOf(nodes).leaves + leaves,
      }
    : { nodes: rows.length, leaves };
  const over: 'nodes' | 'leaves' | null =
    total.nodes > MAX_NODES ? 'nodes'
    : total.leaves > MAX_LEAVES ? 'leaves'
    : null;
  return { nodes: rows.length, leaves, total, over };
}

/** 읽은 줄을 목차에 넣는다. [목록, 넣은 첫 줄 자리]. key 는 지금 목록·avoid(저장한 목차)·이미 지은 새 key 와 겹치지 않는다 — 바꾸기에서도. */
export function placePaste(
  nodes: readonly OutlineNode[],
  rows: readonly PasteRow[],
  how: PasteHow,
  make: KeyMaker,
  avoid: readonly OutlineNode[] = [],
): [OutlineNode[], number] {
  const taken: OutlineNode[] = [...nodes, ...avoid];
  const parents: string[] = [];
  const fresh = rows.map((row): OutlineNode => {
    const key = freshKey(taken, make);
    parents.length = row.depth - 1;
    const node: OutlineNode = {
      key,
      parentKey: row.depth === 1 ? null : (parents[row.depth - 2] ?? null),
      depth: row.depth,
      title: row.title,
      requirement: row.requirement,
    };
    parents[row.depth - 1] = key;
    taken.push(node);
    return node;
  });
  return how === 'append' ? [[...nodes, ...fresh], nodes.length] : [fresh, 0];
}
