// RP-03a 목차 붙여넣기 해석·넣기·셈(밴드 RPW9 §2 vitest — 발주서 §1-B). 시험 글은 모두 지어낸 것.
import { describe, expect, it } from 'vitest';

import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { parsePaste, pasteCounts, placePaste } from './paste.ts';
import type { PasteHow, PasteRead, PasteRow } from './paste.ts';
import { bodyOf, countsOf, problemsOf } from './tree.ts';
import type { KeyMaker } from './tree.ts';

const read = (text: string) => {
  const out = parsePaste(text);
  if (out.kind !== 'read') throw new Error('빈 글');
  return out;
};
/** 「단계:제목」 꼴로. */
const shape = (text: string) =>
  read(text).rows.map((row) => `${row.depth}:${row.title}`);
const reqs = (text: string) => read(text).rows.map((row) => row.requirement);
const bads = (text: string) =>
  read(text).bad.map((one) => `${one.line}:${one.reason}`);

const counter = (prefix = 'k'): KeyMaker => {
  let n = 0;
  return () => `${prefix}${(n += 1)}`;
};

describe('parsePaste — 번호', () => {
  it.each([
    ['1. 지어낸 가', 1, '지어낸 가'],
    ['1.1 지어낸 나', 2, '지어낸 나'],
    ['1.1. 지어낸 나', 2, '지어낸 나'],
    ['1.1.1 지어낸 다', 3, '지어낸 다'],
    ['1.1.1.1 지어낸 라', 4, '지어낸 라'],
    ['1.1.1.1. 지어낸 라', 4, '지어낸 라'],
    ['12.3 지어낸 마', 2, '지어낸 마'],
    ['1.가상환경', 1, '가상환경'],
  ])('%s → 날 단계 %i', (line, depth, title) => {
    // 첫 줄은 맞춤으로 1 이 되니 날 단계를 보려고 앞에 사다리를 둔다.
    const ladder = ['1. 위', '1.1 위', '1.1.1 위'].slice(0, depth - 1);
    const rows = read([...ladder, line].join('\n')).rows;
    expect(rows.at(-1)).toMatchObject({ depth, title });
  });

  it('워드 꼴 「1.\\t제목」 의 탭은 요구 칸이 아니다 — 번호를 먼저 뗀다', () => {
    expect(read('1.\t가상 환경').rows).toEqual([
      { line: 1, depth: 1, title: '가상 환경', requirement: '' },
    ]);
    expect(read('1.1\t가상 재무\t지어낸 요구').rows[0]).toMatchObject({
      title: '가상 재무',
      requirement: '지어낸 요구',
    });
  });

  it.each([
    '2026 지어낸 성과',
    '1 지어낸 환경',
    '2026. 지어낸 성과',
    '1.5배 지어낸',
  ])('%s 는 번호가 아니다 — 제목 글자 그대로', (line) => {
    expect(read(line).rows).toEqual([
      { line: 1, depth: 1, title: line, requirement: '' },
    ]);
  });

  it('다섯 마디 번호 → tooDeep, 행 번호', () => {
    expect(bads('1. 가\n1.1 나\n1.1.1 다\n1.1.1.1 라\n1.1.1.1.1 마')).toEqual([
      '5:tooDeep',
    ]);
  });

  it('번호만 있는 줄 → noTitle', () => {
    expect(bads('1. 가\n1.1\n1.2.')).toEqual(['2:noTitle', '3:noTitle']);
  });
});

describe('parsePaste — 들여쓰기', () => {
  it.each([
    ['스페이스 2', '가\n  나\n    다\n      라'],
    ['스페이스 4', '가\n    나\n        다\n            라'],
    ['탭', '가\n\t나\n\t\t다\n\t\t\t라'],
    ['섞임(탭 = 4)', '가\n    나\n\t    다\n\t\t    라'],
    ['전각 공백(2)', '가\n　나\n　　다\n　　　라'],
    ['NBSP(1)', '가\n 나\n  다\n   라'],
  ])('%s → 1·2·3·4', (_, text) => {
    expect(shape(text)).toEqual(['1:가', '2:나', '3:다', '4:라']);
  });

  it('폭이 들쭉날쭉해도 쌓개로 — 같은 폭은 같은 단계', () => {
    expect(shape('가\n   나\n   다\n      라\n   마\n바')).toEqual([
      '1:가',
      '2:나',
      '2:다',
      '3:라',
      '2:마',
      '1:바',
    ]);
  });

  it('맞지 않는 내어쓰기 — 더 얕은 줄 아래 한 단계', () => {
    expect(shape('가\n    나\n  다')).toEqual(['1:가', '2:나', '2:다']);
  });

  it('다섯째 들여쓰기 → tooDeep', () => {
    expect(bads('가\n  나\n    다\n      라\n        마')).toEqual([
      '5:tooDeep',
    ]);
  });

  it('번호가 들여쓰기를 이긴다 — 감독 골자 예(다음 줄 요구)', () => {
    const text = [
      '1. 환경',
      '  1.1 기후변화 대응',
      '    1.1.1 온실가스 배출 현황',
      '        요구: Scope 1·2 배출량을 연도별로',
    ].join('\n');
    const out = read(text);
    expect(out.rows).toEqual([
      { line: 1, depth: 1, title: '환경', requirement: '' },
      { line: 2, depth: 2, title: '기후변화 대응', requirement: '' },
      {
        line: 3,
        depth: 3,
        title: '온실가스 배출 현황',
        requirement: 'Scope 1·2 배출량을 연도별로',
      },
    ]);
    expect(out.bad).toEqual([]);
    expect(pasteCounts([], out.rows, 'append').leaves).toBe(1);
  });

  it('번호가 들여쓰기를 이긴다 — 들여쓰기 0 인 번호 글(critic ①)', () => {
    expect(shape('1. 가상 A\n1.1 가상 B\n1.1.1 가상 C')).toEqual([
      '1:가상 A',
      '2:가상 B',
      '3:가상 C',
    ]);
  });
  it('번호가 들여쓰기를 이긴다 — 거꾸로 들여쓴 번호 글(critic ①)', () => {
    expect(shape('    1. 가상 A\n1.1 가상 B')).toEqual([
      '1:가상 A',
      '2:가상 B',
    ]);
  });

  it('번호 줄 아래 번호 없는 들여쓴 줄은 그 아래로', () => {
    expect(shape('1. 가\n1.1 나\n    지어낸 다\n    지어낸 라\n2. 마')).toEqual(
      ['1:가', '2:나', '3:지어낸 다', '3:지어낸 라', '1:마'],
    );
  });
});

describe('parsePaste — 요구', () => {
  it.each([
    ['가상 제목\t지어낸 요구', '가상 제목', '지어낸 요구'],
    ['가상 제목\t첫 칸\t\t둘째 칸\t ', '가상 제목', '첫 칸 둘째 칸'],
    ['가상 제목 요구: 지어낸 요구', '가상 제목', '지어낸 요구'],
    ['가상 제목 요구 : 지어낸 요구', '가상 제목', '지어낸 요구'],
    ['가상 제목 요구：지어낸 요구', '가상 제목', '지어낸 요구'],
    ['가상 제목\t요구: 지어낸 요구', '가상 제목', '지어낸 요구'],
    ['요구사항 관리', '요구사항 관리', ''],
    ['가상요구: 붙음', '가상요구: 붙음', ''],
    ['1.1 가상 제목 요구: 지어낸 요구', '가상 제목', '지어낸 요구'],
  ])('%s', (line, title, requirement) => {
    expect(read(line).rows[0]).toMatchObject({ title, requirement });
  });

  it('다음 줄 요구 둘은 줄바꿈으로 잇는다', () => {
    expect(reqs('가상 제목\n  요구: 첫째\n요구: 둘째')).toEqual(['첫째\n둘째']);
    expect(reqs('가상 제목 요구: 앞\n요구: 뒤')).toEqual(['앞\n뒤']);
  });

  it('첫 줄이 요구 줄 → noTitle', () => {
    expect(bads('요구: 지어낸\n가상 제목')).toEqual(['1:noTitle']);
    expect(shape('요구: 지어낸\n가상 제목')).toEqual(['1:가상 제목']);
  });

  it('못 읽은 줄 뒤 요구 줄은 그 줄과 같이 빠진다(따로 세지 않음)', () => {
    const long = '가'.repeat(201);
    const out = read(`가상 위\n${long}\n  요구: 지어낸\n가상 아래`);
    expect(out.bad).toEqual([{ line: 2, reason: 'titleLong' }]);
    expect(out.rows.map((row) => row.requirement)).toEqual(['', '']);
  });
});

describe('parsePaste — 경계', () => {
  it('제목 200 통과 · 201 titleLong', () => {
    expect(bads(`${'가'.repeat(200)}`)).toEqual([]);
    expect(bads(`${'가'.repeat(201)}`)).toEqual(['1:titleLong']);
  });

  it('요구 2,000 통과 · 2,001 requirementLong(이음 뒤 포함, 제목 줄의 행)', () => {
    expect(bads(`가\t${'나'.repeat(2000)}`)).toEqual([]);
    expect(bads(`가\t${'나'.repeat(2001)}`)).toEqual(['1:requirementLong']);
    // 1,000 + 줄바꿈 1 + 999 = 2,000 · 1,000 + 1 + 1,000 = 2,001
    expect(bads(`가\t${'나'.repeat(1000)}\n요구: ${'다'.repeat(999)}`)).toEqual(
      [],
    );
    expect(
      bads(`빈\n가\t${'나'.repeat(1000)}\n요구: ${'다'.repeat(1000)}`),
    ).toEqual(['2:requirementLong']);
  });

  it('이음으로 2,001 이 된 첫 줄은 그 줄만 빠지고 아래 「1.1」 은 단계 1·부모 없음(critic ②)', () => {
    const out = read(
      `1. 가상 위\t${'나'.repeat(1000)}\n요구: ${'다'.repeat(1000)}\n1.1 가상 아래`,
    );
    expect(out.bad).toEqual([{ line: 1, reason: 'requirementLong' }]);
    expect(out.rows).toEqual([
      { line: 3, depth: 1, title: '가상 아래', requirement: '' },
    ]);
    const [placed] = placePaste([], out.rows, 'replace', counter());
    expect(placed[0]).toMatchObject({ depth: 1, parentKey: null });
  });

  it('BOM(U+FEFF) 은 공백류로 걷는다(critic ⑦)', () => {
    expect(shape('\uFEFF1. 가상 A\n1.1 가상 B')).toEqual([
      '1:가상 A',
      '2:가상 B',
    ]);
  });

  it('서로게이트 글자는 한 자 — 🌱 200 개 통과', () => {
    expect(bads('🌱'.repeat(200))).toEqual([]);
    expect(bads('🌱'.repeat(201))).toEqual(['1:titleLong']);
  });

  it('제목 앞뒤 공백은 걷는다', () => {
    expect(read('1.   가상 제목   ').rows[0]!.title).toBe('가상 제목');
  });

  it('판정 차례 — 다섯째 단계가 이름 길이보다 먼저', () => {
    expect(
      bads(
        `1. 가\n1.1 나\n1.1.1 다\n1.1.1.1 라\n1.1.1.1.1 ${'마'.repeat(201)}`,
      ),
    ).toEqual(['5:tooDeep']);
  });
});

describe('parsePaste — 줄', () => {
  it('빈 줄은 건너뛰되 행 번호에 센다', () => {
    const out = read('가\n\n   \n나\n1.1');
    expect(out.rows.map((row) => row.line)).toEqual([1, 4]);
    expect(out.bad).toEqual([{ line: 5, reason: 'noTitle' }]);
  });

  it.each(['\r\n', '\r', '\n'])('줄 나눔 %j', (sep) => {
    expect(shape(['가', '  나'].join(sep))).toEqual(['1:가', '2:나']);
  });

  it.each(['', '   ', '\n\n', '\t 　 \r\n'])(
    '공백만인 글 %j → empty',
    (text) => {
      expect(parsePaste(text)).toEqual({ kind: 'empty' });
    },
  );

  it('읽었는데 0줄은 empty 가 아니다', () => {
    expect(parsePaste('1.1')).toEqual<PasteRead>({
      kind: 'read',
      rows: [],
      bad: [{ line: 1, reason: 'noTitle' }],
    });
  });
});

describe('parsePaste — 맞춤', () => {
  it('「1.」 뒤 「1.1.1」 → 단계 2', () => {
    expect(shape('1. 가\n1.1.1 나')).toEqual(['1:가', '2:나']);
  });
  it('첫 줄 「1.1」 → 단계 1', () => {
    expect(shape('1.1 가\n1.1.1 나')).toEqual(['1:가', '2:나']);
  });
  it('못 읽은 줄의 아래 줄은 그 줄만 빠지고 앞 줄 아래로 붙는다', () => {
    const long = '가'.repeat(201);
    expect(shape(`1. 위\n1.1 ${long}\n1.1.1 아래\n1.2 옆`)).toEqual([
      '1:위',
      '2:아래',
      '2:옆',
    ]);
  });
  it('다섯째 단계 아래로 내어 쓴 줄은 제 단계', () => {
    expect(
      shape('1. 가\n1.1 나\n1.1.1 다\n1.1.1.1 라\n1.1.1.1.1 마\n1.1.2 바'),
    ).toEqual(['1:가', '2:나', '3:다', '4:라', '3:바']);
  });
});

/** 지어낸 지금 목차 n 줄(대 하나 + 중 n−1). */
const existing = (count: number): OutlineNode[] =>
  Array.from({ length: count }, (_, at) => ({
    key: `old${at}`,
    parentKey: at === 0 ? null : 'old0',
    depth: at === 0 ? 1 : 2,
    title: `지어낸 옛 ${at}`,
    requirement: '',
  }));

const TEXTS = [
  '1. 가\n1.1 나\n1.1.1 다\n1.1.1.1 라\n2. 마',
  '가\n  나\n    다 요구: 지어낸\n  라\n바',
  '1.1 가\n1.1.1.1 나\n가상 다\n  가상 라\n요구: 지어낸',
  '가상 하나',
];

/** 서버 규칙 — 부모가 앞, 뿌리 depth 1, 자식 = 부모 + 1 ≤ 4. */
function wireOk(nodes: readonly OutlineNode[]) {
  const depth = new Map<string, number>();
  for (const one of nodes) {
    if (one.parentKey === null) {
      if (one.depth !== 1) return false;
    } else if (depth.get(one.parentKey) !== one.depth - 1) return false;
    if (one.depth > 4) return false;
    depth.set(one.key, one.depth);
  }
  return true;
}

describe('placePaste — 불변식', () => {
  const cases = TEXTS.flatMap((text) =>
    (['append', 'replace'] as PasteHow[]).flatMap((how) =>
      [0, 1, 13].map((count) => ({ text, how, count })),
    ),
  );
  it.each(cases)('$how · 지금 $count 줄 · %#', ({ text, how, count }) => {
    const nodes = existing(count);
    const { rows } = read(text);
    const [placed, first] = placePaste(nodes, rows, how, counter());
    // ① 첫 줄
    expect(placed[0]!.depth).toBe(1);
    expect(placed[0]!.parentKey).toBeNull();
    // ② 부모가 앞, depth = 부모 + 1 ≤ 4
    expect(wireOk(placed)).toBe(true);
    // ③ key 꼴 · 겹침 0
    for (const one of placed)
      expect(one.key).toMatch(/^[a-z0-9][a-z0-9-]{0,39}$/);
    expect(new Set(placed.map((one) => one.key)).size).toBe(placed.length);
    // ④ 붙이기면 앞 줄 그대로
    if (how === 'append') {
      expect(first).toBe(nodes.length);
      nodes.forEach((one, at) => expect(placed[at]).toBe(one));
      expect(countsOf(placed).leaves).toBe(
        pasteCounts(nodes, rows, how).total.leaves,
      );
    } else {
      expect(first).toBe(0);
      expect(placed).toHaveLength(rows.length);
    }
    // ⑤ 줄 칸 문제 0 · ⑥ bodyOf 가 제목을 바꾸지 않음
    expect(problemsOf(placed).rows.size).toBe(0);
    expect(bodyOf(placed).map((one) => one.title)).toEqual(
      placed.map((one) => one.title),
    );
    expect(placed.slice(first).map((one) => one.title)).toEqual(
      rows.map((row) => row.title),
    );
  });

  it('부모 key 와 요구(잎 아닌 줄에도)', () => {
    const { rows } = read('가 요구: 위 요구\n  나\n    다\n  라');
    const [placed] = placePaste([], rows, 'replace', counter());
    expect(
      placed.map((one) => [one.key, one.parentKey, one.requirement]),
    ).toEqual([
      ['k1', null, '위 요구'],
      ['k2', 'k1', ''],
      ['k3', 'k2', ''],
      ['k4', 'k1', ''],
    ]);
  });

  it('key 는 지금 목록·avoid·이미 지은 새 key 와 겹치지 않는다(바꾸기에서도)', () => {
    const nodes = existing(2).map((one, at) => ({ ...one, key: `k${at + 1}` }));
    const avoid = [{ ...nodes[0]!, key: 'k3' }];
    // 고정 차례: k1, k2, k3(겹침) 뒤 k4 …, 그리고 같은 값을 두 번 내는 짓기
    const repeat: string[] = ['k1', 'k2', 'k3', 'k4', 'k4', 'k5'];
    const make: KeyMaker = () => repeat.shift() ?? 'zz';
    const { rows } = read('가\n나');
    const [placed] = placePaste(nodes, rows, 'replace', make, avoid);
    expect(placed.map((one) => one.key)).toEqual(['k4', 'k5']);
  });
});

/** 대제목 n 개 = 잎 n 개인 지어낸 줄. */
const flatRows = (count: number): PasteRow[] =>
  Array.from({ length: count }, (_, at) => ({
    line: at + 1,
    depth: 1,
    title: `지어낸 ${at}`,
    requirement: '',
  }));

describe('pasteCounts — 한도', () => {
  /** 지금 목차 n 줄(대 하나 + 중 n−1 → 잎 n−1). */
  const chain = (count: number) => existing(count);

  it('붙이기 지금 13 + 새 287 = 300 통과 · 288 넘음', () => {
    const nodes = chain(13);
    // 새 줄을 대·중·소·소소 사슬로 — 네 줄에 잎 하나라 잎이 한도 안
    const rows = (n: number): PasteRow[] =>
      Array.from({ length: n }, (_, at) => ({
        line: at + 1,
        depth: (at % 4) + 1,
        title: `지어낸 ${at}`,
        requirement: '',
      }));
    const ok = pasteCounts(nodes, rows(287), 'append');
    expect(ok.total.nodes).toBe(300);
    expect(ok.over).toBeNull();
    expect(pasteCounts(nodes, rows(288), 'append')).toMatchObject({
      nodes: 288,
      total: { nodes: 301 },
      over: 'nodes',
    });
  });

  it('잎 150 통과 · 151 넘음(지금 잎 + 새 잎)', () => {
    const nodes = chain(13); // 잎 12
    expect(pasteCounts(nodes, flatRows(138), 'append')).toMatchObject({
      leaves: 138,
      total: { leaves: 150 },
      over: null,
    });
    expect(pasteCounts(nodes, flatRows(139), 'append').over).toBe('leaves');
  });

  it('바꾸기는 새 것만 — 지금 290 + 새 11', () => {
    const nodes = chain(290);
    expect(pasteCounts(nodes, flatRows(11), 'append').over).toBe('nodes');
    expect(pasteCounts(nodes, flatRows(11), 'replace')).toMatchObject({
      total: { nodes: 11, leaves: 11 },
      over: null,
    });
  });

  it('둘 다 넘으면 nodes', () => {
    expect(pasteCounts([], flatRows(301), 'replace').over).toBe('nodes');
  });

  it('새 잎 셈 — 바로 뒤 줄이 더 깊지 않은 줄', () => {
    const { rows } = read('가\n  나\n    다\n  라\n바');
    expect(pasteCounts([], rows, 'append')).toMatchObject({
      nodes: 5,
      leaves: 3,
    });
  });
});
