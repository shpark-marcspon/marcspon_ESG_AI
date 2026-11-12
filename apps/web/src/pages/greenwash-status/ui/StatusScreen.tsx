// GW-03 처리 상태(밴드 FW1b ③). 시안 GW-03_r1(캔버스 v64)의 구성:
//   제목 줄(제목 · 시작 시각과 점검할 쪽 · [목록으로]) → STEP 2 → 진행 카드(전체 진행률 막대 + 단계 셋) → (실패면) 실패 안내와 [다시 실행]·[목록으로].
// 저장소 구독은 headless 의 useRunStatus. 진행률·단계 상태는 domain 순수 함수(무게 10·80·10 은 가정).
// [목록으로]는 목록(GW-01)으로 간다(쓰는 쪽 경로 컴포넌트 GreenwashRoutes 가 정한다).
// 실패(밴드 FW2 ⓪, 2026-10-16 사용자 결정·시안 v74): 이 화면의 실패는 실행 전체 실패뿐이다. 안내는 한 문장(멈춘 쪽·단계를 말하지 않는다),
//   [다시 실행]은 같은 문서·같은 입력으로 처음부터 도는 새 실행(store.rerun). 쪽 하나의 실패는 결과 화면(GW-04)이 알린다.
// 진행 막대 바탕과 대기 점은 background-tertiary(#E7E9EC, 디자인 대조 고칠 것 4).
// 밴드 PL1 ②(디자인 대조 C8): 실행이 끝나도 저절로 넘기지 않는다. [결과 보기](onViewResult)를 누르면 GW-04 로 간다
//   (보던 화면이 저절로 바뀌면 화면 읽기 사용자가 자리를 잃는다. 이동은 쓰는 쪽 경로 컴포넌트 GreenwashRoutes — replace).
//   밴드 GP4: [결과 보기]는 머리가 아니라 본문의 끝남 카드(r3 「분석이 끝났을 때」) 한 자리. 머리 설명은 시작 meta(「계속돼요」 없이),
//   「{끝난 때} 끝남 · n문장」과 인식 실패 페이지 줄은 카드 안 — 진행 카드가 빠진 끝남 화면의 STEP 띠 아래가 비어 보였다(사용자 10-25).
// 밴드 LE1(sid:MARC-ENT-260): 불러오는 중은 제목 줄(화면 이름 status.screenTitle + [목록으로]) · STEP 2 를 두고 본문 자리에 스켈레톤(300ms 뒤).
//   스켈레톤은 점검 중 진행 카드를 닮은 StatusSkeleton(밴드 GL2 — 끝난 실행이면 받은 뒤 줄어든다, 까닭은 그 파일 머리).
//   없는 실행은 제목 줄(화면 이름만) + 회색 「점검을 찾을 수 없어요」 + 상자의 [목록으로] 하나(단계 표시 없음). 구독에는 실패 갈래가 없다(store.ts).
//   밴드 LA1 ①: 읽는 동안 내내(스켈레톤 300ms 전에도) 화면 바깥 틀에 aria-busy. 스켈레톤 카드는 role="status" 만.
// 밴드 FW2 ①: 시작 시각은 ISO 를 받아 여기서 꾸민다(한국 시각, domain formatKst). [다시 실행]은 headless useRerun — 거절되면 role="alert" 안내.
// 밴드 GW1R ②(디자인 답·원문, 캔버스 v101 GW-03 r2):
//   - 상태를 읽지 못함(실어댑터의 onFailed)은 CM-03 「불러오지 못함」: 제목 줄(화면 이름) + 빨강 「점검 상태를 불러오지 못했어요」 + [다시 시도][목록으로].
//     [다시 시도]는 loading 부터 다시 구독한다(또 실패하면 같은 꼴).
//   - 실패 code 가 no_text_layer 면 실패 카드가 한 갈래 바뀐다: 글은 GW-02a 글 그대로, [다시 실행] 대신 [새 점검](canWrite 거짓이면 숨김) + [목록으로],
//     파일 줄(이름 + 회색 「텍스트 없음」). 가름은 errorCode 하나다(진행 단계로 가르지 않는다).
// 밴드 GW2R ②(v115 GW-03_r3 안 B, 디자인 답 D1·D4, sid:MARC-ISSUE-228·227):
//   - 진행 중의 파랑 정보 줄은 지웠다(시안 댓글 — sid:MARC-ENT-603). 파랑 줄 꼴(css .g-info--caution — support-blue-subtle·blue-dark. 공용 PageInfo 에
//     tone 이 없어 className 으로 덮는다 — 공용 0줄)은 끝남의 인식 실패 페이지 줄이 쓴다.
//   - 끝남: 「점검이 끝났어요」, 제목 아래 「{끝난 때} 끝남 · {n}개의 그린워싱 리스크 문장을 찾았어요」, 인식 실패 페이지가 있으면 파랑 줄 「인식 실패 페이지 n개 (…페이지)」.
//     문장 수·쪽은 결과를 한 번 읽어(useResult — done 일 때만) 그 결과에서만 센다(실행 상태에는 쪽 번호가 없다). 결과를 못 읽으면 두 토막만 조용히 뺀다.
//     dry-run 결과면 문장 수 토막을 뺀다.
//   - 멈춤 셋(failureKind — errorCode 하나로 가름, 단계·글로 가르지 않는다): 일반(새 글 · [다시 실행][목록으로], 덧글 없음 — D4) /
//     no_text_layer(파일 줄을 안내 위로, 「24쪽 · 텍스트 없음」 — 228 S2) / setup_error(D1 글 · [목록으로]만). 운영 관리자도 고객사와 같은 글이다
//     (sid:MARC-ENT-409 C1 — 운영 관리자 글 갈래를 걷음).
//   - 불러오지 못함에도 STEP 띠(모두 꺼진 꼴 — 228 S1). 텍스트 추출(extract)에서 멈춘 실행은 STEP 1 을 켠다(228 덤 — STEP 2 가 켜져 있었다. 추정).
import type { ReactNode, Ref } from 'react';

import {
  CheckIcon,
  CircleWarningIcon,
  PdfIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  GreenwashStore,
  RunSnapshot,
} from '../../../entities/greenwash/api/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  useRerun,
  useResult,
} from '../../../entities/greenwash/hooks/index.ts';
import type {
  Rerun,
  ResultState,
} from '../../../entities/greenwash/hooks/index.ts';
import {
  RUN_STAGES,
  failedPagesOf,
  failureKind,
  formatKst,
  isScanResult,
  overallPercent,
  stageStates,
} from '../../../entities/greenwash/model/index.ts';
import type {
  RunStage,
  StageState,
} from '../../../entities/greenwash/model/index.ts';
import {
  LoadFailure,
  StepFlow,
  useCountUp,
} from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { useRunStatus } from '../hooks/index.ts';
import { StatusSkeleton } from './StatusSkeleton.tsx';

const words = GW_TEXT.status;

/** 단계 점의 꼴. */
const DOT_LOOK: Record<StageState, string> = {
  done: 'bg-support-green-dark text-text-primary-inverse',
  now: 'bg-button-orange text-text-primary-inverse',
  todo: 'bg-background-tertiary text-text-quaternary',
  failed: 'bg-support-error text-text-primary-inverse',
};
/** 단계 오른쪽 상태 글의 꼴. */
const STATE_LOOK: Record<StageState, string> = {
  done: 'text-text-tertiary',
  now: 'text-support-orange-dark',
  todo: 'text-text-quaternary',
  failed: 'text-support-error',
};

export interface StatusScreenProps {
  store: GreenwashStore;
  runId: string;
  /** [목록으로]. */
  onBack(): void;
  /** [다시 실행]으로 새 실행이 생겼을 때. */
  onRerun(runId: string): void;
  /** 끝난 실행의 [결과 보기](GW-04 결과 요약으로). 없으면 단추 없이 끝난 상태만 보인다. */
  onViewResult?(runId: string): void;
  /** 거짓이면 [다시 실행]·[새 점검]을 숨긴다(로그인하지 않은 세션 — 운영 관리자도 고객사 사용자와 같이 쓴다, sid:MARC-ENT-409). 기본 참. */
  canWrite?: boolean;
  /** 글자 없는 PDF 로 멈춘 실행의 [새 점검](GW-02 로). 없으면 단추 없이. */
  onNewCheck?(): void;
}

/** 파랑 정보 줄(css .g-info--caution — 밴드 GW2R ②). 공용 PageInfo 기본 꼴의 바탕·글 색만 덮는다. */
const CAUTION_CLASS = 'bg-support-blue-subtle text-support-blue-dark';

export function StatusScreen({
  store,
  runId,
  onBack,
  onRerun,
  onViewResult,
  canWrite = true,
  onNewCheck,
}: StatusScreenProps) {
  const status = useRunStatus(store, runId);
  const rerun = useRerun(store, runId);
  // 끝난 실행만 결과를 한 번 읽는다(문장 수·인식 실패 페이지 — Q4). 그 밖에는 읽지 않는다.
  const { status: result } = useResult(
    store,
    runId,
    status.state === 'ready' && status.run.progress.state === 'done',
  );
  const skeleton = useDelayed(status.state === 'loading');
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    status.state === 'missing' ? 'ready' : status.state,
  );
  const back = (
    <Button variant="outlineGrey" shape="round" size="md" onClick={onBack}>
      {words.back}
    </Button>
  );
  if (status.state !== 'ready')
    return (
      <div
        data-screen="status"
        data-run-state={status.state}
        aria-busy={status.state === 'loading' || undefined}
        className="flex flex-col gap-6"
      >
        {status.state === 'missing' ?
          <>
            <PageTitle title={words.screenTitle} />
            <LoadFailure
              kind="missing"
              message={words.missing}
              listLabel={GW_TEXT.load.toList}
              onList={onBack}
            />
          </>
        : status.state === 'failed' ?
          <>
            <PageTitle title={words.screenTitle} />
            {/* 어느 단계인지 모른다 — 모두 꺼진 띠(228 S1) */}
            <StepFlow current={0} />
            <LoadFailure
              kind="failed"
              message={words.loadFailed}
              onRetry={retryFocus.arm(status.retry)}
              onList={onBack}
              actionRef={retryFocus.actionRef}
            />
          </>
        : <>
            {/* 제목(words.title[상태])·설명은 실행을 받아야 안다 — 막대 자리(밴드 GL1, sid:MARC-ENT-443 ③) */}
            <PageTitle
              title={words.screenTitle}
              titlePending
              pendingLabel={GW_TEXT.load.titlePending}
              descriptionPending
              actions={back}
            />
            <StepFlow current={2} />
            {skeleton && <StatusSkeleton label={words.title.loading} />}
          </>
        }
      </div>
    );
  return (
    <RunView
      run={status.run}
      result={result}
      fileName={status.fileName}
      onNewCheck={onNewCheck}
      headingRef={retryFocus.doneRef}
      back={back}
      onBack={onBack}
      rerun={rerun}
      onRerun={onRerun}
      onViewResult={onViewResult}
      canWrite={canWrite}
    />
  );
}

function RunView({
  run,
  result,
  fileName,
  onNewCheck,
  headingRef,
  back,
  onBack,
  rerun,
  onRerun,
  onViewResult,
  canWrite,
}: {
  run: RunSnapshot;
  /** 끝난 실행의 결과 읽기(그 밖에는 loading 그대로). */
  result: ResultState;
  fileName: string | null;
  onNewCheck?(): void;
  /** 제목 줄 h2([다시 시도] 뒤 초점 — 밴드 LA1 꼴). */
  headingRef: Ref<HTMLHeadingElement>;
  back: ReactNode;
  onBack(): void;
  rerun: Rerun;
  onRerun(runId: string): void;
  onViewResult?(runId: string): void;
  canWrite: boolean;
}) {
  const { progress } = run;
  const percent = overallPercent(progress);
  // 화면의 % 글자만 굴린다(막대의 aria-valuenow 는 끝 값 — 밴드 GA1)
  const shownPercent = useCountUp(percent);
  const states = stageStates(progress);
  const failed = progress.state === 'failed';
  const kind = failed ? failureKind(run.errorCode) : null;
  const done = progress.state === 'done';
  // 끝남의 문장 수·인식 실패 페이지는 결과에서만(읽기 전·못 읽음이면 빈 것 — 토막을 뺀다)
  const ready = done && result.state === 'ready' ? result.result : null;
  const sentences =
    ready !== null && isScanResult(ready) ? ready.items.length : null;
  const missedPages = ready === null ? [] : failedPagesOf(ready);
  const doneMeta =
    done ?
      words.doneMeta(
        run.finishedAt === null ? null : formatKst(run.finishedAt),
        sentences,
      )
    : null;
  return (
    <div
      data-screen="status"
      data-run-state={progress.state}
      className="flex flex-col gap-6"
    >
      <PageTitle
        headingRef={headingRef}
        title={words.title[progress.state]}
        description={words.meta(
          run.startedAt === null ? null : formatKst(run.startedAt),
          run.checkedPages,
          progress.state === 'running',
        )}
        actions={back}
      />
      <StepFlow
        current={
          done ? 3
          : failed && progress.stage === 'extract' ?
            1
          : 2
        }
      />

      {/* 끝남 카드(r3 「분석이 끝났을 때」·「끝나면 2」, 밴드 GP4 — 진행 카드가 빠진 자리가 비어 보였다). [결과 보기]는 이 카드 한 자리 */}
      {done && (
        <Card className="gw-m-rise flex flex-col gap-4" data-testid="done-card">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-0 flex-col">
              <b className="text-style-pre-heading-02 text-text-primary">
                {words.title.done}
              </b>
              {doneMeta !== null && (
                <span
                  data-testid="done-meta"
                  className="text-style-pre-caption-03 text-text-tertiary"
                >
                  {doneMeta}
                </span>
              )}
            </div>
            {onViewResult && (
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={() => onViewResult(run.runId)}
              >
                {words.viewResult}
              </Button>
            )}
          </div>
          {missedPages.length > 0 && (
            <PageInfo
              icon={<PageInfoIcon />}
              data-testid="missed-pages"
              className={CAUTION_CLASS}
            >
              {words.failedPages(missedPages)}
            </PageInfo>
          )}
        </Card>
      )}

      {/* 진행 카드(막대·단계 셋)는 점검 중에만(판 r3 — 끝남·멈춤 카드에는 없다, sid:MARC-ISSUE-265 (1)) */}
      {progress.state === 'running' && (
        <Card className="gw-m-rise flex flex-col gap-5">
          <div className="flex items-center justify-between gap-4">
            <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
              {words.progressHeading}
            </h3>
            <span
              data-testid="progress-percent"
              className="text-style-pre-display-04 tabular-nums text-text-primary"
            >
              {words.percent(shownPercent)}
            </span>
          </div>
          <div
            role="progressbar"
            aria-label={words.progressLabel}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="h-2 overflow-hidden rounded-full bg-background-tertiary"
          >
            <div
              className="gw-m-flow h-full rounded-full bg-button-orange transition-[width] duration-300"
              // 진행률 값만 인라인으로 준다(값이 0~100 으로 바뀌어 토큰 클래스로 낼 수 없다).
              style={{ width: `${percent}%` }}
            />
          </div>
          <ol
            aria-label={words.stagesLabel}
            className="m-0 flex list-none flex-col gap-3 p-0"
          >
            {RUN_STAGES.map((stage, index) => (
              <StageRow
                key={stage}
                stage={stage}
                number={index + 1}
                state={states[stage]}
                run={run}
              />
            ))}
          </ol>
          {/* 진행 중 파랑 정보 줄 「몇 페이지를 못 읽어도 …」은 지웠다(시안 댓글 — sid:MARC-ENT-603) */}
        </Card>
      )}

      {kind === 'no_text' && (
        <Card
          className="gw-m-rise flex flex-col gap-4"
          data-testid="failure"
          data-failure="no_text_layer"
        >
          {fileName !== null && (
            // 파일 줄은 안내 위(228 S2, GW-02a 의 e-file 꼴 — 아이콘 + 이름 + 회색 쪽 수·텍스트 없음)
            <p
              data-testid="failure-file"
              className="m-0 flex flex-wrap items-center gap-x-2 text-style-pre-body-06"
            >
              <PdfIcon aria-hidden className="size-4 shrink-0" />
              <span className="text-text-primary">{fileName}</span>
              <span className="text-style-pre-caption-02 text-text-tertiary">
                {words.noText.fileMeta(run.pageCount)}
              </span>
            </p>
          )}
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="failure-info"
          >
            {GW_TEXT.newCheck.upload.noText}
          </PageInfo>
          <div className="flex gap-2">
            {canWrite && onNewCheck && (
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={onNewCheck}
              >
                {words.noText.newCheck}
              </Button>
            )}
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              onClick={onBack}
            >
              {words.back}
            </Button>
          </div>
        </Card>
      )}
      {kind === 'setup' && (
        // 서비스 설정 문제(디자인 답 D1): 오류 카드 꼴, [목록으로]만 — 다시 실행해도 같은 끝
        <Card
          className="gw-m-rise flex flex-col gap-4"
          data-testid="failure"
          data-failure="setup_error"
        >
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="failure-info"
          >
            {words.setupFailure}
          </PageInfo>
          <div className="flex gap-2">
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              onClick={onBack}
            >
              {words.back}
            </Button>
          </div>
        </Card>
      )}
      {kind === 'general' && (
        <Card className="gw-m-rise flex flex-col gap-4" data-testid="failure">
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="failure-info"
          >
            {words.failure}
          </PageInfo>
          {rerun.startError !== null && (
            <PageInfo
              tone="error"
              role="alert"
              icon={<CircleWarningIcon aria-hidden />}
              data-testid="rerun-error"
              data-error={rerun.startError}
            >
              {rerun.startError === 'unreachable' ?
                GW_TEXT.runUnreachable.rerun
              : words.rerunRejected}
            </PageInfo>
          )}
          <div className="flex gap-2">
            {canWrite && (
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                // 끊김 뒤에도 켜 둔다 — 다시 누르면 같은 열쇠로 보내 실행은 하나다(밴드 GR2, sid:MARC-ISSUE-225)
                loading={rerun.rerunning}
                onClick={async () => {
                  const next = await rerun.rerun();
                  if (next !== null) onRerun(next);
                }}
              >
                {words.rerun}
              </Button>
            )}
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              onClick={onBack}
            >
              {words.back}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function StageRow({
  stage,
  number,
  state,
  run,
}: {
  stage: RunStage;
  number: number;
  state: StageState;
  run: RunSnapshot;
}) {
  const body =
    stage === 'extract' ?
      state === 'done' ?
        words.stages.extract.body(run.pageCount)
      : words.stages.extract.bodyPending(run.pageCount)
    : stage === 'judge' ?
      words.stages.judge.body(run.progress.judge.done, run.progress.judge.total)
    : words.stages.summarize.body;
  return (
    <li
      data-stage={stage}
      data-state={state}
      aria-current={state === 'now' ? 'step' : undefined}
      className={cn(
        'box-border flex items-center gap-4 rounded-component px-4 py-3 motion-safe:transition-colors motion-safe:duration-500',
        state === 'now' ? 'bg-background-brand'
        : state === 'failed' ? 'bg-support-error-subtle'
        : 'bg-background-primary',
      )}
    >
      <span
        aria-hidden
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-full text-style-pre-caption-01 [&_svg]:size-4',
          DOT_LOOK[state],
          state === 'now' && 'gw-m-ring',
        )}
      >
        {state === 'done' ?
          <CheckIcon className="gw-m-pop" />
        : number}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <b className="text-style-pre-body-04 text-text-primary">
          {words.stages[stage].name}
        </b>
        <span className="text-style-pre-body-06 text-text-tertiary">
          {body}
        </span>
      </div>
      <span
        className={cn('shrink-0 text-style-pre-caption-02', STATE_LOOK[state])}
      >
        {words.stageState[state]}
      </span>
    </li>
  );
}
