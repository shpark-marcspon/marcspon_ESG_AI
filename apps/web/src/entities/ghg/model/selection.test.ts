// 고객사 인덱스 선택 셈(밴드 W12-0b2 ① — 발주서 §3 2, sid:MARC-ISSUE-426 트리·선택 줄): 엮기·뿌리·차례 · selectable · 부모 셋 꼴 ·
//   toggleParent · J1 · selectionBody · droppedWithData · filterTree · yearsOf. 노드는 손으로 지은 것(서버 꼴 그대로 — 위 단 칸 셋 null).
import { describe, expect, it } from 'vitest';

import {
  blockedReason,
  choosable,
  defaultYearOf,
  droppedWithData,
  filterTree,
  initialChosen,
  parentCheckable,
  parentState,
  pathTo,
  pruneChosen,
  sameChosen,
  selectable,
  selectionBody,
  toggleLeaf,
  toggleParent,
  treeColumns,
  treeLeaves,
  treePath,
  weave,
  yearIn,
  yearsOf,
} from './index.ts';
import type { SelectionNode } from './index.ts';

const up = (
  id: string,
  level: SelectionNode['level'],
  parentId: string | null,
  name = `지어낸 ${id}`,
): SelectionNode => ({
  id,
  level,
  name,
  parentId,
  facilityCodeId: null,
  availableCount: 0,
  selected: false,
  hasFactor: null,
  hasData: null,
});
const leaf = (
  id: string,
  parentId: string,
  {
    count = 1,
    factor = true,
    selected = false,
    data = false,
    name = `지어낸 잎 ${id}`,
  } = {},
): SelectionNode => ({
  id,
  level: 'facility',
  name,
  parentId,
  facilityCodeId: id,
  availableCount: count,
  selected,
  hasFactor: factor,
  hasData: data,
});

/** 범위 1 ─ 유형 3 ─ 활동 5 ─ 잎 20(고름 가능)·22(시설 0·계수 없음)·24(계수 없음)·26(고름 가능) / 활동 7 ─ 잎 28 · 범위 2(자식 0). */
const NODES: SelectionNode[] = [
  up('1', 'scope', null, '지어낸 직접배출'),
  up('2', 'scope', null, '지어낸 간접배출'),
  up('3', 'source_type', '1', '지어낸 고정연소'),
  up('5', 'activity', '3', '지어낸 액체연료'),
  up('7', 'activity', '3', '지어낸 기체연료'),
  leaf('20', '5', { name: '지어낸 보일러' }),
  leaf('22', '5', { count: 0, factor: false }),
  leaf('24', '5', { factor: false }),
  leaf('26', '5'),
  leaf('28', '7', { name: '지어낸 버너' }),
];

describe('트리 엮기(426 트리 꼴)', () => {
  it('평평한 nodes → 열 넷 · 차례는 서버 차례 그대로(다시 줄 세우지 않음)', () => {
    const shuffled = [NODES[1]!, NODES[0]!, ...NODES.slice(2).reverse()];
    const tree = weave(shuffled);
    expect(tree.roots.map((n) => n.id)).toEqual(['2', '1']);
    expect(tree.childrenOf('5').map((n) => n.id)).toEqual([
      '26',
      '24',
      '22',
      '20',
    ]);
    const path = treePath(tree, []);
    expect(path).toEqual(['2']);
    const cols = treeColumns(weave(NODES), ['1', '3', '5']);
    expect(cols.map((col) => col.map((n) => n.id))).toEqual([
      ['1', '2'],
      ['3'],
      ['5', '7'],
      ['20', '22', '24', '26'],
    ]);
  });

  it('부모가 목록에 없는 줄은 뿌리(서버 rollup 과 같음) — 버리지 않는다', () => {
    const orphan = [...NODES, up('9', 'activity', '404'), leaf('30', '9')];
    const tree = weave(orphan);
    expect(tree.roots.map((n) => n.id)).toEqual(['1', '2', '9']);
    expect(tree.leaves.map((n) => n.id)).toContain('30');
    expect(pathTo(tree, '30').map((n) => n.id)).toEqual(['9', '30']);
  });

  it('GX2 S12-05 treeLeaves: 잎을 나무 차례(깊이 먼저 · 자식은 서버 차례)로 — 평평한 차례 끝에 온 잎도 제 가지 자리 · leaves 는 그대로', () => {
    // 범위 8 아래 잎 40 이 평평한 차례 맨 앞, 범위 1 의 활동 5 잎 29 가 맨 끝(늦게 더한 꼴).
    const nodes = [
      up('8', 'scope', null),
      up('4', 'source_type', '8'),
      up('6', 'activity', '4'),
      leaf('40', '6'),
      ...NODES,
      leaf('29', '5'),
    ];
    const tree = weave(nodes);
    expect(treeLeaves(tree).map((n) => n.id)).toEqual([
      '40',
      '20',
      '22',
      '24',
      '26',
      '29',
      '28',
    ]);
    expect(tree.leaves.map((n) => n.id)).toEqual([
      '40',
      '20',
      '22',
      '24',
      '26',
      '28',
      '29',
    ]);
  });

  it('treePath: 고른 길 유지 · 없어진 id 면 거기서 첫 항목 · 잎 열은 고르지 않음', () => {
    const tree = weave(NODES);
    expect(treePath(tree, [])).toEqual(['1', '3', '5']);
    expect(treePath(tree, ['1', '3', '7'])).toEqual(['1', '3', '7']);
    expect(treePath(tree, ['1', '404', '7'])).toEqual(['1', '3', '5']);
  });
});

describe('고르기(426 hasFactor·J1)', () => {
  it('S12-05 selectable = 잎이고 hasFactor(시설 0 이어도) · 까닭은 기본 계수 없음 하나', () => {
    const tree = weave(NODES);
    const ids = tree.leaves.filter(selectable).map((n) => n.id);
    expect(ids).toEqual(['20', '26', '28']);
    expect(selectable(NODES[0]!)).toBe(false);
    const bare = leaf('30', '5', { count: 0 }); // 시설 0 · 기본 계수 있음
    expect(selectable(bare)).toBe(true);
    const none = new Set<string>();
    expect(blockedReason(bare, none)).toBeNull(); // 시설 0 — 고른다
    expect(blockedReason(tree.byId.get('22')!, none)).toBe('noFactor');
    expect(blockedReason(tree.byId.get('24')!, none)).toBe('noFactor');
    expect(
      blockedReason(leaf('29', '5', { count: 0, factor: false }), none),
    ).toBe('noFactor');
    expect(blockedReason(tree.byId.get('20')!, none)).toBeNull();
  });

  it('J1: 처음 고른 못 고를 잎은 해제 → 다시 고름 → 본문에 실림 · 처음부터 안 고른 못 고를 잎은 더해지지 않음', () => {
    const nodes = NODES.map((n) =>
      n.id === '22' || n.id === '20' ? { ...n, selected: true } : n,
    );
    const tree = weave(nodes);
    const initial = initialChosen(nodes);
    expect([...initial]).toEqual(['20', '22']);
    const n22 = tree.byId.get('22')!;
    expect(choosable(n22, initial)).toBe(true);
    expect(blockedReason(n22, initial)).toBeNull();
    let chosen = toggleLeaf(n22, initial, initial);
    expect(chosen.has('22')).toBe(false);
    chosen = toggleLeaf(n22, chosen, initial);
    expect(chosen.has('22')).toBe(true);
    expect(selectionBody(tree, chosen)).toEqual(['20', '22']);
    const n24 = tree.byId.get('24')!;
    expect(toggleLeaf(n24, chosen, initial).has('24')).toBe(false);
  });
});

describe('위 단 체크(잎에서 셈)', () => {
  it('부모 셋 꼴: 없음 · 일부 「−」 · 전부(고를 수 있는 잎 기준) — 서버 selected 는 보지 않음', () => {
    const lying = NODES.map((n) =>
      n.id === '5' ? { ...n, selected: true } : n,
    );
    const tree = weave(lying);
    expect(parentState(tree, '5', new Set())).toBe('none');
    expect(parentState(tree, '5', new Set(['20']))).toBe('some');
    expect(parentState(tree, '5', new Set(['20', '26']))).toBe('all');
    expect(parentState(tree, '3', new Set(['20', '26']))).toBe('some');
    expect(parentState(tree, '1', new Set(['20', '26', '28']))).toBe('all');
    expect(parentState(tree, '2', new Set())).toBe('none');
    expect(parentState(tree, '20', new Set(['20']))).toBe('all');
  });

  it('J1 의 이미 고른 못 고를 잎은 「전부」 셈에 들지 않음(그 잎만 골라지면 일부)', () => {
    const tree = weave(NODES);
    expect(parentState(tree, '5', new Set(['22']))).toBe('some');
    expect(parentState(tree, '5', new Set(['20', '26', '22']))).toBe('all');
  });

  it('toggleParent: 체크 → 고를 수 있는 자식 전부 · 「전부」에서 해제 → 아래 잎 전부(J1 잎 포함)', () => {
    const tree = weave(NODES);
    const on = toggleParent(tree, '5', new Set(['28']));
    expect([...on].sort()).toEqual(['20', '26', '28']);
    const half = toggleParent(tree, '5', new Set(['22']));
    expect([...half].sort()).toEqual(['20', '22', '26']);
    const off = toggleParent(tree, '5', half);
    expect([...off]).toEqual([]);
    // 검증 R3: 고를 수 있는 잎이 없고 J1 잎만 골라진 부모를 누르면 해제(무동작 아님).
    const onlyJ1 = weave([
      up('8', 'activity', null),
      leaf('40', '8', { count: 0, factor: false, selected: true }),
    ]);
    expect(parentState(onlyJ1, '8', new Set(['40']))).toBe('some');
    expect([...toggleParent(onlyJ1, '8', new Set(['40']))]).toEqual([]);
    expect([...toggleParent(tree, '1', new Set())].sort()).toEqual([
      '20',
      '26',
      '28',
    ]);
  });
});

describe('검색 중 위 단 체크 · 흐림(sid:MARC-ISSUE-468)', () => {
  it('R4·M1: 보이는 트리를 넘기면 보이는 잎만 바뀜 — 숨은 고를 수 있는 잎은 더하지 않고, 숨은 고른 잎은 빼지 않음', () => {
    const shown = weave(filterTree(NODES, '보일러'));
    expect([...toggleParent(shown, '5', new Set())]).toEqual(['20']);
    // 숨은 26 이 골라져 있어도 보이는 20 기준 「없음」 → 더함, 26 은 그대로.
    expect([...toggleParent(shown, '5', new Set(['26']))].sort()).toEqual([
      '20',
      '26',
    ]);
    // 보이는 20 이 다 골라짐 → 해제는 20 만(숨은 26 은 남음).
    expect([...toggleParent(shown, '5', new Set(['20', '26']))]).toEqual([
      '26',
    ]);
    expect(parentState(shown, '5', new Set(['20']))).toBe('all');
  });

  it('R5·M4: 고를 잎 0 · 골라진 잎 0 이면 누를 수 없음 — 골라진 잎(J1)이 있으면 누름(해제)', () => {
    const tree = weave([
      up('8', 'activity', null),
      leaf('40', '8', { count: 0, factor: false }),
      leaf('42', '8', { factor: false }),
      up('9', 'activity', null),
    ]);
    expect(parentCheckable(tree, '8', new Set())).toBe(false);
    expect(parentCheckable(tree, '8', new Set(['40']))).toBe(true);
    expect(parentCheckable(tree, '9', new Set())).toBe(false);
    expect(parentCheckable(weave(NODES), '5', new Set())).toBe(true);
    // 검색으로 고를 잎이 다 숨으면 그 활동도 누를 수 없음.
    const shown = weave(filterTree(NODES, '지어낸 액체연료'));
    expect(parentCheckable(shown, '5', new Set())).toBe(false);
  });
});

describe('저장 본문 · 경고 · 다시 읽기', () => {
  it('selectionBody: 잎만(위 단 id 0) · 서버 차례 · 빈 고름이면 []', () => {
    const tree = weave(NODES);
    expect(selectionBody(tree, new Set(['28', '5', '1', '20']))).toEqual([
      '20',
      '28',
    ]);
    expect(selectionBody(tree, new Set())).toEqual([]);
  });

  it('droppedWithData: 처음 고른 것 가운데 뺀 잎의 hasData 참만', () => {
    const nodes = NODES.map((n) =>
      n.id === '20' || n.id === '26' ? { ...n, hasData: true } : n,
    );
    const tree = weave(nodes);
    const before = new Set(['20', '26', '28']);
    expect(
      droppedWithData(tree, before, new Set(['26'])).map((n) => n.id),
    ).toEqual(['20']);
    expect(droppedWithData(tree, before, before)).toEqual([]);
  });

  it('pruneChosen: 다시 읽은 트리에 없는 잎 id 를 뺌(459 M4) · sameChosen', () => {
    const tree = weave(NODES.filter((n) => n.id !== '26'));
    expect([...pruneChosen(tree, new Set(['20', '26', '5']))]).toEqual(['20']);
    expect(sameChosen(new Set(['1', '2']), new Set(['2', '1']))).toBe(true);
    expect(sameChosen(new Set(['1']), new Set(['1', '2']))).toBe(false);
  });
});

describe('검색 · 연도', () => {
  it('filterTree: 4단 이름 부분 일치(대소문자·앞뒤 공백 무시) — 맞는 항목과 조상만, 서버 차례', () => {
    expect(filterTree(NODES, ' 버너 ').map((n) => n.id)).toEqual([
      '1',
      '3',
      '7',
      '28',
    ]);
    expect(filterTree(NODES, '고정').map((n) => n.id)).toEqual(['1', '3']);
    expect(filterTree(NODES, '없는 글').map((n) => n.id)).toEqual([]);
    expect(filterTree(NODES, '')).toHaveLength(NODES.length);
  });

  it('W12-4 ② defaultYearOf: 전년도(Asia/Seoul) · 서울 새해 문턱 양쪽 · 늘 yearsOf 안(sid:MARC-ENT-578)', () => {
    // UTC 12-31 14:59 = 서울 12-31 23:59 → 아직 그해 · 15:00 = 서울 01-01 00:00 → 새해.
    const before = new Date('2026-12-31T14:59:00Z');
    const after = new Date('2026-12-31T15:00:00Z');
    expect(defaultYearOf(before)).toBe(2025);
    expect(defaultYearOf(after)).toBe(2026);
    expect(defaultYearOf(new Date('2026-10-29T03:00:00Z'))).toBe(2025);
    for (const today of [before, after, new Date('2027-06-01T00:00:00Z')])
      expect(yearsOf(today)).toContain(defaultYearOf(today));
  });

  it('yearsOf: 올해(Asia/Seoul)부터 내림 다섯 · yearIn: 범위 밖·없음 → null', () => {
    expect(yearsOf(new Date('2026-10-29T03:00:00Z'))).toEqual([
      2026, 2025, 2024, 2023, 2022,
    ]);
    // UTC 12-31 16시 = 서울 01-01 01시 → 새해.
    expect(yearsOf(new Date('2026-12-31T16:00:00Z'))[0]).toBe(2027);
    const years = [2026, 2025, 2024, 2023, 2022];
    expect(yearIn(2024, years)).toBe(2024);
    expect(yearIn(2021, years)).toBeNull();
    expect(yearIn(2027, years)).toBeNull();
    expect(yearIn(undefined, years)).toBeNull();
  });
});
