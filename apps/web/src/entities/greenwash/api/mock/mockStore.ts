// 목 저장소(밴드 FW1b ①, 넓힘 FW2 ①). GreenwashStore 꼴을 메모리에서 맞춘다. 서버를 부르지 않는다.
//
// - 쪽 수·글자 층은 파일 이름 표(MOCK_FILES)로 정한다. 표 밖 이름은 거절한다(「올릴 수 없는 파일」).
//   목 단계의 제한이다(무효 조건: 실제 API 는 PDF 를 읽어 pageCount 를 채운다).
// - 실행 id·문서 id 는 증가 카운터(run-1, run-2 …). 시험은 setProgress 로 상태를 직접 넣는다.
// - 진행을 시간으로 흘리는 것은 데모 모드(demoIntervalMs + start())에서만이다(그린워싱 틀 app/greenwash/GreenwashRoutes.tsx 가 search 의 demo=1 을 읽어 넘긴다).
// - 시험용 진입: scenario 를 주면 실행 하나를 미리 만든다(seededRunId). ?mock=failed 꼴은 그린워싱 틀(GreenwashRoutes)이 읽는다. 미리 만든 실행의 id 는 늘 run-1(주소 /greenwash/runs/run-1?mock=failed).
// 밴드 FW2 ①:
// - 목록 씨앗 다섯(mockSeeds.ts)이 늘 있다(실행 id run-100~105, 문서 id doc-s0~s5). 새로 만든 실행은 run-1 부터다.
// - subscribeRun 은 구독 즉시 현재값을 한 번 보낸다(저장소 계약, sid:MARC-ISSUE-99 2). 없는 실행이면 onMissing.
// - 실행이 끝나면(finish·setProgress·데모 걸음) 그 실행의 입력 쪽에서 결과를 결정적으로 짓고 검토를 pending 으로 연다 [R7].
//   e2e 는 ?autofinish=1 → autoFinishMs 로 이 세션에서 만든 실행을 곧 끝낸다(그린워싱 틀이 search 를 읽어 넘긴다 [2N1]).
// - PUT 은 받은 marks 로 갈아 끼운다(합치지 않는다 [B3]). 확정된 실행이면 StoreError review_locked, done 이 아닌 실행이면 run_not_done(서버 409).
//   확정하면 검토의 confirmedBy 에 지금 사용자를 넣는다(그 밖에는 null). 목은 dry-run 실행을 짓지 않아 no_review 는 내지 않는다.
// - 시각은 +09:00 ISO 8601 이다(꾸미는 것은 ui). 검토의 runId 는 실행 id 의 숫자(run-101 → 101).
// - 이 세션에서 올린 파일은 openDocumentPdf 가 그 File 을 돌려준다(씨앗 문서는 null). 예외: 실호출 씨앗(run-106)의 문서는
//   처음 열 때 지은 PDF(reportBPdf.ts — 상자 자리에 지어낸 글, 밴드 GVS1)를 짓고 그 뒤로는 같은 File 을 돌려준다.
// 고침(밴드 G1b-3 ③, review@2): PUT 의 edits 를 서버 규칙(apps/api-py/esgapi/greenwash/service/actions/review.py 머리말)대로 흉내 낸다 —
//   edits 생략·null = 고침 그대로, 목록 = 그 실행의 고침 전부 갈아 넣기. 칸마다 strip(사유는 항목마다, 빈 항목 버림),
//   AI 값과 같으면 그 칸 null, 그 칸 값이 바뀐 PUT 에서만 그 칸의 때·사람(지금 사용자)을 새로. 범위 밖·겹친 itemIndex·빈 값·
//   상한(사유 10줄·줄 500자·수정 방향 2000자) 넘음은 StoreError rejected(서버 400 INVALID_REVIEW). 정규화 뒤 고침이 있으면 pending → in_review.
//   다듬기 전 그물(원래 50항목·줄 1000자·수정 방향 4000자)도 같은 상한 문장으로 거절, AI 값도 같은 다듬기를 한 뒤 견주고, 글자 수는 코드 포인트다(밴드 GMK1, 서버 GRV1).
//   확정 뒤는 review_locked(edits 도). 목록의 levelCounts 는 효력 등급(고친 등급 ?? AI — 서버 checks 와 같은 뜻).
// 근거 고침·재판단(밴드 GRJ1 ③, review@3): 규칙은 rejudgeRules.ts 한 벌(시험용 가짜 서버와 같은 함수). PUT 의 evidence 는 갈아 넣기
//   (생략·null = 그대로), 고침 견줌·levelCounts 는 기준 판단(가장 늦은 done 재판단 ?? 첫 판단)과. rejudge 는 실행 id 9001 부터,
//   검토 읽기 REJUDGE_SETTLE_READS 번째에 끝난다(견본은 rejudgeRules.mockJudgement).
// 실행 만들기 열쇠(밴드 GR2): createRun·rerun 은 받은 열쇠를 기억해 같은 열쇠면 앞에 만든 실행 id 를 그대로 돌려준다(새 실행 0 — 서버 IK1 흉내).
//   입력이 다른지는 보지 않는다(같은 열쇠·다른 본문의 409 는 실어댑터 시험이 잰다). 열쇠가 없으면 늘 새 실행.
// 이 폴더는 DOM·location 을 모른다(app/guards/layers.test.ts). 값은 모두 지어낸 것이다.
import {
  RUN_STAGES,
  toKstIso,
  totalPages,
  unionPages,
} from '../../model/index.ts';
import type {
  GreenwashReview,
  LevelCounts,
  ListedRun,
  ReviewEdit,
  ReviewEditIn,
  ReviewUpdate,
  RunProgress,
  ScanResult,
} from '../../model/index.ts';
import { StoreError } from '../store.ts';
import type {
  ExistingDocument,
  GreenwashStore,
  RunRequest,
  RunSnapshot,
} from '../store.ts';
import {
  MOCK_PART_NAMES,
  buildMockResult,
  generatedItems,
  generatedWordPages,
} from './mockResults.ts';
import {
  MOCK_COMPANY_NAME,
  MOCK_CURRENT_USER,
  REPORT_B_RUN_ID,
  mockReviewer,
  seedDocs,
  seedRuns,
} from './mockSeeds.ts';
import type { SeedDoc } from './mockSeeds.ts';
import {
  basisCounts,
  basisItems,
  checkedEvidence,
  confirmRefusal,
  evidenceRefusal,
  nextEvidence,
  rejudgeLines,
  rejudgeRefusal,
  settleOnRead,
  startRejudge,
} from './rejudgeRules.ts';
import type { MockRejudgeRun } from './rejudgeRules.ts';

/** 파일 이름 → 쪽 수·글자 층. 지어낸 이름이다. */
export const MOCK_FILES: Readonly<
  Record<string, { pageCount: number; hasText: boolean }>
> = {
  '목-보고서-60쪽.pdf': { pageCount: 60, hasText: true },
  '목-보고서-139쪽.pdf': { pageCount: 139, hasText: true },
  '목-스캔-24쪽.pdf': { pageCount: 24, hasText: false },
  '목-큰문서-320쪽.pdf': { pageCount: 320, hasText: true },
};

/** 수정본 대상으로 고를 기존 문서(지어낸 이름). */
export const MOCK_DOCUMENTS: readonly ExistingDocument[] =
  latestOfChains(seedDocs());

/**
 * 수정본 대상으로 고를 문서: 판 사슬의 마지막 문서들(올린 때가 늦은 차례). 목록(GW-01)의 줄과 같은 문서다
 * (실제 API 는 둘 다 core_documents_list 를 읽는다 — 밴드 FW2 ②, 발주서 덧붙임 3 예외 4).
 */
function latestOfChains(all: readonly SeedDoc[]): ExistingDocument[] {
  const ids = new Set(all.map((doc) => doc.documentId));
  const superseded = new Set(
    all
      .map((doc) => doc.previousDocumentId)
      .filter((id): id is string => id !== null && ids.has(id)),
  );
  return all
    .filter((doc) => !superseded.has(doc.documentId))
    .sort((x, y) => (x.uploadedAt < y.uploadedAt ? 1 : -1))
    .map(({ documentId, fileName, uploadedAt }) => ({
      documentId,
      fileName,
      uploadedAt,
    }));
}

/** 기본 단어 목록(지어낸 짧은 목록. 코랩 원목록을 옮기지 않았다). */
export const MOCK_DEFAULT_TERMS: readonly string[] = [
  '친환경',
  '탄소중립',
  '넷제로',
  '녹색',
  '지속가능',
];

export const MOCK_SCENARIOS = ['running', 'failed', 'done'] as const;
export type MockScenario = (typeof MOCK_SCENARIOS)[number];

/** 미리 만드는 실행의 점검할 쪽 수(시안 GW-03 의 44쪽, 28쪽 진행). failed 씨앗은 판정 28 / 44쪽에서 실행 전체가 멈춘 것이다(서버 오류 등, 밴드 FW2 ⓪). */
const SEED_PAGES = 44;
/** 미리 만드는 실행의 문서 쪽 수(시안 GW-03 의 139쪽). */
const SEED_PAGE_COUNT = 139;
const SEED_DONE = 28;

export interface MockStoreOptions {
  /** 주면 이 상태의 실행 하나를 미리 만든다. */
  scenario?: MockScenario;
  /** 주면 진행을 시간으로 흘린다(ms 마다 한 걸음). */
  demoIntervalMs?: number;
  /** 주면 이 세션에서 만든 실행(createRun·rerun)을 이 ms 뒤에 끝낸다(e2e 의 &autofinish=1). */
  autoFinishMs?: number;
  /** 지금 시각. 기본 new Date(). */
  now?: () => Date;
}

export interface MockStoreControl {
  store: GreenwashStore;
  /** scenario 로 미리 만든 실행 id. 없으면 null. */
  seededRunId: string | null;
  /** 시험용: 실행 상태를 직접 넣는다(구독자에게 알린다). done 이면 결과를 짓는다. */
  setProgress(runId: string, progress: RunProgress): void;
  /** 시험·e2e 용: 돌고 있는 실행을 끝낸다(결과를 짓고 검토를 연다). 돌고 있지 않으면 아무것도 안 한다. */
  finish(runId: string): void;
  /** 데모 타이머를 켠다(demoIntervalMs 가 있을 때만. 이미 켜져 있으면 그대로). */
  start(): void;
  /** 데모 타이머를 멈춘다. start 로 다시 켤 수 있다(React StrictMode 의 effect 두 번 돌기에 맞춤). */
  stop(): void;
}

export class MockUploadRejected extends Error {
  constructor(fileName: string) {
    super(`목 저장소가 모르는 파일: ${fileName}`);
    this.name = 'MockUploadRejected';
  }
}

interface MockDoc extends SeedDoc {
  hasText: boolean;
  /** 이 세션에서 올린 파일. 씨앗은 null. */
  file: File | null;
}

interface MockRun {
  snapshot: RunSnapshot;
  createdAt: string;
  request: RunRequest;
  result: ScanResult | null;
  review: GreenwashReview | null;
  /** 재판단 실행(만든 차례, GRJ1). 없으면 없음. */
  rejudges?: MockRejudgeRun[];
}

/** 실행 id 의 숫자(검토의 runId). */
const runNumber = (runId: string) => Number(runId.replace(/^\D+/, '')) || 0;

const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

/** 미리 만드는 실행(&mock=)의 문서. */
const SEED_SCENARIO_DOC: SeedDoc = {
  documentId: 'doc-seed',
  fileName: '목-통합보고서-초안.pdf',
  pageCount: SEED_PAGE_COUNT,
  reportYear: 2026,
  previousDocumentId: null,
  uploadedAt: '2026-10-15T14:00:00+09:00',
  uploadedBy: MOCK_CURRENT_USER,
};

export function createMockStore(
  options: MockStoreOptions = {},
): MockStoreControl {
  const now = options.now ?? (() => new Date());
  let documentSeq = 0;
  /** 실행 만들기 열쇠 → 그 열쇠로 만든 실행 id(밴드 GR2). */
  const byKey = new Map<string, string>();
  let runSeq = 0;
  /** 재판단 실행 id(지어낸 수 — 목록 실행 id 와 겹치지 않게 9001 부터). */
  let rejudgeSeq = 9000;
  const docs = new Map<string, MockDoc>();
  const runs = new Map<string, MockRun>();
  const listeners = new Map<string, Set<(run: RunSnapshot) => void>>();
  /** 실호출 씨앗 문서의 지은 PDF(처음 열 때 한 번). */
  let reportBFile: Promise<File> | undefined;

  const addDoc = (doc: SeedDoc, extra: Partial<MockDoc> = {}) =>
    docs.set(doc.documentId, { hasText: true, file: null, ...doc, ...extra });
  for (const doc of seedDocs()) addDoc(doc);
  for (const seed of seedRuns(MOCK_DEFAULT_TERMS)) {
    const doc = docs.get(seed.documentId)!;
    runs.set(seed.runId, {
      snapshot: {
        runId: seed.runId,
        documentId: seed.documentId,
        startedAt: seed.startedAt,
        // 끝난 씨앗은 시작 20분 뒤에 끝난 것으로 둔다(지어낸 값 — 씨앗 표에 끝난 때 칸이 없다, 밴드 GW2R ②)
        finishedAt:
          seed.progress.state === 'done' && seed.startedAt !== null ?
            toKstIso(new Date(Date.parse(seed.startedAt) + 20 * 60 * 1000))
          : null,
        pageCount: doc.pageCount,
        checkedPages: totalPages(seed.request.parts),
        progress: seed.progress,
        rerunOf: null,
        errorCode: null,
      },
      createdAt: seed.createdAt,
      request: seed.request,
      result: seed.result,
      review: seed.review,
    });
  }

  const notify = (run: MockRun) => {
    for (const listener of listeners.get(run.snapshot.runId) ?? [])
      listener(run.snapshot);
  };

  /** 실행 상태를 바꾼다. done 이 되면 결과와 검토(pending)를 짓는다. */
  const advance = (run: MockRun, progress: RunProgress) => {
    run.snapshot = {
      ...run.snapshot,
      progress,
      finishedAt:
        progress.state === 'running' ?
          null
        : (run.snapshot.finishedAt ?? toKstIso(now())),
    };
    if (progress.state === 'done' && run.result === null) {
      run.result = resultFor(run);
      run.review = {
        schemaVersion: 'greenwash.review@3',
        evidence: [],
        rejudges: [],
        runId: runNumber(run.snapshot.runId),
        state: 'pending',
        confirmedAt: null,
        confirmedBy: null,
        marks: [],
        edits: [],
      };
    }
    notify(run);
  };

  const resultFor = (run: MockRun): ScanResult => {
    const doc = docs.get(run.snapshot.documentId)!;
    const { parts, extraTerms } = run.request;
    const checked = unionPages(parts);
    const nameOf = (page: number) =>
      (['ceo', 'company', 'climate'] as const)
        .filter((key) => parts[key].includes(page))
        .map((key) => MOCK_PART_NAMES[key])
        .join('·');
    return buildMockResult({
      fileName: doc.fileName,
      pageCount: doc.pageCount,
      parts: [
        { name: MOCK_PART_NAMES.ceo, pages: parts.ceo },
        { name: MOCK_PART_NAMES.company, pages: parts.company },
        { name: MOCK_PART_NAMES.climate, pages: parts.climate },
      ],
      items: generatedItems(checked, nameOf),
      extraTerms,
      defaultTerms: MOCK_DEFAULT_TERMS,
      wordPages: generatedWordPages(checked, MOCK_DEFAULT_TERMS, extraTerms),
    });
  };

  const finish = (runId: string) => {
    const run = runs.get(runId);
    if (!run || run.snapshot.progress.state !== 'running') return;
    const total = run.snapshot.checkedPages;
    advance(run, {
      state: 'done',
      stage: 'summarize',
      judge: { done: total, total },
    });
  };

  const nextRunId = () => `run-${++runSeq}`;
  /** &autofinish=1 의 끝내기 타이머(stop 에서 지운다). */
  const finishTimers = new Set<ReturnType<typeof setTimeout>>();
  const newRun = (
    documentId: string,
    request: RunRequest,
    rerunOf: string | null,
  ): string => {
    const doc = docs.get(documentId)!;
    const runId = nextRunId();
    const checked = totalPages(request.parts);
    const at = toKstIso(now());
    const run: MockRun = {
      snapshot: {
        runId,
        documentId,
        startedAt: at,
        finishedAt: null,
        pageCount: doc.pageCount,
        checkedPages: checked,
        rerunOf,
        errorCode: null,
        progress: {
          state: 'running',
          stage: 'extract',
          judge: { done: 0, total: checked },
        },
      },
      createdAt: at,
      request,
      result: null,
      review: null,
    };
    runs.set(runId, run);
    notify(run);
    if (options.autoFinishMs !== undefined)
      finishTimers.add(setTimeout(() => finish(runId), options.autoFinishMs));
    return runId;
  };

  let seededRunId: string | null = null;
  if (options.scenario) {
    addDoc(SEED_SCENARIO_DOC);
    const runId = nextRunId();
    seededRunId = runId;
    const at = toKstIso(now());
    runs.set(runId, {
      snapshot: {
        runId,
        documentId: SEED_SCENARIO_DOC.documentId,
        startedAt: at,
        finishedAt: null,
        pageCount: SEED_PAGE_COUNT,
        checkedPages: SEED_PAGES,
        rerunOf: null,
        errorCode: null,
        progress: {
          state: 'running',
          stage: 'judge',
          judge: { done: SEED_DONE, total: SEED_PAGES },
        },
      },
      createdAt: at,
      request: {
        parts: {
          ceo: [],
          company: [],
          climate: Array.from({ length: SEED_PAGES }, (_, i) => i + 1),
        },
        extraTerms: [],
        reportYear: 2026,
        previousDocumentId: null,
      },
      result: null,
      review: null,
    });
    const seeded = runs.get(runId)!;
    if (options.scenario === 'done') finish(runId);
    else if (options.scenario === 'failed')
      advance(seeded, { ...seeded.snapshot.progress, state: 'failed' });
  }

  const runOf = (runId: string) => {
    const run = runs.get(runId);
    if (!run) throw new StoreError('not_found', `없는 실행: ${runId}`);
    return run;
  };

  const store: GreenwashStore = {
    async createDocument(file) {
      // 맥 Finder 는 한글 이름을 NFD 로 넘긴다 — 표의 이름(NFC)과 맞춰 본다(밴드 GA1)
      const known = MOCK_FILES[file.name.normalize('NFC')];
      if (!known) throw new MockUploadRejected(file.name);
      const documentId = `doc-${++documentSeq}`;
      addDoc(
        {
          documentId,
          fileName: file.name,
          pageCount: known.pageCount,
          reportYear: null,
          previousDocumentId: null,
          uploadedAt: toKstIso(now()),
          uploadedBy: MOCK_CURRENT_USER,
        },
        { hasText: known.hasText, file },
      );
      return { documentId, ...known };
    },
    async createRun(documentId, request: RunRequest, idempotencyKey) {
      const replayed =
        idempotencyKey === undefined ? undefined : byKey.get(idempotencyKey);
      if (replayed !== undefined) return { runId: replayed };
      const doc = docs.get(documentId);
      if (!doc) throw new StoreError('not_found', `없는 문서: ${documentId}`);
      // 보고연도는 실행 입력에 실려 온다(실어댑터는 문서 PATCH 로 옮긴다 — 밴드 GW2R ③). 문서에 적어 목록에 보인다.
      doc.reportYear = request.reportYear;
      doc.previousDocumentId = request.previousDocumentId;
      const runId = newRun(documentId, request, null);
      if (idempotencyKey !== undefined) byKey.set(idempotencyKey, runId);
      return { runId };
    },
    async getRun(runId) {
      return runOf(runId).snapshot;
    },
    subscribeRun(runId, listener, onMissing) {
      const run = runs.get(runId);
      if (!run) {
        onMissing?.();
        return () => {};
      }
      let set = listeners.get(runId);
      if (!set) listeners.set(runId, (set = new Set()));
      set.add(listener);
      // 계약: 현재값을 먼저 한 번(곧바로) 보낸다.
      listener(run.snapshot);
      return () => {
        set.delete(listener);
      };
    },
    async rerun(runId, idempotencyKey) {
      const replayed =
        idempotencyKey === undefined ? undefined : byKey.get(idempotencyKey);
      if (replayed !== undefined) return { runId: replayed };
      const run = runs.get(runId);
      if (!run || run.snapshot.progress.state !== 'failed')
        throw new StoreError('rejected', `다시 실행할 수 없는 실행: ${runId}`);
      // 이미 다시 돈 실패 실행은 거절한다(같은 실패에서 새 실행이 둘 생기지 않게 — 밴드 FW2 ⑤ M1)
      if ([...runs.values()].some((other) => other.snapshot.rerunOf === runId))
        throw new StoreError('rejected', `이미 다시 실행한 실행: ${runId}`);
      // 같은 문서·같은 입력으로 처음부터: 추출 단계, 판정 0쪽.
      const next = newRun(run.snapshot.documentId, run.request, runId);
      if (idempotencyKey !== undefined) byKey.set(idempotencyKey, next);
      return { runId: next };
    },
    async listDocuments() {
      // 목록에 보이는 문서(실행이 있거나 앞 판인 것)의 판 사슬 마지막들. 처음에는 MOCK_DOCUMENTS 와 같다.
      return latestOfChains([...docs.values()].filter(listed));
    },
    async listDefaultTerms() {
      return MOCK_DEFAULT_TERMS;
    },
    async getDocument(documentId) {
      const doc = docs.get(documentId);
      if (!doc) throw new StoreError('not_found', `없는 문서: ${documentId}`);
      return {
        documentId,
        fileName: doc.fileName,
        pageCount: doc.pageCount,
      };
    },
    async listCheckRows() {
      const listedRuns: ListedRun[] = [...runs.values()].map((run) => ({
        runId: run.snapshot.runId,
        documentId: run.snapshot.documentId,
        createdAt: run.createdAt,
        finishedAt: run.snapshot.finishedAt ?? null,
        progress: run.snapshot.progress,
        levelCounts:
          run.result ?
            basisCounts(
              run.result.items,
              run.result.counts.byLevel,
              new Map(
                (run.review?.edits ?? []).flatMap((e) =>
                  e.level === null ? [] : [[e.itemIndex, e.level.value]],
                ),
              ),
              run.rejudges ?? [],
            )
          : null,
        review:
          run.review && run.result ?
            {
              state: run.review.state,
              reviewed: run.review.marks.length,
              total: run.result.items.length,
              confirmedAt: run.review.confirmedAt,
              confirmedBy: run.review.confirmedBy?.name ?? null,
            }
          : null,
      }));
      return {
        currentUserId: MOCK_CURRENT_USER.userId,
        companyName: MOCK_COMPANY_NAME,
        documents: [...docs.values()].filter(listed).map((doc) => ({
          documentId: doc.documentId,
          fileName: doc.fileName,
          reportYear: doc.reportYear,
          previousDocumentId: doc.previousDocumentId,
          pageCount: doc.pageCount,
          uploadedAt: doc.uploadedAt,
          uploadedBy: { ...doc.uploadedBy },
        })),
        runs: listedRuns,
      };
    },
    async getResult(runId) {
      const run = runOf(runId);
      if (!run.result)
        throw new StoreError('not_found', `결과가 없는 실행: ${runId}`);
      return copy(run.result);
    },
    async getReview(runId) {
      const run = runOf(runId);
      if (!run.review || !run.result)
        throw new StoreError('not_found', `검토가 없는 실행: ${runId}`);
      const rejudges = (run.rejudges ??= []);
      run.review = {
        ...run.review,
        evidence: settleOnRead(
          run.result.items,
          rejudges,
          run.review.evidence,
          {
            at: toKstIso(now()),
            by: mockReviewer(MOCK_CURRENT_USER),
          },
        ),
      };
      return copy({ ...run.review, rejudges: rejudgeLines(rejudges) });
    },
    async rejudge(runId, itemIndex) {
      const run = runOf(runId);
      // 서버 rejudge.py 차례: done 아님 → 검토 없음 → 문장 밖 404 → 확정됨 → 도는 중 → 같은 근거
      if (run.snapshot.progress.state !== 'done')
        throw new StoreError('run_not_done', `끝나지 않은 실행: ${runId}`);
      if (!run.review || !run.result)
        throw new StoreError('no_review', `검토가 없는 실행: ${runId}`);
      if (
        !Number.isInteger(itemIndex) ||
        itemIndex < 0 ||
        itemIndex >= run.result.items.length
      )
        throw new StoreError('not_found', `없는 문장: ${itemIndex}`);
      const rejudges = (run.rejudges ??= []);
      const refusal = rejudgeRefusal({
        confirmed: run.review.state === 'confirmed',
        items: run.result.items,
        runs: rejudges,
        evidence: run.review.evidence,
        itemIndex,
      });
      if (refusal !== null)
        throw new StoreError(refusal, `재판단 거절: ${refusal}`);
      rejudgeSeq += 1;
      rejudges.push(startRejudge(rejudgeSeq, itemIndex, run.review.evidence));
      return { rejudgeRunId: String(rejudgeSeq) };
    },
    async putReview(runId, update: ReviewUpdate) {
      const run = runOf(runId);
      // code 는 서버 PUT /greenwash/runs/{run_id}/review 의 docstring(apps/api-py/generated/api.d.ts 「Review Put」) 그대로다:
      //   없는 실행 404 · done 이 아님 409 run_not_done · 확정됨 409 review_locked · dry-run 409 no_review(목에는 dry-run 이 없다).
      // 어느 것을 먼저 보는지(없음 → done 아님 → 확정됨)는 목의 차례다 — docstring 에 차례가 없다. 서버 몸(G1b)에서 확인한다.
      if (run.snapshot.progress.state !== 'done')
        throw new StoreError('run_not_done', `끝나지 않은 실행: ${runId}`);
      if (!run.review || !run.result)
        throw new StoreError('not_found', `검토가 없는 실행: ${runId}`);
      if (run.review.state === 'confirmed')
        throw new StoreError('review_locked', `확정된 실행: ${runId}`);
      const count = run.result.items.length;
      const indexes = update.marks.map((mark) => mark.itemIndex);
      const ordered = indexes.every(
        (index, i) =>
          index >= 0 && index < count && (i === 0 || index > indexes[i - 1]!),
      );
      if (!ordered)
        throw new StoreError(
          'rejected',
          'marks 는 문장 차례 안, 오름차순, 겹침 없음',
        );
      // 서버 규칙(결함 D1): state 는 confirmed 나 없음(null)만. 거울을 거치지 않고 들어온 값도 막는다.
      const asked: unknown = update.state;
      if (asked !== undefined && asked !== null && asked !== 'confirmed')
        throw new StoreError(
          'rejected',
          `state 는 confirmed 나 생략만: ${String(asked)}`,
        );
      const confirming = asked === 'confirmed';
      // 고침(G1b-3): 생략·null 이면 그대로, 목록이면 정규화해 갈아 넣는다(잘못이면 거절 — 서버 400).
      const rejudges = (run.rejudges ??= []);
      const edits =
        update.edits == null ?
          run.review.edits
        : nextEdits(
            { ...run.result, items: basisItems(run.result.items, rejudges) },
            run.review.edits,
            update.edits,
            { at: toKstIso(now()), by: mockReviewer(MOCK_CURRENT_USER) },
          );
      if (typeof edits === 'string') throw new StoreError('rejected', edits);
      // 근거 고침(GRJ1): 생략·null 이면 그대로, 목록이면 검사·정규화해 갈아 넣는다
      const checked =
        update.evidence == null ?
          null
        : checkedEvidence(
            run.result.items,
            rejudges,
            run.result.source.pageCount,
            update.evidence,
          );
      if (typeof checked === 'string')
        throw new StoreError('rejected', checked);
      // 확정은 도는 재판단이 없을 때만(서버 규칙 8 — 검사 뒤·쓰기 앞)
      if (confirming && confirmRefusal(rejudges) !== null)
        throw new StoreError('rejudge_running', `재판단이 도는 실행: ${runId}`);
      // 도는 문장의 근거는 바꾸지 않는다(서버 규칙 8 넓힘 — GRJ3)
      if (evidenceRefusal(rejudges, run.review.evidence, checked) !== null)
        throw new StoreError('rejudge_running', `재판단이 도는 문장: ${runId}`);
      const evidence =
        checked === null ?
          run.review.evidence
        : nextEvidence(run.review.evidence, checked, {
            at: toKstIso(now()),
            by: mockReviewer(MOCK_CURRENT_USER),
          });
      // (a) 표시가 하나라도 있거나 정규화 뒤 고침이 있으면 pending → in_review. 둘 다 없으면 그대로(in_review 에서 marks=[] 도 in_review).
      const touched =
        update.marks.length > 0 ||
        (update.edits != null && edits.length > 0) ||
        (checked !== null && evidence.length > 0);
      const state =
        confirming ? 'confirmed'
        : run.review.state === 'pending' && touched ? 'in_review'
        : run.review.state;
      // 받은 marks 로 갈아 끼운다(합치지 않는다 [B3]). (b) 확정이면 표시 없는 문장을 adopted 로 채운 결과 items 전부.
      const byIndex = new Map(
        update.marks.map((mark) => [mark.itemIndex, mark]),
      );
      const marks =
        confirming ?
          run.result.items.map(
            (_item, index) =>
              byIndex.get(index) ?? {
                itemIndex: index,
                decision: 'adopted' as const,
                excludeReason: null,
              },
          )
        : update.marks;
      run.review = {
        ...run.review,
        state,
        confirmedAt: state === 'confirmed' ? toKstIso(now()) : null,
        confirmedBy:
          state === 'confirmed' ? mockReviewer(MOCK_CURRENT_USER) : null,
        marks: marks.map((mark) => ({ ...mark })),
        edits: structuredClone(edits) as ReviewEdit[],
        evidence: structuredClone(evidence),
      };
      return copy({ ...run.review, rejudges: rejudgeLines(rejudges) });
    },
    async openDocumentPdf(documentId) {
      const doc = docs.get(documentId);
      const reportB = runs.get(REPORT_B_RUN_ID);
      if (
        doc !== undefined &&
        doc.file === null &&
        reportB?.snapshot.documentId === documentId &&
        reportB.result !== null
      ) {
        const result = reportB.result;
        reportBFile ??= import('./reportBPdf.ts').then(({ reportBPdf }) =>
          reportBPdf(result, doc.fileName, doc.pageCount),
        );
        return reportBFile;
      }
      return doc?.file ?? null;
    },
    // 엑셀(밴드 GW2R ③): 지어낸 작은 Blob(실제 xlsx 가 아니다). 서버 규칙대로 끝나지 않은 실행·확정 전 확정본은 거절.
    async getReport(runId, confirmed) {
      const run = runOf(runId);
      if (run.result === null)
        throw new StoreError('run_not_done', `끝나지 않은 실행: ${runId}`);
      if (confirmed && run.review?.state !== 'confirmed')
        throw new StoreError('rejected', `확정 전 실행: ${runId}`);
      return {
        blob: new Blob([`지어낸 엑셀 ${runId}${confirmed ? ' 확정본' : ''}`], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }),
        fileName: `greenwash-${runId}${confirmed ? '-confirmed' : ''}.xlsx`,
      };
    },
  };

  /** 목록에 싣는 문서: 실행이 있거나 다른 문서의 앞 판. 실행이 하나도 없는 문서(올렸다가 취소한 것)는 목 단계에서는 버린다(store.ts 머리말). */
  const listed = (doc: MockDoc): boolean =>
    [...runs.values()].some(
      (run) => run.snapshot.documentId === doc.documentId,
    ) || isPrevious(doc);
  /** 다른 문서의 앞 판인가(실행이 없어도 사슬 셈에 쓴다). */
  const isPrevious = (doc: MockDoc) =>
    [...docs.values()].some(
      (other) => other.previousDocumentId === doc.documentId,
    );

  const setProgress = (runId: string, progress: RunProgress) => {
    const run = runs.get(runId);
    if (!run) throw new Error(`없는 실행: ${runId}`);
    advance(run, progress);
  };

  let timer: ReturnType<typeof setInterval> | undefined;
  const start = () => {
    if (options.demoIntervalMs === undefined || timer !== undefined) return;
    timer = setInterval(() => {
      for (const run of [...runs.values()])
        if (run.snapshot.progress.state === 'running')
          advance(run, step(run.snapshot.progress));
    }, options.demoIntervalMs);
  };

  return {
    store,
    seededRunId,
    setProgress,
    finish,
    start,
    stop: () => {
      if (timer !== undefined) clearInterval(timer);
      timer = undefined;
      // &autofinish=1 로 걸어 둔 끝내기도 지운다(내려간 뒤 목이 돌지 않게 — 밴드 FW2 ⑤)
      for (const pending of finishTimers) clearTimeout(pending);
      finishTimers.clear();
    },
  };
}

/** 고침 상한(서버 Q4 — models.py 의 EDIT_* 상수와 같은 값). */
const MAX_BULLETS = 10;
const MAX_BULLET_CHARS = 500;
const MAX_FIX_CHARS = 2000;
/** 다듬기 전 그물(서버 GRV1 — models.py 의 EDIT_*_RAW_* 와 같은 값). */
const MAX_RAW_BULLETS = 50;
const MAX_RAW_BULLET_CHARS = 1000;
const MAX_RAW_FIX_CHARS = 4000;

/** 글자 수는 코드 포인트(서버 len 과 같은 단위 — greenwash-setting terms.ts 의 꼴, sid:MARC-ISSUE-320). */
const charsOf = (text: string) => [...text].length;
const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);
/** 판정 사유 다듬기(서버 _tidy_reasons): 줄마다 trim, 빈 줄은 버린다. 사람 값과 AI 값에 같이 쓴다. */
const tidyBullets = (lines: readonly string[]) =>
  lines.map((line) => line.trim()).filter((line) => line !== '');
/** 수정 방향 다듬기(서버 _tidy_fix): 앞뒤 공백을 지운다. 사람 값과 AI 값에 같이 쓴다. */
const tidyFix = (text: string) => text.trim();

/** 다듬은 사람 값이 같은 규칙으로 다듬은 AI 값과 같은가(서버 _same_as_ai). AI 값이 null·꼴이 다르면 날것끼리 견준다. */
function sameAsAi(value: string | readonly string[], ai: unknown): boolean {
  if (typeof value !== 'string' && Array.isArray(ai)) {
    const lines = ai as unknown[];
    if (lines.every((line) => typeof line === 'string'))
      return same(value, tidyBullets(lines as string[]));
  }
  if (typeof value === 'string' && typeof ai === 'string')
    return value === tidyFix(ai);
  return same(value, ai);
}

/**
 * 문장 하나의 판정 사유·수정 방향 검사와 정규화(서버 _checked_edits 의 번호 검사 뒤 차례 그대로). AI 와 같은 칸은 null.
 * 잘못이면 서버 400 의 문장. 시험용 가짜 서버(api/testing.ts)도 이 함수를 쓴다.
 */
export function checkedEditCells(
  want: Pick<ReviewEditIn, 'reasonBullets' | 'fixParagraph'>,
  ai: { reasonBullets: unknown; fixParagraph: unknown },
): { reasonBullets: string[] | null; fixParagraph: string | null } | string {
  let bullets: string[] | null = null;
  if (want.reasonBullets !== null) {
    if (want.reasonBullets.length > MAX_RAW_BULLETS)
      return `판정 사유는 ${MAX_BULLETS}줄까지 쓸 수 있어요`;
    if (want.reasonBullets.some((b) => charsOf(b) > MAX_RAW_BULLET_CHARS))
      return `판정 사유는 한 줄에 ${MAX_BULLET_CHARS}자까지 쓸 수 있어요`;
    bullets = tidyBullets(want.reasonBullets);
    if (bullets.length === 0) return '판정 사유는 한 줄 이상 있어야 해요';
    if (bullets.length > MAX_BULLETS)
      return `판정 사유는 ${MAX_BULLETS}줄까지 쓸 수 있어요`;
    if (bullets.some((b) => charsOf(b) > MAX_BULLET_CHARS))
      return `판정 사유는 한 줄에 ${MAX_BULLET_CHARS}자까지 쓸 수 있어요`;
  }
  let fix: string | null = null;
  if (want.fixParagraph !== null) {
    if (charsOf(want.fixParagraph) > MAX_RAW_FIX_CHARS)
      return `수정 방향은 ${MAX_FIX_CHARS}자까지 쓸 수 있어요`;
    fix = tidyFix(want.fixParagraph);
    if (fix === '') return '수정 방향은 비워 둘 수 없어요';
    if (charsOf(fix) > MAX_FIX_CHARS)
      return `수정 방향은 ${MAX_FIX_CHARS}자까지 쓸 수 있어요`;
  }
  return {
    reasonBullets:
      bullets === null || sameAsAi(bullets, ai.reasonBullets) ? null : bullets,
    fixParagraph: fix === null || sameAsAi(fix, ai.fixParagraph) ? null : fix,
  };
}

/**
 * PUT 의 평평한 고침 → 저장할 고침(서버 규칙 흉내). 잘못이면 서버 400 의 문장(글자)을 돌려준다.
 * before 는 지금 고침(칸마다 값이 같으면 그 칸의 때·사람을 그대로 둔다).
 */
export function nextEdits(
  result: ScanResult,
  before: readonly ReviewEdit[],
  wanted: readonly ReviewEditIn[],
  now: { at: string; by: { id: number; name: string } },
): ReviewEdit[] | string {
  const old = new Map(before.map((edit) => [edit.itemIndex, edit]));
  const seen = new Set<number>();
  const out: ReviewEdit[] = [];
  const cell = <T>(
    value: T | null,
    prev:
      | { value: T; editedAt: string; editedBy: { id: number; name: string } }
      | null
      | undefined,
  ) => {
    if (value === null) return null;
    if (prev && same(prev.value, value)) return prev;
    return { value, editedAt: now.at, editedBy: { ...now.by } };
  };
  for (const want of wanted) {
    const item = result.items[want.itemIndex];
    if (item === undefined)
      return `문장 번호 ${want.itemIndex}은(는) 이 결과에 없어요(0부터 ${result.items.length - 1}까지)`;
    if (seen.has(want.itemIndex))
      return `고친 문장 번호 ${want.itemIndex}이(가) 두 번 왔어요`;
    seen.add(want.itemIndex);
    const cells = checkedEditCells(want, item);
    if (typeof cells === 'string') return cells;
    const prev = old.get(want.itemIndex);
    const edit: ReviewEdit = {
      itemIndex: want.itemIndex,
      level: cell(want.level === item.level ? null : want.level, prev?.level),
      reasonBullets: cell<readonly string[]>(
        cells.reasonBullets,
        prev?.reasonBullets,
      ),
      fixParagraph: cell(cells.fixParagraph, prev?.fixParagraph),
    };
    if (edit.level || edit.reasonBullets || edit.fixParagraph) out.push(edit);
  }
  return out.sort((a, b) => a.itemIndex - b.itemIndex);
}

/** 목록의 등급 수 = 효력 등급(고친 등급 ?? AI)으로 센 결과 items 전부(서버 checks levelCounts 와 같은 뜻). */
export function effectiveCounts(
  result: ScanResult,
  edits: readonly ReviewEdit[],
): LevelCounts {
  const counts = { ...result.counts.byLevel };
  for (const edit of edits) {
    const item = result.items[edit.itemIndex];
    if (edit.level === null || item === undefined) continue;
    counts[item.level] -= 1;
    counts[edit.level.value] += 1;
  }
  return counts;
}

/** 데모 모드의 한 걸음: 추출 → 판정(쪽 하나씩) → 정리 → 끝. */
export function step(progress: RunProgress): RunProgress {
  if (progress.state !== 'running') return progress;
  if (progress.stage === 'judge' && progress.judge.done < progress.judge.total)
    return {
      ...progress,
      judge: { ...progress.judge, done: progress.judge.done + 1 },
    };
  const at = RUN_STAGES.indexOf(progress.stage);
  const next = RUN_STAGES[at + 1];
  return next === undefined ?
      { ...progress, state: 'done' }
    : { ...progress, stage: next };
}
