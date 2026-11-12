// GW-03 처리 상태의 불러오기 꼴(밴드 GL2, sid:MARC-ENT-443). 공용 LoadSkeleton 카드 하나 대신 점검 중의 진행 카드를 닮게:
//   제목 줄(33.6) → 진행 막대(8) → 단계 셋(70.8, 사이 12), 카드 안 사이 20 — 1440×900 에서 381.9. 진행 카드 끝 파랑 정보 줄과 그 자리(46.4 + 사이 20)는
//   지웠다(시안 댓글 — sid:MARC-ENT-603).
//   꼴은 점검 중 하나다. 끝난 실행은 끝남 카드(106)라 받은 뒤 줄어든다 — 끝난 실행은 목록에서 결과 화면으로 바로 가 이 화면을 처음 여는 것은
//   대개 점검 중이다(감독 판단, GL2 보고).
// 막대 색·모서리·움직임은 SkeletonBar 그대로(LD1 §7). 보조기기: role="status" + aria-label + 숨긴 글 하나, 막대는 aria-hidden.
// 300ms 늦추기(useDelayed)와 화면 틀의 aria-busy 는 쓰는 쪽(StatusScreen)이 한다.
import { Card } from '../../../shared/ui/card/index.ts';
import { SkeletonBar } from '../../../shared/ui/skeleton-bar/index.ts';

export function StatusSkeleton({ label }: { label: string }) {
  return (
    <Card
      role="status"
      aria-label={label}
      data-testid="status-skeleton"
      className="flex flex-col gap-5"
    >
      <span className="sr-only">{label}</span>
      <div aria-hidden className="flex h-[33.6px] items-center justify-between">
        <SkeletonBar className="h-[22px] w-[28%]" />
        <SkeletonBar className="h-7 w-14" />
      </div>
      <SkeletonBar className="h-2" />
      <div aria-hidden className="flex flex-col gap-3">
        {[0, 1, 2].map((n) => (
          <SkeletonBar key={n} shape="block" className="h-[70.8px]" />
        ))}
      </div>
    </Card>
  );
}
