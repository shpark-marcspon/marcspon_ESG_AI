// 온실가스 Scope 3 model 시험(밴드 S3W1 ① — 발주서 §3 의 2).
import { describe, expect, it } from 'vitest';

import {
  CATEGORIES,
  CATEGORY_IDS,
  MAX_UPLOAD_BYTES,
  acceptFile,
  runPhase,
  seoulYear,
  steps,
  toggleCategory,
  yearIn,
  yearsOf,
} from './index.ts';

describe('CATEGORIES — C1~C15, 1차 C10 끔(sid:MARC-ENT-315)', () => {
  it('열다섯이 번호 차례', () => {
    expect(CATEGORIES.map((c) => c.id)).toEqual([...CATEGORY_IDS]);
    expect(CATEGORIES.map((c) => c.number)).toEqual(
      Array.from({ length: 15 }, (_, i) => i + 1),
    );
  });

  it('C10 하나만 끔', () => {
    expect(CATEGORIES.filter((c) => c.disabled).map((c) => c.id)).toEqual([
      'C10',
    ]);
  });

  it('toggleCategory — 넣고 빼고, C 번호 차례, 끈 것은 그대로', () => {
    expect(toggleCategory([], 'C3')).toEqual(['C3']);
    expect(toggleCategory(['C3'], 'C1')).toEqual(['C1', 'C3']);
    expect(toggleCategory(['C1', 'C3'], 'C1')).toEqual(['C3']);
    expect(toggleCategory(['C2'], 'C10')).toEqual(['C2']);
  });
});

describe('yearsOf — 전년도부터 내림 다섯(발주서 Q4)', () => {
  it('서울 2026 이면 2025 가 첫 값', () => {
    const today = new Date('2026-06-15T03:00:00Z');
    expect(yearsOf(today)).toEqual([2025, 2024, 2023, 2022, 2021]);
  });

  it('서울 날짜로 센다 — UTC 12-31 15:00 은 서울 1-1', () => {
    expect(seoulYear(new Date('2025-12-31T15:00:00Z'))).toBe(2026);
    expect(seoulYear(new Date('2025-12-31T14:59:59Z'))).toBe(2025);
  });

  it('yearIn — 범위 안만 그대로, 밖·없음은 null', () => {
    const years = [2025, 2024, 2023, 2022, 2021];
    expect(yearIn(2023, years)).toBe(2023);
    expect(yearIn(2026, years)).toBeNull();
    expect(yearIn(2020, years)).toBeNull();
    expect(yearIn(undefined, years)).toBeNull();
  });
});

describe('runPhase — RunOut.status 그대로', () => {
  it.each([
    ['queued', 'running'],
    ['processing', 'running'],
    ['done', 'done'],
    ['failed', 'failed'],
    ['cancelled', 'unknown'],
    [undefined, 'unknown'],
  ] as const)('%s → %s', (status, phase) => {
    expect(runPhase(status)).toBe(phase);
  });
});

describe('steps — Step 넷(판 S3-01)', () => {
  it('자리마다 끝난 Step', () => {
    const done = (stage: Parameters<typeof steps>[0]) =>
      steps(stage).map((s) => s.done);
    expect(steps('idle').map((s) => s.key)).toEqual([
      'start',
      'categories',
      'upload',
      'calculate',
    ]);
    expect(done('idle')).toEqual([false, false, false, false]);
    expect(done('categories')).toEqual([true, false, false, false]);
    expect(done('upload')).toEqual([true, true, false, false]);
    // 계산 중·실패·잃음: Step 1~3 완료는 남는다(값 파일 GX3 s2).
    expect(done('running')).toEqual([true, true, true, false]);
    expect(done('done')).toEqual([true, true, true, true]);
  });
});

describe('acceptFile — xls·xlsx, 20MB 같으면 받음', () => {
  it('확장자', () => {
    expect(acceptFile({ name: 'a.xlsx', size: 1 })).toBeNull();
    expect(acceptFile({ name: 'a.XLS', size: 1 })).toBeNull();
    expect(acceptFile({ name: 'a.csv', size: 1 })).toBe('type');
    expect(acceptFile({ name: 'xlsx', size: 1 })).toBe('type');
    expect(acceptFile({ name: 'a.xlsx.pdf', size: 1 })).toBe('type');
  });

  it('0바이트는 empty — 형식이 먼저(GX1 M-5)', () => {
    expect(acceptFile({ name: 'a.xlsx', size: 0 })).toBe('empty');
    expect(acceptFile({ name: 'a.csv', size: 0 })).toBe('type');
  });

  it('20MB 경계 — 같음 받음, 넘음 거절, 형식이 먼저', () => {
    expect(MAX_UPLOAD_BYTES).toBe(20 * 1024 * 1024);
    expect(acceptFile({ name: 'a.xlsx', size: MAX_UPLOAD_BYTES })).toBeNull();
    expect(acceptFile({ name: 'a.xlsx', size: MAX_UPLOAD_BYTES + 1 })).toBe(
      'size',
    );
    expect(acceptFile({ name: 'a.pdf', size: MAX_UPLOAD_BYTES + 1 })).toBe(
      'type',
    );
  });
});
