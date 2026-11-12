// S3-13 히스토리 확인(밴드 S3W3b ① — 값 파일 5절, Figma 28276:7773). 줄 하나의 사건을 쪽으로 읽는다.
//   틀 980 · 제목 text-style-pre-heading-02(e6 — S1·2 EntryHistoryDialog 와 같음) · 아래 가운데 [확인] · ✕ 없음(공용 Dialog 는 닫기 아이콘을 스스로 달지 않는다) · Esc·바깥 누름은 공용 그대로.
//   읽는 실행은 연 때 본 지금 결과(seen)이고 rowId 를 늘 싣는다 — 빼면 그 실행 사건 전부가 와 남의 줄 이력이 보인다.
//   차례는 서버 차례(새 것 먼저) 그대로. 긴 사유가 옆 칸을 덮지 않게 fixed 표. 늦은 답(쪽 넘김·닫힘)은 버린다.
//   쪽을 넘기는 동안 앞 쪽 표와 쪽 단추를 둔다 — 지우면 누른 단추가 사라져 초점이 빠진다. 그래서 늦은 답이 실제로 생긴다.
//   쪽 넘김은 앱에 공용 부품이 없어(B5) 상세 표의 s3-pager 꼴을 옮겨 적었다.
//   계수 사건 줄은 종류 글 뒤 「{AI 값} → {고른 값}」(S3W3c2 C6 — e6 덧, Scope 1·2 히스토리 꼴: 화살표·바뀐 값 강조색). 값은 상세 계수 칸과 같은 표기.
import { useEffect, useRef, useState } from 'react';

import type {
  CompanyRefusal,
  Scope3Port,
} from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { HISTORY_PAGE_SIZE } from '../../../entities/ghg-scope3/model/index.ts';
import type {
  EditHistoryLine,
  EditHistoryPage,
} from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { factorNumberText } from './detailText.ts';
import { historyAtText } from './lockAt.ts';

const words = S3_TEXT.rowEdit.history;
const detail = S3_TEXT.detail;
const EMPTY = S3_TEXT.result.empty;

const COLUMNS: DataTableColumnDef<EditHistoryLine>[] = [
  {
    id: 'at',
    header: words.at,
    enableSorting: false,
    meta: { width: 180 },
    cell: ({ row }) => historyAtText(row.original.at),
  },
  {
    id: 'by',
    header: words.by,
    enableSorting: false,
    meta: { width: 160 },
    cell: ({ row }) => row.original.by?.name || EMPTY,
  },
  {
    id: 'reason',
    header: words.reason,
    enableSorting: false,
    cell: ({ row }) => (
      <span className="block whitespace-pre-wrap break-words py-2">
        <span
          data-testid="s3-history-kind"
          className="mr-2 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.kinds[row.original.kind]}
        </span>
        {row.original.kind === 'factor' && row.original.factor !== null && (
          <span
            data-testid="s3-history-change"
            className="mr-2 text-style-pre-caption-03 text-text-tertiary tabular-nums"
          >
            {factorNumberText(row.original.factor.ai.value)}
            <span className="text-text-brand">{words.arrow}</span>
            <span className="text-text-brand">
              {factorNumberText(row.original.factor.value)}
            </span>
          </span>
        )}
        {row.original.reason}
      </span>
    ),
  },
];

type View =
  | { state: 'loading' }
  | { state: 'ok'; value: EditHistoryPage }
  | { state: 'failed' }
  | { state: 'refused'; company: CompanyRefusal };

export interface RowHistoryDialogProps {
  port: Scope3Port;
  /** 연 때 본 지금 결과 실행. */
  seen: string;
  rowId: string;
  /** 닫힐 때 초점을 줄 자리(닫힐 때 찾는다). */
  returnFocus(): HTMLElement | null;
  onClose(): void;
}

export function RowHistoryDialog({
  port,
  seen,
  rowId,
  returnFocus,
  onClose,
}: RowHistoryDialogProps) {
  const [page, setPage] = useState(1);
  const [view, setView] = useState<View>({ state: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const asked = useRef(0);
  useEffect(() => {
    const ticket = ++asked.current;
    setView((now) => (now.state === 'ok' ? now : { state: 'loading' }));
    void port
      .history(seen, { rowId, page, pageSize: HISTORY_PAGE_SIZE })
      .then((read) => {
        if (ticket !== asked.current) return;
        if (read.kind === 'ok') setView({ state: 'ok', value: read.value });
        else if (read.kind === 'refused')
          setView({ state: 'refused', company: read.company });
        else setView({ state: 'failed' });
      });
    return () => {
      asked.current += 1;
    };
  }, [port, seen, rowId, page, attempt]);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="lg"
        data-testid="s3-history"
        className="w-[980px] max-w-[calc(100vw-64px)] gap-6"
        onCloseAutoFocus={(event) => {
          const target = returnFocus();
          if (!target) return;
          event.preventDefault();
          target.focus();
        }}
      >
        <DialogTitle className="text-style-pre-heading-02">
          {words.title}
        </DialogTitle>
        {view.state === 'loading' && (
          <p
            role="status"
            data-testid="s3-history-loading"
            className="m-0 py-8 text-center text-style-pre-body-06 text-text-tertiary"
          >
            {words.loading}
          </p>
        )}
        {view.state === 'failed' && (
          <div
            data-testid="s3-history-failed"
            className="flex flex-col items-center gap-3 py-8"
          >
            <p
              role="alert"
              className="m-0 text-style-pre-body-06 text-support-error-accent"
            >
              {words.failed}
            </p>
            <Button
              variant="solidGrey"
              shape="square"
              size="sm"
              onClick={() => setAttempt((count) => count + 1)}
              data-testid="s3-history-retry"
            >
              {words.retry}
            </Button>
          </div>
        )}
        {view.state === 'refused' && (
          <p
            role="alert"
            data-testid="s3-history-refused"
            className="m-0 py-8 text-center text-style-pre-body-06 text-support-error-accent"
          >
            {S3_TEXT.company[view.company]}
          </p>
        )}
        {view.state === 'ok' && (
          <HistoryTable
            value={view.value}
            wanted={page}
            onTurn={(step) => setPage((now) => now + step)}
          />
        )}
        <DialogFooter className="pt-0">
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onClose}
            data-testid="s3-history-close"
          >
            {words.close}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function HistoryTable({
  value,
  wanted,
  onTurn,
}: {
  value: EditHistoryPage;
  /** 읽으려는 쪽(답이 오기 전엔 보이는 쪽과 다르다). */
  wanted: number;
  onTurn(step: 1 | -1): void;
}) {
  const table = useDataTable<EditHistoryLine>({
    data: value.lines,
    columns: COLUMNS,
    getRowId: (line) => line.id,
  });
  if (value.count === 0)
    return (
      <p
        data-testid="s3-history-empty"
        className="m-0 py-8 text-center text-style-pre-body-06 text-text-tertiary"
      >
        {words.empty}
      </p>
    );
  return (
    <div className="flex flex-col gap-3">
      <DataTable
        table={table}
        layout="fixed"
        aria-label={words.title}
        rowAttrs={() => ({ 'data-testid': 's3-history-row' })}
      />
      {value.totalPages > 1 && (
        <nav
          aria-label={detail.pagerLabel}
          data-testid="s3-history-pager"
          className="flex items-center justify-center gap-3"
        >
          <Button
            variant="solidGrey"
            shape="square"
            size="sm"
            disabled={wanted <= 1}
            onClick={() => onTurn(-1)}
          >
            {detail.prevPage}
          </Button>
          <span
            data-testid="s3-history-page"
            aria-live="polite"
            className="text-style-pre-body-06 text-text-secondary tabular-nums"
          >
            {detail.pageStatus(value.page, value.totalPages)}
          </span>
          <Button
            variant="solidGrey"
            shape="square"
            size="sm"
            disabled={wanted >= value.totalPages}
            onClick={() => onTurn(1)}
          >
            {detail.nextPage}
          </Button>
        </nav>
      )}
    </div>
  );
}
