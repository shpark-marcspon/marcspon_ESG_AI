// 파트 결과 머리(밴드 TRW0b, 시안 TR-04 「스토리 4~41쪽(38쪽) 완료 회차 2 …」·TR-04a). 모양 부품: props 만 받는다.
// - 머리 한 줄(밴드 TRP2 TC20): 제목 body-01 · 상태 배지 · 회차 회색 배지 · 「스타일 · 고객사 용어집 n개 · 시작 · 끝남」 caption-03 | 오른쪽 [내려받기].
// - [내려받기](밴드 TRW14 ① — TR-04a r2, sid:MARC-ENT-662): 단추 하나가 공용 받기 모달(shared/ui/download-dialog)을 연다. 파일이 하나도 없어도 켠다.
//   모달은 Word 셋을 늘 그리고(차례 FILE_KEYS) 만들지 않은 파일은 끈 줄 + (?) 까닭(옛 Word 단추 셋 TE13 · 내려받기 카드 TE12 를 갈음).
//   설명은 PDF 흐름도 같은 글(옛 autofixPdf 가름 없앰). download 는 앱 Loader 그대로(감독 답 Q3).
// - [이 파트만 다시](파트 하나면 [다시 실행]): onRetry 가 있고 서버 오류·일부 쪽일 때만(결정 sid:MARC-ENT-393 — 완료·막은 파트에는 없다).
//   retrying 이면 그 단추를 끈다(보내는 동안 — 밴드 TRW1b).
import { useRef, useState } from 'react';

import {
  DownloadIcon,
  ReportWordIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  failureKindOf,
  formatRange,
  pageCountOf,
} from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
  RejectionKey,
  TabState,
} from '../../../entities/translation/model/index.ts';
import {
  PartStatusText,
  StatusBadge,
} from '../../../entities/translation/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { DownloadDialog } from '../../../shared/ui/download-dialog/index.ts';

const words = TR_TEXT.result;

export type Loader = () => Promise<{ blob: Blob; fileName: string }>;
/** 단추 차례(시안 TR-04). */
const FILE_KEYS = ['bilingual', 'review', 'autofix'] as const;
type FileKey = (typeof FILE_KEYS)[number];

export interface PartResultHeaderProps {
  part: PartKey;
  range: Range;
  state: TabState;
  reason?: RejectionKey;
  round: number;
  style: string;
  glossaryCount: number;
  started: string;
  finished?: string;
  /** 있는 파일만(없는 칸은 모달의 꺼진 줄). */
  files: Partial<Record<FileKey, Loader>>;
  onRetry?(): void;
  /** 다시 하기를 보내는 중(단추 꺼짐). */
  retrying?: boolean;
  /** 파트가 하나면 [다시 실행]. */
  single?: boolean;
}

export function PartResultHeader({
  part,
  range,
  state,
  reason,
  round,
  style,
  glossaryCount,
  started,
  finished,
  files,
  onRetry,
  retrying = false,
  single = false,
}: PartResultHeaderProps) {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const kind = failureKindOf({ state, reason });
  const canRetry =
    onRetry !== undefined && (kind === 'server_error' || kind === 'partial');
  const meta = [words.meta(style, glossaryCount, started)];
  if (finished !== undefined) meta.push(words.finished(finished));
  return (
    <div
      data-testid="part-result"
      className="flex flex-wrap items-center gap-x-3 gap-y-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="m-0 text-style-pre-body-01 text-text-primary">
          {words.title(
            TR_TEXT.parts.names[part],
            formatRange(range),
            pageCountOf(range),
          )}
        </h3>
        <PartStatusText state={state} reason={reason} />
        <StatusBadge look="grey">{TR_TEXT.cells.round(round)}</StatusBadge>
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {meta.join(' · ')}
        </span>
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        {canRetry && (
          <Button
            variant="solidBlack"
            shape="round"
            size="sm"
            disabled={retrying}
            onClick={() => onRetry?.()}
          >
            {single ? TR_TEXT.failure.retrySingle : TR_TEXT.failure.retryPart}
          </Button>
        )}
        <Button
          ref={opener}
          variant="outlineGrey"
          shape="round"
          size="sm"
          data-testid="part-downloads"
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
        >
          <DownloadIcon aria-hidden />
          {words.downloadsTitle}
        </Button>
      </div>
      {open && (
        <DownloadDialog
          testId="part-download-dialog"
          title={words.downloadsTitle}
          footnote={words.wordNote}
          closeLabel={words.close}
          helpLabel={words.fileMissingLabel}
          failedText={words.downloadFailed}
          busyLabel={words.downloading}
          files={FILE_KEYS.map((key) => {
            const load = files[key];
            return {
              key,
              name: words.files[key],
              description: words.fileNotes[key],
              fileLabel: words.files[key],
              icon: <ReportWordIcon />,
              download: load ?? NOTHING,
              ...(load === undefined ?
                { disabledReason: words.fileMissing[key] }
              : {}),
            };
          })}
          onClose={() => setOpen(false)}
          returnFocus={() => opener.current}
        />
      )}
    </div>
  );
}

/** 꺼진 줄의 download(모달이 부르지 않는다 — disabledReason). */
const NOTHING: Loader = () => Promise.reject(new Error('no file'));
