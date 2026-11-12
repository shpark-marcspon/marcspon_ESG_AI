// 폼 → materiality.input@1(밴드 IRW2 ② — 발주서 §3 시험 2, 부록 A3). 칸마다 · 가치사슬 0행 → null · dateRange · 바이트 셈(파이썬 구분자 꼴).
// 지은 입력은 계약 거울(api/contract — input@1 strict)을 지난다.
import { describe, expect, it } from 'vitest';

import { parseInput } from '../api/contract/index.ts';
import {
  buildInput,
  buildOptions,
  optionsOctets,
  optionsTooLarge,
  pyJson,
} from './input.ts';
import { fakeDraft } from './testing.ts';
import { blankValueChainRow } from './valueChain.ts';

describe('buildInput', () => {
  it('계약 칸 차례 그대로 · schemaVersion 첫 열쇠 · 글은 trim · 거울을 지난다', () => {
    const input = buildInput(fakeDraft());
    expect(Object.keys(input)).toEqual([
      'schemaVersion',
      'company',
      'industries',
      'topics',
      'geoScope',
      'userLocation',
      'mainLanguage',
      'dateRange',
      'sector',
      'latestEventMode',
      'subtopicsByTopic',
      'valueChain',
    ]);
    expect(input.schemaVersion).toBe('materiality.input@1');
    expect(input.company).toEqual({ name: '가상물산' });
    expect(parseInput(input).ok).toBe(true);
  });

  it('산업: SASB→GICS→KSIC 차례, 이름이 빈 기준은 뺌, 설명 빔 ""', () => {
    expect(buildInput(fakeDraft()).industries).toEqual([
      {
        standard: 'SASB',
        industryName: '가상 산업',
        description: '가상 산업 설명',
      },
      { standard: 'KSIC', industryName: '가상 분류', description: '' },
    ]);
  });

  it('토픽·서브토픽: 카드 차례, 두 칸 다 빈 서브토픽 줄은 뺌, 설명 빔 ""', () => {
    const input = buildInput(fakeDraft());
    expect(input.topics).toEqual([
      { topic: '가상토픽 A', description: '가상토픽 A 설명' },
      { topic: '가상토픽 B', description: '' },
    ]);
    expect(input.subtopicsByTopic).toEqual({
      '가상토픽 A': [{ name: '가상 서브 1', description: '서브 1 설명' }],
      '가상토픽 B': [{ name: '가상 서브 2', description: '' }],
    });
  });

  it('리서치 조건: 검색 지역 글 · KR · 한국어 · `<시작>~오늘까지`(공백 0) · 업종 · 최신 이슈 늘 false(IRW15 ③)', () => {
    const input = buildInput(
      fakeDraft({
        startDate: ' 2024-03-05 ',
        sector: 'financial',
      }),
    );
    expect(input).toMatchObject({
      geoScope: '가상 범위',
      userLocation: 'KR',
      mainLanguage: '한국어',
      dateRange: '2024-03-05~오늘까지',
      sector: 'financial',
      latestEventMode: false,
    });
  });

  it('가치사슬: 0행 → null, 있으면 행 차례 그대로(열쇠 다섯·서버 값)', () => {
    expect(buildInput(fakeDraft()).valueChain).toBeNull();
    const row = {
      business_unit: ' 가 ',
      business_unit_description: '',
      value_chain_stage: 'downstream' as const,
      stakeholder: '다',
      business_activity: '라',
    };
    const input = buildInput(fakeDraft({ valueChain: [row] }));
    expect(input.valueChain).toEqual([{ ...row, business_unit: '가' }]);
    expect(parseInput(input).ok).toBe(true);
  });

  it('가치사슬: 다섯 칸 다 빈 행은 뺀다 — 그뿐이면 null, 섞이면 뺀 목록(IRW3 Q2)', () => {
    const blank = blankValueChainRow();
    const spaces = { ...blankValueChainRow(), stakeholder: '  ' };
    expect(
      buildInput(fakeDraft({ valueChain: [blank, spaces] })).valueChain,
    ).toBeNull();
    const row = {
      ...blankValueChainRow(),
      value_chain_stage: 'upstream' as const,
      stakeholder: '다',
    };
    const input = buildInput(fakeDraft({ valueChain: [blank, row, spaces] }));
    expect(input.valueChain).toEqual([row]);
    expect(parseInput(input).ok).toBe(true);
  });

  it('options 는 열쇠 input 하나', () => {
    expect(Object.keys(buildOptions(buildInput(fakeDraft())))).toEqual([
      'input',
    ]);
  });
});

describe('바이트 셈(파이썬 json.dumps 기본 구분자 · ensure_ascii 없음)', () => {
  it('구분자 ", "·": " 와 escape', () => {
    expect(pyJson({ a: [true, null, '가"\n'], b: {} })).toBe(
      '{"a": [true, null, "가\\"\\n"], "b": {}}',
    );
    // 한글 한 자 = 3 바이트(ensure_ascii 없음)
    expect(optionsOctets({ k: '가' })).toBe('{"k": "가"}'.length + 2);
  });

  it('262,144 바이트까지 보내고 하나 넘으면 너무 큼', () => {
    const base = optionsOctets({ input: '' });
    const at = (n: number) => ({ input: 'x'.repeat(n) });
    expect(optionsTooLarge(at(262_144 - base))).toBe(false);
    expect(optionsTooLarge(at(262_144 - base + 1))).toBe(true);
  });
});

describe('토픽 이름이 「__proto__」(검증 m1)', () => {
  it('subtopicsByTopic 에 제 칸으로 남는다', () => {
    const base = fakeDraft();
    const [a] = base.topics as [(typeof base.topics)[0]];
    const input = buildInput(
      fakeDraft({ topics: [{ ...a, topic: '__proto__' }] }),
    );
    expect(Object.keys(input.subtopicsByTopic!)).toEqual(['__proto__']);
    expect(JSON.stringify(input.subtopicsByTopic)).toContain('__proto__');
  });
});
