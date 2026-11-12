// S1 대시보드 온실가스 탭(밴드 DB1 ② — 고객사 사용자·운영 관리자, sid:MARC-ENT-469·461·597). 값·간격·글: Figma 28952:20455 · 28607:13640 을
//   디자인 트랙이 옮긴 band-handoffs/DB1-figma-values.md(e6). 몸만 — 머리말·회사 띠는 앱 틀, 탭 줄은 app/ghg 의 ModuleTabs.
//   - 읽기는 GET /inventory/scope12/dashboard?year= 를 세 해(고른 해 · −1 · −2) 따로(useDashboard 셋 — 밴드 DB2, e6 ⑤). 합·몫은 서버 글자와
//     model(scopeSharesOf·siteBarsOf·sharePercent·trendOf·yearChangeOf) — 이 파일은 셈하지 않는다.
//   - 그려짐(sid:MARC-ENT-598 — 밴드 DB2, band-handoffs/DB2-figma-values.md): Scope 카드 3개년 막대(TrendBars) · 총 배출량 「전년 대비」.
//     앞 해를 못 받으면(실패·거절) 그 칸은 「없음」 — 오류 띠 없음. 고른 해의 로딩·거절·실패·덮개 갈래는 DB1 그대로.
//   - 숨김(1차): 지역·시장 토글, 「ESG 데이터」 탭.
//   - Scope 3 표시(e6 — sid:MARC-ISSUE-599): 결과 없음 → 총 배출량 숫자 옆 「Scope 3 결과 없음」만(Scope 3 자리 「-」) ·
//     빠진 시트 n>0 → 총 배출량 숫자 옆과 Scope 3 카드 숫자 옆 「시트 n개 빠짐」(Scope 3 결과 화면 ResultView 의 글·꼴). 도넛·막대·상위 5 는 표시 없음.
//   - 미설정 덮개(e6 ③): Scope 1·2 설정도 Scope 3 결과도 없을 때만 — 빈 값 판 위에 흰 95% 덮개 + 안내 + [바로가기](onSetup → S17).
//     뒤 판은 aria-hidden + inert. 그 밖(Scope 3 만 있음)은 덮지 않고 없는 쪽은 「-」.
//   - 화면은 라우터·세션을 모른다(콜백 onYear·onSetup·onInventory·onOrganization, prop year·years·operator).
//   - 움직임(밴드 DB3 — sid:MARC-TICK-538, band-handoffs/DB3-motion-values.md e6 ②~④): CSS keyframes(shared/ui/motion 의 gw-m-*)만 — 타이머·상태 0.
//     카드 줄 gw-m-rise(감독 판단 2 차례) · 도넛 쓸기 · 3개년 막대 · 사업장별·배출원별 몫 막대 gw-m-grow · 빈 상태 글·덮개 안내 gw-m-fade.
//     띠·「빠짐」·단위·바깥 「온실가스 배출량」 판은 움직이지 않는다. 숫자는 밴드 DB4(감독 판단 3·4) 의 여섯 자리 중 이 화면 다섯만 굴린다 —
//     총 배출량 · 도넛 가운데 · Scope 셋의 합(Rolling — 그 카드 떠오름 지연, 도넛 가운데는 쓸기 지연). 그 밖 숫자(상위 5·범례·말풍선·전년 대비)는 그대로. 판 뿌리 key={year} — 해를 바꾸면 처음부터, 같은 해(앞 해가 늦게 옴)는
//     같은 노드라 다시 돌지 않는다. 덮개 뒤 판은 still(움직임 클래스·지연 0). 지연 셈은 model(cardRiseDelay 등).
//     움직이는 요소는 재지 않는다(범례·배출원별 단은 줄의 scrollWidth/clientWidth · 자리 폭 — transform 을 안 탐).
//   - 배출원별 줄(넘김 e6 정함 3 · 감독 판단 10·16): 이름 칸 최소 글 네 자(min-w-14) · 넘치면 세 칸 같이 숫자 16 → 14 Bold · 그래도 넘치면 % 를 숫자 아래 줄로 ·
//     그래도 넘치면 이름을 위 줄 전체 폭(두 줄까지), 아래 줄에 숫자 왼쪽 · % 오른쪽.
//   - 단이 되돌아옴(넘김 R3): 범례·배출원별 줄은 자리(부모 칸) 폭이 바뀌면 0 부터 다시 잰다(useFitStep).
import { useRef } from 'react';
import type { CSSProperties, HTMLAttributes, ReactNode } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import type { GhgDashboardPort } from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { useDashboard } from '../../../entities/ghg/hooks/index.ts';
import type { ReadState } from '../../../entities/ghg/hooks/index.ts';
import {
  cardRiseDelay,
  coveredOf,
  scope3MarkOf,
  scopeAt,
  scopeSharesOf,
  scopeValuesOf,
  sharePercent,
  siteBarsOf,
  siteGrowDelay,
  sourceGrowDelay,
  trendOf,
  yearChangeOf,
} from '../../../entities/ghg/model/index.ts';
import type {
  Dashboard,
  DashboardCategory,
  DashboardSource,
  Scope3Mark,
  YearBoard,
  YearChange,
} from '../../../entities/ghg/model/index.ts';
import { Button, IconButton } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  LoadSkeleton,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리, 밴드 RPW5 #7).
import '../../../shared/ui/motion/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import {
  EMISSION_UNIT,
  formatEmissionNumber,
} from '../../../widgets/review-table/model/index.ts';
import { Donut, DonutAmount } from './Donut.tsx';
import { Rolling } from './Rolling.tsx';
import { TrendBars } from './TrendBars.tsx';
import { toneOf } from './tones.ts';
import { useFitStep } from './useFitStep.ts';

const words = GHG_TEXT.dashboard;
const MARK = 'text-style-pre-caption-03 text-support-error-accent';
const BOX =
  'box-border flex min-w-0 flex-col rounded-component border border-border-tertiary bg-background-primary p-4';

/** 움직임 하나(클래스 + 제 지연 — 0ms 도 적어 위에서 물려받지 않게). still 이면 둘 다 없음(덮개 뒤 판). */
function motion(
  still: boolean,
  name: string,
  delay: number,
): { className: string; style?: CSSProperties } {
  if (still) return { className: '' };
  return {
    className: name,
    style: { '--gw-m-delay': `${delay}ms` } as CSSProperties,
  };
}

export interface DashboardScreenProps {
  port: GhgDashboardPort;
  /** 주소의 연도(경로가 years 안으로 거른 값). */
  year: number;
  /** 고를 수 있는 연도(올해부터 내림 — model yearsOf. 처음 해는 전년도 — defaultYearOf). */
  years: readonly number[];
  operator: boolean;
  onYear(year: number): void;
  /** 미설정 덮개 [바로가기] → 그 해 인덱스 설정(S17). */
  onSetup(year: number): void;
  /** 「온실가스 배출량」·「배출원별 배출량」 › → 온실가스 데이터(Scope 1&2, 같은 해). */
  onInventory(year: number): void;
  /** 「사업장별 배출량」 › → 조직구조. */
  onOrganization(): void;
}

/** 배출량 글자 → 표기(sid:MARC-ENT-272 한 꼴). 없으면 「-」. */
function amount(text: string | number | null): string {
  if (text === null) return words.empty;
  const value = typeof text === 'number' ? text : Number(text);
  return Number.isFinite(value) ? formatEmissionNumber(value) : words.empty;
}

function shareText(share: string | null): string {
  const percent = sharePercent(share);
  if (percent === null) return words.empty;
  return percent === 'below' ? words.shareBelow : words.share(percent);
}

/** 숫자 24 Bold + 단위 14 + (있으면) 작은 빨간 글 — 같은 줄 오른쪽, 좁으면 아래 줄(flex-wrap). */
function Figure({
  value,
  mark,
  testId,
  align = 'start',
  delay,
  still,
}: {
  value: string | null;
  mark: string | null;
  testId: string;
  align?: 'start' | 'end';
  /** 숫자 굴림 시작 지연(밴드 DB4). */
  delay: number;
  still: boolean;
}) {
  return (
    <p
      data-testid={testId}
      className={`m-0 flex flex-wrap items-baseline gap-x-2 ${align === 'end' ? 'justify-end' : ''}`}
    >
      <span className="flex items-baseline gap-1">
        <span className="text-style-pre-display-04 text-text-secondary tabular-nums">
          <Rolling text={amount(value)} delay={delay} still={still} />
        </span>
        {value !== null && (
          <span className="text-style-pre-body-05 text-text-tertiary">
            {EMISSION_UNIT}
          </span>
        )}
      </span>
      {mark !== null && (
        <span data-testid={`${testId}-mark`} className={MARK}>
          {mark}
        </span>
      )}
    </p>
  );
}

/** Scope 카드 머리 오른쪽 작은 꼴(e6 ① — DB1 범례 숫자 꼴: 18 Bold secondary + 사이 4 단위 12 Medium tertiary). 「빠짐」은 아래 줄 오른쪽. */
function ScopeFigure({
  value,
  mark,
  testId,
  delay,
  still,
}: {
  value: string | null;
  mark: string | null;
  testId: string;
  /** 숫자 굴림 시작 지연(밴드 DB4). */
  delay: number;
  still: boolean;
}) {
  return (
    <p data-testid={testId} className="m-0 ml-auto flex flex-col items-end">
      <span className="flex items-baseline gap-1 whitespace-nowrap">
        <span className="text-style-pre-heading-02 text-text-secondary tabular-nums">
          <Rolling text={amount(value)} delay={delay} still={still} />
        </span>
        {value !== null && (
          <span className="text-style-pre-caption-02 text-text-tertiary">
            {EMISSION_UNIT}
          </span>
        )}
      </span>
      {mark !== null && (
        <span data-testid={`${testId}-mark`} className={MARK}>
          {mark}
        </span>
      )}
    </p>
  );
}

/** 판(흰 바탕 · 모서리 16 · 안쪽 24 · 안 간격 24) + 머리(18 Bold, 오른쪽 ›). */
function Panel({
  title,
  onMore,
  testId,
  className = '',
  children,
  ...rest
}: {
  title: string;
  onMore: () => void;
  testId: string;
  className?: string;
  children: ReactNode;
} & Omit<HTMLAttributes<HTMLElement>, 'title' | 'children'>) {
  return (
    <Card
      {...rest}
      data-testid={testId}
      className={`flex flex-col gap-6 p-6 ${className}`}
    >
      <div className="flex h-8 items-center justify-between">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {title}
        </h3>
        <IconButton
          aria-label={words.more(title)}
          className="size-6 text-text-quaternary [&_svg]:size-6"
          onClick={onMore}
        >
          <ChevronRightIcon aria-hidden />
        </IconButton>
      </div>
      {children}
    </Card>
  );
}

function Swatch({ index }: { index: number }) {
  return (
    <span
      aria-hidden
      className={`size-2.5 shrink-0 rounded-[2px] bg-current ${toneOf(index)}`}
    />
  );
}

/** 세 해 가운데 한 해(왼쪽부터 −2 · −1 · 고른 해). */
type YearLine = { year: number; board: YearBoard };

/** 읽기 상태 → 한 해 판(e6 ⑤ · 감독 판단 11): 거절·실패는 그 해 통째 「없음」(오류 띠 없음). 빈 판(configured 거짓)은 받음 — Scope 별 null 이 「없음」. */
function yearBoardOf(state: ReadState<Dashboard>): YearBoard {
  if (state.state === 'loading') return { kind: 'loading' };
  return state.state === 'ready' ?
      { kind: 'ready', board: state.value }
    : { kind: 'none' };
}

function changeText(change: YearChange): string | null {
  if (change.kind === 'hidden') return null;
  if (change.kind === 'same') return words.yearSame;
  return change.kind === 'up' ?
      words.yearUp(change.percent)
    : words.yearDown(change.percent);
}

/** 범례 꼴 차례(감독 판단 14): 0 = 값 18 + 단위 옆 · 1 = 값 14 + 단위 옆 · 2 = 값 14 + 단위 값 아래 줄. 세 줄이 늘 같은 단. */
const LEGEND_STEPS = 3;

/**
 * 총 배출량 카드 범례(DB1 ② + 감독 판단 13·14). 이름 「Scope n」·값·단위는 꺾지도 줄이지도 않는다(값 말줄임 없음 — 다른 값으로 읽힘).
 * 한 줄이라도 넘치면(그려진 scrollWidth > clientWidth) 셋 다 한 단계 내림. 자리(범례가 든 줄 칸) 폭이 바뀌면 0 부터 다시(넘김 R3 — 밴드 DB3).
 */
function Legend({ values }: { values: readonly (string | null)[] }) {
  const listRef = useRef<HTMLUListElement>(null);
  const step = useFitStep(listRef, LEGEND_STEPS, values.join('|'), {
    rows: (list) => [...list.children] as HTMLElement[],
    ink: (list) => [...list.querySelectorAll('[data-legend-value]')],
    place: (list) => list.parentElement,
  });
  return (
    <ul
      ref={listRef}
      data-testid="dashboard-legend"
      data-step={step}
      className="m-0 flex min-w-0 list-none flex-col gap-0.5 p-0"
    >
      {words.scopes.map((name, index) => (
        <li
          key={name}
          data-testid={`dashboard-legend-${index + 1}`}
          className="flex min-w-0 items-center"
        >
          <Swatch index={index} />
          <span className="ml-2 shrink-0 whitespace-nowrap text-style-pre-body-05 text-text-secondary">
            {name}
          </span>
          <span
            className={`ml-4 flex shrink-0 ${step === 2 ? 'flex-col items-end' : 'items-baseline'}`}
          >
            <span
              data-legend-value
              className={`whitespace-nowrap ${step === 0 ? 'text-style-pre-heading-02' : 'text-style-pre-body-04'} text-text-secondary tabular-nums`}
            >
              {amount(values[index] ?? null)}
            </span>
            {values[index] !== null && (
              <span
                data-legend-unit
                className={`${step === 2 ? '' : 'ml-1'} whitespace-nowrap text-style-pre-caption-02 text-text-tertiary`}
              >
                {EMISSION_UNIT}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

function totalMark(mark: Scope3Mark): string | null {
  if (mark.kind === 'none') return words.scope3None;
  return mark.kind === 'missing' ?
      S3_TEXT.result.scopeTotalMissing(mark.sheets)
    : null;
}

function EmissionPanel({
  board,
  history,
  onMore,
  still,
}: {
  board: Dashboard;
  history: readonly YearLine[];
  onMore: () => void;
  still: boolean;
}) {
  const values = scopeValuesOf(board);
  const shares = scopeSharesOf(board);
  const mark = scope3MarkOf(board.total);
  const chosen = history[history.length - 1]!.year;
  const change = changeText(
    yearChangeOf(board, history[history.length - 2]?.board ?? { kind: 'none' }),
  );
  const totalRise = motion(still, 'gw-m-rise', cardRiseDelay(0));
  return (
    <Panel
      title={words.emissionTitle}
      onMore={onMore}
      testId="dashboard-emission"
    >
      <div className="flex min-h-[330px] gap-6">
        <section
          data-testid="dashboard-total"
          className={`${BOX} w-[404px] shrink-0 gap-4 ${totalRise.className}`}
          style={totalRise.style}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-0.5">
              <h4 className="m-0 text-style-pre-heading-02 text-text-primary">
                {words.totalTitle}
              </h4>
              <p className="m-0 text-style-pre-caption-02 text-text-tertiary">
                {words.totalCaption}
              </p>
            </div>
            <div className="w-[162px] shrink-0">
              <Figure
                value={board.total.sum}
                mark={totalMark(mark)}
                testId="dashboard-total-value"
                align="end"
                delay={cardRiseDelay(0)}
                still={still}
              />
              {change !== null && (
                <p
                  data-testid="dashboard-total-change"
                  className="m-0 text-right text-style-pre-body-05 text-text-tertiary"
                >
                  {change}
                </p>
              )}
            </div>
          </div>
          <div className="flex h-[230px] items-center justify-between gap-4">
            <Donut
              still={still}
              shares={shares}
              center={
                <>
                  <DonutAmount text={amount(board.total.sum)} still={still} />
                  <span className="text-style-pre-caption-01 text-text-primary">
                    {EMISSION_UNIT}
                  </span>
                </>
              }
            />
            <Legend values={values} />
          </div>
        </section>
        {words.scopes.map((name, index) => {
          const rise = motion(still, 'gw-m-rise', cardRiseDelay(index + 1));
          return (
            <section
              key={name}
              data-testid={`dashboard-scope-${index + 1}`}
              className={`${BOX} flex-1 justify-between gap-4 ${rise.className}`}
              style={rise.style}
            >
              {/* 머리 한 줄(e6 ① — DB1 ⑤ 갈음): 왼쪽 제목 · 오른쪽 고른 해 합(18 Bold + 단위 12) · 그 아래 줄 오른쪽 「시트 n개 빠짐」.
                카드 폭(1280~1440 에서 약 240)에 큰 값이 안 들어가면 합은 다음 줄 오른쪽으로 내린다(넘침 대신 — 보고 물을 거리). */}
              <div className="flex flex-wrap items-start justify-between gap-x-4">
                <h4 className="m-0 whitespace-nowrap text-style-pre-heading-02 text-text-primary">
                  {words.scopeTitle(name)}
                </h4>
                <ScopeFigure
                  value={values[index] ?? null}
                  mark={
                    index === 2 && mark.kind === 'missing' ?
                      S3_TEXT.result.scopeTotalMissing(mark.sheets)
                    : null
                  }
                  testId={`dashboard-scope-${index + 1}-value`}
                  delay={cardRiseDelay(index + 1)}
                  still={still}
                />
              </div>
              <TrendBars
                trend={trendOf(history, index as 0 | 1 | 2)}
                index={index}
                year={chosen}
                format={amount}
                unit={EMISSION_UNIT}
                testId={`dashboard-scope-${index + 1}-trend`}
                still={still}
              />
            </section>
          );
        })}
      </div>
    </Panel>
  );
}

function SitePanel({
  board,
  onMore,
  still,
}: {
  board: Dashboard;
  onMore: () => void;
  still: boolean;
}) {
  const bars = siteBarsOf(board);
  // 사업장별 Scope 3 나눔 값이 없으면(1차 늘 null) 막대·범례에서 Scope 3 을 뺀다(e6 값 파일 ② 판 2).
  const legend = board.bySite.some((site) => site.scope3 !== null) ? 3 : 2;
  const rise = motion(still, 'gw-m-rise', cardRiseDelay(4));
  return (
    <Panel
      title={words.siteTitle}
      onMore={onMore}
      testId="dashboard-sites"
      className={`w-[32%] min-w-[320px] max-w-[550px] shrink-0 justify-between ${rise.className}`}
      style={rise.style}
    >
      <div className="relative min-h-[160px] flex-1">
        <ul className="absolute inset-0 m-0 flex list-none flex-col gap-5 overflow-y-auto p-0">
          {bars.map((bar, row) => {
            // 줄 하나에 자람 하나(감독 판단 4 — 회색 바탕은 그대로, 조각을 감싼 안쪽 칸이 자란다. 조각마다 달면 몫이 어긋나 보임).
            const grow = motion(still, 'gw-m-grow', siteGrowDelay(row));
            return (
              <li
                key={bar.siteId}
                data-testid={`dashboard-site-${bar.siteId}`}
                className="flex flex-col gap-2"
              >
                <div className="flex h-[21px] items-center justify-between gap-4">
                  <span className="truncate text-style-pre-caption-02 text-text-tertiary">
                    {bar.siteName}
                  </span>
                  <span className="text-style-pre-body-01 text-text-primary tabular-nums">
                    {amount(bar.sum)}
                  </span>
                </div>
                <div
                  aria-hidden
                  className="flex h-3 w-full overflow-hidden rounded-full bg-background-tertiary"
                >
                  <div
                    data-grow
                    className={`flex h-full w-full ${grow.className}`}
                    style={grow.style}
                  >
                    {bar.parts.map((part) =>
                      part.share <= 0 ?
                        null
                      : <span
                          key={part.scopeId}
                          data-part={part.order}
                          className={`h-full bg-current ${toneOf(part.order - 1)}`}
                          style={{ width: `${part.share * 100}%` }}
                        />,
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="flex items-center justify-between gap-4">
        <ul className="m-0 flex list-none gap-2.5 p-0">
          {words.scopes.slice(0, legend).map((name, index) => (
            <li key={name} className="flex w-[84px] items-center gap-2">
              <Swatch index={index} />
              <span className="text-style-pre-body-05 text-text-secondary">
                {name}
              </span>
            </li>
          ))}
        </ul>
        <span className="text-style-pre-caption-02 text-text-quaternary">
          {words.unitNote(EMISSION_UNIT)}
        </span>
      </div>
    </Panel>
  );
}

type SourceLine = {
  key: string;
  name: string;
  value: string;
  share: string | null;
};

const sourceLine = (source: DashboardSource): SourceLine => ({
  key: source.nodeId,
  name: source.name,
  value: source.value,
  share: source.share,
});

const categoryLine = (line: DashboardCategory): SourceLine => {
  const known =
    S3_TEXT.categories[line.category as keyof typeof S3_TEXT.categories];
  return {
    key: line.category,
    name: words.categoryName(line.category, known ?? line.name),
    value: line.value,
    share: line.share,
  };
};

/**
 * 배출원별 줄 꼴 차례(넘김 e6 정함 3 · 감독 판단 10·16): 0 = 값 16 + % 옆 · 1 = 값 14 + % 옆 · 2 = 값 14 + % 값 아래 줄 ·
 * 3 = 이름이 위 줄 전체 폭(두 줄까지·말줄임·title), 아래 줄에 값 14 왼쪽 · % 오른쪽. 세 칸이 늘 같은 단.
 */
const SOURCE_STEPS = 4;

function SourcePanel({
  board,
  onMore,
  still,
}: {
  board: Dashboard;
  onMore: () => void;
  still: boolean;
}) {
  const shares = scopeSharesOf(board);
  const lines: SourceLine[][] = [
    (scopeAt(board, 1)?.topSources ?? []).map(sourceLine),
    (scopeAt(board, 2)?.topSources ?? []).map(sourceLine),
    board.scope3Categories.map(categoryLine),
  ];
  const rowsRef = useRef<HTMLDivElement>(null);
  const step = useFitStep(
    rowsRef,
    SOURCE_STEPS,
    lines
      .map((scope) =>
        scope
          .slice(0, 5)
          .map((line) => `${line.name}:${line.value}:${line.share}`)
          .join(','),
      )
      .join('|'),
    {
      rows: (root) => [...root.querySelectorAll<HTMLElement>('li')],
      ink: (root) => [...root.querySelectorAll('[data-source-value]')],
      place: (root) => root,
    },
  );
  const rise = motion(still, 'gw-m-rise', cardRiseDelay(5));
  return (
    <Panel
      title={words.sourceTitle}
      onMore={onMore}
      testId="dashboard-sources"
      className={`min-w-0 flex-1 ${rise.className}`}
      style={rise.style}
      data-step={step}
    >
      <div ref={rowsRef} className="flex flex-1 gap-6">
        {words.scopes.map((name, index) => {
          const grow = motion(still, 'gw-m-grow', sourceGrowDelay(index));
          return (
            <section
              key={name}
              data-testid={`dashboard-source-${index + 1}`}
              className={`${BOX} flex-1 gap-4`}
            >
              <h4 className="m-0 text-style-pre-heading-02 text-text-primary">
                {name}
              </h4>
              <div
                aria-hidden
                className="h-2 w-full overflow-hidden rounded-full bg-background-tertiary"
              >
                <span
                  className={`block h-full rounded-full bg-current ${toneOf(index)} ${grow.className}`}
                  style={{
                    ...grow.style,
                    width: `${(shares[index] ?? 0) * 100}%`,
                  }}
                />
              </div>
              {lines[index]!.length === 0 ?
                <p
                  data-testid={`dashboard-source-${index + 1}-empty`}
                  className={`m-0 flex flex-1 items-center justify-center text-style-pre-body-05 text-text-tertiary ${still ? '' : 'gw-m-fade'}`}
                >
                  {words.empty}
                </p>
              : <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                  {lines[index]!.slice(0, 5).map((line) => (
                    <li
                      key={line.key}
                      title={line.name}
                      className={
                        step === 3 ?
                          'flex flex-col gap-1'
                        : 'flex items-start justify-between gap-5'
                      }
                    >
                      <span
                        data-testid="dashboard-source-name"
                        className={`line-clamp-2 min-w-14 text-style-pre-body-05 text-text-primary [overflow-wrap:anywhere] ${step === 3 ? 'w-full' : 'flex-1'}`}
                      >
                        {line.name}
                      </span>
                      <span
                        data-testid="dashboard-source-figure"
                        className={`flex shrink-0 gap-x-5 whitespace-nowrap ${
                          step === 2 ? 'flex-col items-end'
                          : step === 3 ? 'w-full items-baseline justify-between'
                          : 'items-baseline'
                        }`}
                      >
                        <span
                          data-source-value
                          className={`${step === 0 ? 'text-style-pre-body-01' : 'text-style-pre-body-04'} text-text-primary tabular-nums`}
                        >
                          {amount(line.value)}
                        </span>
                        <span className="min-w-9 text-right text-style-pre-body-05 text-text-tertiary tabular-nums">
                          {shareText(line.share)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              }
            </section>
          );
        })}
      </div>
    </Panel>
  );
}

function Board({
  board,
  history,
  onInventory,
  onOrganization,
  still = false,
}: {
  board: Dashboard;
  history: readonly YearLine[];
  onInventory: () => void;
  onOrganization: () => void;
  /** 움직이지 않음(미설정 덮개 뒤 판 — e6 ③). 끄면 움직임 클래스·지연 style 이 하나도 안 붙는다. */
  still?: boolean;
}) {
  return (
    <div className="flex flex-col gap-6">
      <EmissionPanel
        board={board}
        history={history}
        onMore={onInventory}
        still={still}
      />
      <div className="flex items-stretch gap-6">
        <SitePanel board={board} onMore={onOrganization} still={still} />
        <SourcePanel board={board} onMore={onInventory} still={still} />
      </div>
    </div>
  );
}

export function DashboardScreen({
  port,
  year,
  years,
  operator,
  onYear,
  onSetup,
  onInventory,
  onOrganization,
}: DashboardScreenProps) {
  // 고른 해가 먼저 — 앞 두 해는 따로 받아 늦게 오면 그 칸만 채운다(e6 ⑤). 시험은 이 차례에 기대지 않는다.
  const { status, retry } = useDashboard(port, year);
  const before = useDashboard(port, year - 1).status;
  const earlier = useDashboard(port, year - 2).status;
  const history = (board: Dashboard): YearLine[] => [
    { year: year - 2, board: yearBoardOf(earlier) },
    { year: year - 1, board: yearBoardOf(before) },
    { year, board: { kind: 'ready', board } },
  ];
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    status.state === 'loading' ? 'loading'
    : status.state === 'ready' ? 'ready'
    : 'failed',
  );
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;

  const head = (
    <>
      <PageTitle title={words.screenLabel} headingRef={retryFocus.doneRef} />
      <div data-testid="dashboard-filters" className="flex h-16 items-center">
        <NativeSelect
          aria-label={words.yearLabel}
          value={year}
          onChange={(event) => {
            const next = years.find((y) => `${y}` === event.target.value);
            if (next !== undefined) onYear(next);
          }}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {words.yearOption(y)}
            </option>
          ))}
        </NativeSelect>
      </div>
    </>
  );

  let body: ReactNode;
  if (status.state === 'loading')
    body = <LoadSkeleton label={GHG_TEXT.common.loading} />;
  else if (status.state === 'refused')
    body = (
      <PageInfo
        role="alert"
        tone="error"
        icon={<CircleWarningIcon aria-hidden />}
        data-testid="company-refusal"
      >
        {companyText[status.company]}
      </PageInfo>
    );
  else if (status.state !== 'ready')
    body = (
      <div
        role="alert"
        data-testid="load-failure"
        className="flex flex-col items-start gap-4"
      >
        <PageInfo
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          className="w-full"
        >
          {GHG_TEXT.inventory.loadFailed}
        </PageInfo>
        <Button
          ref={retryFocus.actionRef}
          variant="solidBlack"
          shape="round"
          size="md"
          onClick={retryFocus.arm(retry)}
        >
          {GHG_TEXT.common.retry}
        </Button>
      </div>
    );
  else if (coveredOf(status.value))
    body = (
      <div data-testid="dashboard-covered" className="relative">
        <div aria-hidden {...{ inert: '' }}>
          <Board
            key={year}
            still
            board={status.value}
            history={history(status.value)}
            onInventory={() => onInventory(year)}
            onOrganization={onOrganization}
          />
        </div>
        <div className="absolute inset-0 flex items-center justify-center rounded-dialog bg-background-primary/95 gw-m-fade">
          <div
            data-testid="dashboard-setup"
            className="flex flex-col items-center gap-6 px-4 py-3 text-center"
          >
            <div className="flex flex-col gap-1">
              <p className="m-0 text-style-pre-body-01 text-text-secondary">
                {words.setupTitle}
              </p>
              <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                {words.setupBody.map((line, index) => (
                  <span key={index} className="block">
                    {line}
                  </span>
                ))}
              </p>
            </div>
            <Button
              variant="solidGrey"
              shape="round"
              size="md"
              className="min-w-20"
              onClick={() => onSetup(year)}
            >
              {words.setupAction}
            </Button>
          </div>
        </div>
      </div>
    );
  else
    body = (
      <Board
        key={year}
        board={status.value}
        history={history(status.value)}
        onInventory={() => onInventory(year)}
        onOrganization={onOrganization}
      />
    );

  return (
    <div data-screen="ghg-dashboard" className="flex flex-col">
      {head}
      {body}
    </div>
  );
}
