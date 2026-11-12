// GW-05 문장 검토 + 05a 제외 사유 · 05b 확정 확인 · 05c 잠긴 상태(밴드 FW2 ④). 시안 GW-05_r1·05a·05b·05c_r1(캔버스 v76)의 구성:
//   제목 줄(「문장 검토」 + 상태 배지, meta 「파일명 · n문장」, [요약으로] · [확정] → 05b) → StepFlow STEP 3 → (05c: 잠금 띠) →
//   파트 탭(전체 n · 파트별 n) → 세 칸: 왼쪽 목록(검토 n/전체 막대 · 「채택 n · 제외 n · 미검토 n」 · 등급 박스 탭 · 문장 줄) /
//   가운데 쪽(ReviewPagePane) / 오른쪽 상세(등급 · 파트 · 쪽과 근거 쪽, 인용, 근거 확인(「근거에서 확인됨」만), 판정 사유, 수정 방향, 검토 줄).
//   v115 GW-05_r2·05c_r2 에서 뺀 것(sid:MARC-ENT-354·366, 밴드 GW2R ①): 위험 유형 칸, 「빠진 근거」(보완할 정보) 줄, 예시 문장(대체표현) 칸.
// 셈은 domain(joinReview·reviewTally·filterReviewRows·excludeReasonText), 읽기·쓰기는 headless(useResult·useReview).
// 잠금 띠의 확정한 사람은 검토의 confirmedBy 에서 읽는다(밴드 WC1 ① — 목록 원재료를 다시 읽지 않는다).
//   - 채택·제외는 PUT 이 끝난 뒤 반영된다(useReview). 본문은 늘 marks 전부 [B3].
//   - 05a: 사유 글은 excludeReasonText(사유 이름 [+ 「: 설명」]). 「기타」 + 빈 설명이면 모달 안 설명 칸 아래 오류(지은 글).
//   - 05b: 미검토 n개 경고. [확정]은 미검토를 채택으로 채운 marks 전부 + state confirmed(confirmUpdate, 메모 gw-a-05d).
//   - GW-04 [확정]으로 들어오면 05b 가 열린 채 시작한다(initialConfirm — 경로 컴포넌트(app/greenwash/GreenwashRoutes)가 메모리의 한 번 쓰는 표식으로 넘긴다. 주소·history.state 에는 싣지 않는다).
//   - 05c: 버튼 숨김, LockBanner(확정 일시 + 확정한 사람 — 계약에 사람 칸이 없어 목 값), 등급 탭 마지막은 「제외」, 검토 줄은 「확정됨 · 바꿀 수 없음」,
//     제목 줄 [요약으로] · [내려받기](밴드 GDL1 — GW-05c r4, 옛 [엑셀 내보내기 · 확정본]을 갈음: 받기 모달의 「점검 결과 엑셀 · 확정본」 한 줄,
//     ?confirmed=true 로 store.getReport, 실패는 그 줄 아래 role="alert").
// 시안과 다른 자리(보고에): 상태 배지는 meta 가 아니라 제목 줄(GW-04 와 같은 자리 — PageTitle 의 설명은 <p> 라 배지 div 를 넣지 못한다),
//   근거 확인은 「근거에서 확인됨」이 비면 칸째 숨긴다.
// 불러오기(밴드 LE1, sid:MARC-ENT-260, 시안 CM-03): 결과·검토 둘을 읽는 동안 제목 줄([요약으로] 그대로)·STEP 3 + 본문 자리 스켈레톤 하나(300ms 뒤).
//   스켈레톤은 받은 뒤 꼴을 닮은 ReviewSkeleton(파트 탭 줄 + 세 칸 — 밴드 GL2).
//   읽는 동안 내내(스켈레톤 300ms 전에도) 화면 바깥 틀에 aria-busy(밴드 LA1 ①). 스켈레톤 카드는 role="status" 만.
//   둘 중 하나라도 실패면 본문 전체 실패 꼴(먼저 걸린 쪽의 글 — 결과가 먼저), [다시 시도]는 실패한 쪽 전부를 다시 읽는다
//   (결과가 실패면 검토도 실패·꼴 오류일 때 함께 — 한 번에. 밴드 LA1 ②). 없음은 회색 + [목록으로] 하나.
//   실패·없음에서는 제목 줄 [요약으로]를 숨기고 상자의 [목록으로](onList)로 나간다(결과가 실패·없음이면 GW-04 도 열리지 않는다.
//   검토만 실패면 GW-04 는 열리나 [목록으로] 하나로 둔다).
//   [다시 시도] 뒤 초점(밴드 LA1 ②, useRetryFocus): 또 실패·없음이면 상자의 첫 단추, 받으면 본문(또는 dry-run)의 제목 줄 h2(tabIndex -1).
//   결과가 dry-run 이면 검토 읽기 상태와 무관하게 dry-run 안내(서버 GET review 는 dry-run 에 404·501 일 수 있다 — 추정).
// 확정 저장이 실패해도 05b 를 닫는다(본문의 save-error 가 보이게). 저장을 시도하지 않은 false(저장 중)면 그대로.
// 밴드 GW2R ②(v115 GW-05b_r2, sid:MARC-ISSUE-228 S3·S4, 227 ②):
//   - 확정 전 다시 읽기가 어긋나면(stale) 05b 를 닫지 않고 모달 안 오류 줄 + [새로 불러오기] + 꺼진 [확정](본문의 stale 줄은 없앴다).
//     [새로 불러오기]가 실패하면(reload_failed) 같은 자리 글만 「새로 불러오지 못했어요. …」, 보던 검토는 그대로, [확정]은 계속 꺼짐.
//   - 「이미 확정된 점검이에요」 줄은 잠금 띠가 보이면(확정) 그리지 않는다(같은 말 겹침 — S4, 디자인 답 D5).
//   - 「자동 저장됨 HH:MM」: 이 탭에서 검토 PUT 이 받아들여진 마지막 때(useReview.savedAt), 확정이면 없음(디자인 답 D2).
// 밴드 G1b-3 ③(GW-05_r2·05c_r2 — 등급·판정 사유·수정 방향 고침, review@2):
//   - 목록·상세·등급 탭·05a·쪽 칸의 등급은 보이는 값(고친 값 ?? AI — domain joinReview). 고친 문장 줄에 「고침」, tally 에 「고친 문장 n」
//     (고친 문장이 있을 때만, 확정 뒤는 05c 처럼 없음).
//   - 상세: 「등급 [▾]」 고르면 바로 저장(같은 등급이면 저장 안 함) · 판정 사유·수정 방향 [고치기] → 글 칸(「고치는 중 · 칸을 벗어나면 저장돼요」),
//     칸을 벗어나면(blur) 저장 — 판정 사유는 한 줄 = 한 항목(domain reasonsFromText). 값이 보이는 값과 같으면 저장 없이 닫는다.
//     저장되면 닫고, 안 되면(400·저장 중 거절 뒤 다시 보낸 것도 실패) 칸을 연 채 글을 남긴다(오류는 위 save-error 줄).
//   - 고친 칸마다 「고침」과 「AI 원래 판단 보기 · 고친 사람 · 시각」 접기(세 칸 각각). 05c 는 고르기·[고치기] 없이 「고침」·접기만 남고,
//     고친 칸 제목 옆에 「확정해서 잠김 · AI 원래 판단은 엑셀에 함께 담겨요」(05c_r2 :94).
//   - 고치기는 채택·제외와 같이 canWrite 일 때만(로그인하지 않은 세션만 거짓 — 운영 관리자도 고친다, sid:MARC-ENT-409).
// 저장 경합(밴드 GR1, sid:MARC-ISSUE-281 — 디자인 e9 답):
//   - 저장 중에는 [채택]·[제외]·머리 [확정]을 끄고 목록 머리 끝 토막을 「저장하고 있어요」로 둔다(고치던 칸의 blur 저장이 누름보다 먼저
//     떠서 누름이 소리 없이 버려지던 것). 그래도 저장 중에 들어간 누름(끌 수 없는 갈래)은 「저장 중이에요」를 잠깐 보인다(busyRefusals).
//   - 고치던 중 다른 문장을 고르고 그 blur 저장이 안 되면 쓰던 글을 그 문장의 고침 글로 남기고 그 문장으로 돌아간다(연 칸에 되살린다).
// 서비스 화면 값(밴드 GP2 개정 1 — GW3R2 대조 SC1·SC13·SC14, 시안이 정본): 작은 회색 글 400(pre-caption-03), 문장 줄 왼쪽 막대 3px,
//   「검토 n/m」 700(시안 13 — 13 토큰이 없어 크기는 14 그대로 pre-body-04). 세 칸 폭(SC12)은 341 과 부딪혀 사용자 판단 대기.
// 근거 고치기·재판단(밴드 GRJ1 ③ — 시안 GW-05 r4 ①~④·r5, 결정 MARC-ENT-617). 셈은 domain(basisOf·shownValues·nothingToRejudge·
//   evidenceNow — 보이는 값 = 고침 ?? 기준 판단 ?? 첫 판단), 저장·재판단·도는 중 다시 읽기는 useReview.
//   - 근거 칸(EvidenceEditor): [고치기] → [지우기]/[되살리기]·[+ 근거 더하기], 바뀔 때마다 PUT evidence(밴드 GRJ2), 칸을 벗어나면 닫는다. 근거 없는 문장도 고칠 수 있으면 칸.
//   - [재판단]: 등급 줄 끝(outlineGrey round sm ↻). 켜짐 = 고칠 수 있음 + 도는 중 아님 + 지금 근거 ≠ 기준 판단 근거. 꺼지면 title 에 hover 글.
//     근거 칸 아래 바뀜 한 줄. 도는 중: 등급·사유·수정 방향 뼈대 + 진행 한 줄 + 「재판단 중…」, 목록 줄 돌림 표시.
//   - 끝난 뒤: 등급 줄 아래 「재판단 · MM-DD HH:MM · 이름」, 카드 맨 아래 「AI 첫 판단 보기」, 목록 「재판단」 딱지.
//     리스크 아님(r5): 등급 자리 「리스크 아님」 회색 딱지 + 한 줄(등급 고르기 없음 — 제외로 표시), 등급 탭 High·Mid·Low 에 걸리지 않는다.
//   - ③ 고친 칸: 고친 뒤 재판단이 끝났으면 칸 머리 「AI 판단이 바뀌었어요」, 「AI 원래 판단 보기」 안은 기준 판단(새 AI 값).
//   - 실패: 빨간 한 줄 + [다시 시도](근거 고침은 남는다). 확정 뒤 [고치기]·[재판단] 없음.
//   - 쪽 칸 상자: 리스크 아님이면 첫 판단 등급 색으로 둔다(쪽 칸에 회색 상자가 없다 — 보고 물을 거리).
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { MutableRefObject, ReactNode, Ref } from 'react';

import {
  CircleWarningIcon,
  LockIcon,
  RefreshIcon,
  SpinnerIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  useResult,
  useReview,
} from '../../../entities/greenwash/hooks/index.ts';
import type { ReviewHandle } from '../../../entities/greenwash/hooks/index.ts';
import {
  LEVELS,
  aiChangedSince,
  evidenceNow,
  excludeReasonText,
  filterReviewRows,
  formatKst,
  formatKstMonthDay,
  formatKstTime,
  isScanResult,
  joinReview,
  nothingToRejudge,
  reasonsFromText,
  reasonsText,
  reviewTally,
} from '../../../entities/greenwash/model/index.ts';
import type {
  Basis,
  EditChange,
  EvidenceChange,
  GreenwashReview,
  Level,
  ReviewEditedFix,
  ReviewEditedLevel,
  ReviewEditedReasons,
  ReviewRow,
  ReviewTab,
  ReviewTally,
  ScanResult,
} from '../../../entities/greenwash/model/index.ts';
import {
  AiOriginal,
  ConfirmReviewDialog,
  EditedMark,
  ExcludeReasonDialog,
  GwDownloads,
  LevelPicker,
  LoadFailure,
  LockBanner,
  NonRiskBadge,
  RejudgedMark,
  ReviewChoice,
  ReviewMark,
  RiskBadge,
  RunStatusBadge,
  StepFlow,
  partName,
} from '../../../entities/greenwash/ui/index.ts';
import type {
  ExcludeReasonValue,
  ReviewPick,
  RiskLevel,
  RunStatus,
} from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { SkeletonBar } from '../../../shared/ui/skeleton-bar/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { EvidenceEditor } from './EvidenceEditor.tsx';
import type { EvidenceDraft } from './EvidenceEditor.tsx';
import { ReviewPagePane } from './ReviewPagePane.tsx';
import { ReviewSkeleton } from './ReviewSkeleton.tsx';

const words = GW_TEXT.reviewScreen;
const say = words.rejudge;

const RISK: Record<Level, RiskLevel> = { High: 'high', Mid: 'mid', Low: 'low' };
/** 「저장 중이에요」 알림이 보이는 동안(ms). */
const BUSY_NOTICE_MS = 3000;

/** 쪽 칸·상세 칸 sticky 의 위 틈(px, sid:MARC-ISSUE-341 — 디자인 2e). 앱 셸 머리(64)는 sticky 가 아니라 스크롤하면 사라지므로
 *  머리 높이가 아니라 본문 위 안쪽 24(AppShell main 의 pt-6 — 셸이 값을 내보내지 않아 여기 하나)를 쓴다. 칸 높이는 뷰포트 − 위아래 틈. */
const STICKY_GAP = 24;
const STICKY_STYLE = {
  top: STICKY_GAP,
  maxHeight: `calc(100dvh - ${STICKY_GAP * 2}px)`,
};

/** 고치는 중인 칸과 그 글. */
interface EditDraft {
  column: 'reasonBullets' | 'fixParagraph';
  text: string;
}
const LEVEL_OF: Record<RiskLevel, Level> = {
  high: 'High',
  mid: 'Mid',
  low: 'Low',
};

export interface ReviewScreenProps {
  store: GreenwashStore;
  openPdf: OpenPdf;
  runId: string;
  /** 참이면 05b(확정 확인)를 연 채 시작한다(GW-04 [확정]으로 들어온 길). 확정된 검토면 열지 않는다. */
  initialConfirm?: boolean;
  /** [요약으로] → GW-04. */
  onBack(): void;
  /** 실패·없음 꼴의 [목록으로] → GW-01. */
  onList(): void;
  /** 거짓이면 머리 [확정]과 상세의 채택·제외를 숨긴다(로그인하지 않은 세션 — 운영 관리자도 고객사 사용자와 같이 쓴다, sid:MARC-ENT-409). 확정 잠금은 그대로. 기본 참. */
  canWrite?: boolean;
}

export function ReviewScreen({
  store,
  openPdf,
  runId,
  initialConfirm = false,
  onBack,
  onList,
  canWrite = true,
}: ReviewScreenProps) {
  const { status: result, retry: retryResult } = useResult(store, runId);
  const review = useReview(store, runId);

  const back = (
    <Button variant="outlineGrey" shape="round" size="md" onClick={onBack}>
      {words.back}
    </Button>
  );

  const failure = readFailure(result.state, review.status.state);
  const skeleton = useDelayed(failure.state === 'loading');
  // dry-run 은 ready(제목 줄 h2 로). 없음·꼴 오류·실패는 모두 상자(첫 단추)로 — 초점 훅에는 failed 하나
  const dryRun = result.state === 'ready' && !isScanResult(result.result);
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    dryRun || failure.state === 'ready' ? 'ready'
    : failure.state === 'loading' ? 'loading'
    : 'failed',
  );
  // [다시 시도]: 실패한 쪽 전부. 결과가 실패면 검토도 실패·꼴 오류일 때 함께(검토가 읽는 중·있음·없음이면 결과만)
  const retryFailed = retryFocus.arm(() => {
    if (failure.side === 'review') {
      review.retry();
      return;
    }
    retryResult();
    if (review.status.state === 'failed' || review.status.state === 'invalid')
      review.retry();
  });

  // dry-run 은 검토 읽기 상태보다 먼저 본다(디자인 의심 (a)).
  if (dryRun)
    return (
      <div
        data-screen="review"
        data-review-state="dry-run"
        className="flex flex-col gap-6"
      >
        <PageTitle
          title={words.title}
          actions={back}
          headingRef={retryFocus.doneRef}
        />
        <PageInfo icon={<PageInfoIcon />} data-testid="dry-run">
          {GW_TEXT.result.dryRun}
        </PageInfo>
      </div>
    );

  if (
    failure.state !== 'ready' ||
    result.state !== 'ready' ||
    review.status.state !== 'ready'
  )
    return (
      <div
        data-screen="review"
        data-review-state={failure.state}
        aria-busy={failure.state === 'loading' || undefined}
        className="flex flex-col gap-6"
      >
        {failure.state === 'loading' || failure.state === 'ready' ?
          <>
            {/* 제목은 받은 뒤와 같다. 설명(파일 이름·문장 수)만 막대 자리(밴드 GL1, sid:MARC-ENT-443 ③) */}
            <PageTitle title={words.title} descriptionPending actions={back} />
            <StepFlow current={3} />
            {skeleton && <ReviewSkeleton label={words.loading} />}
          </>
        : failure.state === 'missing' ?
          <>
            <PageTitle title={words.title} />
            <LoadFailure
              kind="missing"
              message={words.missing[failure.side]}
              listLabel={GW_TEXT.load.toList}
              onList={onList}
              actionRef={retryFocus.actionRef}
            />
          </>
        : <>
            <PageTitle title={words.title} />
            <StepFlow current={3} />
            <LoadFailure
              kind="failed"
              message={words[failure.state][failure.side]}
              retryLabel={GW_TEXT.load.retry}
              listLabel={GW_TEXT.load.toList}
              onRetry={retryFailed}
              onList={onList}
              actionRef={retryFocus.actionRef}
            />
          </>
        }
      </div>
    );

  const data = result.result;
  // 위에서 dry-run 을 돌려보냈다(타입은 여기서 다시 좁힌다).
  if (!isScanResult(data)) return null;
  return (
    <ReviewBody
      store={store}
      runId={runId}
      openPdf={openPdf}
      result={data}
      review={review.status.review}
      handle={review}
      initialConfirm={initialConfirm}
      canWrite={canWrite}
      back={back}
      onList={onList}
      headingRef={retryFocus.doneRef}
    />
  );
}

type ReadState = 'loading' | 'ready' | 'missing' | 'invalid' | 'failed';

/** 결과와 검토 둘의 읽기 상태를 하나로(결과가 먼저). 실패·없음이면 어느 쪽(side)인지도 낸다(글과 [다시 시도]가 고른다). */
function readFailure(
  result: ReadState,
  review: ReadState,
): { state: ReadState; side: 'result' | 'review' } {
  if (result !== 'ready') return { state: result, side: 'result' };
  return { state: review, side: 'review' };
}

function ReviewBody({
  store,
  runId,
  openPdf,
  result,
  review,
  handle,
  initialConfirm,
  canWrite,
  back,
  onList,
  headingRef,
}: {
  store: GreenwashStore;
  runId: string;
  openPdf: OpenPdf;
  result: ScanResult;
  review: GreenwashReview;
  handle: ReviewHandle;
  initialConfirm: boolean;
  canWrite: boolean;
  back: ReactNode;
  /** 확정 뒤 [목록으로 돌아가기](GW-05c). */
  onList(): void;
  /** 제목 줄 h2 의 ref([다시 시도] 뒤 초점 — 이름 있는 prop. ReviewBody 는 forwardRef 가 아니다). */
  headingRef: Ref<HTMLHeadingElement>;
}) {
  const confirmed = review.state === 'confirmed';
  const rows = joinReview(
    result.items,
    review.marks,
    review.edits,
    review.evidence,
    review.rejudges,
  );
  const tally = reviewTally(rows);

  const [part, setPart] = useState<string | null>(null);
  const [tab, setTab] = useState<ReviewTab>('all');
  // 확정 전 탭 「미검토」 ↔ 확정 뒤 탭 「제외」: 없는 탭을 보고 있으면 전체로.
  const shownTab: ReviewTab =
    (confirmed && tab === 'pending') || (!confirmed && tab === 'excluded') ?
      'all'
    : tab;
  const filtered = filterReviewRows(rows, { part, tab: shownTab });
  const [picked, setPicked] = useState<number | null>(null);
  /** 줄을 누른 횟수(쪽 칸의 쪽 이동을 고를 때마다 버린다). */
  const [pickCount, setPickCount] = useState(0);
  const current =
    filtered.find((row) => row.index === picked) ?? filtered[0] ?? null;
  /** 쪽 칸 상자로 고른 문장(목록이 그 줄로 스크롤한다 — 역 포커싱, sid:MARC-ISSUE-341). 고를 때마다 새 객체. */
  const [jump, setJump] = useState<{ index: number } | null>(null);
  const listRef = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (jump === null) return;
    const row = listRef.current?.querySelector<HTMLElement>(
      `button[data-item="${jump.index}"]`,
    );
    // 쪽 칸은 sticky 라 그대로, 목록(쪽 스크롤)만 움직인다
    row?.scrollIntoView?.({ block: 'center' });
  }, [jump]);
  /** 앞 상세가 내려갈 때 초점을 가졌는지. 다음 상세가 받아 검토 줄 첫 단추로 초점을 잇는다(sid:MARC-ISSUE-105 1). */
  const detailFocus = useRef(false);
  const hasDetail = current !== null;
  useLayoutEffect(() => {
    // 상세가 없어지면(문장 0) 남은 표시를 버린다 — 나중에 놓이는 상세가 초점을 빼앗지 않게
    if (!hasDetail) detailFocus.current = false;
  }, [hasDetail]);

  // 05a 의 문장은 닫힌 뒤에도 남긴다(닫힘이 끝나야 공용 DialogContent 가 연 자리로 초점을 돌린다).
  const [excludeFor, setExcludeFor] = useState<ReviewRow | null>(null);
  const [excludeOpen, setExcludeOpen] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(initialConfirm);
  /** 상세가 내려간 뒤 저장이 안 된 고침 글(문장 차례 → 칸·글). 그 문장의 상세가 다시 놓이면 연 칸으로 되살린다(밴드 GR1). */
  const [drafts, setDrafts] = useState<ReadonlyMap<number, EditDraft>>(
    () => new Map(),
  );
  const keepDraft = (index: number, draft: EditDraft | null) => {
    setDrafts((prev) => {
      if (draft === null && !prev.has(index)) return prev;
      const next = new Map(prev);
      if (draft === null) next.delete(index);
      else next.set(index, draft);
      return next;
    });
    if (draft === null) return;
    // 글을 잃지 않게 그 문장으로 돌아간다
    setPicked(index);
    setPickCount((count) => count + 1);
  };
  /** 「저장 중이에요」 알림을 보이는가(받지 않은 누름이 생길 때마다 BUSY_NOTICE_MS 동안). */
  const [busyNotice, setBusyNotice] = useState(false);
  useEffect(() => {
    if (handle.busyRefusals === 0) return;
    setBusyNotice(true);
    const timer = setTimeout(() => setBusyNotice(false), BUSY_NOTICE_MS);
    return () => clearTimeout(timer);
  }, [handle.busyRefusals]);
  /** 확정이 저장 없이 끝난 횟수 — 막힘(stale·reload_failed)이 아니면 05b 를 닫는다(아래 effect). */
  const [confirmMisses, setConfirmMisses] = useState(0);
  const missHandled = useRef(0);
  /** 재판단이 도는(누른 뒤 답 기다림 포함) 동안 [확정]을 끈다 — 서버도 409 rejudge_running 으로 받지 않는다(GRJ1 ④ B1). */
  const rejudging =
    review.rejudges.some((line) => line.status === 'running') ||
    handle.pressing.size > 0;
  const blocked =
    handle.saveError === 'stale' ? words.saveStale
    : handle.saveError === 'reload_failed' ? words.reloadFailed
    : null;
  useEffect(() => {
    if (confirmMisses === missHandled.current) return;
    missHandled.current = confirmMisses;
    if (blocked === null) setConfirmOpen(false);
  }, [confirmMisses, blocked]);

  const status: RunStatus =
    confirmed ? { kind: 'confirmed' }
    : review.state === 'in_review' ?
      { kind: 'reviewing', reviewed: tally.reviewed, total: tally.total }
    : { kind: 'pending' };

  const pick = (row: ReviewRow, value: ReviewPick) => {
    if (value === 'excluded') {
      setNoteError(null);
      setExcludeFor(row);
      setExcludeOpen(true);
      return;
    }
    if (row.mark?.decision !== 'adopted')
      void handle.mark({ itemIndex: row.index, decision: 'adopted' });
  };

  const submitExclude = (row: ReviewRow, value: ExcludeReasonValue) => {
    const text = excludeReasonText({
      label: GW_TEXT.exclude.reasons[value.reason],
      note: value.note,
      requiresNote: value.reason === 'other',
    });
    if (!text.ok) {
      setNoteError(words.noteRequired);
      return;
    }
    setNoteError(null);
    setExcludeOpen(false);
    void handle.mark({
      itemIndex: row.index,
      decision: 'excluded',
      reason: text.text,
    });
  };

  // 저장을 시도했으면(성공·실패) 닫는다 — 실패면 본문의 save-error 가 모달에 가리지 않게(디자인 의심 (b)).
  // 저장 중(handle.saving)이면 확정을 부르지 않고 그대로 둔다(모달의 [확정]도 pending 으로 눌리지 않는다). 무효 조건: 같은 틱에 표시 저장이
  // 막 시작해 saving 이 아직 그려지지 않았으면 confirm 이 저장 없이 false 를 내고 모달이 닫힌다(「저장 중이에요」 알림이 보인다 —
  // 다시 열어 누르면 된다. 밴드 GR1).
  const confirmReview = async () => {
    if (handle.saving) return;
    if (await handle.confirm(result.items.length)) setConfirmOpen(false);
    else setConfirmMisses((n) => n + 1);
  };

  return (
    <div
      data-screen="review"
      data-review-state={review.state}
      className="flex flex-col gap-6"
    >
      <PageTitle
        headingRef={headingRef}
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>{words.title}</span>
            <span data-testid="review-state" data-state={review.state}>
              <RunStatusBadge status={status} showCount={false} />
            </span>
          </span>
        }
        description={words.meta(result.source.fileName, tally.total)}
        actions={
          <>
            {back}
            {confirmed && (
              // 확정 뒤 목록으로 바로(GW-05c — 시안 댓글, sid:MARC-ENT-603). [요약으로]와 같은 꼴
              <Button
                variant="outlineGrey"
                shape="round"
                size="md"
                data-testid="confirmed-to-list"
                onClick={onList}
              >
                {words.toList}
              </Button>
            )}
            {confirmed ?
              <GwDownloads
                confirmed
                scan
                load={() => store.getReport(runId, true)}
              />
            : canWrite && (
                <Button
                  variant="outlineBlack"
                  shape="round"
                  size="md"
                  disabled={handle.saving || rejudging}
                  onClick={() => setConfirmOpen(true)}
                >
                  {words.confirm}
                </Button>
              )
            }
          </>
        }
      />
      <StepFlow current={3} />
      {confirmed && (
        <LockBanner
          by={review.confirmedBy?.name ?? ''}
          at={review.confirmedAt === null ? '' : formatKst(review.confirmedAt)}
        />
      )}
      {handle.saveError === 'already_confirmed' && !confirmed && (
        // 확정하려던 일이 이미 돼 있다 — 오류가 아니라 회색 정보 줄(디자인 답 ②, 밴드 GW1R ③)
        <PageInfo role="status" icon={<PageInfoIcon />} data-testid="save-info">
          {words.alreadyConfirmed}
        </PageInfo>
      )}
      {rejudging && !confirmed && canWrite && (
        <PageInfo
          role="status"
          icon={<PageInfoIcon />}
          data-testid="confirm-waits"
        >
          {say.confirmWaits}
        </PageInfo>
      )}
      {busyNotice && (
        <PageInfo role="status" icon={<PageInfoIcon />} data-testid="save-busy">
          {words.saveBusy}
        </PageInfo>
      )}
      {handle.saveError !== null &&
        handle.saveError !== 'already_confirmed' &&
        handle.saveError !== 'stale' &&
        handle.saveError !== 'reload_failed' && (
          <PageInfo
            tone="error"
            role="alert"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="save-error"
          >
            {handle.saveError === 'review_locked' ?
              words.saveLocked
            : handle.saveError === 'invalid' ?
              words.saveInvalid
            : handle.saveError === 'run_not_done' ?
              words.saveRunNotDone
            : handle.saveError === 'rejudge_running' ?
              say.saveRunning
            : handle.saveError === 'nothing_to_rejudge' ?
              say.saveNothing
            : handle.saveError === 'confirm_rejudging' ?
              say.confirmWaits
            : handle.saveError === 'no_review' ?
              words.saveNoReview
            : words.saveRejected}
          </PageInfo>
        )}

      <Tabs
        value={part === null ? 'all' : `part:${part}`}
        onValueChange={(value) =>
          setPart(value === 'all' ? null : value.slice('part:'.length))
        }
      >
        <TabsList aria-label={words.partTabsLabel}>
          <TabsTrigger value="all">
            {words.partTab(words.allParts, rows.length)}
          </TabsTrigger>
          {result.parts.map((resultPart) => (
            <TabsTrigger
              key={resultPart.name}
              value={`part:${resultPart.name}`}
            >
              {words.partTab(
                partName(resultPart.name),
                filterReviewRows(rows, { part: resultPart.name, tab: 'all' })
                  .length,
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* 세 칸: 1440 이상 320 · 나머지 · 384(디자이너 값), 그 아래(최소 1280까지) 280 · 나머지 · 320. 가운데 쪽 그림은 쪽 칸(ReviewPagePane 의 page-scroll) 안쪽 폭에 맞춰 줄어든다(밴드 GFS1 fitScale, sid:MARC-ISSUE-449) */}
      {/* 쪽 칸·상세 칸은 sticky(위 STICKY_GAP, 높이 뷰포트 − 틈, 넘치면 칸 안 스크롤) — 목록 아래쪽 문장을 골라도 미리보기·상세가 화면 안(sid:MARC-ISSUE-341). 목록은 쪽 스크롤 그대로 */}
      <div className="flex items-start gap-4">
        <Card className="w-[280px] shrink-0 overflow-hidden p-0 min-[1440px]:w-80">
          <ListHead
            tally={tally}
            savedAt={
              confirmed || handle.savedAt === null ?
                null
              : formatKstTime(handle.savedAt)
            }
            edited={confirmed || tally.edited === 0 ? null : tally.edited}
            saving={!confirmed && handle.saving}
            confirmed={confirmed}
            tab={shownTab}
            onTab={setTab}
          />
          <SentenceList
            listRef={listRef}
            rows={filtered}
            pressing={handle.pressing}
            current={current?.index ?? null}
            onPick={(index) => {
              setPicked(index);
              setPickCount((count) => count + 1);
            }}
          />
        </Card>
        <Card
          className="sticky flex min-w-0 flex-1 flex-col p-4"
          style={STICKY_STYLE}
          data-testid="review-page-card"
        >
          {current !== null && (
            <ReviewPagePane
              store={store}
              openPdf={openPdf}
              runId={runId}
              item={
                // 쪽 칸의 등급 상자·태그도 보이는 등급(고친 값 ?? 기준 판단 — 리스크 아님이면 첫 판단 색)
                (
                  (current.shownLevel ?? current.item.level) ===
                  current.item.level
                ) ?
                  current.item
                : {
                    ...current.item,
                    level: current.shownLevel ?? current.item.level,
                  }
              }
              pickKey={`${pickCount}:${current.index}`}
              pageCount={result.source.pageCount}
              sentences={filtered.map((row) => ({
                index: row.index,
                level: row.shownLevel ?? row.item.level,
                sentence: row.item.sentence,
                position: row.item.position,
              }))}
              currentIndex={current.index}
              onPick={(index) => {
                setPicked(index);
                setPickCount((count) => count + 1);
                setJump({ index });
              }}
            />
          )}
        </Card>
        <Card
          className="sticky w-80 shrink-0 overflow-y-auto p-6 min-[1440px]:w-96"
          style={STICKY_STYLE}
          data-testid="review-detail-card"
        >
          {
            current === null ?
              <p className="m-0 text-style-pre-body-06 text-text-tertiary">
                {words.listEmpty}
              </p>
              // 문장마다 새로 그린다: 「미검토」 탭에서 채택하면 줄이 빠지는데, 같은 DOM 버튼이 다음 문장의 [채택]이 되어
              // 한 번 더 누르면 다음 문장이 채택되었다(밴드 FW2 ⑤ M4).
            : <Detail
                key={current.index}
                focusCarry={detailFocus}
                row={current}
                confirmed={confirmed}
                canWrite={canWrite}
                saving={handle.saving}
                onPick={(value) => pick(current, value)}
                onEdit={handle.edit}
                onEvidence={handle.evidence}
                onRejudge={handle.rejudge}
                pressing={handle.pressing.has(current.index)}
                pageCount={result.source.pageCount}
                draft={drafts.get(current.index) ?? null}
                onDraft={(draft) => keepDraft(current.index, draft)}
              />

          }
        </Card>
      </div>

      {excludeFor !== null && (
        <ExcludeReasonDialog
          key={excludeFor.index}
          open={excludeOpen}
          onOpenChange={setExcludeOpen}
          quote={`「${excludeFor.item.sentence}」`}
          quoteMeta={words.quoteMeta(
            excludeFor.item.parts.map(partName),
            excludeFor.item.page,
            excludeFor.shownLevel ?? say.nonRisk,
          )}
          noteError={noteError ?? undefined}
          onNoteChange={() => setNoteError(null)}
          onSubmit={(value) => submitExclude(excludeFor, value)}
        />
      )}
      <ConfirmReviewDialog
        open={confirmOpen && !confirmed}
        onOpenChange={setConfirmOpen}
        unreviewedCount={tally.pending}
        pending={handle.saving}
        onConfirm={() => void confirmReview()}
        blocked={blocked}
        reloadLabel={words.reload}
        onReload={() => void handle.reload()}
      />
    </div>
  );
}

function ListHead({
  tally,
  savedAt,
  edited,
  saving,
  confirmed,
  tab,
  onTab,
}: {
  tally: ReviewTally;
  /** 「자동 저장됨」의 꾸민 HH:MM(없으면 null — 토막 없음). */
  savedAt: string | null;
  /** 「고친 문장 n」의 n(없으면 null — 토막 없음). */
  edited: number | null;
  /** 저장이 도는 중(끝 토막이 「저장하고 있어요」). */
  saving: boolean;
  confirmed: boolean;
  tab: ReviewTab;
  onTab(tab: ReviewTab): void;
}) {
  const tabs: readonly ReviewTab[] = [
    'all',
    ...LEVELS,
    confirmed ? 'excluded' : 'pending',
  ];
  const percent = tally.total === 0 ? 0 : (tally.reviewed / tally.total) * 100;
  return (
    <div className="flex flex-col gap-3 border-0 border-b border-solid border-border-quaternary p-4">
      <div
        className="flex items-center gap-3 text-style-pre-body-04 text-text-secondary"
        data-testid="review-progress"
        data-reviewed={tally.reviewed}
        data-total={tally.total}
      >
        <span className="shrink-0">
          {words.progress(tally.reviewed, tally.total)}
        </span>
        <span
          aria-hidden
          className="h-2 min-w-20 flex-1 overflow-hidden rounded-full bg-background-tertiary"
        >
          <span
            className="gw-m-width block h-full rounded-full bg-support-orange"
            style={{ width: `${percent}%` }}
          />
        </span>
      </div>
      <span
        className="text-style-pre-caption-03 text-text-tertiary"
        data-testid="review-tally"
        data-adopted={tally.adopted}
        data-excluded={tally.excluded}
        data-pending={tally.pending}
        data-edited={tally.edited}
      >
        {words.tally(
          tally.adopted,
          tally.excluded,
          tally.pending,
          savedAt,
          edited,
          saving,
        )}
      </span>
      <Tabs
        value={tab}
        onValueChange={(value) => onTab(value as ReviewTab)}
        variant="box"
      >
        <TabsList aria-label={words.levelTabsLabel}>
          {tabs.map((value) => (
            <TabsTrigger key={value} value={value}>
              {words.levelTabs[value]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}

function SentenceList({
  listRef,
  rows,
  pressing,
  current,
  onPick,
}: {
  listRef?: Ref<HTMLUListElement>;
  rows: readonly ReviewRow[];
  /** 재판단을 눌러 답을 기다리는 문장(도는 중 표시). */
  pressing: ReadonlySet<number>;
  current: number | null;
  onPick(index: number): void;
}) {
  if (rows.length === 0)
    return (
      <p className="m-0 p-4 text-style-pre-body-06 text-text-tertiary">
        {words.listEmpty}
      </p>
    );
  return (
    <ul
      ref={listRef}
      aria-label={words.listLabel}
      className="m-0 flex list-none flex-col p-0"
      data-testid="sentence-list"
    >
      {rows.map((row) => {
        const selected = row.index === current;
        const excluded = row.mark?.decision === 'excluded';
        return (
          <li key={row.index}>
            <button
              type="button"
              aria-current={selected ? 'true' : undefined}
              data-item={row.index}
              onClick={() => onPick(row.index)}
              className={cn(
                'box-border flex w-full cursor-pointer flex-col gap-1.5 border-0 border-b border-l-[3px] border-solid border-b-border-quaternary bg-transparent p-4 text-left text-style-pre-body-06 hover:bg-background-secondary',
                selected ?
                  'border-l-text-secondary bg-background-secondary'
                : 'border-l-transparent',
                excluded ? 'text-text-tertiary' : 'text-text-secondary',
              )}
            >
              {/* 배지는 줄어들지 않는다(meta 가 길면 글만 줄을 바꾼다 — 「미검/토」 꺾임, GW3R A1) */}
              <span className="flex items-center gap-1.5 text-style-pre-caption-03 text-text-tertiary [&>*]:shrink-0">
                <ReviewMark value={row.mark?.decision ?? 'unreviewed'} />
                <LevelMark level={row.shownLevel} />
                {row.edit !== null && <EditedMark />}
                {row.basis.rejudged !== null && <RejudgedMark />}
                {(pressing.has(row.index) ||
                  row.rejudge?.status === 'running') && (
                  <SpinnerIcon
                    aria-label={say.running}
                    data-testid="row-rejudging"
                    className="size-3"
                  />
                )}
                {words.rowMeta(
                  row.item.parts.map(partName),
                  row.item.page,
                  noEvidenceAt(row.basis, evidenceNow(row).added),
                )}
              </span>
              <span>{row.item.sentence}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function Section({
  heading,
  children,
  testId,
}: {
  heading?: string;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section
      className="flex flex-col gap-2 border-0 border-t border-solid border-border-quaternary py-4"
      data-testid={testId}
    >
      {heading !== undefined && (
        <h4 className="m-0 text-style-pre-body-04 text-text-primary">
          {heading}
        </h4>
      )}
      {children}
    </section>
  );
}

/**
 * 근거가 없다고 말하는가(상세 「근거 조각을 찾지 못했어요」·목록 꼬리 「근거 없음」 — 디자인 b2 11-10, 밴드 GRJ4 sid:MARC-ISSUE-639).
 * 페이지도, 근거 칸이 그리는 조각(기준 판단 칩 — 지운 칩도 줄그음으로 남아 센다 — 과 더한 조각)도 없을 때만. 재판단 뒤 페이지 없는
 * 더한 조각만 있어도 아니다. 목록은 초안이 없어 저장 값, 상세는 지금 근거 칸 값(proof)을 넘긴다.
 */
function noEvidenceAt(
  basis: Pick<Basis, 'evidencePages' | 'confirmedInEvidence'>,
  added: readonly unknown[],
): boolean {
  return (
    basis.evidencePages.length === 0 &&
    basis.confirmedInEvidence.length === 0 &&
    added.length === 0
  );
}

function Detail({
  focusCarry,
  row,
  confirmed,
  canWrite,
  saving,
  onPick,
  onEdit,
  onEvidence,
  onRejudge,
  pressing,
  pageCount,
  draft,
  onDraft,
}: {
  focusCarry: MutableRefObject<boolean>;
  row: ReviewRow;
  confirmed: boolean;
  canWrite: boolean;
  saving: boolean;
  onPick(value: ReviewPick): void;
  /** 칸 하나를 고친다(useReview.edit). 저장되면 true. */
  onEdit(change: EditChange): Promise<boolean>;
  /** 근거 고침을 갈아 넣는다(useReview.evidence). 저장되면 true. */
  onEvidence(change: EvidenceChange): Promise<boolean>;
  /** 재판단(useReview.rejudge). */
  onRejudge(itemIndex: number): Promise<boolean>;
  /** 재판단을 눌러 답을 기다리는 중. */
  pressing: boolean;
  /** 문서 쪽 수(더한 근거의 페이지 고르기). */
  pageCount: number;
  /** 이 문장의 남은 고침 글(앞 상세가 내려간 뒤 저장이 안 된 것). 있으면 칸을 연 채 시작한다. */
  draft: EditDraft | null;
  /** 남은 고침 글을 둔다(null 이면 지운다) — 상세가 내려간 뒤 저장이 안 되면 그 글을. */
  onDraft(draft: EditDraft | null): void;
}) {
  const { item, edit } = row;
  const rootRef = useRef<HTMLDivElement>(null);
  // 초점 잇기: 「미검토」 탭에서 채택하면 줄이 빠져 상세가 다음 문장으로 바뀌고(key), 누른 단추가 사라져 초점이 body 로 빠졌다.
  // 내려갈 때(정리 함수는 DOM 을 떼기 전에 돈다) 초점을 가졌으면 표시를 남기고, 다음 상세가 놓일 때 검토 줄 첫 단추로 옮긴다.
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (focusCarry.current) {
      focusCarry.current = false;
      root
        ?.querySelector<HTMLElement>('[data-testid="review-row"] button')
        ?.focus();
    }
    return () => {
      focusCarry.current = root?.contains(document.activeElement) ?? false;
    };
  }, [focusCarry]);
  const value = row.mark?.decision ?? 'unreviewed';
  /** 고칠 수 있는가(확정 전 + 쓰기). 05c·읽기만이면 고르기·[고치기] 없음. */
  const editable = !confirmed && canWrite;
  /** 고치는 중인 칸과 그 글(이 문장 안에서만 — 문장이 바뀌면 key 로 새로 그린다. 남은 고침 글이 있으면 그것부터). */
  const [editing, setEditing] = useState<EditDraft | null>(draft);
  /** 이 상세가 놓여 있는가 — 문장을 바꿔 내려간 뒤 끝난 blur 저장을 가른다(밴드 GR1). */
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  const basis = row.basis;
  const saved = evidenceNow(row);
  /** 근거 칸을 고치는 중인가와 그 값(고치는 동안만 — 아니면 서버 값). */
  const [proofEditing, setProofEditing] = useState(false);
  const [proofDraft, setProofDraft] = useState<EvidenceDraft>(saved);
  const proof = proofEditing ? proofDraft : saved;
  const running = pressing || row.rejudge?.status === 'running';
  const unchanged = nothingToRejudge(proof.removed, proof.added, basis);
  const canRejudge = editable && !running && !unchanged;
  /** 기준 판단 때 보낸 것에 없는 더한 조각 수(바뀜 한 줄). */
  const addedNew = proof.added.filter(
    (piece) =>
      !basis.added.some((b) => b.text === piece.text && b.page === piece.page),
  ).length;
  const sameProof = (a: EvidenceDraft, b: EvidenceDraft) =>
    JSON.stringify([a.removed, a.added]) ===
    JSON.stringify([b.removed, b.added]);
  // 근거 저장(밴드 GRJ2 — sid:MARC-TICK-568): 초안이 바뀔 때마다 그 값으로 저장한다(저장 길은 useReview.evidence → queue 하나).
  // 「추가」는 입력 상자째 지워 칸 blur 가 오지 않았고, 저장 안 된 초안으로 켜진 [재판단]이 옛 근거로 409 nothing_to_rejudge 였다.
  /** 마지막으로 보낸 근거 저장 — 같은 초안을 두 번 보내지 않고 [재판단]·칸 벗어남이 그 답을 기다린다. 실패하면 비운다. */
  const sent = useRef<{
    draft: EvidenceDraft;
    done: Promise<boolean>;
  } | null>(null);
  const saveProof = (draft: EvidenceDraft): Promise<boolean> => {
    const before = sent.current;
    if (before !== null && sameProof(before.draft, draft)) return before.done;
    const done = onEvidence({ itemIndex: row.index, ...draft });
    const mine = { draft, done };
    sent.current = mine;
    void done.then((ok) => {
      if (!ok && sent.current === mine) sent.current = null;
    });
    return done;
  };
  /** 서버에 실린(또는 실리는 중인) 값과 같은가 — 같으면 저장하지 않는다. */
  const settled = (draft: EvidenceDraft) =>
    sent.current === null ?
      sameProof(draft, saved)
    : sameProof(draft, sent.current.draft);
  const changeProof = (next: EvidenceDraft) => {
    setProofDraft(next);
    if (!settled(next)) void saveProof(next);
  };
  // 근거 칸을 벗어나면 닫는다(서버 값과 같으면 저장 없이). 다르면 저장하고, 안 되면 칸을 연 채 초안을 남긴다.
  const leaveProof = async () => {
    const ok =
      sent.current === null && sameProof(proofDraft, saved) ?
        true
      : await saveProof(proofDraft);
    if (ok && live.current) setProofEditing(false);
  };
  /** [재판단]을 누른 뒤 앞 저장을 기다리는 중(겹쳐 누름 막기 — 겉모습은 그대로). */
  const holding = useRef(false);
  // [재판단]: 고치는 중이고 초안이 서버 값과 다르면(또는 저장이 도는 중이면) 먼저 저장한다. 저장이 안 되면 보내지 않는다.
  const pressRejudge = async () => {
    if (holding.current) return;
    holding.current = true;
    try {
      if (
        proofEditing &&
        !(sent.current === null && sameProof(proofDraft, saved))
      ) {
        const ok = await saveProof(proofDraft);
        if (!ok || !live.current) return;
      }
      // 받아들여지면 근거 칸 고치기를 닫는다 — 도는 동안·끝난 뒤 칸은 서버 값(밴드 GRJ3). 거절되면 연 채 초안을 둔다
      if ((await onRejudge(row.index)) && live.current) closeProof();
    } finally {
      holding.current = false;
    }
  };
  /** 근거 칸 고치기를 닫고 마지막으로 보낸 저장을 잊는다(다시 열면 onStart 가 서버 값부터). */
  const closeProof = () => {
    sent.current = null;
    setProofEditing(false);
  };
  // 다른 길(다른 탭·다시 읽기)로 이 문장의 재판단이 돌기 시작해도 닫는다 — 서버는 도는 문장의 근거 PUT 을 받지 않는다(GRJ3)
  const serverRunning = row.rejudge?.status === 'running';
  useEffect(() => {
    if (!serverRunning) return;
    sent.current = null;
    setProofEditing(false);
  }, [serverRunning]);

  const pickLevel = (level: RiskLevel) => {
    const next = LEVEL_OF[level];
    if (next === row.shownLevel) return;
    void onEdit({ itemIndex: row.index, column: 'level', value: next });
  };
  // 칸을 벗어나면 저장한다. 보이는 값과 같으면 저장 없이 닫고, 저장이 안 되면 칸을 연 채 글을 남긴다.
  // 보이는 값도 같은 규칙으로 다듬어 견준다 — AI 값의 앞뒤 공백·빈 항목만으로 고침이 남지 않게(sid:MARC-ISSUE-282).
  const finish = async (
    column: 'reasonBullets' | 'fixParagraph',
    text: string,
  ) => {
    const bullets = reasonsFromText(text, row.shownReasons);
    const change: EditChange =
      column === 'reasonBullets' ?
        { itemIndex: row.index, column, value: bullets }
      : { itemIndex: row.index, column, value: text };
    const unchanged =
      column === 'reasonBullets' ?
        bullets.join('\n') ===
        reasonsFromText(reasonsText(row.shownReasons), row.shownReasons).join(
          '\n',
        )
      : text.trim() === row.shownFix.trim();
    if (unchanged) {
      setEditing(null);
      onDraft(null);
      return;
    }
    const saved = await onEdit(change);
    if (saved) {
      setEditing(null);
      onDraft(null);
    } else if (!live.current) onDraft({ column, text });
  };

  const field = (
    column: 'reasonBullets' | 'fixParagraph',
    heading: string,
    edited: ReviewEditedReasons | ReviewEditedFix | null,
    shown: ReactNode,
    original: ReactNode,
    startText: string,
  ) => {
    const open = editing?.column === column ? editing : null;
    return (
      <Section testId={`field-${column}`}>
        <div className="flex items-center justify-between gap-2">
          <h4 className="m-0 inline-flex flex-wrap items-center gap-1.5 text-style-pre-body-04 text-text-primary">
            {heading}
            {edited !== null && open === null && <EditedMark />}
            {open !== null && (
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {words.edit.editing}
              </span>
            )}
            {confirmed && edited !== null && (
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {words.edit.lockedNote}
              </span>
            )}
            {edited !== null && aiChangedSince(edited.editedAt, basis) && (
              <AiChanged />
            )}
          </h4>
          {editable && open === null && (
            <Button
              variant="outlineGrey"
              shape="round"
              size="sm"
              onClick={() => setEditing({ column, text: startText })}
            >
              {words.edit.start}
            </Button>
          )}
        </div>
        {open !== null ?
          <Textarea
            aria-label={heading}
            // 연 칸에 바로 쓴다(누른 [고치기] 는 사라진다). 커서는 글 끝(sid:MARC-ISSUE-315 — 맨 앞이면 친 글이 첫 항목 앞에 붙는다)
            ref={caretAtEnd}
            autoFocus
            rows={column === 'reasonBullets' ? 4 : 5}
            value={open.text}
            onChange={(event) =>
              setEditing({ column, text: event.currentTarget.value })
            }
            onBlur={(event) => void finish(column, event.currentTarget.value)}
            className="text-style-pre-body-06 text-text-secondary"
          />
        : shown}
        {edited !== null && (
          <AiOriginal
            column={column}
            by={edited.editedBy.name}
            at={editedAt(edited)}
          >
            {original}
          </AiOriginal>
        )}
      </Section>
    );
  };

  return (
    <div
      ref={rootRef}
      className="gw-m-fade flex flex-col"
      data-testid="review-detail"
      data-item={row.index}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {running ?
          <SkeletonBar className="h-7 w-24" />
        : row.shownLevel === null ?
          <NonRiskBadge />
        : editable ?
          <LevelPicker
            level={RISK[row.shownLevel]}
            disabled={saving}
            onPick={pickLevel}
          />
        : <RiskBadge level={RISK[row.shownLevel]} />}
        {edit?.level != null && <EditedMark />}
        {edit?.level != null && aiChangedSince(edit.level.editedAt, basis) && (
          <AiChanged />
        )}
        {item.parts.map((name) => (
          <Badge key={name} variant="grey" size="sm">
            {partName(name)}
          </Badge>
        ))}
        {/* 근거 페이지만(문장 페이지는 가운데 칸 제목·왼쪽 줄에 있다 — 시안 댓글 중복 정보, sid:MARC-ENT-603). 근거가 없으면 아래 안내가 말한다 */}
        {basis.evidencePages.length > 0 && (
          <span
            data-testid="detail-evidence-pages"
            className="text-style-pre-caption-03 text-text-tertiary"
          >
            {words.detailPage(basis.evidencePages)}
          </span>
        )}
        {editable && (
          // 꺼진 단추는 hover 를 받지 않아 감싼 칸에 글을 단다(r4 ② 「근거를 고치면 …」)
          <span
            className="ml-auto"
            title={!running && unchanged ? say.buttonOff : undefined}
          >
            <Button
              variant="outlineGrey"
              shape="round"
              size="sm"
              data-testid="rejudge"
              disabled={!canRejudge}
              leftIcon={
                running ?
                  <SpinnerIcon aria-hidden />
                : <RefreshIcon aria-hidden />
              }
              onClick={() => void pressRejudge()}
            >
              {running ? say.buttonRunning : say.button}
            </Button>
          </span>
        )}
      </div>
      {running ?
        <p
          role="status"
          data-testid="rejudge-running"
          className="m-0 mb-2 inline-flex items-center gap-1.5 text-style-pre-caption-02 text-text-tertiary"
        >
          <SpinnerIcon aria-hidden className="size-3 shrink-0" />
          {say.running}
        </p>
      : <>
          {row.rejudge?.status === 'failed' && (
            <div
              role="alert"
              data-testid="rejudge-failed"
              className="mb-2 flex flex-wrap items-center gap-2 text-style-pre-caption-02 text-support-red"
            >
              <span>{say.failed}</span>
              {editable && (
                <Button
                  variant="text"
                  shape="square"
                  size="xs"
                  disabled={!canRejudge}
                  onClick={() => void pressRejudge()}
                >
                  {say.retry}
                </Button>
              )}
            </div>
          )}
          {basis.rejudged !== null && (
            <p
              data-testid="rejudge-judged"
              className="m-0 mb-2 text-style-pre-caption-03 text-text-tertiary"
            >
              {say.judged(
                `${formatKstMonthDay(basis.rejudged.judgedAt)} ${formatKstTime(basis.rejudged.judgedAt)}`,
                basis.rejudged.judgedBy,
              )}
            </p>
          )}
          {row.shownLevel === null && (
            <p
              data-testid="nonrisk-note"
              className="m-0 mb-2 text-style-pre-caption-03 text-text-tertiary"
            >
              {say.nonRiskNote}
            </p>
          )}
        </>
      }
      {edit?.level != null && (
        <LevelOriginal edited={edit.level} ai={basis.level} />
      )}
      {/* 「근거 조각을 찾지 못했어요」 — noEvidenceAt(더한 조각은 고치는 중이면 초안, 아니면 저장 값). */}
      {noEvidenceAt(basis, proof.added) && (
        <PageInfo
          icon={<PageInfoIcon />}
          className="mb-2"
          data-testid="no-evidence"
        >
          {words.noEvidence}
        </PageInfo>
      )}
      <p className="m-0 mb-1 rounded-component bg-background-secondary px-4 py-3 text-style-pre-body-05 text-text-primary">
        {`「${item.sentence}」`}
      </p>
      <EvidenceEditor
        chips={basis.confirmedInEvidence}
        draft={proof}
        editable={editable && !running}
        editing={proofEditing}
        pageCount={pageCount}
        onStart={() => {
          sent.current = null;
          setProofDraft(saved);
          setProofEditing(true);
        }}
        onDraft={changeProof}
        onLeave={() => void leaveProof()}
        footer={
          editable && !running && !unchanged ?
            <p
              data-testid="evidence-changed"
              className="m-0 text-style-pre-caption-03 text-text-tertiary"
            >
              {say.changed(proof.removed.length, addedNew)}
            </p>
          : null
        }
      />
      {running && (
        <Section testId="rejudge-skeleton">
          <SkeletonBar className="h-4 w-3/4" />
          <SkeletonBar className="h-4 w-2/3" />
          <SkeletonBar className="h-4 w-1/2" />
        </Section>
      )}
      {!running &&
        row.shownReasons.length > 0 &&
        field(
          'reasonBullets',
          words.reasonHeading,
          edit?.reasonBullets ?? null,
          <Bullets values={row.shownReasons} />,
          <Bullets values={basis.reasonBullets} />,
          reasonsText(row.shownReasons),
        )}
      {!running &&
        row.shownFix !== '' &&
        field(
          'fixParagraph',
          words.fixHeading,
          edit?.fixParagraph ?? null,
          <p className="m-0 text-style-pre-body-06 text-text-secondary">
            {row.shownFix}
          </p>,
          <p className="m-0">{basis.fixParagraph}</p>,
          row.shownFix,
        )}
      {basis.rejudged !== null && <FirstJudgment item={item} />}
      <Section testId="review-row">
        <div className="flex flex-wrap items-center gap-2">
          <ReviewMark value={value} />
          {confirmed ?
            <span className="inline-flex items-center gap-1 text-style-pre-caption-02 text-text-tertiary">
              <LockIcon aria-hidden className="size-3 shrink-0" />
              {words.locked}
            </span>
          : canWrite && (
              // 쓰지 못하면(로그인하지 않은 세션) 안내 글과 채택·제외는 숨긴다(지금 표시 ReviewMark 만).
              <>
                <span className="text-style-pre-caption-03 text-text-tertiary">
                  {words.excludeHint}
                </span>
                <ReviewChoice
                  className="ml-auto"
                  value={value}
                  disabled={saving}
                  onChange={onPick}
                />
              </>
            )
          }
        </div>
      </Section>
    </div>
  );
}

/** 연 글 칸의 커서를 글 끝에 둔다(마운트 때 한 번 — 모듈 함수라 ref 가 다시 불리지 않는다. autoFocus 는 이 선택을 그대로 쓴다). */
function caretAtEnd(box: HTMLTextAreaElement | null) {
  box?.setSelectionRange(box.value.length, box.value.length);
}

/** 고친 칸의 「MM-DD HH:MM」(GW-05_r2 :99 「10-15 14:28」). */
const editedAt = (
  edited: ReviewEditedLevel | ReviewEditedReasons | ReviewEditedFix,
) => `${formatKstMonthDay(edited.editedAt)} ${formatKstTime(edited.editedAt)}`;

/** 등급 줄 아래의 「AI 원래 판단 보기」(펼치면 AI 등급 — 기준 판단. 리스크 아님이면 그 딱지). */
function LevelOriginal({
  edited,
  ai,
}: {
  edited: ReviewEditedLevel;
  ai: Level | null;
}) {
  return (
    <AiOriginal
      column="level"
      by={edited.editedBy.name}
      at={editedAt(edited)}
      className="mb-2"
    >
      {ai === null ?
        <NonRiskBadge />
      : <RiskBadge level={RISK[ai]} />}
    </AiOriginal>
  );
}

/** 목록 줄의 등급 딱지(리스크 아님이면 회색 딱지). */
function LevelMark({ level }: { level: Level | null }) {
  return level === null ? <NonRiskBadge /> : <RiskBadge level={RISK[level]} />;
}

/** ③ 고친 칸 머리 — 고친 뒤 재판단으로 AI 값이 바뀜(물음: 마크스폰 r4 ③). */
function AiChanged() {
  return (
    <span
      data-ai-changed
      className="text-style-pre-caption-03 text-support-orange-dark"
    >
      {words.edit.aiChanged}
    </span>
  );
}

/** 카드 맨 아래 「AI 첫 판단 보기」(재판단이 있을 때 — 첫 판단 하나, r4 ②). */
function FirstJudgment({ item }: { item: Basis | ReviewRow['item'] }) {
  return (
    <details
      data-testid="first-judgment"
      className="border-0 border-t border-solid border-border-quaternary py-4 text-style-pre-caption-02 text-text-tertiary"
    >
      <summary className="cursor-pointer">{say.firstJudgment}</summary>
      <div className="mt-2 flex flex-col gap-2">
        <LevelMark level={item.level} />
        <Bullets values={item.reasonBullets} />
        {item.fixParagraph !== '' && <p className="m-0">{item.fixParagraph}</p>}
      </div>
    </details>
  );
}

function Bullets({ values }: { values: readonly string[] }) {
  return (
    <ul className="m-0 list-disc pl-5 text-style-pre-body-06 text-text-secondary">
      {values.map((bullet, index) => (
        <li key={index}>{bullet}</li>
      ))}
    </ul>
  );
}
