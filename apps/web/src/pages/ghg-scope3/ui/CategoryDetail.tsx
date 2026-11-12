// S3-09 카테고리 상세 · S3-10 생물기원(밴드 S3W2b ② — 판 「그대로」, Figma 가 정본이나 이 세션은 Figma 를 못 읽어 간격은 S3-08 카드와 shared 표 기본).
// 카드에서 연다(ResultView 의 화면 상태 — 주소 칸 0, Q4). 위 [목록] 은 카드 목록으로 돌아가고 초점은 연 카드로(ResultView 가 옮긴다).
//   - 머리 카드: 카테고리 합(일부 실패면 둘째 줄 「일부 시트 계산 실패」, 다 실패면 「계산 실패」) · C5·C12 는 생물기원 칸 + 띠(S3-10).
//     띠는 [Figma] 글(총·생물기원 합 둘 — S3W2c ② Q9, brand 바탕 tone important), 합 숫자는 display-04(S3W2c ② — 토큰 정의에 없는 글꼴 이름을 갈음).
//   - 시트마다 머리(서버 sheet 글자 그대로 — Q10) + processed 표 / failed·empty 까닭 글(서버 error 0). 시트 차례는 서버 차례.
//   - 표: shared data-table(정렬은 수동 — 검색·정렬 뒤에 쪽을 나눈다, Q6). 열은 model 의 SHEET_COLUMNS(결과 꼴에 있는 열만, sid:MARC-ENT-538).
//   - 검색 칸: [Figma] 자리글 「검색」 · 폭 최소 300(S3W2c ② Q10) · 표 위 줄 왼쪽(S3W3b). 검색 하나가 그 상세의 글자 칸 있는 표를 거른다(글자 칸 없는 표는 검색이 닿지 않는다 — 감독 처분 R5). 검색어가 바뀌면 표마다 첫 쪽으로.
//     글자 칸 있는 표가 하나도 없으면 검색 칸을 두지 않는다.
//   - 열면 초점은 [목록] 단추로(감독 처분 R6 — 닫으면 ResultView 가 누른 카드로 돌려준다).
//   - 표 앞뒤 체크·히스토리 열 · 표 위 줄(검색 + [산정 제외]·[산정으로 복구]) · 제외 줄 앞 글(밴드 S3W3b). 거름은 뒤 밴드(e6 처분).
//     [원본 다운로드](밴드 S3Q1 ①): 그 카테고리 지금 실행(card.state.current.runId)에 올린 파일 통째 — 단추 무리 맨 앞, 잠겨도 켬. 실행이 있으면
//     표 위 줄을 늘 그린다(시트가 다 실패해도 — 검색·제외·복구는 지금 조건 그대로). 실패 글은 표 위 줄 아래 한 줄(role=alert).
//     고름은 이 상세 하나에 둔다(요청은 카테고리 하나 — 시트가 달라도 된다). 칸은 컨텍스트로 읽는다(RowEditParts). 검색어가 바뀌면 고름을 푼다(B7).
//   - 여는 칸(model openingColumn — 시트마다 줄을 부르는 이름 칸 하나, 값 파일 ② · sid:MARC-ENT-585)의 글은 링크 꼴 단추로 그룹별 배출계수 창을 연다. 글이 없거나 basic 줄이면 단추 없이 글 그대로(C12 만 빈 글도 회색 「이름 없음」 단추 — S3Q2).
//     C15 는 창이 없고 표 위 오른쪽에 한 줄(잠겨도 남는다 — 단추가 없어 툴팁 자리가 없다). 고친 줄은 꼴 없이 값만 바뀌고 「추정」 뱃지를 뗀다(S3W3c1).
//     열은 표마다 한 번만 짓는다(useMemo): 새로 지으면 칸이 다시 달려 누른 단추가 사라지고 닫을 때 초점이 돌아올 자리가 없다.
//   - 창 상태·계수 수정은 이 상세의 useFactorEdit 가 쥔다(S3W3c2). 칸은 FactorOpenContext 로 open 을 부른다 — 고름·창 상태는 columns 의존에 넣지 않는다.
//     성공 뒤 합이 바뀌면 칸이 다시 달려 단추가 사라지므로 초점은 [목록]으로(C4).
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';

import { ChevronLeftIcon } from '@marcspon/common/generated/icons/MyIcons';

import type { Scope3Port } from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  PAGE_SIZE,
  SHEET_COLUMNS,
  SORT_COLUMNS,
  categorySheets,
  cellOf,
  filterRows,
  leadColumn,
  opensFactorWindow,
  pageOf,
  rowIdsOf,
  rowNumber,
  searchable,
  sortRows,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  CellValue,
  ColumnId,
  CurrentCard,
  DetailSheet,
  ResultRow,
  RowSort,
  Scope3Done,
  SheetLayout,
} from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { AdjustLaterMark } from './AdjustLater.tsx';
import {
  EditButtons,
  HeadCheck,
  HistoryButton,
  OriginalButton,
  PageIdsContext,
  RowCheck,
  RowPickContext,
  useOriginalDownload,
} from './RowEditParts.tsx';
import type { SaveFile } from './RowEditParts.tsx';
import type { RowPick } from './RowEditParts.tsx';
import { RowHistoryDialog } from './RowHistoryDialog.tsx';
import { SourceText } from './SourceText.tsx';
import { cardState } from './cardState.ts';
import { cellText, headerOf, isNumberColumn } from './detailText.ts';
import { EMISSION_UNIT, emissionText } from './emission.ts';
import { lockAtText } from './lockAt.ts';
import { useCategoryLock } from './useCategoryLock.tsx';
import { useFactorEdit } from './useFactorEdit.tsx';
import { useRowEdit } from './useRowEdit.tsx';

const words = S3_TEXT.detail;
const result = S3_TEXT.result;
const editWords = S3_TEXT.rowEdit;

/** 칸 단추가 창을 여는 손잡이(상세 하나 — 줄 사진과 누른 단추). */
const FactorOpenContext = createContext<
  (row: ResultRow, button: HTMLElement) => void
>(() => {});

/** 제외 줄 앞 글. 칸 값이 비면 「산정 제외」만(e6 덧 B3 — 「-」 글자가 아니라 값으로 가른다, 빈 글자도 빈 값). */
const leadText = (cell: CellValue, text: string) =>
  cell.type === 'text' && !cell.text ?
    editWords.excludedLead
  : `${editWords.excludedLead}${editWords.excludedSeparator}${text}`;

export interface CategoryDetailProps {
  port: Scope3Port;
  year: number;
  operator: boolean;
  /** 그 카테고리 지금 결과 실행의 덧씌운 결과. */
  done: Scope3Done;
  card: CurrentCard;
  /** 쓰기 답 뒤 지금 결과를 다시 읽는다. */
  reread(): Promise<void>;
  /** [목록] — 카드 목록으로. */
  onBack(): void;
  /** 파일 저장(시험이 바꿔 끼운다 — 기본 saveBlob). */
  save?: SaveFile;
}

export function CategoryDetail({
  port,
  year,
  operator,
  done,
  card,
  reread,
  onBack,
  save,
}: CategoryDetailProps) {
  const [query, setQuery] = useState('');
  const backRef = useRef<HTMLButtonElement>(null);
  const lock = useCategoryLock({
    port,
    year,
    card,
    operator,
    reread,
    afterLock: () => backRef.current?.focus(),
  });
  useEffect(() => {
    backRef.current?.focus();
  }, []);
  const sheets = categorySheets(done, card.id);
  const processed = sheets.filter(
    (sheet): sheet is ProcessedSheet => sheet.status === 'processed',
  );
  const canSearch = processed.some((sheet) => searchable(sheet.layout));
  const held = card.state;
  const runId = held?.current?.runId ?? null;
  const locked = held?.locked ?? false;
  const original = useOriginalDownload({ port, runId, save });
  const edit = useRowEdit({
    port,
    category: card.id,
    runId,
    locked,
    rows: processed.flatMap((sheet) => sheet.rows),
    reread,
    fallback: () => backRef.current,
  });
  const factor = useFactorEdit({
    port,
    category: card.id,
    runId,
    locked,
    reread,
    fallback: () => backRef.current,
  });
  // 알림 줄은 마지막 하나(GX1 S3-09 — 줄 고침과 계수 고침의 알림이 쌓였다). 어느 쪽이 나중에 바뀌었는지 그림 중에 적는다.
  const [notices, setNotices] = useState({
    edit: edit.notice,
    factor: factor.notice,
    latest: null as 'edit' | 'factor' | null,
  });
  let latest = notices.latest;
  if (notices.edit !== edit.notice || notices.factor !== factor.notice) {
    if (edit.notice !== notices.edit && edit.notice !== null) latest = 'edit';
    else if (factor.notice !== notices.factor && factor.notice !== null)
      latest = 'factor';
    setNotices({ edit: edit.notice, factor: factor.notice, latest });
  }
  const showEdit =
    edit.notice !== null && (factor.notice === null || latest !== 'factor');
  const showFactor = factor.notice !== null && !showEdit;
  /** 연 때 본 실행을 쥔다. button 은 닫을 때 초점 자리. */
  const [history, setHistory] = useState<{
    seen: string;
    rowId: string;
    button: HTMLElement;
  } | null>(null);
  const pick: RowPick = {
    chosen: edit.chosen,
    blocked: edit.blocked,
    canHistory: runId !== null,
    choose: edit.choose,
    openHistory: (rowId, button) => {
      if (runId !== null) setHistory({ seen: runId, rowId, button });
    },
  };
  return (
    <section
      data-testid="s3-detail"
      data-category={card.id}
      aria-label={`${result.cardTitle(card.number)} ${result.cards[card.id]}`}
      className="flex flex-col gap-4"
    >
      <div className="flex items-center justify-between gap-2">
        <Button
          ref={backRef}
          variant="solidGrey"
          shape="square"
          size="sm"
          onClick={onBack}
          data-testid="s3-detail-back"
        >
          <ChevronLeftIcon aria-hidden className="size-4" />
          {words.back}
        </Button>
      </div>
      <DetailHead card={card} lock={lock.control} />
      {lock.problem !== null && (
        <p
          role="alert"
          data-testid="s3-lock-problem"
          className="m-0 text-style-pre-caption-03 text-support-error-accent"
        >
          {lock.problem}
        </p>
      )}
      {lock.windows}
      {card.hasBiogenic && (
        // S3R3 Q7(e6 506 ②): 이 띠만 글자색 brand — 공용 important(orange-dark)는 그대로, cn 이 뒤 글자색을 이기게 한다.
        <PageInfo
          tone="important"
          icon={<PageInfoIcon />}
          className="text-text-brand"
          data-testid="s3-biogenic-notice"
        >
          {words.biogenicNotice(withUnit(card.total), withUnit(card.biogenic))}
        </PageInfo>
      )}
      {(processed.length > 0 || runId !== null) && (
        <div
          data-testid="s3-detail-tools"
          className="flex flex-wrap items-center gap-2"
        >
          {canSearch && (
            <SearchField
              className="min-w-[300px]"
              aria-label={words.searchLabel}
              placeholder={words.searchPlaceholder}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                edit.clearChosen();
              }}
              data-testid="s3-detail-search"
            />
          )}
          <div className="ml-auto flex items-center gap-2">
            {runId !== null && (
              <OriginalButton
                busy={original.busy}
                onTake={() => void original.take()}
              />
            )}
            {processed.length > 0 && (
              <EditButtons
                locked={locked}
                blocked={edit.blocked}
                excludeCount={edit.excludeCount}
                restoreCount={edit.restoreCount}
                onAsk={edit.ask}
              />
            )}
          </div>
        </div>
      )}
      {original.problem !== null && (
        <p
          role="alert"
          data-testid="s3-original-problem"
          className="m-0 text-style-pre-caption-03 text-support-error-accent"
        >
          {original.problem}
        </p>
      )}
      {showEdit && edit.notice !== null && (
        <p
          role={edit.notice.tone}
          data-testid="s3-edit-notice"
          className={`m-0 text-style-pre-caption-03 ${
            edit.notice.tone === 'alert' ?
              'text-support-error-accent'
            : 'text-text-secondary'
          }`}
        >
          {edit.notice.text}
        </p>
      )}
      {showFactor && factor.notice !== null && (
        <p
          role={factor.notice.tone}
          data-testid="s3-factor-notice"
          className={`m-0 text-style-pre-caption-03 ${
            factor.notice.tone === 'alert' ?
              'text-support-error-accent'
            : 'text-text-secondary'
          }`}
        >
          {factor.notice.text}
        </p>
      )}
      {sheets.length === 0 ?
        <p
          data-testid="s3-detail-none"
          className="m-0 text-style-pre-body-06 text-text-tertiary"
        >
          {words.noSheets}
        </p>
      : <RowPickContext.Provider value={pick}>
          <FactorOpenContext.Provider value={factor.open}>
            {sheets.map((sheet, index) => (
              <SheetBlock
                // 서버 차례 그대로 — 같은 이름 시트가 둘이어도 자리가 다르다.
                key={`${index}:${sheet.sheet}`}
                sheet={sheet}
                query={query}
              />
            ))}
          </FactorOpenContext.Provider>
        </RowPickContext.Provider>
      }
      {edit.dialog}
      {factor.dialog}
      {history !== null && (
        <RowHistoryDialog
          port={port}
          seen={history.seen}
          rowId={history.rowId}
          returnFocus={() =>
            history.button.isConnected ? history.button : backRef.current
          }
          onClose={() => setHistory(null)}
        />
      )}
    </section>
  );
}

/** 띠 글의 수 자리: 값 + 단위(EMISSION_UNIT — ENT-264), 값이 없으면 「-」(단위 없이). */
const withUnit = (value: number | null) =>
  value === null ?
    result.empty
  : `${emissionText(value, result.empty)} ${EMISSION_UNIT}`;

/** 상세 위 카드(합·일부 실패·생물기원 칸). */
function DetailHead({ card, lock }: { card: CurrentCard; lock: ReactNode }) {
  const state = cardState(card);
  const held = card.state;
  return (
    <div
      data-testid="s3-detail-card"
      data-state={state.kind}
      data-partial={state.partial ? 'true' : undefined}
      className="flex flex-wrap items-stretch gap-4 rounded-component border border-border-tertiary px-6 py-6"
    >
      <div className="flex min-w-60 flex-1 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {result.cardTitle(card.number)}
          </h3>
          {lock}
          {held?.locked && held.lockedAt !== null && (
            <span
              data-testid="s3-locked-info"
              className="text-style-pre-caption-02 text-text-tertiary"
            >
              {S3_TEXT.lock.lockedInfo(
                held.lockedBy?.name || result.empty,
                lockAtText(held.lockedAt),
              )}
            </span>
          )}
        </div>
        <p className="m-0 text-style-pre-body-06 text-text-secondary">
          {result.cards[card.id]}
          {/* 밴드 S3N1: 카드와 같은 이름 옆 고정 안내(상세는 꺼진 카드로 열리지 않는다). */}
          <AdjustLaterMark category={card.id} />
        </p>
      </div>
      <dl className="m-0 flex flex-wrap gap-8">
        <div className="flex flex-col gap-0.5">
          <dt className="text-style-pre-caption-03 text-text-tertiary">
            {result.totalLabel}
          </dt>
          <dd data-testid="s3-detail-total" className="m-0">
            {state.kind === 'failed' ?
              <span className="text-style-pre-body-04 text-support-error-accent">
                {result.cardFailed}
              </span>
            : <>
                <span className="text-style-pre-display-04 text-text-brand">
                  {emissionText(card.total, result.empty)}
                </span>
                {card.total !== null && (
                  <span className="ml-1 text-style-pre-caption-03 text-text-secondary">
                    {EMISSION_UNIT}
                  </span>
                )}
              </>
            }
          </dd>
          {state.partial && (
            <dd
              data-testid="s3-detail-partial"
              className="m-0 text-style-pre-caption-03 text-support-error-accent"
            >
              {result.cardPartial(card.failedSheets)}
            </dd>
          )}
        </div>
        {card.hasBiogenic && (
          <div className="flex flex-col gap-0.5">
            <dt className="text-style-pre-caption-03 text-text-tertiary">
              {result.biogenicLabel}
            </dt>
            <dd data-testid="s3-detail-biogenic" className="m-0">
              <span className="text-style-pre-display-04 text-text-secondary">
                {emissionText(card.biogenic, result.empty)}
              </span>
              {card.biogenic !== null && (
                <span className="ml-1 text-style-pre-caption-03 text-text-secondary">
                  {EMISSION_UNIT}
                </span>
              )}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

/** 시트 하나 — 머리 + 표 또는 까닭 글. */
function SheetBlock({ sheet, query }: { sheet: DetailSheet; query: string }) {
  return (
    <section
      data-testid="s3-sheet"
      data-sheet={sheet.sheet}
      data-status={sheet.status}
      data-layout={sheet.status === 'processed' ? sheet.layout : undefined}
      className="flex flex-col gap-2"
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="m-0 text-style-pre-body-04 text-text-primary">
          {sheet.sheet}
        </h4>
        {sheet.status === 'processed' && sheet.layout === 'C15' && (
          <p
            data-testid="s3-sheet-no-factor-edit"
            className="m-0 text-style-pre-caption-02 text-text-tertiary"
          >
            {words.noFactorEdit}
          </p>
        )}
      </div>
      {sheet.status === 'processed' ?
        <SheetTable sheet={sheet} query={query} />
      : <PageInfo
          tone={sheet.status === 'failed' ? 'error' : 'default'}
          icon={<PageInfoIcon />}
          data-testid="s3-sheet-reason"
        >
          {sheet.status === 'failed' ? words.sheetFailed : words.sheetEmpty}
        </PageInfo>
      }
    </section>
  );
}

type ProcessedSheet = Extract<DetailSheet, { status: 'processed' }>;

/** 접는 칸. 그 밖은 한 줄(whitespace-nowrap) — 그룹명·품목명도 한 줄, 넘치면 표 안 가로 밀기(GX4 ①, 말줄임 꼴은 없어 새로 만들지 않음). */
const WRAP_COLUMNS: readonly ColumnId[] = [
  'inEnergy',
  'inVehicle',
  'treatment',
];

function SheetTable({
  sheet,
  query,
}: {
  sheet: ProcessedSheet;
  query: string;
}) {
  const [sort, setSort] = useState<RowSort | null>(null);
  const [paging, setPaging] = useState({ query, page: 1 });
  // 글자 칸이 없는 표에는 검색이 닿지 않는다(R5 — 「결과 없음」으로 비우지 않음).
  const word = searchable(sheet.layout) ? query : '';
  // 검색어가 바뀌면 쪽 번호를 그 검색어의 1 쪽으로 덮는다(지웠을 때 옛 쪽으로 돌아가지 않게 — 가지 리뷰 L1). 그림 중 상태 맞춤.
  if (paging.query !== word) setPaging({ query: word, page: 1 });
  const wanted = paging.query === word ? paging.page : 1;
  const found = filterRows(sheet.rows, sheet.layout, word, cellText);
  const sorted = sortRows(found, sort, sheet.total);
  const page = pageOf(sorted, wanted);
  const columns = useMemo(
    (): DataTableColumnDef<ResultRow>[] => [
      {
        id: 'pick',
        header: () => <HeadCheck />,
        enableSorting: false,
        meta: { width: 52 },
        cell: ({ row }) => <RowCheck row={row.original} />,
      },
      ...SHEET_COLUMNS[sheet.layout].map(
        (column): DataTableColumnDef<ResultRow> => ({
          id: column,
          header: headerOf(sheet.layout, column),
          // 정렬은 수동(manualSorting — 쪽 앞에서 model 의 sortRows). 값 읽기는 TanStack 이 정렬할 수 있는 열로 알게 하는 데만 쓴다.
          accessorFn: (row) => {
            const cell = cellOf(row, column, sheet.total);
            return cell.type === 'number' ? cell.value : cell.text;
          },
          enableSorting: SORT_COLUMNS.includes(column),
          meta: { align: isNumberColumn(column) ? 'right' : 'left' },
          cell: ({ row }) => {
            const cell = (
              <Cell
                row={row.original}
                column={column}
                layout={sheet.layout}
                total={sheet.total}
              />
            );
            // 접는 칸 밖은 이름 칸까지 한 줄. 짧은 글·수·계수 칸은 한 줄로 두고, 넘치면 표 틀(DataTable 의 overflow-x-auto) 안에서 가로로 민다(GX1 S3-09).
            return WRAP_COLUMNS.includes(column) ? cell : (
                <span className="whitespace-nowrap">{cell}</span>
              );
          },
        }),
      ),
      {
        id: 'history',
        header: editWords.history.column,
        enableSorting: false,
        meta: { width: 140 },
        cell: ({ row }) => <HistoryButton row={row.original} />,
      },
    ],
    [sheet.layout, sheet.total],
  );
  const table = useDataTable<ResultRow>({
    data: page.rows,
    columns,
    getRowId: (_row, index) => `${(page.page - 1) * PAGE_SIZE + index}`,
    manualSorting: true,
    state: {
      sorting:
        sort === null ?
          []
        : [{ id: sort.column, desc: sort.direction === 'desc' }],
    },
    onSortingChange: (updater) => {
      const now =
        sort === null ?
          []
        : [{ id: sort.column, desc: sort.direction === 'desc' }];
      const next = typeof updater === 'function' ? updater(now) : updater;
      const first = next[0];
      setSort(
        first ?
          {
            column: first.id as ColumnId,
            direction: first.desc ? 'desc' : 'asc',
          }
        : null,
      );
      setPaging({ query: word, page: 1 });
    },
  });
  return (
    <div className="flex flex-col gap-2">
      <PageIdsContext.Provider value={rowIdsOf(page.rows)}>
        <DataTable
          table={table}
          aria-label={words.tableLabel(sheet.sheet)}
          rowAttrs={(row) => ({
            'data-testid': 's3-row',
            'data-origin': row.origin ?? undefined,
            // 제외 꼴은 칸(Cell). 고친 줄은 꼴 없이 값만 바뀐다(S3W3c C5) — 속성까지.
            'data-excluded': row.excluded ? 'true' : undefined,
            'data-edited': row.edited ? 'true' : undefined,
          })}
          empty={
            <p className="m-0 py-4 text-center text-style-pre-body-06 text-text-tertiary">
              {words.noMatch}
            </p>
          }
        />
      </PageIdsContext.Provider>
      {page.pageCount > 1 && (
        <nav
          aria-label={words.pagerLabel}
          data-testid="s3-pager"
          className="flex items-center justify-center gap-3"
        >
          <Button
            variant="solidGrey"
            shape="square"
            size="sm"
            disabled={page.page <= 1}
            onClick={() => setPaging({ query: word, page: page.page - 1 })}
          >
            {words.prevPage}
          </Button>
          <span
            data-testid="s3-page"
            aria-live="polite"
            className="text-style-pre-body-06 text-text-secondary tabular-nums"
          >
            {words.pageStatus(page.page, page.pageCount)}
          </span>
          <Button
            variant="solidGrey"
            shape="square"
            size="sm"
            disabled={page.page >= page.pageCount}
            onClick={() => setPaging({ query: word, page: page.page + 1 })}
          >
            {words.nextPage}
          </Button>
        </nav>
      )}
    </div>
  );
}

function Cell({
  row,
  column,
  layout,
  total,
}: {
  row: ResultRow;
  column: ColumnId;
  layout: SheetLayout;
  total: number | null;
}) {
  const onOpen = useContext(FactorOpenContext);
  const cell = cellOf(row, column, total);
  const text = cellText(cell, column);
  // 앞 글은 그리기만 한다 — 검색·정렬·셈은 서버 줄 값(cellOf)을 본다.
  const lead = row.excluded && column === leadColumn(layout);
  if (column === 'co2e' && row.origin === 'estimate' && !row.edited)
    return (
      <span className="inline-flex items-baseline gap-1">
        <span className="tabular-nums">{text}</span>
        <span
          data-testid="s3-estimate"
          className="rounded-control bg-background-secondary px-1 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.estimate}
        </span>
      </span>
    );
  if (column === 'source' && cell.type === 'text')
    return <SourceText source={cell} />;
  if (opensFactorWindow(row, layout, column)) {
    // 글이 빈 여는 칸(C12 제품명 빈 줄 — model opensFactorWindow)은 회색 「이름 없음」 · aria 는 줄 번호(S3Q2 · c3 11-11).
    const noName = cell.type === 'text' && !cell.text;
    const opener = (
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={
          noName ? words.factorWindow.openAria(rowNumber(row.rowId)) : undefined
        }
        data-testid="s3-window-open"
        onClick={(event) => onOpen(row, event.currentTarget)}
        className={`cursor-pointer border-0 bg-transparent p-0 text-left ${noName ? 'text-text-tertiary' : 'text-text-secondary'} [font:inherit] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary`}
      >
        {noName ? words.factorWindow.noName : text}
      </button>
    );
    // 앞 글은 단추 밖 — 이름만 링크.
    return lead ?
        <>
          {editWords.excludedLead}
          {editWords.excludedSeparator}
          {opener}
        </>
      : opener;
  }
  const shown = lead ? leadText(cell, text) : text;
  return isNumberColumn(column) ?
      <span className="tabular-nums">{shown}</span>
    : shown;
}
