// 결과 글 칸 고침의 순수 규칙(밴드 IRW11 — 발주서 §2 「model/edits.test.ts」). 서버 규칙(apps/api-py/esgapi/materiality/outputs/edits.py)과
// 같은 답인지 본다: 주소 꼴(서버 POINTER_PATTERN 글로 대조) · 바른 주소(★C — 서버 tests/outputs/test_edits.py 의 EDIT_BODY 를 같은 꼴
// 지어낸 본문으로 다시 지어 같은 답) · 코드포인트 경계 · url 꼴·같은 출처·비울 수 없음 · 공백만 null · 바뀐 칸만 · 칸 ↔ 고침 · 시각 글.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { parseResult } from '../api/contract/index.ts';
import {
  POINTER_PATTERN,
  canonicalItem,
  changesOf,
  checkDrafts,
  codepoints,
  editOfCell,
  editSummary,
  editedClock,
  editedStamp,
  groupsOf,
  impactFields,
  itemFields,
  itemPointer,
  lineContext,
  outgoing,
  pathwayFields,
  summaryCellPointers,
} from './edits.ts';
import type { EditField, ItemRef, ResultEdit } from './edits.ts';
import { impactLines, pathwayLines, shortlistLines } from './result.ts';
import type { MaterialityResult } from './result.ts';
import { ctx, done, fakeResult, financialRow, impactRow } from './testing.ts';

type Json = Record<string, unknown>;

const U1 = 'https://example.test/가상/하나';
const U2 = 'https://example.test/가상/둘';
const T0 = '/part2/topics/0/subtopics/0';
const T01 = '/part2/topics/0/subtopics/1';
const REG = 'context/regulations';

const it_ = (title: string, url: string | null): Json => ({
  title,
  summary: `${title}의 요약`,
  url,
});
const pathOf = (i: number | null, fin: Json | null): Json => ({
  i,
  impactDefinition: fin === null ? null : fin.impactDefinition,
  impactDriver: '가상 동인',
  businessImpact: '가상 사업 영향',
  financialImpact: '가상 재무 영향',
  impactType: fin === null ? null : fin.impactType,
  riskType: fin === null ? null : fin.riskType,
  context: fin === null ? ctx() : structuredClone(fin.context),
});
const notRun = { status: 'not_run', message: '가상 — 돌리지 않음' };

/** ★C: 서버 test_edits.py edit_body 와 같은 꼴(값은 지어낸 것). */
function editBody(): MaterialityResult {
  const i0 = impactRow(
    '가상 영향 정의 하나',
    '부정',
    ctx(
      [it_('가상 규정 A', U1), it_('가상 규정 B', '')],
      [it_('가상 사건 C', U1)],
    ),
  );
  const i1 = impactRow(
    '가상 영향 정의 둘',
    '부정',
    ctx([it_('가상 규정 A2', ` ${U1} `)]),
  );
  const f0 = financialRow(
    '가상 재무 정의 하나',
    '리스크',
    '리스크-시장',
    ctx([it_('가상 규정 D', U1), it_('가상 규정 E', U2)]),
  );
  const f1 = financialRow(
    '가상 재무 정의 둘',
    '리스크',
    '리스크-시장',
    ctx([it_('가상 규정 G', null)]),
  );
  const sub = (name: string, extra: Json) => ({
    name,
    description: '가상 설명',
    autofilled: false,
    ...extra,
  });
  const raw = fakeResult({}, [
    {
      topic: '가상토픽 하나',
      description: '가상 설명',
      subtopics: [
        sub('가상 서브토픽 가', {
          impact: done([i0, i1]),
          financial: done([f0, f1]),
          pathway: done([pathOf(1, f0), pathOf(2, f1), pathOf(null, null)]),
        }),
        sub('가상 서브토픽 나', {
          impact: done([
            impactRow(
              '가상 영향 정의 셋',
              '부정',
              ctx([it_('가상 규정 H', U2)]),
            ),
          ]),
          financial: done([
            financialRow(
              '가상 재무 정의 셋',
              '리스크',
              '리스크-시장',
              ctx([it_('가상 규정 K', U1)]),
            ),
          ]),
          pathway: notRun,
        }),
      ],
    },
    {
      topic: '가상토픽 둘',
      description: '가상 설명',
      subtopics: [
        sub('가상 서브토픽 다', {
          impact: done([
            impactRow(
              '가상 영향 정의 넷',
              '부정',
              ctx([it_('가상 규정 X', U1)]),
            ),
          ]),
          financial: notRun,
          pathway: notRun,
        }),
      ],
    },
  ]);
  const parsed = parseResult(raw);
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
}

const G1 = `${T0}/impact/rows/0/${REG}/0`;
const G2 = `${T01}/impact/rows/0/${REG}/0`;
const G3 = `${T0}/financial/rows/1/${REG}/0`;
const B = `${T0}/impact/rows/0/${REG}/1`;

/** 맥락 항목 주소 → ItemRef. */
function refOf(pointer: string): ItemRef {
  const p = pointer.split('/');
  return {
    topic: Number(p[3]),
    subtopic: Number(p[5]),
    phase: p[6] as ItemRef['phase'],
    row: Number(p[8]),
    side: p[10] as ItemRef['side'],
    k: Number(p[11]),
  };
}
const canonical = (result: MaterialityResult, pointer: string) => {
  const field = pointer.split('/').at(-1) as 'title' | 'summary' | 'url';
  const first = canonicalItem(result, refOf(pointer));
  return first === null ? null : itemPointer(first, field);
};

describe('주소 꼴', () => {
  it('POINTER_PATTERN 은 서버 contracts/edit_shapes.py 의 글과 같다', () => {
    const source = readFileSync(
      resolve(
        dirname(fileURLToPath(import.meta.url)),
        '../../../../../api-py/esgapi/materiality/contracts/edit_shapes.py',
      ),
      'utf8',
    );
    const n = /_N = "([^"]+)"/.exec(source)![1]!;
    const block = /POINTER_PATTERN: Final = \(([\s\S]*?)\n\)/.exec(source)![1]!;
    const text = [...block.matchAll(/f?"([^"]*)"/g)]
      .map((m) => m[1]!)
      .join('')
      .replaceAll('{_N}', n);
    expect(POINTER_PATTERN.source).toBe(text.replaceAll('/', '\\/'));
    expect(POINTER_PATTERN.test(`${T0}/impact/rows/0/impactDefinition`)).toBe(
      true,
    );
    expect(POINTER_PATTERN.test(`${T0}/impact/rows/0/impactDriver`)).toBe(
      false,
    );
    expect(POINTER_PATTERN.test(`${T0}/impact/rows/01/impactDefinition`)).toBe(
      false,
    );
    expect(
      POINTER_PATTERN.test(`${T0}/financial/rows/0/impactDefinition`),
    ).toBe(false);
  });
});

describe('바른 주소(★C — 서버 test_canonical_pointer 와 같은 답)', () => {
  const body = editBody();
  it.each([
    [`${T0}/impact/rows/0/${REG}/0/title`, `${G1}/title`],
    [`${T0}/impact/rows/1/${REG}/0/title`, `${G1}/title`],
    [`${T0}/financial/rows/0/${REG}/0/summary`, `${G1}/summary`],
    [`${T01}/financial/rows/0/${REG}/0/url`, `${G1}/url`],
    [`${T0}/pathway/rows/0/${REG}/0/title`, `${G1}/title`],
    [`${T0}/financial/rows/0/${REG}/1/title`, `${G2}/title`],
    [`${T0}/pathway/rows/0/${REG}/1/title`, `${G2}/title`],
    [`${T0}/financial/rows/1/${REG}/0/title`, `${G3}/title`],
    [`${T0}/pathway/rows/1/${REG}/0/title`, `${G3}/title`],
    [`${B}/title`, `${B}/title`],
    [
      '/part2/topics/1/subtopics/0/impact/rows/0/context/regulations/0/title',
      '/part2/topics/1/subtopics/0/impact/rows/0/context/regulations/0/title',
    ],
  ])('%s → %s', (given, first) => {
    expect(canonical(body, given)).toBe(first);
  });

  it('pathway: i null · k 가 재무 항목 범위 밖이면 고칠 수 없음(null)', () => {
    expect(canonical(body, `${T0}/pathway/rows/2/${REG}/0/title`)).toBeNull();
    expect(canonical(body, `${T0}/pathway/rows/1/${REG}/1/title`)).toBeNull();
  });

  it('묶음: 첫 자리 · impact+financial 수(pathway 사본은 세지 않음) · 지금 url', () => {
    expect(
      groupsOf(body, 0, 'regulations').map((g) => [
        itemPointer(g.first, 'url'),
        g.members,
        g.url,
      ]),
    ).toEqual([
      [`${G1}/url`, 4, U1],
      [`${B}/url`, 1, null],
      [`${G2}/url`, 2, U2],
      [`${G3}/url`, 1, null],
    ]);
  });

  it('1-1 칸의 항목 자리(MergedItem.at)는 묶음 첫 자리다(mergedItems 와 같은 차례)', () => {
    const [line] = shortlistLines(body);
    expect(
      line!.regulation.items.map((item) => {
        const fields = itemFields(body, 0, item)!;
        return [item.label, fields.title.pointer];
      }),
    ).toEqual([
      ['both', `${G1}/title`],
      ['social', `${B}/title`],
      ['both', `${G2}/title`],
      ['financial', `${G3}/title`],
    ]);
  });

  it('2-1·2-2 요약 칸: 2-1 은 자기 묶음, 2-2 는 재무 항목의 묶음으로(fin null 줄은 null)', () => {
    const [first] = impactLines(body);
    expect(
      impactFields(body, first!).summaries.map((f) => f?.pointer ?? null),
    ).toEqual([
      `${G1}/summary`,
      `${B}/summary`,
      `${T0}/impact/rows/0/context/controversies/0/summary`,
    ]);
    const lines = pathwayLines(body);
    expect(lines.map((line) => line.fin)).toEqual([0, 1, null]);
    expect(
      pathwayFields(body, lines[0]!).summaries.map((f) => f?.pointer ?? null),
    ).toEqual([`${G1}/summary`, `${G2}/summary`]);
    expect(
      pathwayFields(body, lines[1]!).summaries.map((f) => f?.pointer),
    ).toEqual([`${G3}/summary`]);
    expect(pathwayFields(body, lines[0]!).rows.driver.pointer).toBe(
      `${T0}/pathway/rows/0/impactDriver`,
    );
  });
});

const field = (
  pointer: string,
  kind: EditField['kind'],
  value: string | null,
  extra: Partial<EditField> = {},
): EditField => ({ pointer, kind, value, ...extra });

describe('값 검사(서버 _value·check 와 같은 규칙)', () => {
  const body = editBody();
  const DEF = `${T0}/impact/rows/0/impactDefinition`;

  it('길이는 코드포인트: 서로게이트 짝 4,000 통과 · 4,001 거절, title 1,000 · url 2,048', () => {
    expect(codepoints('😀'.repeat(4000))).toBe(4000);
    const check = (kind: EditField['kind'], text: string) =>
      checkDrafts(body, [field(DEF, kind, null)], { [DEF]: text })[DEF];
    expect(check('impactDefinition', '😀'.repeat(4000))).toBeUndefined();
    expect(check('impactDefinition', '😀'.repeat(4001))).toBe('tooLong');
    expect(check('summary', 'ㄱ'.repeat(4001))).toBe('tooLong');
    expect(check('title', 'ㄱ'.repeat(1000))).toBeUndefined();
    expect(check('title', 'ㄱ'.repeat(1001))).toBe('titleTooLong');
    expect(check('url', `https://${'a'.repeat(2040)}`)).toBeUndefined();
    expect(check('url', `https://${'a'.repeat(2041)}`)).toBe('urlTooLong');
  });

  it('url 꼴: trim 이 http(s):// 로 시작 · 공백만이면 null(비움)', () => {
    const urls = itemFields(
      body,
      0,
      shortlistLines(body)[0]!.regulation.items[1]!,
    )!.url;
    const check = (text: string) =>
      checkDrafts(body, [urls], { [urls.pointer]: text })[urls.pointer];
    expect(check('  https://example.test/새 ')).toBeUndefined();
    expect(check('HTTP://example.test')).toBe('urlScheme');
    expect(check('javascript:alert(1)')).toBe('urlScheme');
    expect(check('   ')).toBeUndefined();
  });

  it('같은 출처: 같은 토픽·쪽의 다른 묶음 url(strip)과 같으면 거절 · 다른 쪽·다른 토픽은 지남 · 같은 저장의 다른 고침도 본다', () => {
    const [line] = shortlistLines(body);
    const items = line!.regulation.items;
    const g3 = itemFields(body, 0, items[3]!)!.url;
    const b = itemFields(body, 0, items[1]!)!.url;
    const g2 = itemFields(body, 0, items[2]!)!.url;
    expect(checkDrafts(body, [g3], { [g3.pointer]: ` ${U2}` })).toEqual({
      [g3.pointer]: 'urlDuplicate',
    });
    expect(checkDrafts(body, [b], { [b.pointer]: U1 })).toEqual({
      [b.pointer]: 'urlDuplicate',
    });
    // 같은 저장에서 G2 를 비켜 주면 G3 가 U2 를 가질 수 있다
    expect(
      checkDrafts(body, [g2, g3], {
        [g2.pointer]: 'https://example.test/가상/새',
        [g3.pointer]: U2,
      }),
    ).toEqual({});
    const controversy = itemFields(body, 0, line!.controversy.items[0]!)!.url;
    expect(
      checkDrafts(body, [controversy], { [controversy.pointer]: U2 }),
    ).toEqual({});
  });

  it('비울 수 없음: 묶음의 impact+financial 이 둘 이상이면 거절, 하나면 지남', () => {
    const items = shortlistLines(body)[0]!.regulation.items;
    const g1 = itemFields(body, 0, items[0]!)!.url;
    const g3 = itemFields(body, 0, items[3]!)!.url;
    expect(checkDrafts(body, [g1], { [g1.pointer]: '  ' })).toEqual({
      [g1.pointer]: 'urlLocked',
    });
    expect(
      checkDrafts(body, [g3], { [g3.pointer]: 'https://example.test/x' }),
    ).toEqual({});
    const b = itemFields(body, 0, items[1]!)!.url;
    expect(checkDrafts(body, [b], { [b.pointer]: '' })).toEqual({});
  });

  it('보낼 값: 공백만 null, 아니면 쓴 글 그대로 · 바뀐 칸만(null 은 빈 글로 견줌) · 같은 바른 주소는 하나', () => {
    expect(outgoing(' \n\t')).toBeNull();
    expect(outgoing('  가상 글 ')).toBe('  가상 글 ');
    const fields = [
      field('/a', 'summary', null),
      field('/b', 'summary', '그대로'),
      field('/c', 'summary', '원문'),
      field('/c', 'summary', '원문'),
    ];
    expect(changesOf(fields, { '/a': '', '/b': '그대로', '/c': '  ' })).toEqual(
      [{ pointer: '/c', value: null }],
    );
    expect(
      changesOf(fields, { '/a': ' 새 글', '/b': '그대로', '/c': '원문' }),
    ).toEqual([{ pointer: '/a', value: ' 새 글' }]);
  });
});

describe('칸 ↔ 고침 · 시각 글', () => {
  const edit = (
    pointer: string,
    editedAt: string,
    name = '담당자 A',
  ): ResultEdit => ({
    pointer,
    value: '가상',
    original: '가상 원문',
    editedAt,
    editedBy: { name },
  });

  it('주소가 하나라도 겹치면 고친 칸 · 사람·때는 가장 늦은 고침', () => {
    const edits = [
      edit('/x', '2026-11-03T14:28:05+09:00'),
      edit('/y', '2026-11-03T15:01:00+09:00', '담당자 B'),
    ];
    expect(editOfCell(['/z'], edits)).toBeNull();
    expect(editOfCell(['/x', '/y'], edits)!.editedBy.name).toBe('담당자 B');
    expect(editSummary([['/x'], ['/y'], ['/z']], edits)).toEqual({
      count: 2,
      latest: edits[1],
    });
  });

  it('비운 요약도 그 칸 주소에 든다(연필이 붙게)', () => {
    const body = editBody();
    const [line] = impactLines(body);
    const emptied = structuredClone(body);
    const sub =
      emptied.part2.status === 'done' ?
        emptied.part2.topics[0]!.subtopics[0]!
      : null;
    if (sub?.impact.status === 'done')
      sub.impact.rows[0]!.context.controversies[0]!.summary = null;
    const [after] = impactLines(emptied);
    expect(after!.summaries).toHaveLength(2);
    expect(
      summaryCellPointers(
        emptied,
        after!,
        'impact',
        lineContext(emptied, after!, 'impact'),
      ),
    ).toContain(`${T0}/impact/rows/0/context/controversies/0/summary`);
    expect(line!.summaries).toHaveLength(3);
  });

  it('시각: +09:00 ISO 글에서 MM-DD HH:mm · HH:mm 를 뗀다(Date 셈 0), 꼴 밖은 「–」', () => {
    expect(editedStamp('2026-11-03T14:28:05+09:00')).toBe('11-03 14:28');
    expect(editedClock('2026-11-03T14:28:05+09:00')).toBe('14:28');
    expect(editedStamp('2026-11-03T23:59:59+09:00')).toBe('11-03 23:59');
    expect(editedStamp('어제')).toBe('–');
    expect(editedClock('')).toBe('–');
  });
});
