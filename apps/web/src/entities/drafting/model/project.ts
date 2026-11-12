// 원고작성 프로젝트·실행 꼴과 목록 상태 셈(밴드 RPW1 ① — 발주서 §2-0 ③). 꼴은 openapi 의 DraftingProject·DraftingProjectListItem·
//   DraftingRunItem 그대로(api/contract 의 거울이 이 꼴을 지킨다 — 서버 칸 밖은 없다). React·DOM·통신을 모른다.
// 상태는 서버 사실로만 가른다(§2-0 ③): PDF 올리기 전 · 목차 설정 전 · 초안 전 · 만드는 중 n/m(latestRun.progress) · 초안 완료 ·
//   일부 못 만듦 · 목차 바뀜 · 실패(failed·rejected). 시안의 「읽기 실패」는 목록 못 불러옴(CM-03) 자리다(행 상태가 아니다).

export type RunStatus = 'queued' | 'processing' | 'done' | 'failed';

/** 실행 진행(RPS1 — processing 만 값, 그 밖 null). */
export interface RunProgress {
  step: string;
  done: number | null;
  total: number | null;
}

/** 잎 셈(RPS1 — done ∧ @3 결과만, 그 밖 null). */
export interface RunLeaves {
  total: number;
  drafted: number;
  noMaterial: number;
  failed: number;
  notRun: number;
}

/** 프로젝트의 실행 한 줄(DraftingRunItem). */
export interface RunItem {
  id: number;
  status: RunStatus;
  createdAt: string;
  finishedAt: string | null;
  outlineId: number | null;
  baseRunId: number | null;
  rebuild: string[];
  progress: RunProgress | null;
  rejected: boolean | null;
  leaves: RunLeaves | null;
}

export interface RunPage {
  count: number;
  isNext: boolean;
  results: RunItem[];
}

/** 목록 한 줄(DraftingProjectListItem). */
export interface ProjectRow {
  id: number;
  name: string;
  year: number;
  createdAt: string;
  hasDocument: boolean;
  documentName: string | null;
  outlineId: number | null;
  outlineRevision: number | null;
  latestRun: RunItem | null;
}

export interface ProjectPage {
  count: number;
  isNext: boolean;
  results: ProjectRow[];
}

/** 목차 마디(drafting.outline@1). */
export interface OutlineNode {
  key: string;
  parentKey: string | null;
  depth: number;
  title: string;
  requirement: string;
}

/** 프로젝트 하나(DraftingProject). */
export interface Project {
  id: number;
  name: string;
  year: number;
  createdAt: string;
  createdByUserId: number;
  /** 서버 칸 `document` — 거울(api/contract)이 `pdf` 로 옮겨 싣는다(model 은 DOM 낱말을 쓰지 않는다 — 영문번역 batch.ts 꼴). */
  pdf: {
    documentId: number;
    kind: string;
    attachedAt: string;
    attachedByUserId: number;
  } | null;
  outline: {
    outlineId: number;
    revision: number;
    sha256: string;
    outline: { nodes: OutlineNode[] };
  } | null;
  latestRun: RunItem | null;
}

/** 목록 행의 상태(§2-0 ③). */
export type ProjectState =
  | 'no_document'
  | 'no_outline'
  | 'no_draft'
  | 'drafting'
  | 'done'
  | 'partial'
  | 'outline_changed'
  | 'failed';

/** 상태마다 「다음 할 일」 하나가 가는 곳. */
export type NextStep =
  { to: 'upload' } | { to: 'outline' } | { to: 'run'; runId: number };

export interface RowView {
  state: ProjectState;
  /** 만드는 중 n/m — progress 가 둘 다 값일 때만. */
  progress: { done: number; total: number } | null;
  /** 「목차 · 초안」 칸 — 초안이 있는 목차 수 / 초안 지을 목차 수(잎 셈이 없으면 null = 「—」). 초안 단계 진행 중이면 그 단계의 처리 수 / 전체. */
  leaves: { drafted: number; total: number } | null;
  next: NextStep;
}

/** 목록 행 → 상태·진행·잎 셈·다음 할 일. */
export function rowViewOf(row: ProjectRow): RowView {
  const run = row.latestRun;
  const leaves =
    run?.leaves ?
      { drafted: run.leaves.drafted, total: run.leaves.total }
    : null;
  if (!row.hasDocument)
    return {
      state: 'no_document',
      progress: null,
      leaves,
      next: { to: 'upload' },
    };
  if (row.outlineId === null)
    return {
      state: 'no_outline',
      progress: null,
      leaves,
      next: { to: 'outline' },
    };
  if (run === null)
    return {
      state: 'no_draft',
      progress: null,
      leaves,
      next: { to: 'outline' },
    };
  const next: NextStep = { to: 'run', runId: run.id };
  if (run.status === 'queued' || run.status === 'processing') {
    const p = run.progress;
    const progress =
      p && p.done !== null && p.total !== null ?
        { done: p.done, total: p.total }
      : null;
    const counting =
      p?.step === 'draft' && progress ?
        { drafted: progress.done, total: progress.total }
      : leaves;
    return { state: 'drafting', progress, leaves: counting, next };
  }
  if (run.status === 'failed' || run.rejected === true)
    return { state: 'failed', progress: null, leaves, next };
  // 실행의 판을 모르면(versions 에 없는 옛 실행 — outlineId null) 바뀌었다고 말하지 않는다(검증 R2).
  if (run.outlineId !== null && run.outlineId !== row.outlineId)
    return { state: 'outline_changed', progress: null, leaves, next };
  if (run.leaves && run.leaves.failed + run.leaves.notRun > 0)
    return { state: 'partial', progress: null, leaves, next };
  return { state: 'done', progress: null, leaves, next };
}

/** 목록 거르기 탭(시안 「전체 · 준비 중 · 만드는 중 · 초안 완료 · 실패」). */
export type ProjectFilter =
  'all' | 'preparing' | 'drafting' | 'done' | 'failed';
export const PROJECT_FILTERS: readonly ProjectFilter[] = [
  'all',
  'preparing',
  'drafting',
  'done',
  'failed',
];

const FILTER_STATES: Record<
  Exclude<ProjectFilter, 'all'>,
  readonly ProjectState[]
> = {
  preparing: ['no_document', 'no_outline', 'no_draft'],
  drafting: ['drafting'],
  done: ['done', 'partial', 'outline_changed'],
  failed: ['failed'],
};

/** 그 거르기에 드는 상태인가. */
export const inFilter = (filter: ProjectFilter, state: ProjectState) =>
  filter === 'all' || FILTER_STATES[filter].includes(state);

/** 목록의 보고연도 고름(줄에 있는 해 — 큰 해 먼저). */
export const yearsOfRows = (rows: readonly ProjectRow[]): number[] =>
  [...new Set(rows.map((row) => row.year))].sort((a, b) => b - a);

/** 시각 글자 → 한국 날짜 「YYYY-MM-DD」(못 읽으면 글자 그대로). */
export function dayOf(iso: string): string {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return iso;
  return new Date(time + 9 * 3_600_000).toISOString().slice(0, 10);
}

/** 시각 글자 → 한국 시각 「YYYY-MM-DD HH:MM」(못 읽으면 글자 그대로). */
export function minuteOf(iso: string): string {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return iso;
  return new Date(time + 9 * 3_600_000)
    .toISOString()
    .slice(0, 16)
    .replace('T', ' ');
}

/** 목록 검색 — 이름·전년도 보고서 파일 이름에 그 글이 있는가(앞뒤 공백 걷음, 대소문자 무시). 빈 글은 다 든다. */
export function matchesQuery(row: ProjectRow, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (needle === '') return true;
  return [row.name, row.documentName ?? ''].some((text) =>
    text.toLowerCase().includes(needle),
  );
}

/** 실행 단계 하나(RunOut.steps — extract·map·draft·report). */
export interface RunStep {
  step: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  done: number | null;
  total: number | null;
}

/** GET /runs/{id} 를 원고작성 꼴로(errorCode·message 는 싣지 않는다 — 화면 0). */
export interface RunState {
  id: number;
  status: RunStatus;
  steps: RunStep[];
  /** 그 실행의 옵션(drafting.options@2 거울을 지난 것만 — 아니면 null). */
  projectId: number | null;
  base: { runId: number; rebuild: string[] } | null;
}
