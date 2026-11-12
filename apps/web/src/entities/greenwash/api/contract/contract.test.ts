// 계약 예시 파일이 거울을 지나는가(밴드 FW2 ① §3). 예시는 백엔드 저장소 자리를 읽기만 한다(옮기지 않는다):
//   apps/api-py/esgapi/greenwash/tests/data/contract-examples/ — result 넷, review 셋.
// 심은 파손 (다): obj 에서 .strict() 를 빼면 「속 객체의 모르는 키」 시험이 빨강이다. 맨 위 객체는 strip 이다(결함 D10, 밴드 WC1 ①).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { parseResult, parseReview, parseReviewUpdate } from './index.ts';

const examples = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../../api-py/esgapi/greenwash/tests/data/contract-examples',
);
const read = (name: string): unknown =>
  JSON.parse(readFileSync(resolve(examples, name), 'utf8'));

const RESULTS = [
  'result-normal.json',
  'result-many.json',
  'result-no-pages.json',
  'result-dry-run.json',
];
const REVIEWS = [
  'review/review-pending.json',
  'review/review-in-review.json',
  'review/review-confirmed.json',
  'review/review-edited.json',
];

type Json = Record<string, unknown>;
const clone = (value: unknown) => structuredClone(value) as Json;

describe('계약 예시 → 거울', () => {
  it.each(RESULTS)('결과 %s 는 지난다', (name) => {
    const parsed = parseResult(read(name));
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
  });

  it.each(REVIEWS)('검토 %s 는 지난다', (name) => {
    const parsed = parseReview(read(name));
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
  });

  it('갈래: normal 은 점검한 실행(dryRun null), dry-run 은 dryRun 이 있고 items 가 빈 목록', () => {
    const normal = parseResult(read('result-normal.json'));
    const dry = parseResult(read('result-dry-run.json'));
    expect(normal.ok && normal.value.dryRun).toBeNull();
    expect(dry.ok && dry.value.dryRun !== null).toBe(true);
    expect(dry.ok && dry.value.items).toEqual([]);
  });

  it('판 단어로 센 실행의 terms(밴드 G2d ③): 있어도 없어도 지나고, 있으면 그대로 싣는다(두 갈래)', () => {
    for (const name of ['result-normal.json', 'result-dry-run.json']) {
      const without = parseResult(read(name));
      expect(without.ok && 'terms' in without.value).toBe(false);
      const value = clone(read(name));
      value.terms = ['지어낸 낱말', '탄소중립'];
      const parsed = parseResult(value);
      expect(parsed.ok ? parsed.value.terms : parsed.issues).toEqual([
        '지어낸 낱말',
        '탄소중립',
      ]);
    }
  });
});

describe('단어 글자 수는 코드 포인트(GWB1, MARC-ISSUE-320)', () => {
  // CJK 확장 B(U+20000 대)는 한 글자가 UTF-16 둘이다. 서버는 코드 포인트로 1~30자를 받는다. zod 4 의 .max 는 UTF-16 수가
  // 넘으면 코드 포인트로 다시 센다(zod v4/core/checks.js) — 그 단위를 이 시험이 못박는다(zod 를 바꾸면 여기서 드러남).
  const wide = (n: number) =>
    Array.from({ length: n }, (_, i) => String.fromCodePoint(0x20000 + i)).join(
      '',
    );

  it.each(['terms', 'extraTerms'])(
    '%s: 확장 B 30자 단어는 지나고 31자·빈 글은 거절',
    (field) => {
      for (const name of ['result-normal.json', 'result-dry-run.json']) {
        const ok = clone(read(name));
        ok[field] = [wide(30), '지어낸 낱말'];
        const parsed = parseResult(ok);
        expect(
          parsed.ok ? parsed.value[field as 'terms'] : parsed.issues,
        ).toEqual([wide(30), '지어낸 낱말']);
        for (const bad of [wide(31), '']) {
          const refused = clone(read(name));
          refused[field] = [bad];
          expect(parseResult(refused).ok).toBe(false);
        }
      }
    },
  );
});

describe('맨 위만 strip(결함 D10)', () => {
  it('맨 위의 모르는 키는 버리고 지난다(결과 두 갈래·검토)', () => {
    for (const name of ['result-normal.json', 'result-dry-run.json']) {
      const value = clone(read(name));
      value.surprise = 1;
      const parsed = parseResult(value);
      expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
      expect(parsed.ok && 'surprise' in parsed.value).toBe(false);
    }
    const review = clone(read('review/review-pending.json'));
    review.unknown_extra = '김목';
    const parsed = parseReview(review);
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
    expect(parsed.ok && 'unknown_extra' in parsed.value).toBe(false);
  });

  it('맨 위라도 필수 칸이 없거나 타입이 틀리면 거절', () => {
    const missing = clone(read('result-normal.json'));
    delete missing.wordCounts;
    expect(parseResult(missing).ok).toBe(false);
    const wrong = clone(read('result-normal.json'));
    wrong.promptVersion = 1;
    expect(parseResult(wrong).ok).toBe(false);
    const review = clone(read('review/review-confirmed.json'));
    delete review.confirmedBy;
    expect(parseReview(review).ok).toBe(false);
  });

  it('review@2 의 edits 는 필수 칸 — 없으면 거절(기본값으로 채우지 않는다. 밴드 G1b-3 검증 1 R1)', () => {
    const noEdits = clone(read('review/review-edited.json'));
    expect(parseReview(noEdits).ok).toBe(true);
    delete noEdits.edits;
    const parsed = parseReview(noEdits);
    expect(parsed.ok ? 'ok' : parsed.issues).toMatch(/^edits: /);
  });
});

describe('거울이 거절한다', () => {
  it('속 객체의 모르는 키(문장 한 줄, 쪽 위 자리, 검토 표시)', () => {
    const item = clone(read('result-normal.json'));
    ((item.items as Json[])[0] as Json).note = '더한 칸';
    expect(parseResult(item).ok).toBe(false);

    const position = clone(read('result-normal.json'));
    (((position.items as Json[])[0] as Json).position as Json).width = 10;
    expect(parseResult(position).ok).toBe(false);

    const review = clone(read('review/review-in-review.json'));
    ((review.marks as Json[])[0] as Json).by = 'me';
    expect(parseReview(review).ok).toBe(false);
  });

  it('level 「Critical」', () => {
    const value = clone(read('result-normal.json'));
    ((value.items as Json[])[0] as Json).level = 'Critical';
    const parsed = parseResult(value);
    expect(parsed.ok).toBe(false);
  });

  it('실패 글에 틀린 칸의 경로가 나온다(union 이 「(맨 위)」 하나로 접지 않는다. sid:MARC-ISSUE-133)', () => {
    const value = clone(read('result-normal.json'));
    ((value.items as Json[])[0] as Json).level = 'Medium';
    const parsed = parseResult(value);
    expect(parsed.ok ? 'ok' : parsed.issues).toMatch(/^items\.0\.level: /);

    const dry = clone(read('result-dry-run.json'));
    (dry.dryRun as Json).chunks = -1;
    const dryParsed = parseResult(dry);
    expect(dryParsed.ok ? 'ok' : dryParsed.issues).toMatch(/^dryRun\.chunks: /);
  });

  it('갈래가 섞이면: dryRun 이 null 인데 counts 가 null', () => {
    const value = clone(read('result-normal.json'));
    value.counts = null;
    expect(parseResult(value).ok).toBe(false);
  });

  it('dry-run 인데 items 가 있으면', () => {
    const value = clone(read('result-dry-run.json'));
    value.items = (clone(read('result-normal.json')).items as Json[]).slice(
      0,
      1,
    );
    expect(parseResult(value).ok).toBe(false);
  });

  it('칸이 빠지면(exampleSentence), 쪽이 0 이면, 상자가 넷이 아니면', () => {
    const missing = clone(read('result-normal.json'));
    delete ((missing.items as Json[])[0] as Json).exampleSentence;
    expect(parseResult(missing).ok).toBe(false);

    const zeroPage = clone(read('result-normal.json'));
    ((zeroPage.items as Json[])[0] as Json).page = 0;
    expect(parseResult(zeroPage).ok).toBe(false);

    const box = clone(read('result-normal.json'));
    (((box.items as Json[])[0] as Json).position as Json).boxes = [[1, 2, 3]];
    expect(parseResult(box).ok).toBe(false);
  });

  it('검토: 모르는 상태, 정수가 아닌 runId', () => {
    const state = clone(read('review/review-pending.json'));
    state.state = 'done';
    expect(parseReview(state).ok).toBe(false);
    const runId = clone(read('review/review-pending.json'));
    runId.runId = '101';
    expect(parseReview(runId).ok).toBe(false);
  });
});

describe('PUT 본문 거울', () => {
  it('state 는 없어도, null 이어도, confirmed 여도 된다. in_review·pending 은 거절(결함 D1). 모르는 칸은 거절', () => {
    const marks = [{ itemIndex: 0, decision: 'adopted', excludeReason: null }];
    expect(parseReviewUpdate({ marks }).ok).toBe(true);
    expect(parseReviewUpdate({ state: null, marks }).ok).toBe(true);
    expect(parseReviewUpdate({ state: 'confirmed', marks }).ok).toBe(true);
    expect(parseReviewUpdate({ state: 'in_review', marks }).ok).toBe(false);
    expect(parseReviewUpdate({ state: 'pending', marks }).ok).toBe(false);
    expect(parseReviewUpdate({ marks, runId: 1 }).ok).toBe(false);
    expect(
      parseReviewUpdate({
        marks: [{ itemIndex: -1, decision: 'adopted', excludeReason: null }],
      }).ok,
    ).toBe(false);
  });
});
