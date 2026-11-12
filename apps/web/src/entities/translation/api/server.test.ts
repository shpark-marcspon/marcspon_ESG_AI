// 영문번역 실어댑터(밴드 TRW1a ① — 발주서 §3-1 1~5). 진짜 어댑터 + 가짜 서버(testing.ts). 값은 전부 지어낸 것이다.
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  OPTIONS_MAX_OCTETS,
  PAGES_TIMEOUT_MS,
  optionsOctets,
  optionsOf,
} from './server.ts';
import { storeErrorKind } from './store.ts';
import type { StartInput } from './store.ts';
import {
  FAKE_PAIRS,
  fakeDocument,
  fakeLayout,
  fakeOptions,
  fakeRun,
  fakeSteps,
  fakeTranslationServer,
  json,
  refusal,
  serverStoreOf,
  unreachable,
} from './testing.ts';

/** POST /runs 본문(시험이 읽는 칸). */
interface RunBody {
  module: string;
  documentId: number;
  launchKey: string;
  options: Record<string, unknown> & {
    batchId: string;
    part: string;
    ceoPageLimit: number | null;
    pages: unknown;
    glossary: unknown;
    peerGroupStyle?: unknown;
  };
}

const BATCH = '0b9f1a2c-3d4e-4f50-8a6b-7c8d9e0f1a2b';
const KEYS = [
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
  '55555555-5555-4555-8555-555555555555',
];
/** 차례대로 열쇠를 내주는 지은 함수(batchId · launchKey · 파트마다 Idempotency-Key). */
const keys = () => {
  let at = 0;
  return () => KEYS[at++ % KEYS.length]!;
};

const kindOf = async (promise: Promise<unknown>) => {
  try {
    await promise;
  } catch (error) {
    return storeErrorKind(error);
  }
  return 'resolved';
};

const input = (extra: Partial<StartInput> = {}): StartInput => ({
  documentId: '12',
  parts: [
    { part: 'ceo', range: { from: 1, to: 3 } },
    { part: 'story', range: { from: 4, to: 9 } },
  ],
  company: {
    name: 'Sample Corp',
    preferredSubject: 'virtual services',
    industryStandards: 'GRI',
  },
  style: { compareAb: false, single: 'B' },
  glossary: { final: FAKE_PAIRS.map((pair) => ({ ...pair })) },
  peerGroupStyle: null,
  ...extra,
});

describe('uploadDocument (§3-1 1)', () => {
  it('세 요청 차례·본문(+ GET pages, 밴드 TRP6), 쪽 수 null 이면 null', async () => {
    const server = fakeTranslationServer();
    const store = serverStoreOf(server);
    const file = new File(['[PAGE 1]\nabc'], 'extract.txt');
    const doc = await store.uploadDocument(file);
    expect(server.calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      'POST /documents',
      'POST /documents/12/confirm',
      'GET /translation/documents/12/pages',
    ]);
    expect(server.calls[0]!.body).toEqual({
      fileName: 'extract.txt',
      sizeBytes: file.size,
    });
    expect(server.uploads).toEqual([
      {
        url: 'http://test.local/api/fake-upload/12',
        method: 'PUT',
        size: file.size,
      },
    ]);
    expect(doc).toMatchObject({
      documentId: '12',
      fileName: 'extract.txt',
      pageCount: null,
    });
  });

  it('서버가 쪽 수를 주면 그대로', async () => {
    const server = fakeTranslationServer({ serverPageCount: 64 });
    const doc = await serverStoreOf(server).uploadDocument(
      new File(['x'], 'a.txt'),
    );
    expect(doc.pageCount).toBe(64);
  });

  it('confirm 거절 → 거절, pages 0번', async () => {
    const server = fakeTranslationServer();
    server.override['POST /documents/12/confirm'] = () =>
      refusal(409, 'UPLOAD_SIZE_MISMATCH');
    expect(
      await kindOf(
        serverStoreOf(server).uploadDocument(new File(['x'], 'a.txt')),
      ),
    ).toBe('rejected');
    expect(server.count('GET /translation/documents/12/pages')).toBe(0);
  });

  it('서명 올림 실패 → confirm 0·거절', async () => {
    const server = fakeTranslationServer();
    const store = serverStoreOf(server, {
      sendUpload: async () => {
        throw new Error('put failed');
      },
    });
    expect(await kindOf(store.uploadDocument(new File(['x'], 'a.txt')))).toBe(
      'rejected',
    );
    expect(server.count('POST /documents/12/confirm')).toBe(0);
  });
});

describe('uploadDocument 의 쪽 수 — GET …/pages (밴드 TRP6 §3-5 14)', () => {
  const PAGES = 'GET /translation/documents/12/pages';
  const upload = (server: ReturnType<typeof fakeTranslationServer>) =>
    serverStoreOf(server).uploadDocument(new File(['[PAGE 1]'], 'a.docx'));

  afterEach(() => {
    vi.useRealTimers();
  });

  it('pages 7(confirm null) → 7', async () => {
    const server = fakeTranslationServer({ translationPageCount: 7 });
    expect((await upload(server)).pageCount).toBe(7);
    expect(server.count(PAGES)).toBe(1);
  });

  it('pages null 이면 confirm 64 를 덮어 null(이름만 .txt 인 PDF 꼴)', async () => {
    const server = fakeTranslationServer({
      serverPageCount: 64,
      translationPageCount: null,
    });
    expect((await upload(server)).pageCount).toBeNull();
  });

  const fallbacks: [string, () => Response | Promise<Response>][] = [
    ['404', () => refusal(404, 'NOT_FOUND')],
    ['500', () => refusal(500, 'INTERNAL_ERROR')],
    ['끊김', () => unreachable()],
    ['documentId 다름', () => json(200, { documentId: 13, pageCount: 7 })],
    ['0', () => json(200, { documentId: 12, pageCount: 0 })],
    ['음수', () => json(200, { documentId: 12, pageCount: -3 })],
    ['글자', () => json(200, { documentId: 12, pageCount: '7' })],
    ['소수', () => json(200, { documentId: 12, pageCount: 2.5 })],
    ['칸 없음', () => json(200, { documentId: 12 })],
    [
      '수가 너무 큼(JSON 1e400 → Infinity)',
      () =>
        new Response('{"documentId":12,"pageCount":1e400}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    ],
  ];
  it.each(fallbacks)(
    'pages %s → confirm 의 쪽 수, 올림 성공·다시 보내기 0',
    async (_name, answer) => {
      const server = fakeTranslationServer({ serverPageCount: 64 });
      server.override[PAGES] = answer;
      const doc = await upload(server);
      expect(doc).toMatchObject({ documentId: '12', pageCount: 64 });
      expect(server.count(PAGES)).toBe(1);
    },
  );

  it('5초 넘김(가짜 타이머 + 늦춤) → confirm 의 쪽 수', async () => {
    vi.useFakeTimers();
    const server = fakeTranslationServer({ serverPageCount: 64 });
    server.override[PAGES] = () =>
      new Promise((resolve) => {
        setTimeout(
          () => resolve(json(200, { documentId: 12, pageCount: 7 })),
          PAGES_TIMEOUT_MS * 4,
        );
      });
    let settled: number | null | undefined;
    const pending = upload(server).then((doc) => {
      settled = doc.pageCount;
    });
    await vi.advanceTimersByTimeAsync(PAGES_TIMEOUT_MS - 1);
    expect(settled).toBeUndefined(); // 상한 전에는 기다린다
    await vi.advanceTimersByTimeAsync(1);
    await pending;
    expect(settled).toBe(64);
    expect(PAGES_TIMEOUT_MS).toBe(5000);
  });

  it('상한 안에 온 늦은 답은 받는다', async () => {
    vi.useFakeTimers();
    const server = fakeTranslationServer({ serverPageCount: 64 });
    server.override[PAGES] = () =>
      new Promise((resolve) => {
        setTimeout(
          () => resolve(json(200, { documentId: 12, pageCount: 9 })),
          PAGES_TIMEOUT_MS - 100,
        );
      });
    const pending = upload(server);
    await vi.advanceTimersByTimeAsync(PAGES_TIMEOUT_MS);
    expect((await pending).pageCount).toBe(9);
  });
});

describe('startBatch (§3-1 2)', () => {
  const ready = () => fakeTranslationServer({ documents: [fakeDocument(12)] });

  it('파트 둘 → POST /runs 둘: batchId 같음·launchKey 같음·둘은 서로 다름, Idempotency-Key 서로 다름', async () => {
    const server = ready();
    const result = await serverStoreOf(server, { newKey: keys() }).startBatch(
      input(),
    );
    const bodies = server.runBodies();
    expect(bodies).toHaveLength(2);
    const [a, b] = bodies as unknown as [RunBody, RunBody];
    expect(a.options.batchId).toBe(KEYS[0]);
    expect(b.options.batchId).toBe(KEYS[0]);
    expect(a.launchKey).toBe(KEYS[1]);
    expect(b.launchKey).toBe(KEYS[1]);
    expect(a.launchKey).not.toBe(a.options.batchId);
    const idem = server.calls
      .filter((c) => c.path === '/runs')
      .map((c) => c.headers.get('Idempotency-Key'));
    expect(idem).toEqual([KEYS[2], KEYS[3]]);
    expect(result).toEqual({
      kind: 'started',
      documentId: '12',
      batchKey: KEYS[0],
      runs: [
        { part: 'ceo', runId: '20' },
        { part: 'story', runId: '21' },
      ],
      failed: [],
    });
  });

  it('본문: module·documentId 수·ceoPageLimit 6/null·서버 파트 이름·쪽 범위, autofix·retry·companyId·flowId 없음', async () => {
    const server = ready();
    await serverStoreOf(server, { newKey: keys() }).startBatch(input());
    const [a, b] = server.runBodies() as unknown as [RunBody, RunBody];
    expect(a.module).toBe('translation');
    expect(a.documentId).toBe(12);
    expect(a.options.part).toBe('ceo_message');
    expect(a.options.ceoPageLimit).toBe(6);
    expect(b.options.part).toBe('story');
    expect(b.options.ceoPageLimit).toBeNull();
    expect('ceoPageLimit' in b.options).toBe(true);
    expect(a.options.pages).toEqual({ start: 1, end: 3 });
    expect(b.options.pages).toEqual({ start: 4, end: 9 });
    for (const body of [a, b]) {
      expect(Object.keys(body).sort()).toEqual(
        ['documentId', 'launchKey', 'module', 'options'].sort(),
      );
      for (const key of ['autofix', 'retry', 'companyId', 'flowId'])
        expect(key in body.options).toBe(false);
    }
    expect(a.options.glossary).toEqual({ final: FAKE_PAIRS });
    expect('peerGroupStyle' in a.options).toBe(false);
  });

  it('평가용어집·참고 문체를 켜면 base·peerGroupStyle 을 싣는다', async () => {
    const server = ready();
    await serverStoreOf(server, { newKey: keys() }).startBatch(
      input({
        parts: [{ part: 'general', range: { from: 2, to: 2 } }],
        glossary: { base: [{ ko: '가상', en: 'Virtual' }], final: [] },
        peerGroupStyle: 'calm tone',
      }),
    );
    const [a] = server.runBodies() as unknown as [RunBody];
    expect(a.options.glossary).toEqual({
      base: [{ ko: '가상', en: 'Virtual' }],
      final: [],
    });
    expect(a.options.peerGroupStyle).toEqual({ prompt: 'calm tone' });
  });

  it('빈 파트는 0번(입력에 든 파트만)', async () => {
    const server = ready();
    await serverStoreOf(server, { newKey: keys() }).startBatch(
      input({ parts: [{ part: 'general', range: { from: 5, to: 8 } }] }),
    );
    expect(server.count('POST /runs')).toBe(1);
  });

  it('옵션 바이트 = 상한이면 보내고, +1 이면 하나도 보내지 않고 too_long', async () => {
    const base = input({
      parts: [{ part: 'general', range: { from: 1, to: 2 } }],
    });
    const size = (text: string) =>
      optionsOctets(
        optionsOf(
          { ...base, peerGroupStyle: text },
          'general',
          { from: 1, to: 2 },
          BATCH,
        ),
      );
    const pad = OPTIONS_MAX_OCTETS - size('');
    const exact = 'a'.repeat(pad);
    expect(size(exact)).toBe(OPTIONS_MAX_OCTETS);

    const ok = ready();
    const sent = await serverStoreOf(ok, { newKey: () => BATCH }).startBatch({
      ...base,
      peerGroupStyle: exact,
    });
    expect(sent.kind).toBe('started');

    const over = ready();
    const refused = await serverStoreOf(over, {
      newKey: () => BATCH,
    }).startBatch({ ...base, peerGroupStyle: `${exact}a` });
    expect(refused).toEqual({ kind: 'too_long' });
    expect(over.count('POST /runs')).toBe(0);
  });

  it('서버 셈(구분자 공백)으로 상한을 넘으면 too_long — JSON.stringify 로는 상한 아래', async () => {
    const base = input({
      parts: [{ part: 'general', range: { from: 1, to: 2 } }],
    });
    const optionsWith = (text: string) =>
      optionsOf(
        { ...base, peerGroupStyle: text },
        'general',
        { from: 1, to: 2 },
        BATCH,
      );
    const pad = OPTIONS_MAX_OCTETS + 1 - optionsOctets(optionsWith(''));
    const over = optionsWith('a'.repeat(pad));
    expect(optionsOctets(over)).toBe(OPTIONS_MAX_OCTETS + 1);
    // 옛 셈(JSON.stringify)은 문턱 아래였다.
    expect(
      new TextEncoder().encode(JSON.stringify(over)).length,
    ).toBeLessThanOrEqual(OPTIONS_MAX_OCTETS);

    const server = ready();
    const refused = await serverStoreOf(server, {
      newKey: () => BATCH,
    }).startBatch({ ...base, peerGroupStyle: 'a'.repeat(pad) });
    expect(refused).toEqual({ kind: 'too_long' });
    expect(server.count('POST /runs')).toBe(0);
  });

  it('둘째 거절 → 만든 것만 started, 못 만든 파트는 failed', async () => {
    const server = ready();
    server.override['POST /runs'] = [
      () => ok201(20),
      () => refusal(400, 'INVALID_OPTIONS'),
    ];
    const result = await serverStoreOf(server, { newKey: keys() }).startBatch(
      input(),
    );
    expect(result).toMatchObject({
      kind: 'started',
      runs: [{ part: 'ceo', runId: '20' }],
      failed: ['story'],
    });
  });

  it('모두 거절 → 거절, 모두 끊김 → unreachable', async () => {
    const refused = ready();
    refused.override['POST /runs'] = () => refusal(400, 'INVALID_OPTIONS');
    expect(
      await kindOf(
        serverStoreOf(refused, { newKey: keys() }).startBatch(input()),
      ),
    ).toBe('rejected');
    const lost = ready();
    lost.override['POST /runs'] = unreachable;
    expect(
      await kindOf(serverStoreOf(lost, { newKey: keys() }).startBatch(input())),
    ).toBe('unreachable');
  });

  it('꼴 밖 문서 id → 요청 0·not_found', async () => {
    const server = ready();
    expect(
      await kindOf(
        serverStoreOf(server).startBatch(input({ documentId: 'doc-12' })),
      ),
    ).toBe('not_found');
    expect(server.calls).toEqual([]);
  });
});

const ok201 = (id: number) =>
  new Response(JSON.stringify({ id, status: 'queued' }), {
    status: 201,
    headers: { 'Content-Type': 'application/json' },
  });

describe('readGlossary · glossaryTemplate (§3-1 3)', () => {
  it('ok: 짝·수, 본문은 파일 바이트 그대로·Content-Type 은 xlsx', async () => {
    const server = fakeTranslationServer();
    const bytes = new Uint8Array([80, 75, 3, 4, 1, 2, 3, 4, 5]);
    const read = await serverStoreOf(server).readGlossary(
      new File([bytes], 'glossary.xlsx'),
    );
    expect(read).toEqual({
      ok: true,
      pairs: FAKE_PAIRS.map((pair) => ({ ...pair })),
      rowCount: 2,
    });
    const call = server.calls[0]!;
    expect(`${call.method} ${call.path}`).toBe(
      'POST /translation/glossary/read',
    );
    expect(call.octets).toBe(bytes.length);
    expect(call.headers.get('Content-Type')).toBe(
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    );
  });

  it.each([
    'too_large',
    'not_xlsx',
    'unsafe_xlsx',
    'bad_header',
    'empty_cell',
    'not_text',
    'too_long',
    'duplicate_ko',
    'too_many_rows',
    'no_rows',
  ])('거절 %s → {ok:false, kind, row}(서버 글 버림)', async (kind) => {
    const server = fakeTranslationServer({
      glossaryAnswer: { ok: false, kind, row: 12, message: '지어낸 서버 글' },
    });
    const read = await serverStoreOf(server).readGlossary(
      new File(['x'], 'g.xlsx'),
    );
    expect(read).toEqual({ ok: false, kind, row: 12 });
  });

  it('모르는 kind → 꼴 틀림 거절', async () => {
    const server = fakeTranslationServer({
      glossaryAnswer: { ok: false, kind: 'zzz', row: null, message: 'x' },
    });
    expect(
      await kindOf(
        serverStoreOf(server).readGlossary(new File(['x'], 'g.xlsx')),
      ),
    ).toBe('rejected');
  });

  it('양식: blob·Content-Disposition 이름', async () => {
    const server = fakeTranslationServer();
    const file = await serverStoreOf(server).glossaryTemplate();
    expect(file.fileName).toBe('translation-glossary-template.xlsx');
    expect(file.blob.size).toBe(6);
  });
});

describe('archive (§3-1 4)', () => {
  const withDone = (
    extra: Parameters<typeof fakeTranslationServer>[0] = {},
  ) => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH))],
      ...extra,
    });
    server.advance(30, { status: 'done' });
    return server;
  };

  it.each([
    ['0', 0],
    ['2', 2],
  ])('200 + 머리 %s → file·missing %d', async (header, missing) => {
    const server = withDone({ archiveMissing: header });
    const got = await serverStoreOf(server).archive('12', BATCH);
    expect(got).toMatchObject({
      kind: 'file',
      fileName: `translation-12-${BATCH.slice(0, 8)}.zip`,
      missing,
    });
  });

  it('409 ARCHIVE_TOO_LARGE → too_large · 409 NO_FINISHED_PARTS → nothing', async () => {
    const big = withDone({ archiveTooLarge: true });
    expect(await serverStoreOf(big).archive('12', BATCH)).toEqual({
      kind: 'too_large',
    });
    const none = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH))],
    });
    expect(await serverStoreOf(none).archive('12', BATCH)).toEqual({
      kind: 'nothing',
    });
  });

  it.each([[null], ['abc'], ['-1'], ['01']])(
    '머리 %s(없음·수 아님) → 거절',
    async (header) => {
      const server = withDone({ archiveMissing: header });
      expect(await kindOf(serverStoreOf(server).archive('12', BATCH))).toBe(
        'rejected',
      );
    },
  );

  it('404 → not_found · 꼴 밖 열쇠 → 요청 0·not_found', async () => {
    const server = withDone();
    expect(
      await kindOf(
        serverStoreOf(server).archive(
          '12',
          'aaaaaaaa-0000-4000-8000-000000000000',
        ),
      ),
    ).toBe('not_found');
    const before = server.calls.length;
    expect(await kindOf(serverStoreOf(server).archive('12', 'BAD'))).toBe(
      'not_found',
    );
    expect(server.calls.length).toBe(before);
  });
});

describe('getBatch · listBatches · getResult · runFile (§3-1 5)', () => {
  const seeded = () => {
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12),
        fakeDocument(13, { uploadedBy: { id: 8, name: '담당자 나' } }),
      ],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
        fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH), {
          status: 'processing',
          steps: fakeSteps(1, { status: 'running', done: 2, total: 6 }),
        }),
        fakeRun(32, 13, fakeOptions('general', 1, 2, null)),
      ],
    });
    server.advance(30, { status: 'done' });
    return server;
  };

  it('목록 쿼리: limit 20·offset, state 는 있을 때만, mine 은 참일 때만', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    await store.listBatches({ mine: false, offset: 0 });
    await store.listBatches({ state: 'active', mine: true, offset: 20 });
    const [first, second] = server.calls.map((c) => c.query);
    expect(Object.fromEntries(first!)).toEqual({ limit: '20', offset: '0' });
    expect(Object.fromEntries(second!)).toEqual({
      state: 'active',
      mine: 'true',
      limit: '20',
      offset: '20',
    });
  });

  it('목록: 묶음 둘(run-<id> 묶음 포함), 끝나지 않은 파트의 digest 는 null 그대로', async () => {
    const page = await serverStoreOf(seeded()).listBatches({
      mine: false,
      offset: 0,
    });
    expect(page.results.map((b) => b.batchKey)).toEqual(['run-32', BATCH]);
    expect(page.companyName).toBe('지어낸 회사'); // 가짜 서버 기본(밴드 TRC1)
    const batch = page.results[1]!;
    expect(batch.state).toBe('active');
    expect(batch.parts[1]!.latest.digest).toBeNull();
    expect(batch.parts[0]!.latest.digest?.outcome).toBe('done');
  });

  it('묶음 하나: 경로·꼴, 꼴 밖 열쇠·문서 id 는 요청 0', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const batch = await store.getBatch('12', BATCH);
    expect(server.calls[0]!.path).toBe(
      `/translation/documents/12/batches/${BATCH}`,
    );
    expect(batch.truncated).toBe(false);
    expect(batch.parts.map((p) => p.part)).toEqual(['ceo_message', 'story']);
    for (const [doc, key] of [
      ['12', 'run-0'],
      ['12', BATCH.toUpperCase()],
      ['x', BATCH],
    ] as const)
      expect(await kindOf(store.getBatch(doc, key))).toBe('not_found');
    expect(server.calls).toHaveLength(1);
  });

  it('거울 거절: 안쪽 모르는 키 → 거절, 맨 위 모르는 키 → 버리고 통과', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const { file, ...rest } = await store.getBatch('12', BATCH);
    // 서버 꼴로 되돌림(거울은 document → file 로 옮겨 싣는다).
    const good = { ...rest, document: file };
    server.override[`GET /translation/documents/12/batches/${BATCH}`] = [
      () =>
        new Response(JSON.stringify({ ...good, extraTop: 1 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      () =>
        new Response(
          JSON.stringify({
            ...good,
            document: { ...good.document, extraInner: 1 },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    ];
    expect('extraTop' in (await store.getBatch('12', BATCH))).toBe(false);
    expect(await kindOf(store.getBatch('12', BATCH))).toBe('rejected');
  });

  it('결과: done 은 화면 꼴, 409 RUN_NOT_DONE 은 not_done, 404 는 not_found', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const result = await store.getResult('30');
    expect(result.status).toBe('done');
    if (result.status === 'done') {
      expect(result.part).toBe('ceo_message');
      expect(result.pageNumbers).toEqual([1, 2, 3]);
      expect(result.variants[0]!.pages[0]!.review.issues[0]!.issueType).toBe(
        'UNNATURAL',
      );
    }
    expect(await kindOf(store.getResult('31'))).toBe('not_done');
    expect(await kindOf(store.getResult('99'))).toBe('not_found');
  });

  it('결과 거절 갈래: rejection 꼴만(서버 message 없음)', async () => {
    const server = seeded();
    server.advance(31, {
      status: 'done',
      outcome: 'rejected',
      rejectionKind: 'too_large',
    });
    const result = await serverStoreOf(server).getResult('31');
    expect(result).toEqual({
      status: 'rejected',
      part: 'story',
      rejection: { kind: 'too_large', pageCount: null, limit: null },
      warnings: [],
    });
  });

  it('실행 파일: 이름 그대로·blob', async () => {
    const server = seeded();
    const file = await serverStoreOf(server).runFile(
      '30',
      'translation-autofix-single.docx',
    );
    expect(file.fileName).toBe('translation-autofix-single.docx');
    expect(server.calls[0]!.path).toBe(
      '/runs/30/files/translation-autofix-single.docx',
    );
  });
});

// [밴드 TRW1b §3-1 1~3] [이 파트만 다시](결정 sid:MARC-ENT-393·405) · 끊김 한 번 다시 보냄.
describe('retryPart (TRW1b §3-1 1·2)', () => {
  const ready = () => fakeTranslationServer({ documents: [fakeDocument(12)] });
  const retryCalls = (server: ReturnType<typeof ready>) =>
    server.calls.filter(
      (c) => c.path === '/runs' || c.path.startsWith('/runs/'),
    );

  it('GET /runs/{id} 한 번 → POST /runs 한 번: options 는 받은 그대로(바이트 같음) · launchKey·Idempotency-Key 만 새로', async () => {
    const server = ready();
    const store = serverStoreOf(server);
    const started = await store.startBatch(input());
    if (started.kind !== 'started') throw new Error('not started');
    const first = server.runBodies()[1] as unknown as RunBody;
    const firstKey = server.calls
      .filter((c) => c.method === 'POST' && c.path === '/runs')[1]!
      .headers.get('Idempotency-Key');
    server.calls.length = 0;
    const again = await store.retryPart({
      documentId: '12',
      batchKey: started.batchKey,
      part: 'story',
      runId: '21',
    });
    expect(again).toEqual({ runId: '22' });
    expect(retryCalls(server).map((c) => `${c.method} ${c.path}`)).toEqual([
      'GET /runs/21',
      'POST /runs',
    ]);
    const body = server.runBodies()[0] as unknown as RunBody;
    expect(JSON.stringify(body.options)).toBe(
      JSON.stringify(server.runs.get(21)!.options),
    );
    expect(body.options.batchId).toBe(started.batchKey);
    expect(body.launchKey).not.toBe(first.launchKey);
    expect(body.launchKey).not.toBe(started.batchKey);
    expect(Object.keys(body).sort()).toEqual(
      ['documentId', 'launchKey', 'module', 'options'].sort(),
    );
    expect(body.options).not.toHaveProperty('retry');
    expect(body.options).not.toHaveProperty('autofix');
    expect(body.options).not.toHaveProperty('companyId');
    const key1 = server.calls
      .find((c) => c.method === 'POST')!
      .headers.get('Idempotency-Key');
    expect(key1).not.toBe(firstKey);
    // 두 번째 다시 하기(낡은 화면 — 같은 runId 21 에서 또): 열쇠가 또 새로(앞 실행을 받지 않음 — 새 실행 23).
    server.calls.length = 0;
    expect(
      await store.retryPart({
        documentId: '12',
        batchKey: started.batchKey,
        part: 'story',
        runId: '21',
      }),
    ).toEqual({ runId: '23' });
    const key2 = server.calls
      .find((c) => c.method === 'POST')!
      .headers.get('Idempotency-Key');
    expect(key2).not.toBe(key1);
    const body2 = server.runBodies()[0] as unknown as RunBody;
    expect(body2.launchKey).not.toBe(body.launchKey);
  });

  const seeded = (options: Record<string, unknown>, documentId = 12) =>
    fakeTranslationServer({
      documents: [fakeDocument(12), fakeDocument(13)],
      runs: [fakeRun(30, documentId, options, { status: 'failed' })],
    });
  const tryIt = (
    server: ReturnType<typeof seeded>,
    extra: Partial<{
      batchKey: string;
      part: 'ceo' | 'story' | 'general';
    }> = {},
  ) =>
    kindOf(
      serverStoreOf(server).retryPart({
        documentId: '12',
        batchKey: BATCH,
        part: 'story',
        runId: '30',
        ...extra,
      }),
    );

  it.each([
    ['batchId 다름', fakeOptions('story', 4, 9, KEYS[4]!), 12],
    ['part 다름', fakeOptions('general', 4, 9, BATCH), 12],
    ['documentId 다름', fakeOptions('story', 4, 9, BATCH), 13],
    ['batchId 없음', fakeOptions('story', 4, 9, null), 12],
  ] as const)('어긋남(%s) → rejected · POST 0', async (_, options, doc) => {
    const server = seeded({ ...options }, doc);
    expect(await tryIt(server)).toBe('rejected');
    expect(server.count('GET /runs/30')).toBe(1);
    expect(server.count('POST /runs')).toBe(0);
  });

  it('module 다름 → rejected · POST 0', async () => {
    const server = seeded(fakeOptions('story', 4, 9, BATCH));
    server.override['GET /runs/30'] = () =>
      new Response(
        JSON.stringify({
          id: 30,
          module: 'greenwash',
          documentId: 12,
          options: fakeOptions('story', 4, 9, BATCH),
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    expect(await tryIt(server)).toBe('rejected');
    expect(server.count('POST /runs')).toBe(0);
  });

  it('`run-<id>` 열쇠 → 요청 0·rejected · GET 404 → not_found · 꼴 밖 runId → 요청 0·not_found', async () => {
    const server = seeded(fakeOptions('story', 4, 9, null));
    expect(await tryIt(server, { batchKey: 'run-30' })).toBe('rejected');
    expect(server.calls).toEqual([]);
    const gone = seeded(fakeOptions('story', 4, 9, BATCH));
    gone.runs.delete(30);
    expect(await tryIt(gone)).toBe('not_found');
    expect(gone.count('POST /runs')).toBe(0);
    const bad = seeded(fakeOptions('story', 4, 9, BATCH));
    expect(
      await kindOf(
        serverStoreOf(bad).retryPart({
          documentId: '12',
          batchKey: BATCH,
          part: 'story',
          runId: 'run-30',
        }),
      ),
    ).toBe('not_found');
    expect(bad.calls).toEqual([]);
  });

  it('POST 거절(400) → rejected, 다시 보내지 않음', async () => {
    const server = seeded(fakeOptions('story', 4, 9, BATCH));
    server.override['POST /runs'] = () => refusal(400, 'INVALID_OPTIONS');
    expect(await tryIt(server)).toBe('rejected');
    expect(server.count('POST /runs')).toBe(1);
  });
});

describe('POST /runs 끊김 한 번 다시 보냄 (TRW1b §3-1 3)', () => {
  const ready = () => fakeTranslationServer({ documents: [fakeDocument(12)] });
  const posts = (server: ReturnType<typeof ready>) =>
    server.calls.filter((c) => c.method === 'POST' && c.path === '/runs');

  it('첫 POST 끊김 → 둘째는 같은 Idempotency-Key·같은 본문, 둘 다 started', async () => {
    const server = ready();
    server.override['POST /runs'] = [unreachable];
    const result = await serverStoreOf(server, { newKey: keys() }).startBatch(
      input(),
    );
    const sent = posts(server);
    expect(sent).toHaveLength(3);
    expect(sent[1]!.headers.get('Idempotency-Key')).toBe(
      sent[0]!.headers.get('Idempotency-Key'),
    );
    expect(JSON.stringify(sent[1]!.body)).toBe(JSON.stringify(sent[0]!.body));
    expect(sent[2]!.headers.get('Idempotency-Key')).not.toBe(
      sent[0]!.headers.get('Idempotency-Key'),
    );
    expect(result).toMatchObject({
      kind: 'started',
      runs: [
        { part: 'ceo', runId: '20' },
        { part: 'story', runId: '21' },
      ],
      failed: [],
    });
  });

  it('서버가 만들고 답만 잃은 꼴 → 다시 보냄이 앞 실행을 받음(실행 하나)', async () => {
    const server = ready();
    server.loseAnswer('POST /runs');
    const result = await serverStoreOf(server).startBatch(
      input({ parts: [{ part: 'story', range: { from: 4, to: 9 } }] }),
    );
    expect(posts(server)).toHaveLength(2);
    expect(server.runs.size).toBe(1);
    expect(result).toMatchObject({
      kind: 'started',
      runs: [{ part: 'story', runId: '20' }],
      failed: [],
    });
  });

  it('[이 파트만 다시]도 같은 도우미: 답을 잃으면 같은 열쇠로 한 번 더, 실행 하나', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 9, BATCH), {
          status: 'failed',
        }),
      ],
      nextRunId: 40,
    });
    server.loseAnswer('POST /runs');
    expect(
      await serverStoreOf(server).retryPart({
        documentId: '12',
        batchKey: BATCH,
        part: 'story',
        runId: '30',
      }),
    ).toEqual({ runId: '40' });
    const sent = posts(server);
    expect(sent).toHaveLength(2);
    expect(sent[1]!.headers.get('Idempotency-Key')).toBe(
      sent[0]!.headers.get('Idempotency-Key'),
    );
    expect(server.runs.size).toBe(2);
  });

  it('둘 다 끊김 → unreachable(POST 2번) · 400 거절은 다시 보내지 않음(POST 1번)', async () => {
    const one = {
      parts: [{ part: 'story' as const, range: { from: 4, to: 9 } }],
    };
    const lost = ready();
    lost.override['POST /runs'] = [unreachable, unreachable];
    expect(await kindOf(serverStoreOf(lost).startBatch(input(one)))).toBe(
      'unreachable',
    );
    expect(posts(lost)).toHaveLength(2);
    const refused = ready();
    refused.override['POST /runs'] = () => refusal(400, 'INVALID_OPTIONS');
    expect(await kindOf(serverStoreOf(refused).startBatch(input(one)))).toBe(
      'rejected',
    );
    expect(posts(refused)).toHaveLength(1);
  });
});

// 밴드 TRW6 ① S1 — PDF 저장소(TRS3 §1-1·§1-2 꼴의 가짜 서버). 워드 본문은 위 시험들이 BASE 그대로 지킨다.
describe('PDF 저장소 (TRW6 S1)', () => {
  const PDF_BYTES = new Uint8Array([37, 80, 68, 70, 45, 49, 46, 52]);

  it('uploadPdf: 세 요청에서 멈춘다(pages 0) · confirm 의 pageCount 정수·hasText', async () => {
    const server = fakeTranslationServer({
      serverPageCount: 64,
      serverHasText: true,
    });
    const doc = await serverStoreOf(server).uploadPdf(
      new File([PDF_BYTES], 'made_up_report.pdf'),
    );
    expect(server.calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      'POST /documents',
      'POST /documents/12/confirm',
    ]);
    expect(doc).toMatchObject({
      documentId: '12',
      fileName: 'made_up_report.pdf',
      pageCount: 64,
      hasText: true,
    });
  });

  it('uploadPdf: pageCount null·hasText false 도 그대로(pages 로 메우지 않음)', async () => {
    const server = fakeTranslationServer({
      serverPageCount: null,
      serverHasText: false,
      translationPageCount: 9,
    });
    const doc = await serverStoreOf(server).uploadPdf(
      new File([PDF_BYTES], 'scan.pdf'),
    );
    expect(doc.pageCount).toBeNull();
    expect(doc.hasText).toBe(false);
    expect(server.count('GET /translation/documents/12/pages')).toBe(0);
  });

  it('getDocument: GET /documents/{id} 의 쪽 수·hasText · 없으면 not_found', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12, { pageCount: 3, hasText: true })],
    });
    const store = serverStoreOf(server);
    expect(await store.getDocument('12')).toEqual({
      documentId: '12',
      fileName: 'sample_extract_12.txt',
      pageCount: 3,
      hasText: true,
    });
    expect(await kindOf(store.getDocument('99'))).toBe('not_found');
    expect(await kindOf(store.getDocument('x'))).toBe('not_found');
  });

  it('getRunInfo: flowId·resultShapes(layout 있음/없음)·documentId·파트', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH), {
          flowId: 'translation.pdf@158',
        }),
        fakeRun(31, 12, fakeOptions('general', 4, 5, BATCH)),
      ],
    });
    server.advance(30, { status: 'done', layout: fakeLayout(1) });
    server.advance(31, { status: 'done' });
    const store = serverStoreOf(server);
    const pdf = await store.getRunInfo('30');
    expect(pdf).toEqual({
      runId: '30',
      flowId: 'translation.pdf@158',
      resultShapes: [
        'translation.result@1',
        'translation.digest@1',
        'translation.layout@1',
      ],
      documentId: '12',
      part: 'story',
    });
    const word = await store.getRunInfo('31');
    expect(word.flowId).toBe('translation.colab@158');
    expect(word.resultShapes).not.toContain('translation.layout@1');
    expect(word.part).toBe('general');
    expect(await kindOf(store.getRunInfo('99'))).toBe('not_found');
  });

  it('getRunInfo: 꼴이 틀리면(resultShapes 없음) rejected', async () => {
    const server = fakeTranslationServer();
    server.override['GET /runs/5'] = () =>
      json(200, {
        id: 5,
        module: 'translation',
        flowId: 'translation.pdf@158',
        documentId: 12,
        options: {},
      });
    expect(await kindOf(serverStoreOf(server).getRunInfo('5'))).toBe(
      'rejected',
    );
  });

  it('startBatch: flowId 를 주면 POST /runs 본문에 flowId(옵션 안이 아니라 맨 위)', async () => {
    const server = fakeTranslationServer({ documents: [fakeDocument(12)] });
    await serverStoreOf(server, { newKey: keys() }).startBatch(
      input({ flowId: 'translation.pdf@158' }),
    );
    const bodies = server.runBodies();
    expect(bodies).toHaveLength(2);
    for (const body of bodies) {
      expect(body.flowId).toBe('translation.pdf@158');
      expect(Object.keys(body).sort()).toEqual(
        ['documentId', 'flowId', 'launchKey', 'module', 'options'].sort(),
      );
      expect('flowId' in (body.options as object)).toBe(false);
    }
    expect([...server.runs.values()].map((run) => run.flowId)).toEqual([
      'translation.pdf@158',
      'translation.pdf@158',
    ]);
  });

  it('startBatch: flowId 가 없으면 본문에 flowId 키가 없다(워드 BASE)', async () => {
    const server = fakeTranslationServer({ documents: [fakeDocument(12)] });
    await serverStoreOf(server, { newKey: keys() }).startBatch(input());
    for (const body of server.runBodies()) expect('flowId' in body).toBe(false);
  });

  it('getLayout: 200 거울 · 404 not_found · 409 not_done · 끊김 unreachable 아님(rejected) · 꼴 틀림 rejected', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH)),
        fakeRun(31, 12, fakeOptions('story', 1, 3, BATCH)),
        fakeRun(32, 12, fakeOptions('story', 1, 3, BATCH)),
      ],
    });
    server.advance(30, { status: 'done', layout: fakeLayout(1) });
    server.advance(31, { status: 'done' });
    server.advance(32, { status: 'processing' });
    const store = serverStoreOf(server);
    const layout = await store.getLayout('30');
    expect(layout.status).toBe('done');
    expect(layout.units).toHaveLength(3);
    expect(await kindOf(store.getLayout('31'))).toBe('not_found');
    expect(await kindOf(store.getLayout('99'))).toBe('not_found');
    expect(await kindOf(store.getLayout('32'))).toBe('not_done');
    server.override['GET /translation/runs/30/layout'] = unreachable;
    expect(await kindOf(store.getLayout('30'))).toBe('rejected');
    server.override['GET /translation/runs/30/layout'] = () =>
      json(200, { ...fakeLayout(1), pages: 'x' });
    expect(await kindOf(store.getLayout('30'))).toBe('rejected');
  });

  it('openRunPdf: ready(File) · 두 번 불러도 요청 하나 · 404·409 missing · 500 failed 는 다시 보낸다', async () => {
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, { fileName: 'made_up.pdf', pdf: PDF_BYTES }),
        fakeDocument(13),
        fakeDocument(14, { pdf: PDF_BYTES }),
      ],
    });
    const store = serverStoreOf(server);
    const first = await store.openRunPdf('12');
    const second = await store.openRunPdf('12');
    expect(first.kind).toBe('ready');
    expect(second).toBe(first);
    if (first.kind === 'ready') {
      expect(first.file.name).toBe('made_up.pdf');
      expect(first.file.type).toBe('application/pdf');
      expect(new Uint8Array(await first.file.arrayBuffer())).toEqual(PDF_BYTES);
    }
    expect(server.count('GET /documents/12/file')).toBe(1);
    expect(await store.openRunPdf('13')).toEqual({ kind: 'missing' });
    expect(await store.openRunPdf('99')).toEqual({ kind: 'missing' });
    server.override['GET /documents/14/file'] = [
      () => refusal(500, 'INTERNAL'),
    ];
    expect(await store.openRunPdf('14')).toEqual({ kind: 'failed' });
    expect((await store.openRunPdf('14')).kind).toBe('ready');
    expect(server.count('GET /documents/14/file')).toBe(2);
  });
});

// 밴드 TRW6 ② 검증 권고 R3·R4: retryPart 는 GET /runs 의 바탕 칸만 본다 — flowId·resultShapes 가 없는 답(옛 서버·e2e 모의 꼴)도
// POST /runs 한 번, GET 자체가 거절이면 send 의 글 「run failed」(BASE 그대로 — 꼴 어긋남 글로 바꾸지 않는다).
describe('retryPart · GET /runs 읽기(TRW6 R3·R4)', () => {
  const seededRun = () =>
    fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 9, BATCH), {
          status: 'failed',
        }),
      ],
    });
  const retry = (server: ReturnType<typeof seededRun>) =>
    serverStoreOf(server).retryPart({
      documentId: '12',
      batchKey: BATCH,
      part: 'story',
      runId: '30',
    });

  it('R4: GET /runs 답에 flowId·resultShapes·steps 가 없어도 POST /runs 한 번', async () => {
    const server = seededRun();
    server.override['GET /runs/30'] = () =>
      json(200, {
        id: 30,
        module: 'translation',
        documentId: 12,
        status: 'failed',
        options: fakeOptions('story', 4, 9, BATCH),
      });
    expect(await retry(server)).toEqual({ runId: expect.any(String) });
    expect(server.count('POST /runs')).toBe(1);
  });

  it.each([
    [500, 'INTERNAL_ERROR'],
    [400, 'INVALID_OPTIONS'],
  ] as const)(
    'R3: GET /runs 거절(%i) → rejected, 글은 「run failed」 · POST 0',
    async (status, code) => {
      const server = seededRun();
      server.override['GET /runs/30'] = () => refusal(status, code);
      const error = await retry(server).then(
        () => null,
        (caught: unknown) => caught,
      );
      expect(storeErrorKind(error)).toBe('rejected');
      expect((error as Error).message).toBe('run failed');
      expect(server.count('POST /runs')).toBe(0);
    },
  );

  it('R3: 꼴 어긋남(options 없음)은 「retry: run does not match the batch part」', async () => {
    const server = seededRun();
    server.override['GET /runs/30'] = () =>
      json(200, { id: 30, module: 'translation', documentId: 12 });
    const error = await retry(server).then(
      () => null,
      (caught: unknown) => caught,
    );
    expect((error as Error).message).toBe(
      'retry: run does not match the batch part',
    );
    expect(server.count('POST /runs')).toBe(0);
  });
});

// 밴드 TRW6 ④: TRS3 병합 뒤 잇기 — retryPart 의 flowId(W5·E1) · 가짜 묶음의 두 칸(latest.flowId·inputKind)이 실행 flowId 를 따름.
describe('retryPart · PDF flowId(TRW6 ④ E1)', () => {
  const PDF = 'translation.pdf@158';
  const seeded = (flowId?: string) =>
    fakeTranslationServer({
      documents: [fakeDocument(12, { fileName: 'made_up.pdf' })],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 9, BATCH), {
          status: 'failed',
          launchKey: 'made-up-first-key',
          ...(flowId === undefined ? {} : { flowId }),
        }),
      ],
    });
  const retry = (server: ReturnType<typeof seeded>) =>
    serverStoreOf(server).retryPart({
      documentId: '12',
      batchKey: BATCH,
      part: 'story',
      runId: '30',
    });

  it('E1: PDF 실행이면 POST /runs 본문에 같은 flowId · 옵션 바이트 그대로 · 새 launchKey', async () => {
    const server = seeded(PDF);
    const { runId } = await retry(server);
    const body = server.runBodies()[0] as unknown as RunBody & {
      flowId?: string;
    };
    expect(body.flowId).toBe(PDF);
    expect(Object.keys(body).sort()).toEqual(
      ['documentId', 'flowId', 'launchKey', 'module', 'options'].sort(),
    );
    expect(JSON.stringify(body.options)).toBe(
      JSON.stringify(server.runs.get(30)!.options),
    );
    expect(body.launchKey).not.toBe('made-up-first-key');
    // 새 실행도 PDF 흐름으로 섬(가짜 서버가 본문 flowId 를 저장).
    expect(server.runs.get(Number(runId))!.flowId).toBe(PDF);
  });

  it('E1: 워드 실행(colab)·flowId 칸이 없는 답은 flowId 키 0', async () => {
    const word = seeded();
    await retry(word);
    expect(word.runBodies()[0]).not.toHaveProperty('flowId');
    const bare = seeded(PDF);
    bare.override['GET /runs/30'] = () =>
      json(200, {
        id: 30,
        module: 'translation',
        documentId: 12,
        status: 'failed',
        options: fakeOptions('story', 4, 9, BATCH),
      });
    await retry(bare);
    expect(bare.runBodies()[0]).not.toHaveProperty('flowId');
  });
});

describe('가짜 묶음의 TRS3 두 칸이 실행 flowId 를 따름(TRW6 ④)', () => {
  it('파트 latest.flowId = 그 실행 flowId · inputKind = 가장 새 실행이 PDF 면 pdf', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH)),
        fakeRun(31, 12, fakeOptions('story', 4, 9, BATCH), {
          flowId: 'translation.pdf@158',
        }),
      ],
    });
    const store = serverStoreOf(server);
    const batch = await store.getBatch('12', BATCH);
    expect(batch.inputKind).toBe('pdf');
    expect(batch.parts.map((p) => [p.part, p.latest.flowId])).toEqual([
      ['ceo_message', 'translation.colab@158'],
      ['story', 'translation.pdf@158'],
    ]);
    const word = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [fakeRun(30, 12, fakeOptions('ceo_message', 1, 3, BATCH))],
    });
    expect((await serverStoreOf(word).getBatch('12', BATCH)).inputKind).toBe(
      'word',
    );
  });
});
