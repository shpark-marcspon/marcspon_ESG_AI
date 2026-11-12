// 실행 상세의 꼴과 순수 함수(밴드 AD4W — AD-04a, 서버 AD4D 의 GET /run-logs/{run_id}). React·DOM·통신을 모른다.
// 계약 타입(RunLogDetailOut)은 shared/api 가 다시 내보낸 것을 타입으로만 가져온다.
//   - 문서 두 칸(documentId·documentName)은 generated 가 `| null` 로 낸다(ND1 sid:MARC-TICK-236 — 문서 없는 실행). 웹 넓힘 사본은 걷었다(ND1W).
//   - 단계 숫자: 단계 기록이 없는 실행(stepUsageRecorded 거짓)·null·AI 를 부르지 않은 단계(토큰 0 · 비용 0)는 토큰·비용 빈 값(감독 처분 Q6 (가)).
//   - 표시 글은 글자를 넣어 받는다(model 은 문구 표를 모른다 — 화면이 RUN_LOG_TEXT 를 넣는다).
//   - 결과 파일(밴드 AD4P): 흐름 출력(step null)과 이름이 같은 단계 중간 파일은 한 줄로 접고(shownFiles — 디자인 2e 답 ⓑ, 모든 모듈 같은 규칙),
//     [내려받기]는 흐름 출력 줄이면서 실패 실행이 아닐 때만(downloadable — 시안 v138).
import type { Schemas } from '../../../shared/api/index.ts';
import { costText, durationText, formatRunTime, withCommas } from './run.ts';

/** GET /run-logs/{run_id} 의 답(계약 그대로). */
export type RunLogDetail = Schemas['RunLogDetailOut'];
/** 단계 하나(선언 차례). */
export type RunLogStep = Schemas['RunLogStepOut'];
/** 단계 상태(서버 값 그대로). */
export type RunStepStatus = RunLogStep['status'];
/** 결과 파일 하나(step null = 흐름의 출력 — GET /run-logs/{run_id}/files/{name} 로 받는다, RF1W). */
export type RunLogFile = Schemas['RunLogFileOut'];

/** 단계 상태 넷(대기·처리 중·완료·실패). 계약 enum 과 집합이 같다(model 시험). */
export const RUN_STEP_STATUSES = [
  'pending',
  'running',
  'done',
  'failed',
] as const satisfies readonly RunStepStatus[];

/** 짧은 시간 글: 60초 미만 「42초」, 이상은 목록 꼴(durationText — 「1분 05초」·「5분 31초」, 판 AD-04a 단계 칸). null 이면 null. */
export function shortDurationText(seconds: number | null): string | null {
  if (seconds === null) return null;
  return seconds < 60 ? `${seconds}초` : durationText(seconds);
}

/** 단계 줄의 숫자 칸 셋(시간·토큰·비용). */
export function stepFigures(
  step: Pick<RunLogStep, 'durationSec' | 'tokens' | 'costUsd'>,
  recorded: boolean,
  words: { empty: string; costBelow: string },
): { duration: string; tokens: string; cost: string } {
  const duration = shortDurationText(step.durationSec) ?? words.empty;
  if (!recorded || step.tokens === null || step.costUsd === null)
    return { duration, tokens: words.empty, cost: words.empty };
  if (step.tokens === 0 && step.costUsd === 0)
    return { duration, tokens: words.empty, cost: words.empty };
  return {
    duration,
    tokens: withCommas(step.tokens),
    cost: costText(step.costUsd, words.costBelow),
  };
}

/** 단계 이름: 문구 표(모듈 → 단계 → 글)에 있으면 그 글, 없으면 서버 이름 그대로. */
export function stepLabel(
  module: string,
  name: string,
  labels: Readonly<Record<string, Readonly<Record<string, string>>>>,
): string {
  if (!Object.hasOwn(labels, module)) return name;
  const steps = labels[module]!;
  return Object.hasOwn(steps, name) ? steps[name]! : name;
}

/** 시각 칸의 두 토막(시작 = startedAt — 처음 잡힌 때): 시작 「YYYY-MM-DD HH:MM」, 끝 「HH:MM」(날짜가 다르면 날짜까지). 없으면 null. */
export function detailTimes(
  detail: Pick<RunLogDetail, 'startedAt' | 'finishedAt'>,
): { start: string | null; end: string | null } {
  const { startedAt, finishedAt } = detail;
  const start = startedAt === null ? null : formatRunTime(startedAt);
  if (finishedAt === null) return { start, end: null };
  const sameDay =
    startedAt !== null && startedAt.slice(0, 10) === finishedAt.slice(0, 10);
  return {
    start,
    end: sameDay ? finishedAt.slice(11, 16) : formatRunTime(finishedAt),
  };
}

/** 보일 결과 파일: 흐름 출력(step null)과 이름이 같은 단계 중간 파일 줄을 뺀다. 이름이 다른 중간 파일은 남기고 차례는 받은 그대로. */
export function shownFiles(files: readonly RunLogFile[]): RunLogFile[] {
  const outputs = new Set(
    files.filter((file) => file.step === null).map((file) => file.name),
  );
  return files.filter((file) => file.step === null || !outputs.has(file.name));
}

/** 그 줄에 [내려받기]를 다는가: 흐름 출력이고 실패 실행이 아닐 때만(실패 실행은 결과 파일이 없다 — 시안 v138). */
export function downloadable(
  detail: Pick<RunLogDetail, 'status'>,
  file: Pick<RunLogFile, 'step'>,
): boolean {
  return file.step === null && detail.status !== 'failed';
}
