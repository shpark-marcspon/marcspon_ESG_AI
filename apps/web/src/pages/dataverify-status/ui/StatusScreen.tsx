// DV-03 처리 상태(밴드 DV2a ③, 시안 v148 DV-03_r1 + 2e ③④⑦). 라우터를 모른다 — 저장소와 콜백 props 를 받는다.
// 같은 화면이 실행 상태에 따라 넷 가운데 하나로 보인다(판 「검증 화면이 바뀌는 흐름」):
//   ① queued·processing → 「검증 중이에요」 + 진행 카드(단계 다섯 — 상태 글만, 수 0, 2e ④) · queued 는 「차례를 기다리고 있어요…」
//   ② done → 머리 「검증이 끝났어요」 + 시작 meta(「계속돼요」 뺌) + [목록으로], STEP 3, 끝남 카드(밴드 DV13 ③ — GW-03 r3 꼴) 안에
//      결과를 한 번 읽어(useResult — done 일 때만) 「<끝> 끝남 · 검산 n곳 · 리스크 n건」 + [결과 보기] + 「확인할 곳」 띠(2e ③).
//      결과를 못 읽으면 끝 시각만(2e ④). 저절로 넘기지 않는다(그린워싱 GW-03 꼴 — 보던 화면이 바뀌지 않게).
//   ③ failed → 「검증이 멈췄어요」 + [다시 실행](GET /runs/{id} 의 options 그대로 새 실행)·[목록으로]. 거절 글은 DV-02 시작 실패 글(감독 답 4).
//   ④ done + 경고 no_target_theme → 「검증할 항목이 없어요」 + [결과 보기]·[새 검증](「환경」이 빈 목록이면 경고가 없어 ② 다).
// 머리의 제목 자리는 기업명(Q4 (나) — DV2b 가 출처로 바꾼다). 읽지 못한 입력이면 「–」.
// 폴링 실패는 shared load-failure(CM-03 꼴), 없는 실행은 「결과를 찾을 수 없어요」 + [목록으로]. 서버 errorCode·message 는 보이지 않는다.
import type { ReactNode } from 'react';

import {
  CheckIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import type { DataverifyStore } from '../../../entities/dataverify/api/index.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  useRerun,
  useResult,
  useRun,
} from '../../../entities/dataverify/hooks/index.ts';
import type {
  RerunHandle,
  ResultState,
} from '../../../entities/dataverify/hooks/index.ts';
import {
  atText,
  currentStep,
  hasNoTarget,
  notices,
  resultCounts,
  stepViews,
} from '../../../entities/dataverify/model/index.ts';
import type {
  DataverifyRun,
  StepStatus,
  StepView,
} from '../../../entities/dataverify/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
import { useCountUp } from '../../../shared/ui/motion/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';

const words = DV_TEXT.status;
const common = DV_TEXT.common;

/** 단계 점의 꼴. */
const DOT_LOOK: Record<StepStatus, string> = {
  done: 'bg-support-green-dark text-text-primary-inverse',
  running: 'bg-button-orange text-text-primary-inverse',
  pending: 'bg-background-tertiary text-text-quaternary',
  failed: 'bg-support-error text-text-primary-inverse',
};
/** 단계 오른쪽 상태 글의 꼴. */
const STATE_LOOK: Record<StepStatus, string> = {
  done: 'text-text-tertiary',
  running: 'text-support-orange-dark',
  pending: 'text-text-quaternary',
  failed: 'text-support-error',
};

export interface StatusScreenProps {
  store: DataverifyStore;
  runId: string;
  /** [목록으로]. */
  onBack(): void;
  /** [결과 보기](DV-04). */
  onViewResult(runId: string): void;
  /** [다시 실행]으로 새 실행이 생겼을 때. */
  onRerun(runId: string): void;
  /** 검증할 항목이 없을 때의 [새 검증](DV-02). */
  onNewCheck(): void;
}

export function StatusScreen({
  store,
  runId,
  onBack,
  onViewResult,
  onRerun,
  onNewCheck,
}: StatusScreenProps) {
  const { status, retry } = useRun(store, runId);
  const done = status.state === 'ready' && status.run.status === 'done';
  const { status: result } = useResult(store, done ? runId : null);
  const rerun = useRerun(store, runId);
  const skeleton = useDelayed(status.state === 'loading');
  const back = (
    <Button variant="outlineGrey" shape="round" size="md" onClick={onBack}>
      {common.toList}
    </Button>
  );

  if (status.state !== 'ready')
    return (
      <div
        data-screen="dataverify-status"
        data-run-state={status.state}
        aria-busy={status.state === 'loading' || undefined}
        className="flex flex-col gap-6"
      >
        {/* 읽는 동안은 제목·머리 줄 자리만(ready 제목은 상태마다 달라 셸 제목을 그렸다가 바꾸지 않는다 — 밴드 DV2e, sid:MARC-ENT-443 ④). */}
        <PageTitle
          title={DV_TEXT.shell.title}
          titlePending={status.state === 'loading'}
          descriptionPending={status.state === 'loading'}
          actions={status.state === 'loading' ? back : undefined}
        />
        {status.state === 'missing' ?
          <LoadFailure
            kind="missing"
            message={common.notFound}
            listLabel={common.toList}
            onList={onBack}
          />
        : status.state === 'failed' ?
          <LoadFailure
            kind="failed"
            message={words.loadFailed}
            retryLabel={common.retry}
            listLabel={common.toList}
            onRetry={retry}
            onList={onBack}
          />
        : skeleton && <LoadSkeleton />}
      </div>
    );

  return (
    <RunView
      run={status.run}
      result={result}
      back={back}
      onBack={onBack}
      onViewResult={onViewResult}
      rerun={rerun}
      onRerun={onRerun}
      onNewCheck={onNewCheck}
    />
  );
}

function RunView({
  run,
  result,
  back,
  onBack,
  onViewResult,
  rerun,
  onRerun,
  onNewCheck,
}: {
  run: DataverifyRun;
  result: ResultState;
  back: ReactNode;
  onBack(): void;
  onViewResult(runId: string): void;
  rerun: RerunHandle;
  onRerun(runId: string): void;
  onNewCheck(): void;
}) {
  const ready = result.state === 'ready' ? result.result : null;
  const noTarget = ready !== null && hasNoTarget(ready);
  const title = DV_TEXT.source.title(
    run.source,
    DV_TEXT.orDash(run.input?.company.name ?? null),
  );
  const started = atText(run.createdAt);
  const head = words.head(started, title);
  const views = stepViews(run.steps);
  // 「n번째」는 굴러 올라간다(밴드 DV3 ②-2 — 훅은 갈래 앞에, 조건 없이. 움직임이 없으면 끝 값 그대로)
  const shownNth = useCountUp(currentStep(views));

  if (run.status === 'done') {
    const finished = atText(run.finishedAt ?? run.createdAt);
    const counts = ready === null ? null : resultCounts(ready);
    const places =
      ready === null || noTarget ?
        []
      : [...new Set(notices(ready).map((n) => DV_TEXT.notices[n].short))];
    const doneLine = words.doneLine(
      finished,
      counts === null ? null : (
        {
          plan:
            ready?.plan.status === 'done' ? ready.plan.formulas.length : null,
          places: counts.summary.places,
          ok: counts.summary.okYears,
          mismatches: counts.summary.mismatches,
          uncomputable: counts.summary.uncomputable,
          risks: counts.risks,
        }
      ),
    );
    return (
      <div
        data-screen="dataverify-status"
        data-run-state={noTarget ? 'no_target' : 'done'}
        className="flex flex-col gap-6"
      >
        {/* 끝남(밴드 DV13 ③ — 디자인 b2 답 (가), sid:MARC-ISSUE-646): 진행 카드가 빠진 자리가 비어 보였다(컨설턴트 댓글 11-10).
            그린워싱 GW-03 끝남 카드 꼴 — 머리는 제목 + 시작 meta(「계속돼요」 뺌) + [목록으로], 끝 줄·[결과 보기]·확인할 곳은 카드 한 자리. ④ 는 그대로. */}
        <PageTitle
          title={noTarget ? words.noTargetTitle : words.doneTitle}
          description={noTarget ? doneLine : words.head(started, title, false)}
          actions={back}
        />
        <StepFlow
          current={3}
          steps={DV_TEXT.steps.items.map((item) => item.label)}
          label={DV_TEXT.steps.label}
        />
        {!noTarget && (
          <Card
            className="gw-m-rise flex flex-col gap-4"
            data-testid="done-card"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex min-w-0 flex-col">
                <b className="text-style-pre-heading-02 text-text-primary">
                  {words.doneTitle}
                </b>
                <span
                  data-testid="done-meta"
                  className="text-style-pre-caption-03 text-text-tertiary"
                >
                  {doneLine}
                </span>
              </div>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={() => onViewResult(run.runId)}
              >
                {common.viewResult}
              </Button>
            </div>
            {places.length > 0 && (
              <PageInfo
                icon={<PageInfoIcon />}
                data-testid="check-places"
                tone="caution"
              >
                {words.checkPlaces(places)}
              </PageInfo>
            )}
          </Card>
        )}
        {noTarget && (
          <Card
            className="gw-m-rise flex flex-col gap-4"
            data-testid="no-target"
          >
            <PageInfo icon={<PageInfoIcon />} tone="caution">
              {words.noTargetBody}
            </PageInfo>
            <div className="flex gap-2">
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={() => onViewResult(run.runId)}
              >
                {common.viewResult}
              </Button>
              <Button
                variant="outlineGrey"
                shape="round"
                size="md"
                onClick={onNewCheck}
              >
                {common.newCheck}
              </Button>
            </div>
          </Card>
        )}
      </div>
    );
  }

  const failed = run.status === 'failed';
  return (
    <div
      data-screen="dataverify-status"
      data-run-state={run.status}
      className="flex flex-col gap-6"
    >
      <PageTitle
        title={failed ? words.failedTitle : words.running}
        description={head}
        actions={back}
      />
      <StepFlow
        current={2}
        steps={DV_TEXT.steps.items.map((item) => item.label)}
        label={DV_TEXT.steps.label}
      />
      {run.status === 'queued' && (
        <p
          data-testid="queued"
          className="m-0 flex items-center gap-2 text-style-pre-body-04 text-text-secondary"
        >
          <Badge variant="grey">{words.stepBadge.pending}</Badge>
          {words.queued}
        </p>
      )}
      <Card className="flex flex-col gap-4" data-testid="progress">
        <div className="flex items-center justify-between gap-4">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.progressTitle}
          </h3>
          <span
            data-testid="progress-nth"
            className="text-style-pre-caption-03 text-text-tertiary"
          >
            {words.progressNth(shownNth)}
          </span>
        </div>
        <ol
          aria-label={DV_TEXT.steps.label}
          className="m-0 flex list-none flex-col gap-3 p-0"
        >
          {views.map((view, index) => (
            <StepRow key={view.name} view={view} number={index + 1} />
          ))}
        </ol>
        {/* 「계산 계획을…」은 카드 안 맨 아래 파랑 안내(시안 DV-03 g-info--caution, 밴드 DV3 J2) */}
        <PageInfo
          icon={<PageInfoIcon />}
          data-testid="plan-skip"
          tone="caution"
        >
          {words.footnote}
        </PageInfo>
      </Card>

      {failed && (
        <Card className="flex flex-col gap-4" data-testid="failure">
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
          >
            {words.failedBody}
          </PageInfo>
          {rerun.failed && (
            <PageInfo
              tone="error"
              role="alert"
              icon={<CircleWarningIcon aria-hidden />}
              data-testid="rerun-error"
            >
              {DV_TEXT.newCheck.errors.startFailed}
            </PageInfo>
          )}
          <div className="flex gap-2">
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              loading={rerun.rerunning}
              onClick={async () => {
                const next = await rerun.rerun();
                if (next !== null) onRerun(next);
              }}
            >
              {common.rerun}
            </Button>
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              onClick={onBack}
            >
              {common.toList}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function StepRow({ view, number }: { view: StepView; number: number }) {
  const text = DV_TEXT.status.stepText[view.name];
  // 못 한 단계는 진행 중 글 그대로 + 배지 「못 함」(2e ④).
  const body = view.status === 'failed' ? text.running : text[view.status];
  return (
    <li
      data-step={view.name}
      data-state={view.status}
      aria-current={view.status === 'running' ? 'step' : undefined}
      className={cn(
        'box-border flex items-center gap-4 rounded-component px-4 py-3',
        view.status === 'running' ? 'bg-background-brand'
        : view.status === 'failed' ? 'bg-support-error-subtle'
        : 'bg-background-primary',
      )}
    >
      <span
        aria-hidden
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-full text-style-pre-caption-01 [&_svg]:size-4',
          DOT_LOOK[view.status],
          // 지금 단계 점 둘레 고리 · 끝난 단계 체크 튀어나옴(밴드 DV3 ②-1 — 그린워싱 GA1b 꼴)
          view.status === 'running' && 'gw-m-ring',
        )}
      >
        {view.status === 'done' ?
          <CheckIcon className="gw-m-pop" />
        : number}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <b className="text-style-pre-body-04 text-text-primary">
          {words.stepNames[view.name]}
        </b>
        <span className="text-style-pre-body-06 text-text-tertiary">
          {body}
        </span>
      </div>
      <span
        className={cn(
          'shrink-0 text-style-pre-caption-02',
          STATE_LOOK[view.status],
        )}
      >
        {words.stepBadge[view.status]}
      </span>
    </li>
  );
}
