// S3-01 Scope 3 첫 화면(밴드 S3W1 ② — 판 S3-01·01a [1차], Figma default 28023:7468). 고객사 사용자·운영 관리자 같은 화면·같은 흐름
// (작업 회사 — sid:MARC-ENT-374, 운영 관리자는 회사 거절·403 글만 다르다). 화면은 라우터·세션을 모른다(prop year·years·operator·port, 콜백 onYear).
//   - 머리: 제목 「온실가스 데이터」 → tabs 자리(경로 컴포넌트가 Scope 탭 줄을 넘긴다 — ③) → 연도(전년도부터 다섯).
//   - 그 해 마지막 실행(port.latest): 없음 → 기본 · 진행 중 → S3-07 창을 다시 띄움(재접속, 판 S3-07c) · 끝남 → 소개·Step 대신 S3-08 카드
//     (ResultView — 밴드 S3W2a Q5, 주소 칸 0) · 실패 → 실패 한 줄 + errorCode 갈래 글(S3W2a §1-6) + [배출량 재계산하기](file 갈래는
//     [데이터 업로드]) · 모름 → 한 줄. 끝남의 바깥 틀(data-testid s3-done)은 결과 읽는 중·실패·거절도 감싼다(app/ghg 경로 시험이 본다).
//   - H-3(밴드 GX3 ④ — 사용자 11-07, sid:MARC-ISSUE-583): 마지막 실행이 실패·진행·모름이어도 그 해 기준 실행(port.year baseRunId — 없으면 앞 판의
//     끝난 마지막 실행)이 있으면 카드·총합·잠금을 그대로 그리고, 실행 상태 줄은 카드 위 띠 자리에 둔다(첫 화면·[다음] 0). 진행 중이면 결과의 [데이터 업로드]는 막는다.
//     거절(done 안의 rejected)은 ResultView 가 같은 갈래로 그린다. 지금 결과가 없으면 앞 갈래 그대로.
//   - [다음] → S3-02 카테고리(화면 상태) → S3-03 올리기 → 실행이 서면 S3-07 창. 창을 닫으면 화면 안에 진행 글(판 S3-07b)과 [진행 보기].
//   - 폴링은 화면이 한다(창이 닫혀도 계속 — RUN_POLL_MS). 첫 값 전이든 뒤든 POLL_FAILURES 번 잇달아 못 읽으면 「진행 상태를 불러오지 못했어요」 —
//     그동안 [다음]은 막고(두 번째 실행 0) [다시 확인]이 그 해 마지막 실행을 다시 읽는다. 끝나면 그 해 마지막 실행을 다시 읽는다.
//   - 다시 계산은 누를 때의 해를 쥐고, 답이 왔을 때 해가 바뀌었으면 버린다(옛 해 실행이 새 해 화면에 붙지 않게).
//   - 첫 읽기 실패만 화면 자리(다시 시도), 다시 읽기(연도 바꿈·계산 끝) 실패는 notice 한 줄 — 앞 해의 실행은 보이지 않는다(sid:MARC-ISSUE-459 꼴).
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { RUN_POLL_MS } from '../../../entities/ghg-scope3/api/index.ts';
import type {
  CompanyRefusal,
  Scope3Port,
} from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  STEP_KEYS,
  failureKind,
  progressOf,
  runPhase,
  steps,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  CategoryId,
  Scope3Run,
  Scope3Stage,
} from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  LoadSkeleton,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { CategoryDialog } from './CategoryDialog.tsx';
import { ConfirmModal } from './ConfirmModal.tsx';
import { ProgressCount, ProgressDialog } from './ProgressDialog.tsx';
import type { ProgressView } from './ProgressDialog.tsx';
import { ResultView } from './ResultView.tsx';
import { UploadDialog } from './UploadDialog.tsx';
import { YearHint, useLatestResultYear } from './YearHint.tsx';

const words = S3_TEXT.screen;
/** 소개 구분 표 칸(값 파일 GX3 ② 고침 3). */
const INTRO_HEAD =
  'box-border h-10 border-0 border-b border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 font-medium text-text-tertiary';
const INTRO_CELL =
  'box-border h-14 border-0 border-b border-solid border-border-quaternary px-4 py-2 text-text-secondary';
const STEP_COUNT = STEP_KEYS.length;
/** 이만큼 잇달아 못 읽으면(첫 값 전 포함) 진행 상태를 잃은 것으로 본다(데이터 검증 RUN_POLL_FAILURES 와 같은 수). */
const POLL_FAILURES = 3;

export interface Scope3ScreenProps {
  port: Scope3Port;
  /** 주소의 연도(경로가 years 안으로 거른 값). */
  year: number;
  /** 고를 수 있는 연도(전년도부터 내림 — model yearsOf). */
  years: readonly number[];
  operator?: boolean;
  /** 제목 아래 Scope 탭 줄(경로 컴포넌트가 넘긴다). */
  tabs?: ReactNode;
  /** 폴링 간격(ms). 기본 RUN_POLL_MS(시험이 줄인다). */
  pollMs?: number;
  onYear(year: number): void;
}

type Loaded =
  | { state: 'loading' }
  | { state: 'failed' }
  | { state: 'refused'; company: CompanyRefusal }
  | {
      state: 'ready';
      year: number;
      last: Scope3Run | null;
      /** 마지막 실행이 끝나지 않았을 때(실패·진행·모름) 그 해 지금 결과의 기준 실행(H-3 — 있으면 카드를 그대로 그린다). */
      base: string | null;
    };

type Notice = 'reloadFailed' | { company: CompanyRefusal } | null;

/** 570 문을 어디서 지났나(읽기 실패 한 줄의 자리). */
type GateAt = 'result' | 'line' | 'start';

/** 띄운 경고: 고친 행 수 · 계속하면 할 일 · 취소면 돌아갈 일. */
interface Warning {
  rows: number;
  go(): void;
  back?: () => void;
  /** 누른 단추(취소면 초점이 돌아온다). */
  from: HTMLElement | null;
}

/** 지켜보는 실행: 받은 값(아직 없으면 null)·잇단 읽기 실패 수·잃음. */
interface Watch {
  runId: string;
  run: Scope3Run | null;
  failures: number;
  lost: boolean;
}

export function Scope3Screen({
  port,
  year,
  years,
  operator = false,
  tabs,
  pollMs = RUN_POLL_MS,
  onYear,
}: Scope3ScreenProps) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });
  const [notice, setNotice] = useState<Notice>(null);
  const [dialog, setDialog] = useState<'categories' | 'upload' | null>(null);
  const [chosen, setChosen] = useState<CategoryId[]>([]);
  const [watch, setWatch] = useState<Watch | null>(null);
  const [progressOpen, setProgressOpen] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryProblem, setRetryProblem] = useState<string | null>(null);
  const [warning, setWarning] = useState<Warning | null>(null);
  const [gateProblem, setGateProblem] = useState<GateAt | null>(null);
  const startRef = useRef<HTMLButtonElement>(null);
  const reopenRef = useRef<HTMLButtonElement>(null);
  /** S3-08·실패 줄의 [데이터 업로드](창이 닫히면 초점이 여기로). */
  const uploadRef = useRef<HTMLButtonElement>(null);
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    loaded.state === 'loading' ? 'loading'
    : loaded.state === 'failed' ? 'failed'
    : 'ready',
  );
  const hasList = useRef(false);
  const asked = useRef(0);
  /** 다시 계산을 보내는 중(두 번 누름 막음 — UploadDialog busyRef 꼴). */
  const retryingRef = useRef(false);
  /** 570 문이 답을 기다리는 해(그 해의 두 번 누름만 막는다 — 해를 바꾸면 새 해의 단추는 눌린다). */
  const gateRef = useRef<number | null>(null);
  /** 지금 화면의 해(다시 계산 답이 왔을 때 견준다). */
  const yearRef = useRef(year);
  yearRef.current = year;
  const yearBoxRef = useRef<HTMLDivElement>(null);

  /** 그 해 기준 실행 id(마지막 실행 자신이면 없음). 못 읽으면 없음. */
  const baseIdOf = async (from: number, lastId: string) => {
    const state = await port.year(from);
    if (state.kind !== 'ok') return null;
    const id = state.value.baseRunId;
    return id === null || id === lastId ? null : id;
  };

  /** 그 해 마지막 실행을 읽는다. 판이 없을 때(첫 읽기)만 실패가 화면 자리. 진행 중이면 창을 다시 띄운다(재접속). */
  const load = async () => {
    const ticket = ++asked.current;
    if (!hasList.current) setLoaded({ state: 'loading' });
    const out = await port.latest(year);
    if (ticket !== asked.current) return;
    if (out.kind === 'ok' || out.kind === 'none') {
      // latest 는 그 해 상태의 latest 다(GX5) — none 이면 그 해 후보가 없어 기준 실행도 없다(서버 base_run).
      const last = out.kind === 'ok' ? out.value : null;
      // 마지막 실행이 끝나지 않았으면 그 해 기준 실행을 본다(못 읽으면 없음 — 앞 갈래 그대로, H-3).
      const base =
        last === null || runPhase(last.status) === 'done' ?
          null
        : await baseIdOf(year, last.id);
      if (ticket !== asked.current) return;
      hasList.current = true;
      setLoaded({ state: 'ready', year, last, base });
      setNotice(null);
      if (last !== null && runPhase(last.status) === 'running') {
        setWatch({ runId: last.id, run: last, failures: 0, lost: false });
        setProgressOpen(true);
      } else setWatch((now) => (now?.lost ? null : now)); // [다시 확인] — 잃은 실행은 마지막 실행 판으로 갈음
      return;
    }
    if (!hasList.current)
      setLoaded(
        out.kind === 'refused' ?
          { state: 'refused', company: out.company }
        : { state: 'failed' },
      );
    else
      setNotice(
        out.kind === 'refused' ? { company: out.company } : 'reloadFailed',
      );
  };
  useEffect(() => {
    // 해가 바뀌면 앞 해의 실행은 그만 본다.
    setWatch(null);
    setProgressOpen(false);
    setRetryProblem(null);
    setWarning(null);
    setGateProblem(null);
    void load();
    // load 는 port·year 로만 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, year]);

  /** 지켜보는 실행의 폴링(처음은 곧바로, 그다음 pollMs). 끝나면 멈추고 그 해를 다시 읽는다. */
  const watchedId = watch?.runId ?? null;
  const watchedPhase =
    watch === null || watch.lost ? null
    : watch.run === null ? 'running'
    : runPhase(watch.run.status);
  useEffect(() => {
    if (watchedId === null || watchedPhase !== 'running') return;
    let stopped = false;
    const timer = setTimeout(
      async () => {
        const read = await port.run(watchedId);
        if (stopped) return;
        setWatch((now) => {
          if (now === null || now.runId !== watchedId) return now;
          if (read.kind === 'ok')
            return { ...now, run: read.value, failures: 0 };
          const failures = now.failures + 1;
          return {
            ...now,
            failures,
            lost: failures >= POLL_FAILURES,
          };
        });
      },
      watch?.run === null && watch.failures === 0 ? 0 : pollMs,
    );
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
    // watch 의 값이 바뀔 때마다 다음 한 번을 건다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, watch, pollMs]);

  /** 끝나면 창을 닫고 그 해를 다시 읽는다(「완료 했을시」). */
  useEffect(() => {
    if (watchedPhase !== 'done') return;
    // 끝난 실행을 먼저 그 해의 마지막으로 둔다 — 다시 읽기가 실패해도 앞 상태(진행·앞 실패)로 돌아가지 않는다(notice 만).
    const finished = watch?.run ?? null;
    if (finished !== null)
      setLoaded({ state: 'ready', year, last: finished, base: null });
    setWatch(null);
    setProgressOpen(false);
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchedPhase]);

  const retry = async (runId: string) => {
    if (retryingRef.current) return;
    retryingRef.current = true;
    const from = year;
    setRetrying(true);
    setRetryProblem(null);
    const out = await port.retry(runId);
    retryingRef.current = false;
    setRetrying(false);
    if (yearRef.current !== from) return;
    if (out.kind === 'ok') {
      setWatch({ runId: out.value.runId, run: null, failures: 0, lost: false });
      setProgressOpen(true);
      return;
    }
    setRetryProblem(
      out.kind === 'refused' ?
        S3_TEXT.company[out.company]
      : S3_TEXT.progressDialog.retryFailed,
    );
  };

  /**
   * 570 문 — 새 실행 길 여섯이 지나는 함수 하나. 누른 때 연도를 다시 읽어 잠기지 않은 고친 행이 있으면 경고 창, 없으면 바로,
   * 읽기 실패면 넘어가지 않고 그 단추 옆 한 줄(경고를 건너뛰어 말없이 잃지 않게). 막지는 않는다(sid:MARC-ENT-570). 해가 바뀌면 늦은 답은 버린다.
   */
  const throughGate = async (at: GateAt, go: () => void, back?: () => void) => {
    if (gateRef.current === year) return;
    gateRef.current = year;
    const from = year;
    const pressed = document.activeElement;
    setGateProblem(null);
    const read = await port.year(from);
    if (gateRef.current === from) gateRef.current = null;
    if (yearRef.current !== from) return;
    if (read.kind !== 'ok') {
      setGateProblem(at);
      back?.();
      return;
    }
    const rows = read.value.editedRowsUnlocked;
    if (rows > 0)
      setWarning({
        rows,
        go,
        ...(back ? { back } : {}),
        // 눌러도 초점이 안 가는 브라우저면 pressed 가 body 다 — 돌아올 자리가 아니라 물러선다.
        from:
          pressed instanceof HTMLElement && pressed !== document.body ?
            pressed
          : null,
      });
    else go();
  };
  /** 진행 창 위의 길: 창을 먼저 닫고 문을 지난다(겹친 창 초점). 취소면 진행 창으로. */
  const throughGateFromProgress = (go: () => void) => {
    setProgressOpen(false);
    void throughGate('line', go, () => setProgressOpen(true));
  };

  /** 빈 해 안내: 그 해 판이 섰고, 끝난 결과도 진행 중 실행도 없고, 지켜보는 실행이 없을 때(처분 K4). */
  const settled = loaded.state === 'ready' && loaded.year === year;
  const lastPhase =
    settled && loaded.last !== null ? runPhase(loaded.last.status) : null;
  const hintYear = useLatestResultYear(
    port,
    year,
    years,
    settled &&
      watch === null &&
      lastPhase !== 'done' &&
      lastPhase !== 'running',
  );

  const head = (
    <>
      <PageTitle title={words.title} headingRef={retryFocus.doneRef} />
      {tabs}
    </>
  );

  if (loaded.state === 'refused')
    return (
      <div data-screen="ghg-scope3" className="flex flex-col gap-6">
        {head}
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="company-refusal"
        >
          {S3_TEXT.company[loaded.company]}
        </PageInfo>
      </div>
    );

  if (loaded.state !== 'ready')
    return (
      <div data-screen="ghg-scope3" className="flex flex-col gap-6">
        {head}
        {loaded.state === 'loading' ?
          <LoadSkeleton label={words.loading} />
        : <div
            role="alert"
            data-testid="load-failure"
            className="flex flex-col items-start gap-4"
          >
            <PageInfo
              tone="error"
              icon={<CircleWarningIcon aria-hidden />}
              className="w-full"
            >
              {words.loadFailed}
            </PageInfo>
            <Button
              ref={retryFocus.actionRef}
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={retryFocus.arm(() => void load())}
            >
              {words.retryLoad}
            </Button>
          </div>
        }
      </div>
    );

  // 다시 읽기가 실패해 앞 해의 판이 남았으면 그 실행은 보이지 않는다.
  const last = loaded.year === year ? loaded.last : null;
  const shown = watch?.run ?? (watch === null ? last : null);
  const phase =
    watch !== null ?
      watch.lost ?
        'lost'
      : watchedPhase
    : shown === null ? null
    : runPhase(shown.status);
  const stage: Scope3Stage =
    dialog === 'categories' ? 'categories'
    : dialog === 'upload' ? 'upload'
    : phase === 'done' ? 'done'
    : phase === 'running' || phase === 'failed' || phase === 'lost' ? 'running'
    : 'idle';
  const progressView: ProgressView =
    phase === 'failed' ? 'failed'
    : phase === 'lost' ? 'lost'
    : 'running';
  const progress = progressOf(watch?.run?.steps ?? []);
  const noticeText =
    notice === null ? null
    : typeof notice === 'object' ? S3_TEXT.company[notice.company]
    : words.reloadFailed;
  const failedId = phase === 'failed' ? (shown?.id ?? null) : null;
  const failure = failureKind(shown?.errorCode ?? null);
  const doneId = phase === 'done' && shown !== null ? shown.id : null;
  // 마지막 실행이 실패·진행·모름이어도 그 해 지금 결과가 있으면 카드를 그린다(H-3 — 안내는 카드 위 띠).
  const baseId =
    doneId !== null || loaded.state !== 'ready' || loaded.year !== year ?
      null
    : (loaded.base ??
      (loaded.last !== null && runPhase(loaded.last.status) === 'done' ?
        loaded.last.id
      : null));
  const resultId = doneId ?? baseId;
  const openUpload = () => {
    setProgressOpen(false);
    setDialog('categories');
  };
  const backFocus = () => startRef.current ?? uploadRef.current;
  const gateText = S3_TEXT.rerunWarning.readFailed;
  /** 실패 줄·진행 창의 단추 옆 한 줄. */
  const lineProblem =
    retryProblem ?? (gateProblem === 'line' ? gateText : null);

  /** 실행 상태 줄(진행·모름·잃음·실패). 지금 결과 카드가 있으면 카드 위 띠 자리에(H-3), 없으면 첫 화면 아래 앞 자리에. */
  const statusLines = (
    <>
      {phase === 'running' && !progressOpen && (
        <div
          data-testid="s3-running"
          className="flex flex-col items-center gap-2 text-center"
        >
          <div role="status" className="flex flex-col gap-2">
            <p className="m-0 text-style-pre-heading-02 text-text-secondary">
              {words.runningTitle}
            </p>
            <p className="m-0 text-style-pre-body-06 text-text-tertiary">
              {words.runningBody[0]}
              <br />
              {words.runningBody[1]}
            </p>
          </div>
          <ProgressCount progress={progress} />
          <Button
            ref={reopenRef}
            variant="outlineBlack"
            shape="round"
            size="md"
            onClick={() => setProgressOpen(true)}
          >
            {words.openProgress}
          </Button>
        </div>
      )}
      {(phase === 'unknown' || (phase === 'lost' && !progressOpen)) && (
        <div
          role="status"
          data-testid="s3-unknown"
          className="flex flex-wrap items-center gap-3"
        >
          <p className="m-0">
            {phase === 'lost' ?
              S3_TEXT.progressDialog.pollFailed
            : words.unknownLine}
          </p>
          {phase === 'lost' && (
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={() => void load()}
            >
              {words.recheck}
            </Button>
          )}
        </div>
      )}
      {phase === 'failed' && !progressOpen && failedId !== null && (
        <div
          role="alert"
          data-testid="s3-failed"
          className="flex flex-wrap items-center gap-3"
        >
          <p className="m-0 text-style-pre-body-04 text-text-primary">
            {words.failedLine}
          </p>
          <p
            data-testid="s3-failed-body"
            data-failure={failure}
            className="m-0 w-full text-style-pre-body-06 text-text-secondary"
          >
            {S3_TEXT.progressDialog.failureBody[failure]}
          </p>
          {/* setup(설정 없음)은 다시 계산해도·다시 올려도 풀리지 않아 단추 0(S3W2c ② e6 대조 11). */}
          {failure === 'setup' ?
            null
          : failure === 'file' ?
            <Button
              // 카드가 있으면 결과의 [데이터 업로드]가 초점 자리(같은 ref 를 둘이 쥐지 않는다 — H-3).
              ref={resultId === null ? uploadRef : undefined}
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={() => void throughGate('line', openUpload)}
            >
              {S3_TEXT.result.upload}
            </Button>
          : <Button
              variant="solidBlack"
              shape="round"
              size="md"
              loading={retrying}
              onClick={() =>
                void throughGate('line', () => void retry(failedId))
              }
            >
              {S3_TEXT.progressDialog.retry}
            </Button>
          }
          {lineProblem !== null && (
            <p
              data-testid="s3-retry-problem"
              className="m-0 text-style-pre-caption-03 text-support-error-accent"
            >
              {lineProblem}
            </p>
          )}
        </div>
      )}
    </>
  );

  return (
    <div data-screen="ghg-scope3" className="flex flex-col gap-6">
      {head}
      <div ref={yearBoxRef} className="flex flex-wrap items-center gap-2">
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
      {noticeText !== null && (
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="s3-notice"
        >
          {noticeText}
        </PageInfo>
      )}
      {baseId !== null && statusLines}
      {resultId !== null && (
        <div data-testid="s3-done">
          <ResultView
            port={port}
            runId={resultId}
            uploadDisabled={phase === 'running' || phase === 'lost'}
            year={year}
            operator={operator}
            uploadRef={uploadRef}
            onUpload={() => void throughGate('result', openUpload)}
            uploadProblem={gateProblem === 'result' ? gateText : null}
          />
        </div>
      )}
      {resultId === null && (
        <>
          <Card className="flex flex-col gap-4">
            {hintYear !== null && (
              <YearHint
                year={year}
                to={hintYear}
                onGo={() => {
                  onYear(hintYear);
                  // 띠가 사라져 초점 돌아올 자리가 없다 — 연도 고르기로.
                  yearBoxRef.current?.querySelector('select')?.focus();
                }}
              />
            )}
            {/* 소개 머리·글(값 파일 GX3 ② 고침 2 — 판 S3-01 `.f-card .head`): 주황 머리 ↔ 12 ↔ 한 문단 두 줄. */}
            <div className="flex flex-col gap-3">
              <h3
                data-testid="s3-intro-title"
                className="m-0 text-style-pre-heading-02 text-support-orange"
              >
                {words.introTitle}
              </h3>
              <p className="m-0 text-style-pre-body-03 text-text-secondary">
                {words.intro.map((line, index) => (
                  <span key={line}>
                    {index > 0 && <br />}
                    {line}
                  </span>
                ))}
              </p>
            </div>
            {/* 구분 표(고침 3): 머리 40 회색 · 줄 최소 56 · 「구분」 200 왼쪽, 「의미」·「예시」 반씩 가운데. */}
            <table
              aria-label={words.tableLabel}
              className="w-full table-fixed border-collapse border-0 border-t border-solid border-border-tertiary text-style-pre-body-06"
            >
              <thead>
                <tr>
                  <th
                    scope="col"
                    className={`${INTRO_HEAD} w-[200px] text-left`}
                  >
                    {words.columns.scope}
                  </th>
                  <th scope="col" className={`${INTRO_HEAD} text-center`}>
                    {words.columns.meaning}
                  </th>
                  <th scope="col" className={`${INTRO_HEAD} text-center`}>
                    {words.columns.example}
                  </th>
                </tr>
              </thead>
              <tbody>
                {words.rows.map((row) => (
                  <tr key={row.scope}>
                    <td className={`${INTRO_CELL} text-left`}>{row.scope}</td>
                    <td className={`${INTRO_CELL} text-center`}>
                      {row.meaning}
                    </td>
                    <td className={`${INTRO_CELL} text-center`}>
                      {row.example}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="m-0 text-style-pre-body-06">{words.categoryNote}</p>
          </Card>
          <Card className="flex flex-col gap-6">
            <h3 className="m-0 text-style-pre-heading-02 text-text-secondary">
              {words.processTitle}
            </h3>
            {/* Step 줄(고침 4·5 — 판 S3-01 `.f-steps`·S3-01a `.f-step.done`): 위 주황 막대 4 · 라벨 줄 · 줄 2 · 이름 줄 · 아래 막대 4. */}
            <div className="flex flex-col">
              <div aria-hidden className="h-1 bg-support-orange" />
              <ol
                data-testid="s3-steps"
                className="m-0 grid list-none grid-cols-4 gap-0 p-0"
              >
                {steps(stage).map((step, index) => (
                  <li
                    key={step.key}
                    data-step={step.key}
                    data-done={step.done ? 'true' : 'false'}
                    className="relative flex flex-col"
                  >
                    <span
                      className={`flex items-center gap-2 px-3 py-2 text-style-pre-body-04 ${
                        step.done ?
                          'text-text-quaternary'
                        : 'text-text-secondary'
                      }`}
                    >
                      {words.stepPrefix(index + 1)}
                      {step.done && (
                        <span
                          data-testid="s3-step-done"
                          className="inline-flex h-5 items-center rounded-control bg-support-blue-subtle px-1 text-style-pre-caption-02 text-support-blue-dark"
                        >
                          {words.stepDone}
                        </span>
                      )}
                    </span>
                    <span
                      aria-hidden
                      className="h-0.5 bg-background-tertiary"
                    />
                    <span
                      className={`px-3 py-2 text-style-pre-body-01 ${
                        step.done ?
                          'text-text-quaternary'
                        : 'text-support-orange'
                      }`}
                    >
                      {S3_TEXT.steps[step.key]}
                    </span>
                    {/* 화살표는 그 Step 칸 오른쪽 끝 안(Figma 28150:5877 — 칸 418 중 x 394~418, GX4 ③). 경계에 걸치지 않는다. */}
                    {index < STEP_COUNT - 1 && (
                      <span
                        aria-hidden
                        data-testid="s3-step-arrow"
                        className="absolute right-0 top-1/2 z-[1] box-border flex size-6 -translate-y-1/2 items-center justify-center rounded-full border-2 border-solid border-text-tertiary bg-background-primary text-text-tertiary"
                      >
                        <ChevronRightIcon className="size-4" />
                      </span>
                    )}
                  </li>
                ))}
              </ol>
              <div aria-hidden className="h-1 bg-background-quaternary" />
            </div>
          </Card>
        </>
      )}
      {baseId === null && statusLines}
      {resultId === null && (
        <div className="flex items-center justify-end gap-2">
          {gateProblem === 'start' && (
            <p
              data-testid="s3-gate-problem"
              className="m-0 text-style-pre-caption-03 text-support-error-accent"
            >
              {gateText}
            </p>
          )}
          <Button
            ref={startRef}
            variant="solidBlack"
            shape="round"
            size="md"
            disabled={phase === 'running' || phase === 'lost'}
            onClick={() =>
              void throughGate('start', () => setDialog('categories'))
            }
          >
            {words.start}
          </Button>
        </div>
      )}
      {dialog === 'categories' && (
        <CategoryDialog
          initial={chosen}
          returnFocus={backFocus}
          onConfirm={(next) => {
            setChosen(next);
            setDialog('upload');
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'upload' && (
        <UploadDialog
          port={port}
          year={year}
          chosenCount={chosen.length}
          operator={operator}
          returnFocus={backFocus}
          onStarted={(runId) => {
            setDialog(null);
            setRetryProblem(null);
            setWatch({ runId, run: null, failures: 0, lost: false });
            setProgressOpen(true);
          }}
          onClose={() => setDialog(null)}
        />
      )}
      {progressOpen && watch !== null && (
        <ProgressDialog
          progress={progress}
          view={progressView}
          failure={failure}
          retrying={retrying}
          retryProblem={lineProblem}
          returnFocus={() => reopenRef.current ?? backFocus()}
          onRetry={() =>
            throughGateFromProgress(() => {
              setProgressOpen(true);
              void retry(watch.runId);
            })
          }
          onUpload={() => throughGateFromProgress(openUpload)}
          onClose={() => setProgressOpen(false)}
        />
      )}
      {warning !== null && (
        <ConfirmModal
          testId="s3-rerun-warning"
          title={S3_TEXT.rerunWarning.title(warning.rows)}
          cancel={S3_TEXT.rerunWarning.cancel}
          confirm={S3_TEXT.rerunWarning.confirm}
          initialFocus="cancel"
          returnFocus={() =>
            warning.back ? null : (warning.from ?? backFocus())
          }
          onConfirm={() => {
            setWarning(null);
            warning.go();
          }}
          onClose={() => {
            setWarning(null);
            warning.back?.();
          }}
        />
      )}
    </div>
  );
}
