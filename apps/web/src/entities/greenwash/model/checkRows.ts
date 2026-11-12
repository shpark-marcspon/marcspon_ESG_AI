// 문서 목록(GW-01)의 줄 짓기와 거르기(밴드 FW2 ①, 메모 gw-a-01a~d [R11]). 순수 함수만.
//   - 판 사슬(previousDocumentId)의 마지막 문서만 한 줄(gw-a-01b). 앞 판 수 = 사슬에서 그 앞에 있는 문서 수(목록에 있는 것만).
//   - 줄 = 문서 + 마지막 실행. 상태 하나(AI 점검 중 n% · 멈춤 · 검토 대기 · 검토 중 n/전체 · 검토 완료)와 다음 할 일 하나
//     (진행 보기 · 다시 실행 · 검토하기 · 검토 이어 하기 · 결과 보기).
//   - 회차 = 그 문서의 실행 차례(만든 시각 차례, 1부터. gw-a-01c, GW-04 meta 「n회차」).
//   - 거르기: 문서명 검색(대소문자 무시, 앞뒤 공백 지움), 보고연도, 상태 탭 여섯(전체 · AI 점검 중 · 검토 대기 · 검토 중 · 검토 완료 · 멈춤),
//     내가 올린 것만(서버 짝 uploadedBy [R3]).
// 차례: 마지막 실행(없으면 올린 때)이 늦은 줄이 위. 시각은 ISO 8601 을 Date.parse 로 순간끼리 견준다(오프셋이 달라도 맞다 — 밴드 FW2 ⑤).
//   읽을 수 없는 시각이 섞이면 그 둘만 글자로 견준다.
import { overallPercent } from './progress.ts';
import type { RunProgress } from './progress.ts';
import type { LevelCounts, ReviewState } from './result.ts';

export interface ListedDocument {
  documentId: string;
  fileName: string;
  reportYear: number | null;
  /** 수정본이면 앞 판 문서 id. */
  previousDocumentId: string | null;
  /** 쪽 수. 모르면 null(화면은 「–」 — 밴드 GW1R ② Q2). */
  pageCount: number | null;
  /** 올린 때(ISO 8601). */
  uploadedAt: string;
  uploadedBy: { userId: string; name: string };
}

export interface ListedRun {
  runId: string;
  documentId: string;
  /** 만든 때(ISO 8601). */
  createdAt: string;
  /** 끝난 때(+09:00 ISO 8601 — checks@1 runs[].finishedAt, done·failed 일 때만). 없거나 null 이면 끝나지 않음·모름(GCB1). */
  finishedAt?: string | null;
  progress: RunProgress;
  /** 결과의 등급별 수(끝난 실행만). */
  levelCounts: LevelCounts | null;
  /** 검토 상태(끝난 실행만). reviewed/total 은 표시 수/문장 수. */
  review: {
    state: ReviewState;
    reviewed: number;
    total: number;
    confirmedAt: string | null;
    /** 확정한 사람의 이름(검토 greenwash.review@3 의 confirmedBy.name. 확정 전이면 null). */
    confirmedBy: string | null;
  } | null;
  /**
   * 실행 실패의 code(서버 greenwash.checks@1 의 runs[].errorCode — 검증 G1e 가 더하는 칸이라 없을 수 있다, 밴드 GW1R Q8).
   * 없거나 null 이면 모름. `no_text_layer` 면 GW-01 실패 줄에 [다시 실행]이 없다(디자인 원문 2).
   */
  errorCode?: string | null;
}

/** 목록 줄의 원재료(GreenwashStore.listCheckRows). */
export interface CheckRowsSource {
  /** 지금 사용자 id(「내가 올린 것만」). */
  currentUserId: string;
  /** 회사 이름(제목 줄 meta). */
  companyName: string;
  documents: readonly ListedDocument[];
  runs: readonly ListedRun[];
}

export type CheckRowStatus =
  'running' | 'failed' | 'pending' | 'in_review' | 'confirmed';

export type NextAction =
  'view_progress' | 'rerun' | 'review' | 'continue_review' | 'view_result';

export interface CheckRow {
  doc: ListedDocument;
  /** 판 차례(1부터 — 사슬 길이). 1 이면 새 문서. */
  version: number;
  /** 앞 판 수(목록에 있는 것만). */
  previousVersionCount: number;
  lastRun: ListedRun | null;
  /** 마지막 실행의 회차(그 문서의 실행 수). 실행이 없으면 0. */
  runOrdinal: number;
  /** 실행이 없으면 null. */
  status: CheckRowStatus | null;
  /** AI 점검 중이면 전체 진행률. */
  percent: number | null;
  next: NextAction | null;
}

/** 실행의 회차(그 문서의 실행 가운데 만든 차례, 1부터). 없는 실행이면 0. */
export function runOrdinal(runs: readonly ListedRun[], runId: string): number {
  const run = runs.find((r) => r.runId === runId);
  if (!run) return 0;
  return (
    byCreated(runs.filter((r) => r.documentId === run.documentId)).findIndex(
      (r) => r.runId === runId,
    ) + 1
  );
}

const byCreated = (runs: readonly ListedRun[]) =>
  [...runs].sort((a, b) => compareTime(a.createdAt, b.createdAt));
/** ISO 8601 두 시각의 차례(순간끼리). 하나라도 읽을 수 없으면 글자 비교. */
const compareTime = (a: string, b: string) => {
  const ta = Date.parse(a);
  const tb = Date.parse(b);
  if (!Number.isNaN(ta) && !Number.isNaN(tb)) return ta - tb;
  return (
    a < b ? -1
    : a > b ? 1
    : 0
  );
};

export function runStatusOf(run: ListedRun): CheckRowStatus {
  if (run.progress.state === 'running') return 'running';
  if (run.progress.state === 'failed') return 'failed';
  return run.review?.state ?? 'pending';
}

export const NEXT_ACTION: Readonly<Record<CheckRowStatus, NextAction>> = {
  running: 'view_progress',
  failed: 'rerun',
  pending: 'review',
  in_review: 'continue_review',
  confirmed: 'view_result',
};

/** 목록 줄. 판 사슬의 마지막 문서만, 늦은 차례. */
export function buildCheckRows(source: CheckRowsSource): CheckRow[] {
  const byId = new Map(source.documents.map((d) => [d.documentId, d]));
  const superseded = new Set(
    source.documents
      .map((d) => d.previousDocumentId)
      .filter((id): id is string => id !== null && byId.has(id)),
  );
  const rows = source.documents
    .filter((d) => !superseded.has(d.documentId))
    .map((doc): CheckRow => {
      const previousVersionCount = chainLength(doc, byId) - 1;
      const runs = byCreated(
        source.runs.filter((r) => r.documentId === doc.documentId),
      );
      const lastRun = runs.at(-1) ?? null;
      const status = lastRun ? runStatusOf(lastRun) : null;
      return {
        doc,
        version: previousVersionCount + 1,
        previousVersionCount,
        lastRun,
        runOrdinal: runs.length,
        status,
        percent:
          lastRun && status === 'running' ?
            overallPercent(lastRun.progress)
          : null,
        next: status ? NEXT_ACTION[status] : null,
      };
    });
  return rows.sort((a, b) => compareTime(activity(b), activity(a)));
}

const activity = (row: CheckRow) =>
  row.lastRun?.createdAt ?? row.doc.uploadedAt;

/** 사슬 길이(자기 포함). 목록에 없는 앞 판에서 멈추고, 고리가 있으면 한 바퀴에서 멈춘다. */
function chainLength(
  start: ListedDocument,
  byId: ReadonlyMap<string, ListedDocument>,
): number {
  const seen = new Set<string>([start.documentId]);
  let at = start;
  while (at.previousDocumentId !== null) {
    const previous = byId.get(at.previousDocumentId);
    if (!previous || seen.has(previous.documentId)) break;
    seen.add(previous.documentId);
    at = previous;
  }
  return seen.size;
}

/**
 * 상태 탭 여섯(시안 댓글 1차 반영 — sid:MARC-ENT-603): 전체 · AI 점검 중 · 검토 대기 · 검토 중 · 검토 완료 · 멈춤.
 * 옛 한 탭 「점검 중·멈춤」(running_failed, [N5])을 둘로 나눴다. 멈춤은 맨 끝 별도 탭. 거르기는 웹 안(줄 상태)이라 서버 값은 그대로다.
 */
export const CHECK_ROW_TABS = [
  'all',
  'running',
  'pending',
  'in_review',
  'confirmed',
  'failed',
] as const;
export type CheckRowTab = (typeof CHECK_ROW_TABS)[number];

export interface CheckRowFilter {
  query: string;
  reportYear: number | null;
  tab: CheckRowTab;
  mineOnly: boolean;
}

export function filterCheckRows(
  rows: readonly CheckRow[],
  filter: CheckRowFilter,
  currentUserId: string,
): CheckRow[] {
  const query = filter.query.trim().toLowerCase();
  return rows.filter(
    (row) =>
      (query === '' || row.doc.fileName.toLowerCase().includes(query)) &&
      (filter.reportYear === null ||
        row.doc.reportYear === filter.reportYear) &&
      (!filter.mineOnly || row.doc.uploadedBy.userId === currentUserId) &&
      inTab(row.status, filter.tab),
  );
}

function inTab(status: CheckRowStatus | null, tab: CheckRowTab): boolean {
  if (tab === 'all') return true;
  return status === tab;
}
