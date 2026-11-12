// RP-04 개조식 초안 — 실행 진행(밴드 RPW1 ②, 시안 v188 RP-04_r1 「만드는 중」 — 발주서 §2-2). 라우터를 모른다. done 이면 결과 세 칸(ResultView — 경계 ③).
// GET /runs/{id} 를 pollMs 마다 다시 읽고 done·failed 에서 멈춘다(읽기 실패 한두 번은 앞 보기 그대로 다시 읽고, 연달아 셋이면 실패 화면). 주소의 프로젝트와 실행 옵션의 projectId 가 다르면 찾지 못함(§1-4 ⑥).
// 진행 줄 셋(§2-0 ④): extract 「전년도 보고서 읽는 중」(수 없음) · map(수 없음 — 서버 셈이 묶음 단위, RPQ1) · draft(「목차 n/m」 + 막대 — 잎 단위, 둘 다 값일 때만). report 단계는 줄로 두지 않는다.
//   줄 앞: 완료 초록 체크 · 진행 주황 번호 · 그 밖 회색 번호 · 이름 아래 설명 한 줄(RPW2 d:진행).
// base 실행(앞 실행 위에 일부 목차만 다시 짓기)은 진행 카드 없이 앞 실행의 결과(단추 끔 · 다시 짓는 잎만 만드는 중 꼴)를 둔다(RPW2 D#6).
// 실행 고르기(경계 ④, 시안 「실행 n · <시각> · 지금」): 머리에 프로젝트의 실행 목록 — 고르면 그 실행의 RP-04 로. 못 읽으면 고르기만 숨긴다.
//   폭은 결과 머리와 같은 내용 폭(RPW3 D5) · base 실행 진행 중엔 결과 머리 안(결과 → 다시 짓는 중에 몸이 뛰지 않게).
//   전체 실행 진행·실패 머리(RunHead)도 결과 머리와 같은 줄 — 부제 + 고르기 + 셈(아는 값만). 값이 없으면 같은 높이 자리만(RPW4 E2).
// failed → 빨간 띠 「이번 실행은 만들지 못했어요」, 띠 아래 [전체 다시 만들기](POST /runs {projectId} — base 0). errorCode·서버 글은 싣지 않는다.
import { type ReactNode, useEffect, useRef, useState } from 'react';

import {
  CheckIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  DraftingStore,
  ReadOutcome,
} from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { useProject, useRead } from '../../../entities/drafting/hooks/index.ts';
import type {
  RunState,
  RunStep,
} from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리, 밴드 RPW5 #6).
import '../../../shared/ui/motion/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { leafCountOf } from '../model/index.ts';
import { ResultView } from './ResultView.tsx';
import { RunPicker } from './RunPicker.tsx';

const words = DR_TEXT.run;

/** 다시 읽는 사이(ms). */
export const POLL_MS = 2000;
/** 진행을 한 번 본 뒤 읽기 실패가 연달아 이만큼이면 실패 화면(그 아래는 앞 보기 그대로 다시 읽는다). */
export const POLL_MISSES = 3;

/** 진행 줄로 보이는 단계(차례 그대로). */
const SHOWN = ['extract', 'map', 'draft'] as const;
type ShownStep = (typeof SHOWN)[number];

export interface RunScreenProps {
  store: DraftingStore;
  /** 주소의 프로젝트·실행 id(정수가 아니면 null — 요청 없이 찾지 못함). */
  projectId: number | null;
  runId: number | null;
  operator: boolean;
  onList(): void;
  /** RP-03 목차 설정으로(주면 머리에 단추). */
  onOutline?(): void;
  /** 새 실행의 RP-04 로. */
  onRun(runId: number): void;
  /** 실행 고르기에서 고른 실행의 RP-04 로. */
  onPickRun(runId: number): void;
  /** 원본 PDF 를 여는 함수(틀이 pdf.js 를 넘긴다 — 시험은 가짜). */
  openPdf: OpenPdf;
  /** 다시 읽는 사이(시험이 줄인다). */
  pollMs?: number;
}

type View =
  | { state: 'loading' }
  | { state: 'ready'; run: RunState }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'not_found' }
  | { state: 'failed' };

const ended = (run: RunState) =>
  run.status === 'done' || run.status === 'failed';

/** 읽은 것 → 화면 상태(다른 프로젝트의 실행은 찾지 못함). */
function viewOf(outcome: ReadOutcome<RunState>, projectId: number): View {
  if (outcome.kind === 'ok')
    return outcome.value.projectId === projectId ?
        { state: 'ready', run: outcome.value }
      : { state: 'not_found' };
  if (outcome.kind === 'refused')
    return { state: 'refused', company: outcome.company };
  return { state: outcome.kind };
}

/** 실행을 읽고 끝날 때까지 다시 읽는다. */
function useRunPoll(
  store: DraftingStore,
  projectId: number | null,
  runId: number | null,
  pollMs: number,
): [View, () => void] {
  const [view, setView] = useState<View>(
    projectId === null || runId === null ?
      { state: 'not_found' }
    : { state: 'loading' },
  );
  const [round, setRound] = useState(0);
  useEffect(() => {
    if (projectId === null || runId === null) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let seen = false;
    let misses = 0;
    const tick = async () => {
      const next = viewOf(await store.getRun(runId), projectId);
      if (!alive) return;
      misses = next.state === 'failed' ? misses + 1 : 0;
      if (next.state === 'failed' && seen && misses < POLL_MISSES) {
        timer = setTimeout(() => void tick(), pollMs);
        return;
      }
      seen = seen || next.state === 'ready';
      setView(next);
      if (next.state === 'ready' && !ended(next.run))
        timer = setTimeout(() => void tick(), pollMs);
    };
    void tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [store, projectId, runId, pollMs, round]);
  return [
    view,
    () => {
      setView({ state: 'loading' });
      setRound((old) => old + 1);
    },
  ];
}

export function RunScreen({
  store,
  projectId,
  runId,
  operator,
  onList,
  onOutline,
  onRun,
  onPickRun,
  openPdf,
  pollMs = POLL_MS,
}: RunScreenProps) {
  const [view, retry] = useRunPoll(store, projectId, runId, pollMs);
  // 첫 불러오기: 제목 + STEP 띠 뒤 300ms 뒤 LoadSkeleton(sid:MARC-ENT-443 ①, 밴드 RPW5 #4).
  const skeleton = useDelayed(view.state === 'loading');
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<
    CompanyRefusal | 'start' | 'startFailed' | null
  >(null);
  const pressed = useRef(false);
  const companyText = operator ? DR_TEXT.companyOperator : DR_TEXT.company;
  const picker =
    projectId !== null && runId !== null ?
      <RunPicker
        store={store}
        projectId={projectId}
        runId={runId}
        onPick={onPickRun}
      />
    : null;

  const restartAll = async () => {
    if (pressed.current || projectId === null) return;
    pressed.current = true;
    setBusy(true);
    try {
      // 실패 실행의 목차 판은 RunState 에 없다 — null(같은 프로젝트의 다시 누름은 같은 열쇠, RPW2 C0).
      const started = await store.startRun({ projectId }, null);
      if (started.kind === 'ok') onRun(started.value.runId);
      else
        setRefused(
          started.kind === 'refused' ? started.company
          : started.kind === 'failed' ? 'startFailed'
          : 'start',
        );
    } finally {
      pressed.current = false;
      setBusy(false);
    }
  };

  return (
    <div data-screen="drafting-draft" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        descriptionPending={view.state === 'loading'}
        actions={
          view.state === 'ready' ?
            <div className="flex flex-wrap items-center gap-2">
              {onOutline && (
                <Button
                  variant="outlineGrey"
                  shape="round"
                  size="md"
                  onClick={onOutline}
                >
                  {words.toOutline}
                </Button>
              )}
              <Button
                variant="outlineGrey"
                shape="round"
                size="md"
                onClick={onList}
              >
                {DR_TEXT.common.toList}
              </Button>
            </div>
          : undefined
        }
      />
      <StepFlow
        current={3}
        steps={DR_TEXT.steps.items}
        label={DR_TEXT.steps.label}
      />
      {view.state === 'refused' ?
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="company-refusal"
        >
          {companyText[view.company]}
        </PageInfo>
      : view.state === 'not_found' ?
        <LoadFailure
          kind="missing"
          message={words.runMissing}
          listLabel={DR_TEXT.common.toList}
          onList={onList}
        />
      : view.state === 'failed' ?
        <LoadFailure
          kind="failed"
          message={words.runLoadFailed}
          retryLabel={DR_TEXT.common.retry}
          onRetry={retry}
        />
      : view.state === 'ready' ?
        <>
          {(view.run.status === 'failed' ||
            (view.run.status !== 'done' && view.run.base === null)) && (
            <RunHead
              store={store}
              projectId={projectId!}
              run={view.run}
              picker={picker}
            />
          )}
          {view.run.status === 'failed' ?
            <>
              <PageInfo
                role="alert"
                tone="error"
                icon={<CircleWarningIcon aria-hidden />}
                data-testid="run-failed"
              >
                {words.failed}
              </PageInfo>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="outlineGrey"
                  shape="round"
                  size="sm"
                  loading={busy}
                  disabled={busy}
                  onClick={() => void restartAll()}
                >
                  {words.restartAll}
                </Button>
                <span
                  data-testid="run-failed-hint"
                  className="text-style-pre-caption-03 text-text-tertiary"
                >
                  {words.failedHint}
                </span>
              </div>
            </>
          : view.run.status === 'done' ?
            <ResultView
              store={store}
              openPdf={openPdf}
              projectId={projectId!}
              runId={view.run.id}
              operator={operator}
              onList={onList}
              onRun={onRun}
              picker={picker}
            />
          : view.run.base !== null ?
            <ResultView
              store={store}
              openPdf={openPdf}
              projectId={projectId!}
              runId={view.run.base.runId}
              operator={operator}
              onList={onList}
              onRun={onRun}
              readOnly={{ rebuilding: view.run.base.rebuild }}
              picker={picker}
            />
          : <Progress run={view.run} />}
          {refused !== null && (
            <p
              role="alert"
              data-testid="start-refused"
              className="m-0 flex items-start gap-1 text-style-pre-caption-03 text-support-error [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0"
            >
              <CircleWarningIcon aria-hidden />
              {refused === 'start' ?
                DR_TEXT.startRefused
              : refused === 'startFailed' ?
                DR_TEXT.startFailed
              : companyText[refused]}
            </p>
          )}
        </>
      : skeleton && <LoadSkeleton />}
    </div>
  );
}

/** 결과 머리(ResultView)와 같은 줄 — 다 끝나 결과로 넘어갈 때 고르기가 뛰지 않게. */
function RunHead({
  store,
  projectId,
  run,
  picker,
}: {
  store: DraftingStore;
  projectId: number;
  run: RunState;
  picker: ReactNode;
}) {
  const project = useProject(store, projectId);
  const known = project.status.state === 'ready' ? project.status.value : null;
  const documentId = known?.pdf?.documentId ?? null;
  const pdf = useRead(documentId === null ? null : [store, documentId], () =>
    store.getDocument(documentId!),
  );
  const nodes = known?.outline?.outline.nodes ?? null;
  // 실패한 앞 실행의 목차는 지금 목차와 다를 수 있다 — 실행이 센 값이 없으면 싣지 않는다.
  const total =
    run.steps.find((step) => step.step === 'draft')?.total ??
    (run.status === 'failed' || nodes === null ? null : leafCountOf(nodes));
  return (
    <div data-testid="run-head" className="flex flex-col gap-4">
      <p
        data-testid="run-subtitle"
        className="m-0 min-h-[1lh] truncate text-style-pre-caption-03 text-text-tertiary"
      >
        {known &&
          `${DR_TEXT.outline.lead(known.year, known.name)}${
            pdf.status.state === 'ready' ?
              DR_TEXT.outline.leadFile(pdf.status.value.fileName, null)
            : ''
          }`}
      </p>
      <div
        data-testid="run-picker-row"
        className="flex min-h-9 flex-wrap items-center gap-3"
      >
        {picker}
        {total !== null && (
          <p
            data-testid="run-counts"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {words.headCount(total)}
          </p>
        )}
      </div>
    </div>
  );
}

/** 만드는 중 — 머리 둘과 진행 줄 셋. */
function Progress({ run }: { run: RunState }) {
  const steps = new Map(run.steps.map((step) => [step.step, step]));
  return (
    <Card className="gw-m-rise flex flex-col gap-4" data-testid="run-progress">
      <div className="flex flex-col gap-1">
        <h3
          data-testid="run-heading"
          className="m-0 text-style-pre-heading-02 text-text-primary"
        >
          {words.making}
        </h3>
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {words.keepGoing}
        </p>
      </div>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {SHOWN.map((name, index) => (
          <StepRow
            key={name}
            index={index + 1}
            name={name}
            step={steps.get(name)}
          />
        ))}
      </ol>
    </Card>
  );
}

/** 단계 오른쪽 상태 글의 꼴 — pages/materiality-status/ui/StatusScreen.tsx STATE_LOOK 값(같은 층 다른 슬라이스 import 금지). */
const STATE_LOOK: Record<RunStep['status'], string> = {
  done: 'text-text-tertiary',
  running: 'text-support-orange-dark',
  pending: 'text-text-quaternary',
  failed: 'text-support-error',
};

function StepRow({
  index,
  name,
  step,
}: {
  index: number;
  name: ShownStep;
  step: RunStep | undefined;
}) {
  const status = step?.status ?? 'pending';
  const counted =
    name === 'draft' && step && step.done !== null && step.total !== null ?
      { done: step.done, total: step.total }
    : null;
  const hint =
    name === 'draft' && status === 'running' && counted && counted.total > 0 ?
      words.stepNow(Math.min(counted.done + 1, counted.total), counted.total)
    : words.stepHints[name];
  return (
    // 줄 꼴은 IR-03·DV-03 LineRow 와 같다(밴드 RPW5 #5): 점 28 · 이름 body-04 굵게 · 설명 body-06 · 진행 중·실패 줄 바탕.
    <li
      data-step={name}
      data-status={status}
      aria-current={status === 'running' ? 'step' : undefined}
      className={cn(
        'box-border flex items-center gap-4 rounded-component px-4 py-3',
        status === 'running' ? 'bg-background-brand'
        : status === 'failed' ? 'bg-support-error-subtle'
        : 'bg-background-primary',
      )}
    >
      <span
        aria-hidden
        data-testid="step-mark"
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-full tabular-nums text-style-pre-caption-01 [&_svg]:size-4',
          status === 'done' ? 'bg-support-success text-text-primary-inverse'
          : status === 'running' ? 'bg-button-orange text-text-primary-inverse'
          : 'bg-background-secondary text-text-tertiary',
          // 지금 단계 점 둘레 고리(#6)
          status === 'running' && 'gw-m-ring',
        )}
      >
        {status === 'done' ?
          <CheckIcon className="gw-m-pop" />
        : index}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <b className="text-style-pre-body-04 text-text-primary">
          {words.steps[name]}
        </b>
        <span
          data-testid="step-hint"
          className="text-style-pre-body-06 text-text-tertiary"
        >
          {hint}
        </span>
        {counted && (
          <div className="mt-1 flex items-center gap-3 text-style-pre-body-02">
            <span
              data-testid="step-count"
              className="shrink-0 tabular-nums text-text-secondary"
            >
              {words.stepCount(counted.done, counted.total)}
            </span>
            {counted.total > 0 && (
              <div
                role="progressbar"
                aria-label={words.stepBar}
                aria-valuemin={0}
                aria-valuenow={counted.done}
                aria-valuemax={counted.total}
                className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-background-tertiary"
              >
                <div
                  data-testid="step-bar-fill"
                  className="gw-m-flow gw-m-width h-full rounded-full bg-button-orange"
                  style={{
                    width: `${Math.min(100, (counted.done / counted.total) * 100)}%`,
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>
      <span
        data-testid="step-state"
        className={cn('shrink-0 text-style-pre-caption-02', STATE_LOOK[status])}
      >
        {words.stepStates[status]}
      </span>
    </li>
  );
}
