// Scope 3 결과 model 시험(밴드 S3W2a ① — 발주서 §3 의 1): parseNumber(표 1-5)·summarize(카드 셈·실패 수)·failureKind(표 1-6). 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import { parseNumber } from './number.ts';
import { summarize } from './result.ts';
import type { ResultRow, ResultSheet, Scope3Done } from './result.ts';
import { failureKind } from './run.ts';

const done = (
  sheets: ResultSheet[],
  llmCalls: Scope3Done['llmCalls'] = {},
): Scope3Done => ({ status: 'done', sheets, llmCalls });
const row = (
  co2e: string | null,
  biogenic: string | null = null,
): ResultRow => ({
  rowId: null,
  co2e,
  biogenic,
  origin: null,
  formula: null,
  detail: { shape: 'basic' },
  input: null,
});
const rows = (...co2e: (string | null)[]) => co2e.map((one) => row(one));
const card = (summary: ReturnType<typeof summarize>, number: number) =>
  summary.cards[number - 1]!;

describe('parseNumber — 수 글자만, -0 은 0', () => {
  it('표 1-5: 지수·긴 꼬리·경계·-0 → 수(표기 글자는 pages/ghg-scope3 emission.test)', () => {
    expect(parseNumber('1e-05')).toBe(0.00001);
    expect(parseNumber('0.30000000000000004')).toBe(0.30000000000000004);
    expect(parseNumber('0.0005')).toBe(0.0005);
    expect(parseNumber('0.00049999')).toBe(0.00049999);
    expect(Object.is(parseNumber('-0.0'), 0)).toBe(true);
    expect(Object.is(parseNumber('-0'), 0)).toBe(true);
    expect(parseNumber('1.5E+3')).toBe(1500);
    expect(parseNumber('-2.25')).toBe(-2.25);
  });

  it('수가 아닌 글자는 null', () => {
    for (const text of [
      null,
      '',
      ' ',
      'nan',
      'NaN',
      'inf',
      '-inf',
      'Infinity',
      '1e999',
      '1,000',
      '.5',
      '5.',
      '+1',
      '0x10',
      '1 ',
      '1e',
    ])
      expect(parseNumber(text), String(text)).toBeNull();
  });
});

describe('summarize — 카드 15 · 실패 수', () => {
  it('한 카테고리의 시트 여럿을 모두 더한다(첫 시트만이 아님) · tCO2eq 그대로(÷1000 0)', () => {
    const summary = summarize(
      done([
        {
          status: 'processed',
          sheet: 's',
          category: 'Category4',
          rows: rows('1.25'),
        },
        {
          status: 'processed',
          sheet: 's',
          category: 'Category4',
          rows: rows('2', '0.5'),
        },
        {
          status: 'processed',
          sheet: 's',
          category: 'Category8',
          rows: rows('1000'),
        },
      ]),
    );
    expect(card(summary, 4).total).toBe(3.75);
    expect(card(summary, 8).total).toBe(1000);
    expect(summary.cards.map((c) => c.id)).toEqual([
      'C1',
      'C2',
      'C3',
      'C4',
      'C5',
      'C6',
      'C7',
      'C8',
      'C9',
      'C10',
      'C11',
      'C12',
      'C13',
      'C14',
      'C15',
    ]);
  });

  it('null·수 아닌 줄은 건너뜀 · 수가 하나도 없으면 null · 빈 시트·other 는 합 0 이 아니라 null', () => {
    const summary = summarize(
      done([
        {
          status: 'processed',
          sheet: 's',
          category: 'Category1',
          rows: rows(null, '2', 'nan'),
        },
        {
          status: 'processed',
          sheet: 's',
          category: 'Category2',
          rows: rows(null),
        },
        { status: 'processed', sheet: 's', category: 'Category3', rows: [] },
        { status: 'other' },
        {
          status: 'processed',
          sheet: 's',
          category: 'Category7',
          rows: rows('0', '0.0', '-0.0'),
        },
      ]),
    );
    // 0 뿐인 카드는 합 0(「-」 아님) — -0 도 0 으로.
    expect(Object.is(card(summary, 7).total, 0)).toBe(true);
    expect(card(summary, 1).total).toBe(2);
    expect(card(summary, 2).total).toBeNull();
    expect(card(summary, 3).total).toBeNull();
    expect(card(summary, 6).total).toBeNull();
  });

  it('C10 은 끔 — 서버가 Category10 을 보내도 합 null · 실패 아님', () => {
    const summary = summarize(
      done([
        {
          status: 'processed',
          sheet: 's',
          category: 'Category10',
          rows: rows('9'),
        },
        { status: 'failed', sheet: 's', category: 'Category10' },
      ]),
    );
    expect(card(summary, 10)).toMatchObject({
      off: true,
      total: null,
      sheets: 0,
      failedSheets: 0,
    });
    expect(summary.cards.filter((c) => c.off).map((c) => c.id)).toEqual([
      'C10',
    ]);
    expect(summary.failedSheets).toBe(1);
  });

  it('생물기원 합은 C5·C12 만(둘째 줄) · null 이면 null', () => {
    const summary = summarize(
      done([
        {
          status: 'processed',
          sheet: 's',
          category: 'Category5',
          rows: [row('1', '0.25'), row('1', '0.5')],
        },
        {
          status: 'processed',
          sheet: 's',
          category: 'Category12',
          rows: [row('1')],
        },
        {
          status: 'processed',
          sheet: 's',
          category: 'Category3',
          rows: [row('1', '7')],
        },
      ]),
    );
    expect(card(summary, 5)).toMatchObject({
      hasBiogenic: true,
      biogenic: 0.75,
    });
    expect(card(summary, 12)).toMatchObject({
      hasBiogenic: true,
      biogenic: null,
    });
    expect(card(summary, 3)).toMatchObject({
      hasBiogenic: false,
      biogenic: null,
    });
    expect(summary.cards.filter((c) => c.hasBiogenic).map((c) => c.id)).toEqual(
      ['C5', 'C12'],
    );
  });

  it('카드 시트 수 둘(계산된·실패) — 일부 실패면 둘 다 > 0 · 실패 수 = sheets.failed 수 · llmCalls 의 모든 프롬프트 failed: 합', () => {
    const summary = summarize(
      done(
        [
          {
            status: 'processed',
            sheet: 's',
            category: 'Category6',
            rows: rows('1'),
          },
          { status: 'failed', sheet: 's', category: 'Category6' },
          { status: 'empty', sheet: 's', category: 'Category6' },
          { status: 'failed', sheet: 's', category: 'Category9' },
          { status: 'failed', sheet: 's', category: 'Category99' },
        ],
        {
          classify: { success: 4, 'failed:refusal': 2, 'failed:timeout': 1 },
          factor: { 'failed:truncated': 3 },
          spend: { success: 9 },
        },
      ),
    );
    // C6 일부 실패: 성공 시트의 합은 남는다(발주서 Q3 — 「계산 실패」로 숨기지 않음).
    expect(card(summary, 6)).toMatchObject({
      total: 1,
      sheets: 1,
      failedSheets: 1,
    });
    expect(card(summary, 9)).toMatchObject({
      total: null,
      sheets: 0,
      failedSheets: 1,
    });
    expect(card(summary, 1)).toMatchObject({ sheets: 0, failedSheets: 0 });
    expect(summary.failedSheets).toBe(3);
    expect(summary.failedLlmCalls).toBe(6);
    expect(summarize(done([])).failedLlmCalls).toBe(0);
    expect(summarize(done([])).failedSheets).toBe(0);
  });
});

describe('failureKind — errorCode 표(발주서 §1-6)', () => {
  it('표의 code 전부', () => {
    const table: Record<string, string> = {
      setup_error: 'setup',
      step_error: 'general',
      attempts_exhausted: 'transient',
      internal: 'transient',
      document_missing: 'file',
      object_missing: 'file',
      object_changed: 'file',
      object_too_large: 'file',
      storage_denied: 'general',
      storage_unconfigured: 'general',
      flow_not_runnable: 'general',
      result_too_large: 'general',
      options_rejected: 'general',
      versions_mismatch: 'general',
      flow_input_invalid: 'general',
      step_output_invalid: 'general',
      no_text_layer: 'general',
      embedding_failed: 'general',
    };
    for (const [code, kind] of Object.entries(table))
      expect(failureKind(code), code).toBe(kind);
  });

  it('null·모르는 글자·대문자·프로토타입 이름은 general', () => {
    for (const code of [
      null,
      '',
      'SETUP_ERROR',
      'step_failed',
      'toString',
      '__proto__',
    ])
      expect(failureKind(code), String(code)).toBe('general');
  });
});
