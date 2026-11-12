// 칸 글자의 웹 갈음(밴드 GX3 ① — GX1 M-1·M-3·L-4·L-5). 엔진 글은 그대로 두고 화면 글만 바꾼다(sid:MARC-ENT-442).
import { describe, expect, it } from 'vitest';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { cellText, formulaText, rawSourceText } from './detailText.ts';

const raw = (text: string | null) => ({
  type: 'text' as const,
  text,
  raw: true,
});
const plain = (text: string | null) => ({ type: 'text' as const, text });

describe('rawSourceText — 서버 시트 이름 → 화면 글', () => {
  it('폐기물 시트 둘은 「폐기물 배출계수 표」(M-3)', () => {
    expect(rawSourceText('폐기물_C5')).toBe('폐기물 배출계수 표');
    expect(rawSourceText('폐기물_C12')).toBe('폐기물 배출계수 표');
    expect(cellText(raw('폐기물_C5'), 'source')).toBe('폐기물 배출계수 표');
  });

  it('구매 줄 고친 출처의 긴 책 글은 「US EPA」(L-5)', () => {
    expect(
      rawSourceText(
        '구매_USEPA EF (kgCO2e/KRW) 2099년말 기준 (2099-12-31 1,000.00 KRW/USD)',
      ),
    ).toBe('US EPA');
  });

  it('표에 없는 글(직접 입력한 출처)은 그대로 · 없으면 줄표', () => {
    expect(rawSourceText('지어낸 출처 문서')).toBe('지어낸 출처 문서');
    expect(rawSourceText('폐기물_C5 덧')).toBe('폐기물_C5 덧');
    expect(cellText(raw(null), 'source')).toBe(S3_TEXT.result.empty);
  });

  it('갈래 값(raw 아님)은 앞과 같다', () => {
    expect(cellText(plain('usepa'), 'source')).toBe('US EPA');
    expect(cellText(plain('모르는갈래'), 'source')).toBe(S3_TEXT.result.empty);
  });
});

describe('수단 칸 — 서버 정규화 값 → 이름표(M-1)', () => {
  it('출장·통근·운송 값', () => {
    expect(cellText(plain('bus'), 'mode')).toBe('버스');
    expect(cellText(plain('train'), 'mode')).toBe('철도');
    expect(cellText(plain('subway'), 'mode')).toBe('지하철');
    expect(cellText(plain('road'), 'mode')).toBe('도로(트럭)');
    expect(cellText(plain('flight_long_biz'), 'mode')).toBe(
      '항공(장거리 · 비즈니스)',
    );
    expect(cellText(plain('unknown'), 'mode')).toBe('기타');
  });

  it('표에 없는 코드는 「기타」(코드를 내지 않음) · 다른 열은 바꾸지 않음', () => {
    expect(cellText(plain('flight_eco'), 'mode')).toBe('기타');
    expect(cellText(plain('지어낸 수단'), 'mode')).toBe('기타');
    expect(cellText(plain('bus'), 'inName')).toBe('bus');
    expect(cellText(plain(null), 'mode')).toBe(S3_TEXT.result.empty);
  });
});

describe('formulaText — 수식 마디만(L-4)', () => {
  it('숫자 자취 마디부터 뺀다', () => {
    expect(
      formulaText(
        '배출량(tCO2e) = 구매금액(KRW) × EF(kgCO2e/KRW) / 1000 = 9.1e+06 × 5.42043e-05 / 1000 = 0.493259',
      ),
    ).toBe('배출량(tCO2e) = 구매금액(KRW) × EF(kgCO2e/KRW) / 1000');
    expect(
      formulaText(
        '배출량(tCO2e) = 이동거리 × 왕복계수 × 인원수 × 이동횟수 × EF / 1000 = 12 × 2 × 1 × 3 × 0.1 / 1000 = 0.0072',
      ),
    ).toBe(
      '배출량(tCO2e) = 이동거리 × 왕복계수 × 인원수 × 이동횟수 × EF / 1000',
    );
    expect(formulaText('배출량 = 활동량 × EF = nan × 1 = nan')).toBe(
      '배출량 = 활동량 × EF',
    );
  });

  it('자취가 없으면 그대로', () => {
    expect(formulaText('지어낸 식')).toBe('지어낸 식');
    expect(formulaText('1 × 2')).toBe('1 × 2');
    expect(formulaText('배출량 = 활동량 × EF')).toBe('배출량 = 활동량 × EF');
  });
});
