// PDF 보기 상세 「번역 복사」 아이콘 단추(밴드 TRW14 ③ — TR-P05 c3 스펙). 모양 부품: 클립보드를 모른다(copy 를 props 로 — app 층이 넣는다).
//   - 꼴: 같은 상세 머리 줄 ‹ › 와 같은 IconButton md(아이콘 20, 글 없음) · CopySimpleIcon · 툴팁 「번역 복사」(공용 Tooltip).
//   - 누르면 copy(text) → 단추 바로 왼쪽에 role=status 짧은 글(caption 12 · tertiary) 「번역을 복사했어요」/ 실패 「복사하지 못했어요」, 약 2초 뒤 사라짐.
//     글 자리는 늘 잡아 둔다(보이지 않는 긴 글로 폭 고정) — 머리 줄이 흔들리지 않고 전환 단추를 덮지 않는다(감독 답 Q1 — c3). 체크 아이콘으로 바꾸지 않는다.
//   - 공용 토스트는 없다(후속 — 감독이 이슈로 올림).
import { useEffect, useRef, useState } from 'react';

import { CopySimpleIcon } from '@marcspon/common/generated/icons/MyIcons';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';

import { TR_TEXT } from '../../../../entities/translation/config/text.ts';
import { IconButton } from '../../../../shared/ui/button/index.ts';

const words = TR_TEXT.pdfView.pair.copy;
/** 누른 뒤 글이 머무는 시간(ms). */
export const COPY_NOTE_MS = 2000;

export type CopyText = (text: string) => Promise<void>;

export function PairCopy({
  text,
  copy,
  label = words.label,
  testId = 'pdf-pair-copy',
}: {
  /** 복사할 글(pdfCopy copyTextOf). */
  text: string;
  copy: CopyText;
  /** 단추 이름(「둘 다」면 「번역 A 복사」 — 감독 Q9). 툴팁은 늘 「번역 복사」. */
  label?: string;
  testId?: string;
}) {
  const [note, setNote] = useState<'done' | 'failed' | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );
  const show = (next: 'done' | 'failed') => {
    if (timer.current !== null) clearTimeout(timer.current);
    setNote(next);
    timer.current = setTimeout(() => {
      timer.current = null;
      setNote(null);
    }, COPY_NOTE_MS);
  };
  const press = () => {
    copy(text).then(
      () => show('done'),
      () => show('failed'),
    );
  };
  return (
    <span className="inline-flex shrink-0 items-center gap-1">
      {/* 글 자리를 늘 잡아 둔다(긴 글 둘을 보이지 않게 겹쳐 폭을 정함) — 글이 뜨고 져도 머리 줄이 흔들리지 않고 전환 단추를 덮지 않는다. */}
      <span className="inline-grid text-right text-style-pre-caption-03 text-text-tertiary">
        <span
          aria-hidden
          className="invisible whitespace-nowrap [grid-area:1/1]"
        >
          {words.done}
        </span>
        <span
          aria-hidden
          className="invisible whitespace-nowrap [grid-area:1/1]"
        >
          {words.failed}
        </span>
        <span
          role="status"
          data-testid={`${testId}-note`}
          data-note={note ?? undefined}
          className="whitespace-nowrap [grid-area:1/1]"
        >
          {note === null ? '' : words[note]}
        </span>
      </span>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <IconButton
              size="md"
              data-testid={testId}
              aria-label={label}
              onClick={press}
            >
              <CopySimpleIcon aria-hidden />
            </IconButton>
          </TooltipTrigger>
          <TooltipContent>{words.label}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </span>
  );
}
