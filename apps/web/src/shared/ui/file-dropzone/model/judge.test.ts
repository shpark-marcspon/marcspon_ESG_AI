// 파일 판정: FV3 4.3 의 키트 버그 1(둘)과 3 을 재현하는 입력이 우리 함수에서 바르게 판정되는지, 그리고 걸러서 통과.
import { describe, expect, it } from 'vitest';

import {
  acceptAttribute,
  extensionOf,
  judgeFiles,
  matchesAccept,
  toDateText,
} from './judge.ts';
import type { PickedFile } from './judge.ts';

const MB = 1024 * 1024;
const file = (name: string, type = '', size = 1): PickedFile => ({
  name,
  type,
  size,
});
const names = (files: readonly PickedFile[]) => files.map((item) => item.name);
const reasons = (judgement: ReturnType<typeof judgeFiles>) =>
  judgement.rejected.map(({ file: item, reason }) => `${item.name}:${reason}`);

describe('형식 판정', () => {
  it('버그 1-가: .xlsx 만 받을 때 .xls 는 거부된다(키트는 부분 문자열 비교로 통과시켰다)', () => {
    const result = judgeFiles(
      [file('a.xls'), file('b.xlsx'), file('c.XLSX')],
      [],
      { accept: ['.xlsx'] },
    );
    expect(names(result.accepted)).toEqual(['b.xlsx', 'c.XLSX']);
    expect(reasons(result)).toEqual(['a.xls:type']);
  });

  it('버그 1-나: image/* 를 받을 때 image/png 는 받는다(키트는 와일드카드에 확장자를 비교해 거부했다)', () => {
    const result = judgeFiles(
      [file('사진.png', 'image/png'), file('글.pdf', 'application/pdf')],
      [],
      { accept: ['image/*'] },
    );
    expect(names(result.accepted)).toEqual(['사진.png']);
    expect(reasons(result)).toEqual(['글.pdf:type']);
  });

  it('정확한 MIME, 확장자와 MIME 섞기, 빈 목록은 모두 받기', () => {
    expect(
      matchesAccept(file('x.bin', 'application/pdf'), ['application/pdf']),
    ).toBe(true);
    expect(matchesAccept(file('x.pdf', ''), ['application/pdf'])).toBe(false);
    expect(matchesAccept(file('x.pdf', ''), ['.xlsx', '.pdf'])).toBe(true);
    expect(matchesAccept(file('image', 'image/'), ['image/*'])).toBe(true);
    expect(matchesAccept(file('x', ''), ['image/*'])).toBe(false);
    expect(matchesAccept(file('x.anything'), [])).toBe(true);
    expect(matchesAccept(file('x.anything'), undefined)).toBe(true);
    // 확장자 없는 파일, 점으로 시작하는 이름
    expect(matchesAccept(file('xlsx'), ['.xlsx'])).toBe(false);
    expect(matchesAccept(file('.xlsx'), ['.xlsx'])).toBe(false);
    // 잘못 쓴 항목(점도 / 도 없음)은 아무것도 받지 않는다
    expect(matchesAccept(file('a.xlsx'), ['xlsx'])).toBe(false);
  });

  it('확장자는 점을 포함한 소문자, accept 속성은 쉼표로 잇는다', () => {
    expect(extensionOf('보고서.최종.XLSX')).toBe('.xlsx');
    expect(extensionOf('README')).toBe('');
    expect(extensionOf('.env')).toBe('');
    expect(acceptAttribute(['.xlsx', 'image/*'])).toBe('.xlsx,image/*');
    expect(acceptAttribute([])).toBeUndefined();
  });
});

describe('걸러서 통과', () => {
  it('버그 3: 한 번에 고른 파일끼리 이름이 겹치면 뒤의 것을 거부한다(대소문자 무시). 이미 있는 것과 겹쳐도 거부한다', () => {
    const result = judgeFiles(
      [file('a.xlsx'), file('A.xlsx'), file('b.xlsx'), file('있는.xlsx')],
      [{ name: '있는.xlsx' }],
      { accept: ['.xlsx'] },
    );
    expect(names(result.accepted)).toEqual(['a.xlsx', 'b.xlsx']);
    expect(reasons(result)).toEqual([
      'A.xlsx:duplicate',
      '있는.xlsx:duplicate',
    ]);
  });

  it('크기 상한은 파일 하나 기준이다(합계가 아니다)', () => {
    const result = judgeFiles(
      [
        file('a.pdf', '', 15 * MB),
        file('b.pdf', '', 15 * MB),
        file('c.pdf', '', 20 * MB + 1),
        file('d.pdf', '', 20 * MB),
      ],
      [],
      { maxMb: 20 },
    );
    expect(names(result.accepted)).toEqual(['a.pdf', 'b.pdf', 'd.pdf']);
    expect(reasons(result)).toEqual(['c.pdf:size']);
  });

  it('개수 초과는 남은 자리만큼 앞에서부터 받고 나머지를 거부한다(전부 거부가 아니다)', () => {
    const result = judgeFiles(
      [file('1.pdf'), file('2.pdf'), file('3.pdf'), file('4.pdf')],
      [{ name: '있는.pdf' }],
      { maxCount: 3 },
    );
    expect(names(result.accepted)).toEqual(['1.pdf', '2.pdf']);
    expect(reasons(result)).toEqual(['3.pdf:count', '4.pdf:count']);
  });

  it('자리를 세는 것은 형식·크기·이름을 통과한 것뿐이다. 이미 꽉 찼으면 모두 count', () => {
    const result = judgeFiles(
      [file('x.exe'), file('1.pdf'), file('2.pdf')],
      [],
      { accept: ['.pdf'], maxCount: 1 },
    );
    expect(names(result.accepted)).toEqual(['1.pdf']);
    expect(reasons(result)).toEqual(['x.exe:type', '2.pdf:count']);
    const full = judgeFiles([file('1.pdf')], [{ name: 'a' }, { name: 'b' }], {
      maxCount: 1,
    });
    expect(reasons(full)).toEqual(['1.pdf:count']);
  });

  it('날짜는 YYYY-MM-DD', () => {
    expect(toDateText(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05');
  });
});
