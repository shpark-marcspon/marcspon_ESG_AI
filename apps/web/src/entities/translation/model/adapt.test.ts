// 묶음 → 화면 꼴 잇기(밴드 TRW1a ① — 발주서 §3-1 7). 시험 표 하나로 상태·까닭·파트·회차·단계를 잰다. 값은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import {
  batchRowId,
  batchViewOf,
  partViewOf,
  rejectionKeyOf,
  runStateOf,
  splitBatchRowId,
  stageOf,
  tabStateOf,
} from './adapt.ts';
import type {
  BatchRun,
  Outcome,
  RunStatus,
  ServerRejectionKind,
  TranslationBatch,
  TranslationDigest,
} from './batch.ts';

const digest = (
  outcome: Outcome,
  rejectionKind: ServerRejectionKind | null = null,
): TranslationDigest => ({
  schemaVersion: 'translation.digest@1',
  status: outcome === 'rejected' ? 'rejected' : 'done',
  rejectionKind,
  outcome,
  pageCount: 3,
  failedPages: outcome === 'partial' ? [2] : [],
  variants: [],
  warningCount: 0,
});

const run = (status: RunStatus, extra: Partial<BatchRun> = {}): BatchRun => ({
  runId: 30,
  flowId: 'translation.colab@158',
  status,
  pages: { start: 4, end: 9 },
  style: { compareAb: false, single: 'B' },
  glossaryCounts: { base: 0, final: 12 },
  createdAt: '2026-10-19T11:48:00+09:00',
  startedAt: null,
  finishedAt: null,
  failedStep: null,
  errorCode: null,
  steps: [],
  digest: null,
  ...extra,
});

describe('상태 표 → TabState', () => {
  it.each<[string, BatchRun, string]>([
    ['queued', run('queued'), 'queued'],
    ['processing', run('processing'), 'running'],
    ['failed', run('failed', { errorCode: 'step_error' }), 'failed'],
    [
      'done · 요약 rejected',
      run('done', { digest: digest('rejected', 'too_large') }),
      'failed',
    ],
    [
      'done · 요약 partial',
      run('done', { digest: digest('partial') }),
      'failed_partial',
    ],
    ['done · 요약 done', run('done', { digest: digest('done') }), 'done'],
    ['done · 요약 없음(옛 실행)', run('done'), 'done'],
  ])('%s', (_, given, want) => expect(runStateOf(given)).toBe(want));

  it('앞 회차: outcome 으로 같은 표', () => {
    expect(tabStateOf('done', 'partial')).toBe('failed_partial');
    expect(tabStateOf('done', null)).toBe('done');
    expect(tabStateOf('processing', null)).toBe('running');
  });
});

describe('까닭 일곱 → 글 열쇠', () => {
  it.each<[ServerRejectionKind, string | undefined]>([
    ['no_pages', 'no_pages'],
    ['ceo_page_limit', 'ceo_over_limit'],
    ['unsupported_input', 'bad_file'],
    ['too_large', 'too_large'],
    ['over_budget', 'over_budget'],
    ['retry_source_not_found', undefined],
    ['retry_source_mismatch', undefined],
  ])('%s → %s', (kind, key) =>
    expect(
      rejectionKeyOf(run('done', { digest: digest('rejected', kind) })),
    ).toBe(key),
  );

  it('done 이 아니거나 거절이 아니면 없음', () => {
    expect(rejectionKeyOf(run('failed'))).toBeUndefined();
    expect(
      rejectionKeyOf(run('done', { digest: digest('partial') })),
    ).toBeUndefined();
  });
});

describe('단계 → StageCard', () => {
  it('prepare done · translate running · report pending → 2단계, 쪽 진행', () => {
    const given = run('processing', {
      steps: [
        { step: 'prepare', status: 'done', done: null, total: null },
        { step: 'translate', status: 'running', done: 20, total: 38 },
        { step: 'report', status: 'pending', done: null, total: null },
      ],
    });
    expect(stageOf(given)).toEqual({
      stageIndex: 2,
      stages: ['done', 'now', 'todo'],
    });
    expect(
      partViewOf({ part: 'story', latest: given, earlier: [], round: 1 }).pages,
    ).toEqual({
      done: 20,
      total: 38,
    });
  });

  it('단계가 없으면 셋 다 대기·1단계, 다 끝나면 3단계, 실패 단계 그대로', () => {
    expect(stageOf(run('queued'))).toEqual({
      stageIndex: 1,
      stages: ['todo', 'todo', 'todo'],
    });
    const all = ['prepare', 'translate', 'report'].map((step) => ({
      step,
      status: 'done' as const,
      done: null,
      total: null,
    }));
    expect(stageOf(run('done', { steps: all })).stageIndex).toBe(3);
    expect(
      stageOf(
        run('failed', {
          steps: [
            { step: 'prepare', status: 'failed', done: null, total: null },
          ],
        }),
      ),
    ).toEqual({ stageIndex: 1, stages: ['failed', 'todo', 'todo'] });
  });

  it('쪽 진행은 둘 다 수일 때만(진행 중 파트만)', () => {
    const given = run('processing', {
      steps: [{ step: 'translate', status: 'running', done: null, total: 38 }],
    });
    expect(
      partViewOf({ part: 'story', latest: given, earlier: [], round: 1 }).pages,
    ).toBeUndefined();
  });
});

describe('묶음 → BatchView', () => {
  const batch: TranslationBatch = {
    batchKey: '0b9f1a2c-3d4e-4f50-8a6b-7c8d9e0f1a2b',
    inputKind: 'word',
    file: {
      id: 12,
      fileName: 'sample_report_ko_extract.docx',
      uploadedAt: '2026-10-19T02:40:00+00:00',
      uploadedBy: { userId: 7, name: '담당자 가' },
    },
    createdBy: { userId: 7, name: '담당자 가' },
    parts: [
      {
        part: 'ceo_message',
        latest: run('done', {
          runId: 31,
          pages: { start: 1, end: 3 },
          digest: digest('done'),
          createdAt: '2026-10-19T11:48:00+09:00',
          startedAt: '2026-10-19T11:48:30+09:00',
          finishedAt: '2026-10-19T11:55:00+09:00',
        }),
        earlier: [],
        round: 1,
      },
      {
        part: 'story',
        latest: run('processing', {
          runId: 40,
          createdAt: '2026-10-19T14:10:00+09:00',
        }),
        earlier: [
          {
            runId: 32,
            status: 'done',
            createdAt: '2026-10-19T11:48:00+09:00',
            finishedAt: '2026-10-19T12:00:00+09:00',
            outcome: 'partial',
          },
        ],
        round: 2,
      },
    ],
    state: 'active',
    doneParts: 1,
    partCount: 2,
  };

  it('ceo_message ↔ ceo, 회차·앞 회차, 시각 꼴, 마지막 시작, 스타일 열쇠', () => {
    const view = batchViewOf(batch);
    expect(view).toMatchObject({
      rowId: `12/${batch.batchKey}`,
      documentId: '12',
      fileName: 'sample_report_ko_extract.docx',
      uploaded: '2026-10-19 11:40',
      uploader: '담당자 가',
      lastStarted: '2026-10-19 14:10',
      style: 'B',
    });
    expect(view.parts.map((p) => p.part)).toEqual(['ceo', 'story']);
    expect(view.parts[0]).toMatchObject({
      runId: '31',
      rangeText: '1~3',
      round: 1,
      started: '2026-10-19 11:48',
      finished: '2026-10-19 11:55',
      state: 'done',
      glossaryCount: 12,
    });
    expect(view.parts[1]!.earlier).toEqual([
      { round: 1, state: 'failed_partial', at: '2026-10-19 12:00' },
    ]);
  });

  it('올림 전·범위 모름·문체 모름은 null(0·빈 글로 삼키지 않음)', () => {
    const view = batchViewOf({
      ...batch,
      file: { ...batch.file, uploadedAt: null },
      parts: [
        {
          ...batch.parts[0]!,
          latest: { ...batch.parts[0]!.latest, pages: null, style: null },
        },
      ],
    });
    expect(view.uploaded).toBeNull();
    expect(view.style).toBeNull();
    expect(view.parts[0]!.range).toBeNull();
    expect(view.parts[0]!.rangeText).toBeNull();
  });

  it('A·B 견주기 → AB', () => {
    const view = batchViewOf({
      ...batch,
      parts: [
        {
          ...batch.parts[0]!,
          latest: {
            ...batch.parts[0]!.latest,
            style: { compareAb: true, single: 'B' },
          },
        },
      ],
    });
    expect(view.style).toBe('AB');
  });

  it('줄 열쇠 왕복', () => {
    expect(splitBatchRowId(batchRowId('12', 'run-3'))).toEqual({
      documentId: '12',
      batchKey: 'run-3',
    });
    expect(splitBatchRowId('nope')).toBeNull();
  });
});
