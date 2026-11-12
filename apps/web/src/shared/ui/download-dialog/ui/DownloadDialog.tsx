// 공용 받기 모달(밴드 TRW14 ① — 결정 sid:MARC-ENT-662 꼴 · sid:MARC-ENT-663 자리, 값 TR-04a r2 · band-handoffs/download-dialog-values.md).
//   모양 부품: 저장소도 글도 모른다. 글(머리·설명·각주·닫기·(?) 이름·실패·받는 중)은 전부 props 로 받는다(이 폴더에 한국어 글자 0 — 시험이 원문을 본다).
//   - 파일마다 묶음 하나: 이름(+ 꺼졌으면 (?)) · 설명 한 줄(늘 보임) → 줄 전체가 단추(아이콘 · 파일 이름 · 받기 아이콘).
//   - 받기: 누르면 download() → 이 부품이 save(blob, fileName)(기본 shared/lib/saveBlob). 받는 동안 그 줄에 도는 표시, 다시 눌러도 한 번(ref).
//     실패는 그 줄 아래 role=alert(앞 경고 아이콘 16 · failedText — DownloadButton 실패 줄과 같은 꼴, gap-1). 다시 누르면 지우고 다시 받는다.
//   - 꺼짐(disabledReason): aria-disabled + 흐림 · not-allowed, 누름이 download 를 부르지 않는다. 이유는 이름 옆 (?) 단추의 공용 툴팁 —
//     꺼진 파일 단추 자체에는 툴팁을 달지 않는다.
//   - 아래 각주 한 줄 · 가운데 [닫기] 하나(solidBlack round). 닫히면 초점은 returnFocus() 의 요소로(EntryDownloadDialog 꼴).
//   - 부르는 쪽이 열 때만 그린다(닫으면 내린다 — 받는 중·실패 글이 다음에 남지 않게).
//   값 → 앱 토큰: 폭 640 = DialogContent md · 안쪽 space-8 = Content 의 32 · 묶음 사이 space-6 = gap-6 · 묶음 안 space-3 = gap-3 ·
//   머리 700 18/1.4 = pre-heading-02 · 이름 500 14/1.6 = pre-body-05 secondary · 설명 400 14/1.6 = pre-body-06 tertiary ·
//   단추 h 64 = h-16 · 여백 space-1 space-4 = py-1 px-4 · 1px button-grey = border-button-grey · radius-component = rounded-component ·
//   파일 이름 500 16/1.6 = pre-body-02 · 받기 아이콘 16 grey-400 = size-4 text-grey-400 · (?) 16 tertiary = size-4 text-text-tertiary ·
//   툴팁 tooltip-background #383C40 = bg-grey-800 · 흰 500 12/1.4 = pre-caption-02 text-primary-inverse · 여백 space-1 space-2 = py-1 px-2 ·
//   radius-control = rounded-control · 오른쪽 space-2 = side right · sideOffset 8 · 한 줄 = whitespace-nowrap.
import { useRef, useState } from 'react';
import type { ReactNode } from 'react';

import {
  CircleQuestionIcon,
  CircleWarningIcon,
  DownloadIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Spinner } from '@marcspon/ui/components/spinner';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import { saveBlob } from '../../../lib/saveBlob.ts';
import { Button } from '../../button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../dialog/index.ts';

export interface DownloadDialogFile {
  /** 줄 열쇠(data-file 과 data-testid 에 쓴다). */
  key: string;
  /** 묶음 이름(단추 위). */
  name: string;
  /** 설명 한 줄(늘 보인다). */
  description: string;
  /** 단추 안 파일 이름. */
  fileLabel: string;
  /** 단추 왼쪽 파일 꼴 아이콘(48). */
  icon: ReactNode;
  /** 있으면 꺼진 줄 — 이름 옆 (?) 툴팁 글. */
  disabledReason?: string;
  /** 파일을 받는다(쓰는 화면이 저장소를 부른다). 거절되면 failedText. */
  download: () => Promise<{ blob: Blob; fileName: string }>;
}

export interface DownloadDialogProps {
  title: string;
  /** 아래 각주 한 줄. */
  footnote?: string;
  closeLabel: string;
  /** (?) 단추 aria-label 머리(「<머리>: <이유>」). */
  helpLabel: string;
  /** 받기 실패 글(그 줄 아래 role=alert). */
  failedText: string;
  /** 받는 동안 도는 표시의 이름. */
  busyLabel: string;
  files: readonly DownloadDialogFile[];
  /** 닫기([닫기] · Esc · 덮개). */
  onClose(): void;
  /** 닫힌 뒤 초점을 돌릴 요소(연 단추). */
  returnFocus(): HTMLElement | null;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
  /** 모달 data-testid. */
  testId?: string;
}

export function DownloadDialog({
  title,
  footnote,
  closeLabel,
  helpLabel,
  failedText,
  busyLabel,
  files,
  onClose,
  returnFocus,
  save = saveBlob,
  testId = 'download-dialog',
}: DownloadDialogProps) {
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const busyRef = useRef(false);

  const take = async (file: DownloadDialogFile) => {
    if (file.disabledReason !== undefined || busyRef.current) return;
    busyRef.current = true;
    setBusy(file.key);
    setFailed(null);
    try {
      const out = await file.download();
      save(out.blob, out.fileName);
    } catch {
      setFailed(file.key);
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
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
        data-testid={testId}
        className="gap-6"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <DialogTitle className="m-0 text-style-pre-heading-02 text-text-secondary">
          {title}
        </DialogTitle>
        <TooltipProvider>
          <ul className="m-0 flex list-none flex-col gap-6 p-0">
            {files.map((file) => {
              const off = file.disabledReason !== undefined;
              return (
                <li
                  key={file.key}
                  data-file={file.key}
                  className="flex min-w-0 flex-col gap-3"
                >
                  <div className="flex flex-col">
                    <p className="m-0 flex items-center gap-1 text-style-pre-body-05 text-text-secondary">
                      {file.name}
                      {off && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              data-testid={`${testId}-help-${file.key}`}
                              aria-label={`${helpLabel}: ${file.disabledReason}`}
                              className="inline-flex cursor-help border-0 bg-transparent p-0 text-text-tertiary [&_svg]:size-4"
                            >
                              <CircleQuestionIcon aria-hidden />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent
                            side="right"
                            sideOffset={8}
                            showArrow={false}
                            className="max-w-none whitespace-nowrap rounded-control bg-grey-800 px-2 py-1 text-style-pre-caption-02 text-text-primary-inverse"
                          >
                            {file.disabledReason}
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </p>
                    <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                      {file.description}
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid={`${testId}-file-${file.key}`}
                    aria-disabled={off || undefined}
                    aria-busy={busy === file.key || undefined}
                    onClick={() => void take(file)}
                    className={cn(
                      'box-border flex h-16 w-full items-center gap-2 rounded-component border border-solid border-button-grey bg-button-white px-4 py-1 text-left text-style-pre-body-02 text-text-secondary',
                      off ? 'cursor-not-allowed opacity-40' : 'cursor-pointer',
                    )}
                  >
                    <span
                      aria-hidden
                      className="inline-flex shrink-0 [&_svg]:size-12"
                    >
                      {file.icon}
                    </span>
                    <span className="min-w-0 flex-1 truncate">
                      {file.fileLabel}
                    </span>
                    {busy === file.key ?
                      <Spinner aria-label={busyLabel} className="size-4" />
                    : <DownloadIcon
                        aria-hidden
                        className="size-4 shrink-0 text-grey-400"
                      />
                    }
                  </button>
                  {failed === file.key && (
                    <p
                      role="alert"
                      data-testid={`${testId}-problem-${file.key}`}
                      className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent"
                    >
                      <CircleWarningIcon
                        aria-hidden
                        className="size-4 shrink-0"
                      />
                      {failedText}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </TooltipProvider>
        {footnote !== undefined && (
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {footnote}
          </p>
        )}
        <DialogFooter className="justify-center gap-2 pt-0 sm:justify-center">
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            className="min-w-20"
            onClick={onClose}
          >
            {closeLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
