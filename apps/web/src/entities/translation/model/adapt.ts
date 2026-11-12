// 묶음(translation.batch@1) → 화면 꼴(밴드 TRW1a ①). 순수 함수 — 부품 props(BatchTable·PartTabs·StageCard)의 재료를 짓는다.
// 글은 짓지 않는다(model 은 config 를 모른다 — 칸 규칙): 스타일은 열쇠(A·B·AB), 시각은 shared/lib/time 의 꼴, 없음은 null.
// 잇기 표(발주서 TRW1-order §2-1):
//   파트      ceo_message ↔ ceo · story · general
//   상태      queued → queued · processing → running · failed → failed · done 이고 요약 outcome rejected → failed ·
//             partial → failed_partial · done(또는 요약 없는 옛 done) → done
//   까닭      요약 rejectionKind: no_pages → no_pages · ceo_page_limit → ceo_over_limit · unsupported_input → bad_file ·
//             too_large → too_large · over_budget → over_budget · retry_source_* → 없음(일반 실패 꼴 — 판에 글 없음)
//   단계      서버 단계 prepare·translate·report → StageCard 의 1·2·3. 쪽 진행은 translate 단계의 done/total(둘 다 수일 때만).
//   회차      latest = round, earlier[i](새 것 먼저) = round - 1 - i.
import { formatKst, formatKstTime } from '../../../shared/lib/time.ts';
import type {
  BatchEarlier,
  BatchRun,
  BatchStep,
  Outcome,
  RunStatus,
  ServerPart,
  ServerRejectionKind,
  TranslationBatch,
} from './batch.ts';
import type { PartKey } from './parts.ts';
import { formatRange } from './range.ts';
import type { Range } from './range.ts';
import type { RejectionKey, TabState } from './status.ts';

const TO_KEY: Readonly<Record<ServerPart, PartKey>> = {
  ceo_message: 'ceo',
  story: 'story',
  general: 'general',
};
const TO_SERVER: Readonly<Record<PartKey, ServerPart>> = {
  ceo: 'ceo_message',
  story: 'story',
  general: 'general',
};

/** 서버 파트 → 화면 파트. */
export const partKeyOf = (part: ServerPart): PartKey => TO_KEY[part];
/** 화면 파트 → 서버 파트. */
export const serverPartOf = (part: PartKey): ServerPart => TO_SERVER[part];

const REJECTION: Readonly<
  Record<ServerRejectionKind, RejectionKey | undefined>
> = {
  no_pages: 'no_pages',
  ceo_page_limit: 'ceo_over_limit',
  unsupported_input: 'bad_file',
  too_large: 'too_large',
  over_budget: 'over_budget',
  retry_source_not_found: undefined,
  retry_source_mismatch: undefined,
};

/** 실행 상태 + 요약 outcome → 탭 상태. */
export function tabStateOf(
  status: RunStatus,
  outcome: Outcome | null,
): TabState {
  switch (status) {
    case 'queued':
      return 'queued';
    case 'processing':
      return 'running';
    case 'failed':
      return 'failed';
    case 'done':
      return (
        outcome === 'rejected' ? 'failed'
        : outcome === 'partial' ? 'failed_partial'
        : 'done'
      );
  }
}

/** 최신 실행 → 탭 상태(요약이 없으면 outcome 모름 — done 은 done). */
export const runStateOf = (run: BatchRun): TabState =>
  tabStateOf(run.status, run.digest?.outcome ?? null);

/** 막은 까닭(done 이고 요약이 거절일 때만). 판에 글이 없는 갈래는 없음. */
export function rejectionKeyOf(run: BatchRun): RejectionKey | undefined {
  if (run.status !== 'done' || run.digest?.status !== 'rejected')
    return undefined;
  const kind = run.digest.rejectionKind;
  return kind === null ? undefined : REJECTION[kind];
}

/** 옵션의 쪽 범위 → 구간(양끝이 다 수일 때만 — 웹이 늘 둘 다 싣는다). */
export function rangeOf(run: BatchRun): Range | null {
  const pages = run.pages;
  if (pages === null || pages.start === null || pages.end === null) return null;
  return { from: pages.start, to: pages.end };
}

const STAGE_STEPS = ['prepare', 'translate', 'report'] as const;
export type StageState = 'done' | 'now' | 'todo' | 'failed';
const STAGE_OF: Readonly<Record<BatchStep['status'], StageState>> = {
  done: 'done',
  running: 'now',
  pending: 'todo',
  failed: 'failed',
};

/** 번역 단계의 쪽 진행(done·total 이 다 수일 때만). */
export function pageProgressOf(
  run: BatchRun,
): { done: number; total: number } | undefined {
  const step = run.steps.find((s) => s.step === 'translate');
  if (!step || step.done === null || step.total === null) return undefined;
  return { done: step.done, total: step.total };
}

/** StageCard 의 재료: 단계 셋의 상태와 지금 단계(처음으로 끝나지 않은 단계, 다 끝났으면 3). */
export function stageOf(run: BatchRun): {
  stageIndex: 1 | 2 | 3;
  stages: [StageState, StageState, StageState];
} {
  const stages = STAGE_STEPS.map((name) => {
    const step = run.steps.find((s) => s.step === name);
    return step ? STAGE_OF[step.status] : 'todo';
  }) as [StageState, StageState, StageState];
  const at = stages.findIndex((stage) => stage !== 'done');
  return { stageIndex: (at === -1 ? 3 : at + 1) as 1 | 2 | 3, stages };
}

export type StyleKey = 'A' | 'B' | 'AB';
/** 옵션 문체 → 열쇠(꼴이 어긋난 옛 실행이면 null). */
export function styleKeyOf(run: BatchRun): StyleKey | null {
  if (run.style === null) return null;
  return run.style.compareAb ? 'AB' : run.style.single;
}

/** 파트 하나의 화면 꼴. */
export interface PartView {
  part: PartKey;
  runId: string;
  range: Range | null;
  /** 「4~41」(범위를 모르면 null). */
  rangeText: string | null;
  round: number;
  /** 시작 시각(보이는 글 — 아직 시작 전이면 만든 시각). */
  started: string;
  finished?: string;
  /** 시작·끝남의 시각만(「11:48」 — [전체] 탭 파트별 표, 밴드 TRP2 TC22). */
  startedTime: string;
  finishedTime?: string;
  state: TabState;
  reason?: RejectionKey;
  pages?: { done: number; total: number };
  earlier: { round: number; state: TabState; at: string }[];
  style: StyleKey | null;
  /** 고객사 용어집 짝 수(옵션 final). */
  glossaryCount: number;
  run: BatchRun;
}

const earlierOf = (round: number, earlier: readonly BatchEarlier[]) =>
  earlier.map((run, index) => ({
    round: round - 1 - index,
    state: tabStateOf(run.status, run.outcome),
    at: formatKst(run.finishedAt ?? run.createdAt),
  }));

export function partViewOf(part: TranslationBatch['parts'][number]): PartView {
  const run = part.latest;
  const range = rangeOf(run);
  const state = runStateOf(run);
  const reason = rejectionKeyOf(run);
  const pages = state === 'running' ? pageProgressOf(run) : undefined;
  return {
    part: partKeyOf(part.part),
    runId: String(run.runId),
    range,
    rangeText: range === null ? null : formatRange(range),
    round: part.round,
    started: formatKst(run.startedAt ?? run.createdAt),
    ...(run.finishedAt === null ? {} : { finished: formatKst(run.finishedAt) }),
    startedTime: formatKstTime(run.startedAt ?? run.createdAt),
    ...(run.finishedAt === null ?
      {}
    : { finishedTime: formatKstTime(run.finishedAt) }),
    state,
    ...(reason === undefined ? {} : { reason }),
    ...(pages === undefined ? {} : { pages }),
    earlier: earlierOf(part.round, part.earlier),
    style: styleKeyOf(run),
    glossaryCount: run.glossaryCounts.final,
    run,
  };
}

/** 묶음 하나의 화면 꼴(목록 줄·묶음 화면). */
export interface BatchView {
  /** 목록 줄 열쇠(batchRowId). */
  rowId: string;
  documentId: string;
  batchKey: string;
  fileName: string;
  /** 올린 시각(보이는 글 — 올림을 안 마쳤으면 null). */
  uploaded: string | null;
  uploader: string;
  /** 파트 최신 실행 가운데 가장 늦게 만든 때(보이는 글). */
  lastStarted: string;
  /** 첫 파트의 문체(파트끼리 같다 — [번역 시작] 한 번의 옵션). */
  style: StyleKey | null;
  parts: PartView[];
}

/** 목록 줄 열쇠: 「문서 id/묶음 열쇠」(묶음 열쇠에 「/」가 없다 — BATCH_KEY_PATTERN). */
export const batchRowId = (documentId: string, batchKey: string) =>
  `${documentId}/${batchKey}`;
/** 목록 줄 열쇠 → 문서 id·묶음 열쇠(꼴이 아니면 null). */
export function splitBatchRowId(
  rowId: string,
): { documentId: string; batchKey: string } | null {
  const at = rowId.indexOf('/');
  if (at <= 0 || at === rowId.length - 1) return null;
  return { documentId: rowId.slice(0, at), batchKey: rowId.slice(at + 1) };
}

export function batchViewOf(batch: TranslationBatch): BatchView {
  const parts = batch.parts.map(partViewOf);
  const documentId = String(batch.file.id);
  const latest = batch.parts
    .map((part) => part.latest.createdAt)
    .sort((a, b) => Date.parse(b) - Date.parse(a))[0];
  return {
    rowId: batchRowId(documentId, batch.batchKey),
    documentId,
    batchKey: batch.batchKey,
    fileName: batch.file.fileName,
    uploaded:
      batch.file.uploadedAt === null ? null : formatKst(batch.file.uploadedAt),
    uploader: batch.file.uploadedBy.name,
    lastStarted: latest === undefined ? '' : formatKst(latest),
    style: parts[0]?.style ?? null,
    parts,
  };
}
