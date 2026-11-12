// 번역 목록 화면(밴드 TRW1a ③, 시안 TR-01·01a 확정 판 v136, 결정 sid:MARC-ENT-404 — 한 줄 = [번역 시작] 한 번 = 묶음). 라우터를 모른다.
// - 머리 「번역 목록」 + 설명 줄은 운영 관리자의 「작업 회사 {company}」만(회사는 서버 목록 응답 companyName, 밴드 TRC1 · sid:MARC-ISSUE-360 —
//   일반 사용자 줄은 지움, 회사가 비면 줄 없음: 밴드 WT1 · sid:MARC-ENT-625, 그린워싱 GW-01 꼴).
// - 상태 탭(키트 Tabs box: 전체·대기·진행 중·완료·실패 → state 없음·active·done·failed) · 「내가 올린 것만」(고객사만 → mine=true) · [새 번역].
// - 표는 BatchTable(adapt 의 batchViewOf). 빈 꼴 둘·불러오기 실패([다시 시도])·불러오는 중.
// - [이 파트만 다시](밴드 TRW1b, 결정 sid:MARC-ENT-393 — 서버 오류·일부 쪽 파트 줄에만, BatchTable 규칙): 받은 쪽에서 그 파트의 최신 runId 로
//   store.retryPart 한 번(보내는 동안 다시 누름은 버림) → 됨: onOpenPart(그 파트 탭, 감독 판단 a) · 안 됨: 표 위 오류 한 줄 retryFailed.
// - 검색 칸(밴드 TRP2 TE2): 서버에 검색 인자가 없어 받은 첫 20줄 안에서 파일명으로 거른다(meta 의 수는 서버 count 그대로).
// - 표 아래 안내 상자(TE4, 표가 있을 때만). 쪽 넘김·「더 있음」은 없다(감독 판단 6 — 첫 쪽 20줄만).
// - 머리 오른쪽 「번역 안내」 링크(밴드 TRP3, sid:MARC-ENT-435 — GW-01 꼴). onIntro 를 받을 때만, 목록 상태와 상관없이 늘 보인다.
// - 불러오는 중(밴드 TRP5, sid:MARC-ENT-443 ①②③): 카드 LoadSkeleton 대신 BatchTable loading(머리줄 + 스켈레톤 줄), 빈 꼴은 받은 뒤에만,
//   운영 관리자 설명 줄 자리는 운영 관리자 && 불러오는 중에만 descriptionPending.
// - [PDF로 새 번역](밴드 TRW6 ②, 6c v174 TR-01): onNewPdf 를 받을 때만 — 머리 [새 번역] 왼쪽(outline-grey + 더하기)과 빈 꼴 [새 번역] 옆.
import { useId, useRef, useState } from 'react';

import { PlusIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Label } from '@marcspon/ui/components/label';

import type { TranslationStore } from '../../../entities/translation/api/index.ts';
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { useBatches } from '../../../entities/translation/hooks/index.ts';
import {
  batchViewOf,
  splitBatchRowId,
} from '../../../entities/translation/model/index.ts';
import type {
  BatchState,
  BatchView,
  PartKey,
} from '../../../entities/translation/model/index.ts';
import { BatchTable } from '../../../entities/translation/ui/index.ts';
import type { BatchRow } from '../../../entities/translation/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import { filterByFileName } from '../model/index.ts';

const words = TR_TEXT.list;

const TABS = ['all', 'active', 'done', 'failed'] as const;
type Tab = (typeof TABS)[number];

export interface ListScreenProps {
  store: TranslationStore;
  /** 운영 관리자인가(「내가 올린 것만」 숨김·meta). */
  operator: boolean;
  onNewTranslation(): void;
  /** [PDF로 새 번역](TR-P02). 없으면 단추를 그리지 않는다. */
  onNewPdf?(): void;
  /** 「번역 안내」(TR-00). 없으면 링크를 그리지 않는다. */
  onIntro?(): void;
  onOpenBatch(documentId: string, batchKey: string): void;
  onOpenPart(documentId: string, batchKey: string, part: PartKey): void;
}

/** 화면 꼴 → 표 줄(스타일 열쇠·없음 글을 글자로). pdf = 묶음 inputKind 가 pdf(밴드 TRW6 ④ — 워드 줄은 칸 0). */
export function rowOf(view: BatchView, pdf = false): BatchRow {
  return {
    ...(pdf ? { pdf: true } : {}),
    batchId: view.rowId,
    fileName: view.fileName,
    uploaded: view.uploaded ?? TR_TEXT.stats.none,
    style: view.style === null ? TR_TEXT.stats.none : words.styles[view.style],
    uploader: view.uploader,
    lastStarted: view.lastStarted,
    parts: view.parts.map((part) => ({
      part: part.part,
      range: part.rangeText ?? TR_TEXT.stats.none,
      round: part.round,
      started: part.started,
      state: part.state,
      ...(part.reason === undefined ? {} : { reason: part.reason }),
      ...(part.pages === undefined ? {} : { pages: part.pages }),
      earlier: part.earlier,
    })),
    // batchId 없는 옛 실행의 묶음(`run-` 열쇠)은 다시 단추 0(감독 판단 c).
    retryable: !view.batchKey.startsWith('run-'),
  };
}

export function ListScreen({
  store,
  operator,
  onNewTranslation,
  onNewPdf,
  onIntro,
  onOpenBatch,
  onOpenPart,
}: ListScreenProps) {
  /** [PDF로 새 번역] 단추 하나(머리·빈 꼴이 같이 쓴다 — 빈 꼴에서 빼려면 그 자리 한 줄만). */
  const pdfButton = (testId: string) =>
    onNewPdf !== undefined && (
      <Button
        variant="outlineGrey"
        shape="round"
        size="md"
        data-testid={testId}
        onClick={onNewPdf}
      >
        <PlusIcon aria-hidden />
        {words.newPdf}
      </Button>
    );
  const mineId = useId();
  const [tab, setTab] = useState<Tab>('all');
  const [mine, setMine] = useState(false);
  const [query, setQuery] = useState('');
  const [retryFailed, setRetryFailed] = useState(false);
  const sending = useRef(false);
  const showMine = !operator;
  const state: BatchState | undefined = tab === 'all' ? undefined : tab;
  const { status, retry } = useBatches(store, {
    ...(state === undefined ? {} : { state }),
    mine: showMine && mine,
    offset: 0,
  });
  const filtered = tab !== 'all' || (showMine && mine) || query.trim() !== '';
  const batches = status.state === 'ready' ? status.page.results : [];
  const views = batches.map(batchViewOf);
  const rows = filterByFileName(
    views.map((view, i) => rowOf(view, batches[i]?.inputKind === 'pdf')),
    query,
  );
  const open = (
    rowId: string,
    then: (documentId: string, key: string) => void,
  ) => {
    const ids = splitBatchRowId(rowId);
    if (ids) then(ids.documentId, ids.batchKey);
  };

  const retryPart = (rowId: string, part: PartKey) => {
    const view = views.find((v) => v.rowId === rowId);
    const runId = view?.parts.find((p) => p.part === part)?.runId;
    if (view === undefined || runId === undefined || sending.current) return;
    sending.current = true;
    setRetryFailed(false);
    store
      .retryPart({
        documentId: view.documentId,
        batchKey: view.batchKey,
        part,
        runId,
      })
      .then(
        () => {
          sending.current = false;
          onOpenPart(view.documentId, view.batchKey, part);
        },
        () => {
          sending.current = false;
          setRetryFailed(true);
        },
      );
  };

  return (
    <div data-screen="translation-list" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        description={
          (
            operator &&
            status.state === 'ready' &&
            status.page.companyName !== ''
          ) ?
            words.metaOperator(status.page.companyName)
          : undefined
        }
        descriptionPending={operator && status.state === 'loading'}
        actions={
          onIntro && (
            <a
              href="/translation/intro"
              onClick={(event) => {
                event.preventDefault();
                onIntro();
              }}
              className="text-style-pre-caption-03 text-text-secondary"
            >
              {words.introLink}
            </a>
          )
        }
      />
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchField
              aria-label={words.searchLabel}
              placeholder={words.searchLabel}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-[300px]"
            />
            <Tabs
              value={tab}
              onValueChange={(value) => setTab(value as Tab)}
              variant="box"
            >
              <TabsList aria-label={words.tabsLabel}>
                {TABS.map((key) => (
                  <TabsTrigger key={key} value={key}>
                    {words.tabs[key]}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            {showMine && (
              <div className="flex items-center gap-2">
                <Checkbox
                  id={mineId}
                  checked={mine}
                  onCheckedChange={(checked) => setMine(checked === true)}
                />
                <Label
                  htmlFor={mineId}
                  className="cursor-pointer text-style-pre-body-06 text-text-secondary"
                >
                  {words.mineOnly}
                </Label>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {pdfButton('new-pdf')}
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={onNewTranslation}
            >
              <PlusIcon aria-hidden />
              {words.newTranslation}
            </Button>
          </div>
        </div>
        {status.state === 'loading' && <BatchTable rows={[]} loading />}
        {status.state === 'failed' && (
          <LoadFailure
            kind="failed"
            message={words.loadFailed}
            retryLabel={words.retry}
            onRetry={retry}
          />
        )}
        {status.state === 'ready' &&
          (rows.length === 0 ?
            filtered ?
              <Empty
                data-testid="list-empty-filtered"
                title={words.emptyFiltered}
                action={
                  <Button
                    variant="outlineGrey"
                    shape="round"
                    size="md"
                    onClick={() => {
                      setTab('all');
                      setMine(false);
                      setQuery('');
                    }}
                  >
                    {words.clearFilter}
                  </Button>
                }
              />
            : <Empty
                data-testid="list-empty"
                title={words.empty}
                action={
                  <div className="flex items-center gap-2">
                    {pdfButton('new-pdf-empty')}
                    <Button
                      variant="solidBlack"
                      shape="round"
                      size="md"
                      onClick={onNewTranslation}
                    >
                      <PlusIcon aria-hidden />
                      {words.newTranslation}
                    </Button>
                  </div>
                }
              />
          : <>
              {retryFailed && (
                <PageInfo
                  tone="error"
                  icon={<PageInfoIcon />}
                  role="alert"
                  data-testid="retry-failed"
                >
                  {TR_TEXT.failure.retryFailed}
                </PageInfo>
              )}
              <BatchTable
                rows={rows}
                onRetryPart={retryPart}
                onOpenBatch={(rowId) => open(rowId, onOpenBatch)}
                onOpenPart={(rowId, part) =>
                  open(rowId, (documentId, key) =>
                    onOpenPart(documentId, key, part),
                  )
                }
              />
              <PageInfo data-testid="list-guide" icon={<PageInfoIcon />}>
                {words.guide}
              </PageInfo>
            </>)}
      </Card>
    </div>
  );
}
