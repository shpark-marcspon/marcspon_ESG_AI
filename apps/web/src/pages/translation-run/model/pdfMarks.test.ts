// 짝 칸 밑줄 셈(밴드 TRW7 ① S1). 값은 전부 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import { marksOf, pairMarksOf } from './pdfMarks.ts';

const issue = (n: number) => ({ kind: 'issue' as const, n });
const term = (n: number) => ({ kind: 'term' as const, n });

describe('marksOf', () => {
  it('찾은 구간을 원래 글자 그대로 자르고 나머지는 이어 붙이면 원래 줄', () => {
    const { lines, hits } = marksOf(
      ['We cut made-up gas by 40%.'],
      [{ needles: ['made-up gas'], mark: issue(1) }],
    );
    expect(lines[0]).toEqual([
      { text: 'We cut ' },
      { text: 'made-up gas', mark: issue(1) },
      { text: ' by 40%.' },
    ]);
    expect(hits).toEqual([0]);
  });

  it('정규화: 대소문자·공백 덩어리를 가리지 않고 원래 자리로 되돌린다', () => {
    const { lines } = marksOf(
      ['A  Made-Up\n gas line'],
      [{ needles: ['  made-up GAS '], mark: issue(1) }],
    );
    expect(lines[0]!.map((piece) => piece.text)).toEqual([
      'A  ',
      'Made-Up\n gas',
      ' line',
    ]);
  });

  it('못 찾으면 mark 0 · hit null', () => {
    const { lines, hits } = marksOf(
      ['Nothing here'],
      [{ needles: ['absent'], mark: issue(1) }],
    );
    expect(lines[0]).toEqual([{ text: 'Nothing here' }]);
    expect(hits).toEqual([null]);
  });

  it('앞 말이 없으면 다음 말 · 빈 말은 건넌다', () => {
    const { hits } = marksOf(
      ['old words stay'],
      [{ needles: ['', 'new words', 'old words'], mark: issue(1) }],
    );
    expect(hits).toEqual([2]);
  });

  it('줄을 넘는 구간은 못 찾음 · 둘째 줄에서 찾으면 그 줄', () => {
    const { lines, hits } = marksOf(
      ['first half', 'second half'],
      [
        { needles: ['half second'], mark: issue(1) },
        { needles: ['second'], mark: issue(2) },
      ],
    );
    expect(hits).toEqual([null, 0]);
    expect(lines[0]).toEqual([{ text: 'first half' }]);
    expect(lines[1]![0]).toEqual({ text: 'second', mark: issue(2) });
  });

  it('겹치면 앞 번호가 이기고 뒤 번호는 겹치지 않는 다음 자리로(없으면 0)', () => {
    const { lines, hits } = marksOf(
      ['gas cut gas'],
      [
        { needles: ['gas cut'], mark: issue(1) },
        { needles: ['gas'], mark: issue(2) },
        { needles: ['cut'], mark: issue(3) },
      ],
    );
    expect(hits).toEqual([0, 0, null]);
    expect(lines[0]).toEqual([
      { text: 'gas cut', mark: issue(1) },
      { text: ' ' },
      { text: 'gas', mark: issue(2) },
    ]);
  });
});

describe('pairMarksOf', () => {
  const pair = {
    source: ['지어낸 용어가 든 원문'],
    translation: ['Old span and new fix here'],
  };
  const issues = [{ span: 'Old span', suggestion: 'new fix' }];

  it('번호: 이슈 1..k, 용어는 이어서 k+1..', () => {
    const out = pairMarksOf(
      pair,
      [...issues, { span: 'here', suggestion: '' }],
      [{ ko: '지어낸 용어' }],
      'translated',
    );
    expect(
      out.translation![0]!.flatMap((p) => (p.mark ? [p.mark] : [])),
    ).toEqual([issue(1), issue(2)]);
    expect(out.source[0]!.flatMap((p) => (p.mark ? [p.mark] : []))).toEqual([
      term(3),
    ]);
  });

  it('autofix 문체는 제안 글 자리 · fixed 참', () => {
    const out = pairMarksOf(pair, issues, [], 'autofix');
    expect(out.translation![0]!.find((p) => p.mark)?.text).toBe('new fix');
    expect(out.fixed).toEqual([true]);
  });

  it('translated 문체는 고칠 부분 자리 · fixed 거짓', () => {
    const out = pairMarksOf(pair, issues, [], 'translated');
    expect(out.translation![0]!.find((p) => p.mark)?.text).toBe('Old span');
    expect(out.fixed).toEqual([false]);
  });

  it('autofix 인데 제안 글이 없으면 고칠 부분 · fixed 거짓 · 빈 제안도 거짓', () => {
    const none = pairMarksOf(
      { ...pair, translation: ['Old span only'] },
      [...issues, { span: 'only', suggestion: '' }],
      [],
      'autofix',
    );
    expect(none.translation![0]!.find((p) => p.mark)?.text).toBe('Old span');
    expect(none.fixed).toEqual([false, false]);
  });

  it('번역 없는 짝은 이슈 밑줄 0 · 원문 용어는 그대로', () => {
    const out = pairMarksOf(
      { source: pair.source, translation: null },
      issues,
      [{ ko: '용어' }],
      'autofix',
    );
    expect(out.translation).toBeNull();
    expect(out.fixed).toEqual([false]);
    expect(out.source[0]!.some((p) => p.mark?.kind === 'term')).toBe(true);
  });
});
