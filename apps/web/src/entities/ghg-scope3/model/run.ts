// Scope 3 실행의 꼴과 갈래(밴드 S3W1 ①). 실행은 core 의 POST /runs·GET /runs/{id}(generated RunOut). 결과 본문은 result.ts(S3W2a).
import type { RunStep } from './runProgress.ts';

/** 모듈 id. */
export const SCOPE3_MODULE = 'inventory.scope3';

/** 1차 흐름(sid:MARC-ENT-442 — 코랩 그대로). 서버 기본 흐름은 아직 llm-first 라 늘 싣는다. */
export const SCOPE3_FLOW_ID = 'scope3.colab@157';

/** RunOut.status 그대로(generated). */
export type RunStatus = 'queued' | 'processing' | 'done' | 'failed';

/** 화면이 읽는 실행 하나(GET /runs/{id} 에서 고른 칸). id 는 글자다. */
export interface Scope3Run {
  id: string;
  status: RunStatus;
  documentId: string | null;
  flowId: string;
  /** options.reportYear(정수가 아니면 null). */
  reportYear: number | null;
  /** 받은 options 그대로(다시 계산이 고치지 않고 싣는다). */
  options: Record<string, unknown>;
  createdAt: string;
  finishedAt: string | null;
  errorCode: string | null;
  /** 서버 단계(꼴이 틀린 낱개는 뺀 것). 진행 표시만 쓴다. */
  steps: readonly RunStep[];
}

/** 화면의 갈래: 진행(queued·processing) · 완료(done) · 실패(failed) · 그 밖 모름. */
export type RunPhase = 'running' | 'done' | 'failed' | 'unknown';

export function runPhase(status: unknown): RunPhase {
  switch (status) {
    case 'queued':
    case 'processing':
      return 'running';
    case 'done':
      return 'done';
    case 'failed':
      return 'failed';
    default:
      return 'unknown';
  }
}

/**
 * 실패 글의 갈래(발주서 §1-6 표). errorMessage 는 말투가 다르고 step_error 에 여러 뜻이 접혀 화면에 싣지 않는다 — errorCode 로만 가른다.
 * setup 설정 없음(mock 배포본은 늘 이것) · file 올린 파일을 못 읽음(같은 문서로 다시 계산해도 소용없음) · transient 일시적 · general 그 밖·모르는 글자.
 */
export type FailureKind = 'setup' | 'file' | 'transient' | 'general';

const FAILURE_KINDS: Readonly<Record<string, FailureKind>> = {
  setup_error: 'setup',
  document_missing: 'file',
  object_missing: 'file',
  object_changed: 'file',
  object_too_large: 'file',
  attempts_exhausted: 'transient',
  internal: 'transient',
};

export function failureKind(code: string | null): FailureKind {
  if (code === null || !Object.hasOwn(FAILURE_KINDS, code)) return 'general';
  return FAILURE_KINDS[code]!;
}

/** Step 1~4(판 S3-01). */
export const STEP_KEYS = [
  'start',
  'categories',
  'upload',
  'calculate',
] as const;
export type StepKey = (typeof STEP_KEYS)[number];

/** 화면이 선 자리: 처음 · 카테고리 고름 · 올림 · 계산 중(실패·잃음 포함 — 올리기까지 마친 사실은 그대로, 값 파일 GX3 s2) · 계산 끝(「완료 했을시」). */
export type Scope3Stage = 'idle' | 'categories' | 'upload' | 'running' | 'done';

/** 자리마다 Step 넷의 끝남. 「완료 했을시」(판 S3-01a)는 끝낸 Step 까지 완료 표시. */
export function steps(stage: Scope3Stage): { key: StepKey; done: boolean }[] {
  const doneCount =
    stage === 'idle' ? 0
    : stage === 'categories' ? 1
    : stage === 'upload' ? 2
    : stage === 'running' ? 3
    : 4;
  return STEP_KEYS.map((key, index) => ({ key, done: index < doneCount }));
}
