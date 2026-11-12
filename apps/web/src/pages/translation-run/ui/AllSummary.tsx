// [전체] 탭(밴드 TRW0b, 시안 TR-04 확정 판 v136). 모양 부품: props 만 받는다.
// - 남은 파트 줄(「3파트 중 1파트 완료 · 2파트 진행 중」 — 있을 때, PageInfo 기본 톤) · 요약 머리와 [모두 받기] · 수치 칸 · 파트별 표(흰 카드).
// - 파트별 표: 파트·쪽 · 회차 · 시작·끝남(시각만) · 상태 · 검수 이슈 · 용어집 미반영 · 자동 수정한 쪽 · [Word](있는 줄만). 줄을 누르면 그 파트 탭(밴드 TRP2 TC22).
//   수치 없음(null)은 「–」, 0 은 「0건」.
// - A·B 견주기(compare, 밴드 TRW2 · 6c 10-26): 수 칸·표 수치는 「A / B」, 표 머리는 두 줄(윗줄 이름 · 아랫줄 작은 회색 「A / B」 — 밴드 TRW5),
//   [Word] 자리는 [Word A]·[Word B](있는 것만, 한 줄 — 내려받기 열 최소 166). 회차·시각은 꺾지 않고 파트 이름만 두 줄까지(말줄임 없음 — TRW5 · 디자인 N2).
//   표는 shared DataTable(밴드 TRP2 TC3). 줄 표시 data-part 는 파트 칸 안 단추에, data-cell 은 수 칸 안 글에 단다(DataTable 은 줄 data-* 를 받지 않는다).
// - [모두 받기](확정 판 v136 · 디자인 e9 10-23): 받을 자동 수정 병기본이 하나도 없을 때만 끈다(disabled — 안내 「받을 … 없어요」).
//   누른 뒤 묶음이 64MB 를 넘으면 archiveError='too_large' 글, 빠진 파일이 있으면 missingCount 글(서버 잇기는 TRW1).
import type { ReactNode } from 'react';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import type {
  PartKey,
  RejectionKey,
  TabState,
} from '../../../entities/translation/model/index.ts';
import {
  PartStatusText,
  StatTiles,
} from '../../../entities/translation/ui/index.ts';
import type { StatTile } from '../../../entities/translation/ui/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { DownloadButton } from '../../../shared/ui/download-button/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import type { Loader } from './PartResultHeader.tsx';

const words = TR_TEXT.all;
const cells = TR_TEXT.cells;
const none = TR_TEXT.stats.none;

export interface AllSummaryRow {
  part: PartKey;
  range: string;
  round: number;
  started: string;
  finished?: string;
  state: TabState;
  reason?: RejectionKey;
  pages?: { done: number; total: number };
  issues: Count;
  misses: Count;
  fixed: Count;
  loadWord?: Loader;
  /** A·B 견주기 — 스타일마다 그 자동 수정 병기본(없는 스타일은 키 없음). */
  loadWords?: Partial<Record<CompareStyle, Loader>>;
}

type CompareStyle = 'A' | 'B';
/** 수치 하나, 또는 A·B 견주기의 둘. */
export type Count =
  number | null | Readonly<Record<CompareStyle, number | null>>;

export interface AllSummaryProps {
  stats: readonly StatTile[];
  /** 수 칸 열 수(PDF 묶음 다섯 칸 — 밴드 TRW7 ③a). 기본 4. */
  statColumns?: 4 | 5;
  rows: readonly AllSummaryRow[];
  /** A·B 견주기 실행 — 수 칸 머리 아랫줄 「A / B」. */
  compare?: boolean;
  /** 남은 파트가 있을 때 한 줄(ui remainingLine). */
  remainingLine?: string;
  onOpenPart(part: PartKey): void;
  /** 없으면 [모두 받기]를 그리지 않는다. */
  downloadAll?: {
    /** [TRW1a ③] 409(too_large)처럼 화면이 글을 보인 끝은 {kind:'handled'}(단추 실패 글 0 — shared DownloadButton H4). */
    load: () => Promise<{ blob: Blob; fileName: string } | { kind: 'handled' }>;
    /** [TRW1a ③] 받는 동안 단추 글(시안 TR-04 「받는 중…」). */
    busyLabel?: string;
    /** 받을 자동 수정 병기본이 하나도 없음. */
    disabled: boolean;
    /** too_large = 409 ARCHIVE_TOO_LARGE · nothing = 409 NO_FINISHED_PARTS(받을 것 없음 — 끈 단추와 같은 글 noFiles, TRP1 W4). */
    archiveError?: 'too_large' | 'nothing';
    missingCount?: number;
  };
}

const value = (n: number | null, unit: (n: number) => string) =>
  n === null ? none : unit(n);

const partLabel = (row: AllSummaryRow) =>
  cells.partRange(TR_TEXT.parts.names[row.part], row.range);

const countText = (count: Count, unit: (n: number) => string) =>
  count === null || typeof count === 'number' ?
    value(count, unit)
  : <>
      <span data-style="A">{value(count.A, unit)}</span>
      <span className="text-text-tertiary">{TR_TEXT.stats.pairSeparator}</span>
      <span data-style="B">{value(count.B, unit)}</span>
    </>;

/**
 * 짧은 칸 폭 = 그 칸 max-content(머리 글 포함) + 좌우 32, 1280 에서 잰 값(밴드 TRW5 — DT1 꼴, layout="fixed").
 * 한 스타일·견주기 중 큰 값(견주기 머리는 두 줄이라 수 칸은 「12건 / 9건」이 정한다). 파트 칸만 남은 폭(두 줄까지, 말줄임 없음).
 * 내려받기는 견주기 [Word A]·[Word B] 한 줄 198(디자인 N2 의 최소 166 보다 큼), 한 스타일 [Word] 101.
 */
const WIDTH = {
  round: 68,
  time: 109,
  state: 124,
  issues: 93,
  misses: 108,
  fixed: 135,
  download: { single: 101, compare: 198 },
} as const;

const countCell = (
  id: 'issues' | 'misses' | 'fixed',
  header: ReactNode,
  unit: (n: number) => string,
): DataTableColumnDef<AllSummaryRow> => ({
  id,
  // 견주기 머리는 두 줄 요소라 그리는 함수로 넘긴다(열 정의 header 는 글이나 함수만 받는다).
  header: () => header,
  enableSorting: false,
  meta: { align: 'right', width: WIDTH[id] },
  // 견주기 「12건 / 9건」은 줄이지 않고 열이 넓어진다(nowrap — 6c 10-26).
  cell: ({ row }) => (
    <span data-cell={id} className="whitespace-nowrap tabular-nums">
      {countText(row.original[id], unit)}
    </span>
  ),
});

export function AllSummary({
  stats,
  statColumns,
  rows,
  compare = false,
  remainingLine,
  onOpenPart,
  downloadAll,
}: AllSummaryProps) {
  // 견주기 머리는 두 줄 — 아랫줄 앞 빈칸은 화면에선 줄 머리라 접히고, 칸 이름은 「검수 이슈 A / B」로 읽힌다.
  const header = (text: string) =>
    compare ?
      <>
        {text}{' '}
        <span
          data-header-sub
          className="block text-style-pre-caption-03 text-text-tertiary"
        >
          {words.pairSub}
        </span>
      </>
    : text;
  // 열 정의는 그릴 때마다 짓는다(Word 단추의 load 가 줄마다 다르다. 줄이 셋뿐이다).
  const columns: DataTableColumnDef<AllSummaryRow>[] = [
    {
      id: 'part',
      header: words.columns.part,
      enableSorting: false,
      // 글자만(400 14 #383C40 — 몸 칸 기본). 누르는 것은 줄 전체(onClickRow, 밴드 TRP2 TC22).
      cell: ({ row }) => (
        <span data-part={row.original.part}>{partLabel(row.original)}</span>
      ),
    },
    {
      id: 'round',
      header: words.columns.round,
      enableSorting: false,
      meta: { width: WIDTH.round },
      cell: ({ row }) => (
        <span className="whitespace-nowrap">
          {cells.round(row.original.round)}
        </span>
      ),
    },
    {
      id: 'time',
      header: words.columns.time,
      enableSorting: false,
      meta: { width: WIDTH.time },
      cell: ({ row }) => (
        <span className="whitespace-nowrap">
          {row.original.finished === undefined ?
            row.original.started
          : cells.time(row.original.started, row.original.finished)}
        </span>
      ),
    },
    {
      id: 'state',
      header: words.columns.state,
      enableSorting: false,
      meta: { width: WIDTH.state },
      cell: ({ row }) => (
        <PartStatusText
          state={row.original.state}
          reason={row.original.reason}
          pages={row.original.pages}
        />
      ),
    },
    countCell('issues', header(words.columns.issues), cells.count),
    countCell('misses', header(words.columns.glossaryMiss), cells.count),
    countCell('fixed', header(words.columns.fixed), cells.pages),
    {
      id: 'download',
      header: words.columns.download,
      enableSorting: false,
      meta: {
        align: 'center',
        width: compare ? WIDTH.download.compare : WIDTH.download.single,
      },
      cell: ({ row }) => {
        const { part, loadWord, loadWords } = row.original;
        if (loadWords !== undefined)
          return (
            <span
              data-testid={`words-${part}`}
              className="inline-flex flex-nowrap items-center gap-2"
            >
              {(['A', 'B'] as const).map((style) => {
                const load = loadWords[style];
                return (
                  load !== undefined && (
                    <DownloadButton
                      key={style}
                      label={words.wordOf(style)}
                      failedText={TR_TEXT.result.downloadFailed}
                      load={load}
                      testId={`word-${part}-${style}`}
                      size="sm"
                    />
                  )
                );
              })}
            </span>
          );
        return (
          loadWord !== undefined && (
            <DownloadButton
              label={words.word}
              failedText={TR_TEXT.result.downloadFailed}
              load={loadWord}
              testId={`word-${part}`}
              size="sm"
            />
          )
        );
      },
    },
  ];
  const table = useDataTable({
    data: rows as AllSummaryRow[],
    columns,
    getRowId: (row) => row.part,
  });
  return (
    <section data-testid="all-summary" className="flex flex-col gap-4">
      {remainingLine !== undefined && (
        // 흰 바탕(밴드 TRP3 ② TC23 — 시안 TR-04 c-alt 안의 e-info. 쪽 바탕 #F3F4F5 위라 기본 톤 회색은 안 보인다)
        <PageInfo
          data-testid="remaining-line"
          icon={<PageInfoIcon />}
          className="bg-background-primary"
        >
          {remainingLine}
        </PageInfo>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-2">
          <h3 className="m-0 text-style-pre-body-02 text-text-primary">
            {words.title}
          </h3>
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.lead}
          </span>
        </div>
        {downloadAll !== undefined && (
          <div className="flex flex-col items-end gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {downloadAll.disabled ? words.noFiles : words.downloadLead}
              </span>
              <DownloadButton
                label={words.downloadAll}
                failedText={TR_TEXT.result.downloadFailed}
                load={downloadAll.load}
                busyLabel={downloadAll.busyLabel}
                disabled={downloadAll.disabled}
                testId="download-all"
                variant="solidBlack"
              />
            </div>
            {/* nothing 은 끈 단추 옆 noFiles 와 같은 글 — 단추가 꺼졌으면 두 자리에 그리지 않는다(밴드 TRW1b D2). too_large 는 그대로. */}
            {downloadAll.archiveError !== undefined &&
              !(
                downloadAll.archiveError === 'nothing' && downloadAll.disabled
              ) && (
                <p
                  role="alert"
                  data-testid="archive-error"
                  className="m-0 text-style-pre-caption-03 text-support-error-accent"
                >
                  {downloadAll.archiveError === 'too_large' ?
                    words.archiveTooLarge
                  : words.noFiles}
                </p>
              )}
            {downloadAll.missingCount !== undefined &&
              downloadAll.missingCount > 0 && (
                <p
                  data-testid="archive-missing"
                  className="m-0 text-style-pre-caption-03 text-support-orange-dark"
                >
                  {words.archiveMissing(downloadAll.missingCount)}
                </p>
              )}
          </div>
        )}
      </div>
      <StatTiles
        items={stats}
        {...(statColumns === undefined ? {} : { columns: statColumns })}
      />
      <Card className="flex flex-col gap-4">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.tableTitle}
        </h3>
        <DataTable
          table={table}
          layout="fixed"
          aria-label={words.tableTitle}
          onClickRow={(row) => onOpenPart(row.part)}
          rowLabel={(row) => words.rowLabel(partLabel(row))}
        />
      </Card>
    </section>
  );
}
