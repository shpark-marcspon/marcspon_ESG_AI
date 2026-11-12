// 밴드 GW2R ③(발주서 §3 A): 엑셀 파일 이름 뽑기 — Content-Disposition 에서.
import { describe, expect, it } from 'vitest';

import { fallbackReportName, fileNameFromDisposition } from './report.ts';

describe('fileNameFromDisposition', () => {
  it.each([
    ['attachment; filename="a b.xlsx"', 'a b.xlsx'],
    ['attachment; filename=plain.xlsx', 'plain.xlsx'],
    [
      `attachment; filename="fallback.xlsx"; filename*=UTF-8''${encodeURIComponent('지어낸 보고서.xlsx')}`,
      '지어낸 보고서.xlsx',
    ],
    [
      `attachment; filename*=utf-8''${encodeURIComponent('확정본 1.xlsx')}`,
      '확정본 1.xlsx',
    ],
    // 깨진 퍼센트 꼴이면 filename= 으로
    [`attachment; filename*=UTF-8''%E0%A4%A; filename="b.xlsx"`, 'b.xlsx'],
    ['attachment; filename="a \\"q\\".xlsx"', 'a "q".xlsx'],
    // 경로 글자는 지운다
    ['attachment; filename="../x/y.xlsx"', '..xy.xlsx'],
    ['attachment', null],
    ['attachment; filename=""', null],
    [null, null],
  ] as const)('%j → %j', (header, name) => {
    expect(fileNameFromDisposition(header)).toBe(name);
  });

  it('없으면 greenwash-<runId>.xlsx', () => {
    expect(fallbackReportName('12')).toBe('greenwash-12.xlsx');
  });
});
