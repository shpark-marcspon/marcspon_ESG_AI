// 대상 단어 초안의 순수 함수(밴드 AS3b ① — 발주서 §3-1). 낱말은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import {
  TERMS_CODES,
  addTerm,
  addedTexts,
  refusedRow,
  removeTerms,
  switchTerm,
  termKey,
  termProblem,
  termsBase,
  termsBlocked,
  termsChanged,
  termsCount,
  termsRefusal,
} from './terms.ts';
import type { TermsDraft } from './terms.ts';

const BASE: TermsDraft = [
  { text: '지어낸 초록', enabled: true },
  { text: '지어낸 푸름', enabled: true },
  { text: '지어낸 숲', enabled: false },
];

const WORDS = {
  label: '대상 단어',
  added: (n: number) => `${n}개 추가`,
  removed: (n: number) => `${n}개 삭제`,
  toggled: (n: number) => `${n}개 사용 바꿈`,
  join: ' · ',
};

describe('셈 — 더함·지움·사용 바꿈 각 1', () => {
  it('안 고침 0 · 더함 1 · 지움 1 · 스위치 1 · 셋 다 3', () => {
    expect(termsCount(BASE, BASE)).toBe(0);
    const added = addTerm(BASE, '지어낸 새말');
    expect(added.kind).toBe('ok');
    if (added.kind !== 'ok') return;
    expect(termsCount(BASE, added.draft)).toBe(1);
    expect(termsCount(BASE, removeTerms(BASE, new Set(['지어낸 푸름'])))).toBe(
      1,
    );
    expect(termsCount(BASE, switchTerm(BASE, '지어낸 숲', true))).toBe(1);
    const all = switchTerm(
      removeTerms(added.draft, new Set(['지어낸 초록'])),
      '지어낸 숲',
      true,
    );
    expect(termsCount(BASE, all)).toBe(3);
  });

  it('되돌리면 0 · 더한 뒤 지운 새 낱말 0', () => {
    const off = switchTerm(BASE, '지어낸 초록', false);
    expect(termsCount(BASE, switchTerm(off, '지어낸 초록', true))).toBe(0);
    const added = addTerm(BASE, '지어낸 새말');
    if (added.kind !== 'ok') throw new Error('추가 실패');
    expect(
      termsCount(BASE, removeTerms(added.draft, new Set(['지어낸 새말']))),
    ).toBe(0);
  });

  it('지운 낱말을 다시 [추가]하면 「지움」이 빠지고 사용만 견줌 — 차례는 끝', () => {
    const removed = removeTerms(BASE, new Set(['지어낸 초록', '지어낸 숲']));
    expect(termsCount(BASE, removed)).toBe(2);
    const again = addTerm(removed, '지어낸 초록');
    if (again.kind !== 'ok') throw new Error('추가 실패');
    expect(again.draft.map((term) => term.text)).toEqual([
      '지어낸 푸름',
      '지어낸 초록',
    ]);
    expect(termsCount(BASE, again.draft)).toBe(1); // 숲 지움만(초록은 켠 채 그대로)
    const forest = addTerm(again.draft, '지어낸 숲');
    if (forest.kind !== 'ok') throw new Error('추가 실패');
    expect(termsCount(BASE, forest.draft)).toBe(1); // 숲은 바탕에서 꺼져 있었다 — 켜서 다시 넣으면 사용 바꿈 1
  });

  it('더한 낱말은 끝 · trim 한 글 · 켬', () => {
    const added = addTerm(BASE, '  지어낸 새말  ');
    if (added.kind !== 'ok') throw new Error('추가 실패');
    expect(added.draft.at(-1)).toEqual({ text: '지어낸 새말', enabled: true });
    expect([...addedTexts(BASE, added.draft)]).toEqual(['지어낸 새말']);
    expect(addedTexts(BASE, BASE).size).toBe(0);
  });
});

describe('changed — 저장 창 「고친 것」 조각 하나(0 조각 뺌)', () => {
  it('안 고침 → 빈 목록 · 더함만 · 셋 다', () => {
    expect(termsChanged(BASE, BASE, WORDS)).toEqual([]);
    const added = addTerm(BASE, '지어낸 새말');
    if (added.kind !== 'ok') throw new Error('추가 실패');
    expect(termsChanged(BASE, added.draft, WORDS)).toEqual([
      '대상 단어 1개 추가',
    ]);
    const all = switchTerm(
      removeTerms(added.draft, new Set(['지어낸 초록'])),
      '지어낸 숲',
      true,
    );
    expect(termsChanged(BASE, all, WORDS)).toEqual([
      '대상 단어 1개 추가 · 1개 삭제 · 1개 사용 바꿈',
    ]);
    expect(
      termsChanged(BASE, switchTerm(BASE, '지어낸 숲', true), WORDS),
    ).toEqual(['대상 단어 1개 사용 바꿈']);
  });
});

describe('blocked — 켠 낱말 0 이면 저장을 끈다', () => {
  it('켠 것 0 → 참, 하나 → 거짓', () => {
    const none = switchTerm(
      switchTerm(BASE, '지어낸 초록', false),
      '지어낸 푸름',
      false,
    );
    expect(termsBlocked(none)).toBe(true);
    expect(termsBlocked(switchTerm(none, '지어낸 숲', true))).toBe(false);
    expect(termsBlocked([])).toBe(true);
  });
});

describe('받기 검사 넷(웹 — 글자 유무·보이지 않는 글자는 서버)', () => {
  it('길이 0자·31자 · 괄호·따옴표 · 키 겹침 · 101번째', () => {
    expect(termProblem(BASE, '')).toBe('length');
    expect(termProblem(BASE, '   ')).toBe('length');
    expect(termProblem(BASE, '가'.repeat(31))).toBe('length');
    expect(termProblem(BASE, '가'.repeat(30))).toBeNull();
    for (const bad of [
      '지어(낸',
      '지어]낸',
      '지어{낸',
      '"지어낸',
      "지어'낸",
      '“지어낸”',
    ])
      expect(termProblem(BASE, bad), bad).toBe('chars');
    const carbon: TermsDraft = [{ text: '지어낸 탄소 중립', enabled: true }];
    expect(termProblem(carbon, '지어낸탄소중립')).toBe('duplicate');
    expect(termProblem(carbon, '지어낸-탄소·중립')).toBe('duplicate');
    expect(termProblem(BASE, '지어낸 초록')).toBe('duplicate');
    const full: TermsDraft = Array.from({ length: 100 }, (_, index) => ({
      text: `지어낸말${index}`,
      enabled: index === 0,
    }));
    expect(termProblem(full, '지어낸 백하나')).toBe('count');
    expect(termProblem(full.slice(1), '지어낸 백')).toBeNull();
  });

  it('보지 않는 것은 통과(서버 TERMS_TEXT 몫): 「.」·제어 글자', () => {
    expect(termProblem(BASE, '.')).toBeNull();
    expect(termProblem(BASE, '지어낸\u0007말')).toBeNull();
  });

  it('검사에 걸리면 추가 0 — 갈래만', () => {
    expect(addTerm(BASE, '지어낸 초록')).toEqual({
      kind: 'problem',
      problem: 'duplicate',
    });
  });
});

describe('바탕 몫', () => {
  it('판 terms 목록 그대로 · null 이면 기본 낱말을 다 켬', () => {
    expect(termsBase(BASE, ['무시'])).toEqual(BASE);
    expect(termsBase(null, ['지어낸 하나', '지어낸 둘'])).toEqual([
      { text: '지어낸 하나', enabled: true },
      { text: '지어낸 둘', enabled: true },
    ]);
  });
});

describe('refusal — TERMS_* 넷 → 웹 글·짚은 자리, 모르는 code → null', () => {
  const refused = {
    TERMS_TEXT: '지어낸 글 거절',
    TERMS_DUPLICATE: '지어낸 겹침 거절',
    TERMS_COUNT: '지어낸 수 거절',
    TERMS_NONE_ENABLED: '지어낸 켬 거절',
  } as const;
  const words = { label: '대상 단어', refused };

  it('넷 다 「대상 단어 — <웹 글>」, 서버 문장은 안 보임', () => {
    expect(TERMS_CODES).toEqual(Object.keys(refused));
    for (const code of TERMS_CODES) {
      const out = termsRefusal(code, { terms: ['서버 문장'] }, words);
      expect(out?.line).toBe(`대상 단어 — ${refused[code]}`);
      expect(out?.refused).toEqual({ terms: [refused[code]] });
    }
  });

  it('줄 경로 terms.<i>.text 는 그 자리 그대로 · 다른 칸 경로는 뺌', () => {
    expect(
      termsRefusal(
        'TERMS_DUPLICATE',
        { 'terms.3.text': ['서버 문장'], title: ['다른 칸'] },
        words,
      ),
    ).toEqual({
      line: '대상 단어 — 지어낸 겹침 거절',
      refused: { 'terms.3.text': ['지어낸 겹침 거절'] },
    });
    expect(refusedRow('terms.3.text')).toBe(3);
    expect(refusedRow('terms')).toBeNull();
  });

  it('모르는 code · null → null', () => {
    expect(termsRefusal('AI_PROMPT_TEXT_EMPTY', {}, words)).toBeNull();
    expect(termsRefusal(null, {}, words)).toBeNull();
  });
});

describe('termKey — 서버 term_key 와 같은 키(고정 표, 출력되는 글자만 — X3)', () => {
  // 기대 키는 서버 wordcount.normalize_term(…).replace(' ', '') 를 같은 입력으로 돌린 값(보고 「term_key 대조」).
  const TABLE: readonly [string, string][] = [
    ['탄소중립', '탄소중립'],
    ['탄소 중립', '탄소중립'],
    ['탄소-중립', '탄소중립'],
    ['탄소_중립', '탄소중립'],
    ['탄소/중립', '탄소중립'],
    ['탄소·중립', '탄소중립'],
    ['탄소•중립', '탄소중립'],
    ['탄소∙중립', '탄소중립'],
    ['  탄소   중립  ', '탄소중립'],
    ['Net-Zero', 'netzero'],
    ['NET ZERO', 'netzero'],
    ['net_zero', 'netzero'],
    ['Eco', 'eco'],
    ['eco프리', 'eco프리'],
    ['ECO 프리', 'eco프리'],
    ['친환경', '친환경'],
    ['친 환경', '친환경'],
    ['RE100', 're100'],
    ['re-100', 're100'],
    ['Green/Bond', 'greenbond'],
    ['그린 · 워싱', '그린워싱'],
    ['A-B_C/D·E•F∙G', 'abcdefg'],
    ['Scope 3', 'scope3'],
    ['scope-3', 'scope3'],
  ];

  it.each(TABLE)('%s → %s', (raw, key) => {
    expect(termKey(raw)).toBe(key);
  });
});
