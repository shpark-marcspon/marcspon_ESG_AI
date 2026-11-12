// 그린워싱 AI 설정 판의 순수 함수(밴드 AD2R ① — 발주서 §3 A). 자료는 가짜 서버의 지어낸 판 셋(id 11·12·13)과 저장 판 0 묶음.
import { describe, expect, it } from 'vitest';

import {
  fakeDefaultSetting,
  fakeSettingList,
  fakeSettings,
} from '../api/testing.ts';
import {
  CRITERION_IDS,
  DEFAULT_KEY,
  criterionTextProblem,
  firstPick,
  idOut,
  saveBody,
  versionRows,
} from './setting.ts';
import type { SettingList } from './setting.ts';

const withSaved = (): SettingList => fakeSettingList(fakeSettings());
const empty = (): SettingList => fakeSettingList([]);

describe('판 열 줄', () => {
  it('저장 판은 서버 차례 그대로, 기본 판 줄은 맨 아래 — 저장 판이 적용 중이면 기본 판 배지는 「기본」', () => {
    const rows = versionRows(withSaved());
    expect(rows.map((row) => [row.key, row.name, row.badge])).toEqual([
      ['13', 'v3', 'testing'],
      ['12', 'v2', 'applied'],
      ['11', 'v1', 'past'],
      [DEFAULT_KEY, 'colab-2026-01-15-v1', 'default'],
    ]);
  });

  it('저장 판이 없고 applied 가 default 면 기본 판 줄 하나가 「적용 중」', () => {
    expect(
      versionRows(empty()).map((row) => [row.kind, row.key, row.badge]),
    ).toEqual([['default', DEFAULT_KEY, 'applied']]);
  });
});

describe('처음 고름', () => {
  const rows = versionRows(withSaved());

  it('이름이 맞는 판 → 없으면 가장 새 시험 중', () => {
    expect(firstPick(rows, 'v1')).toBe('11');
    expect(firstPick(rows, 'v9')).toBe('13');
    expect(firstPick(rows, undefined)).toBe('13');
    expect(firstPick(rows, 'colab-2026-01-15-v1')).toBe(DEFAULT_KEY);
  });

  it('시험 중이 없으면 적용 중(저장 판), 그것도 없으면 기본 판', () => {
    const noTesting = rows.filter((row) => row.badge !== 'testing');
    expect(firstPick(noTesting, undefined)).toBe('12');
    expect(firstPick(versionRows(empty()), undefined)).toBe(DEFAULT_KEY);
    const pastOnly = versionRows(
      fakeSettingList(
        fakeSettings().filter((one) => one.id === 11),
        { kind: 'default' },
      ),
    );
    expect(firstPick(pastOnly, undefined)).toBe(DEFAULT_KEY);
  });
});

describe('기준 글 검사(서버 받기와 같은 차례)', () => {
  it('trim 뒤 빈 글은 length', () => {
    expect(criterionTextProblem('')).toBe('length');
    expect(criterionTextProblem('   ')).toBe('length');
  });

  it('300 코드 포인트까지(이모지는 하나로 센다), 301 은 length', () => {
    const emoji = '🌱';
    const exactly = emoji.repeat(100) + '가'.repeat(200);
    expect([...exactly].length).toBe(300);
    expect(exactly.length).toBeGreaterThan(300);
    expect(criterionTextProblem(exactly)).toBeNull();
    expect(criterionTextProblem(`  ${exactly}  `)).toBeNull();
    expect(criterionTextProblem(exactly + '가')).toBe('length');
  });

  it('줄바꿈·줄 나눔·서식 글자·탭은 multiline', () => {
    for (const text of ['a\nb', 'a b', 'a​b', 'a\tb', 'a\rb'])
      expect(criterionTextProblem(text), JSON.stringify(text)).toBe(
        'multiline',
      );
    expect(criterionTextProblem('지어낸 기준 글 한 줄')).toBeNull();
  });

  it('길이를 먼저 본다(서버 차례 — 301자에 줄바꿈이 있어도 length)', () => {
    expect(criterionTextProblem('가'.repeat(300) + '\n가')).toBe('length');
  });
});

describe('저장 본문', () => {
  const base = fakeSettings()[1]!.criteria;
  /** 지어낸 모델 설정·프롬프트(AD2W ③ — 본문 다섯 칸). */
  const modelSettings = {
    steps: [
      {
        key: 'judge',
        route: 'fake-mini',
        temperature: 0.2,
        maxOutputTokens: 2000,
        webSearch: false,
      },
    ],
  };
  const prompts = {
    steps: [
      {
        key: 'judge',
        prompts: [
          { key: 'detect', text: '지어낸 찾기 글', memo: '지어낸 메모' },
          { key: 'eval', text: '지어낸 판정 글', memo: '' },
        ],
      },
    ],
  };
  const input = (
    criteria: Parameters<typeof saveBody>[0]['criteria'],
    rows = criteria.rows,
  ) => ({
    criteria: { ...criteria, rows },
    title: '지어낸 판 이름',
    memo: '',
    modelSettings,
    prompts,
    terms: null,
  });

  it('키 정확히: title + criteria{schemaVersion, version, rows} + memo + modelSettings + prompts + terms', () => {
    const body = saveBody(input(base));
    expect(Object.keys(body)).toEqual([
      'title',
      'criteria',
      'memo',
      'modelSettings',
      'prompts',
      'terms',
    ]);
    expect(body.terms).toBeNull();
    expect(body.title).toBe('지어낸 판 이름');
    expect(body.memo).toBe('');
    expect(Object.keys(body.criteria)).toEqual([
      'schemaVersion',
      'version',
      'rows',
    ]);
    expect(body.criteria.schemaVersion).toBe('greenwash.criteria@1');
    expect(body.criteria.version).toBe('v2');
  });

  it('rows 15줄 차례 그대로, terms·guideline 그대로, 모르는 칸은 빠진다', () => {
    const rows = base.rows.map((row) =>
      row.id === 'high-2' ?
        { ...row, enabled: false, extra: 'x' as unknown as never }
      : row,
    );
    const body = saveBody(input(base, rows));
    expect(body.criteria.rows.map((row) => row.id)).toEqual([...CRITERION_IDS]);
    expect(body.criteria.rows).toEqual(
      base.rows.map((row) =>
        row.id === 'high-2' ? { ...row, enabled: false } : row,
      ),
    );
    expect(body.criteria.rows[0]!.terms).toEqual(base.rows[0]!.terms);
    expect(body.criteria.rows[0]!.terms).not.toBe(base.rows[0]!.terms);
    for (const row of body.criteria.rows)
      expect(Object.keys(row)).toEqual([
        'id',
        'category',
        'order',
        'enabled',
        'text',
        'terms',
        'verdict',
        'guideline',
      ]);
  });

  it('G2d: 대상 단어는 받은 차례 그대로 {text, enabled} 만 새 객체로 싣는다(모르는 칸은 빠진다)', () => {
    const given = [
      { text: '지어낸 초록낱말', enabled: true, extra: 'x' },
      { text: '친환경', enabled: false },
    ];
    const body = saveBody({ ...input(base), terms: given });
    expect(body.terms).toEqual([
      { text: '지어낸 초록낱말', enabled: true },
      { text: '친환경', enabled: false },
    ]);
    expect(body.terms![1]).not.toBe(given[1]);
  });

  it('기본 판 바탕이면 version 은 기본 판 이름(서버가 새 이름으로 덮는다)', () => {
    const fallback = fakeDefaultSetting().criteria;
    expect(saveBody(input(fallback)).criteria.version).toBe(
      'colab-2026-01-15-v1',
    );
  });

  it('판 메모·모델 설정·프롬프트는 받은 값 그대로(계약 칸만 — 모르는 칸은 빠진다), 바뀐 객체는 새로 담는다', () => {
    const extra = { extra: 'x' } as Record<string, unknown>;
    const body = saveBody({
      ...input(base),
      memo: '지어낸 판 메모',
      modelSettings: {
        steps: [{ ...modelSettings.steps[0]!, temperature: null, ...extra }],
      },
      prompts: {
        steps: [
          {
            ...prompts.steps[0]!,
            ...extra,
            prompts: prompts.steps[0]!.prompts.map((one) => ({
              ...one,
              ...extra,
            })),
          },
        ],
      },
    });
    expect(body.memo).toBe('지어낸 판 메모');
    expect(body.modelSettings).toEqual({
      steps: [
        {
          key: 'judge',
          route: 'fake-mini',
          temperature: null,
          maxOutputTokens: 2000,
          webSearch: false,
        },
      ],
    });
    expect(body.prompts).toEqual(prompts);
    expect(body.prompts!.steps[0]!.prompts).not.toBe(prompts.steps[0]!.prompts);
  });
});

describe('나가는 id', () => {
  it('양의 정수 글자만 숫자로', () => {
    expect(idOut('12')).toBe(12);
    expect(idOut('1')).toBe(1);
    for (const id of [
      '012',
      '1.5',
      '',
      'v3',
      '0',
      '-1',
      '1e3',
      ' 12',
      '99999999999999999999',
    ])
      expect(idOut(id), id).toBeNull();
  });
});
