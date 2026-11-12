// e2e 의 그린워싱 흉내 서버(밴드 GW1R ②). 빌드한 웹의 실어댑터가 부르는 경로를 page.route 로 채운다. 답의 값은 전부 지어낸 것이다.
//   - 경로: POST /api/documents · POST /api/documents/{id}/confirm · GET /api/documents/{id} · POST /api/runs · GET /api/runs/{id} ·
//     GET /api/greenwash/checks · GET /api/greenwash/terms/default · GET /api/greenwash/runs/{id}/result·review · PUT …/review.
//   - 서명 올리기 주소는 같은 출처의 `/fake-upload/<문서 id>`(저장소 CORS 는 백엔드 sid:MARC-ISSUE-222 몫 — 여기서는 재지 않는다).
//   - 받은 요청을 calls 에 적는다(메서드·경로·본문·Authorization·본문 크기).
//   - 새 실행의 끝(runOutcome)은 시험이 정한다: 기본은 글자 층 없는 PDF 로 extract 에서 멈춘 failed(no_text_layer).
//   - 밴드 GW2R ③: PATCH /api/documents/{id}(본문 {reportYear} — 1900~2100 밖 422, 올림 확인 전 409 NOT_UPLOADED)와
//     GET /api/greenwash/runs/{id}/report?confirmed=(끝나지 않음 409 RUN_NOT_DONE · 확정 전 확정본 409 NOT_CONFIRMED,
//     받으면 지어낸 바이트 + Content-Disposition). calls 에 쿼리(search)도 적는다.
//   - 밴드 GR3: GET /api/documents/{id}/file(없음 404 · 올림 확인 전 409 NOT_UPLOADED) — 받으면 tools/pdf-writer 로 지은 쪽 수만큼의 PDF
//     (글자 「Page n」만) + Content-Disposition. 이 탭에서 올리지 않은 문서(새로 고침·다른 사용자)의 미리보기 길.
// 목 저장소로 여는 spec 은 useMockStore(page) 를 부른다(탭 표지 — 데모 빌드에서만 먹는다, 밴드 GW1R Q1).
// 로그인은 e2e/session.ts 의 signIn 을 먼저 부른다(이 흉내는 /api/auth·/api/users 를 받지 않는다).
import type { Page, Route } from '@playwright/test';

import { writePdf } from '../tools/pdf-writer.ts';

/** 목 저장소 탭 표지(app/greenwash/GreenwashRoutes.tsx 의 MOCK_TAB_KEY 와 같은 글자 — e2e 는 app 을 가져오지 않는다). */
const MOCK_TAB_KEY = 'esg.gw.store';

/** 이 탭을 목 저장소로 연다(쪽을 열 때마다 sessionStorage 에 표지를 심는다). */
export async function useMockStore(page: Page) {
  await page.addInitScript(
    ([key]) => sessionStorage.setItem(key!, 'mock'),
    [MOCK_TAB_KEY],
  );
}

export interface GreenwashCall {
  method: string;
  path: string;
  /** 쿼리 글자(「?confirmed=true」, 없으면 빈 글자). */
  search: string;
  body: unknown;
  authorization: string | null;
  size: number;
}

type Step = {
  step: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  done: number | null;
  total: number | null;
};

const STEP_NAMES = [
  'extract',
  'index',
  'judge',
  'wordcount',
  'locate',
  'report',
];
export const steps = (
  doneUntil: number,
  at?: Partial<Step> & { status: Step['status'] },
): Step[] =>
  STEP_NAMES.map((step, index) =>
    index < doneUntil ? { step, status: 'done', done: null, total: null }
    : index === doneUntil && at ?
      {
        step,
        status: at.status,
        done: at.done ?? null,
        total: at.total ?? null,
      }
    : { step, status: 'pending', done: null, total: null },
  );

export interface FakeDoc {
  id: number;
  fileName: string;
  sizeBytes: number;
  uploaded: boolean;
  pageCount: number | null;
  uploadedAt: string | null;
  uploadedBy: { userId: number; name: string };
  /** 보고연도(PATCH 로 정한다 — 밴드 GW2R ③). */
  reportYear?: number | null;
}

export interface FakeRun {
  id: number;
  documentId: number;
  status: 'queued' | 'processing' | 'done' | 'failed';
  steps: Step[];
  options: Record<string, unknown>;
  errorCode: string | null;
  createdAt: string;
  /** 끝난 때(RunOut.finishedAt — 밴드 GW2R ②). 없으면 null. */
  finishedAt?: string | null;
  result: Record<string, unknown> | null;
  review: {
    state: 'pending' | 'in_review' | 'confirmed';
    marks: {
      itemIndex: number;
      decision: string;
      excludeReason: string | null;
    }[];
    confirmedAt: string | null;
    confirmedBy: { id: number; name: string } | null;
    /** review@2 의 고침(G1b-3). 없으면 []. */
    edits?: FakeEdit[];
  } | null;
}

/** review@2 고친 칸 하나(값·때·사람). */
interface FakeEdited<T> {
  value: T;
  editedAt: string;
  editedBy: { id: number; name: string };
}
interface FakeEdit {
  itemIndex: number;
  level: FakeEdited<string> | null;
  reasonBullets: FakeEdited<string[]> | null;
  fixParagraph: FakeEdited<string> | null;
}
interface FakeEditIn {
  itemIndex: number;
  level: string | null;
  reasonBullets: string[] | null;
  fixParagraph: string | null;
}

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

const NOW = '2026-10-19T10:00:00+09:00';

export interface FakeGreenwashApiOptions {
  documents?: FakeDoc[];
  runs?: FakeRun[];
  /** 새 실행(POST /runs)의 끝. 기본: extract 에서 멈춘 failed no_text_layer. */
  runOutcome?: Pick<FakeRun, 'status' | 'steps' | 'errorCode'>;
  /** 확정한 사람(PUT state=confirmed 의 confirmedBy). */
  confirmer?: { id: number; name: string };
}

export async function fakeGreenwashApi(
  page: Page,
  {
    documents = [],
    runs = [],
    runOutcome = {
      status: 'failed',
      steps: steps(0, { status: 'failed' }),
      errorCode: 'no_text_layer',
    },
    confirmer = { id: 1, name: '지어낸-user01' },
  }: FakeGreenwashApiOptions = {},
) {
  const calls: GreenwashCall[] = [];
  const docs = new Map(documents.map((doc) => [doc.id, doc]));
  const runMap = new Map(runs.map((run) => [run.id, run]));
  const uploads = new Map<number, number>();
  let docSeq = 12;
  let runSeq = 13;

  const documentOut = (doc: FakeDoc) => ({
    id: doc.id,
    fileName: doc.fileName,
    sizeBytes: doc.sizeBytes,
    status: doc.uploaded ? 'uploaded' : 'awaiting_upload',
    pageCount: doc.pageCount,
    hasText: null,
    reportYear: doc.reportYear ?? null,
    previousDocumentId: null,
    etag: null,
    createdAt: NOW,
    uploadedAt: doc.uploadedAt,
  });
  const runOut = (run: FakeRun) => ({
    id: run.id,
    documentId: run.documentId,
    module: 'greenwash',
    flowId: 'greenwash.colab@E0',
    status: run.status,
    steps: run.steps,
    options: run.options,
    errorCode: run.errorCode,
    errorMessage: null,
    failedStep: null,
    files: [],
    resultShapes: ['greenwash.result@1'],
    resumedFromRunId: null,
    createdAt: run.createdAt,
    startedAt: NOW,
    finishedAt: run.finishedAt ?? null,
  });
  const reviewOut = (run: FakeRun) => ({
    schemaVersion: 'greenwash.review@3',
    evidence: [],
    rejudges: [],
    runId: run.id,
    ...run.review!,
    edits: run.review!.edits ?? [],
  });
  /** PUT 의 평평한 고침 → 서버 규칙(strip·빈 줄 버림·AI 와 같은 칸 null·칸마다 값이 바뀐 PUT 에서만 때·사람) 흉내. */
  const nextEdits = (
    items: Record<string, unknown>[],
    before: FakeEdit[],
    wanted: FakeEditIn[],
  ): FakeEdit[] => {
    const old = new Map(before.map((e) => [e.itemIndex, e]));
    const cell = <T>(
      value: T | null,
      ai: unknown,
      prev: FakeEdited<T> | null | undefined,
    ): FakeEdited<T> | null => {
      if (value === null || JSON.stringify(value) === JSON.stringify(ai))
        return null;
      if (prev && JSON.stringify(prev.value) === JSON.stringify(value))
        return prev;
      return { value, editedAt: NOW, editedBy: confirmer };
    };
    return wanted
      .map((w) => {
        const ai = items[w.itemIndex] ?? {};
        const prev = old.get(w.itemIndex);
        const bullets =
          w.reasonBullets === null ?
            null
          : w.reasonBullets.map((b) => b.trim()).filter((b) => b !== '');
        return {
          itemIndex: w.itemIndex,
          level: cell(w.level, ai.level, prev?.level),
          reasonBullets: cell(bullets, ai.reasonBullets, prev?.reasonBullets),
          fixParagraph: cell(
            w.fixParagraph === null ? null : w.fixParagraph.trim(),
            ai.fixParagraph,
            prev?.fixParagraph,
          ),
        };
      })
      .filter((e) => e.level || e.reasonBullets || e.fixParagraph)
      .sort((a, b) => a.itemIndex - b.itemIndex);
  };
  const levelCountsOf = (run: FakeRun) => {
    const counts = {
      ...(run.result!.counts as { byLevel: Record<string, number> }).byLevel,
    };
    const items = run.result!.items as { level: string }[];
    for (const edit of run.review?.edits ?? []) {
      const ai = items[edit.itemIndex]?.level;
      if (edit.level === null || ai === undefined) continue;
      counts[ai] = (counts[ai] ?? 0) - 1;
      counts[edit.level.value] = (counts[edit.level.value] ?? 0) + 1;
    }
    return counts;
  };
  const union = (options: Record<string, unknown>) => {
    const parts = options.parts as Record<string, number[]>;
    return new Set(Object.values(parts).flat()).size;
  };

  await page.route('**/fake-upload/*', async (route) => {
    const request = route.request();
    const id = Number(new URL(request.url()).pathname.split('/').pop());
    const size = request.postDataBuffer()?.length ?? 0;
    calls.push({
      method: request.method(),
      path: new URL(request.url()).pathname,
      search: '',
      body: undefined,
      authorization: request.headers()['authorization'] ?? null,
      size,
    });
    uploads.set(id, size);
    return route.fulfill({ status: 200, body: '' });
  });

  const handler = async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^.*?\/api(?=\/)/, '');
    const method = request.method();
    const body: unknown =
      request.postData() ? request.postDataJSON() : undefined;
    calls.push({
      method,
      path,
      search: new URL(request.url()).search,
      body,
      authorization: request.headers()['authorization'] ?? null,
      size: request.postDataBuffer()?.length ?? 0,
    });
    const key = `${method} ${path}`;
    if (key === 'POST /documents') {
      const { fileName, sizeBytes } = body as {
        fileName: string;
        sizeBytes: number;
      };
      const doc: FakeDoc = {
        id: docSeq++,
        fileName,
        sizeBytes,
        uploaded: false,
        pageCount: null,
        uploadedAt: null,
        uploadedBy: { userId: 1, name: '지어낸-user01' },
      };
      docs.set(doc.id, doc);
      const origin = new URL(request.url()).origin;
      return answer(route, 201, {
        document: documentOut(doc),
        upload: {
          url: `${origin}/fake-upload/${doc.id}`,
          method: 'PUT',
          expiresInSeconds: 900,
        },
      });
    }
    let match = /^\/documents\/(\d+)\/file$/.exec(path);
    if (match && method === 'GET') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      if (!doc.uploaded) return refusal(route, 409, 'NOT_UPLOADED');
      const pages = Array.from(
        { length: Math.min(doc.pageCount ?? 1, 20) },
        (_, i) => ({
          width: 595,
          height: 842,
          rotate: 0 as const,
          marks: [],
          texts: [{ x: 72, top: 72, size: 18, str: `Page ${i + 1}` }],
          tables: [],
        }),
      );
      return route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        headers: {
          'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(doc.fileName)}`,
        },
        body: Buffer.from(writePdf(pages)),
      });
    }
    match = /^\/documents\/(\d+)(\/confirm)?$/.exec(path);
    if (match) {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      if (match[2] && method === 'POST') {
        if (uploads.get(doc.id) !== doc.sizeBytes)
          return refusal(route, 409, 'NOT_UPLOADED');
        doc.uploaded = true;
        doc.uploadedAt = NOW;
      }
      if (!match[2] && method === 'PATCH') {
        const year = (body as { reportYear?: unknown }).reportYear;
        if (!(
          year === null ||
          (Number.isInteger(year) &&
            (year as number) >= 1900 &&
            (year as number) <= 2100)
        ))
          return refusal(route, 422, 'VALIDATION_ERROR');
        if (!doc.uploaded) return refusal(route, 409, 'NOT_UPLOADED');
        doc.reportYear = year as number | null;
        return answer(route, 200, documentOut(doc));
      }
      return answer(route, 200, { document: documentOut(doc), jobs: [] });
    }
    if (key === 'POST /runs') {
      const { documentId, options } = body as {
        documentId: number;
        options: Record<string, unknown>;
      };
      const doc = docs.get(documentId);
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      if (!doc.uploaded) return refusal(route, 409, 'DOCUMENT_NOT_UPLOADED');
      const run: FakeRun = {
        id: runSeq++,
        documentId,
        options,
        createdAt: NOW,
        result: null,
        review: null,
        ...runOutcome,
      };
      runMap.set(run.id, run);
      return answer(route, 201, { id: run.id, status: 'queued' });
    }
    match = /^\/runs\/(\d+)$/.exec(path);
    if (match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      return answer(route, 200, runOut(run));
    }
    if (key === 'GET /greenwash/terms/default')
      return answer(route, 200, { terms: ['친환경'] });
    if (key === 'GET /greenwash/checks') {
      const used = new Set([...runMap.values()].map((run) => run.documentId));
      return answer(route, 200, {
        schemaVersion: 'greenwash.checks@1',
        currentUserId: 1,
        companyName: '지어낸 회사',
        documents: [...docs.values()]
          .filter((doc) => used.has(doc.id))
          .map((doc) => ({
            documentId: doc.id,
            fileName: doc.fileName,
            reportYear: doc.reportYear ?? null,
            previousDocumentId: null,
            pageCount: doc.pageCount,
            uploadedAt: doc.uploadedAt,
            uploadedBy: doc.uploadedBy,
          })),
        runs: [...runMap.values()].map((run) => ({
          runId: run.id,
          documentId: run.documentId,
          createdAt: run.createdAt,
          // 끝난 때(checks@1 runs[].finishedAt — GCB1): done·failed 만 값, 그 밖 null(testing.ts·mockStore 와 같게)
          finishedAt:
            run.status === 'done' || run.status === 'failed' ?
              (run.finishedAt ?? null)
            : null,
          createdByUserId: 1,
          status: run.status,
          steps: run.steps,
          checkedPages: union(run.options),
          errorCode: run.status === 'failed' ? run.errorCode : null,
          // 효력 등급(고친 등급 ?? AI) — 서버 checks levelCounts 와 같은 뜻(밴드 G1b-3 ②)
          levelCounts: run.result ? levelCountsOf(run) : null,
          review:
            run.review && run.result ?
              {
                state: run.review.state,
                reviewed: run.review.marks.length,
                total: (run.result.items as unknown[]).length,
                confirmedAt: run.review.confirmedAt,
                confirmedBy: run.review.confirmedBy,
              }
            : null,
        })),
      });
    }
    match = /^\/greenwash\/runs\/(\d+)\/report$/.exec(path);
    if (match && method === 'GET') {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done' || !run.result)
        return refusal(route, 409, 'RUN_NOT_DONE');
      const confirmed =
        new URL(request.url()).searchParams.get('confirmed') === 'true';
      if (confirmed && run.review?.state !== 'confirmed')
        return refusal(route, 409, 'NOT_CONFIRMED');
      const name = `지어낸 보고서 ${run.id}${confirmed ? ' 확정본' : ''}.xlsx`;
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: {
          'Content-Disposition': `attachment; filename="report-${run.id}.xlsx"; filename*=UTF-8''${encodeURIComponent(name)}`,
        },
        body: Buffer.from([80, 75, 3, 4, 1, 2, 3]),
      });
    }
    match = /^\/greenwash\/runs\/(\d+)\/(result|review)$/.exec(path);
    if (match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done' || !run.result)
        return refusal(route, 409, 'RUN_NOT_DONE');
      if (match[2] === 'result') return answer(route, 200, run.result);
      if (!run.review) return refusal(route, 409, 'NO_REVIEW');
      if (method === 'GET') return answer(route, 200, reviewOut(run));
      if (run.review.state === 'confirmed')
        return refusal(route, 409, 'REVIEW_LOCKED');
      const update = body as {
        state?: string | null;
        marks: NonNullable<FakeRun['review']>['marks'];
        edits?: FakeEditIn[] | null;
      };
      const confirming = update.state === 'confirmed';
      const byIndex = new Map(
        update.marks.map((mark) => [mark.itemIndex, mark]),
      );
      const items = run.result.items as Record<string, unknown>[];
      const edits =
        update.edits == null ?
          (run.review.edits ?? [])
        : nextEdits(items, run.review.edits ?? [], update.edits);
      const touched =
        update.marks.length > 0 || (update.edits != null && edits.length > 0);
      run.review = {
        edits,
        state:
          confirming ? 'confirmed'
          : touched ? 'in_review'
          : run.review.state,
        marks:
          confirming ?
            items.map(
              (_item, itemIndex) =>
                byIndex.get(itemIndex) ?? {
                  itemIndex,
                  decision: 'adopted',
                  excludeReason: null,
                },
            )
          : update.marks,
        confirmedAt: confirming ? NOW : null,
        confirmedBy: confirming ? confirmer : null,
      };
      return answer(route, 200, reviewOut(run));
    }
    return refusal(route, 404, 'NOT_FOUND');
  };
  for (const glob of [
    '**/api/documents',
    '**/api/documents/**',
    '**/api/runs',
    '**/api/runs/**',
    '**/api/greenwash/**',
  ])
    await page.route(glob, handler);

  /** 「메서드 경로」 차례(서명 PUT 포함). */
  const keys = () => calls.map((call) => `${call.method} ${call.path}`);
  return { calls, keys, docs, runs: runMap };
}
