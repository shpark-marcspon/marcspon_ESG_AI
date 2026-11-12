// 시험용 가짜 원고작성 서버(밴드 RPW1 ①). 시험만 쓴다(공개 표면이 아니다). 값은 전부 지어낸 것이다.
// 답의 꼴은 openapi 의 Drafting*·DocumentCreatedOut·DocumentStatusOut·RunOut(RPS1 의 latestRun·runs 포함)을 따르고 서버 규칙을 흉내 낸다:
//   - 만들기: year 2000~2100 정수·name 앞뒤 공백 걷어 1~80(코드 포인트) 밖이면 422 fields.year·name. 같은 회사·연도 둘째도 막지 않는다(⑬).
//   - 문서: POST /documents → 서명 주소(밖 저장소) → confirm. confirm 은 PUT 이 온 문서만(아니면 409). hasText 는 씨앗(noText·textUnknown).
//     PUT …/document 는 confirm 한 문서만(아니면 404), hasText 거짓이면 422 DOCUMENT_NO_TEXT_LAYER.
//   - 목차: wire.py 규칙(key 꼴·겹침·첫 마디·부모가 앞·depth = 부모 + 1·1~4·마디 1~300·잎 1~150·title strip 1~200·requirement ≤2,000) →
//     422 VALIDATION_ERROR fields `nodes.<i>.<칸>`(칸 하나 문제) 또는 `nodes`(구조). 저장마다 새 outlineId·revision + 1.
//   - 실행: Idempotency-Key 필수 · 같은 열쇠 같은 본문 = 앞 실행 · 같은 열쇠 다른 본문 409 IDEMPOTENCY_KEY_REUSED · 옵션은 options@2(모르는 키·
//     문서·목차 없음·base 실행이 done 아님 → 400 INVALID_OPTIONS) · aiUnusable 이면 409 AI_SETTING_UNUSABLE. 새 실행은 queued.
//     시험이 runPatch(id, …)로 단계·상태를 옮기고 results 에 결과를 심는다(done 이 아니면 결과 409 RUN_NOT_DONE).
//   - 차이: 기준 실행의 목차 → 지금 목차의 잎 차이(제목 경로 + 요구 내용이 다르면 changed) · 문서 id 가 다르면 document changed.
//   - 회사 거절: company 를 주면 /drafting/** 이 그 거절(400)을 낸다.
// override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다).
import { createApi } from '../../../shared/api/index.ts';
import type {
  DraftingResult,
  OutlineNode,
  Project,
  RunItem,
  RunStatus,
  RunStep,
} from '../model/index.ts';
import { createDraftingStore } from './server.ts';
import type { NewKey, PendingRuns } from './server.ts';

/** 서버가 보내는 프로젝트 꼴(model 의 pdf 칸이 줄 위에서는 document — 거울이 옮긴다). */
export type ProjectWire = Omit<Project, 'pdf'> & { document: Project['pdf'] };
/** 서버가 보내는 결과 꼴(model 의 pdf 칸이 줄 위에서는 document). */
export type ResultWire = Omit<DraftingResult, 'pdf'> & {
  document: DraftingResult['pdf'];
};

export interface FakeDraftingCall {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
  headers: Headers;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
/** 거절 본문 — message 는 화면에 새면 시험이 잡도록 눈에 띄는 지어낸 글. */
export const refusal = (
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  json(status, {
    error: {
      code,
      message: `지어낸-서버글-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });
export const unreachable = (): Response => {
  throw new TypeError('fetch failed');
};

export const STORAGE = 'http://storage.test';
const KEY = /^[a-z0-9][a-z0-9-]{0,39}$/;
const STEPS = ['extract', 'map', 'draft', 'report'] as const;
const NOW = '2026-10-30T09:00:00+09:00';

interface FakeDocument {
  id: number;
  fileName: string;
  sizeBytes: number;
  uploaded: boolean;
  confirmed: boolean;
  pageCount: number | null;
  hasText: boolean | null;
}

interface FakeRun {
  id: number;
  projectId: number;
  status: RunStatus;
  steps: RunStep[];
  options: Record<string, unknown>;
  outlineId: number;
  documentId: number;
  outlineNodes: OutlineNode[];
  createdAt: string;
  finishedAt: string | null;
}

export interface FakeDraftingServerOptions {
  baseUrl?: string;
  /** 씨앗 프로젝트(document·outline·latestRun 은 서버가 셈 — 씨앗의 값은 무시). */
  projects?: Pick<Project, 'id' | 'name' | 'year'>[];
  /** 주면 /drafting/** 이 이 회사 거절(400)을 낸다. */
  company?: 'COMPANY_AMBIGUOUS' | 'COMPANY_INACTIVE' | 'COMPANY_NOT_FOUND';
  /** 참이면 POST /runs 가 409 AI_SETTING_UNUSABLE. */
  aiUnusable?: boolean;
  /** 참이면 confirm 한 문서의 hasText 가 거짓(글자 없는 PDF). */
  noText?: boolean;
  /** 참이면 confirm 한 문서의 hasText 가 null(서버가 아직 모름). */
  textUnknown?: boolean;
  /** confirm 한 문서의 쪽 수(기본 3). */
  pageCount?: number;
  /** 문서 id → PDF 바이트(GET /documents/{id}/file). 없으면 404. */
  pdfs?: Record<number, Uint8Array>;
}

/** 지어낸 목차 넷(대 하나 · 중 둘 · 소 하나) — 잎은 셋. */
export function fakeOutline(): OutlineNode[] {
  return [
    {
      key: 'n1',
      parentKey: null,
      depth: 1,
      title: '지어낸 환경',
      requirement: '',
    },
    {
      key: 'n2',
      parentKey: 'n1',
      depth: 2,
      title: '지어낸 기후 대응',
      requirement: '지어낸 요구 가',
    },
    {
      key: 'n3',
      parentKey: 'n1',
      depth: 2,
      title: '지어낸 자원',
      requirement: '',
    },
    {
      key: 'n4',
      parentKey: 'n3',
      depth: 3,
      title: '지어낸 물 관리',
      requirement: '지어낸 요구 나',
    },
  ];
}

const pathId = (text: string | undefined): number | null =>
  text !== undefined && /^[1-9][0-9]*$/.test(text) ? Number(text) : null;
const points = (text: string) => [...text].length;
const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value);

/** 목차 검사(wire.py) → 422 fields 나 null. */
function outlineProblems(nodes: unknown): Record<string, string[]> | null {
  if (!Array.isArray(nodes) || nodes.length < 1 || nodes.length > 300)
    return { nodes: ['지어낸 마디 수'] };
  const depthOf = new Map<string, number>();
  const parents = new Set<string>();
  for (const [index, raw] of nodes.entries()) {
    const node = raw as Record<string, unknown>;
    const at = `nodes.${index}`;
    if (
      typeof node.key !== 'string' ||
      !KEY.test(node.key) ||
      depthOf.has(node.key)
    )
      return { [`${at}.key`]: ['지어낸 key'] };
    const parent = node.parentKey;
    if (!isInt(node.depth)) return { [`${at}.depth`]: ['지어낸 depth'] };
    if (parent === null) {
      if (node.depth !== 1) return { nodes: ['지어낸 구조'] };
    } else if (typeof parent !== 'string' || !depthOf.has(parent))
      return { nodes: ['지어낸 구조'] };
    else if (node.depth !== depthOf.get(parent)! + 1 || node.depth > 4)
      return { nodes: ['지어낸 구조'] };
    if (typeof node.title !== 'string')
      return { [`${at}.title`]: ['지어낸 제목'] };
    const title = node.title.trim();
    if (points(title) < 1 || points(title) > 200)
      return { [`${at}.title`]: ['지어낸 제목'] };
    if (typeof node.requirement !== 'string' || points(node.requirement) > 2000)
      return { [`${at}.requirement`]: ['지어낸 요구'] };
    depthOf.set(node.key, node.depth);
    if (typeof parent === 'string') parents.add(parent);
  }
  const leaves = [...depthOf.keys()].filter((key) => !parents.has(key));
  if (leaves.length > 150) return { nodes: ['지어낸 잎 수'] };
  return null;
}

/** 잎 key → 제목 경로 + 요구(차이 셈). */
function leafDigests(nodes: readonly OutlineNode[]): Map<string, string> {
  const paths = new Map<string, string[]>();
  const parents = new Set(nodes.map((node) => node.parentKey));
  const out = new Map<string, string>();
  for (const node of nodes) {
    const path = [
      ...(node.parentKey ? paths.get(node.parentKey)! : []),
      node.title,
    ];
    paths.set(node.key, path);
    if (!parents.has(node.key))
      out.set(node.key, JSON.stringify([path, node.requirement]));
  }
  return out;
}

export function fakeDraftingServer({
  baseUrl = 'http://test.local/api',
  projects = [],
  company,
  aiUnusable = false,
  noText = false,
  textUnknown = false,
  pageCount = 3,
  pdfs = {},
}: FakeDraftingServerOptions = {}) {
  const calls: FakeDraftingCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const stored = projects.map((project) => ({
    id: project.id,
    name: project.name,
    year: project.year,
    createdAt: NOW,
    documentId: null as number | null,
    outline: null as {
      outlineId: number;
      revision: number;
      nodes: OutlineNode[];
    } | null,
  }));
  const documents = new Map<number, FakeDocument>();
  const runs = new Map<number, FakeRun>();
  const results = new Map<number, ResultWire>();
  const keys = new Map<string, { body: string; runId: number }>();
  const uploads: { url: string; method: string; file: File }[] = [];
  let nextProject = Math.max(0, ...stored.map((p) => p.id)) + 1;
  let nextDocument = 101;
  let nextOutline = 201;
  let nextRun = 301;

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) =>
    /^\/(drafting|documents|runs)(\/|$)/.test(pathOf(request));

  const findProject = (id: number | null) =>
    id === null ? undefined : stored.find((p) => p.id === id);

  const runItemOf = (run: FakeRun): RunItem => {
    const result = results.get(run.id);
    const base = run.options.base as
      { runId: number; rebuild: string[] } | undefined;
    const running = run.steps.find((step) => step.status === 'running');
    const leaves =
      run.status === 'done' && result ?
        {
          total: result.leaves.length,
          drafted: result.leaves.filter((l) => l.outcome.status === 'done')
            .length,
          noMaterial: result.leaves.filter(
            (l) => l.outcome.status === 'no_material',
          ).length,
          failed: result.leaves.filter((l) => l.outcome.status === 'failed')
            .length,
          notRun: result.leaves.filter((l) => l.outcome.status === 'not_run')
            .length,
        }
      : null;
    return {
      id: run.id,
      status: run.status,
      createdAt: run.createdAt,
      finishedAt: run.finishedAt,
      outlineId: run.outlineId,
      baseRunId: base?.runId ?? null,
      rebuild: base?.rebuild ?? [],
      progress:
        run.status === 'processing' && running ?
          { step: running.step, done: running.done, total: running.total }
        : null,
      rejected:
        run.status === 'done' && result ?
          result.status.status === 'rejected'
        : null,
      leaves,
    };
  };

  const latestOf = (projectId: number) => {
    const mine = [...runs.values()].filter(
      (run) => run.projectId === projectId,
    );
    const last = mine.sort((a, b) => b.id - a.id)[0];
    return last ? runItemOf(last) : null;
  };

  const projectOut = (project: (typeof stored)[number]): ProjectWire => ({
    id: project.id,
    name: project.name,
    year: project.year,
    createdAt: project.createdAt,
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
          outline: { nodes: structuredClone(project.outline.nodes) },
        },
    latestRun: latestOf(project.id),
  });

  const documentOut = (doc: FakeDocument) => ({
    id: doc.id,
    fileName: doc.fileName,
    sizeBytes: doc.sizeBytes,
    status: doc.uploaded ? 'uploaded' : 'awaiting_upload',
    pageCount: doc.pageCount,
    hasText: doc.hasText,
    reportYear: null,
    previousDocumentId: null,
    etag: null,
    createdAt: NOW,
    uploadedAt: doc.uploaded ? NOW : null,
  });

  const runOut = (run: FakeRun) => ({
    id: run.id,
    module: 'drafting',
    flowId: 'drafting.bullets@3',
    documentId: null,
    options: structuredClone(run.options),
    status: run.status,
    steps: structuredClone(run.steps),
    errorCode: run.status === 'failed' ? 'DRAFT_FAILED' : null,
    errorMessage: run.status === 'failed' ? '지어낸-서버글-실패' : null,
    failedStep: null,
    files: [],
    resultShapes: [],
    resumedFromRunId: null,
    createdAt: run.createdAt,
    startedAt: null,
    finishedAt: run.finishedAt,
  });

  /** 옵션 검사(options@2) → 문제면 true. */
  const badOptions = (options: unknown): boolean => {
    if (typeof options !== 'object' || options === null) return true;
    const { projectId, base, ...rest } = options as Record<string, unknown>;
    if (Object.keys(rest).length > 0 || !isInt(projectId)) return true;
    const project = findProject(projectId);
    if (!project || project.documentId === null || project.outline === null)
      return true;
    if (base === undefined) return false;
    if (typeof base !== 'object' || base === null) return true;
    const { runId, rebuild, ...more } = base as Record<string, unknown>;
    if (
      Object.keys(more).length > 0 ||
      !isInt(runId) ||
      !Array.isArray(rebuild)
    )
      return true;
    const prior = runs.get(runId);
    if (!prior || prior.projectId !== projectId || prior.status !== 'done')
      return true;
    return !rebuild.every((key) => typeof key === 'string' && KEY.test(key));
  };

  const answer = (
    request: Request,
    path: string,
    url: URL,
    body: unknown,
  ): Response => {
    const key = `${request.method} ${path}`;
    const parts = path.split('/');
    if (company && parts[1] === 'drafting') return refusal(400, company);

    if (key === 'GET /drafting/projects') {
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const rows = [...stored]
        .sort((a, b) => b.id - a.id)
        .map((project) => ({
          id: project.id,
          name: project.name,
          year: project.year,
          createdAt: project.createdAt,
          hasDocument: project.documentId !== null,
          documentName:
            project.documentId === null ?
              null
            : (documents.get(project.documentId)?.fileName ?? null),
          outlineId: project.outline?.outlineId ?? null,
          outlineRevision: project.outline?.revision ?? null,
          latestRun: latestOf(project.id),
        }));
      return json(200, {
        count: rows.length,
        isNext: offset + limit < rows.length,
        results: rows.slice(offset, offset + limit),
      });
    }
    if (key === 'POST /drafting/projects') {
      const { year, name } = (body ?? {}) as { year?: unknown; name?: unknown };
      if (!isInt(year) || year < 2000 || year > 2100)
        return refusal(422, 'VALIDATION_ERROR', { year: ['지어낸 연도'] });
      const text = typeof name === 'string' ? name.trim() : '';
      if (points(text) < 1 || points(text) > 80)
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 이름'] });
      const project = {
        id: nextProject++,
        name: text,
        year,
        createdAt: NOW,
        documentId: null,
        outline: null,
      };
      stored.push(project);
      return json(201, { ...projectOut(project), latestRun: null });
    }
    if (parts[1] === 'drafting' && parts[2] === 'projects') {
      const project = findProject(pathId(parts[3]));
      if (!project) return refusal(404, 'NOT_FOUND');
      const rest = parts.slice(4).join('/');
      if (request.method === 'GET' && rest === '')
        return json(200, projectOut(project));
      if (request.method === 'PUT' && rest === 'document') {
        const { documentId } = (body ?? {}) as { documentId?: unknown };
        const doc = isInt(documentId) ? documents.get(documentId) : undefined;
        if (!doc || !doc.confirmed) return refusal(404, 'NOT_FOUND');
        if (doc.hasText === false)
          return refusal(422, 'DOCUMENT_NO_TEXT_LAYER');
        project.documentId = doc.id;
        return json(200, projectOut(project));
      }
      if (request.method === 'PUT' && rest === 'outline') {
        const nodes = (body as { nodes?: unknown } | undefined)?.nodes;
        const problems = outlineProblems(nodes);
        if (problems) return refusal(422, 'VALIDATION_ERROR', problems);
        const clean = (nodes as OutlineNode[]).map((node) => ({
          ...node,
          title: node.title.trim(),
        }));
        project.outline = {
          outlineId: nextOutline++,
          revision: (project.outline?.revision ?? 0) + 1,
          nodes: clean,
        };
        return json(200, {
          outlineId: project.outline.outlineId,
          revision: project.outline.revision,
          sha256: 'b'.repeat(64),
        });
      }
      if (request.method === 'GET' && rest === 'outline/changes') {
        const base = runs.get(
          pathId(url.searchParams.get('baseRunId') ?? '') ?? 0,
        );
        if (!base || base.projectId !== project.id || !project.outline)
          return refusal(404, 'NOT_FOUND');
        const before = leafDigests(base.outlineNodes);
        const now = leafDigests(project.outline.nodes);
        return json(200, {
          baseRunId: base.id,
          baseOutlineId: base.outlineId,
          outlineId: project.outline.outlineId,
          document: base.documentId === project.documentId ? 'same' : 'changed',
          leaves: [...now].map(([leaf, digest]) => ({
            key: leaf,
            change:
              !before.has(leaf) ? 'added'
              : before.get(leaf) === digest ? 'same'
              : 'changed',
          })),
          removed: [...before.keys()].filter((leaf) => !now.has(leaf)),
        });
      }
      if (request.method === 'GET' && rest === 'runs') {
        const mine = [...runs.values()]
          .filter((run) => run.projectId === project.id)
          .sort((a, b) => b.id - a.id)
          .map(runItemOf);
        return json(200, { count: mine.length, isNext: false, results: mine });
      }
    }
    if (parts[1] === 'drafting' && parts[2] === 'runs') {
      const run = runs.get(pathId(parts[3]) ?? 0);
      if (!run) return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
      const result = results.get(run.id);
      if (!result) return refusal(404, 'NOT_FOUND');
      if (parts[4] === 'result') return json(200, result);
      if (parts[4] === 'result.docx')
        return new Response(new Uint8Array([80, 75, 3, 4]), {
          status: 200,
          headers: {
            'Content-Type':
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent('지어낸 초안')}.docx`,
          },
        });
    }
    if (key === 'POST /documents') {
      const { fileName, sizeBytes } = (body ?? {}) as Record<string, unknown>;
      if (typeof fileName !== 'string' || !isInt(sizeBytes))
        return refusal(422, 'VALIDATION_ERROR', { fileName: ['지어낸'] });
      const doc: FakeDocument = {
        id: nextDocument++,
        fileName,
        sizeBytes,
        uploaded: false,
        confirmed: false,
        pageCount: null,
        hasText: null,
      };
      documents.set(doc.id, doc);
      return json(201, {
        document: documentOut(doc),
        upload: {
          url: `${STORAGE}/upload/${doc.id}?signature=지어낸`,
          method: 'PUT',
          expiresInSeconds: 600,
        },
      });
    }
    if (parts[1] === 'documents') {
      const doc = documents.get(pathId(parts[2]) ?? 0);
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (request.method === 'POST' && parts[3] === 'confirm') {
        if (!doc.uploaded) return refusal(409, 'UPLOAD_NOT_FOUND');
        doc.confirmed = true;
        doc.pageCount = pageCount;
        doc.hasText = textUnknown ? null : !noText;
        return json(200, { document: documentOut(doc), jobs: [] });
      }
      if (request.method === 'GET' && parts[3] === undefined)
        return json(200, { document: documentOut(doc), jobs: [] });
      if (request.method === 'GET' && parts[3] === 'file') {
        const bytes = pdfs[doc.id];
        if (!bytes) return refusal(404, 'NOT_FOUND');
        return new Response(bytes, {
          status: 200,
          headers: {
            'Content-Type': 'application/pdf',
            // 머리글은 ISO-8859-1 만 — 한글 이름은 RFC 5987 꼴로(result.docx 와 같게).
            'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(doc.fileName)}`,
          },
        });
      }
    }
    if (key === 'POST /runs') {
      const idem = request.headers.get('Idempotency-Key');
      if (!idem) return refusal(400, 'VALIDATION_ERROR');
      const text = JSON.stringify(body);
      const held = keys.get(idem);
      if (held) {
        if (held.body !== text) return refusal(409, 'IDEMPOTENCY_KEY_REUSED');
        const heldRun = runs.get(held.runId)!;
        return json(201, { id: heldRun.id, status: heldRun.status });
      }
      const { module, options } = (body ?? {}) as Record<string, unknown>;
      if (module !== 'drafting') return refusal(400, 'INVALID_OPTIONS');
      if (badOptions(options)) return refusal(400, 'INVALID_OPTIONS');
      if (aiUnusable) return refusal(409, 'AI_SETTING_UNUSABLE');
      const project = findProject(
        (options as { projectId: number }).projectId,
      )!;
      const run: FakeRun = {
        id: nextRun++,
        projectId: project.id,
        status: 'queued',
        steps: STEPS.map((step) => ({
          step,
          status: 'pending',
          done: null,
          total: null,
        })),
        options: structuredClone(options as Record<string, unknown>),
        outlineId: project.outline!.outlineId,
        documentId: project.documentId!,
        outlineNodes: structuredClone(project.outline!.nodes),
        createdAt: NOW,
        finishedAt: null,
      };
      runs.set(run.id, run);
      keys.set(idem, { body: text, runId: run.id });
      return json(201, { id: run.id, status: run.status });
    }
    if (request.method === 'GET' && parts[1] === 'runs') {
      const run = runs.get(pathId(parts[2]) ?? 0);
      if (!run) return refusal(404, 'NOT_FOUND');
      return json(200, runOut(run));
    }
    return refusal(404, 'NOT_FOUND');
  };

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    const key = `${request.method} ${path}`;
    const text = await request.clone().text();
    const body: unknown = text === '' ? undefined : JSON.parse(text);
    calls.push({
      method: request.method,
      path,
      query: url.searchParams,
      body,
      headers: request.headers,
    });
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(request, path, url, body);
  };

  /** 서명 PUT 흉내(sendUpload 자리) — 그 문서를 올림으로 표시한다. */
  const sendUpload = async (url: string, method: string, file: File) => {
    uploads.push({ url, method, file });
    const id = /\/upload\/(\d+)\?/.exec(url)?.[1];
    const doc = id ? documents.get(Number(id)) : undefined;
    if (!doc || method !== 'PUT') throw new Error('upload failed');
    doc.uploaded = true;
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  const bodies = (key: string) =>
    calls
      .filter((call) => `${call.method} ${call.path}` === key)
      .map((call) => call.body);

  /** 문서 하나를 올리고 확인까지 한 꼴로 심는다(문서 id). */
  const seedDocument = (fileName = '지어낸 전년도 보고서.pdf') => {
    const doc: FakeDocument = {
      id: nextDocument++,
      fileName,
      sizeBytes: 1024,
      uploaded: true,
      confirmed: true,
      pageCount,
      hasText: true,
    };
    documents.set(doc.id, doc);
    return doc.id;
  };

  return {
    send,
    handles,
    sendUpload,
    uploads,
    calls,
    count,
    bodies,
    override,
    results,
    seedDocument,
    /** 프로젝트에 문서·목차를 곧바로 심는다(검사 없음). */
    seedProject(
      projectId: number,
      { documentId, nodes }: { documentId?: number; nodes?: OutlineNode[] },
    ) {
      const project = findProject(projectId)!;
      if (documentId !== undefined) project.documentId = documentId;
      if (nodes)
        project.outline = {
          outlineId: nextOutline++,
          revision: (project.outline?.revision ?? 0) + 1,
          nodes: structuredClone(nodes),
        };
    },
    /** 실행을 옮긴다(상태·단계). done·failed 면 끝난 때를 채운다. */
    runPatch(runId: number, patch: { status?: RunStatus; steps?: RunStep[] }) {
      const run = runs.get(runId)!;
      Object.assign(run, structuredClone(patch));
      if (run.status === 'done' || run.status === 'failed')
        run.finishedAt = NOW;
    },
    runs: () => [...runs.values()].map((run) => structuredClone(run)),
    project: (id: number) => {
      const project = findProject(id);
      return project ? projectOut(project) : null;
    },
  };
}

/** 그 실행의 결과(@3 줄 위 꼴)를 짓는다 — 프로젝트·목차 판·문서는 그 실행 것, 쪽은 595×842 pt 로 pageCount 만큼. 시험이 server.results 에 심는다. */
export function fakeResult(
  server: ReturnType<typeof fakeDraftingServer>,
  runId: number,
  {
    leaves = [],
    pageCount = 3,
    ...patch
  }: Partial<Omit<ResultWire, 'leaves'>> & {
    leaves?: ResultWire['leaves'];
    pageCount?: number;
  } = {},
): ResultWire {
  const run = server.runs().find((one) => one.id === runId)!;
  return {
    schemaVersion: 'drafting.bullets@3',
    projectId: run.projectId,
    outlineId: run.outlineId,
    outlineSha256: 'c'.repeat(64),
    base: null,
    status: { status: 'done' },
    document: {
      documentId: run.documentId,
      fileName: '지어낸 보고서.pdf',
      pageCount,
      textPages: pageCount,
      pages: Array.from({ length: pageCount }, (_, at) => ({
        page: at + 1,
        width: 595,
        height: 842,
      })),
    },
    leaves,
    mapping: { failedBatches: [] },
    warnings: [],
    ...patch,
  };
}

/** 가짜 서버 앞에 둔 실어댑터(시험이 진짜 createApi 로 잇는다 — 온실가스 portsOf 꼴). */
export function storeOf(
  server: ReturnType<typeof fakeDraftingServer>,
  {
    baseUrl = 'http://test.local/api',
    newKey,
    newLaunchKey,
    pendingRuns = new Map(),
  }: {
    baseUrl?: string;
    newKey?: NewKey;
    newLaunchKey?: NewKey;
    pendingRuns?: PendingRuns;
  } = {},
) {
  const api = createApi({ baseUrl, fetch: server.send });
  return createDraftingStore({
    api,
    sendUpload: server.sendUpload,
    pendingRuns,
    ...(newKey ? { newKey } : {}),
    ...(newLaunchKey ? { newLaunchKey } : {}),
  });
}

/** 거울 ⊆ 판정: 거울에 있는데 openapi 꼴에 없는 「꼴.칸」. 꼴이 칸을 더해도 빈 목록(온실가스 mirrorGaps 를 옮겨 적음). */
export function mirrorGaps(
  mirrored: Readonly<Record<string, readonly string[]>>,
  schemas: Readonly<Record<string, { properties?: Record<string, unknown> }>>,
): string[] {
  const gaps: string[] = [];
  for (const [name, fields] of Object.entries(mirrored)) {
    const schema = schemas[name];
    if (!schema?.properties) {
      gaps.push(name);
      continue;
    }
    for (const field of fields)
      if (!(field in schema.properties)) gaps.push(`${name}.${field}`);
  }
  return gaps;
}
