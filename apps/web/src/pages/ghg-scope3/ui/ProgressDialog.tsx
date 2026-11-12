// S3-07 배출량 계산 창(밴드 S3W1 ② — Figma modal_배출량 계산 진행중 28029:2521 · 실패 28160:13433, 판 S3-07·07a 「그대로」).
// 모양만 한다 — 폴링은 화면(Scope3Screen)이 하고 이 창은 그 상태를 그린다(창을 닫아도 화면이 계속 본다, 판 S3-07b).
//   진행 → 아이콘(값 파일 V1·덧) · 글 둘(role="status") · 셈 한 줄(aria-live — 2초 폴링이 글 둘을 되읽지 않게 따로 둔다) · 실패 → 제목 + 갈래(failure — errorCode, S3W2a §1-6)의 본문 + [배출량 재계산하기](onRetry — 새 POST,
//   앞 실행은 그대로) · 갈래 file 은 같은 문서를 다시 계산해도 소용없어 [재계산] 대신 [데이터 업로드](onUpload — S3-02 흐름) ·
//   갈래 setup(설정 없음)은 다시 계산도 다시 올림도 풀지 못해 [닫기]만(S3W2c ② e6 대조 11) ·
//   진행 상태를 읽지 못함 → 한 줄. 서버의 실패 글(말투가 다르고 뜻이 접힘)은 싣지 않는다.
//   닫기(✕·Esc·바깥)는 onClose — 계산은 서버에서 이어 돈다. 다시 계산 중에는 닫지 않는다.
// sid:MARC-ISSUE-460 꼴: [배출량 재계산하기]가 있는 실패 창은 <form onSubmit>(Enter = 다시 계산), 열 때 초점은 그 단추, 닫히면 returnFocus.
import { useRef } from 'react';
import type { FormEvent } from 'react';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { SPARKLE } from '../../../entities/ghg-scope3/model/index.ts';
import type {
  FailureKind,
  RunProgress,
} from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogCloseIconButton,
  DialogContent,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const words = S3_TEXT.progressDialog;

/** 창이 그리는 갈래(완료는 화면이 창을 닫는다). */
export type ProgressView = 'running' | 'failed' | 'lost';

/** 셈 한 줄(창·창 닫은 뒤 화면 같은 꼴). 단계를 못 읽으면 없음. */
export function ProgressCount({ progress }: { progress: RunProgress | null }) {
  if (progress === null) return null;
  return (
    <p
      aria-live="polite"
      data-testid="s3-progress-count"
      className="m-0 text-style-pre-caption-03 text-text-tertiary"
    >
      {progress.kind === 'assembling' ?
        words.assembling
      : words.countDone(progress.total, progress.done)}
    </p>
  );
}

/** 반짝이 + 둘레 호(90°)만 1초에 한 바퀴. 움직임 줄이기면 돌지 않는다. */
function ProgressIcon() {
  return (
    <span
      aria-hidden="true"
      data-testid="s3-progress-icon"
      className="relative flex size-8 items-center justify-center text-text-brand"
    >
      <svg
        viewBox="0 0 32 32"
        fill="none"
        className="absolute inset-0 size-8 motion-safe:animate-spin"
      >
        <path
          d="M16 1a15 15 0 0 1 15 15"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      <svg viewBox="0 0 16.5 16.5" fill="none" className="size-4">
        <path
          d={SPARKLE}
          fill="currentColor"
          stroke="currentColor"
          strokeWidth="0.5"
        />
      </svg>
    </span>
  );
}

export interface ProgressDialogProps {
  view: ProgressView;
  /** 진행 셈(view 가 running 일 때). */
  progress: RunProgress | null;
  /** 실패 글의 갈래(view 가 failed 일 때). */
  failure: FailureKind;
  /** 다시 계산을 보내는 중. */
  retrying: boolean;
  /** 다시 계산이 거절됐으면 그 글. */
  retryProblem: string | null;
  returnFocus(): HTMLElement | null;
  onRetry(): void;
  /** 갈래 file 의 [데이터 업로드]. */
  onUpload(): void;
  onClose(): void;
}

export function ProgressDialog({
  view,
  progress,
  failure,
  retrying,
  retryProblem,
  returnFocus,
  onRetry,
  onUpload,
  onClose,
}: ProgressDialogProps) {
  const retryRef = useRef<HTMLButtonElement>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!retrying) onRetry();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !retrying) onClose();
      }}
    >
      <DialogContent
        size="lg"
        className="w-[960px] max-w-[calc(100vw-64px)]"
        data-testid="s3-progress-dialog"
        data-view={view}
        onOpenAutoFocus={(event) => {
          if (view !== 'failed') return;
          event.preventDefault();
          retryRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <DialogTitle>{words.title}</DialogTitle>
          <DialogCloseIconButton aria-label={words.close} />
        </div>
        {view === 'failed' && failure === 'file' ?
          <div className="flex min-h-[300px] flex-col items-center justify-center gap-2 text-center">
            <p
              role="alert"
              className="m-0 text-style-pre-heading-02 text-text-primary"
            >
              {words.failedTitle}
            </p>
            <p className="m-0 max-w-[420px] text-style-pre-body-06 text-text-secondary">
              {words.failureBody.file}
            </p>
            <Button
              ref={retryRef}
              variant="solidBlack"
              shape="round"
              size="md"
              className="mt-6"
              onClick={onUpload}
            >
              {S3_TEXT.result.upload}
            </Button>
          </div>
        : view === 'failed' && failure === 'setup' ?
          // setup(설정 없음)은 [배출량 재계산하기]·[데이터 업로드] 없이 [닫기]만(S3W2c ② e6 대조 11 — 운영 관리자 몫).
          <div className="flex min-h-[300px] flex-col items-center justify-center gap-2 text-center">
            <p
              role="alert"
              className="m-0 text-style-pre-heading-02 text-text-primary"
            >
              {words.failedTitle}
            </p>
            <p className="m-0 max-w-[420px] text-style-pre-body-06 text-text-secondary">
              {words.failureBody.setup}
            </p>
            <Button
              ref={retryRef}
              variant="solidBlack"
              shape="round"
              size="md"
              className="mt-6"
              onClick={onClose}
            >
              {words.close}
            </Button>
          </div>
        : view === 'failed' ?
          <form
            onSubmit={submit}
            className="flex min-h-[300px] flex-col items-center justify-center gap-2 text-center"
          >
            <p
              role="alert"
              className="m-0 text-style-pre-heading-02 text-text-primary"
            >
              {words.failedTitle}
            </p>
            <p className="m-0 max-w-[420px] text-style-pre-body-06 text-text-secondary">
              {words.failureBody[failure]}
            </p>
            {retryProblem !== null && (
              <p
                role="alert"
                data-testid="s3-retry-problem"
                className="m-0 text-style-pre-caption-03 text-support-error-accent"
              >
                {retryProblem}
              </p>
            )}
            <Button
              ref={retryRef}
              type="submit"
              variant="solidBlack"
              shape="round"
              size="md"
              loading={retrying}
              className="mt-6"
            >
              {words.retry}
            </Button>
          </form>
        : <div className="flex min-h-[300px] flex-col items-center justify-center gap-2 text-center">
            {view === 'running' ?
              <>
                <ProgressIcon />
                <div role="status" className="flex flex-col gap-2">
                  <p className="m-0 text-style-pre-heading-02 text-text-secondary">
                    {words.runningTitle}
                  </p>
                  <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                    {words.runningBody[0]}
                    <br />
                    {words.runningBody[1]}
                  </p>
                </div>
                <ProgressCount progress={progress} />
              </>
            : <p
                role="status"
                className="m-0 text-style-pre-body-06 text-support-error-accent"
              >
                {words.pollFailed}
              </p>
            }
          </div>
        }
      </DialogContent>
    </Dialog>
  );
}
