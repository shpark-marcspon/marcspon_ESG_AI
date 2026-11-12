// 문구 표의 값 끼우기(밴드 FW1 ⓪). 거부 사유 넷: 한도 값이 있으면 값을 넣은 꼴, 없으면 값 없는 꼴.
import { describe, expect, it } from 'vitest';

import { PARTS_TEXT } from './text.ts';

const { rejectReason } = PARTS_TEXT;

describe('드롭존 거부 사유 문구', () => {
  it('값이 있으면 값을 끼운다', () => {
    expect(rejectReason.type({ formats: 'PDF' })).toBe(
      'PDF 파일만 올려 주세요',
    );
    expect(rejectReason.type({ formats: 'XLSX·CSV' })).toBe(
      'XLSX·CSV 파일만 올려 주세요',
    );
    expect(rejectReason.size({ maxMb: 20 })).toBe(
      '20MB 이하 파일을 올려 주세요',
    );
    expect(rejectReason.duplicate()).toBe('같은 이름의 파일이 이미 있어요');
    expect(rejectReason.count({ maxCount: 3 })).toBe('3개까지 올릴 수 있어요');
  });

  it('값이 없으면 값 없는 꼴이다', () => {
    expect(rejectReason.type({})).toBe('올릴 수 없는 형식이에요');
    expect(rejectReason.type({ formats: '' })).toBe('올릴 수 없는 형식이에요');
    expect(rejectReason.size({})).toBe('파일이 너무 커요');
    expect(rejectReason.duplicate()).toBe('같은 이름의 파일이 이미 있어요');
    expect(rejectReason.count({})).toBe('더 올릴 수 없어요');
  });

  it('0 도 값이다(빈 값으로 읽지 않는다)', () => {
    expect(rejectReason.size({ maxMb: 0 })).toBe('0MB 이하 파일을 올려 주세요');
    expect(rejectReason.count({ maxCount: 0 })).toBe('0개까지 올릴 수 있어요');
  });
});

describe('올린 부품의 기본 글(밴드 TRW0a ①)', () => {
  it('불러오기 실패 단추·위험 등급·단계 번호 앞 글자', () => {
    expect(PARTS_TEXT.load).toEqual({ retry: '다시 시도', toList: '목록으로' });
    expect(PARTS_TEXT.risk).toEqual({ high: 'High', mid: 'Mid', low: 'Low' });
    expect(PARTS_TEXT.stepFlow).toEqual({ prefix: 'STEP' });
  });

  it('모델 카드 쓰는 곳 줄의 숨은 이름(AV1 R4)', () => {
    expect(PARTS_TEXT.modelUses).toBe('쓰는 곳');
  });
});
