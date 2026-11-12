// 온실가스 model(밴드 W12-0a ① — 발주서 §3 2): toRequestId · branchSaveBody · validateBranch·validateFacilityLine · validateCodeName ·
//   본사 규칙 · inventoryTargets·deleteTargets · draftOf·sameDraft · branchPutBody(밴드 K1b-3). 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import {
  branchPutBody,
  branchSaveBody,
  canToggleInventory,
  codesInKoreanOrder,
  deleteTargets,
  draftOf,
  emptyDraft,
  inventoryTargets,
  isSelectable,
  sameDraft,
  toRequestId,
  validateBranch,
  validateCodeName,
  validateFacilityLine,
} from './index.ts';
import type {
  Branch,
  BranchDetail,
  BranchDraft,
  FacilityLine,
} from './index.ts';

const branch = (id: string, isHeadquarters = false): Branch => ({
  id,
  name: `지어낸 사업장 ${id}`,
  isHeadquarters,
  inventoryEnabled: true,
  externalId: null,
  createdAt: '2026-10-28T09:00:00+09:00',
});

const line = (
  key: string,
  id: string | null,
  facilityCodeId: string,
  detailName: string,
): FacilityLine => ({
  key,
  id,
  facilityCodeId,
  facilityName: `지어낸 코드 ${facilityCodeId}`,
  detailName,
});

const detail: BranchDetail = {
  ...branch('7'),
  name: '제1공장',
  updatedAt: '2026-10-28T09:30:00.123456+09:00',
  facilities: [
    {
      id: '31',
      facilityCodeId: '2',
      facilityCode: 'F0002',
      facilityName: '지어낸 발전기',
      detailName: '2호기',
    },
    {
      id: '30',
      facilityCodeId: '1',
      facilityCode: 'F0001',
      facilityName: '지어낸 보일러',
      detailName: '1호기',
    },
  ],
};

describe('toRequestId', () => {
  it('양의 정수 글자 → 정수', () => {
    expect(toRequestId('1')).toBe(1);
    expect(toRequestId('42')).toBe(42);
    expect(typeof toRequestId('9007199254740991')).toBe('number');
  });

  it.each([
    '',
    '0',
    '-1',
    '1.5',
    '01',
    'abc',
    ' 3',
    '3 ',
    '1e3',
    '9007199254740993',
  ])('%j 는 던진다', (id) => expect(() => toRequestId(id)).toThrow(RangeError));
});

describe('branchSaveBody', () => {
  it('이름 trim · 줄 차례 그대로 · 있던 줄은 id 정수, 새 줄은 id 없음 · 코드 id 정수 · 세부시설명 trim', () => {
    const draft = draftOf(detail);
    draft.name = '  제1공장 고침  ';
    draft.facilities.push(line('new-1', null, '3', '  지게차 A '));
    expect(branchSaveBody(draft)).toEqual({
      name: '제1공장 고침',
      inventoryEnabled: true,
      facilities: [
        { id: 31, facilityCodeId: 2, detailName: '2호기' },
        { id: 30, facilityCodeId: 1, detailName: '1호기' },
        { facilityCodeId: 3, detailName: '지게차 A' },
      ],
    });
    expect('id' in branchSaveBody(draft).facilities[2]!).toBe(false);
  });

  it('빠진 줄은 본문에 없다(삭제 표시) · 끈 사업장은 inventoryEnabled false', () => {
    const draft = draftOf(detail);
    draft.facilities = draft.facilities.filter((one) => one.id !== '31');
    draft.inventoryEnabled = false;
    expect(branchSaveBody(draft)).toEqual({
      name: '제1공장',
      inventoryEnabled: false,
      facilities: [{ id: 30, facilityCodeId: 1, detailName: '1호기' }],
    });
  });

  it('본사는 판이 꺼져 있어도 늘 켬으로 보낸다', () => {
    const draft: BranchDraft = {
      ...draftOf({ ...detail, isHeadquarters: true }),
      inventoryEnabled: false,
    };
    expect(branchSaveBody(draft).inventoryEnabled).toBe(true);
  });

  it('id 가 정수 글자가 아니면 던진다(요청하지 않는다)', () => {
    const draft = emptyDraft();
    draft.name = '제2공장';
    draft.facilities.push(line('x', null, 'F0001', '1호기'));
    expect(() => branchSaveBody(draft)).toThrow(RangeError);
  });
});

describe('branchPutBody', () => {
  it('공통 본문 + updatedAt 은 받은 글자 그대로(µs·+09:00 — 날짜로 바꾸지 않는다)', () => {
    const draft = draftOf(detail);
    expect(branchPutBody(draft, detail.updatedAt)).toStrictEqual({
      ...branchSaveBody(draft),
      updatedAt: '2026-10-28T09:30:00.123456+09:00',
    });
    expect(branchPutBody(draft, '2026-10-28T00:30:00.1234Z').updatedAt).toBe(
      '2026-10-28T00:30:00.1234Z',
    );
  });

  it('판(draft)과 POST 본문에는 버전이 없다 — 버전만 다른 상세 둘의 판은 같다', () => {
    const draft = draftOf(detail);
    expect('updatedAt' in draft).toBe(false);
    expect('updatedAt' in branchSaveBody(draft)).toBe(false);
    expect(
      sameDraft(
        draft,
        draftOf({ ...detail, updatedAt: '2026-10-29T09:00:00.000001+09:00' }),
      ),
    ).toBe(true);
  });
});

describe('validateBranch', () => {
  it('이름 빔(공백만 포함) → nameRequired 가 먼저', () => {
    const draft = emptyDraft();
    expect(validateBranch(draft)).toBe('nameRequired');
    draft.name = '   ';
    draft.facilities = [line('a', null, '1', 'x'), line('b', null, '1', 'x')];
    expect(validateBranch(draft)).toBe('nameRequired');
  });

  it('(코드, 세부시설명) 겹침 — 세부시설명은 앞뒤 공백을 걷고 견준다', () => {
    const draft = { ...emptyDraft(), name: '제2공장' };
    draft.facilities = [
      line('a', '1', '1', '1호기'),
      line('b', null, '1', ' 1호기 '),
    ];
    expect(validateBranch(draft)).toBe('duplicateFacility');
  });

  it('코드가 다르거나 세부시설명이 다르면 겹침 아님', () => {
    const draft = { ...emptyDraft(), name: '제2공장' };
    draft.facilities = [
      line('a', null, '1', '1호기'),
      line('b', null, '2', '1호기'),
      line('c', null, '1', '2호기'),
    ];
    expect(validateBranch(draft)).toBeNull();
  });
});

describe('validateFacilityLine', () => {
  const lines = [line('a', '30', '1', '1호기')];
  it('코드 빔 → 세부시설명 빔 → 겹침 차례', () => {
    expect(validateFacilityLine(lines, '', '')).toBe('codeRequired');
    expect(validateFacilityLine(lines, '1', '  ')).toBe('detailRequired');
    expect(validateFacilityLine(lines, '1', ' 1호기')).toBe(
      'duplicateFacility',
    );
    expect(validateFacilityLine(lines, '2', '1호기')).toBeNull();
  });
});

describe('GX2 L-8 codesInKoreanOrder', () => {
  it('이름 가나다(한글 먼저, 영문 뒤) → 같은 이름은 id · 받은 배열은 그대로', () => {
    const codes = [
      { id: '3', code: 'F3', name: '용제' },
      { id: '1', code: 'F1', name: 'B-A유' },
      { id: '9', code: 'F9', name: '경유' },
      { id: '2', code: 'F2', name: '구매 전력' },
      { id: '10', code: 'F10', name: '나프타' },
      { id: '4', code: 'F4', name: '경유' },
    ];
    expect(codesInKoreanOrder(codes).map((c) => c.id)).toEqual([
      '4',
      '9',
      '2',
      '10',
      '3',
      '1',
    ]);
    expect(codes[0]!.id).toBe('3');
  });
});

describe('validateCodeName', () => {
  const codes = [
    { id: '1', code: 'F0001', name: '지어낸 보일러' },
    { id: '2', code: 'F0002', name: '지어낸 발전기' },
  ];
  it('빔·공백 → required, 다른 항목과 같은 이름(공백 걷고) → duplicate', () => {
    expect(validateCodeName('', codes)).toBe('required');
    expect(validateCodeName('   ', codes)).toBe('required');
    expect(validateCodeName(' 지어낸 보일러 ', codes)).toBe('duplicate');
    expect(validateCodeName('지어낸 냉동기', codes)).toBeNull();
  });

  it('수정은 자기 항목과 견주지 않는다', () => {
    expect(validateCodeName('지어낸 보일러', codes, '1')).toBeNull();
    expect(validateCodeName('지어낸 발전기', codes, '1')).toBe('duplicate');
  });
});

describe('본사 규칙', () => {
  const hq = branch('1', true);
  const one = branch('7');
  const two = branch('8');

  it('본사는 고르지 못하고 토글하지 못한다', () => {
    expect(isSelectable(hq)).toBe(false);
    expect(canToggleInventory(hq)).toBe(false);
    expect(isSelectable(one)).toBe(true);
    expect(canToggleInventory(one)).toBe(true);
  });

  it('inventoryTargets: 끄기는 본사를 뺀다 · 켜기는 섞여도 된다', () => {
    expect(inventoryTargets([hq, one, two], false)).toEqual(['7', '8']);
    expect(inventoryTargets([hq, one], true)).toEqual(['1', '7']);
    expect(inventoryTargets([hq], false)).toEqual([]);
  });

  it('deleteTargets: 본사는 빠진다', () => {
    expect(deleteTargets([hq, one, two])).toEqual(['7', '8']);
  });
});

describe('draftOf·sameDraft', () => {
  it('상세 → 판: 줄 차례 그대로 · 열쇠는 서버 id', () => {
    const draft = draftOf(detail);
    expect(draft.facilities.map((one) => [one.key, one.id])).toEqual([
      ['saved-31', '31'],
      ['saved-30', '30'],
    ]);
    expect(sameDraft(draft, draftOf(detail))).toBe(true);
  });

  it('이름·사용 상태·줄 하나라도 다르면 다르다', () => {
    const base = draftOf(detail);
    expect(sameDraft(base, { ...base, name: '제1공장 ' })).toBe(false);
    expect(sameDraft(base, { ...base, inventoryEnabled: false })).toBe(false);
    expect(
      sameDraft(base, { ...base, facilities: base.facilities.slice(1) }),
    ).toBe(false);
    expect(
      sameDraft(base, {
        ...base,
        facilities: [...base.facilities].reverse(),
      }),
    ).toBe(false);
  });
});
