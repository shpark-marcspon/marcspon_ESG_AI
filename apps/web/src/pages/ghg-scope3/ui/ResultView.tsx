// S3-08 카테고리 카드 목록(밴드 S3W2a ② — 판 S3-08·08a 「그대로」, 캔버스 그림을 읽음 · 간격은 그림 어림, 디자인 확인 거리).
// 그 해의 지금 결과를 그린다(밴드 S3W3a ②): 마지막 실행 결과(rejected 면 지금 갈래) → 연도 상태(port.year) → 카테고리 지금 결과 실행의 서로 다른 값마다 result·edits.
//   카드 합·시트 수는 서버 categories[] 글자 그대로, 상세는 그 카테고리 current.runId 의 결과에 그 실행 edits 를 덧씌운 것이다. 하나라도 못 읽으면 읽기 실패(본문 합으로 물러서지 않는다 — Q5).
// 카드 15장(5×3)을 그린다. C10 빼고 카드는 단추다 — 누르면 그 카테고리 상세(S3-09·S3-10, CategoryDetail —
//   밴드 S3W2b ②, 화면 상태 · 주소 칸 0). 빈·실패 카드도 열린다(시트별 까닭). [목록] 이면 카드 목록으로, 초점은 연 카드로.
//   runId 가 바뀌거나(해·새 계산) 다시 읽으면 목록으로.
//   - 수는 model 이 낸 수(currentCards — parseNumber 한 곳)를 emission.ts 가 review-table 표기로 적는다(sid:MARC-ENT-272). ÷·× 0(sid:MARC-ENT-264).
//   - 합 없음(빈 시트·C10)은 「-」, 계산된 시트 없이 실패만 있으면 「계산 실패」, 일부만 실패면 합 + 「시트 n개 계산 실패」(Q3 — cardState),
//     C5·C12 는 둘째 줄에 생물기원 합.
//   - done 안의 실패 수(시트·AI 호출)는 한 줄. 시트의 error·거절 detail 은 model 꼴에 없다(화면 0).
//   - rejected 는 그 해 지금 결과(port.year 의 카테고리 지금 결과)가 있으면 카드·총합·잠금을 그대로 그리고 까닭 글은 카드 위 띠(H-3 — 사용자 11-07,
//     sid:MARC-ISSUE-583). 지금 결과가 없을 때만 앞처럼 까닭 글 + [데이터 업로드]. 읽기 실패(404 결과 없음 포함)는 그 자리 + [다시 시도] + [데이터 업로드]
//     (새 계산 길 — S3W2a ⑤), 늦은 답은 버린다(asked 꼴).
//   - [데이터 업로드]는 있는 S3-02 흐름(onUpload). 거름은 0(발주서 S3W2a §1-5). 자물쇠는 카드에 표시만, 누르는 단추는 상세 머리(S3W3a ③).
//   - [데이터 다운로드](밴드 S3D1 — S3-15)는 카드 목록이 그려질 때만(ok 갈래 — 거절·실패·불러오는 중 0) [데이터 업로드] 오른쪽 끝(Figma 28023:11429 — 디자인 확인 S3D1). 창은 Scope3DownloadDialog,
//     닫히면 초점은 그 단추로.
//   - 움직임(밴드 DB3 — sid:MARC-TICK-538, band-handoffs/DB3-motion-values.md e6 ②·③): 카드 15장만 gw-m-rise(카드마다 40ms, 상한 400 — 아래 cardRiseDelay).
//     총합 머리·띠·s3-problems·상세는 움직이지 않는다. 카드 목록은 key={year} · 같은 해 다시 읽기는 같은 노드(안 돎) ·
//     상세 → [목록]은 「이 해·실행 떠오름 끝」 ref 로 안 돎(감독 판단 7 (a)) · 새 실행(runId 바뀜)·해 바뀜은 다시 떠오름(7 (b)).
//   - 숫자 굴림(밴드 DB5 — sid:MARC-TICK-544 · 발주서 §2-② · 감독 판단 1·2): 카드 합·생물기원 값 칸만(단위·「총 배출량」·빠짐 글·생물기원 앞 글 0).
//     시작 = 그 카드 떠오름 지연 · 길이 = min(700, 1000 − 지연)(셈은 entities/ghg model rollTiming) · 생물기원은 합과 같은 지연·길이.
//     때 = 떠오름과 같음(still — 상세 → [목록]·같은 실행 다시 읽기 0) · 실패·빈 칸·「-」·0·「<0.001」은 처음부터 제자리.
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, ReactNode, Ref } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import type {
  CompanyRefusal,
  Scope3Port,
} from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  currentCards,
  currentFailedSheets,
  currentRunIds,
  currentTotal,
  overlayResult,
  summarize,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  CategoryId,
  CurrentCard,
  RejectReason,
  Scope3Done,
  Scope3Year,
} from '../../../entities/ghg-scope3/model/index.ts';
import { useRoll } from '../../../entities/ghg/hooks/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
// 움직임 클래스(gw-m-*)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리, 밴드 RPW5 #7).
import '../../../shared/ui/motion/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { AdjustLaterMark } from './AdjustLater.tsx';
import { CategoryDetail } from './CategoryDetail.tsx';
import { LockMark } from './LockControl.tsx';
import { Scope3DownloadDialog } from './Scope3DownloadDialog.tsx';
import { cardState } from './cardState.ts';
import { EMISSION_UNIT, emissionText } from './emission.ts';

const words = S3_TEXT.result;

/**
 * Scope 3 결과 카드 떠오름 지연(밴드 DB3 — e6 ② 「카드마다 40ms, 상한 400ms(11번째 카드부터)」 · ① 지연 상한 400).
 * 대시보드 지연 셈(entities/ghg/model/motion.ts)과 같은 값이다(DB3 때는 이 화면이 entities/ghg 를 가져올 수 없어 여기 두었다 — DB5 부터 훅 표면은 들인다).
 */
const cardRiseDelay = (order: number): number => Math.min(order * 40, 400);

/**
 * 카드 숫자 굴림 칸(밴드 DB5 — 대시보드 Rolling·인벤토리 RollingText 와 같은 꼴, pages 끼리는 가져오지 않아 여기 둔다 — 세 벌째).
 * 굴리는 동안 끝 글자를 깔아 칸 폭을 잡고 프레임은 aria-hidden, 화면 읽기는 sr-only 끝 글자. 다 굴면 끝 글자 하나만(BASE 와 같은 DOM).
 * 값 칸(합·생물기원 값)은 늘 tabular-nums 다(끝 그림 포함 — 굴림 끝에 칸 폭이 안 바뀜. 디자인 e6 (나), 감독 a4 11-09).
 */
function RollingValue({
  text,
  delay,
  still,
}: {
  text: string;
  delay: number;
  still: boolean;
}) {
  const frame = useRoll(text, { delay, enabled: !still });
  if (frame === null) return <>{text}</>;
  return (
    <span data-rolling="" className="inline-grid">
      <span aria-hidden className="invisible [grid-area:1/1]">
        {text}
      </span>
      <span aria-hidden className="text-right [grid-area:1/1]">
        {frame}
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

export interface ResultViewProps {
  port: Scope3Port;
  /** done 인 그 해 마지막 실행. */
  runId: string;
  /** 화면의 해(지금 결과를 읽는다). */
  year: number;
  operator?: boolean;
  /** [데이터 업로드] — 570 문을 지나 S3-02 흐름을 연다. */
  onUpload(): void;
  /** 그 단추 옆 한 줄(570 문의 연도 읽기 실패). */
  uploadProblem?: string | null;
  /** [데이터 업로드] 단추(창이 닫히면 초점이 돌아온다). */
  uploadRef?: Ref<HTMLButtonElement>;
  /** [데이터 업로드]를 막는다(그 해 새 실행이 도는 중 — 지금 결과만 보일 때, H-3). */
  uploadDisabled?: boolean;
}

type Loaded =
  | { state: 'loading' }
  | { state: 'failed' }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'rejected'; reason: RejectReason }
  | {
      state: 'ok';
      /** 마지막 실행의 결과(AI 호출 실패 수만 여기서). 마지막 실행이 거절이면 null(그 수는 싣지 않는다). */
      last: Scope3Done | null;
      /** 마지막 실행이 거절이었으면 그 까닭(카드 위 띠 — H-3). */
      rejected: RejectReason | null;
      year: Scope3Year;
      /** 지금 결과 실행 → 덧씌우기 전 결과(다시 읽기는 덧판만 새로 받아 여기에 덧씌운다). */
      raw: ReadonlyMap<string, Scope3Done>;
      /** 지금 결과 실행 → 덧씌운 결과. */
      runs: ReadonlyMap<string, Scope3Done>;
    };

const EMPTY_DONE: Scope3Done = { status: 'done', sheets: [], llmCalls: {} };

export function ResultView({
  port,
  runId,
  year,
  operator = false,
  onUpload,
  uploadProblem = null,
  uploadRef,
  uploadDisabled = false,
}: ResultViewProps) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });
  const [rereadFailed, setRereadFailed] = useState(false);
  const asked = useRef(0);
  /** 다시 읽기의 차례(늦은 답은 버린다). */
  const rereads = useRef(0);
  /** 가장 새 다시 읽기. 밀린 다시 읽기는 값을 버리고 이것이 끝날 때까지 기다린다(sid:MARC-ISSUE-587 R1). */
  const newest = useRef<Promise<void> | null>(null);
  /** 카드가 떠오름을 마친 「해|실행」(감독 판단 7 — 상세 → [목록]으로 다시 붙어도 안 돎. 해·실행이 바뀌면 키가 달라 다시 떠오름). */
  const risen = useRef<string | null>(null);
  /** 연 상세(없으면 카드 목록). */
  const [opened, setOpened] = useState<CategoryId | null>(null);
  /** [목록] 뒤 초점을 돌려줄 카드. */
  const [backTo, setBackTo] = useState<CategoryId | null>(null);
  const cardButtons = useRef(new Map<CategoryId, HTMLButtonElement>());
  /** S3-15 창이 열렸는가 · 닫히면 초점을 돌려줄 [데이터 다운로드]. */
  const [downloading, setDownloading] = useState(false);
  const downloadButton = useRef<HTMLButtonElement>(null);
  useLayoutEffect(() => {
    if (backTo === null || opened !== null) return;
    cardButtons.current.get(backTo)?.focus();
    setBackTo(null);
  }, [backTo, opened]);

  /** 지금 결과 실행의 서로 다른 값마다 result·edits(손에 든 result 는 다시 읽지 않는다). 하나라도 못 읽으면 그 갈래. */
  const readRuns = async (
    state: Scope3Year,
    known: ReadonlyMap<string, Scope3Done>,
  ): Promise<
    | {
        kind: 'ok';
        raw: Map<string, Scope3Done>;
        runs: Map<string, Scope3Done>;
      }
    | { kind: 'refused'; company: CompanyRefusal }
    | { kind: 'failed' }
  > => {
    const read = await Promise.all(
      currentRunIds(state).map(async (id) => {
        const held = known.get(id);
        const [result, edits] = await Promise.all([
          held ? ({ kind: 'ok', value: held } as const) : port.result(id),
          port.edits(id),
        ]);
        return { id, result, edits };
      }),
    );
    const raw = new Map<string, Scope3Done>();
    const runs = new Map<string, Scope3Done>();
    for (const { id, result, edits } of read) {
      if (result.kind === 'refused') return result;
      if (edits.kind === 'refused') return edits;
      if (
        result.kind !== 'ok' ||
        edits.kind !== 'ok' ||
        result.value.status !== 'done'
      )
        return { kind: 'failed' };
      raw.set(id, result.value);
      runs.set(id, overlayResult(result.value, edits.value));
    }
    return { kind: 'ok', raw, runs };
  };

  const load = async () => {
    const ticket = ++asked.current;
    const stale = () => ticket !== asked.current;
    const fail = (
      out: { kind: 'failed' } | { kind: 'refused'; company: CompanyRefusal },
    ) =>
      setLoaded(
        out.kind === 'refused' ?
          { state: 'refused', company: out.company }
        : { state: 'failed' },
      );
    setOpened(null);
    setRereadFailed(false);
    // 새로 읽는 판은 다시 떠오른다(감독 판단 7 (b) — 해·실행 바뀜. 바뀐 직후 앞 값 그리기에서 적힌 키도 지운다).
    risen.current = null;
    setLoaded({ state: 'loading' });
    const out = await port.result(runId);
    if (stale()) return;
    if (out.kind !== 'ok') return fail(out);
    const result = out.value;
    const last = result.status === 'done' ? result : null;
    const state = await port.year(year);
    if (stale()) return;
    if (state.kind !== 'ok')
      // 거절은 앞처럼 까닭 글로(지금 결과를 못 읽었으니 카드를 그릴 수 없다).
      return last === null && result.status === 'rejected' ?
          setLoaded({ state: 'rejected', reason: result.reason })
        : fail(state);
    // 거절이고 그 해 지금 결과가 없으면 앞 갈래 그대로(H-3 — 지금 결과가 없을 때의 갈래는 그대로).
    if (result.status === 'rejected' && currentRunIds(state.value).length === 0)
      return setLoaded({ state: 'rejected', reason: result.reason });
    const read = await readRuns(
      state.value,
      last === null ? new Map() : new Map([[runId, last]]),
    );
    if (stale()) return;
    if (read.kind !== 'ok') return fail(read);
    setLoaded({
      state: 'ok',
      last,
      rejected: result.status === 'rejected' ? result.reason : null,
      year: state.value,
      raw: read.raw,
      runs: read.runs,
    });
  };

  /**
   * 쓰기 답 뒤 다시 읽기(load 와 따로 — S3W3b·c 도 이것을 쓴다): 연도 → 그 지금 결과 실행마다 덧판, 손에 없는 실행은 결과도.
   * 뼈대·opened 0 — 상세·검색·쪽을 그대로 둔다. 실패는 한 줄(지금 값 유지).
   * 뒤 다시 읽기에 밀려 값을 버린 것은 그 뒤 것(서버를 더 늦게 읽었다)이 끝난 뒤에 끝난다 — 부른 쪽이 답 뒤 그린 값으로
   * 재는 자리(끊긴 잠금의 settled)가 밀린 사이의 낡은 값으로 재지 않게(sid:MARC-ISSUE-587 R1).
   */
  const reread = () => {
    const run = rereadOnce();
    newest.current = run;
    return run;
  };
  const rereadOnce = async () => {
    const from = asked.current;
    const ticket = ++rereads.current;
    const stale = () => from !== asked.current || ticket !== rereads.current;
    /** 밀렸으면 가장 새 것을 기다린다(그것도 밀리면 다시 그다음을). load 가 바뀌었으면 그냥 끝. */
    const behind = async () => {
      if (from !== asked.current) return;
      await newest.current;
    };
    if (loaded.state !== 'ok') return;
    const state = await port.year(year);
    if (stale()) return behind();
    if (state.kind !== 'ok') return setRereadFailed(true);
    const read = await readRuns(state.value, loaded.raw);
    if (stale()) return behind();
    if (read.kind !== 'ok') return setRereadFailed(true);
    setRereadFailed(false);
    setLoaded({
      ...loaded,
      year: state.value,
      raw: read.raw,
      runs: read.runs,
    });
  };
  useEffect(() => {
    void load();
    return () => {
      // 바뀌거나 내려간 뒤의 답은 버린다.
      asked.current += 1;
    };
    // load 는 port·runId·year 로만 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, runId, year]);

  const upload = (
    <div className="flex flex-wrap items-center gap-2">
      {uploadProblem !== null && (
        <p
          data-testid="s3-gate-problem"
          className="m-0 text-style-pre-caption-03 text-support-error-accent"
        >
          {uploadProblem}
        </p>
      )}
      <Button
        ref={uploadRef}
        variant="solidGrey"
        shape="square"
        size="sm"
        disabled={uploadDisabled}
        onClick={onUpload}
      >
        {words.upload}
      </Button>
    </div>
  );

  if (loaded.state === 'loading') return <LoadSkeleton label={words.loading} />;

  if (loaded.state === 'failed' || loaded.state === 'refused')
    return (
      <div
        role="alert"
        data-testid="s3-result-failed"
        className="flex flex-col items-start gap-4"
      >
        <PageInfo
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          className="w-full"
        >
          {loaded.state === 'refused' ?
            S3_TEXT.company[loaded.company]
          : words.loadFailed}
        </PageInfo>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={() => void load()}
          >
            {words.retryLoad}
          </Button>
          {upload}
        </div>
      </div>
    );

  if (loaded.state === 'rejected')
    return (
      <div
        role="alert"
        data-testid="s3-rejected"
        className="flex flex-col items-start gap-4"
      >
        <PageInfo
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          className="w-full"
        >
          {words.rejected[loaded.reason]}
        </PageInfo>
        {upload}
      </div>
    );

  const doneOf = (id: string | undefined) =>
    id === undefined ? undefined : loaded.runs.get(id);
  const cards = currentCards(loaded.year, doneOf);
  const rereadLine = rereadFailed && (
    <PageInfo
      role="alert"
      tone="error"
      icon={<CircleWarningIcon aria-hidden />}
      data-testid="s3-reread-failed"
    >
      {S3_TEXT.screen.reloadFailed}
    </PageInfo>
  );
  const openCard =
    opened === null ? null : cards.find((card) => card.id === opened);
  if (openCard && !openCard.off)
    return (
      <Card data-testid="s3-result-detail" className="flex flex-col gap-4">
        {rereadLine}
        <CategoryDetail
          port={port}
          year={year}
          operator={operator}
          done={doneOf(openCard.state?.current?.runId) ?? EMPTY_DONE}
          card={openCard}
          reread={reread}
          onBack={() => {
            setOpened(null);
            setBackTo(openCard.id);
          }}
        />
      </Card>
    );
  // 시트 수는 지금 결과(핀이 섞여도 카드와 같은 수), AI 호출 수만 마지막 실행.
  const failedSheets = currentFailedSheets(loaded.year);
  const failedLlmCalls =
    loaded.last === null ? 0 : summarize(loaded.last).failedLlmCalls;
  const problems =
    failedSheets > 0 || failedLlmCalls > 0 ?
      words.problems(failedSheets, failedLlmCalls)
    : null;
  const scopeTotal = currentTotal(loaded.year);
  return (
    <Card data-testid="s3-result" className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <p
          data-testid="s3-scope-total"
          className="m-0 flex flex-wrap items-baseline gap-2"
        >
          <span className="text-style-pre-body-06 text-text-secondary">
            {words.scopeTotalLabel}
          </span>
          <span className="flex items-baseline gap-1">
            <span className="text-style-pre-heading-02 text-text-primary">
              {emissionText(scopeTotal, words.empty)}
            </span>
            {scopeTotal !== null && (
              <span className="text-style-pre-caption-03 text-text-secondary">
                {EMISSION_UNIT}
              </span>
            )}
          </span>
          {scopeTotal !== null && failedSheets > 0 && (
            <span
              data-testid="s3-scope-missing"
              className="text-style-pre-caption-03 text-support-error-accent"
            >
              {words.scopeTotalMissing(failedSheets)}
            </span>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {upload}
          <Button
            ref={downloadButton}
            variant="solidBlack"
            shape="square"
            size="sm"
            data-testid="s3-download-open"
            onClick={() => setDownloading(true)}
          >
            {words.download}
          </Button>
        </div>
      </div>
      {downloading && (
        <Scope3DownloadDialog
          port={port}
          year={year}
          returnFocus={() => downloadButton.current}
          onClose={() => setDownloading(false)}
        />
      )}
      {rereadLine}
      {loaded.rejected !== null && (
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="s3-rejected-banner"
        >
          {words.rejected[loaded.rejected]}
        </PageInfo>
      )}
      <PageInfo icon={<PageInfoIcon />} data-testid="s3-result-notice">
        {words.notice}
      </PageInfo>
      {problems !== null && (
        <PageInfo
          role="status"
          tone="caution"
          icon={<PageInfoIcon />}
          data-testid="s3-problems"
        >
          {problems}
        </PageInfo>
      )}
      <CardList key={year} risen={risen} rise={`${year}|${runId}`}>
        {(still) =>
          cards.map((card, order) => (
            <CategoryCard
              key={card.id}
              card={card}
              still={still}
              order={order}
              onOpen={() => setOpened(card.id)}
              buttonRef={(node) => {
                if (node) cardButtons.current.set(card.id, node);
                else cardButtons.current.delete(card.id);
              }}
            />
          ))
        }
      </CardList>
    </Card>
  );
}

/**
 * 카드 목록(밴드 DB3 — 감독 판단 7). 붙을 때 한 번 「이 해|실행이 이미 떠올랐는가」를 잡아 둔다(그 뒤 다시 읽기로 다시 그려도 안 바뀜 — 같은 노드).
 * 처음 붙으면 떠오르고, 붙은 뒤 ref 에 적는다. 상세 → [목록]으로 다시 붙으면 적힌 키와 같아 안 돎.
 */
function CardList({
  risen,
  rise,
  children,
}: {
  risen: { current: string | null };
  rise: string;
  children(still: boolean): ReactNode;
}) {
  // 붙은 때의 키만 적는다 — 해·실행이 바뀐 직후의 그리기(아직 앞 값)에서 새 키를 적으면 다음 붙음이 안 돈다.
  const [mounted] = useState(rise);
  const [still] = useState(() => risen.current === mounted);
  useEffect(() => {
    risen.current = mounted;
  }, [risen, mounted]);
  return (
    <ul className="m-0 grid list-none grid-cols-5 gap-4 p-0">
      {children(still)}
    </ul>
  );
}

/** 카드 한 장. C10(1차 끔)은 표시만, 나머지는 단추(누르면 상세). */
function CategoryCard({
  card,
  onOpen,
  buttonRef,
  still,
  order,
}: {
  card: CurrentCard;
  onOpen(): void;
  buttonRef: Ref<HTMLButtonElement>;
  /** 떠오르지 않음(상세 → [목록]). */
  still: boolean;
  /** 카드 차례(지연 — 카드마다 40ms, 상한 400). */
  order: number;
}) {
  const { kind: state, partial } = cardState(card);
  // 단추 안에는 글줄 요소만 둘 수 있어 S3W2a 의 h4·p 를 같은 꼴의 span(block)으로 옮겼다. 글꼴·간격은 S3W2c ② e6 대조 1–5.
  const body = (
    <>
      {state !== 'off' && (
        <ChevronRightIcon
          aria-hidden
          className="absolute right-4 top-6 size-5 text-text-tertiary"
        />
      )}
      {/* S3W2c ② e6 대조 5: 제목·이름 한 묶음(gap 6) · 합 줄·「총 배출량」·꼬리 줄 한 묶음(가운데, gap 2). */}
      <span className="flex flex-col gap-1.5">
        <span className="flex items-center gap-2 text-style-pre-heading-02 text-text-primary">
          {words.cardTitle(card.number)}
          <LockMark locked={card.state?.locked ?? false} />
        </span>
        <span className="block text-style-pre-body-05 text-text-tertiary">
          {words.cards[card.id]}
          {/* 밴드 S3N1: 이름 옆 고정 안내(꺼진 카드 0 — 셈한 값이 없다). */}
          {state !== 'off' && <AdjustLaterMark category={card.id} />}
        </span>
      </span>
      <span className="flex flex-col items-center gap-0.5">
        <span
          data-testid="s3-card-total"
          className="flex items-baseline justify-center gap-1"
        >
          {state === 'value' ?
            <>
              <span className="text-style-pre-display-04 text-text-brand tabular-nums">
                <RollingValue
                  text={emissionText(card.total, words.empty)}
                  delay={cardRiseDelay(order)}
                  still={still}
                />
              </span>
              <span className="text-style-pre-body-05 text-text-tertiary">
                {EMISSION_UNIT}
              </span>
            </>
          : <span
              className={
                state === 'failed' ?
                  'text-style-pre-body-04 text-support-error-accent'
                : 'text-style-pre-display-04 text-text-quaternary'
              }
            >
              {state === 'failed' ? words.cardFailed : words.empty}
            </span>
          }
        </span>
        <span className="block text-center text-style-pre-caption-02 text-text-quaternary">
          {words.totalLabel}
        </span>
        {partial && (
          <span
            data-testid="s3-card-partial"
            className="block text-center text-style-pre-caption-03 text-support-error-accent"
          >
            {words.cardPartial(card.failedSheets)}
          </span>
        )}
        {card.hasBiogenic && state === 'value' && (
          <span
            data-testid="s3-card-biogenic"
            className="block text-center text-style-pre-caption-03 text-text-secondary"
          >
            {words.biogenicLabel}{' '}
            <span className="tabular-nums">
              <RollingValue
                text={emissionText(card.biogenic, words.empty)}
                delay={cardRiseDelay(order)}
                still={still}
              />
            </span>
            {card.biogenic !== null && ` ${EMISSION_UNIT}`}
          </span>
        )}
      </span>
    </>
  );
  const box =
    'relative flex min-h-[163px] w-full flex-col gap-3.5 rounded-component border border-border-tertiary px-6 py-6 text-left';
  return (
    <li
      data-testid="s3-result-card"
      data-category={card.id}
      data-state={state}
      data-partial={partial ? 'true' : undefined}
      className={still ? 'flex' : 'flex gw-m-rise'}
      style={
        still ? undefined : (
          ({ '--gw-m-delay': `${cardRiseDelay(order)}ms` } as CSSProperties)
        )
      }
    >
      {state === 'off' ?
        <div className={box}>{body}</div>
      : <button
          ref={buttonRef}
          type="button"
          onClick={onOpen}
          className={`${box} cursor-pointer border-solid bg-transparent hover:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-secondary`}
        >
          {body}
        </button>
      }
    </li>
  );
}
