// S3-03 데이터 업로드 창(밴드 S3W1 ② — Figma [modal] Upload 28029:2331, 판 S3-03 「그대로」). 통합 템플릿 파일 하나를 올린다
// (카테고리별로 따로 올리지 않는다 — 사용자 10-29). 머리의 「고른 카테고리 n개」는 화면 표시만이다(요청에 싣지 않는다).
//   - [양식 다운로드] = port.template() — outline 알약 sm·아이콘 없음(값 파일 GX3 고침 9 · S1·2 꼴. 공용 DownloadButton 은 내려받기 아이콘을 늘 그려 이 창이 직접 부른다). 실패면 단추 옆 한 줄.
//   - 파일은 하나. 고르면 acceptFile(xls·xlsx·0바이트·20MB)로 거르고, 아니면 까닭 한 줄(요청 0).
//   - [데이터 업로드] = upload(file, year) → start(documentId, year). 올린 문서는 쥐고 있다가 실행만 거절되면(예 422 flow_not_runnable)
//     다시 누를 때 같은 문서로 실행만 다시 보낸다(문서는 서버에 남는다 — 보고 물을 거리). 파일을 바꾸면 버린다.
//   - 거절 글: 413 크기 · 올리기 422 validation_error(파일 거절) · 400 invalid_options · 422 flow_not_runnable · 403(운영 관리자 글) · 회사 거절 셋 · 그 밖 한 줄. 서버 message 0.
// sid:MARC-ISSUE-460 꼴: <form onSubmit>, 열 때 초점은 끌어다 놓기 칸, 닫히면 초점을 returnFocus 로.
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

import {
  CircleWarningIcon,
  XlsIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import type {
  Scope3Port,
  WriteOutcome,
} from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { acceptFile } from '../../../entities/ghg-scope3/model/index.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { FileDropzone } from '../../../shared/ui/file-dropzone/index.ts';

const words = S3_TEXT.uploadDialog;

export interface UploadDialogProps {
  port: Scope3Port;
  year: number;
  /** 고른 카테고리 수(표시만). */
  chosenCount: number;
  operator: boolean;
  returnFocus(): HTMLElement | null;
  onStarted(runId: string): void;
  onClose(): void;
}

/** 쓰기 거절 → 화면 글. */
function problemOf(
  outcome: Exclude<WriteOutcome<unknown>, { kind: 'ok' }>,
  operator: boolean,
): string {
  if (outcome.kind === 'refused') return S3_TEXT.company[outcome.company];
  if (outcome.kind === 'failed') return words.failed;
  switch (outcome.code) {
    case 'UPLOAD_TOO_LARGE':
      return S3_TEXT.fileProblem.size;
    case 'INVALID_OPTIONS':
      return words.invalidOptions;
    case 'FLOW_NOT_RUNNABLE':
      return words.flowNotRunnable;
    case 'FORBIDDEN':
      return operator ? words.operatorForbidden : words.failed;
    default:
      return words.failed;
  }
}

export function UploadDialog({
  port,
  year,
  chosenCount,
  operator,
  returnFocus,
  onStarted,
  onClose,
}: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** 올린 문서(실행만 거절됐을 때 다시 쓴다 — 파일을 바꾸면 버린다). */
  const uploaded = useRef<{ file: File; documentId: string } | null>(null);
  const busyRef = useRef(false);
  const zoneRef = useRef<HTMLDivElement>(null);

  const pick = (picked: File | null) => {
    uploaded.current = null;
    if (picked === null) {
      setFile(null);
      setProblem(null);
      return;
    }
    const why = acceptFile(picked);
    setFile(why === null ? picked : null);
    setProblem(why === null ? null : S3_TEXT.fileProblem[why]);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (file === null || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    try {
      let documentId =
        uploaded.current?.file === file ? uploaded.current.documentId : null;
      if (documentId === null) {
        const sent = await port.upload(file, year);
        if (sent.kind !== 'ok') {
          // 문서 만들기의 VALIDATION_ERROR 는 파일 칸(이름·크기)이 서버 조건에 안 맞는 것 — 다시 해도 같다(GX1 M-5).
          setProblem(
            sent.kind === 'rejected' && sent.code === 'VALIDATION_ERROR' ?
              words.fileRejected
            : problemOf(sent, operator),
          );
          return;
        }
        documentId = sent.value.documentId;
        uploaded.current = { file, documentId };
      }
      const started = await port.start(documentId, year);
      if (started.kind !== 'ok') {
        setProblem(problemOf(started, operator));
        return;
      }
      onStarted(started.value.runId);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busyRef.current) onClose();
      }}
    >
      <DialogContent
        size="md"
        data-testid="s3-upload-dialog"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          zoneRef.current
            ?.querySelector<HTMLElement>('[role="button"]')
            ?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <form
          onSubmit={(event) => void submit(event)}
          className="flex flex-col gap-4"
        >
          <DialogTitle>{words.title}</DialogTitle>
          <p
            data-testid="s3-chosen-count"
            className="m-0 text-style-pre-body-05 text-text-secondary"
          >
            {words.chosen(chosenCount)}
          </p>
          <div ref={zoneRef}>
            <FileDropzone
              itemList={
                file === null ?
                  []
                : [
                    {
                      id: 'scope3-file',
                      name: file.name,
                      size: file.size,
                      date: '',
                      file,
                    },
                  ]
              }
              onChangeItemList={(items) => pick(items.at(-1)?.file ?? null)}
              maxCount={1}
              isUploading={busy}
              guide={words.guide}
              formats={words.formats}
              invalid={problem !== null}
              describedBy={problem === null ? undefined : 's3-upload-problem'}
            />
          </div>
          {problem !== null && (
            <p
              id="s3-upload-problem"
              role="alert"
              data-testid="s3-upload-problem"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4"
            >
              <CircleWarningIcon aria-hidden />
              {problem}
            </p>
          )}
          {/* 양식 칸(값 파일 GX3 ② 고침 9 — Scope 1·2 올리기 창 EntryUploadDialog 꼴 그대로): 앞 파일 아이콘 · 제목 · outline 알약(아이콘 없음). */}
          <div className="flex flex-col gap-2 rounded-lg bg-background-secondary p-6">
            <div className="flex flex-wrap items-center gap-2">
              <XlsIcon
                aria-hidden
                data-testid="s3-template-icon"
                className="size-7 shrink-0 text-support-success"
              />
              <p className="m-0 flex-1 text-style-pre-body-04">
                {words.templateTitle}
              </p>
              <TemplateButton port={port} />
            </div>
            <p className="m-0 text-style-pre-body-06 text-text-secondary">
              {words.templateGuide}
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              disabled={busy}
              onClick={onClose}
            >
              {words.cancel}
            </Button>
            <Button
              type="submit"
              variant="solidBlack"
              shape="round"
              size="md"
              disabled={file === null}
              loading={busy}
            >
              {busy ? words.submitting : words.submit}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** [양식 다운로드] — 받는 동안 한 번만, 실패면 단추 옆 role="alert" 한 줄(공용 DownloadButton 과 같은 갈래, 아이콘만 없음). */
function TemplateButton({ port }: { port: Scope3Port }) {
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const press = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setFailed(false);
    try {
      const read = await port.template();
      if (read.kind !== 'ok') throw new Error('template failed');
      saveBlob(read.value.blob, read.value.fileName);
    } catch {
      setFailed(true);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <p
        role="alert"
        data-testid="s3-template-error"
        className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
      >
        {failed && (
          <>
            <CircleWarningIcon aria-hidden />
            {words.templateFailed}
          </>
        )}
      </p>
      <Button
        type="button"
        variant="outlineBlack"
        shape="round"
        size="sm"
        loading={busy}
        data-testid="s3-template"
        onClick={() => void press()}
      >
        {words.templateDownload}
      </Button>
    </span>
  );
}
