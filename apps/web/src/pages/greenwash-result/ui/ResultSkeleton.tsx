// GW-04 결과 요약의 불러오기 꼴(밴드 GL2, sid:MARC-ENT-443 — LR4 실측 「셋째」 −455.6 의 몫). 공용 LoadSkeleton 카드 하나 대신 받은 뒤 꼴을 닮게:
//   안내 띠 둘(이미지 · 확정 전, 46.4) → 통계 넷(카드, 115.6) → 두 칸(파트별 결과 카드 | 단어 빈도 카드, 347).
//   높이는 1440×900 에서 ready 를 잰 값(GL2 보고 「ready 블록 표」). 두 칸은 파트 셋(ceo·company·climate — 표 머리 40 + 줄 56×3)의 높이로 둔다.
// 막대 색·모서리·움직임은 SkeletonBar 그대로(LD1 §7). 보조기기: role="status" + aria-label + 숨긴 글 하나, 막대는 aria-hidden.
// 300ms 늦추기(useDelayed)와 화면 틀의 aria-busy 는 쓰는 쪽(ResultScreen)이 한다.
import { Card } from '../../../shared/ui/card/index.ts';
import { SkeletonBar } from '../../../shared/ui/skeleton-bar/index.ts';

export function ResultSkeleton({ label }: { label: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      data-testid="result-skeleton"
      className="flex flex-col gap-6"
    >
      <span className="sr-only">{label}</span>
      <SkeletonBar shape="block" className="h-[46.4px]" />
      <SkeletonBar shape="block" className="h-[46.4px]" />
      <div aria-hidden className="grid grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((n) => (
          <Card key={n} className="flex h-[115.6px] flex-col gap-1.5 p-6">
            <SkeletonBar className="mt-[5px] h-3 w-16" />
            <SkeletonBar className="mt-[11px] h-7 w-20" />
          </Card>
        ))}
      </div>
      <div aria-hidden className="grid grid-cols-2 items-start gap-6">
        {[0, 1].map((n) => (
          <Card key={n} className="flex h-[347px] flex-col gap-4">
            <SkeletonBar className="h-[22px] w-[28%]" />
            <SkeletonBar shape="block" className="flex-1" />
          </Card>
        ))}
      </div>
    </div>
  );
}
