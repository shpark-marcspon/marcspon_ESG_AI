// e2e 의 영문번역 흉내 서버(밴드 TRW1a ③ — e2e/greenwash-server.ts 꼴, 테스트 73 알림). 빌드한 웹의 실어댑터가 부르는 경로를 page.route 로 채운다.
// 답의 값은 전부 지어낸 것이다(실재 기업명 0). 포트는 쥐지 않는다 — playwright.config.ts 의 WEB_TEST_PORT 미리보기 서버에 붙는 page.route 뿐이다.
//   - 경로: POST /api/documents · POST /api/documents/{id}/confirm · POST /api/runs · GET /api/translation/batches ·
//     GET /api/translation/documents/{d}/batches/{k}(·/archive) · GET /api/translation/runs/{id}/result · GET /api/runs/{id}/files/{name} ·
//     POST /api/translation/glossary/read · GET /api/translation/glossary/template · GET /api/runs/{id}(options 는 저장한 그대로 — 밴드 TRW1b).
//     서명 올리기는 같은 출처 /fake-upload/<문서 id>.
//   - GET /api/translation/documents/{id}/pages(밴드 TRP6): 올린 바이트의 `^\[PAGE (\d+)\]$` 줄 최댓값(없으면 null), 없는 문서 404.
//   - 새 실행은 queued 로 생기고, 묶음 읽기 한 번마다 한 걸음(queued → processing → done). 끝난 실행은 결과·요약을 짓는다.
//   - [모두 받기]: archiveTooLarge 면 409 ARCHIVE_TOO_LARGE, 아니면 zip 바이트 + X-Archive-Missing.
//   - 한 묶음(batchId)의 첫 회차 실행들은 같은 launchKey 여야 한다 — 어긋나면 400 INVALID_OPTIONS(시험이 같은 값을 단언하기도 한다).
//     이미 그 파트가 있는 묶음에 오는 실행([이 파트만 다시] — 회차 하나 더)은 새 launchKey 다(결정 sid:MARC-ENT-405, 밴드 TRW1b).
//   - failParts(서버 파트 이름)의 첫 회차는 끝날 때 failed(서버 오류)가 된다. 다시 한 회차는 done. 묶음의 파트는 최신 회차 + 앞 회차.
// 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다(route 는 나중 것이 이긴다 — 이 흉내는 /api/** 를 받고 로그인 경로는 session 이 답한다).
import type { Page, Route } from '@playwright/test';

export interface TranslationCall {
  method: string;
  path: string;
  search: string;
  body: unknown;
  authorization: string | null;
  idempotencyKey: string | null;
  size: number;
}

type Json = Record<string, unknown>;

const NOW = '2026-10-19T11:48:00+09:00';
const FINISHED = '2026-10-19T12:05:00+09:00';
/** 지어낸 파일 바이트(「PK」 머리만 — 실제 Word·zip 이 아니다). */
const BYTES = Buffer.from([80, 75, 3, 4, 9, 9]);
const PAIRS = [
  { ko: '지어낸용어', en: 'Made-up Term' },
  { ko: '가상지표', en: 'Virtual Metric' },
];

const answer = (route: Route, status: number, body?: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: body === undefined ? '' : JSON.stringify(body),
  });
const refusal = (route: Route, status: number, code: string) =>
  answer(route, status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

interface Doc {
  id: number;
  fileName: string;
  sizeBytes: number;
  uploaded: boolean;
  /** 올린 바이트에서 센 [PAGE n] 최댓값(밴드 TRP6 — 서버 흉내). */
  pageCount?: number | null;
}
interface Run {
  id: number;
  documentId: number;
  options: Json;
  launchKey: string | null;
  status: 'queued' | 'processing' | 'done' | 'failed';
  /** 끝날 때 failed 가 된다(failParts 의 첫 회차). */
  failAtEnd: boolean;
}

export interface FakeTranslationApiOptions {
  archiveTooLarge?: boolean;
  archiveMissing?: number;
  /** 첫 회차가 서버 오류로 끝나는 파트(서버 이름 — 'general' 등). */
  failParts?: readonly string[];
  /** 목록 답의 companyName(기본 '지어낸 회사' — 밴드 TRC1). */
  companyName?: string;
}

const stepsOf = (status: Run['status']) =>
  ['prepare', 'translate', 'report'].map((step, index) => ({
    step,
    status:
      status === 'done' ? 'done'
      : status === 'failed' ?
        index === 0 ? 'done'
        : index === 1 ? 'failed'
        : 'pending'
      : status === 'queued' ? 'pending'
      : index === 0 ? 'done'
      : index === 1 ? 'running'
      : 'pending',
    done: status === 'processing' && index === 1 ? 1 : null,
    total: status === 'processing' && index === 1 ? 3 : null,
  }));

function pagesOf(run: Run): number[] {
  const pages = run.options.pages as { start: number; end: number };
  const out: number[] = [];
  for (let n = pages.start; n <= pages.end; n++) out.push(n);
  return out;
}

const fileName = (kind: string) => `translation-${kind}-single.docx`;

function digestOf(run: Run): Json {
  const pages = pagesOf(run);
  return {
    schemaVersion: 'translation.digest@1',
    status: 'done',
    rejectionKind: null,
    outcome: 'done',
    pageCount: pages.length,
    failedPages: [],
    variants: [
      {
        label: 'single',
        reviewStatus: 'reviewed',
        reviewStoppedAt: null,
        parseFailedPages: 0,
        issueCount: pages.length,
        issueCounts: { high: 0, medium: 0, low: pages.length },
        glossaryMisses: 0,
        autofixStatus: 'done',
        autofixChangedPages: 1,
        files: {
          bilingual: fileName('bilingual'),
          qa: fileName('qa'),
          autofix: fileName('autofix'),
        },
      },
    ],
    warningCount: 0,
  };
}

function resultOf(run: Run): Json {
  const pages = pagesOf(run);
  return {
    schemaVersion: 'translation.result@1',
    status: 'done',
    rejection: null,
    settings: {
      part: run.options.part,
      variants: ['single'],
      routes: { translate: 'light-anthropic', review: 'light-anthropic' },
      promptIds: ['translation/section@2'],
      engine: 'colab_158',
      constants: {
        editorialQaMinScore: 96,
        tableBatchSize: 24,
        polishMinChars: 120,
        polishMaxChars: 6000,
        koreanRepairRounds: 2,
        autofixKoreanRepairRounds: 1,
      },
      retry: null,
    },
    document: {
      pageNumbers: pages,
      duplicatePages: {},
      sourceSha256: '0'.repeat(64),
    },
    variants: [
      {
        label: 'single',
        translatedText: '[PAGE 1]\nMade-up text',
        bilingualText: '[PAGE 1]\nMade-up text',
        fragments: pages.map((pageNum) => ({
          pageNum,
          status: 'translated',
          error: null,
          editorialQa: null,
          remainingKorean: [],
        })),
        pages: pages.map((pageNum) => ({
          pageNum,
          translated: `[PAGE ${pageNum}]\nMade-up text`,
          bilingual: `[PAGE ${pageNum}]\nMade-up text`,
          review: {
            status: 'reviewed',
            issues: [
              {
                issueType: 'UNNATURAL',
                severity: 'LOW',
                originalSpan: 'Made-up text',
                suggestion: 'Invented text',
                reason: '지어낸 까닭',
                source: 'model',
              },
            ],
            counts: { high: 0, medium: 0, low: 1 },
            message: null,
          },
        })),
        glossaryCheck: [],
        autofix: {
          status: 'done',
          pages: [],
          translatedText: '[PAGE 1]\nFixed text',
          bilingualText: '[PAGE 1]\nFixed text',
          stop: null,
          notRunReason: null,
        },
      },
    ],
    warnings: [],
  };
}

export async function fakeTranslationApi(
  page: Page,
  {
    archiveTooLarge = false,
    archiveMissing = 0,
    failParts = [],
    companyName = '지어낸 회사',
  }: FakeTranslationApiOptions = {},
) {
  const calls: TranslationCall[] = [];
  const docs = new Map<number, Doc>();
  const runs = new Map<number, Run>();
  let docSeq = 12;
  let runSeq = 20;

  const keyOf = (run: Run) =>
    typeof run.options.batchId === 'string' ?
      run.options.batchId
    : `run-${run.id}`;
  const order = ['ceo_message', 'story', 'general'];
  const batchOf = (documentId: number, key: string) => {
    const list = [...runs.values()]
      .filter((run) => run.documentId === documentId && keyOf(run) === key)
      .sort(
        (a, b) =>
          order.indexOf(String(a.options.part)) -
          order.indexOf(String(b.options.part)),
      );
    if (list.length === 0) return null;
    // 파트마다 최신 회차.
    const latest = order.flatMap((part) => {
      const newest = list
        .filter((run) => run.options.part === part)
        .sort((a, b) => b.id - a.id)[0];
      return newest === undefined ? [] : [newest];
    });
    const doc = docs.get(documentId)!;
    const glossary = run0Glossary(list[0]!);
    return {
      batchKey: key,
      inputKind: 'word',
      document: {
        id: doc.id,
        fileName: doc.fileName,
        uploadedAt: NOW,
        uploadedBy: { userId: 1, name: '지어낸-user01' },
      },
      createdBy: { userId: 1, name: '지어낸-user01' },
      parts: order.flatMap((part) => {
        // 그 파트의 회차들(새것부터) — 최신 하나 + 앞 회차.
        const rounds = list
          .filter((run) => run.options.part === part)
          .sort((a, b) => b.id - a.id);
        if (rounds.length === 0) return [];
        const [run, ...earlier] = rounds as [Run, ...Run[]];
        const pages = run.options.pages as { start: number; end: number };
        return [
          {
            part: run.options.part,
            latest: {
              runId: run.id,
              flowId: 'translation.colab@158',
              status: run.status,
              pages: { start: pages.start, end: pages.end },
              style: run.options.style,
              glossaryCounts: glossary,
              createdAt: NOW,
              startedAt: run.status === 'queued' ? null : NOW,
              finishedAt:
                run.status === 'done' || run.status === 'failed' ?
                  FINISHED
                : null,
              failedStep: run.status === 'failed' ? 'translate' : null,
              errorCode: run.status === 'failed' ? 'step_error' : null,
              steps: stepsOf(run.status),
              digest: run.status === 'done' ? digestOf(run) : null,
            },
            earlier: earlier.map((old) => ({
              runId: old.id,
              status: old.status,
              createdAt: NOW,
              finishedAt: FINISHED,
              outcome: null,
            })),
            round: rounds.length,
          },
        ];
      }),
      state:
        (
          latest.some(
            (run) => run.status === 'queued' || run.status === 'processing',
          )
        ) ?
          'active'
        : latest.some((run) => run.status === 'failed') ? 'failed'
        : 'done',
      doneParts: latest.filter((run) => run.status === 'done').length,
      partCount: latest.length,
    };
  };
  const run0Glossary = (run: Run) => {
    const glossary = (run.options.glossary ?? {}) as {
      base?: unknown[];
      final?: unknown[];
    };
    return {
      base: glossary.base?.length ?? 0,
      final: glossary.final?.length ?? 0,
    };
  };
  /** 묶음 읽기 한 번마다 한 걸음. */
  const step = (documentId: number, key: string) => {
    for (const run of runs.values())
      if (run.documentId === documentId && keyOf(run) === key)
        run.status =
          run.status === 'queued' ? 'processing'
          : run.status === 'processing' ?
            run.failAtEnd ?
              'failed'
            : 'done'
          : run.status;
  };

  await page.route('**/fake-upload/*', async (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').pop());
    const doc = docs.get(id);
    if (doc) {
      doc.uploaded = true;
      const text = route.request().postDataBuffer()?.toString('utf8') ?? '';
      const pages = [...text.matchAll(/^\[PAGE (\d+)\]$/gm)]
        .map((m) => Number(m[1]))
        .filter((n) => n >= 1);
      doc.pageCount = pages.length > 0 ? Math.max(...pages) : null;
    }
    calls.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      search: '',
      body: undefined,
      authorization: route.request().headers()['authorization'] ?? null,
      idempotencyKey: null,
      size: route.request().postDataBuffer()?.length ?? 0,
    });
    return route.fulfill({ status: 200, body: '' });
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
    const method = request.method();
    let body: unknown;
    try {
      body = request.postData() ? request.postDataJSON() : undefined;
    } catch {
      body = undefined;
    }
    calls.push({
      method,
      path,
      search: url.search,
      body,
      authorization: request.headers()['authorization'] ?? null,
      idempotencyKey: request.headers()['idempotency-key'] ?? null,
      size: request.postDataBuffer()?.length ?? 0,
    });
    const key = `${method} ${path}`;
    if (key === 'POST /documents') {
      const { fileName: name, sizeBytes } = body as {
        fileName: string;
        sizeBytes: number;
      };
      const doc: Doc = {
        id: docSeq++,
        fileName: name,
        sizeBytes,
        uploaded: false,
      };
      docs.set(doc.id, doc);
      return answer(route, 201, {
        document: {
          id: doc.id,
          fileName: name,
          sizeBytes,
          status: 'awaiting_upload',
          pageCount: null,
          uploadedAt: null,
        },
        upload: {
          url: `${url.origin}/fake-upload/${doc.id}`,
          method: 'PUT',
          expiresInSeconds: 900,
        },
      });
    }
    const pagesOf = /^\/translation\/documents\/(\d+)\/pages$/.exec(path);
    if (pagesOf && method === 'GET') {
      const doc = docs.get(Number(pagesOf[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      return answer(route, 200, {
        documentId: doc.id,
        pageCount: doc.pageCount ?? null,
      });
    }
    let match = /^\/documents\/(\d+)\/confirm$/.exec(path);
    if (match && method === 'POST') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      if (!doc.uploaded) return refusal(route, 409, 'NOT_UPLOADED');
      return answer(route, 200, {
        document: {
          id: doc.id,
          fileName: doc.fileName,
          sizeBytes: doc.sizeBytes,
          status: 'uploaded',
          // docx·txt 는 서버가 쪽을 재지 않는다(시연 길).
          pageCount: null,
          uploadedAt: NOW,
        },
      });
    }
    if (key === 'POST /runs') {
      const b = body as Json;
      const options = b.options as Json;
      const sameBatch = [...runs.values()].filter(
        (run) => run.options.batchId === options.batchId,
      );
      const again = sameBatch.some((run) => run.options.part === options.part);
      if (!again && sameBatch.some((run) => run.launchKey !== b.launchKey))
        return refusal(route, 400, 'INVALID_OPTIONS');
      const run: Run = {
        id: runSeq++,
        documentId: b.documentId as number,
        options,
        launchKey: (b.launchKey as string | undefined) ?? null,
        status: 'queued',
        failAtEnd: !again && failParts.includes(String(options.part)),
      };
      runs.set(run.id, run);
      return answer(route, 201, { id: run.id, status: 'queued' });
    }
    if (key === 'GET /translation/batches') {
      const groups = new Map<string, { documentId: number; key: string }>();
      for (const run of runs.values())
        groups.set(`${run.documentId}/${keyOf(run)}`, {
          documentId: run.documentId,
          key: keyOf(run),
        });
      const results = [...groups.values()].map((g) =>
        batchOf(g.documentId, g.key),
      );
      return answer(route, 200, {
        companyName,
        count: results.length,
        isNext: false,
        truncated: false,
        results,
      });
    }
    match =
      /^\/translation\/documents\/(\d+)\/batches\/([^/]+)(\/archive)?$/.exec(
        path,
      );
    if (match && method === 'GET') {
      const documentId = Number(match[1]);
      const batchKey = decodeURIComponent(match[2]!);
      if (match[3] === undefined) {
        const found = batchOf(documentId, batchKey);
        if (!found) return refusal(route, 404, 'NOT_FOUND');
        step(documentId, batchKey);
        return answer(route, 200, { ...found, truncated: false });
      }
      if (!batchOf(documentId, batchKey))
        return refusal(route, 404, 'NOT_FOUND');
      if (archiveTooLarge) return refusal(route, 409, 'ARCHIVE_TOO_LARGE');
      return route.fulfill({
        status: 200,
        contentType: 'application/zip',
        headers: {
          'Content-Disposition': `attachment; filename="translation-${documentId}-${batchKey.slice(0, 8)}.zip"`,
          'X-Archive-Missing': String(archiveMissing),
        },
        body: BYTES,
      });
    }
    match = /^\/translation\/runs\/(\d+)\/result$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(route, 409, 'RUN_NOT_DONE');
      return answer(route, 200, resultOf(run));
    }
    match = /^\/runs\/(\d+)$/.exec(path);
    if (method === 'GET' && match) {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      return answer(route, 200, {
        id: run.id,
        module: 'translation',
        flowId: 'translation.colab@158',
        documentId: run.documentId,
        options: run.options,
        status: run.status,
        createdAt: NOW,
      });
    }
    match = /^\/runs\/(\d+)\/files\/([^/]+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      const name = decodeURIComponent(match[2]!);
      if (!run || run.status !== 'done')
        return refusal(route, 404, 'NOT_FOUND');
      return route.fulfill({
        status: 200,
        contentType: 'application/octet-stream',
        headers: { 'Content-Disposition': `attachment; filename="${name}"` },
        body: BYTES,
      });
    }
    if (key === 'POST /translation/glossary/read')
      return answer(route, 200, {
        ok: true,
        pairs: PAIRS,
        rowCount: PAIRS.length,
      });
    if (key === 'GET /translation/glossary/template')
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: {
          'Content-Disposition':
            'attachment; filename="translation-glossary-template.xlsx"',
        },
        body: BYTES,
      });
    return refusal(route, 404, 'NOT_FOUND');
  });

  const keys = () => calls.map((call) => `${call.method} ${call.path}`);
  const runBodies = () =>
    calls
      .filter((call) => call.method === 'POST' && call.path === '/runs')
      .map((call) => call.body as Json & { options: Json; launchKey: string });
  return { calls, keys, runBodies, runs };
}
