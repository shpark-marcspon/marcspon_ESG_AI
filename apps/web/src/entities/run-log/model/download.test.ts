// 실행 기록 엑셀 파일 이름(밴드 AD4X ②): Content-Disposition → 이름. filename*(대소문자 무시) → filename="…" → filename=…, 경로 글자 지움, 없으면 null.
import { describe, expect, it } from 'vitest';

import { RUN_EXPORT_FALLBACK_NAME, fileNameFromDisposition } from './index.ts';

const NAME = '실행기록_2026-10-22_1430.xlsx';
const star = (charset: string) =>
  `attachment; filename*=${charset}''${encodeURIComponent(NAME)}`;

describe('fileNameFromDisposition', () => {
  it("filename*=utf-8''·UTF-8'' 둘 다 퍼센트 꼴을 푼다", () => {
    expect(fileNameFromDisposition(star('utf-8'))).toBe(NAME);
    expect(fileNameFromDisposition(star('UTF-8'))).toBe(NAME);
  });

  it('별 꼴과 맨 꼴이 같이 있으면 별 꼴이 이긴다', () => {
    expect(
      fileNameFromDisposition(
        `attachment; filename="run-log.xlsx"; ${star('utf-8').slice(12)}`,
      ),
    ).toBe(NAME);
  });

  it('퍼센트 꼴이 깨지면 filename= 으로', () => {
    expect(
      fileNameFromDisposition(
        `attachment; filename*=utf-8''%E0%A4%A; filename="fallback.xlsx"`,
      ),
    ).toBe('fallback.xlsx');
  });

  it('따옴표 안의 \\" 는 풀고, 따옴표 없는 꼴도 읽는다', () => {
    expect(
      fileNameFromDisposition('attachment; filename="a \\"b\\".xlsx"'),
    ).toBe('a "b".xlsx');
    expect(fileNameFromDisposition('attachment; filename=plain.xlsx')).toBe(
      'plain.xlsx',
    );
  });

  it('경로 글자(/ \\)는 지운다', () => {
    expect(
      fileNameFromDisposition(
        `attachment; filename*=utf-8''${encodeURIComponent('../a/b\\c.xlsx')}`,
      ),
    ).toBe('..abc.xlsx');
  });

  it('null·빈 글·이름 없음·경로 글자만 → null', () => {
    expect(fileNameFromDisposition(null)).toBeNull();
    expect(fileNameFromDisposition('')).toBeNull();
    expect(fileNameFromDisposition('attachment')).toBeNull();
    expect(fileNameFromDisposition('attachment; filename="/"')).toBeNull();
  });

  it('대체 이름(초안)', () => {
    expect(RUN_EXPORT_FALLBACK_NAME).toBe('실행기록.xlsx');
  });
});
