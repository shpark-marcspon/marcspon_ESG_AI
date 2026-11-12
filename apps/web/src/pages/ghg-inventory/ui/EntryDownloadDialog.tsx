// S5 「데이터 다운로드」 창(밴드 W12-5 ② — Figma 28538:9695, 스펙 ① S5). S2 [데이터 다운로드] 가 연다.
//   받기 줄 셋(전체·Scope 1·Scope 2)은 줄 전체가 단추다 — 공용 DownloadButton 은 Button 꼴이라 576×64 줄이 안 돼(발주서 Q8) 이 창이 saveBlob 을 직접 부른다.
//   받는 동안 그 줄에 도는 표시, 다시 눌러도 한 번(ref). 실패는 그 줄 아래 role=alert. 둘째 무리 「온실가스 인벤토리 보고서」는 1차 숨김(자리 0).
//   [취소]·[확인] 둘 다 닫기(디자인 e6 — Figma 그대로). 닫히면 초점은 연 단추로.
import { useRef, useState } from 'react';

import { DownloadIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Spinner } from '@marcspon/ui/components/spinner';

import type {
  CompanyRefusal,
  GhgEntryPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { ReportXlsxIcon } from '../../../shared/ui/file-type-icon/index.ts';

const words = GHG_TEXT.inventory.bulk.download;

type ExportScope = 'all' | 1 | 2;

const LINES: readonly { scope: ExportScope; label: string }[] = [
  { scope: 'all', label: words.all },
  { scope: 1, label: words.scope1 },
  { scope: 2, label: words.scope2 },
];

export interface EntryDownloadDialogProps {
  port: GhgEntryPort;
  year: number;
  companyText: Record<CompanyRefusal, string>;
  returnFocus(): HTMLElement | null;
  onClose(): void;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
}

export function EntryDownloadDialog({
  port,
  year,
  companyText,
  returnFocus,
  onClose,
  save = saveBlob,
}: EntryDownloadDialogProps) {
  const [busy, setBusy] = useState<ExportScope | null>(null);
  const [problem, setProblem] = useState<{
    scope: ExportScope;
    text: string;
  } | null>(null);
  const busyRef = useRef(false);

  const take = async (scope: ExportScope) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(scope);
    setProblem(null);
    const out = await port.exportFile(year, scope);
    busyRef.current = false;
    setBusy(null);
    if (out.kind === 'ok') save(out.value.blob, out.value.fileName);
    else
      setProblem({
        scope,
        text:
          out.kind === 'notFound' ? words.notFound
          : out.kind === 'refused' ? companyText[out.company]
          : words.failed,
      });
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
        data-testid="entry-download"
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
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {LINES.map(({ scope, label }) => (
              <li key={scope} className="flex flex-col gap-1">
                <button
                  type="button"
                  data-testid={`entry-download-${scope}`}
                  aria-busy={busy === scope || undefined}
                  onClick={() => void take(scope)}
                  className="box-border flex h-16 w-full cursor-pointer items-center gap-2 rounded-component border border-solid border-border-quaternary bg-background-primary px-4 py-2 text-left text-style-pre-body-03 text-text-secondary"
                >
                  <ReportXlsxIcon aria-hidden className="size-12 shrink-0" />
                  <span className="min-w-0 flex-1 truncate">{label}</span>
                  {busy === scope ?
                    <Spinner aria-label={words.busy} className="size-4" />
                  : <DownloadIcon aria-hidden className="size-4 shrink-0" />}
                </button>
                {problem?.scope === scope && (
                  <p
                    role="alert"
                    data-testid={`entry-download-problem-${scope}`}
                    className="m-0 text-style-pre-caption-03 text-support-error-accent"
                  >
                    {problem.text}
                  </p>
                )}
              </li>
            ))}
          </ul>
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
