// IR-03 처리 상태(밴드 IRW1 ②, 시안 v157 IR-03_r1). 라우터를 모른다 — 저장소와 콜백 props 를 받는다(데이터 검증 StatusScreen 꼴).
// 같은 화면이 실행 상태에 따라 셋 가운데 하나로 보인다:
//   ① queued·processing → 「평가 중이에요」 + 「<시작> 시작(queued 면 「<접수> 접수」) · <기업> · 토픽 n개 · 이 창을 닫아도…」 + 단계 카드
//      (줄 여섯 — 진행 중 줄·머리에 n / m토픽(IRW6, sid:MARC-ISSUE-378)) · queued 는 「대기」 배지 + 「차례를 기다리고 있어요 …」.
//   ② done → 결과를 한 번 읽어(useResult — done 일 때만) 「평가가 끝났어요」 + 「<끝> · 환경·사회 영향 n · 재무 영향 경로 n」(「끝남」 0 — IRW17 20be9a06) +
//      [결과 보기](저절로 넘어가지 않음) + 정하지 못한 서브토픽이 있으면 안내(important). 결과를 못 읽으면 수는 「–」.
//   ③ failed → 단계 카드(실패 줄) + 「평가를 끝내지 못했어요. …」(error) + [다시 실행](그 실행의 options 그대로 새 실행)·[목록으로].
// done·failed 의 머리 제목은 「<기업명> · 중대성평가」, 머리 줄에 「이 창을 닫아도…」 토막은 0(밴드 IRW1b W7). 기업명·토픽 수는 실행의 input(못 읽으면 「–」).
// 폴링 실패·모르는 단계 이름은 shared load-failure, 없는 실행은 「평가를 찾을 수 없어요」 + [목록으로]. 서버 errorCode·message 는 보이지 않는다.
// 첫 불러오기는 제목 막대(titlePending) + LoadSkeleton(sid:MARC-ENT-443).
import type { ReactNode } from 'react';

import {
  CheckIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import type { MaterialityStore } from '../../../entities/materiality/api/index.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import {
  useRerun,
  useResult,
  useRun,
} from '../../../entities/materiality/hooks/index.ts';
import type {
  RerunHandle,
  ResultState,
} from '../../../entities/materiality/hooks/index.ts';
import {
  atText,
  currentLine,
  resultCards,
  stepLines,
  subtopicTotal,
  undecidedSubtopics,
} from '../../../entities/materiality/model/index.ts';
import type {
  LineStatus,
  MaterialityRun,
  StepLineView,
} from '../../../entities/materiality/model/index.ts';
import { IroFlow } from '../../../entities/materiality/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리, 밴드 IRW1b J3).
import '../../../shared/ui/motion/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';

const words = IR_TEXT.status;
const common = IR_TEXT.common;

/** 단계 점의 꼴. */
const DOT_LOOK: Record<LineStatus, string> = {
  done: 'bg-support-green-dark text-text-primary-inverse',
  running: 'bg-button-orange text-text-primary-inverse',
  pending: 'bg-background-tertiary text-text-quaternary',
  failed: 'bg-support-error text-text-primary-inverse',
};
/** 단계 오른쪽 상태 글의 꼴. */
const STATE_LOOK: Record<LineStatus, string> = {
  done: 'text-text-tertiary',
  running: 'text-support-orange-dark',
  pending: 'text-text-quaternary',
  failed: 'text-support-error',
};

export interface StatusScreenProps {
  store: MaterialityStore;
  runId: string;
  /** [목록으로]. */
  onBack(): void;
  /** [결과 보기](IR-04). */
  onViewResult(runId: string): void;
  /** [다시 실행]으로 새 실행이 생겼을 때(새 IR-03 — push). */
  onRerun(runId: string): void;
}

/** 단계 줄 여섯 — 모르는 단계 이름이면 null(화면은 load-failure). */
function linesOf(run: MaterialityRun): StepLineView[] | null {
  try {
    return stepLines(run.steps);
  } catch {
    return null;
  }
}

export function StatusScreen({
  store,
  runId,
  onBack,
  onViewResult,
  onRerun,
}: StatusScreenProps) {
  const { status, retry } = useRun(store, runId);
  const done = status.state === 'ready' && status.run.status === 'done';
  const { status: result } = useResult(store, done ? runId : null);
  const rerun = useRerun(store, runId);
  const skeleton = useDelayed(status.state === 'loading');
  const lines = status.state === 'ready' ? linesOf(status.run) : null;
  const back = (
    <Button variant="outlineGrey" shape="round" size="md" onClick={onBack}>
      {common.toList}
    </Button>
  );

  if (status.state !== 'ready' || lines === null) {
    const failed =
      status.state === 'failed' || (status.state === 'ready' && lines === null);
    return (
      <div
        data-screen="materiality-status"
        data-run-state={failed ? 'failed_load' : status.state}
        aria-busy={status.state === 'loading' || undefined}
        className="flex flex-col gap-6"
      >
        {/* 읽는 동안은 제목·머리 줄 자리만(ready 제목은 상태마다 달라 셸 제목을 그렸다가 바꾸지 않는다 — sid:MARC-ENT-443). */}
        <PageTitle
          title={IR_TEXT.shell.title}
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
        : failed ?
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
  }

  return (
    <RunView
      run={status.run}
      lines={lines}
      result={result}
      back={back}
      onBack={onBack}
      onViewResult={onViewResult}
      rerun={rerun}
      onRerun={onRerun}
    />
  );
}

function RunView({
  run,
  lines,
  result,
  back,
  onBack,
  onViewResult,
  rerun,
  onRerun,
}: {
  run: MaterialityRun;
  lines: StepLineView[];
  result: ResultState;
  back: ReactNode;
  onBack(): void;
  onViewResult(runId: string): void;
  rerun: RerunHandle;
  onRerun(runId: string): void;
}) {
  const company = IR_TEXT.orDash(run.input?.company.name ?? null);
  const topics = IR_TEXT.orDash(run.input?.topics.length ?? null);
  const head =
    run.status === 'queued' ?
      words.queuedLine(atText(run.createdAt), company, topics)
    : words.startedLine(
        atText(run.startedAt ?? run.createdAt),
        company,
        topics,
        run.status === 'processing',
      );
  const titled = run.status === 'done' || run.status === 'failed';

  if (run.status === 'done') {
    const ready = result.state === 'ready' ? result.result : null;
    const cards = ready === null ? null : resultCards(ready);
    const undecided = ready === null ? 0 : undecidedSubtopics(ready).length;
    return (
      <div
        data-screen="materiality-status"
        data-run-state="done"
        className="flex flex-col gap-6"
      >
        <PageTitle
          title={IR_TEXT.titleOf(company)}
          description={head}
          actions={back}
        />
        <IroFlow current={2} />
        {/* 진행 → 끝남 카드는 떠오른다(밴드 IRW1b J3 — 데이터 검증 DV3 ②·그린워싱 GA1b 꼴) */}
        <Card className="gw-m-rise flex flex-col gap-4" data-testid="done">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <b className="text-style-pre-heading-02 text-text-primary">
                {words.doneTitle}
              </b>
              <span
                data-testid="done-line"
                className="text-style-pre-caption-02 text-text-tertiary"
              >
                {words.doneLine(
                  atText(run.finishedAt ?? run.createdAt),
                  IR_TEXT.orDash(cards?.impact?.total ?? null),
                  IR_TEXT.orDash(cards?.pathway?.total ?? null),
                )}
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
          {ready !== null && undecided > 0 && (
            <PageInfo
              tone="important"
              icon={<PageInfoIcon />}
              data-testid="undecided"
            >
              {words.undecided(subtopicTotal(ready), undecided)}
            </PageInfo>
          )}
        </Card>
      </div>
    );
  }

  const failed = run.status === 'failed';
  return (
    <div
      data-screen="materiality-status"
      data-run-state={run.status}
      className="flex flex-col gap-6"
    >
      <PageTitle
        title={titled ? IR_TEXT.titleOf(company) : words.title}
        description={head}
        actions={back}
      />
      <IroFlow current={2} />
      {run.status === 'queued' && (
        <p
          data-testid="queued"
          className="m-0 flex items-center gap-2 text-style-pre-body-04 text-text-secondary"
        >
          <Badge variant="grey">{IR_TEXT.badge.queued}</Badge>
          {words.waiting}
        </p>
      )}

      <Card className="flex flex-col gap-4" data-testid="progress">
        <div className="flex items-center justify-between gap-4">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.progress}
          </h3>
          <span
            data-testid="progress-now"
            className="text-style-pre-caption-02 text-text-tertiary"
          >
            {nowText(lines)}
          </span>
        </div>
        <ol
          aria-label={IR_TEXT.flow.label}
          className="m-0 flex list-none flex-col gap-3 p-0"
        >
          {lines.map((view, index) => (
            <LineRow key={view.line} view={view} number={index + 1} />
          ))}
        </ol>
      </Card>

      {failed && (
        <Card className="flex flex-col gap-4" data-testid="failure">
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
          >
            {common.rerunAgain}
          </PageInfo>
          {rerun.failed && (
            <PageInfo
              tone="error"
              role="alert"
              icon={<CircleWarningIcon aria-hidden />}
              data-testid="rerun-error"
            >
              {common.rerunFailed}
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

function countText(count: NonNullable<StepLineView['count']>): string {
  return words.count(count.done, count.total, count.unit);
}

/** 머리 「진행」 오른쪽: 지금 줄 이름(그 줄에 수가 있으면 「<이름> <n / m토픽>」). */
function nowText(lines: readonly StepLineView[]): string {
  const at = currentLine(lines);
  const name = words.lines[at].name;
  const count = lines.find((view) => view.line === at)?.count ?? null;
  return count === null ? name : `${name} ${countText(count)}`;
}

function LineRow({ view, number }: { view: StepLineView; number: number }) {
  const text = words.lines[view.line];
  return (
    <li
      data-line={view.line}
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
          // 지금 단계 점 둘레 고리 · 끝난 단계 체크 튀어나옴(밴드 IRW1b J3 — IR-03 에는 막대가 없어 DV3 처럼 점에 단다)
          view.status === 'running' && 'gw-m-ring',
        )}
      >
        {view.status === 'done' ?
          <CheckIcon className="gw-m-pop" />
        : number}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <b className="text-style-pre-body-04 text-text-primary">{text.name}</b>
        <span className="text-style-pre-body-06 text-text-tertiary">
          {text.text}
          {view.count !== null && (
            <>
              {' · '}
              <span data-testid="line-count" className="tabular-nums">
                {countText(view.count)}
              </span>
            </>
          )}
        </span>
      </div>
      <span
        className={cn(
          'shrink-0 text-style-pre-caption-02',
          STATE_LOOK[view.status],
        )}
      >
        {words.lineStatus[view.status]}
      </span>
    </li>
  );
}
