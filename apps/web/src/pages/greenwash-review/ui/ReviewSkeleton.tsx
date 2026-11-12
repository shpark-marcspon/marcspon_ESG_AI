// GW-05 문장 검토의 불러오기 꼴(밴드 GL2, sid:MARC-ENT-443 — LR4 실측 「셋째」 −462 의 몫). 공용 LoadSkeleton 카드 하나 대신 받은 뒤 꼴을 닮게:
//   파트 탭 줄(40) → 세 칸(목록 280·1440 이상 320 | 쪽 칸 나머지 | 상세 320·1440 이상 384). 쪽·상세 칸은 ready 와 같이 뷰포트 − 틈 48 높이라
//   세 칸 줄 높이가 받기 전·뒤 같다. 목록 칸은 머리(128.2) + 문장 줄 셋(81.4).
// 막대 색·모서리·움직임은 SkeletonBar 그대로(LD1 §7). 보조기기: role="status" + aria-label + 숨긴 글 하나, 막대는 aria-hidden.
// 300ms 늦추기(useDelayed)와 화면 틀의 aria-busy 는 쓰는 쪽(ReviewScreen)이 한다.
import { Card } from '../../../shared/ui/card/index.ts';
import { SkeletonBar } from '../../../shared/ui/skeleton-bar/index.ts';

/** 쪽·상세 칸 높이(ReviewScreen 의 STICKY_STYLE 과 같은 셈 — 위 틈 24 × 2). */
const PANE_STYLE = { height: 'calc(100dvh - 48px)' };

export function ReviewSkeleton({ label }: { label: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      data-testid="review-skeleton"
      className="flex flex-col gap-6"
    >
      <span className="sr-only">{label}</span>
      <div aria-hidden className="flex h-10 items-center gap-6">
        {[72, 88, 72, 72].map((width, n) => (
          <SkeletonBar key={n} className="h-3" style={{ width }} />
        ))}
      </div>
      <div aria-hidden className="flex items-start gap-4">
        <Card className="w-[280px] shrink-0 p-0 min-[1440px]:w-80">
          <div className="box-border flex h-[128.2px] flex-col gap-3 p-4">
            <SkeletonBar className="h-3 w-[60%]" />
            <SkeletonBar className="h-3 w-[40%]" />
            <SkeletonBar shape="block" className="h-8 w-[214px]" />
          </div>
          {[66, 54, 78].map((width, n) => (
            <div
              key={n}
              className="box-border flex h-[81.4px] flex-col gap-2 p-4"
            >
              <SkeletonBar className="h-3" style={{ width: `${width}%` }} />
              <SkeletonBar className="h-3 w-[40%]" />
            </div>
          ))}
        </Card>
        <Card
          className="flex min-w-0 flex-1 flex-col gap-3 p-4"
          style={PANE_STYLE}
        >
          <SkeletonBar className="h-3 w-16" />
          <SkeletonBar shape="block" className="flex-1" />
        </Card>
        <Card
          className="flex w-80 shrink-0 flex-col gap-4 p-6 min-[1440px]:w-96"
          style={PANE_STYLE}
        >
          <SkeletonBar className="h-[22px] w-[28%]" />
          <SkeletonBar shape="block" className="h-24" />
          <SkeletonBar className="h-3 w-[78%]" />
          <SkeletonBar className="h-3 w-[60%]" />
        </Card>
      </div>
    </div>
  );
}
