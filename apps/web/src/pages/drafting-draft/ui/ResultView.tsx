// RP-04 개조식 초안 결과 세 칸(밴드 RPW1 ③ — 발주서 §2-3, 시안 v188 RP-04_r1). 라우터를 모른다.
// - 읽기: 결과(GET /drafting/runs/{id}/result — 409 RUN_NOT_DONE 은 not_done) · 프로젝트(지금 목차·지금 문서). result.projectId ≠ 주소 프로젝트면 찾지 못함(§1-4 ⑥).
// - 머리: 부제 · 「개조식」 탭 · 셈 「목차 n개 · 초안 n · …」(잎만) · [전체 다시 만들기] · [내려받기](공용 받기 모달 → 「개조식 초안」 줄의 [Word] = docx — 이름은 Content-Disposition · rejected·readOnly 면 줄만 끄고 (?) 까닭 — RPW13).
// - 세 칸: 트리(지금 목차에 결과 잎을 key 로 · 점 다섯 · 접기) | 고른 잎의 bullet(칩·갈래 글·잎 갈래 글) | 원문 보기(SourcePane).
// - 띠(§2-0 ⑤): 결과의 목차 판이나 문서가 지금과 다를 때만 차이를 읽어 「목차가 바뀌었어요 · 바뀐 목차 n개」+[바뀐 목차 다시 만들기] · 줄 「바뀜」 ·
//   added 잎은 「아직 만들지 않았어요 · 새로 더한 목차예요」 · 문서 changed 면 「전년도 보고서를 다시 올렸어요」 · 차이 not_found·failed 면 띠 0.
// - 다시 만들기(→ 새 실행 주소): 전체 = {projectId}(base 0) · 바뀐 목차 = base{runId, rebuild: []} · 이 목차 = base{runId, rebuild:[key]}.
//   rejected 결과는 이어 받을 수 없어 바뀐 목차·이 목차를 끈다(전체는 켬). 거절은 한 줄(설정 화면 이름·서버 글 0). readOnly(앞 실행 위에서 다시 짓는 중 — §2-0 ⑦)면 단추 셋 다 끄고 다시 짓는 잎(rebuildingKeysOf)만 만드는 중 꼴·파란 점.
// - status rejected → 빨간 띠(숫자·서버 글 0), 띠 아래 [전체 다시 만들기] + 안내 한 줄(04c 꼴 — 머리 단추는 숨김)·잎 전부 아직 · base.matched false → 회색 한 줄 · 경고(warnings)는 화면 0 · reusedFrom 은 받아 두기만.
import { useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleWarningIcon,
  DownloadIcon,
  FileIcon,
  InfoIcon,
  ReportWordIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  DraftingStore,
  ResultOutcome,
} from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import {
  useProject,
  useRead,
  useResult,
} from '../../../entities/drafting/hooks/index.ts';
import type {
  Bullet,
  DraftingResult,
  Project,
} from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import { DownloadDialog } from '../../../shared/ui/download-dialog/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리, 밴드 RPW5 #7).
import '../../../shared/ui/motion/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import {
  bandOf,
  bulletKindOf,
  chipPagesOf,
  headCountsOf,
  needsChanges,
  pageSpanOf,
  rebuildOptionsOf,
  rebuildingKeysOf,
  rebuildsMoreThanAsked,
  treeOf,
} from '../model/index.ts';
import type { Dot, TreeRow } from '../model/index.ts';
import { SourcePane } from './SourcePane.tsx';

const words = DR_TEXT.result;

/** 좁은 폭의 기준(이 폭 이하면 트리를 접은 채 시작 — 처음 값만, 누른 뒤엔 사용자 값). */
const NARROW = '(max-width: 1280px)';
const narrowAtFirst = () =>
  typeof window.matchMedia === 'function' && window.matchMedia(NARROW).matches;

export interface ResultViewProps {
  store: DraftingStore;
  openPdf: OpenPdf;
  projectId: number;
  runId: number;
  operator: boolean;
  onList(): void;
  /** 새 실행의 RP-04 로. */
  onRun(runId: number): void;
  /** 앞 실행 위에서 다시 짓는 중(§2-0 ⑦) — 단추 끔, 이 key 들은 「다시 만드는 중」. */
  readOnly?: { rebuilding: readonly string[] };
  /** 머리 왼쪽의 실행 고르기(RunScreen 이 준다 — 경계 ④). */
  picker?: ReactNode;
}

type ResultState =
  | { state: 'loading' }
  | { state: 'ready'; result: DraftingResult; project: Project }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'not_found' | 'not_done' | 'failed' };

function stateOf(
  result: ResultOutcome | null,
  project: ReturnType<typeof useProject>['status'],
  projectId: number,
): ResultState {
  if (result === null || project.state === 'loading')
    return { state: 'loading' };
  if (result.kind === 'refused')
    return { state: 'refused', company: result.company };
  if (project.state === 'refused')
    return { state: 'refused', company: project.company };
  if (result.kind !== 'ok') return { state: result.kind };
  if (result.value.projectId !== projectId || project.state === 'not_found')
    return { state: 'not_found' };
  if (project.state !== 'ready') return { state: 'failed' };
  return { state: 'ready', result: result.value, project: project.value };
}

export function ResultView(props: ResultViewProps) {
  const { store, projectId, runId, operator, onList } = props;
  const loaded = useResult(store, runId);
  const project = useProject(store, projectId);
  const view = stateOf(
    loaded.status.kind === 'loading' ? null : loaded.status,
    project.status,
    projectId,
  );
  const companyText = operator ? DR_TEXT.companyOperator : DR_TEXT.company;
  const retry = () => {
    loaded.retry();
    project.retry();
  };

  if (view.state === 'loading') return <LoadSkeleton />;
  if (view.state === 'refused')
    return (
      <PageInfo
        role="alert"
        tone="error"
        icon={<CircleWarningIcon aria-hidden />}
        data-testid="company-refusal"
      >
        {companyText[view.company]}
      </PageInfo>
    );
  if (view.state === 'not_found')
    return (
      <LoadFailure
        kind="missing"
        message={words.resultMissing}
        listLabel={DR_TEXT.common.toList}
        onList={onList}
      />
    );
  if (view.state !== 'ready')
    return (
      <LoadFailure
        kind="failed"
        message={words.resultLoadFailed}
        retryLabel={DR_TEXT.common.retry}
        onRetry={retry}
      />
    );
  return <Ready {...props} result={view.result} project={view.project} />;
}

function Ready({
  store,
  openPdf,
  projectId,
  runId,
  operator,
  onRun,
  readOnly,
  picker,
  result,
  project,
}: ResultViewProps & { result: DraftingResult; project: Project }) {
  const rows = useMemo(
    () => treeOf(project.outline?.outline.nodes ?? [], result),
    [project, result],
  );
  const counts = headCountsOf(rows);
  const changes = useRead(
    needsChanges(project, result) ? [store, projectId, runId] : null,
    () => store.getChanges(projectId, runId),
  );
  const band =
    changes.status.state === 'ready' ? bandOf(changes.status.value) : null;
  const rebuilding =
    readOnly ?
      rebuildingKeysOf(readOnly.rebuilding, band, rows, result)
    : new Set<string>();
  const rejected = result.status.status === 'rejected';

  const [picked, setPicked] = useState<string | null>(
    () => rows.find((row) => row.isLeaf)?.key ?? null,
  );
  const row = rows.find((one) => one.key === picked) ?? null;
  const [bulletAt, setBulletAt] = useState<number | null>(null);
  const [page, setPage] = useState<number | null>(
    () => row?.leaf?.pages[0] ?? null,
  );
  const [folded, setFolded] = useState(narrowAtFirst);

  const bullets =
    row?.leaf?.outcome.status === 'done' ? row.leaf.outcome.bullets : [];
  const bullet = bulletAt === null ? null : (bullets[bulletAt] ?? null);

  const pick = (next: TreeRow) => {
    setPicked(next.key);
    setBulletAt(null);
    setPage(next.leaf?.pages[0] ?? null);
  };
  const pickBullet = (at: number, chip?: number) => {
    setBulletAt(at);
    const target = chip ?? chipPagesOf(bullets[at]!)[0];
    if (target !== undefined) setPage(target);
  };

  // 다시 만들기 — 두 번 눌러도 요청 하나(ref), 거절은 한 줄.
  const pressed = useRef(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<
    CompanyRefusal | 'start' | 'startFailed' | null
  >(null);
  const rebuild = async (
    how: Parameters<typeof rebuildOptionsOf>[0],
  ): Promise<void> => {
    if (pressed.current || readOnly) return;
    pressed.current = true;
    setBusy(true);
    setRefused(null);
    try {
      const started = await store.startRun(
        rebuildOptionsOf(how, projectId, runId),
        project.outline?.outlineId ?? null,
      );
      if (started.kind === 'ok') onRun(started.value.runId);
      else
        setRefused(
          started.kind === 'refused' ? started.company
          : started.kind === 'failed' ? 'startFailed'
          : 'start',
        );
    } finally {
      pressed.current = false;
      setBusy(false);
    }
  };
  const locked = busy || readOnly !== undefined;
  // 받기 모달 — 머리 단추는 늘 켬, 받을 수 없으면 모달 안 줄만 끄고 (?) 에 까닭(밴드 RPW13).
  const opener = useRef<HTMLButtonElement>(null);
  const [downloadsOpen, setDownloadsOpen] = useState(false);
  const downloadOff =
    rejected ? words.downloads.rejected
    : readOnly !== undefined ? words.downloads.rebuilding
    : undefined;
  const companyText = operator ? DR_TEXT.companyOperator : DR_TEXT.company;

  return (
    <div data-testid="run-result" className="flex flex-col gap-4">
      <p
        data-testid="result-subtitle"
        className="m-0 truncate text-style-pre-caption-03 text-text-tertiary"
      >
        {words.subtitle(project.year, project.name, result.pdf.fileName)}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          {picker}
          <p
            data-testid="result-counts"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {words.counts(
              counts.total,
              counts.drafted,
              counts.noMaterial,
              counts.failed,
              counts.notRun,
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!rejected && (
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              disabled={locked}
              onClick={() => void rebuild({ kind: 'all' })}
            >
              {DR_TEXT.run.restartAll}
            </Button>
          )}
          <Button
            ref={opener}
            variant="outlineGrey"
            shape="round"
            size="md"
            data-testid="result-download"
            aria-haspopup="dialog"
            onClick={() => setDownloadsOpen(true)}
          >
            <DownloadIcon aria-hidden />
            {words.download}
          </Button>
          {downloadsOpen && (
            <DownloadDialog
              testId="result-download-dialog"
              title={words.downloads.title}
              closeLabel={words.downloads.close}
              helpLabel={words.downloads.helpLabel}
              failedText={words.downloadFailed}
              busyLabel={words.downloads.busy}
              files={[
                {
                  key: 'docx',
                  name: words.downloads.name,
                  description: words.downloads.description,
                  fileLabel: words.downloads.fileLabel,
                  icon: <ReportWordIcon />,
                  download: async () => {
                    const got = await store.downloadDocx(runId);
                    if (got.kind !== 'ok') throw new Error('download');
                    return { blob: got.blob, fileName: got.fileName };
                  },
                  ...(downloadOff !== undefined ?
                    { disabledReason: downloadOff }
                  : {}),
                },
              ]}
              onClose={() => setDownloadsOpen(false)}
              returnFocus={() => opener.current}
            />
          )}
        </div>
      </div>
      <Tabs value="draft">
        <TabsList>
          <TabsTrigger value="draft">{words.tab}</TabsTrigger>
        </TabsList>
      </Tabs>
      {rejected && (
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="result-rejected"
        >
          {words.rejected}
        </PageInfo>
      )}
      {rejected && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outlineGrey"
            shape="round"
            size="sm"
            loading={busy}
            disabled={locked}
            onClick={() => void rebuild({ kind: 'all' })}
          >
            {DR_TEXT.run.restartAll}
          </Button>
          <span
            data-testid="result-rejected-hint"
            className="text-style-pre-caption-03 text-text-tertiary"
          >
            {DR_TEXT.run.failedHint}
          </span>
        </div>
      )}
      {result.base !== null && !result.base.matched && (
        <p
          data-testid="result-not-matched"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.notMatched}
        </p>
      )}
      {readOnly &&
        rebuildsMoreThanAsked(rebuilding, readOnly.rebuilding, band) && (
          <p
            data-testid="result-rebuilding-more"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {words.rebuildingMore}
          </p>
        )}
      {band !== null && (
        <PageInfo
          tone="important"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="result-band"
          className="[&>div]:flex-1"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span data-testid="band-text" className="min-w-0">
              {band.count > 0 && (
                <span data-testid="band-count">
                  <strong className="font-bold">{words.changed}</strong>
                  {` · ${words.changedCount(band.count)}`}
                </span>
              )}
              {band.reuploaded && (
                <span data-testid="band-reuploaded" className="block">
                  {words.reuploaded}
                </span>
              )}
            </span>
            {band.count > 0 && (
              <Button
                variant="solidBlack"
                shape="round"
                size="sm"
                disabled={locked || rejected}
                onClick={() => void rebuild({ kind: 'changed' })}
              >
                {words.rebuildChanged}
              </Button>
            )}
          </div>
        </PageInfo>
      )}
      {refused !== null && (
        <p
          role="alert"
          data-testid="start-refused"
          className="m-0 flex items-start gap-1 text-style-pre-caption-03 text-support-error [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0"
        >
          <CircleWarningIcon aria-hidden />
          {refused === 'start' ?
            DR_TEXT.startRefused
          : refused === 'startFailed' ?
            DR_TEXT.startFailed
          : companyText[refused]}
        </p>
      )}
      <div
        className={cn(
          'grid items-start gap-4',
          folded ?
            'grid-cols-[3.5rem_minmax(0,1.4fr)_minmax(0,1fr)]'
          : 'grid-cols-[minmax(14rem,0.65fr)_minmax(0,1.4fr)_minmax(0,1fr)]',
        )}
      >
        <Tree
          rows={rows}
          picked={picked}
          folded={folded}
          onFold={setFolded}
          marks={band?.marks ?? null}
          rebuilding={rebuilding}
          onPick={pick}
        />
        {/* 세 칸 첫 그림 rise · 잎을 바꾸면 bullet 칸 fade(key = 잎 — 밴드 RPW5 #7) */}
        <Card
          className="gw-m-rise flex min-w-0 flex-col gap-3"
          data-testid="leaf-pane"
        >
          {row === null ?
            null
          : !row.isLeaf ?
            <p className="m-0 text-style-pre-body-05 text-text-tertiary">
              {words.pickLeaf}
            </p>
          : <div
              key={row.key}
              data-testid="leaf-fade"
              data-leaf={row.key}
              className="gw-m-fade flex min-w-0 flex-col gap-3"
            >
              <LeafBody
                row={row}
                bullets={bullets}
                bulletAt={bulletAt}
                page={page}
                added={band?.marks.get(row.key) === 'added'}
                rebuilding={rebuilding.has(row.key)}
                locked={locked || rejected}
                onRebuild={() => void rebuild({ kind: 'one', key: row.key })}
                onBullet={pickBullet}
              />
            </div>
          }
        </Card>
        <Card className="gw-m-rise min-w-0" data-testid="source-card">
          <SourcePane
            store={store}
            openPdf={openPdf}
            pdf={result.pdf}
            leafPages={row?.leaf?.pages ?? []}
            page={page}
            onPage={setPage}
            bullet={bullet}
          />
        </Card>
      </div>
    </div>
  );
}

/** 트리 들여쓰기(RPW3 R6 — 소소 단계 약 −8px). */
const treeIndent = (depth: number) => 12 + (depth - 1) * 9;

/** 점은 눈에 셋(RPW12 · `MARC-ENT-656`) — 완성(채움) · 미완성(빈 원: 근거 빈 문장·자료 없음·실패·아직) · 재생성 중(파랑+옅은 고리).
 *  뜻 다섯은 `data-dot` 에 그대로 남는다(까닭은 머리 셈 줄·오른쪽 칸이 말함). */
const DOT_OPEN = 'border border-text-tertiary bg-transparent';
const DOT_CLASS: Record<Dot | 'rebuilding', string> = {
  rebuilding: 'bg-support-blue ring ring-support-blue-subtle',
  done: 'bg-text-primary',
  unsupported: DOT_OPEN,
  no_material: DOT_OPEN,
  failed: DOT_OPEN,
  not_run: DOT_OPEN,
};

function Tree({
  rows,
  picked,
  folded,
  onFold,
  marks,
  rebuilding,
  onPick,
}: {
  rows: readonly TreeRow[];
  picked: string | null;
  folded: boolean;
  onFold(folded: boolean): void;
  marks: ReadonlyMap<string, 'changed' | 'added'> | null;
  rebuilding: ReadonlySet<string>;
  onPick(row: TreeRow): void;
}) {
  return (
    <Card
      className={cn('gw-m-rise flex min-w-0 flex-col gap-2', folded && 'px-2')}
      data-testid="result-tree"
      data-folded={folded}
    >
      <div
        className={cn(
          'flex items-center gap-2',
          folded ? 'justify-center' : 'justify-between',
        )}
      >
        {!folded && (
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.tree}
          </h3>
        )}
        <button
          type="button"
          aria-label={folded ? words.treeOpen : words.treeFold}
          onClick={() => onFold(!folded)}
          className="flex size-6 items-center justify-center rounded text-text-secondary [&_svg]:size-4"
        >
          {folded ?
            <ChevronRightIcon aria-hidden />
          : <ChevronLeftIcon aria-hidden />}
        </button>
      </div>
      <ul role="listbox" className="m-0 flex list-none flex-col gap-0.5 p-0">
        {rows.map((row) => {
          const mark = marks?.get(row.key);
          const dot = rebuilding.has(row.key) ? 'rebuilding' : row.dot;
          // 점·「바뀜」은 첫 줄에만 선다 — 번호와 제목은 한 흐름이라 둘째 줄이 칸 폭 전부를 쓴다(1280 소소 단계도 끝까지).
          const rowMarks = (
            <span
              data-testid="tree-marks"
              className={cn(
                'flex h-[1lh] items-center gap-2',
                folded ? 'shrink-0' : 'float-right ml-2',
              )}
            >
              {!folded && mark && (
                <span
                  data-testid="changed-mark"
                  className="shrink-0 rounded-full bg-support-orange-subtle px-1.5 text-style-pre-caption-02 text-support-orange-dark"
                >
                  {words.changedMark}
                </span>
              )}
              {dot !== null ?
                <span
                  aria-hidden
                  data-testid="tree-dot"
                  className={cn(
                    'inline-block size-2 shrink-0 rounded-full',
                    DOT_CLASS[dot],
                  )}
                />
              : <span aria-hidden className="inline-block size-2 shrink-0" />}
            </span>
          );
          return (
            <li
              key={row.key}
              role="option"
              aria-selected={row.key === picked}
              data-key={row.key}
              data-dot={dot ?? undefined}
              data-mark={mark}
              tabIndex={0}
              aria-label={folded ? `${row.number} ${row.title}` : undefined}
              onClick={() => onPick(row)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onPick(row);
                }
              }}
              className={cn(
                'flex cursor-pointer items-start gap-2 rounded border-0 border-l-2 border-solid py-1 pr-2 text-style-pre-body-05',
                folded && 'justify-center px-0',
                row.depth === 1 && 'font-bold',
                row.key === picked ?
                  'border-l-text-primary bg-background-secondary text-text-primary'
                : 'border-l-transparent text-text-secondary',
              )}
              style={
                folded ? undefined : { paddingLeft: treeIndent(row.depth) }
              }
            >
              {folded ?
                rowMarks
              : <span
                  data-testid="tree-title"
                  title={row.title}
                  className="line-clamp-2 min-w-0 flex-1 break-words"
                >
                  {rowMarks}
                  <span
                    data-testid="tree-number"
                    className="mr-2 whitespace-nowrap tabular-nums text-text-tertiary"
                  >
                    {row.number}
                  </span>
                  <span data-testid="tree-title-text">{row.title}</span>
                </span>
              }
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function LeafBody({
  row,
  bullets,
  bulletAt,
  page,
  added,
  rebuilding,
  locked,
  onRebuild,
  onBullet,
}: {
  row: TreeRow;
  bullets: readonly Bullet[];
  bulletAt: number | null;
  page: number | null;
  added: boolean;
  rebuilding: boolean;
  locked: boolean;
  onRebuild(): void;
  onBullet(at: number, chip?: number): void;
}) {
  const leaf = row.leaf;
  const status = leaf?.outcome.status ?? 'not_run';
  const path = leaf?.titlePath ?? row.titlePath;
  return (
    <>
      <p
        data-testid="leaf-path"
        className="m-0 text-style-pre-caption-03 text-text-tertiary"
      >
        {path.slice(0, -1).map((title) => `${title} › `)}
      </p>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <h3
            data-testid="leaf-title"
            className="m-0 text-style-pre-heading-02 text-text-primary"
          >
            {`${row.number} ${row.title}`}
          </h3>
          {status === 'done' && !rebuilding && (
            <p
              data-testid="leaf-meta"
              className="m-0 text-style-pre-caption-03 text-text-secondary"
            >
              {words.leafMeta(bullets.length, pageSpanOf(leaf!.pages))}
            </p>
          )}
          {rebuilding && (
            <p
              data-testid="leaf-rebuilding"
              className="m-0 text-style-pre-caption-03 text-text-secondary"
            >
              {words.rebuilding}
            </p>
          )}
        </div>
        <Button
          variant="outlineGrey"
          shape="round"
          size="sm"
          disabled={locked}
          onClick={onRebuild}
        >
          {words.rebuildOne}
        </Button>
      </div>
      {row.requirement !== '' && (
        <div className="flex flex-col gap-1">
          <span className="text-style-pre-caption-02 text-text-tertiary">
            {words.requirement}
          </span>
          <p className="m-0 whitespace-pre-wrap text-style-pre-body-05 text-text-secondary">
            {row.requirement}
          </p>
        </div>
      )}
      {rebuilding ?
        <div className="flex flex-col gap-2">
          <div
            aria-hidden
            data-testid="leaf-skeleton"
            className="flex animate-pulse flex-col gap-2"
          >
            <div className="h-4 rounded bg-background-secondary" />
            <div className="h-4 w-5/6 rounded bg-background-secondary" />
            <div className="h-4 w-2/3 rounded bg-background-secondary" />
          </div>
          <p
            data-testid="leaf-state"
            className="m-0 text-style-pre-body-05 text-text-secondary"
          >
            {words.rebuildingNote}
          </p>
        </div>
      : status === 'done' ?
        <>
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {words.guide}
          </p>
          <ul
            data-testid="bullets"
            className="m-0 flex list-none flex-col gap-3 p-0"
          >
            {bullets.map((bullet, at) => (
              <BulletRow
                key={at}
                bullet={bullet}
                picked={at === bulletAt}
                page={page}
                onPick={(chip) => onBullet(at, chip)}
              />
            ))}
          </ul>
        </>
      : status === 'failed' ?
        <PageInfo
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="leaf-state"
          data-state={status}
        >
          {words.leafFailed}
        </PageInfo>
      : <div
          data-testid="leaf-state"
          data-state={status}
          data-tone="plain"
          className="flex items-start gap-2 rounded-component border border-solid border-border-tertiary bg-background-primary px-4 py-3 text-style-pre-body-06 text-text-secondary [&_svg]:mt-0.5 [&_svg]:size-4 [&_svg]:shrink-0"
        >
          <InfoIcon aria-hidden />
          <div className="flex min-w-0 flex-col gap-1">
            <p className="m-0">
              {status === 'no_material' ? words.noMaterial : words.notRun}
            </p>
            {added && status === 'not_run' && (
              <p
                data-testid="leaf-added"
                className="m-0 text-style-pre-caption-03 text-text-tertiary"
              >
                {words.added}
              </p>
            )}
          </div>
        </div>
      }
    </>
  );
}

function BulletRow({
  bullet,
  picked,
  page,
  onPick,
}: {
  bullet: Bullet;
  picked: boolean;
  page: number | null;
  onPick(chip?: number): void;
}) {
  const kind = bulletKindOf(bullet);
  return (
    <li
      data-testid="bullet"
      data-kind={kind}
      data-picked={picked || undefined}
      className={cn(
        'flex flex-col gap-1.5 border-0 border-l-2 border-solid px-2 py-1.5',
        picked ? 'border-l-text-primary' : 'border-l-transparent',
      )}
    >
      <button
        type="button"
        onClick={() => onPick()}
        className="text-left text-style-pre-body-05 text-text-primary"
      >
        {`• ${bullet.text}`}
      </button>
      {kind === 'chips' ?
        <div className="flex flex-wrap gap-1">
          {chipPagesOf(bullet).map((chip) => (
            <button
              key={chip}
              type="button"
              data-testid="source-chip"
              data-page={chip}
              aria-pressed={picked && chip === page}
              onClick={() => onPick(chip)}
              className={cn(
                'inline-flex items-center gap-1 rounded-full border border-solid px-2 py-0.5 text-style-pre-caption-02 [&_svg]:size-3.5 [&_svg]:shrink-0',
                picked && chip === page ?
                  'border-transparent bg-background-primary-inverse text-text-primary-inverse'
                : 'border-border-tertiary bg-transparent text-text-secondary',
              )}
            >
              <FileIcon aria-hidden />
              {words.chip(chip)}
            </button>
          ))}
        </div>
      : <span
          data-testid="bullet-note"
          className="self-start rounded-full bg-support-error-subtle px-2 py-0.5 text-style-pre-caption-02 text-support-error-accent"
        >
          {kind === 'no_source' ? words.noSource : words.notInSource}
        </span>
      }
    </li>
  );
}
