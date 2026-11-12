// S4 「데이터 업로드」 창(밴드 W12-5 ③ — Figma 28535:9577·9593, 스펙 ① S4. 꼴은 Scope 3 UploadDialog 를 옮겨 적음 — pages 끼리 import 0).
//   파일 하나를 맨 바이트로 올린다. 연도·사업장은 양식이 말한다(고르는 것 없음). 고르면 acceptEntryUpload(.xlsx·20MB — 서버 값)로 걸러 요청 0.
//   올리는 동안 닫기를 막는다(Esc·✕·[취소] — busyRef): 닫히면 결과를 보일 자리가 없다.
//   답: 값이 든 200 만 창을 닫는다(onUploaded). 값 안 든 200 둘은 창 그대로 — 닫으면 「됐다」로 읽힌다.
//   ★ failed 는 서버가 안 했다는 뜻이 아니다(커밋 뒤 답만 끊길 수 있다): onWrote 로 표를 다시 읽고 「결과를 모른다」고 말한다. 「실패」로 쓰지 않는다.
//   파일을 못 읽으면(고른 뒤 디스크에서 바뀜) 보내지 않은 것이 확실하니 「모른다」고 말하지 않는다: 파일을 비우고 다시 고르게 한다.
//   422 글은 서버 글 그대로(uploadProblems — 시트 이름은 주소에 있을 때만). 파일은 그대로 둔다. 파일을 바꾸면 글을 지운다.
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

import {
  CircleWarningIcon,
  XlsIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import type {
  CompanyRefusal,
  GhgEntryPort,
  GhgOrganizationPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  acceptEntryUpload,
  uploadOutcome,
  uploadProblems,
} from '../../../entities/ghg/model/index.ts';
import type {
  EntryUploadProblem,
  EntryUploadResult,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { FileDropzone } from '../../../shared/ui/file-dropzone/index.ts';
import { EntryTemplateDialog } from './EntryTemplateDialog.tsx';

const words = GHG_TEXT.inventory.bulk.upload;

export interface EntryUploadDialogProps {
  port: GhgEntryPort;
  organization: GhgOrganizationPort;
  year: number;
  companyText: Record<CompanyRefusal, string>;
  returnFocus(): HTMLElement | null;
  /** 표를 다시 읽는다(참 = 다시 읽음). */
  onWrote(): Promise<boolean>;
  /** 값이 든 200 — 부르는 쪽이 창을 닫고 표를 다시 읽는다. */
  onUploaded(result: EntryUploadResult): void;
  onClose(): void;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
}

export function EntryUploadDialog({
  port,
  organization,
  year,
  companyText,
  returnFocus,
  onWrote,
  onUploaded,
  onClose,
  save,
}: EntryUploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [lines, setLines] = useState<EntryUploadProblem[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [template, setTemplate] = useState(false);
  const busyRef = useRef(false);
  const zoneRef = useRef<HTMLDivElement>(null);
  const templateRef = useRef<HTMLButtonElement>(null);

  const clear = () => {
    setProblem(null);
    setLines(null);
  };

  const pick = (picked: File | null) => {
    clear();
    if (picked === null) {
      setFile(null);
      return;
    }
    const why = acceptEntryUpload(picked);
    setFile(why === null ? picked : null);
    if (why !== null) setProblem(words[why]);
  };

  const send = async (chosen: File) => {
    const out = await port.upload(year, chosen);
    switch (out.kind) {
      case 'ok': {
        const outcome = uploadOutcome(out.value);
        if (outcome === 'filled') {
          busyRef.current = false;
          onUploaded(out.value);
          return;
        }
        setProblem(words[outcome]);
        return;
      }
      case 'rejected':
        setLines(uploadProblems(out.fields));
        return;
      case 'tooLarge':
        setProblem(words.size);
        return;
      case 'refused':
        setProblem(companyText[out.company]);
        return;
      case 'unreadable':
        // 보내지 않았다 — 표는 그대로이니 다시 읽지 않고, 같은 파일로 다시 눌러도 안 풀리니 비운다.
        setFile(null);
        setProblem(words.unreadable);
        return;
      case 'locked':
      case 'notFound':
        setProblem(words[out.kind]);
        await onWrote();
        return;
      case 'failed':
        setProblem((await onWrote()) ? words.unknownRead : words.unknownUnread);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (file === null || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    clear();
    try {
      await send(file);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <>
      <Dialog
        open
        onOpenChange={(open) => {
          if (!open && !busyRef.current) onClose();
        }}
      >
        <DialogContent
          size="md"
          data-testid="entry-upload"
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
            <DialogTitle className="flex h-10 items-center text-style-pre-heading-02 text-text-secondary">
              {words.title}
            </DialogTitle>
            <div ref={zoneRef}>
              <FileDropzone
                itemList={
                  file === null ?
                    []
                  : [
                      {
                        id: 'entry-upload-file',
                        name: file.name,
                        size: file.size,
                        date: '',
                        file,
                      },
                    ]
                }
                // GX2 L-7: 개수 상한을 두지 않아 둘째 파일이 앞 파일을 바꿔 끼운다(마지막 것 하나만 — pick 이 앞 오류 글도 지움).
                onChangeItemList={(items) => pick(items.at(-1)?.file ?? null)}
                isUploading={busy}
                guide={words.guide}
                formats={words.formats}
                invalid={problem !== null || lines !== null}
                describedBy={
                  problem !== null ? 'entry-upload-problem'
                  : lines !== null ?
                    'entry-upload-lines'
                  : undefined
                }
              />
            </div>
            {problem !== null && (
              <p
                id="entry-upload-problem"
                role="alert"
                data-testid="entry-upload-problem"
                className="m-0 flex items-start gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
              >
                <CircleWarningIcon aria-hidden />
                {problem}
              </p>
            )}
            {lines !== null && (
              <div
                id="entry-upload-lines"
                role="alert"
                data-testid="entry-upload-lines"
                className="flex flex-col gap-1"
              >
                <p className="m-0 text-style-pre-body-05 text-support-error">
                  {words.linesHead}
                </p>
                <ul
                  tabIndex={0}
                  aria-label={words.linesHead}
                  className="m-0 flex max-h-[200px] list-none flex-col gap-1 overflow-y-auto p-0 text-style-pre-body-06"
                >
                  {lines.map((line, index) => (
                    <li key={index}>
                      {line.where !== null && (
                        <span className="text-text-secondary">
                          {line.where}{' '}
                        </span>
                      )}
                      <span className="text-support-error">{line.text}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex flex-col gap-2 rounded-lg bg-background-secondary p-6">
              <div className="flex flex-wrap items-center gap-2">
                <XlsIcon
                  aria-hidden
                  className="size-7 shrink-0 text-support-success"
                />
                <p className="m-0 flex-1 text-style-pre-body-04">
                  {words.templateTitle}
                </p>
                <Button
                  ref={templateRef}
                  variant="outlineBlack"
                  shape="round"
                  size="sm"
                  data-testid="entry-template-open"
                  disabled={busy}
                  onClick={() => setTemplate(true)}
                >
                  {words.templateOpen}
                </Button>
              </div>
              <p className="m-0 text-style-pre-body-06 text-text-secondary">
                {words.templateGuide1}
                <br />
                {words.templateGuide2}
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
                data-testid="entry-upload-submit"
                disabled={file === null}
                loading={busy}
              >
                {busy ? words.submitting : words.submit}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      {template && (
        <EntryTemplateDialog
          port={port}
          organization={organization}
          year={year}
          companyText={companyText}
          returnFocus={() => templateRef.current}
          onClose={() => setTemplate(false)}
          save={save}
        />
      )}
    </>
  );
}
