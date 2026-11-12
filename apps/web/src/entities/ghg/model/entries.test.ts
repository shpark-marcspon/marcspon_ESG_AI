// Scope 1·2 입력 셈(밴드 W12-1a ② — 발주서 §3 4): slotsOf · rowBody(보내는 칸 규칙 — 추정만 바뀐 칸도 금액, 행은 늘 unit·na·siteFacilityId,
//   새 행 rowId 0, id 정수) · saveBody · fieldOf(본문 차례) · checkAmount · addable · formatAmount(글자 반올림) · addAmounts·cardOf(글자 합 — 뜨는 소수 0) · listSpans(세로 합침).
import { describe, expect, it } from 'vitest';

import {
  ENTRY_UPLOAD_MAX_BYTES,
  acceptEntryUpload,
  addAmounts,
  addable,
  cardOf,
  checkAmount,
  draftEdited,
  draftProblems,
  entryAtText,
  estimatedOn,
  fieldOf,
  formatAmount,
  isKnownHistoryKind,
  listSpans,
  mergeSiteDraft,
  newRowDraft,
  rowBody,
  rowDraftOf,
  saveBody,
  slotHeadOf,
  slotsOf,
  uploadOutcome,
  uploadProblems,
  withEstimated,
} from './index.ts';
import type {
  EntryListRow,
  EntryRow,
  EntryRowDraft,
  EntryRowEdit,
  EntryScope,
  EntrySite,
} from './index.ts';

const row = (over: Partial<EntryRow> = {}): EntryRow => ({
  rowId: '7',
  siteFacilityId: '3',
  detailName: '1호기',
  unit: 'kL',
  na: false,
  values: [
    { slot: '2025-01', amount: '12.5', estimated: false },
    { slot: '2025-02', amount: null, estimated: false },
  ],
  emission: '1.5',
  emissionProblem: null,
  factor: null,
  ...over,
});
const edit = (before: EntryRow, over: Partial<EntryRowEdit> = {}) => ({
  rowId: before.rowId,
  siteFacilityId: before.siteFacilityId,
  unit: before.unit,
  na: before.na,
  values: before.values.map((slot) => ({ ...slot })),
  ...over,
});

describe('slotsOf', () => {
  it('그 해 달 열둘(「YYYY-MM」, 차례)', () => {
    const slots = slotsOf(2025);
    expect(slots).toHaveLength(12);
    expect(slots[0]).toBe('2025-01');
    expect(slots[11]).toBe('2025-12');
  });
});

describe('rowBody · saveBody — 보내는 칸 규칙', () => {
  it('바뀐 것 없음 → null(보낼 것 없음)', () => {
    const before = row();
    expect(rowBody(before, edit(before))).toBeNull();
  });

  it('금액 바뀐 칸만 · 실은 칸은 amount·estimated 둘 다 · 행은 늘 unit·na·siteFacilityId · id 정수 · 금액 글자', () => {
    const before = row();
    const body = rowBody(
      before,
      edit(before, {
        values: [
          { slot: '2025-01', amount: '12.5', estimated: false },
          { slot: '2025-02', amount: '0.000001', estimated: false },
        ],
      }),
    );
    expect(body).toStrictEqual({
      rowId: 7,
      siteFacilityId: 3,
      unit: 'kL',
      na: false,
      values: [{ slot: '2025-02', amount: '0.000001', estimated: false }],
    });
    expect(typeof body!.values[0]!.amount).toBe('string');
  });

  it('추정만 바뀐 칸도 금액(지금 글자)을 싣는다 — 빠지면 서버가 null 로 덮음', () => {
    const before = row();
    const body = rowBody(
      before,
      edit(before, {
        values: [
          { slot: '2025-01', amount: '12.5', estimated: true },
          { slot: '2025-02', amount: null, estimated: false },
        ],
      }),
    );
    expect(body!.values).toStrictEqual([
      { slot: '2025-01', amount: '12.5', estimated: true },
    ]);
    expect(Object.keys(body!.values[0]!).sort()).toEqual([
      'amount',
      'estimated',
      'slot',
    ]);
  });

  it('지운 칸은 amount null 로 · 단위·N/A 만 바뀌어도 행(칸 0)을 보낸다', () => {
    const before = row();
    expect(
      rowBody(
        before,
        edit(before, {
          values: [
            { slot: '2025-01', amount: null, estimated: false },
            { slot: '2025-02', amount: null, estimated: false },
          ],
        }),
      )!.values,
    ).toStrictEqual([{ slot: '2025-01', amount: null, estimated: false }]);
    const unit = rowBody(before, edit(before, { unit: 'L' }))!;
    expect(unit).toStrictEqual({
      rowId: 7,
      siteFacilityId: 3,
      unit: 'L',
      na: false,
      values: [],
    });
    const na = rowBody(before, edit(before, { na: true }))!;
    expect([na.na, na.unit, na.siteFacilityId]).toEqual([true, 'kL', 3]);
  });

  it('새 행: rowId 열쇠 없음 · 값 있는 칸만(빈 칸 기본은 null·거짓) · 값 없어도 보냄', () => {
    const fresh: EntryRowEdit = {
      rowId: null,
      siteFacilityId: '4',
      unit: 'kL',
      na: false,
      values: [
        { slot: '2025-03', amount: '1', estimated: false },
        { slot: '2025-04', amount: null, estimated: false },
        { slot: '2025-05', amount: null, estimated: true },
      ],
    };
    const body = rowBody(null, fresh)!;
    expect('rowId' in body).toBe(false);
    expect(body).toStrictEqual({
      siteFacilityId: 4,
      unit: 'kL',
      na: false,
      values: [
        { slot: '2025-03', amount: '1', estimated: false },
        { slot: '2025-05', amount: null, estimated: true },
      ],
    });
    expect(rowBody(null, { ...fresh, values: [] })).toStrictEqual({
      siteFacilityId: 4,
      unit: 'kL',
      na: false,
      values: [],
    });
  });

  it('id 가 정수 글자가 아니면 던진다(어댑터 전에 막힘)', () => {
    const before = row({ rowId: 'x' });
    expect(() => rowBody(before, edit(before, { na: true }))).toThrow();
  });

  it('saveBody: 보낼 것 없는 행은 빼고 차례 그대로', () => {
    const a = row();
    const b = row({ rowId: '8', siteFacilityId: '5' });
    const body = saveBody([
      { before: a, edited: edit(a) },
      { before: b, edited: edit(b, { na: true }) },
    ]);
    expect(body.rows.map((r) => r.rowId)).toEqual([8]);
  });
});

describe('fieldOf — 422 칸 열쇠를 본문 차례로', () => {
  const body = {
    rows: [
      {
        rowId: 7,
        siteFacilityId: 3,
        unit: 'kL',
        na: false,
        values: [{ slot: '2025-01', amount: '1', estimated: false }],
      },
      {
        siteFacilityId: 4,
        unit: 'kL',
        na: false,
        values: [
          { slot: '2025-03', amount: '1', estimated: false },
          { slot: '2025-04', amount: 'x', estimated: false },
        ],
      },
    ],
  };

  it('rows.<i>.values.<j>.amount → 본문 i 행·j 칸의 달', () => {
    expect(fieldOf('rows.1.values.1.amount', body)).toStrictEqual({
      row: 1,
      rowId: null,
      siteFacilityId: '4',
      slot: '2025-04',
      field: 'amount',
    });
    expect(fieldOf('rows.1.values.0.slot', body)!.slot).toBe('2025-03');
  });

  it('행 칸(unit·siteFacilityId·rowId) → slot null · 그 밖 열쇠·없는 자리 → null', () => {
    expect(fieldOf('rows.0.unit', body)).toStrictEqual({
      row: 0,
      rowId: '7',
      siteFacilityId: '3',
      slot: null,
      field: 'unit',
    });
    expect(fieldOf('rows.0.rowId', body)!.field).toBe('rowId');
    expect(fieldOf('rows.0.siteFacilityId', body)!.rowId).toBe('7');
    for (const key of [
      'memo',
      'decimals',
      'q',
      'rows',
      'rows.2.unit',
      'rows.0.values.5.amount',
    ])
      expect(fieldOf(key, body), key).toBeNull();
  });
});

describe('checkAmount · addable · 히스토리 종류', () => {
  it('0 이상 · 지수 0 · 정수 18자리 · 소수 6자리(서버 사본)', () => {
    for (const ok of ['0', '12', '0.000001', '123456789012345678.5'])
      expect(checkAmount(ok), ok).toBeNull();
    for (const bad of [
      '',
      '-1',
      '1e3',
      '1.',
      '.5',
      ' 1',
      '1234567890123456789',
    ])
      expect(checkAmount(bad), bad).toBe('format');
    expect(checkAmount('0.0000001')).toBe('decimals');
    // GX2 S12-03: 쉼표는 글만 가른다(받지 않음).
    for (const comma of ['1,000', '1,000.5', ','])
      expect(checkAmount(comma), comma).toBe('comma');
  });

  it('addable: 행 없는 자산/시설만(서버 차례)', () => {
    expect(
      addable({
        siteId: '2',
        siteName: '제1공장',
        rows: [],
        period: 'month',
        slots: [],
        facilities: [
          { id: '3', detailName: '1호기', hasRow: true },
          { id: '4', detailName: '2호기', hasRow: false },
        ],
      }).map((f) => f.id),
    ).toEqual(['4']);
  });

  it('아는 종류 여섯 밖은 모름(그래도 꼴 실패 아님 — 어댑터 시험)', () => {
    expect(
      ['value', 'na_on', 'na_off', 'unit', 'period', 'factor'].every(
        isKnownHistoryKind,
      ),
    ).toBe(true);
    expect(isKnownHistoryKind('mystery')).toBe(false);
  });
});

describe('formatAmount — 표시 반올림(글자 셈, half-up)', () => {
  it('null → 「-」 · 0 → 「0」 · 자릿수 안이면 그대로(끝 0 붙이지 않음)', () => {
    expect(formatAmount(null, 2)).toBe('-');
    expect(formatAmount('0', 2)).toBe('0');
    expect(formatAmount('1354.6', 2)).toBe('1354.6');
    expect(formatAmount('522', 0)).toBe('522');
  });

  it('반 올림: 1.005 → 1.01 · 2.5(0자리) → 3 · 9.995 → 10 · 0.004 → 0 · 1.2349 → 1.23', () => {
    expect(formatAmount('1.005', 2)).toBe('1.01');
    expect(formatAmount('2.5', 0)).toBe('3');
    expect(formatAmount('9.995', 2)).toBe('10');
    expect(formatAmount('0.004', 2)).toBe('0');
    expect(formatAmount('1.2349', 2)).toBe('1.23');
    expect(formatAmount('1.2', 3)).toBe('1.2');
  });

  it('20자리 수도 글자 그대로(뜨는 수 오차 0)', () => {
    expect(formatAmount('12345678901234567890.125', 2)).toBe(
      '12345678901234567890.13',
    );
    expect(formatAmount('99999999999999999999.995', 2)).toBe(
      '100000000000000000000',
    );
  });
});

describe('addAmounts · cardOf — 글자 십진 합', () => {
  it('0.1 + 0.2 = 0.3 · 받아올림 · 20자리', () => {
    expect(addAmounts('0.1', '0.2')).toBe('0.3');
    expect(addAmounts('99.9', '0.1')).toBe('100');
    expect(addAmounts('12345678901234567890', '1.5')).toBe(
      '12345678901234567891.5',
    );
    expect(addAmounts('0', '0')).toBe('0');
    expect(addAmounts('1', 'x')).toBeNull();
  });

  const scope = (
    scopeId: string,
    scopeName: string,
    value: string | null,
  ): EntryScope => ({
    scopeId,
    scopeName,
    values: { '2024': '9', '2025': value },
    rows: [],
  });

  it('배출범위마다 그 해 값 · 합 · 고리 몫(표시만)', () => {
    const card = cardOf(
      [scope('1', 'Scope 1', '0.1'), scope('2', 'Scope 2', '0.2')],
      2025,
    );
    expect(card.total).toBe('0.3');
    expect(card.scopes.map((s) => [s.scopeName, s.value])).toEqual([
      ['Scope 1', '0.1'],
      ['Scope 2', '0.2'],
    ]);
    expect(card.scopes[0]!.share).toBeCloseTo(1 / 3);
    expect(card.scopes[1]!.share).toBeCloseTo(2 / 3);
  });

  it('값 없는 범위는 몫 0 · 다 없으면 합 null · 합 0 이면 몫 0 · 20자리 합', () => {
    const one = cardOf(
      [scope('1', 'Scope 1', '5'), scope('2', 'Scope 2', null)],
      2025,
    );
    expect([one.total, one.scopes[1]!.share]).toEqual(['5', 0]);
    expect(cardOf([scope('1', 'Scope 1', null)], 2025).total).toBeNull();
    expect(cardOf([scope('1', 'Scope 1', '0')], 2025).scopes[0]!.share).toBe(0);
    expect(
      cardOf(
        [
          scope('1', 'Scope 1', '12345678901234567890.1'),
          scope('2', 'Scope 2', '0.2'),
        ],
        2025,
      ).total,
    ).toBe('12345678901234567890.3');
  });

  it('꼴이 아닌 값이 하나라도 있으면 합 null — 뒤 값으로 다시 시작하지 않음', () => {
    expect(
      cardOf(
        [
          scope('1', 'Scope 1', '1'),
          scope('2', 'Scope 2', '지어낸'),
          scope('3', 'Scope 3', '2'),
        ],
        2025,
      ).total,
    ).toBeNull();
    expect(
      cardOf([scope('1', 'Scope 1', 'x'), scope('2', 'Scope 2', '2')], 2025)
        .total,
    ).toBeNull();
    // 꼴 아닌 값 하나뿐이어도 합 null(검증 R1)
    expect(cardOf([scope('1', 'Scope 1', 'x')], 2025).total).toBeNull();
  });
});

describe('listSpans — 배출원 유형·배출활동 세로 합침(서버 차례 그대로)', () => {
  const line = (
    id: string,
    source: string,
    activity: string,
  ): EntryListRow => ({
    nodeId: id,
    path: ['Scope 1', source, activity, `지어낸 시설 ${id}`],
    values: {},
    hasMemo: false,
    estimated: false,
    locked: false,
  });

  it('이웃한 같은 유형·활동은 첫 줄에 줄 수, 덮인 줄은 0 · 활동 묶음은 유형 경계에서 끊김', () => {
    expect(
      listSpans([
        line('1', '지어낸 고정연소', '지어낸 액체연료'),
        line('2', '지어낸 고정연소', '지어낸 액체연료'),
        line('3', '지어낸 고정연소', '지어낸 기체연료'),
        line('4', '지어낸 이동연소', '지어낸 기체연료'),
      ]),
    ).toStrictEqual([
      { source: 3, activity: 2 },
      { source: 0, activity: 0 },
      { source: 0, activity: 1 },
      { source: 1, activity: 1 },
    ]);
  });

  it('떨어진 같은 이름은 다른 묶음(차례를 다시 매기지 않음) · 빈 목록 → 빈 목록', () => {
    expect(
      listSpans([
        line('1', '지어낸 고정연소', '지어낸 액체연료'),
        line('2', '지어낸 이동연소', '지어낸 도로수송'),
        line('3', '지어낸 고정연소', '지어낸 액체연료'),
      ]),
    ).toStrictEqual([
      { source: 1, activity: 1 },
      { source: 1, activity: 1 },
      { source: 1, activity: 1 },
    ]);
    expect(listSpans([])).toStrictEqual([]);
  });
});

describe('S3 상세 도움(밴드 W12-1b ①)', () => {
  const slots = ['2025-01', '2025-02', '2025-03'];
  const site = (over: Partial<EntrySite> = {}): EntrySite => ({
    siteId: '2',
    siteName: '제1공장',
    period: 'month',
    slots,
    facilities: [
      { id: '3', detailName: '1호기', hasRow: true },
      { id: '9', detailName: '2호기', hasRow: false },
    ],
    rows: [row()],
    ...over,
  });

  it('entryAtText: 한국 시각 · 날짜 넘어감 · 읽을 수 없으면 그대로', () => {
    expect(entryAtText('2026-01-02T03:04:05Z')).toBe('2026-01-02 12:04');
    expect(entryAtText('2026-01-02T20:00:00Z')).toBe('2026-01-03 05:00');
    expect(entryAtText('2026-01-02T12:04:05+09:00')).toBe('2026-01-02 12:04');
    expect(entryAtText('이상한 글')).toBe('이상한 글');
  });

  it('slotHeadOf: 월·분기·연 · 꼴 밖 null', () => {
    expect(slotHeadOf('2025-03')).toEqual({ kind: 'month', n: 3 });
    expect(slotHeadOf('2025-Q2')).toEqual({ kind: 'quarter', n: 2 });
    expect(slotHeadOf('2025')).toEqual({ kind: 'year' });
    expect(slotHeadOf('2025-Q5')).toBeNull();
    expect(slotHeadOf('이상')).toBeNull();
  });

  it('rowDraftOf: 칸은 slots 만(없는 칸 빈 칸 · slots 밖 칸 뺌) · 그대로면 고침 없음 · rowBody null', () => {
    const before = row({
      values: [
        { slot: '2025-02', amount: '1', estimated: true },
        { slot: '2025-Q1', amount: '9', estimated: false },
      ],
    });
    const draft = rowDraftOf(before, slots);
    expect(draft.key).toBe('r7');
    expect(draft.edited.values).toEqual([
      { slot: '2025-01', amount: null, estimated: false },
      { slot: '2025-02', amount: '1', estimated: true },
      { slot: '2025-03', amount: null, estimated: false },
    ]);
    expect(draftEdited(draft)).toBe(false);
    expect(rowBody(draft.before, draft.edited)).toBeNull();
  });

  it('draftEdited: 추정만 바꾼 칸도 고침(나가기 확인·다른 블록 저장 때 지킴 — 검증 R1)', () => {
    const draft = rowDraftOf(row(), slots);
    const flagged: EntryRowDraft = {
      ...draft,
      edited: {
        ...draft.edited,
        values: draft.edited.values.map((value) =>
          value.slot === '2025-01' ? { ...value, estimated: true } : value,
        ),
      },
    };
    expect(draftEdited(flagged)).toBe(true);
    const kept = mergeSiteDraft([flagged], site({ rows: [row()] }));
    expect(kept[0]!.edited.values[0]!.estimated).toBe(true);
  });

  it('S12-03 estimatedOn·withEstimated: 켜짐 = N/A 아닌 줄 칸 하나라도 · 켬은 N/A 아닌 줄의 빈 칸까지 · 끔은 N/A 줄까지 · 바뀌는 칸 없으면 같은 초안', () => {
    const plain = newRowDraft(
      { id: '9', detailName: '2호기', hasRow: false },
      'kL',
      slots,
    );
    const na: EntryRowDraft = {
      ...plain,
      key: 'n10',
      edited: {
        ...plain.edited,
        na: true,
        values: plain.edited.values.map((value, at) =>
          at === 0 ? { ...value, estimated: true } : value,
        ),
      },
    };
    expect(estimatedOn([plain])).toBe(false);
    expect(estimatedOn([na])).toBe(false); // N/A 줄 추정은 셈 밖
    const on = withEstimated(plain, true);
    expect(on.edited.values.every((value) => value.estimated)).toBe(true);
    expect(on.edited.values.every((value) => value.amount === null)).toBe(true);
    expect(estimatedOn([on, na])).toBe(true);
    expect(withEstimated(na, true)).toBe(na); // N/A 줄은 켜지 않음
    const off = withEstimated(na, false);
    expect(off.edited.values.every((value) => !value.estimated)).toBe(true);
    expect(withEstimated(plain, false)).toBe(plain);
    const mixed: EntryRowDraft = {
      ...plain,
      edited: {
        ...plain.edited,
        values: plain.edited.values.map((value, at) =>
          at === 1 ? { ...value, amount: '3', estimated: true } : value,
        ),
      },
    };
    expect(estimatedOn([mixed])).toBe(true);
    const cleared = withEstimated(mixed, false);
    expect(cleared.edited.values[1]).toEqual({
      slot: mixed.edited.values[1]!.slot,
      amount: '3',
      estimated: false,
    });
  });

  it('newRowDraft: 늘 고침 · rowId 없이 나감', () => {
    const draft = newRowDraft(
      { id: '9', detailName: '2호기', hasRow: false },
      'kL',
      slots,
    );
    expect(draft.key).toBe('n9');
    expect(draftEdited(draft)).toBe(true);
    expect(rowBody(draft.before, draft.edited)).toEqual({
      siteFacilityId: 9,
      unit: 'kL',
      na: false,
      values: [],
    });
  });

  it('mergeSiteDraft: 고친 칸·unit·na 만 지키고 손대지 않은 것은 새 서버 값 — 본문에 남의 칸이 실리지 않는다(가지 리뷰)', () => {
    const [jan, feb] = slots;
    const before = row({
      values: [
        { slot: jan!, amount: '1', estimated: false },
        { slot: feb!, amount: '2', estimated: false },
      ],
    });
    const draft = rowDraftOf(before, slots);
    const typed: EntryRowDraft = {
      ...draft,
      edited: {
        ...draft.edited,
        values: draft.edited.values.map((value) =>
          value.slot === jan ? { ...value, amount: '7' } : value,
        ),
      },
    };
    const fresh = row({
      unit: 'L',
      na: true,
      values: [
        { slot: jan!, amount: '1', estimated: false },
        { slot: feb!, amount: '9', estimated: true },
      ],
    });
    const [merged] = mergeSiteDraft([typed], site({ rows: [fresh] }));
    const cell = (slot: string) =>
      merged!.edited.values.find((value) => value.slot === slot);
    expect(cell(jan!)).toMatchObject({ amount: '7', estimated: false });
    expect(cell(feb!)).toMatchObject({ amount: '9', estimated: true });
    expect([merged!.edited.unit, merged!.edited.na]).toEqual(['L', true]);
    expect(
      rowBody(merged!.before, merged!.edited)!.values.map(
        (value) => value.slot,
      ),
    ).toEqual([jan]);
  });

  it('mergeSiteDraft: 고친 unit·na 는 지킨다', () => {
    const draft = rowDraftOf(row(), slots);
    const [merged] = mergeSiteDraft(
      [{ ...draft, edited: { ...draft.edited, unit: 'L', na: true } }],
      site({ rows: [row({ unit: 'kg' })] }),
    );
    expect([merged!.edited.unit, merged!.edited.na]).toEqual(['L', true]);
  });

  it('mergeSiteDraft: 고친 행은 지키고 before 만 새것 · 안 고친 행은 응답 · 없어진 행 빠짐 · 새 행은 자리가 비었을 때만', () => {
    const edited = rowDraftOf(row(), slots);
    const typed: EntryRowDraft = {
      ...edited,
      edited: { ...edited.edited, unit: 'L' },
    };
    const fresh = row({ emission: '2.5' });
    const merged = mergeSiteDraft([typed], site({ rows: [fresh] }));
    expect(merged[0]!.edited.unit).toBe('L');
    expect(merged[0]!.before).toBe(fresh);
    const clean = mergeSiteDraft(
      [rowDraftOf(row({ unit: 'old' }), slots)],
      site({ rows: [fresh] }),
    );
    expect(clean[0]!.edited.unit).toBe('kL');
    expect(mergeSiteDraft([typed], site({ rows: [] }))).toEqual([]);
    const free = newRowDraft(
      { id: '9', detailName: '2호기', hasRow: false },
      'kL',
      slots,
    );
    const taken = newRowDraft(
      { id: '3', detailName: '1호기', hasRow: true },
      'kL',
      slots,
    );
    expect(
      mergeSiteDraft([free, taken], site({ rows: [] })).map((d) => d.key),
    ).toEqual(['n9']);
  });

  it('draftProblems: 바뀐 칸만 · 화면 차례 · 안 바뀐 서버 글자는 안 잼', () => {
    const before = row({
      values: [{ slot: '2025-01', amount: '1.00000000', estimated: false }],
    });
    const draft = rowDraftOf(before, slots);
    expect(draftProblems([draft])).toEqual([]);
    const typed: EntryRowDraft = {
      ...draft,
      edited: {
        ...draft.edited,
        values: draft.edited.values.map((value) =>
          value.slot === '2025-02' ? { ...value, amount: '-1' }
          : value.slot === '2025-03' ? { ...value, amount: '0.1234567' }
          : value,
        ),
      },
    };
    expect(draftProblems([typed])).toEqual([
      { key: 'r7', slot: '2025-02', problem: 'format' },
      { key: 'r7', slot: '2025-03', problem: 'decimals' },
    ]);
  });
});

describe('일괄 올리기 셈(W12-5 ①)', () => {
  it('acceptEntryUpload: 형식 먼저 · .xlsx 만(대소문자 무시) · 딱 상한은 지남 · 1 넘으면 size', () => {
    const at = (name: string, size: number) =>
      acceptEntryUpload({ name, size });
    expect(ENTRY_UPLOAD_MAX_BYTES).toBe(20_971_520);
    expect(at('a.xlsx', ENTRY_UPLOAD_MAX_BYTES)).toBeNull();
    expect(at('A.XLSX', 1)).toBeNull();
    expect(at('a.xlsx', ENTRY_UPLOAD_MAX_BYTES + 1)).toBe('size');
    expect(at('a.xls', 1)).toBe('type');
    expect(at('a.csv', ENTRY_UPLOAD_MAX_BYTES + 1)).toBe('type');
  });

  it('uploadProblems: 받은 차례 · 시트 주소만 자리 · file·모르는 열쇠는 자리 없음 · 글 여럿은 줄 여럿 · more 는 맨 끝', () => {
    expect(
      uploadProblems({
        more: ['지어낸 더 있음'],
        '월!C3': ['지어낸 하나', '지어낸 둘'],
        file: ['지어낸 파일'],
        '년도!AA12': ['지어낸 셋'],
        year: ['지어낸 모름'],
      }),
    ).toEqual([
      { where: '월 시트 C3', text: '지어낸 하나' },
      { where: '월 시트 C3', text: '지어낸 둘' },
      { where: null, text: '지어낸 파일' },
      { where: '년도 시트 AA12', text: '지어낸 셋' },
      { where: null, text: '지어낸 모름' },
      { where: null, text: '지어낸 더 있음' },
    ]);
  });

  it('uploadOutcome: 채움 · 같은 값만 · 넷 다 0', () => {
    const base = { added: 0, filled: 0, unchanged: 0, unresolved: 0 };
    expect(uploadOutcome({ ...base, filled: 1 })).toBe('filled');
    expect(uploadOutcome({ ...base, unchanged: 2, unresolved: 3 })).toBe(
      'sameValues',
    );
    expect(uploadOutcome(base)).toBe('noValues');
  });
});
