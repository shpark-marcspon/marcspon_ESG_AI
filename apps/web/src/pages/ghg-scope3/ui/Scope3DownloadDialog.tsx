// S3-15 「데이터 다운로드」 창(밴드 S3D1 ② — 판 S3-15 r1 [1차], 꼴은 S5 EntryDownloadDialog 그대로 · 감독 처분 Q5).
//   결과 화면의 [데이터 다운로드]가 연다. 받기 줄은 하나(Scope 3 데이터 — Scope·사업장 거름 없음). 줄 전체가 단추이고 saveBlob 을 직접 부른다.
//   받는 동안 그 줄에 도는 표시, 다시 눌러도 한 번(ref). 실패는 그 줄 아래 role=alert(그 해 결과 없음 · 회사 거절 · 그 밖).
//   둘째 무리 「온실가스 인벤토리 보고서」(PDF)는 1차 숨김(자리 0). [취소]·[확인] 둘 다 닫기. 닫히면 초점은 연 단추로.
import { useRef, useState } from 'react';

import { DownloadIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Spinner } from '@marcspon/ui/components/spinner';

import type { Scope3Port } from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { ReportXlsxIcon } from '../../../shared/ui/file-type-icon/index.ts';

const words = S3_TEXT.download;

export interface Scope3DownloadDialogProps {
  port: Scope3Port;
  year: number;
  returnFocus(): HTMLElement | null;
  onClose(): void;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
}

export function Scope3DownloadDialog({
  port,
  year,
  returnFocus,
  onClose,
  save = saveBlob,
}: Scope3DownloadDialogProps) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const busyRef = useRef(false);

  const take = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    const out = await port.exportFile(year);
    busyRef.current = false;
    setBusy(false);
    if (out.kind === 'ok') save(out.value.blob, out.value.fileName);
    else
      setProblem(
        out.kind === 'notFound' ? words.notFound
        : out.kind === 'refused' ? S3_TEXT.company[out.company]
        : words.failed,
      );
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="md"
        data-testid="s3-download"
        className="gap-6"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <DialogTitle className="flex h-10 items-center text-style-pre-heading-02 text-text-secondary">
          {words.title}
        </DialogTitle>
        <div className="flex flex-col gap-2.5">
          <div>
            <p className="m-0 text-style-pre-body-05 text-text-secondary">
              {words.groupTitle}
            </p>
            <p className="m-0 text-style-pre-body-06 text-text-tertiary">
              {words.groupBody}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <button
              type="button"
              data-testid="s3-download-file"
              aria-busy={busy || undefined}
              onClick={() => void take()}
              className="box-border flex h-16 w-full cursor-pointer items-center gap-2 rounded-component border border-solid border-border-quaternary bg-background-primary px-4 py-2 text-left text-style-pre-body-03 text-text-secondary"
            >
              <ReportXlsxIcon aria-hidden className="size-12 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{words.line}</span>
              {busy ?
                <Spinner aria-label={words.busy} className="size-4" />
              : <DownloadIcon aria-hidden className="size-4 shrink-0" />}
            </button>
            {problem !== null && (
              <p
                role="alert"
                data-testid="s3-download-problem"
                className="m-0 text-style-pre-caption-03 text-support-error-accent"
              >
                {problem}
              </p>
            )}
          </div>
        </div>
        <DialogFooter className="justify-center gap-2 pt-0 sm:justify-center">
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            className="min-w-20"
            onClick={onClose}
          >
            {words.cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            className="min-w-20"
            onClick={onClose}
          >
            {words.ok}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
