// 시험용 가짜 그린워싱 서버(밴드 GW1R ①). 어댑터·화면·경로 시험이 같이 쓴다(공개 표면이 아니다 — 시험만 직접 가져온다).
// 답의 꼴은 api-py 의 경로(generated/api.d.ts)를 따른다. 값은 전부 지어낸 것이다. Bearer 는 보지 않는다(세션 가짜 서버의 몫).
//   - 거르지 않는다: 받은 요청을 calls 에 적고(method·path·query·body·headers), 서버 규칙대로 답한다. 시험은 요청과 화면으로 단언한다.
//   - 경로: POST /documents · POST /documents/{id}/confirm · GET /documents/{id} · POST /runs · GET /runs/{id} · GET /greenwash/checks ·
//     GET /greenwash/terms/default · GET /greenwash/runs/{id}/result · GET·PUT /greenwash/runs/{id}/review.
//   - 서명 PUT 은 같은 출처의 `/fake-upload/<문서 id>` 주소를 내주고, sendUpload(어댑터에 넣는 것)가 그 올림을 uploads 에 적는다.
//     confirm 은 올림이 없으면 409 NOT_UPLOADED, 크기가 다르면 409 UPLOAD_SIZE_MISMATCH. 올림 확인 전 문서로 POST /runs 는 409 DOCUMENT_NOT_UPLOADED.
//   - 옵션(greenwash.options@1)의 모르는 열쇠·parts 꼴 틀림은 400 INVALID_OPTIONS.
//   - POST /runs 의 머리 Idempotency-Key(밴드 GR2, 서버 IK1): 소문자 UUID 가 아니면 422 VALIDATION_ERROR. 본 열쇠·같은 본문이면 검사 앞에서
//     앞 실행을 201 로 돌려준다(새 실행 0), 본 열쇠·다른 본문은 409 IDEMPOTENCY_KEY_REUSED. 머리가 없으면 늘 새 실행.
//   - POST /runs 본문 launchKey(밴드 GP6, 서버 LK1 — 선택): 소문자 UUID 가 아니면 422 VALIDATION_ERROR(열쇠 다시 보냄 검사 뒤). 값은 적지 않는다.
//   - 검토 PUT 은 서버 규칙(actions/review.py): 없음 404 → done 아님 409 RUN_NOT_DONE → dry-run 409 NO_REVIEW → 확정됨 409 REVIEW_LOCKED,
//     marks 범위·차례 틀림 400 INVALID_REVIEW, 표시가 있으면 in_review, state confirmed 면 미검토를 adopted 로 채우고 confirmedAt·confirmedBy.
//   - PATCH /documents/{id}(밴드 GW2R ③): 본문은 reportYear·previousDocumentId 만(모르는 열쇠·둘 다 없음·1900~2100 밖 → 422 VALIDATION_ERROR),
//     없음 404, 올림 확인 전 409 NOT_UPLOADED. 받으면 문서 칸을 바꾸고 DocumentOut 을 돌려준다.
//   - GET /greenwash/runs/{id}/report?confirmed=(밴드 GW2R ③): 없음 404 → done 아님 409 RUN_NOT_DONE → dry-run 409 NO_REPORT →
//     confirmed=true 인데 확정 전 409 NOT_CONFIRMED. 받으면 지어낸 바이트(xlsx 종류) + Content-Disposition attachment(reportFileName).
//   - GET /documents/{id}/file(밴드 GR3): 없음 404 → 올림 확인 전 409 NOT_UPLOADED. 받으면 지어낸 바이트(FAKE_PDF_BYTES — 실제 PDF 아님) +
//     application/pdf + Content-Disposition attachment(filename*=UTF-8''<문서 이름>).
//   - 근거 고침·재판단(밴드 GRJ1 ③): 규칙은 mock/rejudgeRules.ts 한 벌(목 저장소와 같은 함수). PUT 의 evidence 검사 400 INVALID_REVIEW ·
//     POST /greenwash/runs/{id}/items/{i}/rejudge: 없음·문장 밖 404 → done 아님 409 RUN_NOT_DONE → dry-run 409 NO_REVIEW → 409 REVIEW_LOCKED ·
//     REJUDGE_RUNNING · NOTHING_TO_REJUDGE, 받으면 202 {rejudgeRunId}(9001 부터). 검토 GET REJUDGE_SETTLE_READS 번째에 끝난다.
//     고침 견줌·levelCounts 는 기준 판단과(서버 GRJ1 ②).
//   - checks 답은 처음부터 runs[].errorCode 를 싣는다(실패 줄만 값 — 검증 G1e 가 더하는 칸, 감독 판단 Q8).
// override 에 「메서드 경로」(id 는 숫자 그대로, 예 'GET /runs/12') → 답을 주면 그 경로는 그 답을 낸다(차례 목록도 된다. 끊김은 던지는 함수로).
// advance(runId, {status, steps, errorCode}) 로 실행 상태를 바꾼다. done 이 되면 결과(문장 셋)와 검토(pending)를 짓는다.
//   done·failed 가 되면 finishedAt 은 FAKE_FINISHED_AT(이미 있으면 그대로).
import { createApi } from '../../../shared/api/index.ts';
import { LEVELS } from '../model/index.ts';
import type { Level, ScanResult } from '../model/index.ts';
import type { ReviewEvidence, ReviewEvidenceIn } from '../model/index.ts';
import { IDEMPOTENCY_KEY_PATTERN } from './idempotency.ts';
import { MOCK_PART_NAMES, buildMockResult } from './mock/mockResults.ts';
import { checkedEditCells } from './mock/mockStore.ts';
import {
  basisCounts,
  basisItems as basisItemsOf,
  checkedEvidence,
  confirmRefusal,
  evidenceRefusal,
  nextEvidence,
  rejudgeLines,
  rejudgeRefusal,
  settleOnRead,
  startRejudge,
} from './mock/rejudgeRules.ts';
import type { MockRejudgeRun } from './mock/rejudgeRules.ts';
import { createGreenwashServerStore } from './server.ts';
import type { GreenwashServerDeps } from './server.ts';

/** 흉내 재판단의 끝남 견본을 고르는 글 머리(화면 시험이 이 문으로 가져간다 — layers). */
export { MOCK_FAIL_MARK, MOCK_NONRISK_MARK } from './mock/rejudgeRules.ts';

export interface FakeGreenwashCall {
  method: string;
  path: string;
  query: URLSearchParams;
  /** JSON 본문(없으면 undefined). */
  body: unknown;
  headers: Headers;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (status: number, code: string) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

export type FakeRunStatus = 'queued' | 'processing' | 'done' | 'failed';
export interface FakeStep {
  step: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  done: number | null;
  total: number | null;
}

export interface FakeUser {
  id: number;
  name: string;
}

export interface FakeDocument {
  id: number;
  fileName: string;
  sizeBytes: number;
  status: 'awaiting_upload' | 'uploaded';
  /** 서버가 아는 쪽 수(X1b-2a 뒤 — 모르면 null). */
  pageCount: number | null;
  hasText: boolean | null;
  reportYear: number | null;
  previousDocumentId: number | null;
  createdAt: string;
  uploadedAt: string | null;
  uploadedBy: FakeUser;
}

export interface FakeRun {
  id: number;
  documentId: number;
  module: string;
  status: FakeRunStatus;
  steps: FakeStep[];
  options: Record<string, unknown>;
  errorCode: string | null;
  createdAt: string;
  startedAt: string | null;
  /** 끝난 때(RunOut.finishedAt). advance 가 done·failed 로 바꿀 때 FINISHED 를 넣는다(밴드 GW2R ②). */
  finishedAt: string | null;
  createdByUserId: number;
  result: ScanResult | null;
  /** 검토 행. dry-run 이면 null(검토 GET·PUT 409 NO_REVIEW). */
  review: FakeReview | null;
  dryRun: boolean;
}

export interface FakeReview {
  state: 'pending' | 'in_review' | 'confirmed';
  marks: {
    itemIndex: number;
    decision: string;
    excludeReason: string | null;
  }[];
  confirmedAt: string | null;
  confirmedBy: FakeUser | null;
  /** review@2 의 고침(G1b-3). 없으면 []. */
  edits?: FakeReviewEdit[];
  /** review@3 의 근거 고침(GRJ1). 없으면 []. */
  evidence?: ReviewEvidence[];
  /** 재판단 실행(만든 차례, GRJ1). 없으면 []. */
  rejudges?: MockRejudgeRun[];
}

/** 고친 칸 하나(값·때·사람). */
export interface FakeEdited<T> {
  value: T;
  editedAt: string;
  editedBy: FakeUser;
}
export interface FakeReviewEdit {
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

/** 흐름 greenwash.colab@E0 의 단계 여섯(선언 차례). */
export const FAKE_STEP_NAMES = [
  'extract',
  'index',
  'judge',
  'wordcount',
  'locate',
  'report',
] as const;

/** 단계 여섯: 앞의 이름은 done, 그다음 하나는 주어진 상태, 나머지 pending. */
export function fakeSteps(
  doneUntil: number,
  at: Partial<FakeStep> & { status?: FakeStep['status'] } = {},
): FakeStep[] {
  return FAKE_STEP_NAMES.map((step, index) => {
    if (index < doneUntil)
      return { step, status: 'done', done: null, total: null };
    if (index === doneUntil && at.status)
      return {
        step,
        status: at.status,
        done: at.done ?? null,
        total: at.total ?? null,
      };
    return { step, status: 'pending', done: null, total: null };
  });
}

const ALL_DONE = () => fakeSteps(FAKE_STEP_NAMES.length);

/** 지어낸 결과(문장 셋 — High·Mid·Low). 점검 쪽의 앞 셋에 하나씩. */
export function fakeResult(
  fileName: string,
  pageCount: number,
  parts: { ceo: number[]; company: number[]; climate: number[] },
): ScanResult {
  const checked = [
    ...new Set([...parts.ceo, ...parts.company, ...parts.climate]),
  ].sort((a, b) => a - b);
  const pages = [0, 1, 2].map((i) => checked[i % checked.length] ?? 1);
  return buildMockResult({
    fileName,
    pageCount,
    parts: [
      { name: MOCK_PART_NAMES.ceo, pages: parts.ceo },
      { name: MOCK_PART_NAMES.company, pages: parts.company },
      { name: MOCK_PART_NAMES.climate, pages: parts.climate },
    ],
    items: pages.map((page, i) => ({
      page,
      level: LEVELS[i]!,
      sentence: `[지어낸 ${i + 1}] ${page}쪽의 환경 주장 문장이에요.`,
      riskTags: ['근거 부족'],
      evidencePages: [page],
      position: null,
    })),
    defaultTerms: ['친환경'],
    wordPages: {},
  });
}

const KNOWN_OPTION_KEYS = new Set(['parts', 'extraTerms']);
const isPageList = (value: unknown) =>
  Array.isArray(value) &&
  value.every(
    (page) =>
      Number.isInteger(page) &&
      (page as number) >= 1 &&
      (page as number) <= 300,
  );

/** greenwash.options@1 검사(서버 끼움 check_options 의 꼴 부분). 틀리면 글. */
function optionsProblem(options: unknown): string | null {
  if (typeof options !== 'object' || options === null || Array.isArray(options))
    return 'options 가 객체가 아님';
  const keys = Object.keys(options);
  const unknown = keys.find((key) => !KNOWN_OPTION_KEYS.has(key));
  if (unknown) return `모르는 열쇠 ${unknown}`;
  const parts = (options as { parts?: unknown }).parts;
  if (typeof parts !== 'object' || parts === null) return 'parts 없음';
  const p = parts as Record<string, unknown>;
  if (
    Object.keys(p).some(
      (key) => !['ceo', 'company', 'climate'].includes(key),
    ) ||
    !isPageList(p.ceo) ||
    !isPageList(p.company) ||
    !isPageList(p.climate)
  )
    return 'parts 꼴';
  const extra = (options as { extraTerms?: unknown }).extraTerms;
  if (
    extra !== undefined &&
    !(Array.isArray(extra) && extra.every((term) => typeof term === 'string'))
  )
    return 'extraTerms 꼴';
  return null;
}

export interface FakeGreenwashServerOptions {
  baseUrl?: string;
  /** 지금 사용자(checks 의 currentUserId, 확정의 confirmedBy). */
  currentUser?: FakeUser;
  companyName?: string;
  documents?: FakeDocument[];
  runs?: FakeRun[];
  defaultTerms?: string[];
  /** 새 문서·새 실행의 id 시작(기본 12 — 문서 12·실행 13 이 처음 만든 것). */
  nextDocumentId?: number;
  nextRunId?: number;
  /** 새로 만든 문서의 서버 쪽 수·글자 층(기본 null — X1b-2a 전 꼴). */
  serverPageCount?: number | null;
  serverHasText?: boolean | null;
  /** report 답의 Content-Disposition 값(기본 「attachment; filename="지어낸 보고서 <id>.xlsx"; filename*=UTF-8''…」). null 이면 머리 없음. */
  reportDisposition?: ((runId: number, confirmed: boolean) => string) | null;
}

/** report 답의 바이트(지어낸 — 실제 xlsx 가 아니다). */
export const FAKE_REPORT_BYTES = new Uint8Array([80, 75, 3, 4, 1, 2, 3]);
/** 문서 원본 답의 바이트(지어낸 — 「%PDF-」 머리만, 실제 PDF 가 아니다. 밴드 GR3). */
export const FAKE_PDF_BYTES = new Uint8Array([37, 80, 68, 70, 45, 49, 46, 55]);

const NOW = '2026-10-19T10:00:00+09:00';
/** 가짜가 끝낸 실행의 끝난 때(한국 시각 10:52). */
export const FAKE_FINISHED_AT = '2026-10-19T10:52:00+09:00';

export function fakeGreenwashServer({
  baseUrl = 'http://test.local/api',
  currentUser = { id: 7, name: '담당자 가' },
  companyName = '지어낸 회사',
  documents = [],
  runs = [],
  defaultTerms = ['친환경', '탄소중립'],
  nextDocumentId = 12,
  nextRunId = 13,
  serverPageCount = null,
  serverHasText = null,
  reportDisposition = (runId, confirmed) => {
    const name = `지어낸 보고서 ${runId}${confirmed ? ' 확정본' : ''}.xlsx`;
    return `attachment; filename="report-${runId}.xlsx"; filename*=UTF-8''${encodeURIComponent(name)}`;
  },
}: FakeGreenwashServerOptions = {}) {
  const calls: FakeGreenwashCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const docs = new Map(documents.map((doc) => [doc.id, { ...doc }]));
  const runMap = new Map(runs.map((run) => [run.id, { ...run }]));
  /** 서명 주소로 올린 것: 문서 id → 크기. */
  const uploaded = new Map<number, number>();
  /** sendUpload 가 받은 것(어댑터 시험의 단언). */
  const uploads: { url: string; method: string; size: number }[] = [];
  let documentSeq = nextDocumentId;
  let runSeq = nextRunId;
  /** POST /runs 열쇠 → 만든 실행 id·본문(JSON 글자). */
  const runKeys = new Map<string, { id: number; body: string }>();

  const basePath = new URL(baseUrl).pathname;
  const pathOf = (url: URL) => url.pathname.slice(basePath.length);

  const documentOut = (doc: FakeDocument) => ({
    id: doc.id,
    fileName: doc.fileName,
    sizeBytes: doc.sizeBytes,
    status: doc.status,
    pageCount: doc.pageCount,
    hasText: doc.hasText,
    reportYear: doc.reportYear,
    previousDocumentId: doc.previousDocumentId,
    etag: doc.status === 'uploaded' ? '"지어낸"' : null,
    createdAt: doc.createdAt,
    uploadedAt: doc.uploadedAt,
  });

  const runOut = (run: FakeRun) => ({
    id: run.id,
    documentId: run.documentId,
    module: run.module,
    flowId: 'greenwash.colab@E0',
    status: run.status,
    steps: run.steps,
    options: run.options,
    errorCode: run.errorCode,
    errorMessage: run.errorCode === null ? null : '지어낸 실패 글',
    failedStep:
      run.steps.find((step) => step.status === 'failed')?.step ?? null,
    files: [],
    resultShapes: ['greenwash.result@1'],
    resumedFromRunId: null,
    createdAt: run.createdAt,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
  });

  const reviewOut = (run: FakeRun) => ({
    schemaVersion: 'greenwash.review@3',
    evidence: structuredClone(run.review!.evidence ?? []),
    rejudges: rejudgeLines(run.review!.rejudges ?? []),
    runId: run.id,
    state: run.review!.state,
    confirmedAt: run.review!.confirmedAt,
    confirmedBy: run.review!.confirmedBy,
    marks: run.review!.marks.map((mark) => ({ ...mark })),
    edits: structuredClone(run.review!.edits ?? []),
  });

  /** PUT 의 평평한 고침 → 서버 규칙 흉내(strip·빈 줄 버림·AI 와 같은 칸 null·칸마다 값이 바뀐 PUT 에서만 때·사람).
   *  범위 밖·겹친 itemIndex·칸 검사(목 저장소 checkedEditCells 한 벌 — 다듬기·견줌·상한·그물, 밴드 GMK1) 거절은 null(→ 400). */
  const nextEdits = (
    items: ScanResult['items'],
    before: readonly FakeReviewEdit[],
    wanted: readonly FakeEditIn[],
  ): FakeReviewEdit[] | null => {
    const old = new Map(before.map((e) => [e.itemIndex, e]));
    const seen = new Set<number>();
    const out: FakeReviewEdit[] = [];
    const same = (a: unknown, b: unknown) =>
      JSON.stringify(a) === JSON.stringify(b);
    const cell = <T>(
      value: T | null,
      prev: FakeEdited<T> | null | undefined,
    ): FakeEdited<T> | null => {
      if (value === null) return null;
      if (prev && same(prev.value, value)) return prev;
      return { value, editedAt: NOW, editedBy: { ...currentUser } };
    };
    for (const w of wanted) {
      const ai = items[w.itemIndex];
      if (!ai || seen.has(w.itemIndex)) return null;
      seen.add(w.itemIndex);
      const cells = checkedEditCells(w, ai);
      if (typeof cells === 'string') return null;
      const prev = old.get(w.itemIndex);
      const edit: FakeReviewEdit = {
        itemIndex: w.itemIndex,
        level: cell(w.level === ai.level ? null : w.level, prev?.level),
        reasonBullets: cell(cells.reasonBullets, prev?.reasonBullets),
        fixParagraph: cell(cells.fixParagraph, prev?.fixParagraph),
      };
      if (edit.level || edit.reasonBullets || edit.fixParagraph) out.push(edit);
    }
    return out.sort((a, b) => a.itemIndex - b.itemIndex);
  };

  /** 재판단 실행 id(지어낸 수 — 9001 부터). */
  let rejudgeSeq = 9000;

  const unionCount = (options: Record<string, unknown>) => {
    const parts = options.parts as Record<string, number[]>;
    return new Set([...parts.ceo!, ...parts.company!, ...parts.climate!]).size;
  };

  const checks = () => {
    const greenwash = [...runMap.values()].filter(
      (run) => run.module === 'greenwash',
    );
    const docIds = new Set(greenwash.map((run) => run.documentId));
    return {
      schemaVersion: 'greenwash.checks@1',
      currentUserId: currentUser.id,
      companyName,
      documents: [...docs.values()]
        .filter((doc) => docIds.has(doc.id))
        .map((doc) => ({
          documentId: doc.id,
          fileName: doc.fileName,
          reportYear: doc.reportYear,
          previousDocumentId: doc.previousDocumentId,
          pageCount: doc.pageCount,
          uploadedAt: doc.uploadedAt,
          uploadedBy: { userId: doc.uploadedBy.id, name: doc.uploadedBy.name },
        })),
      runs: greenwash.map((run) => ({
        runId: run.id,
        documentId: run.documentId,
        createdAt: run.createdAt,
        finishedAt:
          run.status === 'done' || run.status === 'failed' ?
            run.finishedAt
          : null,
        createdByUserId: run.createdByUserId,
        status: run.status,
        steps: run.steps,
        checkedPages: unionCount(run.options),
        errorCode: run.status === 'failed' ? run.errorCode : null,
        // 효력 등급(고친 등급 ?? AI) — 서버 checks levelCounts 와 같은 뜻(밴드 G1b-3 ②)
        // 고친 등급 ?? 기준 판단(리스크 아님은 세 칸 밖 — 서버 GRJ1 ②)
        levelCounts:
          run.result ?
            basisCounts(
              run.result.items,
              run.result.counts.byLevel,
              new Map(
                (run.review?.edits ?? []).flatMap((e) =>
                  e.level === null ?
                    []
                  : [[e.itemIndex, e.level.value as Level] as const],
                ),
              ),
              run.review?.rejudges ?? [],
            )
          : null,
        review:
          run.result && run.review ?
            {
              state: run.review.state,
              reviewed: run.review.marks.length,
              total: run.result.items.length,
              confirmedAt: run.review.confirmedAt,
              confirmedBy: run.review.confirmedBy,
            }
          : null,
      })),
    };
  };

  /** 실행을 끝낸다(done 이면 결과와 검토 pending 을 짓는다). */
  const advance = (
    runId: number,
    next: {
      status: FakeRunStatus;
      steps?: FakeStep[];
      errorCode?: string | null;
    },
  ) => {
    const run = runMap.get(runId);
    if (!run) throw new Error(`가짜에 없는 실행: ${runId}`);
    run.status = next.status;
    run.steps = next.steps ?? (next.status === 'done' ? ALL_DONE() : run.steps);
    run.errorCode = next.errorCode ?? null;
    run.finishedAt =
      next.status === 'done' || next.status === 'failed' ?
        (run.finishedAt ?? FAKE_FINISHED_AT)
      : null;
    if (next.status === 'done' && run.result === null) {
      const doc = docs.get(run.documentId)!;
      run.result = fakeResult(
        doc.fileName,
        doc.pageCount ?? 10,
        run.options.parts as {
          ceo: number[];
          company: number[];
          climate: number[];
        },
      );
      if (!run.dryRun)
        run.review = {
          state: 'pending',
          marks: [],
          confirmedAt: null,
          confirmedBy: null,
        };
    }
  };

  const putReview = (run: FakeRun, body: unknown): Response => {
    if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
    if (!run.review || !run.result) return refusal(409, 'NO_REVIEW');
    if (run.review.state === 'confirmed') return refusal(409, 'REVIEW_LOCKED');
    const { state, marks, edits, evidence } = (body ?? {}) as {
      state?: unknown;
      marks?: FakeReview['marks'];
      edits?: FakeEditIn[] | null;
      evidence?: ReviewEvidenceIn[] | null;
    };
    const count = run.result.items.length;
    if (
      !Array.isArray(marks) ||
      !marks.every(
        (mark, i) =>
          Number.isInteger(mark.itemIndex) &&
          mark.itemIndex >= 0 &&
          mark.itemIndex < count &&
          (i === 0 || mark.itemIndex > marks[i - 1]!.itemIndex),
      ) ||
      !(state === undefined || state === null || state === 'confirmed')
    )
      return refusal(400, 'INVALID_REVIEW');
    const nextEdit =
      edits == null ?
        (run.review.edits ?? [])
      : nextEdits(
          basisItemsOf(run.result.items, run.review.rejudges ?? []),
          run.review.edits ?? [],
          edits,
        );
    if (nextEdit === null) return refusal(400, 'INVALID_REVIEW');
    const checked =
      evidence == null ? null : (
        checkedEvidence(
          run.result.items,
          run.review.rejudges ?? [],
          run.result.source.pageCount,
          evidence,
        )
      );
    if (typeof checked === 'string') return refusal(400, 'INVALID_REVIEW');
    // 확정은 도는 재판단이 없을 때만(서버 review.py 규칙 8 — 검사 뒤·쓰기 앞)
    if (
      state === 'confirmed' &&
      confirmRefusal(run.review.rejudges ?? []) !== null
    )
      return refusal(409, 'REJUDGE_RUNNING');
    // 도는 문장의 근거는 바꾸지 않는다(서버 규칙 8 넓힘 — GRJ3)
    if (
      evidenceRefusal(
        run.review.rejudges ?? [],
        run.review.evidence ?? [],
        checked,
      ) !== null
    )
      return refusal(409, 'REJUDGE_RUNNING');
    const nextProof =
      checked === null ?
        (run.review.evidence ?? [])
      : nextEvidence(run.review.evidence ?? [], checked, {
          at: NOW,
          by: { ...currentUser },
        });
    const confirming = state === 'confirmed';
    const byIndex = new Map(marks.map((mark) => [mark.itemIndex, mark]));
    const touched =
      marks.length > 0 ||
      (edits != null && nextEdit.length > 0) ||
      (checked !== null && nextProof.length > 0);
    run.review = {
      edits: nextEdit,
      evidence: nextProof,
      rejudges: run.review.rejudges ?? [],
      state:
        confirming ? 'confirmed'
        : touched ? 'in_review'
        : run.review.state,
      marks: (confirming ?
        run.result.items.map(
          (_item, index) =>
            byIndex.get(index) ?? {
              itemIndex: index,
              decision: 'adopted',
              excludeReason: null,
            },
        )
      : marks
      ).map((mark) => ({ ...mark })),
      confirmedAt: confirming ? NOW : null,
      confirmedBy: confirming ? { ...currentUser } : null,
    };
    return json(200, reviewOut(run));
  };

  const answer = (
    method: string,
    path: string,
    body: unknown,
    query: URLSearchParams,
    headers: Headers,
  ): Response => {
    const key = `${method} ${path}`;
    if (key === 'POST /documents') {
      const { fileName, sizeBytes } = (body ?? {}) as {
        fileName?: unknown;
        sizeBytes?: unknown;
      };
      if (typeof fileName !== 'string' || typeof sizeBytes !== 'number')
        return refusal(422, 'VALIDATION_ERROR');
      const id = documentSeq++;
      const doc: FakeDocument = {
        id,
        fileName,
        sizeBytes,
        status: 'awaiting_upload',
        pageCount: null,
        hasText: null,
        reportYear: null,
        previousDocumentId: null,
        createdAt: NOW,
        uploadedAt: null,
        uploadedBy: currentUser,
      };
      docs.set(id, doc);
      return json(201, {
        document: documentOut(doc),
        upload: {
          url: `${new URL(baseUrl).origin}/fake-upload/${id}`,
          method: 'PUT',
          expiresInSeconds: 900,
        },
      });
    }
    let match = /^\/documents\/(\d+)\/confirm$/.exec(path);
    if (match && method === 'POST') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      const size = uploaded.get(doc.id);
      if (size === undefined) return refusal(409, 'NOT_UPLOADED');
      if (size !== doc.sizeBytes) return refusal(409, 'UPLOAD_SIZE_MISMATCH');
      doc.status = 'uploaded';
      doc.uploadedAt = NOW;
      doc.pageCount = serverPageCount;
      doc.hasText = serverHasText;
      return json(200, { document: documentOut(doc), jobs: [] });
    }
    match = /^\/documents\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      return json(200, { document: documentOut(doc), jobs: [] });
    }
    match = /^\/documents\/(\d+)\/file$/.exec(path);
    if (match && method === 'GET') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (doc.status !== 'uploaded') return refusal(409, 'NOT_UPLOADED');
      return new Response(FAKE_PDF_BYTES.slice(), {
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(doc.fileName)}`,
        },
      });
    }
    match = /^\/documents\/(\d+)$/.exec(path);
    if (match && method === 'PATCH') {
      const patch = (body ?? {}) as Record<string, unknown>;
      const keys = Object.keys(patch);
      const year = patch.reportYear;
      if (
        keys.length === 0 ||
        keys.some((k) => k !== 'reportYear' && k !== 'previousDocumentId') ||
        (year !== undefined &&
          year !== null &&
          !(
            Number.isInteger(year) &&
            (year as number) >= 1900 &&
            (year as number) <= 2100
          ))
      )
        return refusal(422, 'VALIDATION_ERROR');
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (doc.status !== 'uploaded') return refusal(409, 'NOT_UPLOADED');
      if ('reportYear' in patch) doc.reportYear = year as number | null;
      if ('previousDocumentId' in patch)
        doc.previousDocumentId = patch.previousDocumentId as number | null;
      return json(200, documentOut(doc));
    }
    if (key === 'POST /runs') {
      const runKey = headers.get('Idempotency-Key');
      if (runKey !== null && !IDEMPOTENCY_KEY_PATTERN.test(runKey))
        return refusal(422, 'VALIDATION_ERROR');
      const seen = runKey === null ? undefined : runKeys.get(runKey);
      if (seen !== undefined)
        return seen.body === JSON.stringify(body) ?
            json(201, { id: seen.id, status: runMap.get(seen.id)!.status })
          : refusal(409, 'IDEMPOTENCY_KEY_REUSED');
      const { module, documentId, launchKey, options } = (body ?? {}) as {
        module?: unknown;
        documentId?: unknown;
        launchKey?: unknown;
        options?: unknown;
      };
      if (
        launchKey !== undefined &&
        !(
          typeof launchKey === 'string' &&
          IDEMPOTENCY_KEY_PATTERN.test(launchKey)
        )
      )
        return refusal(422, 'VALIDATION_ERROR');
      if (module !== 'greenwash') return refusal(422, 'UNKNOWN_FLOW');
      const doc = docs.get(documentId as number);
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (doc.status !== 'uploaded')
        return refusal(409, 'DOCUMENT_NOT_UPLOADED');
      if (optionsProblem(options) !== null)
        return refusal(400, 'INVALID_OPTIONS');
      const id = runSeq++;
      runMap.set(id, {
        id,
        documentId: doc.id,
        module: 'greenwash',
        status: 'queued',
        steps: fakeSteps(0),
        options: options as Record<string, unknown>,
        errorCode: null,
        createdAt: NOW,
        startedAt: null,
        finishedAt: null,
        createdByUserId: currentUser.id,
        result: null,
        review: null,
        dryRun: false,
      });
      if (runKey !== null)
        runKeys.set(runKey, { id, body: JSON.stringify(body) });
      return json(201, { id, status: 'queued' });
    }
    match = /^\/runs\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(404, 'NOT_FOUND');
      return json(200, runOut(run));
    }
    if (key === 'GET /greenwash/checks') return json(200, checks());
    if (key === 'GET /greenwash/terms/default')
      return json(200, { terms: defaultTerms });
    match = /^\/greenwash\/runs\/(\d+)\/report$/.exec(path);
    if (match && method === 'GET') {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'greenwash') return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done' || !run.result)
        return refusal(409, 'RUN_NOT_DONE');
      if (run.dryRun) return refusal(409, 'NO_REPORT');
      const confirmed = query.get('confirmed') === 'true';
      if (confirmed && run.review?.state !== 'confirmed')
        return refusal(409, 'NOT_CONFIRMED');
      const headers = new Headers({
        'Content-Type':
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      if (reportDisposition !== null)
        headers.set(
          'Content-Disposition',
          reportDisposition(run.id, confirmed),
        );
      return new Response(FAKE_REPORT_BYTES.slice(), { status: 200, headers });
    }
    match = /^\/greenwash\/runs\/(\d+)\/items\/(\d+)\/rejudge$/.exec(path);
    if (match && method === 'POST') {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'greenwash') return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done' || !run.result)
        return refusal(409, 'RUN_NOT_DONE');
      if (!run.review) return refusal(409, 'NO_REVIEW');
      const itemIndex = Number(match[2]);
      if (itemIndex >= run.result.items.length)
        return refusal(404, 'NOT_FOUND');
      const rejudges = (run.review.rejudges ??= []);
      const refused = rejudgeRefusal({
        confirmed: run.review.state === 'confirmed',
        items: run.result.items,
        runs: rejudges,
        evidence: run.review.evidence ?? [],
        itemIndex,
      });
      if (refused !== null) return refusal(409, refused.toUpperCase());
      rejudgeSeq += 1;
      rejudges.push(
        startRejudge(rejudgeSeq, itemIndex, run.review.evidence ?? []),
      );
      return json(202, { rejudgeRunId: rejudgeSeq });
    }
    match = /^\/greenwash\/runs\/(\d+)\/(result|review)$/.exec(path);
    if (match) {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'greenwash') return refusal(404, 'NOT_FOUND');
      if (match[2] === 'result' && method === 'GET') {
        if (run.status !== 'done' || !run.result)
          return refusal(409, 'RUN_NOT_DONE');
        return json(200, run.result);
      }
      if (match[2] === 'review' && method === 'GET') {
        if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
        if (!run.review) return refusal(409, 'NO_REVIEW');
        const rejudges = (run.review.rejudges ??= []);
        run.review.evidence = settleOnRead(
          run.result!.items,
          rejudges,
          run.review.evidence ?? [],
          { at: NOW, by: { ...currentUser } },
        );
        return json(200, reviewOut(run));
      }
      if (match[2] === 'review' && method === 'PUT')
        return putReview(run, body);
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) => {
    const url = new URL(request.url);
    if (!url.pathname.startsWith(basePath)) return false;
    return /^\/(documents|runs|greenwash)(\/|$)/.test(pathOf(url));
  };

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(url);
    const text = await request.clone().text();
    const body: unknown = text === '' ? undefined : JSON.parse(text);
    calls.push({
      method: request.method,
      path,
      query: url.searchParams,
      body,
      headers: new Headers(request.headers),
    });
    const key = `${request.method} ${path}`;
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(
      request.method,
      path,
      body,
      url.searchParams,
      new Headers(request.headers),
    );
  };

  /** 어댑터에 넣는 서명 PUT(같은 출처 /fake-upload/<id>). 받은 것을 uploads 에 적는다. */
  const sendUpload = async (url: string, method: string, file: File) => {
    uploads.push({ url, method, size: file.size });
    const match = /\/fake-upload\/(\d+)$/.exec(url);
    if (!match || method !== 'PUT')
      throw new Error('가짜 저장소가 모르는 올림');
    uploaded.set(Number(match[1]), file.size);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;

  return {
    send,
    handles,
    sendUpload,
    calls,
    uploads,
    count,
    override,
    advance,
    docs,
    runs: runMap,
  };
}

export type FakeGreenwashServer = ReturnType<typeof fakeGreenwashServer>;

/** 지어낸 문서 하나(올라온 것). */
export function fakeDocument(
  id: number,
  overrides: Partial<FakeDocument> = {},
): FakeDocument {
  return {
    id,
    fileName: `지어낸 보고서 ${id}.pdf`,
    sizeBytes: 1000 + id,
    status: 'uploaded',
    pageCount: 10,
    hasText: true,
    reportYear: null,
    previousDocumentId: null,
    createdAt: '2026-10-18T09:00:00+09:00',
    uploadedAt: '2026-10-18T09:00:05+09:00',
    uploadedBy: { id: 7, name: '담당자 가' },
    ...overrides,
  };
}

/** 지어낸 실행 하나(기본: 그 문서의 1~3쪽 기후·환경, queued). */
export function fakeRun(
  id: number,
  documentId: number,
  overrides: Partial<FakeRun> = {},
): FakeRun {
  return {
    id,
    documentId,
    module: 'greenwash',
    status: 'queued',
    steps: fakeSteps(0),
    options: { parts: { ceo: [], company: [], climate: [1, 2, 3] } },
    errorCode: null,
    createdAt: '2026-10-18T09:01:00+09:00',
    startedAt: null,
    finishedAt: null,
    createdByUserId: 7,
    result: null,
    review: null,
    dryRun: false,
    ...overrides,
  };
}

/** 목록 자료 조건(발주서 §3)의 확정자. */
export const FAKE_CONFIRMER: FakeUser = { id: 9, name: '확정자 가' };

/**
 * 목록(GW-01) 자료 조건 ①~⑥ 을 갖춘 가짜 서버: 올린 사람 둘(지금 7·다른 8), 확정 줄(confirmedBy 9 「확정자 가」),
 * processing 줄(extract done · index done · judge running 3/10 → 34%), failed 줄 둘(no_text_layer·step_error — 둘 다 extract 에서 멈춤),
 * 쪽 수 null 하나·숫자 하나, uploadedAt null 하나(방어). 문서 1~4, 실행 5~8(새로 만들면 문서 12·실행 13).
 */
export function listedGreenwashServer(
  options: FakeGreenwashServerOptions = {},
) {
  const other: FakeUser = { id: 8, name: '담당자 나' };
  const server = fakeGreenwashServer({
    documents: [
      fakeDocument(1, { fileName: '지어낸 확정 보고서.pdf', pageCount: 40 }),
      fakeDocument(2, {
        fileName: '지어낸 분석 보고서.pdf',
        pageCount: null,
        uploadedBy: other,
      }),
      fakeDocument(3, {
        fileName: '지어낸 스캔 보고서.pdf',
        uploadedAt: null,
        uploadedBy: other,
      }),
      fakeDocument(4, { fileName: '지어낸 멈춘 보고서.pdf' }),
    ],
    runs: [
      fakeRun(5, 1, { createdAt: '2026-10-18T09:05:00+09:00' }),
      fakeRun(6, 2, {
        status: 'processing',
        steps: fakeSteps(2, { status: 'running', done: 3, total: 10 }),
        startedAt: '2026-10-18T09:06:10+09:00',
        createdAt: '2026-10-18T09:06:00+09:00',
        createdByUserId: 8,
      }),
      fakeRun(7, 3, {
        status: 'failed',
        steps: fakeSteps(0, { status: 'failed' }),
        errorCode: 'no_text_layer',
        createdAt: '2026-10-18T09:07:00+09:00',
        createdByUserId: 8,
      }),
      fakeRun(8, 4, {
        status: 'failed',
        steps: fakeSteps(0, { status: 'failed' }),
        errorCode: 'step_error',
        createdAt: '2026-10-18T09:08:00+09:00',
      }),
    ],
    ...options,
  });
  server.advance(5, { status: 'done' });
  const confirmed = server.runs.get(5)!;
  confirmed.review = {
    state: 'confirmed',
    marks: [0, 1, 2].map((itemIndex) => ({
      itemIndex,
      decision: 'adopted',
      excludeReason: null,
    })),
    confirmedAt: '2026-10-18T10:00:00+09:00',
    confirmedBy: { ...FAKE_CONFIRMER },
  };
  return server;
}

/**
 * 진짜 실어댑터 + 이 가짜 서버(화면·훅 시험의 「세 겹」 ⓑ). 쪽 세기는 기본 7쪽(발주서 §3 자료 조건), 서명 PUT 은 가짜의 sendUpload.
 */
export function serverStoreOf(
  server: FakeGreenwashServer,
  deps: Partial<Omit<GreenwashServerDeps, 'api'>> = {},
  baseUrl = 'http://test.local/api',
) {
  return createGreenwashServerStore({
    api: createApi({ baseUrl, fetch: server.send }),
    sendUpload: server.sendUpload,
    countPages: async () => 7,
    ...deps,
  });
}
