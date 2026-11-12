// e2e 의 원고작성 흉내 서버(밴드 RPW1 ② — e2e/materiality-server.ts·translation-pdf-server.ts 꼴). 빌드한 웹의 실어댑터가 부르는 경로를 page.route 로 채운다.
// 답의 값은 전부 지어낸 것이다(「가상제조」 꼴 — 실재 기업명 0). 포트는 쥐지 않는다 — playwright.config.ts 의 WEB_TEST_PORT 미리보기 서버에 붙는
//   page.route 뿐이다. e2e 는 웹 코드에서 문구 표(config/text.ts)만 들이므로(app/guards/layers.test.ts) 꼴은 여기서 짓는다
//   (entities/drafting/api/testing.ts 의 vitest 가짜와 같은 꼴 — openapi DraftingProject·DraftingProjectListItem·DraftingRunItem·RunOut).
//   - 경로(②): GET·POST /api/drafting/projects · GET /api/drafting/projects/{id} · PUT …/{id}/document · PUT …/{id}/outline ·
//     POST /api/documents · 서명 올리기 /fake-upload/<id>(Authorization 을 calls 에 적는다) · POST /api/documents/{id}/confirm(쪽 수 = 받은 바이트의
//     /Type /Page 수, hasText true) · POST /api/runs(Idempotency-Key 적음, 같은 열쇠·같은 본문이면 앞 실행, 다른 본문이면 409) · GET /api/runs/{id}.
//   - 실행 읽기 한 번마다 한 걸음: queued → extract → map → draft 1/n … n/n → done(n = 잎 수).
//   - 경로(③): GET /api/drafting/runs/{id}/result(@3 — 잎마다 bullet, 첫 잎만 근거 두 층: 1쪽 블록 둘·문장 셋 · 2쪽 블록 하나·문장 없음(SEED_MARKS)) ·
//     …/result.docx · GET /api/drafting/projects/{id}/outline/changes?baseRunId(잎 제목·요구로 견줌) · GET /api/documents/{id}/file(올린 바이트).
//     seed(pdf, nodes?) = 문서·목차(주지 않으면 둘 — 잎 a1·a2)·끝난 실행 하나를 곧바로 심는다(S7b 가 goto 로 RP-04 에 들어간다).
//   - 갈래(RPW2 ②): noTextNext() = 다음 올리는 문서의 hasText 거짓 · dropRunOnce() = 다음 POST /runs 를 적고 연결을 끊는다(같은 열쇠로 다시 오면 그때 선다).
//   - 응답 꼴은 S7e 가 openapi 성공 꼴의 required 와 견준다(RPW2 502 ⓔ).
//   - 목차 검사는 wire.py 의 뼈대만(부모가 앞·depth = 부모 + 1·깊이 4) — 칸 하나하나는 vitest 몫.
// 이 흉내는 위 경로만 받는다 — 그 밖 /api/ 는 다음 route(spec 의 덫 503)로 넘긴다. 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다.
import type { Page, Route } from '@playwright/test';

export interface DraftingCall {
  method: string;
  path: string;
  body: unknown;
  idempotencyKey: string | null;
  authorization: string | null;
}

type Json = Record<string, unknown>;
type Status = 'queued' | 'processing' | 'done' | 'failed';

interface OutlineNode {
  key: string;
  parentKey: string | null;
  depth: number;
  title: string;
  requirement: string;
}

interface Project {
  id: number;
  name: string;
  year: number;
  documentId: number | null;
  outline: { outlineId: number; revision: number; nodes: OutlineNode[] } | null;
}

interface Doc {
  id: number;
  fileName: string;
  sizeBytes: number;
  uploaded: boolean;
  noText: boolean;
  pageCount: number | null;
  bytes: Buffer | null;
}

interface Run {
  id: number;
  projectId: number;
  options: Json;
  outlineId: number;
  documentId: number;
  nodes: OutlineNode[];
  leaves: number;
  /** 걸음 수(0 = queued). */
  tick: number;
  status: Status;
}

const NOW = '2026-10-30T09:00:00+09:00';

const answer = (route: Route, status: number, body?: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: body === undefined ? '' : JSON.stringify(body),
  });
const refusal = (
  route: Route,
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  answer(route, status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });

/** 시드 결과 첫 잎의 근거 상자 손셈(쪽 → [옅은 블록 수, 진한 문장 수]) — S7b 가 견준다. */
export const SEED_MARKS: Record<number, [number, number]> = {
  1: [2, 3],
  2: [1, 0],
};

const leafKeys = (nodes: readonly OutlineNode[]) => {
  const parents = new Set(nodes.map((node) => node.parentKey));
  return nodes.filter((node) => !parents.has(node.key));
};

/** 끝난 실행의 결과(@3). 첫 잎만 근거 두 층, 나머지 잎은 출처 없는 bullet 하나. */
function resultOf(run: Run, doc: Doc) {
  const pages = doc.pageCount ?? 1;
  return {
    schemaVersion: 'drafting.bullets@3',
    projectId: run.projectId,
    outlineId: run.outlineId,
    outlineSha256: 'c'.repeat(64),
    basis: null,
    base: null,
    status: { status: 'done' },
    document: {
      documentId: doc.id,
      fileName: doc.fileName,
      pageCount: pages,
      textPages: pages,
      pages: Array.from({ length: pages }, (_, at) => ({
        page: at + 1,
        width: 595,
        height: 842,
      })),
    },
    leaves: leafKeys(run.nodes).map((node, at) => ({
      key: node.key,
      titlePath: [node.title],
      pages: at === 0 ? [1, 2] : [],
      reusedFrom: null,
      outcome: {
        status: 'done',
        bullets:
          at === 0 ?
            [
              {
                text: '가상 근거 bullet 하나',
                unsupported: false,
                sources: [
                  {
                    documentId: doc.id,
                    blockId: 'p1-b1',
                    page: 1,
                    blockBox: [72, 60, 400, 100],
                    sentence: {
                      index: 0,
                      boxes: [
                        [72, 60, 380, 78],
                        [72, 80, 300, 98],
                      ],
                    },
                  },
                  {
                    documentId: doc.id,
                    blockId: 'p1-b2',
                    page: 1,
                    blockBox: [72, 140, 400, 200],
                    sentence: { index: 0, boxes: [[72, 140, 360, 160]] },
                  },
                  {
                    documentId: doc.id,
                    blockId: 'p2-b1',
                    page: 2,
                    blockBox: [72, 60, 400, 120],
                    sentence: null,
                  },
                ],
              },
            ]
          : [{ text: `가상 ${node.title}`, unsupported: true, sources: [] }],
      },
    })),
    mapping: { batches: 1, failedBatches: [] },
    settings: {
      routes: { map: '지어낸-경로', draft: '지어낸-경로' },
      promptIds: { map: '지어낸-글', draft: '지어낸-글' },
    },
    warnings: [],
  };
}

const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value);

/** 목차 뼈대 검사 — 문제면 422 fields. */
function outlineProblem(nodes: unknown): Record<string, string[]> | null {
  if (!Array.isArray(nodes) || nodes.length < 1 || nodes.length > 300)
    return { nodes: ['지어낸 마디 수'] };
  const depth = new Map<string, number>();
  for (const raw of nodes as OutlineNode[]) {
    if (depth.has(raw.key) || !/^[a-z0-9][a-z0-9-]{0,39}$/.test(raw.key))
      return { nodes: ['지어낸 key'] };
    const expected =
      raw.parentKey === null ? 1 : (depth.get(raw.parentKey) ?? -9) + 1;
    if (raw.depth !== expected || raw.depth > 4)
      return { nodes: ['지어낸 구조'] };
    depth.set(raw.key, raw.depth);
  }
  return null;
}

const leafCount = (nodes: readonly OutlineNode[]) => {
  const parents = new Set(nodes.map((node) => node.parentKey));
  return nodes.filter((node) => !parents.has(node.key)).length;
};

export async function fakeDraftingApi(page: Page) {
  const calls: DraftingCall[] = [];
  const projects = new Map<number, Project>();
  const docs = new Map<number, Doc>();
  const runs = new Map<number, Run>();
  const keys = new Map<string, { id: number; body: string }>();
  let projectSeq = 1;
  let docSeq = 101;
  let outlineSeq = 201;
  let runSeq = 301;
  let noTextNext = false;
  let dropRuns = 0;

  /** 걸음 → 단계 넷과 진행. */
  const stepsOf = (run: Run) => {
    const n = run.leaves;
    const at = (index: number) =>
      run.status === 'done' ? 'done'
      : run.tick === 0 ? 'pending'
      : index < Math.min(run.tick - 1, 2) ? 'done'
      : index === Math.min(run.tick - 1, 2) ? 'running'
      : 'pending';
    const drafted = Math.max(0, Math.min(run.tick - 3, n));
    return [
      { step: 'extract', status: at(0), done: null, total: null },
      { step: 'map', status: at(1), done: null, total: null },
      {
        step: 'draft',
        status: at(2),
        done: run.tick >= 3 || run.status === 'done' ? drafted : null,
        total: run.tick >= 3 || run.status === 'done' ? n : null,
      },
      {
        step: 'report',
        status: run.status === 'done' ? 'done' : 'pending',
        done: null,
        total: null,
      },
    ];
  };

  const runItemOf = (run: Run) => {
    const base = run.options.base as
      { runId: number; rebuild: string[] } | undefined;
    const running = stepsOf(run).find((step) => step.status === 'running');
    return {
      id: run.id,
      status: run.status,
      createdAt: NOW,
      finishedAt: run.status === 'done' || run.status === 'failed' ? NOW : null,
      outlineId: run.outlineId,
      baseRunId: base?.runId ?? null,
      rebuild: base?.rebuild ?? [],
      progress:
        run.status === 'processing' && running ?
          { step: running.step, done: running.done, total: running.total }
        : null,
      // RPS1: rejected·leaves 는 done + @3 결과만(failed·끝나기 전 null).
      rejected: run.status === 'done' ? false : null,
      leaves:
        run.status === 'done' ?
          {
            total: run.leaves,
            drafted: run.leaves,
            noMaterial: 0,
            failed: 0,
            notRun: 0,
          }
        : null,
    };
  };

  const latestOf = (projectId: number) => {
    const last = [...runs.values()]
      .filter((run) => run.projectId === projectId)
      .sort((a, b) => b.id - a.id)[0];
    return last ? runItemOf(last) : null;
  };

  const projectOut = (project: Project) => ({
    id: project.id,
    name: project.name,
    year: project.year,
    createdAt: NOW,
    createdByUserId: 1,
    document:
      project.documentId === null ?
        null
      : {
          documentId: project.documentId,
          kind: 'previous_report',
          attachedAt: NOW,
          attachedByUserId: 1,
        },
    outline:
      project.outline === null ?
        null
      : {
          outlineId: project.outline.outlineId,
          revision: project.outline.revision,
          sha256: 'a'.repeat(64),
          outline: { nodes: project.outline.nodes },
        },
    latestRun: latestOf(project.id),
  });

  const documentOut = (doc: Doc) => ({
    id: doc.id,
    fileName: doc.fileName,
    sizeBytes: doc.sizeBytes,
    status: doc.uploaded ? 'uploaded' : 'awaiting_upload',
    pageCount: doc.pageCount,
    hasText: doc.uploaded ? !doc.noText : null,
    reportYear: null,
    previousDocumentId: null,
    etag: null,
    createdAt: NOW,
    uploadedAt: doc.uploaded ? NOW : null,
  });

  const runOut = (run: Run) => ({
    id: run.id,
    module: 'drafting',
    flowId: 'drafting.bullets@3',
    documentId: null,
    options: run.options,
    status: run.status,
    steps: stepsOf(run),
    errorCode: run.status === 'failed' ? 'DRAFT_FAILED' : null,
    errorMessage: run.status === 'failed' ? '지어낸-서버글-실패' : null,
    failedStep: null,
    files: [],
    resultShapes: [],
    resumedFromRunId: null,
    createdAt: NOW,
    startedAt: null,
    finishedAt: run.status === 'done' || run.status === 'failed' ? NOW : null,
  });

  await page.route('**/fake-upload/*', async (route) => {
    const request = route.request();
    const id = Number(new URL(request.url()).pathname.split('/').pop());
    const doc = docs.get(id);
    const bytes = request.postDataBuffer() ?? Buffer.alloc(0);
    if (doc) {
      doc.uploaded = true;
      doc.bytes = bytes;
      const pages = bytes.toString('latin1').match(/\/Type \/Page(?!s)/g);
      doc.pageCount = pages ? pages.length : null;
    }
    calls.push({
      method: request.method(),
      path: new URL(request.url()).pathname,
      body: undefined,
      idempotencyKey: null,
      authorization: request.headers()['authorization'] ?? null,
    });
    return route.fulfill({ status: 200, body: '' });
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
    const method = request.method();
    if (!/^\/(drafting|documents|runs)(\/|$)/.test(path))
      return route.fallback();
    let body: unknown;
    try {
      body = request.postData() ? request.postDataJSON() : undefined;
    } catch {
      body = undefined;
    }
    const idempotencyKey = request.headers()['idempotency-key'] ?? null;
    calls.push({
      method,
      path,
      body,
      idempotencyKey,
      authorization: null,
    });
    const key = `${method} ${path}`;

    if (key === 'GET /drafting/projects') {
      const rows = [...projects.values()]
        .sort((a, b) => b.id - a.id)
        .map((project) => ({
          id: project.id,
          name: project.name,
          year: project.year,
          createdAt: NOW,
          hasDocument: project.documentId !== null,
          documentName:
            project.documentId === null ?
              null
            : (docs.get(project.documentId)?.fileName ?? null),
          outlineId: project.outline?.outlineId ?? null,
          outlineRevision: project.outline?.revision ?? null,
          latestRun: latestOf(project.id),
        }));
      return answer(route, 200, {
        count: rows.length,
        isNext: false,
        results: rows,
      });
    }
    if (key === 'POST /drafting/projects') {
      const { year, name } = (body ?? {}) as { year?: unknown; name?: unknown };
      if (!isInt(year) || typeof name !== 'string' || name.trim() === '')
        return refusal(route, 422, 'VALIDATION_ERROR', { name: ['지어낸'] });
      const project: Project = {
        id: projectSeq++,
        name: name.trim(),
        year,
        documentId: null,
        outline: null,
      };
      projects.set(project.id, project);
      return answer(route, 201, projectOut(project));
    }
    let match = /^\/drafting\/projects\/(\d+)(?:\/(document|outline))?$/.exec(
      path,
    );
    if (match) {
      const project = projects.get(Number(match[1]));
      if (!project) return refusal(route, 404, 'NOT_FOUND');
      if (method === 'GET' && !match[2])
        return answer(route, 200, projectOut(project));
      if (method === 'PUT' && match[2] === 'document') {
        const { documentId } = (body ?? {}) as { documentId?: unknown };
        const doc = isInt(documentId) ? docs.get(documentId) : undefined;
        if (!doc || !doc.uploaded) return refusal(route, 404, 'NOT_FOUND');
        project.documentId = doc.id;
        return answer(route, 200, projectOut(project));
      }
      if (method === 'PUT' && match[2] === 'outline') {
        const nodes = (body as { nodes?: unknown } | undefined)?.nodes;
        const problem = outlineProblem(nodes);
        if (problem) return refusal(route, 422, 'VALIDATION_ERROR', problem);
        project.outline = {
          outlineId: outlineSeq++,
          revision: (project.outline?.revision ?? 0) + 1,
          nodes: nodes as OutlineNode[],
        };
        return answer(route, 200, {
          outlineId: project.outline.outlineId,
          revision: project.outline.revision,
          sha256: 'b'.repeat(64),
        });
      }
    }
    if (key === 'POST /documents') {
      const { fileName, sizeBytes } = body as {
        fileName: string;
        sizeBytes: number;
      };
      const doc: Doc = {
        id: docSeq++,
        fileName,
        sizeBytes,
        uploaded: false,
        noText: noTextNext,
        pageCount: null,
        bytes: null,
      };
      noTextNext = false;
      docs.set(doc.id, doc);
      return answer(route, 201, {
        document: documentOut(doc),
        upload: {
          url: `${url.origin}/fake-upload/${doc.id}`,
          method: 'PUT',
          expiresInSeconds: 900,
        },
      });
    }
    match = /^\/documents\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      return answer(route, 200, { document: documentOut(doc), jobs: [] });
    }
    match = /^\/documents\/(\d+)\/confirm$/.exec(path);
    if (match && method === 'POST') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      if (!doc.uploaded) return refusal(route, 409, 'UPLOAD_NOT_FOUND');
      return answer(route, 200, { document: documentOut(doc), jobs: [] });
    }
    if (key === 'POST /runs') {
      if (dropRuns > 0) {
        dropRuns -= 1;
        return route.abort('connectionreset');
      }
      const b = (body ?? {}) as Json;
      const options = b.options as Json | undefined;
      const project =
        options && isInt(options.projectId) ?
          projects.get(options.projectId)
        : undefined;
      if (
        Object.keys(b).sort().join() !== 'launchKey,module,options' ||
        b.module !== 'drafting' ||
        !project ||
        project.documentId === null ||
        project.outline === null
      )
        return refusal(route, 400, 'INVALID_OPTIONS');
      const text = JSON.stringify(body);
      if (idempotencyKey === null)
        return refusal(route, 400, 'VALIDATION_ERROR');
      const seen = keys.get(idempotencyKey);
      if (seen && seen.body !== text)
        return refusal(route, 409, 'IDEMPOTENCY_KEY_REUSED');
      if (seen) {
        const held = runs.get(seen.id)!;
        return answer(route, 201, { id: held.id, status: held.status });
      }
      const run: Run = {
        id: runSeq++,
        projectId: project.id,
        options: options!,
        outlineId: project.outline.outlineId,
        documentId: project.documentId,
        nodes: structuredClone(project.outline.nodes),
        leaves: leafCount(project.outline.nodes),
        tick: 0,
        status: 'queued',
      };
      runs.set(run.id, run);
      keys.set(idempotencyKey, { id: run.id, body: text });
      return answer(route, 201, { id: run.id, status: run.status });
    }
    match = /^\/runs\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      const out = runOut(run);
      // 읽기 한 번마다 한 걸음(답은 걸음 앞의 꼴). 끝난 실행은 그대로.
      if (run.status === 'queued' || run.status === 'processing') {
        run.tick += 1;
        run.status = run.tick > run.leaves + 3 ? 'done' : 'processing';
      }
      return answer(route, 200, out);
    }
    match = /^\/drafting\/runs\/(\d+)\/(result|result\.docx)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      const doc = run && docs.get(run.documentId);
      if (!run || !doc) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(route, 409, 'RUN_NOT_DONE');
      if (match[2] === 'result') return answer(route, 200, resultOf(run, doc));
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers: {
          'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent('가상 초안')}.docx`,
        },
        body: Buffer.from([80, 75, 3, 4]),
      });
    }
    match = /^\/drafting\/projects\/(\d+)\/runs$/.exec(path);
    if (match && method === 'GET') {
      const project = projects.get(Number(match[1]));
      if (!project) return refusal(route, 404, 'NOT_FOUND');
      const mine = [...runs.values()]
        .filter((run) => run.projectId === project.id)
        .sort((a, b) => b.id - a.id)
        .map(runItemOf);
      return answer(route, 200, {
        count: mine.length,
        isNext: false,
        results: mine,
      });
    }
    match = /^\/drafting\/projects\/(\d+)\/outline\/changes$/.exec(path);
    if (match && method === 'GET') {
      const project = projects.get(Number(match[1]));
      const base = runs.get(Number(url.searchParams.get('baseRunId')));
      if (!project?.outline || !base || base.projectId !== project.id)
        return refusal(route, 404, 'NOT_FOUND');
      const digest = (node: OutlineNode) =>
        `${node.title}\n${node.requirement}`;
      const before = new Map(
        leafKeys(base.nodes).map((node) => [node.key, digest(node)]),
      );
      const now = leafKeys(project.outline.nodes);
      return answer(route, 200, {
        baseRunId: base.id,
        baseOutlineId: base.outlineId,
        outlineId: project.outline.outlineId,
        document: base.documentId === project.documentId ? 'same' : 'changed',
        leaves: now.map((node) => ({
          key: node.key,
          change:
            !before.has(node.key) ? 'added'
            : before.get(node.key) === digest(node) ? 'same'
            : 'changed',
        })),
        removed: [...before.keys()].filter(
          (key) => !now.some((node) => node.key === key),
        ),
      });
    }
    match = /^\/documents\/(\d+)\/file$/.exec(path);
    if (match && method === 'GET') {
      const doc = docs.get(Number(match[1]));
      if (!doc?.bytes) return refusal(route, 404, 'NOT_FOUND');
      return route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        body: doc.bytes,
      });
    }
    return route.fallback();
  });

  /** 문서(pdf 바이트)·목차(대 하나 아래 잎 a1·a2)·끝난 실행 하나를 심는다 → [프로젝트 id, 실행 id]. */
  const seed = (pdf: Buffer, given?: OutlineNode[]): [number, number] => {
    const doc: Doc = {
      id: docSeq++,
      fileName: 'made_up_report.pdf',
      sizeBytes: pdf.length,
      uploaded: true,
      noText: false,
      pageCount: (pdf.toString('latin1').match(/\/Type \/Page(?!s)/g) ?? [])
        .length,
      bytes: pdf,
    };
    docs.set(doc.id, doc);
    const nodes: OutlineNode[] = given ?? [
      {
        key: 'a',
        parentKey: null,
        depth: 1,
        title: '가상 환경',
        requirement: '',
      },
      {
        key: 'a1',
        parentKey: 'a',
        depth: 2,
        title: '가상 기후',
        requirement: '가상 요구',
      },
      {
        key: 'a2',
        parentKey: 'a',
        depth: 2,
        title: '가상 자원',
        requirement: '',
      },
    ];
    const project: Project = {
      id: projectSeq++,
      name: '가상 보고서',
      year: 2026,
      documentId: doc.id,
      outline: { outlineId: outlineSeq++, revision: 1, nodes },
    };
    projects.set(project.id, project);
    const run: Run = {
      id: runSeq++,
      projectId: project.id,
      options: { projectId: project.id },
      outlineId: project.outline!.outlineId,
      documentId: doc.id,
      nodes: structuredClone(nodes),
      leaves: 2,
      tick: 99,
      status: 'done',
    };
    runs.set(run.id, run);
    return [project.id, run.id];
  };

  const of = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key);
  return {
    calls,
    of,
    projects,
    runs,
    seed,
    noTextNext: () => {
      noTextNext = true;
    },
    dropRunOnce: () => {
      dropRuns += 1;
    },
  };
}
