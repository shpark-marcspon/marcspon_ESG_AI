// AD-04a 실행 상세 모달(밴드 AD4W, 캔버스 v127 AD-04a_r1). 상태는 화면이 넣는다(useRunDetail — GET /run-logs/{run_id} 한 번).
//   머리 「실행 상세」 + 상태 배지 → 칸(문서·모듈 · 흐름 + AI 설정 작은 글·올린 사람·시각·합계) → 단계 기록 없음 안내 줄 → 단계 표 → 표 아래 글 → 실패 줄 → 결과 파일 → [닫기].
//   - 단계 기록이 없는 실행(stepUsageRecorded 거짓)은 단계 토큰·비용 「–」 + 표 위 안내 줄, 표 아래 글은 없다. AI 를 부르지 않은 단계(0·0)도 「–」(감독 처분 Q6 (가)).
//   - 문서 두 칸 null(문서를 지운 실행 — ND1)은 회색 「–」(실패 상자 아님).
//   - 실패 줄: 「{단계} 단계에서 멈췄어요 · 오류 코드 {code}」(단계 null 은 「단계 밖에서 멈췄어요」, 코드 null 은 뒤 토막 없음 — cd 답 10-22).
//   - 결과 파일(RF1W, 결정 MARC-ENT-395): step 이 null 인 줄(흐름의 출력 파일)만 이름 옆 [내려받기](이름 「{파일} 내려받기」), 단계 중간 파일은 이름만.
//     받는 중이면 모든 [내려받기]가 끔 꼴(aria-disabled·opacity — 엑셀 단추 꼴, 누름은 useRunFile 이 막는다). 실패는 목록 아래 role="alert" 한 줄(엑셀 실패 글 꼴).
//     판의 단계 진행·입력/출력 토큰·다시 부른 수·대기 따로는 그리지 않는다.
//   - AD4P(캔버스 v138, 디자인 6c 답 10-25): 흐름 출력과 이름이 같은 단계 중간 파일은 한 줄로 접고(model 의 shownFiles), 실패 실행은 [내려받기] 없이 이름만(downloadable).
//     받기 404(notFound)는 같은 실패 줄에 「파일을 찾을 수 없어요」, 그 밖 실패는 「파일을 받지 못했어요. …」.
//     칸 목록 맨 위에 「같이 시작」 칸(launchSize 2 이상 — 값 「#101 · 2/3」 + 「같이 시작한 실행 2개」, 글만 — 감독 답 Q1 (가))과 「이어서」 칸(값 「#88」 — 판에 없어 같은 꼴).
//   - AF1(디자인 6c R4·R5·R12~R15): 칸 목록은 시안 .e-formrows 꼴(AI 설정 모델 카드와 같은 FORM_*_LOOK — 머리 500 14 tertiary·옅은 회색 바탕·160, 값 400 14 secondary),
//     [내려받기]는 sm outline-black, 파일 줄 사이 8·이름 400 12 tertiary, 「결과 파일」 머리는 h3 그대로 글 꼴만 700 12 tertiary.
//   - 불러오기(CM-03 꼴): 300ms 뒤 스켈레톤, 실패는 실패 상자 + [다시 시도], 404 RUN_NOT_FOUND 는 그 글만. 제목·[닫기] 는 늘 있다.
//   - 닫으면 넣어 준 자리(그 줄의 문서 단추)로 초점을 돌린다 — 마우스로 줄을 눌러 연 때는 연 자리가 body 라 Content 의 되돌림을 막고 여기서 옮긴다.
import type { ReactNode } from 'react';

import {
  CircleWarningIcon,
  DownloadIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import { RUN_LOG_TEXT } from '../../../entities/run-log/config/text.ts';
import {
  aiSettingText,
  detailTimes,
  downloadable,
  flowEdition,
  launchMark,
  resumedMark,
  runFigures,
  shownFiles,
  stepFigures,
  stepLabel,
  uploaderText,
} from '../../../entities/run-log/model/index.ts';
import type {
  RunLogDetail,
  RunStatus,
  RunStepStatus,
} from '../../../entities/run-log/model/index.ts';
import {
  FORM_LABEL_LOOK,
  FORM_ROWS_LOOK,
  FORM_ROW_LOOK,
  FORM_VALUE_LOOK,
} from '../../../shared/ui/ai-setting/index.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import type { RunDetailState, RunFileState } from '../hooks/index.ts';

const words = RUN_LOG_TEXT;
const d = RUN_LOG_TEXT.detail;

/** 실행 상태 → 키트 badge 변형(디자인 답 1: 대기 grey · 처리 중 orange · 완료 success · 실패 error). 표(RunsScreen)와 모달이 같이 쓴다. */
export const STATUS_LOOK = {
  queued: 'grey',
  processing: 'orange',
  done: 'success',
  failed: 'error',
} as const satisfies Record<RunStatus, 'grey' | 'success' | 'orange' | 'error'>;

/** 단계 상태 → 키트 badge 변형(판 S2·S3 — 처리 중 orange 는 cd 답 10-22). */
export const STEP_LOOK = {
  pending: 'grey',
  running: 'orange',
  done: 'success',
  failed: 'error',
} as const satisfies Record<
  RunStepStatus,
  'grey' | 'success' | 'orange' | 'error'
>;

/** 모듈 라벨: 고정 여섯은 이름, 그 밖은 id 그대로(RunsScreen 과 같은 꼴). */
const moduleLabel = (id: string) =>
  Object.hasOwn(words.modules, id) ? words.modules[id]! : id;

export interface RunDetailDialogProps {
  state: RunDetailState;
  /** 결과 파일 받기의 상태(useRunFile). */
  file: RunFileState;
  /** 닫은 뒤 초점이 갈 자리(그 줄의 문서 단추). */
  returnFocus: HTMLElement | null;
  onRetry(): void;
  onClose(): void;
  /** [내려받기] 누름(받는 중 막음은 처리기가 한다). */
  onDownload(name: string): void;
}

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-3 text-left text-style-pre-body-05 text-text-tertiary';
const cellClass =
  'h-11 whitespace-nowrap border-0 border-b border-solid border-border-tertiary px-3 text-left align-middle';
const STEP_COLUMNS = ['step', 'status', 'duration', 'tokens', 'cost'] as const;
const isNumberColumn = (key: (typeof STEP_COLUMNS)[number]) =>
  key === 'duration' || key === 'tokens' || key === 'cost';

function Field({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div className={FORM_ROW_LOOK}>
      <dt className={FORM_LABEL_LOOK}>{name}</dt>
      {/* 값 토막(값 + 곁 글 ml-2)은 한 줄에 잇는다 — 모델 카드의 세로 쌓기를 가로로 바꾼다. */}
      <dd
        className={cn(
          FORM_VALUE_LOOK,
          'flex-row flex-wrap items-center gap-0 text-style-pre-body-06 text-text-secondary',
        )}
      >
        {children}
      </dd>
    </div>
  );
}

function DetailBody({
  detail,
  fetching,
  onDownload,
}: {
  detail: RunLogDetail;
  fetching: RunFileState;
  onDownload(name: string): void;
}) {
  const busy = fetching.phase === 'busy';
  const module = moduleLabel(detail.module);
  const setting =
    detail.aiSetting === null ?
      null
    : aiSettingText(detail.aiSetting, words).text;
  const uploader = uploaderText(detail, words.unknownUploader);
  const times = detailTimes(detail);
  const total = runFigures(detail, words);
  const recorded = detail.stepUsageRecorded;
  const steps = d.steps;
  const launch = launchMark(detail);
  const resumed = resumedMark(detail);
  return (
    <>
      <dl className={FORM_ROWS_LOOK} data-testid="run-fields">
        {launch !== null && (
          <Field name={d.fields.launch}>
            <span data-testid="run-launch" className="tabular-nums">
              {d.launch(launch.first, launch.index, launch.size)}
            </span>
            <span
              data-testid="run-launch-siblings"
              className="ml-2 text-text-secondary"
            >
              {d.launchSiblings(launch.size - 1)}
            </span>
          </Field>
        )}
        {resumed !== null && (
          <Field name={d.fields.resumed}>
            <span data-testid="run-resumed" className="tabular-nums">
              {d.resumed(resumed)}
            </span>
          </Field>
        )}
        <Field name={d.fields.document}>
          {detail.documentName === null ?
            <span className="text-text-tertiary" data-document-missing>
              {words.empty}
            </span>
          : <span className="break-all">{detail.documentName}</span>}
        </Field>
        <Field name={d.fields.moduleFlow}>
          <span data-testid="module-flow">
            {module} · {flowEdition(detail.flowId)}
          </span>
          {setting !== null && (
            <small
              data-testid="ai-setting"
              className="ml-2 text-style-pre-caption-03 text-text-tertiary"
            >
              {d.aiSetting(module, setting)}
            </small>
          )}
        </Field>
        <Field name={d.fields.uploadedBy}>
          <span className={cn(uploader.missing && 'text-text-tertiary')}>
            {uploader.text}
          </span>
        </Field>
        <Field name={d.fields.at}>
          <span data-testid="times" className="tabular-nums">
            {times.start === null ?
              words.empty
            : times.end === null ?
              d.started(times.start)
            : `${d.started(times.start)} · ${d.finished(times.end)}`}
          </span>
        </Field>
        <Field name={d.fields.total}>
          <span data-testid="total" className="tabular-nums">
            {`${total.duration} · ${d.tokens(total.tokens)} · ${d.cost(total.cost)}`}
          </span>
        </Field>
      </dl>
      {!recorded && (
        <PageInfo icon={<PageInfoIcon />} data-testid="no-step-usage">
          {d.noStepUsage}
        </PageInfo>
      )}
      <div className="w-full overflow-x-auto">
        <table
          data-testid="run-steps"
          className="w-full border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary"
        >
          <thead>
            <tr>
              {STEP_COLUMNS.map((key) => (
                <th
                  key={key}
                  scope="col"
                  className={cn(headClass, isNumberColumn(key) && 'text-right')}
                >
                  {d.columns[key]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {detail.steps.length === 0 ?
              <tr>
                <td colSpan={STEP_COLUMNS.length} className={cellClass}>
                  {words.empty}
                </td>
              </tr>
            : detail.steps.map((step) => {
                const figures = stepFigures(step, recorded, words);
                return (
                  <tr
                    key={`${step.position}-${step.name}`}
                    data-step={step.name}
                  >
                    <td className={cellClass}>
                      {stepLabel(detail.module, step.name, steps)}
                    </td>
                    <td className={cellClass}>
                      <Badge
                        variant={STEP_LOOK[step.status]}
                        data-step-status={step.status}
                      >
                        {d.stepStatus[step.status]}
                      </Badge>
                    </td>
                    <td className={cn(cellClass, 'text-right tabular-nums')}>
                      {figures.duration}
                    </td>
                    <td className={cn(cellClass, 'text-right tabular-nums')}>
                      {figures.tokens}
                    </td>
                    <td className={cn(cellClass, 'text-right tabular-nums')}>
                      {figures.cost}
                    </td>
                  </tr>
                );
              })
            }
          </tbody>
        </table>
      </div>
      {recorded && (
        <p
          data-testid="step-usage-note"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {d.stepUsageNote}
        </p>
      )}
      {detail.status === 'failed' && (
        <PageInfo
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="run-failure"
        >
          {detail.failedStep === null ?
            d.failedOutside
          : d.failedAt(stepLabel(detail.module, detail.failedStep, steps))}
          {detail.errorCode !== null && ` · ${d.errorCode(detail.errorCode)}`}
        </PageInfo>
      )}
      <section className="flex flex-col gap-2" data-testid="run-files">
        <h3 className="m-0 text-style-pre-caption-01 text-text-tertiary">
          {d.files}
        </h3>
        {detail.files.length === 0 ?
          <p className="m-0 text-style-pre-body-06 text-text-tertiary">
            {words.empty}
          </p>
        : <ul className="m-0 flex list-none flex-col gap-2 p-0 text-style-pre-caption-03 text-text-tertiary">
            {shownFiles(detail.files).map((file, index) => (
              <li
                key={`${index}-${file.name}`}
                className="flex items-center gap-2"
              >
                <span className="min-w-0 break-all">{file.name}</span>
                {downloadable(detail, file) && (
                  <button
                    type="button"
                    data-file-download
                    aria-label={d.downloadLabel(file.name)}
                    aria-disabled={busy || undefined}
                    aria-busy={
                      (busy && fetching.name === file.name) || undefined
                    }
                    onClick={() => onDownload(file.name)}
                    className={cn(
                      buttonVariants({
                        variant: 'outlineBlack',
                        shape: 'round',
                        size: 'sm',
                      }),
                      busy && 'cursor-not-allowed opacity-40',
                    )}
                  >
                    <DownloadIcon aria-hidden />
                    {d.download}
                  </button>
                )}
              </li>
            ))}
          </ul>
        }
        {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(실패·404). */}
        <p
          role="alert"
          data-testid="file-error"
          className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
        >
          {(fetching.phase === 'failed' || fetching.phase === 'notFound') && (
            <>
              <CircleWarningIcon aria-hidden />
              {fetching.phase === 'notFound' ?
                d.fileNotFound
              : d.downloadFailed}
            </>
          )}
        </p>
      </section>
    </>
  );
}

export function RunDetailDialog({
  state,
  file,
  returnFocus,
  onRetry,
  onClose,
  onDownload,
}: RunDetailDialogProps) {
  const loading = useDelayed(state.phase === 'loading');
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="md"
        data-testid="run-detail"
        aria-describedby={undefined}
        aria-busy={state.phase === 'loading' || undefined}
        onCloseAutoFocus={(event) => {
          if (returnFocus === null) return;
          event.preventDefault();
          returnFocus.focus();
        }}
      >
        <div className="flex items-center gap-2">
          <DialogTitle>{d.title}</DialogTitle>
          {state.phase === 'ready' && (
            <Badge
              variant={STATUS_LOOK[state.detail.status]}
              data-status={state.detail.status}
            >
              {words.status.options[state.detail.status]}
            </Badge>
          )}
        </div>
        <div className="flex flex-col gap-5">
          {state.phase === 'ready' ?
            <DetailBody
              detail={state.detail}
              fetching={file}
              onDownload={onDownload}
            />
          : state.phase === 'notFound' ?
            <PageInfo icon={<PageInfoIcon />} data-testid="run-not-found">
              {d.notFound}
            </PageInfo>
          : state.phase === 'failed' ?
            <div
              role="alert"
              data-testid="run-detail-failure"
              className="flex flex-col items-start gap-4"
            >
              <PageInfo
                tone="error"
                icon={<CircleWarningIcon aria-hidden />}
                className="w-full"
              >
                {d.failed}
              </PageInfo>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={onRetry}
              >
                {words.retry}
              </Button>
            </div>
          : loading ?
            <LoadSkeleton label={d.loading} />
          : null}
        </div>
        <DialogFooter>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onClose}
          >
            {d.close}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
