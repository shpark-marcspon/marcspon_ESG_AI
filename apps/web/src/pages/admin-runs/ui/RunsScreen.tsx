// AD-04 실행 기록·지표(밴드 AD2 ③, 실서버 AD4R ②, 시안 AD-04_r1·디자인 답 캔버스 AD-04 판). 서버 경로 둘(GET /run-logs·/run-logs/metrics).
// 라우터·세션·전역 시계·빌드 환경을 모른다: 어댑터(port)·시계(now)를 props 로 받는다. 모의 공급사 여부는 서버 지표 aiProviderMock(MP1W).
//   제목 줄([엑셀 내보내기]) → 모의 공급사 안내 띠(받은 지표의 aiProviderMock 이 참일 때만 — 받는 중·실패는 없음) → 지표 다섯 → 카드: 거르기 줄(검색·모듈·기간·상태·검토 + 건수) → 표 → [더 보기] → 표 아래 글.
//   - 예시 데이터 띠는 AD4R 에서 걷었다(sid:MARC-ENT-285 — 줄·건수는 실제).
//   - 「AI 설정」·「검토」 열과 검토 거르기(AD4X ① — 서버 AD4S 가 review·aiSetting 을 싣는다): AI 설정 = 판 이름(기본 판 「기본 설정」, 없으면 회색 「–」),
//     검토 = 배지(미검토 grey · 검토 중 blue · 확정 success, null 은 회색 「–」). 검토 거르기도 서버 쿼리(review=) — 화면은 다시 거르지 않는다.
//   - 문서 칸은 한 줄 120px 에서 「…」로 줄이고 올리면 전체 이름(title — 판 S9, 1280 폭에서 상태·검토 열이 보이게). 시험용 배지는 이름 앞 같은 줄 grey·줄임 밖(AF1 — 디자인 6c Q7·Q8).
//     같이 시작·이어서(AD4P, 결정 MARC-ENT-405 — 캔버스 v138, 디자인 6c 답 10-25): 이름 아래 새 줄에 회색 배지 「같이 시작 #101 · 2/3」(launchSize 2 이상만)·「이어서 #88」.
//     문서 단추의 읽는 이름은 그대로 — 배지 글은 보이는 글대로 읽힌다.
//   - 거르기는 서버 쿼리(model 의 runQuery — 빈·공백 q 와 NUL 은 빼고, 날짜는 KST 로 세어 조인다). 검색은 멈춘 뒤 300ms 에 보낸다(입력 150자).
//     거르기가 바뀌면 첫 쪽부터(지표는 다시 부르지 않는다 — 서버가 늘 이번 달 전체를 센다).
//   - 모듈 고르기 = 고정 여섯 + 불러온 줄에서 처음 본 다른 id(한 번 보이면 남김, model 의 moduleOptions). 표·선택지 모두 표에 없는 id 는 id 그대로.
//   - 상태 배지·거르기는 서버 넷 그대로(대기 grey · 처리 중 orange · 완료 success · 실패 error). 「대기」 줄의 처리 시간·토큰·비용은 「–」(model 의 runFigures).
//   - 0건(디자인 답 5): 기간만 걸렸으면 빈 상태 「<기간> 실행이 없어요」·「기간을 넓혀 보세요.」(전체 기간이면 「아직 실행이 없어요」만),
//     검색·모듈·상태·검토가 걸렸으면 「조건에 맞는 실행이 없어요」 + [거르기 풀기](기간까지 전체로).
//   - 건수: 다 불러오지 않았으면 「{전부}건 중 {실린}건」, 다 불러왔으면 「{전부}건」(전부 = 서버 count).
//   - [엑셀 내보내기](AD4X ② — 판 S2~S6): 지금 목록 요청에 넘긴 그 쿼리 객체(보낸 검색 기준 — 칸에 친 글이 300ms 안이면 싣지 않는다)를
//     쪽 없이 GET /run-logs/export 로 한 번 보내고, 서버가 준 Blob·파일 이름을 save(기본 saveBlob — 이 탭에서 내려받기)로 넘긴다.
//     켬 = 목록 ready·count>0(옆 글 「거른 결과 {n}건을 엑셀로 받아요」). 불러오는 중·실패·만드는 중은 끔, 0건은 끔 + 툴팁 「내보낼 기록이 없어요」.
//     「끔」은 aria-disabled(Tab 에 남는다)이고 누름은 처리기가 막는다(요청 0). 만드는 중 두 번째 누름은 ref 로 막는다(같은 그리기 안의 누름도).
//     실패는 단추 옆 role="alert" 한 줄(판은 토스트 — 토스트 부품이 없어 감독 처분 Q4): 409 상한 넘음과 그 밖을 가른다. 다시 누르거나 거르기를 바꾸면 지운다.
//   - 불러오기(MARC-ENT-260·MARC-ENT-443, 밴드 LD1): 첫 그림부터 표 몸에 자리 잡은 스켈레톤 줄 5(막대는 300ms 뒤 — SkeletonRows), 로딩 중 빈 상태 없음.
//     지표 다섯은 로딩 동안 같은 카드 꼴로 자리를 잡는다(이름은 미리 아는 글이라 진짜로, 값만 막대 — 받은 뒤 아래 카드가 밀리지 않게).
//     숨긴 상태 글·aria-busy 는 300ms 뒤. 실패는 CM-03 꼴 실패 상자 + [다시 시도](지표 자리 없음).
//     더 보기 실패는 단추 자리에 한 줄 글 + [다시 시도](CM-03 칸 하나 실패 꼴).
//   - AD-04a 실행 상세(AD4W): 줄 누름(마우스)·줄 Tab 초점 + Enter·Space(밴드 TB1, 공용 clickableRowProps)와 문서 칸 단추
//     (이름 「{문서} 결과 보기」, title 없음 — 줄 이름도 같은 글)가 모달을 연다. 단추는 자기 처리기로 열고, 줄로 번진 단추 누름·키는
//     공용 규칙(isFromControl·target 비교)이 걸러 한 번만 연다.
//     열 때마다 GET /run-logs/{run_id} 한 번(캐시 없음 — useRunDetail). 닫으면 초점은 키보드로 줄을 연 때 그 줄, 그 밖에는 그 줄의 문서 단추.
//     결과 파일 [내려받기](RF1W): useRunFile 이 받고 엑셀과 같은 save 로 내려받게 한다.
import { useEffect, useId, useRef, useState } from 'react';
import type {
  ComponentProps,
  KeyboardEvent,
  MouseEvent,
  ReactNode,
} from 'react';

import {
  CircleWarningIcon,
  DownloadIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import type { RunLogServerPort } from '../../../entities/run-log/api/index.ts';
import { RUN_LOG_TEXT } from '../../../entities/run-log/config/text.ts';
import {
  RUN_NO_FILTER,
  RUN_PERIODS,
  RUN_QUERY_MAX,
  RUN_REVIEWS,
  RUN_STATUSES,
  aiSettingText,
  costText,
  durationText,
  flowEdition,
  formatRunTime,
  launchMark,
  moduleOptions,
  rateText,
  resumedMark,
  runFigures,
  runQuery,
  searchText,
  tokensShort,
  uploaderText,
  withCommas,
} from '../../../entities/run-log/model/index.ts';
import type {
  RunFilter,
  RunMetricsRow,
  RunPeriod,
  RunReview,
  RunStatus,
} from '../../../entities/run-log/model/index.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  ROW_FOCUS,
  ROW_HOVER,
  clickableRowProps,
} from '../../../shared/ui/data-table/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { FilterSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  SkeletonRows,
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import type { SkeletonColumn } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { SkeletonBar } from '../../../shared/ui/skeleton-bar/index.ts';
import { useRunDetail, useRunFile, useRunLog } from '../hooks/index.ts';
import type { RunDetailOpened } from '../hooks/index.ts';
import { RunDetailDialog, STATUS_LOOK } from './RunDetailDialog.tsx';

const words = RUN_LOG_TEXT;

/** 상태 → 키트 badge 변형은 모달과 같이 쓴다(RunDetailDialog 의 STATUS_LOOK — 색은 그 한 곳에만). */
export { STATUS_LOOK };

/** 검토 → 키트 badge 변형(판 S7: 검토 중 blue · 확정 success. 미검토 grey — cd 확정 10-22). null 은 배지 없이 회색 「–」. */
export const REVIEW_LOOK = {
  pending: 'grey',
  in_review: 'blue',
  confirmed: 'success',
} as const satisfies Record<RunReview, 'grey' | 'blue' | 'success'>;

/** 검색을 보내기 전에 기다리는 ms(멈춘 뒤). */
export const SEARCH_DELAY_MS = 300;

/** [거르기 풀기]: 검색·모듈·상태·검토를 비우고 기간은 전체. */
const NO_FILTER_AT_ALL: RunFilter = { ...RUN_NO_FILTER, period: 'all' };

/** 모듈 라벨: 고정 여섯은 이름, 그 밖은 id 그대로(디자인 답 7). */
const moduleLabel = (id: string) =>
  Object.hasOwn(words.modules, id) ? words.modules[id]! : id;

export interface RunsScreenProps {
  port: RunLogServerPort;
  /** 시계(「오늘」을 KST 로 센다). 기본은 지금. */
  now?: () => Date;
  /** 받은 엑셀·결과 파일을 내려받게 한다. 기본은 이 탭에서 <a download>(saveBlob). 시험이 바꿔 끼운다. */
  save?: (blob: Blob, fileName: string) => void;
}

/** 엑셀 내보내기의 상태(목록 상태와 따로). */
type ExportPhase = 'idle' | 'busy' | 'tooLarge' | 'failed';

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
const cellClass =
  'h-14 whitespace-nowrap border-0 border-b border-solid border-border-tertiary px-4 text-left align-middle';
const COLUMNS = [
  'at',
  'module',
  'document',
  'flow',
  'aiSetting',
  'uploadedBy',
  'duration',
  'tokens',
  'cost',
  'status',
  'review',
] as const;
const COLUMN_COUNT = COLUMNS.length;
/** 로딩 줄의 막대(COLUMNS 차례). 폭은 6c 짧은 칸 값(날짜 112 · 상태 48~80), 그 밖은 긴 글. 숫자 칸은 오른쪽. */
const SKELETON_COLUMNS: readonly SkeletonColumn[] = COLUMNS.map((key) =>
  key === 'at' ? { width: 112 }
  : key === 'status' || key === 'review' ? { width: [48, 80] }
  : key === 'duration' || key === 'tokens' || key === 'cost' ?
    { align: 'right' }
  : {},
);
/**
 * 열 폭(px, COLUMNS 차례 — 밴드 DT1 ②, J3·sid:MARC-ISSUE-374). table-fixed + <colgroup> 이라 로딩·받은 뒤 칸 폭이 같다.
 * 칸 내용의 가장 넓은 폭(max-content — 머리 글 포함, 1280×900·e2e 흉내 자료로 잼, 올림) + 좌우 32. 상태·검토는 배지 글 전부(처리 중·검토 중이
 * 가장 넓다) 기준. 6c 10-27 답 (가): 시각은 잰 값 153(옛 6c 186 을 버림)·AI 설정 84·올린 사람 96 도 고정 — 남는 폭(1280 에서 ≈137)을 문서 칸 하나가 갖는다.
 * 문서는 폭 없음, 이름은 칸 폭에서 말줄임(전체 이름 title). 글 칸 셋(모듈·문서·AI 설정)은 줄바꿈한다(LONG_CELL) · 올린 사람은 한 줄 말줄임(KA1).
 * 모듈은 96 그대로 두 줄(밴드 AD8, sid:MARC-ISSUE-575): 가장 긴 「온실가스 Scope 3」 한 줄은 잰 값 103 + 32 = 135 라 문서 칸이 137 → 98 로 준다.
 */
const COLUMN_WIDTHS: Record<(typeof COLUMNS)[number], number | null> = {
  at: 153,
  module: 96,
  document: null,
  flow: 56,
  aiSetting: 84,
  uploadedBy: 96,
  duration: 85,
  tokens: 87,
  cost: 90,
  status: 74,
  review: 74,
};
/** 글 칸 셋(모듈·문서·AI 설정): cellClass 의 한 줄 고정을 풀어 줄바꿈(table-fixed 에서 옆 칸을 덮지 않게). 올린 사람은 한 줄 말줄임(KA1). */
const LONG_CELL = 'whitespace-normal break-words';

function Metric({
  label,
  children,
}: {
  label: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-dialog bg-background-primary p-6">
      <span className="inline-flex items-center gap-1.5 text-style-pre-body-06 text-text-tertiary">
        {label}
      </span>
      <span className="text-style-pre-display-04 text-text-primary">
        {children}
      </span>
    </div>
  );
}

/** 지표 값 자리의 막대(값 줄 높이를 폭 0 글자로 지킨다 — 막대가 줄 높이를 바꾸지 않게). */
const pendingValue = (
  <span aria-hidden className="relative block">
    {'\u200b'}
    <SkeletonBar className="absolute left-0 top-1/2 h-[22px] w-[60%] -translate-y-1/2" />
  </span>
);

/**
 * 문서 칸 둘째 줄의 배지(같이 시작·이어서): 알약 안에서는 꺾지 않고 칸 폭에서 말줄임, 전체 글은 title(밴드 RL1 N2).
 * 키트 Badge 는 글을 바로 품는 inline-flex 라 말줄임이 안 걸려 안쪽 span 이 truncate 한다. 두 배지가 한 줄에 안 들면 둘째는 다음 줄로.
 */
function LinePill({
  children,
  ...rest
}: Omit<ComponentProps<typeof Badge>, 'children' | 'title'> & {
  children: string;
}) {
  return (
    <Badge
      variant="grey"
      className="min-w-0 max-w-full"
      title={children}
      {...rest}
    >
      <span className="min-w-0 truncate">{children}</span>
    </Badge>
  );
}

/** 지표 다섯. metrics 가 null 이면 받는 중 — 이름은 그대로, 값만 막대(같은 높이). */
function Metrics({ metrics }: { metrics: RunMetricsRow | null }) {
  const m = words.metrics;
  const small = (text: string) => (
    <small className="ml-0.5 text-style-pre-body-06 text-text-tertiary">
      {text}
    </small>
  );
  const value = (read: (row: RunMetricsRow) => ReactNode) =>
    metrics ? read(metrics) : pendingValue;
  return (
    <div
      data-testid={metrics ? 'metrics' : 'metrics-pending'}
      className="grid grid-cols-5 gap-4"
    >
      <Metric label={m.runsThisMonth}>
        {value((row) => (
          <>
            {row.runs}
            {small(m.times)}
          </>
        ))}
      </Metric>
      <Metric label={m.averageDuration}>
        {value((row) => durationText(row.averageDurationSec) ?? words.empty)}
      </Metric>
      <Metric label={m.tokens}>
        {value((row) => tokensShort(row.tokens))}
      </Metric>
      <Metric
        label={
          <>
            {m.cost}
            <Badge variant="grey">{m.estimated}</Badge>
          </>
        }
      >
        {value((row) => costText(row.costUsd, words.costBelow))}
      </Metric>
      <Metric label={m.failureRate}>
        {value((row) => {
          const rate = rateText(row.failureRate);
          return rate === null ?
              words.empty
            : <>
                {rate}
                {small(m.percent)}
              </>;
        })}
      </Metric>
    </div>
  );
}

export function RunsScreen({
  port,
  now = () => new Date(),
  save = saveBlob,
}: RunsScreenProps) {
  const [filter, setFilter] = useState<RunFilter>(RUN_NO_FILTER);
  // 검색 칸의 글은 바로 보이고, 서버로는 멈춘 뒤 300ms 에 간다.
  const [sentQuery, setSentQuery] = useState(filter.query);
  useEffect(() => {
    if (filter.query === sentQuery) return;
    const timer = setTimeout(() => setSentQuery(filter.query), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [filter.query, sentQuery]);
  // 목록과 엑셀이 같은 쿼리 객체를 쓴다(보낸 검색 기준 — 엑셀이 따로 짓지 않는다).
  const listQuery = runQuery({ ...filter, query: sentQuery }, now());
  const log = useRunLog(port, listQuery);
  const loading = useDelayed(log.state.phase === 'loading');
  const retryFocus = useRetryFocus<HTMLHeadingElement>(log.state.phase);
  const state = log.state;
  // 모의 AI 공급사로 도는가(토큰·비용이 실제 값이 아니다 — 지표 위에 안내 띠, 디자인 답 6). 서버 지표가 정본, 받기 전·실패면 띠 없음(MP1W).
  const aiMock = state.phase === 'ready' && state.metrics.aiProviderMock;
  const rows = state.phase === 'ready' ? state.rows : [];
  // 불러온 줄에서 본 모듈 id(한 번 보이면 남긴다 — 그릴 때 맞추는 React 꼴).
  const [seen, setSeen] = useState<string[]>([]);
  const fresh = [
    ...new Set(
      rows.map((row) => row.module).filter((id) => !seen.includes(id)),
    ),
  ];
  if (fresh.length > 0) setSeen([...seen, ...fresh]);
  const modules = moduleOptions([...seen, ...fresh]);
  /** 기간 말고 다른 거르기(보낸 검색·모듈·상태·검토)가 있는가 — 0건 꼴을 가른다(디자인 답 5). */
  const narrowed =
    searchText(sentQuery) !== null ||
    filter.module !== 'all' ||
    filter.status !== 'all' ||
    filter.review !== 'all';
  const [exporting, setExporting] = useState<ExportPhase>('idle');
  const exportBusy = useRef(false);
  const exportHintId = useId();
  /** 거르기를 바꾼다(검색 칸 밖 — 기다린 검색 글도 바로 맞춘다). 엑셀 실패 글은 지운다. */
  const refilter = (next: RunFilter) => {
    setFilter(next);
    setSentQuery(next.query);
    if (exporting !== 'busy') setExporting('idle');
  };
  const exportEmpty = state.phase === 'ready' && state.count === 0;
  const exportOn =
    state.phase === 'ready' && state.count > 0 && exporting !== 'busy';
  /** [엑셀 내보내기]: 끈 때는 요청 0(aria-disabled 는 누름을 막지 않는다 — 여기서 막는다). */
  const exportRuns = async () => {
    if (state.phase !== 'ready') return;
    if (state.count === 0) return;
    if (exportBusy.current) return;
    exportBusy.current = true;
    setExporting('busy');
    const outcome = await port
      .exportFile(listQuery)
      .catch(() => ({ kind: 'failed' }) as const);
    exportBusy.current = false;
    if (outcome.kind === 'ok') {
      save(outcome.blob, outcome.fileName);
      setExporting('idle');
    } else setExporting(outcome.kind);
  };

  // AD-04a 실행 상세: 연 차례(seq 는 열 때마다 새 값 — 같은 줄을 다시 열어도 다시 부른다)와 닫은 뒤 초점이 갈 문서 단추.
  const [opened, setOpened] = useState<
    (RunDetailOpened & { opener: HTMLElement | null }) | null
  >(null);
  const openSeq = useRef(0);
  const detail = useRunDetail(port, opened);
  const runFile = useRunFile(port, opened, save);
  /** 실행 상세를 연다. opener = 닫은 뒤 초점이 돌아갈 자리. */
  const open = (runId: number, opener: HTMLElement | null) =>
    setOpened({ runId, seq: ++openSeq.current, opener });
  /**
   * 줄 누름(밴드 TB1 — sid:MARC-ENT-599 규칙 3·4): 공용 clickableRowProps 로 줄이 Tab 자리가 되고 Enter·Space 로 연다.
   * 칸 안 컨트롤(문서 단추)에서 온 누름·키는 공용 규칙이 거른다 — 단추는 자기 onClick 으로 연다(한 번 눌러 한 번).
   * 닫은 뒤 초점: 마우스로 줄을 누르면 지금처럼 그 줄의 문서 단추, 키보드로 줄을 열면 그 줄.
   * 줄 이름은 문서 단추 이름과 같은 글(BatchTable 꼴) — 초점이 줄에 오면 칸 글 전부 대신 그 이름 하나만 읽힌다.
   */
  const rowProps = (runId: number, label: string) => {
    let opener: HTMLElement | null = null;
    const row = clickableRowProps(runId, (id) => open(id, opener))!;
    return {
      ...row,
      'aria-label': label,
      onClick: (event: MouseEvent<HTMLElement>) => {
        opener =
          event.currentTarget.querySelector<HTMLElement>('[data-run-open]');
        row.onClick(event);
      },
      onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
        opener = event.currentTarget;
        row.onKeyDown(event);
      },
    };
  };

  const body = (content: ReactNode) => (
    <tr>
      <td colSpan={COLUMN_COUNT} className="p-0">
        {content}
      </td>
    </tr>
  );

  return (
    <div data-screen="admin-runs" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        headingRef={retryFocus.doneRef}
        description={words.description}
        actions={
          <div className="flex flex-wrap items-center justify-end gap-3">
            {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(실패). */}
            <p
              role="alert"
              data-testid="export-error"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
            >
              {(exporting === 'tooLarge' || exporting === 'failed') && (
                <>
                  <CircleWarningIcon aria-hidden />
                  {exporting === 'tooLarge' ?
                    words.exportTooLarge
                  : words.exportFailed}
                </>
              )}
            </p>
            {state.phase === 'ready' && state.count > 0 && (
              <span
                data-testid="export-count"
                className="text-style-pre-caption-03 text-text-tertiary"
              >
                {words.exportCount(withCommas(state.count))}
              </span>
            )}
            {/* 0건 설명(툴팁과 같은 글) — 화면 읽기용, 늘 두고 aria-describedby 로 잇는다. */}
            <span id={exportHintId} className="sr-only">
              {exportEmpty ? words.exportEmpty : null}
            </span>
            {/* 꺼진 단추는 span 으로 감싸 툴팁(판 S4). 툴팁 글은 0건일 때만. */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <button
                      type="button"
                      data-testid="export"
                      aria-disabled={!exportOn || undefined}
                      aria-busy={exporting === 'busy' || undefined}
                      aria-describedby={exportEmpty ? exportHintId : undefined}
                      onClick={() => void exportRuns()}
                      className={cn(
                        buttonVariants({
                          variant: 'solidGrey',
                          shape: 'round',
                          size: 'md',
                        }),
                        'gap-1.5 [&_svg]:size-4',
                        !exportOn && 'cursor-not-allowed opacity-40',
                      )}
                    >
                      {exporting === 'busy' ?
                        words.exporting
                      : <>
                          <DownloadIcon aria-hidden />
                          {words.export}
                        </>
                      }
                    </button>
                  </span>
                </TooltipTrigger>
                {exportEmpty && (
                  <TooltipContent>{words.exportEmpty}</TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>
        }
      />
      {aiMock && (
        // 정보 띠(디자인 답 6·캔버스 v102 — CM-03 정보 띠, 아이콘·글 색은 PageInfo 기본 꼴). 회색 쪽 바탕 위에서 흐리지 않게
        // 바탕만 카드와 같은 흰 surface·모서리 16(위아래 12·좌우 16 은 PageInfo 그대로) — 디자인 대조 AD4R, 공용 PageInfo 0줄.
        <PageInfo
          icon={<PageInfoIcon />}
          data-testid="ai-mock-notice"
          className="rounded-dialog bg-background-primary"
        >
          {words.aiMockNotice}
        </PageInfo>
      )}
      {state.phase === 'ready' ?
        <Metrics metrics={state.metrics} />
      : state.phase === 'loading' && <Metrics metrics={null} />}
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SearchField
              aria-label={words.searchLabel}
              placeholder={words.searchPlaceholder}
              value={filter.query}
              maxLength={RUN_QUERY_MAX}
              onChange={(event) => {
                setFilter({ ...filter, query: event.target.value });
                if (exporting !== 'busy') setExporting('idle');
              }}
              className="w-52"
            />
            <FilterSelect<string>
              label={words.module.label}
              aria-label={words.module.name}
              value={filter.module}
              options={[
                { value: 'all', label: words.module.all },
                ...modules.map((module) => ({
                  value: module,
                  label: moduleLabel(module),
                })),
              ]}
              onChange={(module) => refilter({ ...filter, module })}
            />
            <FilterSelect<RunPeriod>
              label={words.period.label}
              aria-label={words.period.name}
              value={filter.period}
              options={RUN_PERIODS.map((period) => ({
                value: period,
                label: words.period.options[period],
              }))}
              onChange={(period) => refilter({ ...filter, period })}
            />
            <FilterSelect<RunStatus | 'all'>
              label={words.status.label}
              aria-label={words.status.name}
              value={filter.status}
              options={(['all', ...RUN_STATUSES] as const).map((status) => ({
                value: status,
                label: words.status.options[status],
              }))}
              onChange={(status) => refilter({ ...filter, status })}
            />
            <FilterSelect<RunReview | 'all'>
              label={words.review.label}
              aria-label={words.review.name}
              value={filter.review}
              options={(['all', ...RUN_REVIEWS] as const).map((review) => ({
                value: review,
                label: words.review.options[review],
              }))}
              onChange={(review) => refilter({ ...filter, review })}
            />
          </div>
          {state.phase === 'ready' && (
            <span
              data-testid="count"
              className="text-style-pre-caption-03 text-text-tertiary"
            >
              {state.isNext ?
                words.countOf(state.count, state.rows.length)
              : words.count(state.count)}
            </span>
          )}
        </div>
        {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(밴드 LA1 ①). */}
        <span className="sr-only" role="status">
          {loading ? words.loading : null}
        </span>
        <div className="w-full overflow-x-auto">
          <table
            aria-label={words.tableLabel}
            aria-busy={loading || undefined}
            className="w-full table-fixed border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary"
          >
            <colgroup>
              {COLUMNS.map((key) => {
                const width = COLUMN_WIDTHS[key];
                return (
                  <col
                    key={key}
                    style={width === null ? undefined : { width }}
                  />
                );
              })}
            </colgroup>
            <thead>
              <tr>
                {COLUMNS.map((key) => (
                  <th
                    key={key}
                    scope="col"
                    className={cn(
                      headClass,
                      (key === 'duration' ||
                        key === 'tokens' ||
                        key === 'cost') &&
                        'text-right',
                    )}
                  >
                    {words.columns[key]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.phase === 'loading' ?
                <SkeletonRows columns={SKELETON_COLUMNS} />
              : state.phase === 'failed' ?
                body(
                  <div
                    role="alert"
                    data-testid="load-failure"
                    className="flex flex-col items-start gap-4 py-6"
                  >
                    <PageInfo
                      tone="error"
                      icon={<CircleWarningIcon aria-hidden />}
                      className="w-full"
                    >
                      {words.failed}
                    </PageInfo>
                    <Button
                      ref={retryFocus.actionRef}
                      variant="solidBlack"
                      shape="round"
                      size="md"
                      onClick={retryFocus.arm(log.retry)}
                    >
                      {words.retry}
                    </Button>
                  </div>,
                )
              : rows.length === 0 && !narrowed ?
                // 기간만 거른 0건: 빈 상태 두 줄(전체 기간이면 한 줄), [거르기 풀기] 없음.
                body(
                  <Empty
                    data-testid="empty"
                    className="min-h-[120px]"
                    title={
                      filter.period === 'all' ?
                        words.emptyAll
                      : words.emptyPeriod(words.period.options[filter.period])
                    }
                    description={
                      filter.period === 'all' ? undefined : words.widenPeriod
                    }
                  />,
                )
              : rows.length === 0 ?
                body(
                  <div
                    data-testid="no-match"
                    className="flex min-h-[120px] flex-col items-center justify-center gap-3"
                  >
                    <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                      {words.noMatch}
                    </p>
                    <Button
                      variant="outlineGrey"
                      shape="round"
                      size="sm"
                      onClick={() => refilter(NO_FILTER_AT_ALL)}
                    >
                      {words.clearFilter}
                    </Button>
                  </div>,
                )
              : rows.map((row) => {
                  const uploader = uploaderText(row, words.unknownUploader);
                  const figures = runFigures(row, words);
                  const setting = aiSettingText(row.aiSetting, words);
                  const at = formatRunTime(row.createdAt);
                  const launch = launchMark(row);
                  const resumed = resumedMark(row);
                  const openLabel =
                    row.documentName === null ?
                      words.detail.openLabelNoDocument(at)
                    : words.detail.openLabel(row.documentName);
                  return (
                    <tr
                      key={row.id}
                      data-run-id={row.id}
                      {...rowProps(row.id, openLabel)}
                      className={cn('cursor-pointer', ROW_HOVER, ROW_FOCUS)}
                    >
                      <td className={cn(cellClass, 'tabular-nums')}>{at}</td>
                      <td className={cn(cellClass, LONG_CELL)}>
                        {moduleLabel(row.module)}
                      </td>
                      <td className={cn(cellClass, LONG_CELL)}>
                        {/* table-fixed 의 문서 칸(폭 없음 — 1280 에서 남는 폭이 내용보다 좁다, 밴드 DT1): 첫 줄(배지 + 이름)은 줄을 바꾸지 않고
                            배지는 줄지 않으며 이름이 남은 폭에서 말줄임(전체 이름은 title, 밴드 RL1 N1). 칸 밖으로 넘쳐 옆 칸을 덮지 않게. */}
                        <span className="flex min-w-0 flex-nowrap items-center gap-1.5">
                          {row.isTest && (
                            <Badge
                              variant="grey"
                              className="shrink-0"
                              data-test-run
                            >
                              {words.test}
                            </Badge>
                          )}
                          {/* 단추에는 title 을 달지 않는다(전체 이름 title 은 안쪽 span — 판 S9). 문서 없는 줄은 회색 「–」·title 없음·이름은 시각(ND1W). */}
                          <button
                            type="button"
                            data-run-open
                            aria-label={openLabel}
                            onClick={(event) =>
                              open(row.id, event.currentTarget)
                            }
                            className="m-0 min-w-0 max-w-full cursor-pointer border-0 bg-transparent p-0 text-left text-inherit [font:inherit]"
                          >
                            {row.documentName === null ?
                              <span
                                className="text-text-tertiary"
                                data-document-missing
                              >
                                {words.empty}
                              </span>
                            : <span
                                className="block max-w-[120px] truncate"
                                title={row.documentName}
                              >
                                {row.documentName}
                              </span>
                            }
                          </button>
                        </span>
                        {(launch !== null || resumed !== null) && (
                          <span className="mt-1 flex min-w-0 flex-wrap items-center gap-1 tabular-nums">
                            {launch !== null && (
                              <LinePill data-launch>
                                {words.launch(
                                  launch.first,
                                  launch.index,
                                  launch.size,
                                )}
                              </LinePill>
                            )}
                            {resumed !== null && (
                              <LinePill data-resumed>
                                {words.resumed(resumed)}
                              </LinePill>
                            )}
                          </span>
                        )}
                      </td>
                      <td className={cellClass}>{flowEdition(row.flowId)}</td>
                      <td
                        className={cn(
                          cellClass,
                          LONG_CELL,
                          setting.missing && 'text-text-tertiary',
                        )}
                        data-ai-setting-missing={setting.missing || undefined}
                      >
                        {setting.text}
                      </td>
                      <td
                        className={cn(
                          cellClass,
                          uploader.missing && 'text-text-tertiary',
                        )}
                        data-uploader-missing={uploader.missing || undefined}
                      >
                        {/* 한 줄 말줄임은 안쪽 span — td 에 달면 칸 넘침(scrollWidth)으로 잰다(KA1, 문서 칸 꼴). */}
                        <span
                          className="block truncate"
                          title={uploader.missing ? undefined : uploader.text}
                        >
                          {uploader.text}
                        </span>
                      </td>
                      <td className={cn(cellClass, 'text-right tabular-nums')}>
                        {figures.duration}
                      </td>
                      <td className={cn(cellClass, 'text-right tabular-nums')}>
                        {figures.tokens}
                      </td>
                      <td className={cn(cellClass, 'text-right tabular-nums')}>
                        {figures.cost}
                      </td>
                      <td className={cellClass}>
                        <Badge
                          variant={STATUS_LOOK[row.status]}
                          data-status={row.status}
                        >
                          {words.status.options[row.status]}
                        </Badge>
                      </td>
                      <td className={cellClass}>
                        {row.review === null ?
                          <span className="text-text-tertiary">
                            {words.empty}
                          </span>
                        : <Badge
                            variant={REVIEW_LOOK[row.review]}
                            data-review={row.review}
                          >
                            {words.review.options[row.review]}
                          </Badge>
                        }
                      </td>
                    </tr>
                  );
                })
              }
            </tbody>
          </table>
        </div>
        {state.phase === 'ready' && state.isNext && (
          <div className="flex justify-center" data-testid="more">
            {state.more === 'failed' ?
              <div
                role="alert"
                className="flex items-center gap-3 text-style-pre-body-06 text-text-tertiary"
              >
                <span>{words.moreFailed}</span>
                <Button
                  variant="outlineGrey"
                  shape="round"
                  size="sm"
                  onClick={log.more}
                >
                  {words.retry}
                </Button>
              </div>
            : <Button
                variant="outlineGrey"
                shape="round"
                size="md"
                loading={state.more === 'loading'}
                onClick={log.more}
              >
                {words.more}
              </Button>
            }
          </div>
        )}
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {words.foot}
        </p>
      </Card>
      {opened !== null && (
        <RunDetailDialog
          state={detail.state}
          file={runFile.state}
          returnFocus={opened.opener}
          onRetry={detail.retry}
          onClose={() => setOpened(null)}
          onDownload={runFile.download}
        />
      )}
    </div>
  );
}
