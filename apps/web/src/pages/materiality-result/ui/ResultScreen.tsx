// IR-04·04a 결과(밴드 IRW1 ②, 시안 v157 IR-04_r1·IR-04a_r1). 라우터를 모른다 — 저장소와 콜백 props 를 받는다(데이터 검증 ResultScreen 꼴).
// 머리 「<기업명> · 중대성평가」 + 배지 완료 + 메타 「<끝> 끝남 · 토픽 n · 서브토픽 n · 리서치 기간 <시작> ~ <끝> · 금융|비금융」(「1회차」 0 — Q4)
//   · [다시 실행]·[내려받기] → STEP 3 → 숫자 카드 다섯 → 정하지 못함 안내(important) → 경고 줄 → 탭 셋(기본 2-1, 화면 상태 — search 0).
//   표 줄은 최종 엑셀 규칙(model/result.ts). 「정하지 못함」 줄은 「전체」 탭 끝에만 흐리게(숫자 밖).
// 실행(GET /runs/{id})은 끝 시각·「오늘까지」의 날·파일 목록에만 쓴다. 받기(밴드 IRW16 — 판 IR-04b r1, 결정 sid:MARC-ENT-662·663):
//   머리 [내려받기] 하나가 공용 받기 모달(shared/ui/download-dialog)을 연다 — 줄 둘(결과 엑셀 · 리서치 엑셀)을 늘 그리고
//   files 에 없는 파일은 꺼진 줄 + (?) 까닭(옛 머리·결과 엑셀 카드의 [엑셀 내려받기] · 1-1 탭의 [리서치 엑셀 내려받기]를 갈음, sid:MARC-ENT-449).
//   실행을 못 읽으면(failed·missing) 머리 [내려받기] 자리에 회색 한 줄(381 m3 — 부록 A6-⑫), 「오늘까지」 는 원문 그대로.
// 결과가 아직이면(409 RUN_NOT_DONE) onNotDone(쓰는 쪽이 IR-03 으로 replace). 없음 → 「평가를 찾을 수 없어요」, 그 밖 → load-failure.
// 서버 message 는 보이지 않는다(거울이 버린다). 모델 글은 글자 그대로(마크다운·HTML 해석 0). 모델 url 은 http(s) 일 때만 새 창 링크, 아니면 글자.
// 표(밴드 IRW4·IRW5): 결과 표 셋 다 공용 DataTable — 2-1·1-1 fixed, 2-2 auto(+ DT3 줄 열림·펼침 줄 data-*).
//   2-2 줄 누름 규칙(밴드 IRW13, sid:MARC-ENT-599 규칙 2·4·5): 누름 줄 hover 바탕 · rowLabel 「n번 서브토픽 컨텍스트 요약」 · 첫 열(No 앞) 장식 꺾쇠(개정 2).
// 글 칸 고치기(밴드 IRW11 — 판 IR-04·04a r3, 결정 sid:MARC-ENT-561): 세 표 끝 「고치기」 열 → 그 줄만 편집(한 번에 하나 — 상태는 ResultView 하나,
//   Q5) · 고친 칸 연필·표 머리 배지 · 저장은 useResultEdits(저장 뒤 결과를 뒤에서 다시 읽어 바꿔 낌 — 탭·거르기 그대로, Q6) · 409 → [새로 불러오기] ·
//   바꾼 채 화면 안 이동은 화면이 묻고(guard), 경로 이동은 ResultRoute 의 useBlocker 가 막아 leave 로 묻는다(Q9). 고침을 못 읽으면 읽기 전용(Q7).
//   결과 엑셀은 고친 판 GET /materiality/runs/{id}/report(Q11).
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import type { CSSProperties, ReactNode } from 'react';

import {
  ChevronDownIcon,
  CircleWarningIcon,
  DownloadIcon,
  PenIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import type { MaterialityStore } from '../../../entities/materiality/api/index.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import {
  useRerun,
  useResult,
  useResultEdits,
  useRun,
} from '../../../entities/materiality/hooks/index.ts';
import type { ResultEditsHandle } from '../../../entities/materiality/hooks/index.ts';
import {
  REPORT_FILE_NAME,
  RESEARCH_FILE_NAME,
  atText,
  changesOf,
  checkDrafts,
  editOfCell,
  editSummary,
  editedClock,
  impactFields,
  impactLines,
  itemFields,
  lineContext,
  pathwayFields,
  pathwayLines,
  periodOf,
  resultCards,
  rowPointer,
  runDay,
  shortlistCellPointers,
  shortlistLines,
  subtopicTotal,
  summaryCellPointers,
  undecidedImpact,
  undecidedPathway,
  undecidedSubtopics,
  warningViews,
} from '../../../entities/materiality/model/index.ts';
import type {
  Cell,
  EditField,
  FinancialKind,
  ImpactLine,
  ImpactTone,
  MaterialityResult,
  MaterialityRun,
  MergedItem,
  PathwayLine,
  ShortlistCell,
  ShortlistLine,
  SubtopicRef,
} from '../../../entities/materiality/model/index.ts';
import { IroFlow } from '../../../entities/materiality/ui/index.ts';
import { isSafeLinkUrl } from '../../../shared/lib/safeUrl.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type {
  DataTableColumnDef,
  RowData,
} from '../../../shared/ui/data-table/index.ts';
import { DownloadDialog } from '../../../shared/ui/download-dialog/index.ts';
import type { DownloadDialogFile } from '../../../shared/ui/download-dialog/index.ts';
import { ReportXlsxIcon } from '../../../shared/ui/file-type-icon/index.ts';
import { FilterSelect } from '../../../shared/ui/filter-select/index.ts';
import { LinkChip } from '../../../shared/ui/link-chip/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
import { CountUp } from '../../../shared/ui/motion/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../../shared/ui/tabs/index.ts';
import {
  EditActions,
  EditBox,
  EditContext,
  ItemBoxes,
  isEditing,
  useEdit,
} from './EditRow.tsx';
import type { EditApi, EditTab, Editing } from './EditRow.tsx';
import { EditedMark } from './EditedMark.tsx';
import { LeaveDialog } from './LeaveDialog.tsx';

const words = IR_TEXT.result;
const editWords = IR_TEXT.result.edit;
const common = IR_TEXT.common;
const downloadWords = IR_TEXT.result.downloads;
/** 받기 모달 줄 차례(판 IR-04b r1). */
const DOWNLOAD_KEYS = ['report', 'research'] as const;
const dash = IR_TEXT.dash;

const TONE_BADGE: Record<ImpactTone, BadgeProps['variant']> = {
  positive: 'success',
  negative: 'error',
  other: 'grey',
};
const KIND_BADGE: Record<FinancialKind, BadgeProps['variant']> = {
  risk: 'error',
  opportunity: 'success',
  other: 'grey',
};

type Tab = 'shortlist' | 'impact' | 'pathway';
const TABS: readonly Tab[] = ['shortlist', 'impact', 'pathway'];
const ALL_TOPICS = '';

export interface ResultScreenProps {
  store: MaterialityStore;
  runId: string;
  /** [목록으로](불러오지 못함·없음). */
  onBack(): void;
  /** [다시 실행]으로 새 실행이 생겼을 때(새 IR-03 — push). */
  onRerun(runId: string): void;
  /** 아직 끝나지 않은 실행(409) — 쓰는 쪽이 IR-03 으로 replace. */
  onNotDone(): void;
  /** 편집 줄에 바꾼 글이 생기고 없어질 때(경로 이동 막기 — ResultRoute 의 useBlocker, Q9). */
  onDirtyChange?(dirty: boolean): void;
  /** 경로 이동이 막혔을 때(쓰는 쪽 useBlocker): pending 이면 나가기 창, proceed 는 [나가기], reset 은 [계속 고치기]. */
  leave?: { pending: boolean; proceed(): void; reset(): void };
}

export function ResultScreen({
  store,
  runId,
  onBack,
  onRerun,
  onNotDone,
  onDirtyChange,
  leave,
}: ResultScreenProps) {
  const { status: result, retry } = useResult(store, runId);
  const edits = useResultEdits(store, runId);
  const { status: run } = useRun(store, runId);
  const rerun = useRerun(store, runId);
  const notDone = result.state === 'not_done';
  useEffect(() => {
    if (notDone) onNotDone();
  }, [notDone, onNotDone]);
  const loading =
    result.state === 'loading' || notDone || run.state === 'loading';
  const skeleton = useDelayed(loading);

  if (result.state !== 'ready' || run.state === 'loading')
    return (
      <div
        data-screen="materiality-result"
        data-result-state={loading ? 'loading' : result.state}
        aria-busy={loading || undefined}
        className="flex flex-col gap-6"
      >
        {/* 읽는 동안은 제목·메타 자리만(셸 제목을 그렸다가 기업 제목으로 바꾸지 않는다 — sid:MARC-ENT-443). */}
        <PageTitle
          title={IR_TEXT.shell.title}
          titlePending={loading}
          descriptionPending={loading}
        />
        {result.state === 'missing' ?
          <LoadFailure
            kind="missing"
            message={common.notFound}
            listLabel={common.toList}
            onList={onBack}
          />
        : result.state === 'failed' ?
          <LoadFailure
            kind="failed"
            message={words.loadFailed}
            retryLabel={common.retry}
            listLabel={common.toList}
            onRetry={retry}
            onList={onBack}
          />
        : skeleton && <LoadSkeleton />}
      </div>
    );

  const readyRun = run.state === 'ready' ? run.run : null;
  const reportReady =
    readyRun !== null && readyRun.files.includes(REPORT_FILE_NAME);
  const researchReady =
    readyRun !== null && readyRun.files.includes(RESEARCH_FILE_NAME);
  /** 모달 줄 둘(차례 결과 → 리서치). 실행을 못 읽으면 null — 머리는 회색 한 줄. */
  const files =
    readyRun === null ? null : (
      DOWNLOAD_KEYS.map((key) => {
        const ready = key === 'report' ? reportReady : researchReady;
        return {
          key,
          name: downloadWords.files[key],
          description: downloadWords.fileNotes[key],
          fileLabel: downloadWords.files[key],
          icon: <ReportXlsxIcon />,
          download:
            key === 'report' ?
              () => store.reportFile(runId)
            : () => store.researchFile(runId),
          ...(ready ? {} : { disabledReason: downloadWords.fileMissing[key] }),
        };
      })
    );
  return (
    <ResultView
      result={result.result}
      edits={edits}
      onDirtyChange={onDirtyChange}
      leave={leave}
      run={readyRun}
      files={files}
      researchReady={researchReady}
      rerunError={rerun.failed}
      rerunButton={
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          loading={rerun.rerunning}
          onClick={async () => {
            const next = await rerun.rerun();
            if (next !== null) onRerun(next);
          }}
        >
          {common.rerun}
        </Button>
      }
    />
  );
}

/** 리서치 기간 글(「시작 ~ 끝」, 못 읽으면 원문). */
function periodText(result: MaterialityResult, run: MaterialityRun | null) {
  const period = periodOf(
    result.scope.dateRange,
    run === null ? null : runDay(run),
  );
  return period.kind === 'range' ?
      words.period(period.start, period.end)
    : period.text;
}

const refText = (refs: readonly SubtopicRef[]) =>
  refs
    .map((ref) => words.subtopicRef(ref.topic, ref.subtopic))
    .join(words.refJoiner);

/** 편집 줄의 고칠 칸(차례대로). 그 줄이 없거나 고칠 칸이 없으면 null. */
function fieldsFor(
  result: MaterialityResult,
  tab: EditTab,
  no: number,
): EditField[] | null {
  let fields: EditField[] = [];
  if (tab === 'impact') {
    const line = impactLines(result).find((l) => l.no === no);
    if (line === undefined) return null;
    const found = impactFields(result, line);
    fields = [found.definition, ...found.summaries.filter(isField)];
  } else if (tab === 'pathway') {
    const line = pathwayLines(result).find((l) => l.no === no);
    if (line === undefined) return null;
    const found = pathwayFields(result, line);
    fields = [
      found.rows.definition,
      found.rows.driver,
      found.rows.business,
      found.rows.financial,
      ...found.summaries.filter(isField),
    ];
  } else {
    const line = shortlistLines(result).find((l) => l.no === no);
    if (line === undefined) return null;
    for (const cell of [line.regulation, line.controversy])
      if (cell.researched)
        for (const item of cell.items) {
          const found = itemFields(result, no - 1, item);
          if (found !== null) fields.push(found.title, found.url);
        }
  }
  return fields.length === 0 ? null : fields;
}

const isField = (field: EditField | null): field is EditField => field !== null;

/** 처음 글(지금 값 — null 은 빈 글). 같은 바른 주소는 하나. */
const draftOf = (fields: readonly EditField[]) =>
  Object.fromEntries(
    [...fields].reverse().map((field) => [field.pointer, field.value ?? '']),
  );

function ResultView({
  result: base,
  edits,
  onDirtyChange,
  leave,
  run,
  files,
  researchReady,
  rerunError,
  rerunButton,
}: {
  result: MaterialityResult;
  edits: ResultEditsHandle;
  onDirtyChange: ((dirty: boolean) => void) | undefined;
  leave: ResultScreenProps['leave'];
  run: MaterialityRun | null;
  /** 받기 모달 줄 둘. null 은 실행을 못 읽음(failed·missing) — [내려받기] 자리에 회색 한 줄(381 m3). */
  files: readonly DownloadDialogFile[] | null;
  /** 실행 files 에 리서치 엑셀이 있음(1-1 각주 「전체는 리서치 엑셀에 있어요.」). */
  researchReady: boolean;
  rerunError: boolean;
  rerunButton: ReactNode;
}) {
  const [tab, setTab] = useState<Tab>('impact');
  const [downloadsOpen, setDownloadsOpen] = useState(false);
  const downloadsOpener = useRef<HTMLButtonElement>(null);
  // 저장·다시 읽기 뒤에는 훅이 쥔 새 판(Q6 — 화면은 붙은 채).
  const result = edits.result ?? base;
  const [editing, setEditing] = useState<Editing | null>(null);
  /** 화면 안 이동을 물을 때의 그 이동(Q9). */
  const [pendingLeave, setPendingLeave] = useState<(() => void) | null>(null);
  /** 화면 안 이동을 묻고 [계속 고치기]·Esc 로 머문 참(밴드 IRW11b B1 — 창이 닫힐 때 초점을 연 자리(탭 단추)로 돌려주면
   *  automatic 탭이 그 초점만으로 바뀌어 guard 가 다시 묻는다. 그래서 그때만 초점을 편집 줄 첫 고칠 칸으로 옮긴다). */
  const stayed = useRef(false);
  const [focus, setFocus] = useState<{
    kind: 'open' | 'close';
    tab: EditTab;
    no: number;
  } | null>(null);
  const body = useRef<HTMLDivElement>(null);
  const dirty =
    editing !== null && changesOf(editing.fields, editing.draft).length > 0;
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  // 열면 첫 고칠 칸에 초점(2-2 는 그 칸이 보이게 가로로 밈), 닫으면 그 줄 [고치기]로.
  useEffect(() => {
    if (focus === null) return;
    const root = body.current;
    if (root !== null) {
      if (focus.kind === 'open') {
        const first =
          root.querySelector<HTMLElement>('[data-edit-first]') ??
          root.querySelector<HTMLElement>('[data-edit-field]');
        first?.scrollIntoView?.({ inline: 'nearest', block: 'nearest' });
        first?.focus({ preventScroll: true });
      } else
        root
          .querySelector<HTMLElement>(
            `[data-edit-button="${focus.tab}-${focus.no}"]`,
          )
          ?.focus();
    }
    setFocus(null);
  }, [focus]);

  const close = useCallback((was: Editing | null) => {
    setEditing(null);
    if (was !== null) setFocus({ kind: 'close', tab: was.tab, no: was.no });
  }, []);

  const api: EditApi = {
    result,
    readOnly: edits.state !== 'ready',
    edits: edits.edits,
    editing,
    dirty,
    open(at, no) {
      const fields = fieldsFor(result, at, no);
      if (fields === null) return;
      setEditing({
        tab: at,
        no,
        fields,
        draft: draftOf(fields),
        errors: {},
        conflict: false,
        failed: false,
        saving: false,
      });
      setFocus({ kind: 'open', tab: at, no });
    },
    setDraft(pointer, text) {
      setEditing((now) => {
        if (now === null) return now;
        const errors = { ...now.errors };
        delete errors[pointer];
        return { ...now, draft: { ...now.draft, [pointer]: text }, errors };
      });
    },
    cancel() {
      close(editing);
    },
    save() {
      const now = editing;
      if (now === null || now.saving) return;
      const errors = checkDrafts(result, now.fields, now.draft);
      if (Object.keys(errors).length > 0) {
        setEditing({ ...now, errors });
        return;
      }
      const changes = changesOf(now.fields, now.draft);
      if (changes.length === 0) return;
      setEditing({ ...now, saving: true, failed: false, conflict: false });
      void edits.save(changes, result).then((kind) => {
        if (kind === 'saved') close(now);
        else
          setEditing((later) =>
            later === null ? later : (
              {
                ...later,
                saving: false,
                conflict: kind === 'conflict',
                failed: kind !== 'conflict',
              }
            ),
          );
      });
    },
    reload() {
      const now = editing;
      if (now === null) return;
      void edits.reload().then((fresh) => {
        if (fresh === null) {
          setEditing((later) => later && { ...later, failed: true });
          return;
        }
        const fields = fieldsFor(fresh, now.tab, now.no);
        if (fields === null) {
          close(now);
          return;
        }
        setEditing({
          ...now,
          fields,
          draft: draftOf(fields),
          errors: {},
          conflict: false,
          failed: false,
          saving: false,
        });
      });
    },
    guard(action) {
      if (editing === null) action();
      else if (!dirty) {
        setEditing(null);
        action();
      } else setPendingLeave(() => action);
    },
  };
  const cards = resultCards(result);
  const undecided = undecidedSubtopics(result);
  const warnings = warningViews(result.warnings);
  const finished =
    run === null ? dash : atText(run.finishedAt ?? run.createdAt);
  const notRun = result.part2.status !== 'done';
  return (
    <EditContext.Provider value={api}>
      <TooltipProvider>
        <div
          ref={body}
          data-screen="materiality-result"
          className="flex flex-col gap-6"
        >
          <PageTitle
            title={
              <span className="inline-flex flex-wrap items-center gap-2">
                {IR_TEXT.titleOf(result.companyName)}
                <Badge variant="success">{IR_TEXT.badge.done}</Badge>
              </span>
            }
            description={
              <span data-testid="meta">
                {words.meta(
                  finished,
                  String(cards.topics),
                  IR_TEXT.orDash(cards.subtopics),
                  periodText(result, run),
                  IR_TEXT.sector[result.scope.sector],
                )}
              </span>
            }
            actions={
              <>
                {rerunButton}
                {files === null ?
                  <span data-testid="downloads-run-failed" className={SMALL}>
                    {downloadWords.runFailed}
                  </span>
                : <Button
                    ref={downloadsOpener}
                    variant="outlineGrey"
                    shape="round"
                    size="md"
                    data-testid="downloads"
                    aria-haspopup="dialog"
                    onClick={() => setDownloadsOpen(true)}
                  >
                    <DownloadIcon aria-hidden />
                    {downloadWords.title}
                  </Button>
                }
              </>
            }
          />
          {rerunError && (
            <PageInfo
              tone="error"
              role="alert"
              icon={<CircleWarningIcon aria-hidden />}
              data-testid="rerun-error"
            >
              {common.rerunFailed}
            </PageInfo>
          )}
          <IroFlow current={3} />

          <div
            data-testid="cards"
            className="grid grid-cols-2 gap-4 lg:grid-cols-5"
          >
            <Stat
              order={0}
              id="topics"
              label={words.cards.topics}
              value={cards.topics}
              unit={words.cards.unitCount}
              sub={
                cards.subtopics === null ?
                  null
                : words.cards.subtopics(cards.subtopics)
              }
            />
            <Stat
              order={1}
              id="regulation"
              label={words.cards.regulation}
              value={cards.regulation}
              unit={words.cards.unitCase}
            />
            <Stat
              order={2}
              id="controversy"
              label={words.cards.controversy}
              value={cards.controversy}
              unit={words.cards.unitCase}
            />
            <Stat
              order={3}
              id="impact"
              label={words.cards.impact}
              value={cards.impact?.total ?? null}
              unit={words.cards.unitCount}
              sub={
                cards.impact === null ?
                  null
                : words.cards.impactSub(
                    cards.impact.positive,
                    cards.impact.negative,
                  )
              }
            />
            <Stat
              order={4}
              id="pathway"
              label={words.cards.pathway}
              value={cards.pathway?.total ?? null}
              unit={words.cards.unitCount}
              sub={
                cards.pathway === null ?
                  null
                : words.cards.pathwaySub(
                    cards.pathway.risk,
                    cards.pathway.opportunity,
                  )
              }
            />
          </div>

          {undecided.length > 0 && (
            <PageInfo
              tone="important"
              icon={<PageInfoIcon />}
              data-testid="undecided"
            >
              {words.undecided(
                subtopicTotal(result),
                undecided.length,
                refText(undecided),
              )}
            </PageInfo>
          )}
          {warnings.length > 0 && (
            // 경고 줄은 한 묶음(줄 사이 8 — 키트 --space-2, 433 ③). 빈 묶음은 그리지 않는다(쪽 gap-6 한 칸을 먹으니).
            <div data-testid="warnings" className="flex flex-col gap-2">
              {warnings.map((view) => (
                <PageInfo
                  key={view.line}
                  icon={<PageInfoIcon />}
                  data-testid="warning"
                  data-warning={view.line}
                >
                  {IR_TEXT.warnings[view.line](view.count)}
                </PageInfo>
              ))}
            </div>
          )}

          <Tabs
            value={tab}
            onValueChange={(value) => api.guard(() => setTab(value as Tab))}
          >
            <TabsList aria-label={words.tabs.label}>
              {TABS.map((value) => (
                <TabsTrigger key={value} value={value}>
                  {words.tabs[value]}
                </TabsTrigger>
              ))}
            </TabsList>
            {/* 탭을 바꾸면 몸이 새로 붙어 비친다(밴드 IRW1b J3 — 영문번역 PartTabs 꼴). 탭 단추는 밖이라 ←/→ 초점은 그대로 */}
            <TabsContent value="shortlist" className="mt-4">
              <div className="gw-m-fade">
                {notRun ?
                  <NotRun />
                : <ShortlistCard
                    result={result}
                    researchReady={researchReady}
                  />
                }
              </div>
            </TabsContent>
            <TabsContent value="impact" className="mt-4">
              <div className="gw-m-fade">
                {notRun ?
                  <NotRun />
                : <ImpactCard result={result} />}
              </div>
            </TabsContent>
            <TabsContent value="pathway" className="mt-4">
              <div className="gw-m-fade">
                {notRun ?
                  <NotRun />
                : <PathwayCard result={result} />}
              </div>
            </TabsContent>
          </Tabs>

          {downloadsOpen && files !== null && (
            <DownloadDialog
              testId="download-dialog"
              title={downloadWords.title}
              closeLabel={downloadWords.close}
              helpLabel={downloadWords.fileMissingLabel}
              failedText={common.downloadFailed}
              busyLabel={downloadWords.downloading}
              files={files}
              onClose={() => setDownloadsOpen(false)}
              returnFocus={() => downloadsOpener.current}
            />
          )}
          {(pendingLeave !== null || leave?.pending === true) && (
            <LeaveDialog
              onStay={() => {
                if (pendingLeave !== null) {
                  stayed.current = true;
                  setPendingLeave(null);
                } else leave?.reset();
              }}
              onCloseAutoFocus={(event) => {
                if (!stayed.current) return;
                stayed.current = false;
                event.preventDefault();
                const root = body.current;
                (
                  root?.querySelector<HTMLElement>('[data-edit-first]') ??
                  root?.querySelector<HTMLElement>('[data-edit-field]')
                )?.focus();
              }}
              onLeave={() => {
                if (pendingLeave !== null) {
                  const action = pendingLeave;
                  setPendingLeave(null);
                  setEditing(null);
                  action();
                } else leave?.proceed();
              }}
            />
          )}
        </div>
      </TooltipProvider>
    </EditContext.Provider>
  );
}

/** 작은 글 400 12(시안 g-small — 카드 머리 sub·표 아랫글·결과 엑셀 칸 두 줄, 디자인 대조 W6). */
const SMALL = 'text-style-pre-caption-03 text-text-tertiary';

/** 칸마다 70ms 씩 늦게 떠오른다(entities/translation/ui/StatTiles.tsx:12-14 의 rise 를 옮겨 적음 — 밴드 IRW1b J3). */
const rise = (order: number) =>
  ({ '--gw-m-delay': `${order * 70}ms` }) as CSSProperties;

/** 숫자 카드(시안 g-stat — 디자인 대조 W5, 데이터 검증 DV-04 수 칸과 같은 꼴): 라벨 500 14 · 수 700 28(pre-display-03) · 단위 500 14. 수는 CountUp 800ms. */
function Stat({
  order,
  id,
  label,
  value,
  unit,
  sub = null,
}: {
  order: number;
  id: string;
  label: string;
  value: number | null;
  unit: string;
  sub?: string | null;
}) {
  return (
    <Card
      className="gw-m-rise flex flex-col gap-1"
      style={rise(order)}
      data-stat={id}
    >
      <span className="text-style-pre-body-05 text-text-tertiary">{label}</span>
      <span
        data-testid={`stat-${id}`}
        className="text-style-pre-display-03 tabular-nums text-text-primary"
      >
        {value === null ?
          dash
        : <>
            <CountUp value={value} durationMs={800} />
            <small className="ml-0.5 text-style-pre-body-05 text-text-tertiary">
              {unit}
            </small>
          </>
        }
      </span>
      {sub !== null && (
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {sub}
        </span>
      )}
    </Card>
  );
}

function NotRun() {
  return (
    <Card className="flex flex-wrap items-center justify-between gap-4">
      <p
        data-testid="not-run"
        className="m-0 text-style-pre-body-06 text-text-tertiary"
      >
        {words.notRun}
      </p>
    </Card>
  );
}

const MUTED = 'text-text-quaternary';

/** 모델 글 칸: 글자 그대로(줄바꿈 지킴), null 은 「–」. */
const text = (value: Cell) =>
  value === null ?
    <span className={MUTED}>{dash}</span>
  : <span className="whitespace-pre-wrap">{value}</span>;

/** 가치사슬 활동 한 덩이(판 IR-04_r2 .d-acts .a-w — 2줄 말줄임). 잘린 덩이만 공용 툴팁에 전체 글:
 *  잘림은 마우스를 올려 열릴 때 그 자리 높이로 잰다(scrollHeight > clientHeight) — 칸 폭이 바뀌어도 그때 값.
 *  키보드(sid:MARC-ISSUE-536, 밴드 IRW11 Q12): 덩이마다 ResizeObserver(없으면 붙을 때 한 번)로 잘림을 재어 잘린 덩이만 tabIndex 0 —
 *  초점이 오면 같은 툴팁이 열린다(여는 판정은 위와 같다). */
function Activity({ label }: { label: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [clipped, setClipped] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el === null) return;
    const measure = () => setClipped(el.scrollHeight > el.clientHeight);
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [label]);
  return (
    <Tooltip
      open={open}
      onOpenChange={(next) => {
        const el = ref.current;
        setOpen(next && el !== null && el.scrollHeight > el.clientHeight);
      }}
    >
      <TooltipTrigger asChild>
        <span
          ref={ref}
          data-activity=""
          tabIndex={clipped ? 0 : undefined}
          className="line-clamp-2"
        >
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[320px]">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

/** 가치사슬 활동 칸(2-1·2-2, sid:MARC-ENT-558): 활동마다 한 덩이, 덩이 사이 4 · 빈 목록 회색 「–」. */
const activitiesCell = (activities: readonly string[]) => (
  <div data-activities="" className={ACTIVITIES_CELL}>
    {activities.length === 0 ?
      <span className={MUTED}>{dash}</span>
    : <TooltipProvider>
        {activities.map((label, index) => (
          <Activity key={index} label={label} />
        ))}
      </TooltipProvider>
    }
  </div>
);

/** 가치사슬 활동 칸 몸(판 mod-r1 .d-acts min 180 · max 240 · 줄바꿈 허용 · 덩이 사이 space-1). 위아래 12 는 감싸개 RESULT_TABLE 의 py-3. */
const ACTIVITIES_CELL =
  'flex min-w-[180px] max-w-[240px] flex-col gap-1 whitespace-normal';

/** 결과 표 셋(2-1·2-2·1-1) 공용 DataTable 감싸개: 머리 한 줄 · 데이터 줄 칸 위아래 12·위 붙임(공용에 칸 클래스 계약이 없어 감싸개로 — 데이터 검증 DVW1 ROW_PADDING 꼴).
 *  tr[data-row] 로 거른다 — 빈 줄·스켈레톤 줄에는 새지 않게.
 *  한국어 칸은 낱말 사이에서만 꺾임(시안 키트 .e-table--wrap td.w keep-all, 433 ①). 주소는 a·span 의 break-all 이 제 값. */
const RESULT_TABLE =
  '[&_th]:whitespace-nowrap [&_tr[data-row]>td]:py-3 [&_tr[data-row]>td]:align-top [&_td]:break-keep';
/** 공용 DataTable 의 빈 줄 몸(칸 꼴은 옛 사본 CELL 과 같은 자리·선·글). */
const EMPTY_LINE =
  'box-border min-h-14 border-0 border-b border-solid border-border-tertiary px-4 py-3 text-style-pre-body-06 text-text-secondary';

function CardHead({
  title,
  sub,
  cells,
  children,
}: {
  title: string;
  sub?: string;
  /** 표 거르기 전 전체 칸의 주소 목록(배지 「고친 칸 n · 저장 HH:MM」 — Q10). */
  cells?: readonly (readonly string[])[];
  children?: ReactNode;
}) {
  const api = useEdit();
  const summary =
    api.readOnly || cells === undefined ? null : editSummary(cells, api.edits);
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
        {title}
        {sub !== undefined && <span className={cn('ml-2', SMALL)}>{sub}</span>}
        {summary !== null && summary.latest !== null && (
          <Badge variant="grey" className="ml-2" data-testid="edited-badge">
            {editWords.badge(
              summary.count,
              editedClock(summary.latest.editedAt),
            )}
          </Badge>
        )}
      </h3>
      {children}
    </div>
  );
}

function Foot({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <p data-testid={testId} className={cn('m-0', SMALL)}>
      {children}
    </p>
  );
}

/** 토픽 고르기(「토픽 전체」 + 2부 토픽 차례). */
function TopicSelect({
  result,
  value,
  onChange,
}: {
  result: MaterialityResult;
  value: string;
  onChange(value: string): void;
}) {
  const topics =
    result.part2.status === 'done' ?
      result.part2.topics.map((topic) => topic.topic)
    : [];
  return (
    <FilterSelect
      aria-label={words.topicLabel}
      value={value}
      options={[
        { value: ALL_TOPICS, label: words.topicAll },
        ...topics.map((topic) => ({ value: topic, label: topic })),
      ]}
      onChange={onChange}
    />
  );
}

/** 빈 표 몸(표 머리 그대로, 몸 자리에 이것만). 거르기로 비면 「조건에 맞는 영향이 없어요」+[거르기 풀기],
 *  거르기 없이 비면 「찾은 영향이 없어요」(단추 0 — 6c 10-26, 덧붙임 B3). 2-1·2-2 다 DataTable empty 로. */
function FilteredEmptyBody({ onClear }: { onClear: (() => void) | null }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span>{onClear === null ? words.noImpacts : words.filteredEmpty}</span>
      {onClear !== null && (
        <Button variant="outlineGrey" shape="round" size="sm" onClick={onClear}>
          {words.clearFilter}
        </Button>
      )}
    </div>
  );
}

/** 「찾은 글 없이 정함」 배지(영향 정의 끝). */
const missingBadge = (missing: boolean) =>
  missing && (
    <Badge variant="grey" className="ml-2" data-testid="research-missing">
      {words.researchMissing}
    </Badge>
  );

/** 상자 탭(전체·긍정·부정 / 전체·리스크·기회). */
function KindTabs<K extends string>({
  label,
  value,
  items,
  onChange,
}: {
  label: string;
  value: K;
  items: readonly { value: K; label: string }[];
  onChange(value: K): void;
}) {
  return (
    <Tabs
      value={value}
      onValueChange={(next) => onChange(next as K)}
      variant="box"
    >
      <TabsList aria-label={label}>
        {items.map((item) => (
          <TabsTrigger key={item.value} value={item.value}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

type ImpactKind = 'all' | 'positive' | 'negative';

/** 2-1 표 줄: 영향 줄 하나 또는 「정하지 못함」 서브토픽 하나(「전체」 탭 끝, 흐림). */
type ImpactRow =
  | { kind: 'line'; no: number; line: ImpactLine }
  | { kind: 'undecided'; no: number; ref: SubtopicRef };

/** 정하지 못함 줄 칸: 공용 td 가 글 색을 직접 가져 tr 색이 내려오지 않으니 칸 글을 흐린 span 으로. */
const muted = (content: ReactNode) => <span className={MUTED}>{content}</span>;

/** [고치기] 칸(판 .d-editbtn — sm·outlineBlack·round, 연필 + 「고치기」). 고침을 못 읽으면 열이 없다(Q7). */
function EditButton({ tab, no }: { tab: EditTab; no: number }) {
  const api = useEdit();
  return (
    <Button
      variant="outlineBlack"
      shape="round"
      size="sm"
      className="gap-1"
      data-edit-button={`${tab}-${no}`}
      onClick={() => api.open(tab, no)}
    >
      <PenIcon aria-hidden className="size-4" />
      {editWords.open}
    </Button>
  );
}

/** 「고치기」 열(머리 글 없음 — 이름만, 판 th.d-act). 편집 중엔 열이 숨는다. */
const editColumn = <Row extends RowData>(
  tab: EditTab,
  noOf: (row: Row) => number | null,
  width?: number,
): DataTableColumnDef<Row> => ({
  id: 'edit',
  header: () => <span className="sr-only">{editWords.column}</span>,
  enableSorting: false,
  meta: width === undefined ? {} : { width },
  cell: ({ row: { original } }) => {
    const no = noOf(original);
    return no === null ? null : <EditButton tab={tab} no={no} />;
  },
});

/** 칸 하나: 편집 중이면 글 상자(위 붙임 — 줄 칸 pt 를 되돌림), 아니면 글 + 고친 칸 연필. */
function FieldCell({
  tab,
  no,
  field,
  label,
  first = false,
  pointers,
  boxClass,
  markClass,
  children,
}: {
  tab: EditTab;
  no: number;
  field: EditField;
  label: string;
  first?: boolean;
  pointers: readonly string[];
  boxClass?: string;
  markClass?: string;
  children: ReactNode;
}) {
  const api = useEdit();
  if (isEditing(api, tab, no))
    return (
      <EditBox
        field={field}
        label={label}
        first={first}
        className={cn(EDIT_CELL, boxClass)}
      />
    );
  const edit = api.readOnly ? null : editOfCell(pointers, api.edits);
  return (
    <EditedMark edit={edit} className={edit === null ? undefined : markClass}>
      {children}
    </EditedMark>
  );
}

/** 편집 줄의 글 상자 칸: 줄 칸 위 21(12 + 9 — 고치지 않는 칸 글 자리, 감싸개)을 되돌려 위 12 에 붙임. */
const EDIT_CELL = '-mt-[9px]';

/** 컨텍스트 요약 편집(2-1 칸 안·2-2 펼침): 항목마다 「n)」 + 글 상자, 고칠 수 없는 요약은 회색 글(e6 ⑤). */
function SummaryBoxes({
  summaries,
  fields,
}: {
  summaries: readonly string[];
  fields: readonly (EditField | null)[];
}) {
  if (summaries.length === 0) return <span className={MUTED}>{dash}</span>;
  return (
    <div className="flex flex-col gap-2">
      {summaries.map((summary, index) => {
        const field = fields[index] ?? null;
        return (
          <div
            key={index}
            className="flex items-start gap-2"
            data-summary-edit=""
          >
            <span className="shrink-0 pt-[9px] text-style-pre-caption-03 text-text-tertiary">
              {`${index + 1})`}
            </span>
            {field === null ?
              <span className={cn('whitespace-pre-wrap pt-[9px]', MUTED)}>
                {summary}
              </span>
            : <EditBox
                field={field}
                label={editWords.summary(index + 1)}
                className="flex-1"
              />
            }
          </div>
        );
      })}
    </div>
  );
}

/** 요약 글(보통 때): 「n) 글」 줄마다. */
const summaryLines = (summaries: readonly string[]) =>
  summaries.length === 0 ?
    muted(dash)
  : summaries.map((summary, index) => (
      <span key={index} className="block whitespace-pre-wrap">
        {`${index + 1}) `}
        {summary}
      </span>
    ));

function ImpactDefinitionCell({ line }: { line: ImpactLine }) {
  const api = useEdit();
  const field = impactFields(api.result, line).definition;
  return (
    <FieldCell
      tab="impact"
      no={line.no}
      field={field}
      label={editWords.definition}
      first
      pointers={[field.pointer]}
    >
      {text(line.definition)}
      {missingBadge(line.researchMissing)}
    </FieldCell>
  );
}

function ImpactSummaryCell({ line }: { line: ImpactLine }) {
  const api = useEdit();
  if (isEditing(api, 'impact', line.no))
    return (
      <div className={EDIT_CELL}>
        <SummaryBoxes
          summaries={line.summaries}
          fields={impactFields(api.result, line).summaries}
        />
      </div>
    );
  const edit =
    api.readOnly ? null : (
      editOfCell(
        summaryCellPointers(
          api.result,
          line,
          'impact',
          lineContext(api.result, line, 'impact'),
        ),
        api.edits,
      )
    );
  return <EditedMark edit={edit}>{summaryLines(line.summaries)}</EditedMark>;
}

/** 2-1 열(IRW4 — table-fixed: 짧은 칸은 판 폭 56·120·176·72(6c D2, IRW6), 영향 정의·요약은 남은 폭을 반반 — 판 58:42 는 6c 거리).
 *  가치사슬 활동(IRW10)은 판 max 240 을 col 폭으로(fixed 라 min·max 대신 한 값 — 활동 글이 길면 판 auto 표도 240 에 닿는다). */
/** 「고치기」 열 폭(fixed 표 — sm 단추 「연필 고치기」 약 80 + 칸 16·16). */
const EDIT_WIDTH = 112;

const IMPACT_COLUMNS: DataTableColumnDef<ImpactRow>[] = [
  {
    id: 'no',
    header: words.impact.head.no,
    enableSorting: false,
    meta: { width: 56 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <span className="tabular-nums">{row.no}</span>
      : <span className={cn(MUTED, 'tabular-nums')}>{row.no}</span>,
  },
  {
    id: 'topic',
    header: words.impact.head.topic,
    enableSorting: false,
    meta: { width: 120 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ? row.line.topic : muted(row.ref.topic),
  },
  {
    id: 'subtopic',
    header: words.impact.head.subtopic,
    enableSorting: false,
    meta: { width: 176 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ? row.line.subtopic : muted(row.ref.subtopic),
  },
  {
    id: 'activities',
    header: words.impact.head.activities,
    enableSorting: false,
    meta: { width: 240 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ? activitiesCell(row.line.activities) : muted(dash),
  },
  {
    id: 'definition',
    header: words.impact.head.definition,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <ImpactDefinitionCell line={row.line} />
      : muted(words.undecidedCell),
  },
  {
    id: 'type',
    header: words.impact.head.type,
    enableSorting: false,
    meta: { width: 72 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'undecided' || row.line.type === null ?
        muted(dash)
      : <Badge variant={TONE_BADGE[row.line.tone]}>{row.line.type}</Badge>,
  },
  {
    id: 'summary',
    header: words.impact.head.summary,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'undecided' ?
        muted(dash)
      : <ImpactSummaryCell line={row.line} />,
  },
];
/** 2-1 「고치기」 열(fixed — 단추 폭 + 칸 16·16). */
const IMPACT_EDIT_COLUMNS: DataTableColumnDef<ImpactRow>[] = [
  ...IMPACT_COLUMNS,
  editColumn<ImpactRow>(
    'impact',
    (row) => (row.kind === 'line' ? row.no : null),
    EDIT_WIDTH,
  ),
];

/** 편집 줄 감싸개(2-1·1-1·2-2 공통): 편집 줄 칸 위 21(고치지 않는 칸 글을 상자 글과 맞춤 — 판 :32)·아래 선 0, 단추 줄 바탕(판 .d-rowact). */
const EDITING_TABLE = cn(
  '[&_tr[data-editing]>td]:pt-[21px] [&_tr[data-editing]>td]:border-b-0',
  '[&_tr[data-row=edit-actions]>td]:bg-background-secondary',
  // 단추 줄 위아래 12(판 .d-rowact height:auto — 공용 칸 h-14 56 을 풀어 12 + 단추 28 + 12, 밴드 IRW11b m1).
  '[&_tr[data-row=edit-actions]>td]:h-auto',
);

function ImpactCard({ result }: { result: MaterialityResult }) {
  const api = useEdit();
  const [topic, setTopic] = useState(ALL_TOPICS);
  const [kind, setKind] = useState<ImpactKind>('all');
  const lines = impactLines(result);
  const inTopic = (line: { topic: string }) =>
    topic === ALL_TOPICS || line.topic === topic;
  const topicLines = lines.filter(inTopic);
  const shown = topicLines.filter(
    (line: ImpactLine) => kind === 'all' || line.tone === kind,
  );
  // 정하지 못함 줄의 No 는 거르기 전 차례(2-1 줄 뒤 이어 번호) — 토픽으로 걸러도 「전체」 와 같은 번호.
  const undecidedRows =
    kind === 'all' ?
      undecidedImpact(result)
        .map((ref, index) => ({ ref, no: lines.length + index + 1 }))
        .filter(({ ref }) => inTopic(ref))
    : [];
  const filtered = topic !== ALL_TOPICS || kind !== 'all';
  const count = (tone: ImpactTone) =>
    topicLines.filter((line) => line.tone === tone).length;
  const table = useDataTable<ImpactRow>({
    data: [
      ...shown.map((line): ImpactRow => ({ kind: 'line', no: line.no, line })),
      ...undecidedRows.map(({ ref, no }): ImpactRow => ({
        kind: 'undecided',
        no,
        ref,
      })),
    ],
    columns:
      api.readOnly || api.editing !== null ?
        IMPACT_COLUMNS
      : IMPACT_EDIT_COLUMNS,
    getRowId: (row) =>
      `${row.kind === 'line' ? 'line' : 'undecided'}-${row.no}`,
  });
  const cells = lines.flatMap((line) => [
    [rowPointer(line.at, 'impact', 'impactDefinition')],
    summaryCellPointers(
      result,
      line,
      'impact',
      lineContext(result, line, 'impact'),
    ),
  ]);
  const editingRow = (row: ImpactRow) =>
    row.kind === 'line' && isEditing(api, 'impact', row.no);
  return (
    <Card className="flex flex-col gap-4" data-card="impact">
      <CardHead title={words.impact.title} sub={words.impact.sub} cells={cells}>
        <div className="flex flex-wrap items-center gap-3">
          <TopicSelect
            result={result}
            value={topic}
            onChange={(next) => api.guard(() => setTopic(next))}
          />
          <KindTabs<ImpactKind>
            label={words.impact.kindLabel}
            value={kind}
            onChange={(next) => api.guard(() => setKind(next))}
            items={[
              { value: 'all', label: words.impact.all(topicLines.length) },
              {
                value: 'positive',
                label: words.impact.positive(count('positive')),
              },
              {
                value: 'negative',
                label: words.impact.negative(count('negative')),
              },
            ]}
          />
        </div>
      </CardHead>
      <DataTable
        table={table}
        layout="fixed"
        aria-label={words.impact.title}
        className={cn(RESULT_TABLE, EDITING_TABLE)}
        rowAttrs={(row) => ({
          'data-row': row.kind === 'line' ? 'impact' : 'undecided',
          'data-no': String(row.no),
          'data-editing': editingRow(row) ? '' : undefined,
        })}
        rowTone={(row) => (editingRow(row) ? 'subtle' : undefined)}
        renderExpanded={(row) =>
          editingRow(row) ? <EditActions note={editWords.rowNote} /> : null
        }
        expandedRowAttrs={() => ({ 'data-row': 'edit-actions' })}
        empty={
          <div data-testid="filtered-empty" className={EMPTY_LINE}>
            <FilteredEmptyBody
              onClear={
                filtered ?
                  () => {
                    setTopic(ALL_TOPICS);
                    setKind('all');
                  }
                : null
              }
            />
          </div>
        }
      />
      <Foot>{words.impact.foot}</Foot>
    </Card>
  );
}

type PathwayKind = 'all' | 'risk' | 'opportunity';

/** 2-2 표 줄: 경로 줄 하나 또는 「정하지 못함」 서브토픽 하나(「전체」 탭 끝, 흐림). */
type PathwayRow =
  | { kind: 'line'; no: number; line: PathwayLine }
  | { kind: 'undecided'; no: number; ref: SubtopicRef };

/** 2-2 토픽·서브토픽 머리: 바람 폭 100 을 최소 폭으로도(머리 글 덩이 68 + 공용 th 칸 16·16). 가치사슬 활동 열(IRW10)로
 *  1280 에서 표가 카드보다 넓어지면 auto 표가 이 둘을 글 최소 폭(약 80)까지 줄여 낱말이 꺾인다(IRD1 흠) — 감독 판단 IRW10 B. */
const narrowHead = (label: string) =>
  function NarrowHead() {
    return <span className="block min-w-[68px]">{label}</span>;
  };

/** 2-2 열(auto 짜임 — 글이 칸 폭을 정함. 토픽·서브토픽만 meta.width 100 = 공용 th 의 바람 폭, 낱말이 길면 더 넓음 — 6c D3, IRW6).
 *  정하지 못함 줄은 칸마다 흐린 span(2-1 꼴). */
const PATHWAY_COLUMNS: DataTableColumnDef<PathwayRow>[] = [
  {
    id: 'no',
    header: words.pathway.head.no,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <span className="tabular-nums">{row.no}</span>
      : <span className={cn(MUTED, 'tabular-nums')}>{row.no}</span>,
  },
  {
    id: 'topic',
    header: narrowHead(words.pathway.head.topic),
    enableSorting: false,
    meta: { width: 100 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ? row.line.topic : muted(row.ref.topic),
  },
  {
    id: 'subtopic',
    header: narrowHead(words.pathway.head.subtopic),
    enableSorting: false,
    meta: { width: 100 },
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ? row.line.subtopic : muted(row.ref.subtopic),
  },
  {
    id: 'activities',
    header: words.pathway.head.activities,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ? activitiesCell(row.line.activities) : muted(dash),
  },
  {
    id: 'definition',
    header: words.pathway.head.definition,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <PathwayTextCell line={row.line} cell="definition" first>
          {text(row.line.definition)}
          {missingBadge(row.line.researchMissing)}
        </PathwayTextCell>
      : muted(words.undecidedCell),
  },
  {
    id: 'kind',
    header: words.pathway.head.kind,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'undecided' || row.line.type === null ?
        muted(dash)
      : <Badge variant={KIND_BADGE[row.line.kind]}>{row.line.type}</Badge>,
  },
  {
    id: 'riskType',
    header: words.pathway.head.riskType,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'undecided' || row.line.riskType === null ?
        muted(dash)
      : row.line.riskType,
  },
  {
    id: 'driver',
    header: words.pathway.head.driver,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <PathwayTextCell line={row.line} cell="driver">
          {text(row.line.driver)}
        </PathwayTextCell>
      : muted(dash),
  },
  {
    id: 'business',
    header: words.pathway.head.business,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <PathwayTextCell line={row.line} cell="business">
          {text(row.line.business)}
        </PathwayTextCell>
      : muted(dash),
  },
  {
    id: 'financial',
    header: words.pathway.head.financial,
    enableSorting: false,
    cell: ({ row: { original: row } }) =>
      row.kind === 'line' ?
        <PathwayTextCell line={row.line} cell="financial">
          {text(row.line.financial)}
        </PathwayTextCell>
      : muted(dash),
  },
];

/** 2-2 「고치기」 열(auto — 단추 폭 그대로). */
const PATHWAY_EDIT_COLUMN = editColumn<PathwayRow>('pathway', (row) =>
  row.kind === 'line' ? row.no : null,
);

/** 2-2 펼침 꺾쇠 열(규칙 5 — 판 e6 11-08, 개정 2 첫 열): 머리 글 없음 · 폭 40 가운데 · 앱 꺾쇠 16 tertiary · 열림은 같은 아이콘 180° ·
 *  aria-hidden 장식(이름·상태는 줄의 rowLabel·aria-expanded, 누름은 줄이 받음 — 두 번 토글 0) · 편집 중엔 흐림(줄 누름이 막힘) ·
 *  정하지 못함 줄은 빈 칸. 돌림은 220ms(움직임 줄임이면 없음). 칸 여백 12 는 감싸개 PATHWAY_TABLE 이 :has 로. */
const pathwayExpandColumn = (
  opened: (row: PathwayRow) => boolean,
  editing: boolean,
): DataTableColumnDef<PathwayRow> => ({
  id: 'expand',
  header: () => <span data-col="expand" />,
  enableSorting: false,
  // 가운데는 칸 안 span 이 맡는다(meta.align 은 머리 칸 꼴을 바꿔 2-1 과 한 꼴이 깨짐 — N4).
  meta: { width: 40 },
  cell: ({ row: { original: row } }) =>
    row.kind === 'line' ?
      <span
        data-expand-mark={opened(row) ? 'open' : 'closed'}
        data-dim={editing ? '' : undefined}
        className="flex h-[1lh] items-center justify-center"
      >
        <ChevronDownIcon
          aria-hidden
          className={cn(
            'size-4',
            editing ? 'text-text-quaternary' : 'text-text-tertiary',
            opened(row) && 'rotate-180',
            'motion-safe:transition-transform motion-safe:duration-[220ms] motion-safe:ease-[cubic-bezier(0.22,1,0.36,1)]',
          )}
        />
      </span>
    : null,
});

const PATHWAY_LABEL = {
  definition: editWords.definition,
  driver: words.pathway.head.driver,
  business: words.pathway.head.business,
  financial: words.pathway.head.financial,
} as const;

/** 2-2 글 칸(판 mod-r1 :45-48): 글 칸 ≥120 · 연필 칸 ≥200 · 편집 중 글 상자 218(+칸 32 = 250). */
function PathwayTextCell({
  line,
  cell,
  first = false,
  children,
}: {
  line: PathwayLine;
  cell: keyof typeof PATHWAY_LABEL;
  first?: boolean;
  children: ReactNode;
}) {
  const api = useEdit();
  const field = pathwayFields(api.result, line).rows[cell];
  return (
    <FieldCell
      tab="pathway"
      no={line.no}
      field={field}
      label={PATHWAY_LABEL[cell]}
      first={first}
      pointers={[field.pointer]}
      boxClass="min-w-[218px]"
      markClass="min-w-[168px]"
    >
      <div className="min-w-[88px]">{children}</div>
    </FieldCell>
  );
}

/** 2-2 펼친 요약(보통 때 — 고친 칸 연필은 이 덩이에). */
function PathwaySummary({ line }: { line: PathwayLine }) {
  const api = useEdit();
  const edit =
    api.readOnly ? null : (
      editOfCell(
        summaryCellPointers(
          api.result,
          line,
          'pathway',
          lineContext(api.result, line, 'pathway'),
        ),
        api.edits,
      )
    );
  return (
    <div className="rounded-component bg-background-primary p-3">
      <EditedMark edit={edit}>
        <b className="text-style-pre-caption-01 text-text-tertiary">
          {words.summaryLabel}
        </b>
        {line.summaries.length === 0 ?
          <span className={cn('block', MUTED)}>{dash}</span>
        : line.summaries.map((summary, index) => (
            <span key={index} className="block whitespace-pre-wrap">
              {`${index + 1}) `}
              {summary}
            </span>
          ))
        }
      </EditedMark>
    </div>
  );
}

/** 2-2 편집 줄 펼침(판 IR-04a r3 .d-exp + .d-rowact 한 칸): 요약 항목마다 상자 · 그 아래 [취소][저장](양 끝 sticky). */
function PathwayEditExpand({ line }: { line: PathwayLine }) {
  const api = useEdit();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        <span className="sticky left-4 w-fit text-style-pre-caption-01 text-text-tertiary">
          {words.summaryLabel}
        </span>
        <div className="max-w-[720px]">
          <SummaryBoxes
            summaries={line.summaries}
            fields={pathwayFields(api.result, line).summaries}
          />
        </div>
      </div>
      <EditActions note={editWords.rowNote} sticky />
    </div>
  );
}

/** 2-2 「고치기」 열은 표를 밀어도 오른쪽에 붙음(판 mod-r1 :27-28 .d-act — 공용에 열 클래스 계약이 없어 마지막 칸 선택자로). 편집 중엔 열이 없어 달지 않는다. */
const STICKY_EDIT = cn(
  '[&_th:last-child]:sticky [&_th:last-child]:right-0 [&_th:last-child]:z-[1]',
  '[&_tr:not([data-expanded-row])>td:last-child]:sticky [&_tr:not([data-expanded-row])>td:last-child]:right-0 [&_tr:not([data-expanded-row])>td:last-child]:z-[1]',
  '[&_tr:not([data-expanded-row])>td:last-child]:whitespace-nowrap [&_tr:not([data-expanded-row])>td:last-child]:bg-background-primary',
  '[&_th:last-child]:[box-shadow:inset_1px_0_0_theme(colors.border.tertiary),0_0_6px_rgba(0,0,0,0.12)] [&_th:last-child]:[clip-path:inset(0_0_0_-8px)]',
  '[&_tr:not([data-expanded-row])>td:last-child]:[box-shadow:inset_1px_0_0_theme(colors.border.tertiary),0_0_6px_rgba(0,0,0,0.12)] [&_tr:not([data-expanded-row])>td:last-child]:[clip-path:inset(0_0_0_-8px)]',
  // 누름 줄 hover·초점 바탕이 붙은 칸에서 끊기지 않게(밴드 IRW13 — 붙은 칸 바탕 primary 를 속성 하나 더로 이김).
  '[&_tr[tabindex]:hover>td:last-child]:bg-background-secondary [&_tr[tabindex]:focus-visible>td:last-child]:bg-background-secondary',
);

/** 2-2 감싸개: 결과 표 꼴 + 펼친 줄과 요약 줄은 한 덩이.
 *  펼친 줄 아래 선 0 — 공용 td 의 border-b((0,1,0))를 열린 줄 속성 선택자로 이김.
 *  요약 칸 위 0 — 공용 펼침 칸 py-3 과 감싸개 [&_tr[data-row]>td]:py-3((0,2,2))를 속성 둘((0,3,2))로 이김(아래 12 는 그대로). */
const PATHWAY_TABLE = cn(
  RESULT_TABLE,
  '[&_tr[aria-expanded=true]>td]:border-b-0',
  '[&_tr[data-expanded-row][data-row]>td]:pt-0',
  EDITING_TABLE,
  '[&_tr[data-row=pathway-edit]>td]:bg-background-secondary',
  // 꺾쇠 열 폭 40 = 12 + 16 + 12(공용 칸 px-4 를 :has 로 이김 — 밴드 IRW13).
  '[&_th:has(>[data-col=expand])]:px-3 [&_td:has(>[data-expand-mark])]:px-3',
  // 펼친 줄 hover·초점 바탕이 그 요약 줄까지 한 덩이(밴드 IRW13 — 스크린샷 IRW13.out/3-open-hover).
  '[&_tr[tabindex][aria-expanded=true]:hover+tr[data-expanded-row]>td]:bg-background-secondary',
  '[&_tr[tabindex][aria-expanded=true]:focus-visible+tr[data-expanded-row]>td]:bg-background-secondary',
);

function PathwayCard({ result }: { result: MaterialityResult }) {
  const api = useEdit();
  const [topic, setTopic] = useState(ALL_TOPICS);
  const [kind, setKind] = useState<PathwayKind>('all');
  const [open, setOpen] = useState<number | null>(null);
  const lines = pathwayLines(result);
  const inTopic = (line: { topic: string }) =>
    topic === ALL_TOPICS || line.topic === topic;
  const topicLines = lines.filter(inTopic);
  const shown = topicLines.filter(
    (line: PathwayLine) => kind === 'all' || line.kind === kind,
  );
  // 정하지 못함 줄의 No 는 거르기 전 차례(2-2 줄 뒤 이어 번호).
  const undecidedRows =
    kind === 'all' ?
      undecidedPathway(result)
        .map((ref, index) => ({ ref, no: lines.length + index + 1 }))
        .filter(({ ref }) => inTopic(ref))
    : [];
  const filtered = topic !== ALL_TOPICS || kind !== 'all';
  const count = (value: FinancialKind) =>
    topicLines.filter((line) => line.kind === value).length;
  const editingRow = (row: PathwayRow) =>
    row.kind === 'line' && isEditing(api, 'pathway', row.no);
  /** 편집 줄 펼침은 늘 열림(Q14). */
  const opened = (row: PathwayRow) =>
    row.kind === 'line' && (open === row.no || editingRow(row));
  const table = useDataTable<PathwayRow>({
    data: [
      ...shown.map((line): PathwayRow => ({ kind: 'line', no: line.no, line })),
      ...undecidedRows.map(({ ref, no }): PathwayRow => ({
        kind: 'undecided',
        no,
        ref,
      })),
    ],
    // 꺾쇠 열은 두 짜임 다 첫 열(No 앞 — 개정 2: 끝 열은 1440 에서 붙은 고치기 칸 뒤 스크롤 끝에 가려짐).
    columns: [
      pathwayExpandColumn(opened, api.editing !== null),
      ...PATHWAY_COLUMNS,
      ...(api.readOnly || api.editing !== null ? [] : [PATHWAY_EDIT_COLUMN]),
    ],
    getRowId: (row) =>
      `${row.kind === 'line' ? 'line' : 'undecided'}-${row.no}`,
  });
  const cells = lines.flatMap((line) => {
    const rows = pathwayFields(result, line).rows;
    return [
      [rows.definition.pointer],
      [rows.driver.pointer],
      [rows.business.pointer],
      [rows.financial.pointer],
      summaryCellPointers(
        result,
        line,
        'pathway',
        lineContext(result, line, 'pathway'),
      ),
    ];
  });
  return (
    <Card className="flex flex-col gap-4" data-card="pathway">
      <CardHead
        title={words.pathway.title}
        sub={words.pathway.sub}
        cells={cells}
      >
        <div className="flex flex-wrap items-center gap-3">
          <TopicSelect
            result={result}
            value={topic}
            onChange={(next) => api.guard(() => setTopic(next))}
          />
          <KindTabs<PathwayKind>
            label={words.pathway.kindLabel}
            value={kind}
            onChange={(next) => api.guard(() => setKind(next))}
            items={[
              { value: 'all', label: words.pathway.all(topicLines.length) },
              { value: 'risk', label: words.pathway.risk(count('risk')) },
              {
                value: 'opportunity',
                label: words.pathway.opportunity(count('opportunity')),
              },
            ]}
          />
        </div>
      </CardHead>
      <DataTable
        table={table}
        aria-label={words.pathway.title}
        className={cn(
          PATHWAY_TABLE,
          !api.readOnly && api.editing === null && STICKY_EDIT,
        )}
        rowAttrs={(row) => ({
          'data-row': row.kind === 'line' ? 'pathway' : 'undecided',
          'data-no': String(row.no),
          'data-editing': editingRow(row) ? '' : undefined,
        })}
        rowTone={(row) => (editingRow(row) ? 'subtle' : undefined)}
        rowExpanded={(row) => (row.kind === 'line' ? opened(row) : undefined)}
        onClickRow={(row) => {
          if (row.kind === 'line')
            setOpen((now) => (now === row.no ? null : row.no));
        }}
        // 편집 중엔 다른 줄 누름 0(Q14).
        isRowClickable={(row) => row.kind === 'line' && api.editing === null}
        rowLabel={(row) =>
          row.kind === 'line' ?
            words.pathway.rowLabel(row.no, row.line.subtopic)
          : ''
        }
        renderExpanded={(row) =>
          row.kind !== 'line' || !opened(row) ? null
          : editingRow(row) ? <PathwayEditExpand line={row.line} />
          : <PathwaySummary line={row.line} />
        }
        expandedRowAttrs={(row) => ({
          'data-row': editingRow(row) ? 'pathway-edit' : 'pathway-summary',
          'data-no': String(row.no),
        })}
        empty={
          <div data-testid="filtered-empty" className={EMPTY_LINE}>
            <FilteredEmptyBody
              onClear={
                filtered ?
                  () => {
                    setTopic(ALL_TOPICS);
                    setKind('all');
                  }
                : null
              }
            />
          </div>
        }
      />
      <Foot>
        {words.pathway.foot} {words.pathway.expandHint}
      </Foot>
    </Card>
  );
}

/** 스킴만 있는 주소(`https://`·`http://`, 대소문자 무관) — 보이기 전용(IRW12 개정 2). 칩·회색 판별은 isSafeLinkUrl. */
const SCHEME_ONLY = /^https?:\/\/$/i;

/** 1-1 항목 한 줄(디자인 e6 11-04): 머리 「n) [라벨]」 뒤에 공통 링크 칩(제목 = 칩 label, 도메인·↗·툴팁은 칩이 그린다).
 * 주소가 http(s) 가 아니면 제목은 글로 두고 주소만 회색 글(칩이 회색으로 그린다). 주소가 없으면 제목만.
 * 주소가 스킴만이고 제목이 있으면 제목만(제목도 비면 회색 주소를 남겨 빈 줄을 막는다 — 개정 2). */
function ItemLine({ item, index }: { item: MergedItem; index: number }) {
  const title =
    item.title !== null && item.title.trim() !== '' ? item.title : undefined;
  const given = item.url?.trim() ?? '';
  const url =
    given === '' || (SCHEME_ONLY.test(given) && title !== undefined) ?
      null
    : item.url;
  return (
    <span className="block" data-item-label={item.label}>
      {`${index + 1}) ${words.shortlist.label[item.label]} `}
      {url !== null && isSafeLinkUrl(url) ?
        <LinkChip url={url} label={title} />
      : url !== null && title === undefined ?
        // 제목 없는 비링크 줄은 회색 값만(「– · 」 0 — IRW12b m2)
        <LinkChip url={url} />
      : <>
          <span className="whitespace-pre-wrap">{item.title ?? dash}</span>
          {url !== null && (
            <>
              {' · '}
              <LinkChip url={url} />
            </>
          )}
        </>
      }
    </span>
  );
}

function ShortCell({
  line,
  cell,
  first,
}: {
  line: ShortlistLine;
  cell: ShortlistCell;
  /** 이 칸이 그 줄의 첫 고칠 칸인가(초점·409 글 자리). */
  first: boolean;
}) {
  const api = useEdit();
  if (!cell.researched)
    return <span className={MUTED}>{words.shortlist.notResearched}</span>;
  if (cell.items.length === 0) return <span className={MUTED}>{dash}</span>;
  const topic = line.no - 1;
  if (isEditing(api, 'shortlist', line.no))
    return (
      <div className={cn(EDIT_CELL, 'flex flex-col gap-3')}>
        {cell.items.map((item, index) => {
          const fields = itemFields(api.result, topic, item);
          return fields === null ?
              <ItemLine key={index} item={item} index={index} />
            : <ItemBoxes
                key={index}
                head={`${index + 1}) ${words.shortlist.label[item.label]}`}
                title={fields.title}
                url={fields.url}
                first={first && index === 0}
              />;
        })}
      </div>
    );
  const edit =
    api.readOnly ? null : (
      editOfCell(
        shortlistCellPointers(api.result, topic, cell.items),
        api.edits,
      )
    );
  return (
    // 줄 사이 6(시안 .l-items 세로 flex · space-1_5 — IRW12b m1). 고침 연필은 absolute 라 flex 사이에 끼지 않는다.
    <EditedMark edit={edit} className="flex flex-col gap-1.5">
      {cell.items.map((item, index) => (
        <ItemLine key={index} item={item} index={index} />
      ))}
    </EditedMark>
  );
}

/** 1-1 줄에 고칠 항목이 있는가(리서치를 한 칸의 자리 있는 항목 — 리서치 못 한 칸만 있는 줄은 단추 없음). */
const editableCell = (cell: ShortlistCell) =>
  cell.researched && cell.items.some((item) => item.at !== null);
const shortlistEditable = (line: ShortlistLine) =>
  editableCell(line.regulation) || editableCell(line.controversy);

/** 1-1 열(디자인 대조 W3 · IRW4 table-fixed): No·토픽은 잰 글 폭(토픽이 넘치면 낱말 사이에서만 꺾임 — 고정 폭에서 nowrap 은 옆 칸을 덮음),
 *  규제 및 정책·컨트로버시는 폭 없음 = 남는 폭을 반반. */
const SHORTLIST_COLUMNS: DataTableColumnDef<ShortlistLine>[] = [
  {
    id: 'no',
    header: words.shortlist.head.no,
    enableSorting: false,
    meta: { width: 50 },
    cell: ({ row }) => (
      <span className="whitespace-nowrap tabular-nums">{row.original.no}</span>
    ),
  },
  {
    id: 'topic',
    header: words.shortlist.head.topic,
    enableSorting: false,
    meta: { width: 108 },
    cell: ({ row }) => <span className="break-keep">{row.original.topic}</span>,
  },
  {
    id: 'regulation',
    header: words.shortlist.head.regulation,
    enableSorting: false,
    cell: ({ row }) => (
      <ShortCell
        line={row.original}
        cell={row.original.regulation}
        first={editableCell(row.original.regulation)}
      />
    ),
  },
  {
    id: 'controversy',
    header: words.shortlist.head.controversy,
    enableSorting: false,
    cell: ({ row }) => (
      <ShortCell
        line={row.original}
        cell={row.original.controversy}
        first={!editableCell(row.original.regulation)}
      />
    ),
  },
];
const SHORTLIST_EDIT_COLUMNS: DataTableColumnDef<ShortlistLine>[] = [
  ...SHORTLIST_COLUMNS,
  editColumn<ShortlistLine>(
    'shortlist',
    (line) => (shortlistEditable(line) ? line.no : null),
    EDIT_WIDTH,
  ),
];

function ShortlistCard({
  result,
  researchReady,
}: {
  result: MaterialityResult;
  researchReady: boolean;
}) {
  const api = useEdit();
  const lines = shortlistLines(result);
  const table = useDataTable({
    data: lines,
    columns:
      api.readOnly || api.editing !== null ?
        SHORTLIST_COLUMNS
      : SHORTLIST_EDIT_COLUMNS,
    getRowId: (line) => String(line.no),
  });
  const cells = lines.flatMap((line) =>
    [line.regulation, line.controversy]
      .filter((cell) => cell.researched)
      .map((cell) => shortlistCellPointers(result, line.no - 1, cell.items)),
  );
  const editingRow = (line: ShortlistLine) =>
    isEditing(api, 'shortlist', line.no);
  // 리서치는 했는데 찾은 글이 없는 토픽 — 토픽 이름을 묶은 안내 하나씩(디자인 대조 J2)
  const emptyTopics = (pick: (line: ShortlistLine) => ShortlistCell) =>
    lines
      .filter((line) => pick(line).researched && pick(line).items.length === 0)
      .map((line) => line.topic);
  const noControversy = emptyTopics((line) => line.controversy);
  const noRegulation = emptyTopics((line) => line.regulation);
  return (
    <Card className="flex flex-col gap-4" data-card="shortlist">
      <CardHead title={words.shortlist.title} cells={cells} />
      {noControversy.length > 0 && (
        <PageInfo icon={<PageInfoIcon />} data-testid="no-controversy">
          {words.shortlist.noControversy(noControversy)}
        </PageInfo>
      )}
      {noRegulation.length > 0 && (
        <PageInfo icon={<PageInfoIcon />} data-testid="no-regulation">
          {words.shortlist.noRegulation(noRegulation)}
        </PageInfo>
      )}
      <DataTable
        table={table}
        layout="fixed"
        aria-label={words.shortlist.title}
        className={cn(RESULT_TABLE, EDITING_TABLE)}
        rowAttrs={(line) => ({
          'data-row': 'shortlist',
          'data-editing': editingRow(line) ? '' : undefined,
        })}
        rowTone={(line) => (editingRow(line) ? 'subtle' : undefined)}
        renderExpanded={(line) =>
          editingRow(line) ?
            <EditActions note={editWords.shortlistNote} />
          : null
        }
        expandedRowAttrs={() => ({ 'data-row': 'edit-actions' })}
      />
      <Foot testId="shortlist-basis">
        {researchReady ?
          `${words.shortlist.basis} ${words.shortlist.basisResearch}`
        : words.shortlist.basis}
      </Foot>
      <Foot>{words.shortlist.foot}</Foot>
    </Card>
  );
}
