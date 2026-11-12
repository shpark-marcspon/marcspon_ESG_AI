// 쪽 칸 칠하기 색(밴드 TRW0a ②, 서버 노트 「TR-02 쪽 범위를 GW-02 r2 부품 그대로」). 칠하기 색은 이 표 한 곳에만 둔다.
// 그린워싱 partLook(pages/greenwash-new/ui/partLook.ts)과 같은 값 — 공통화는 하지 않는다(플랫폼-웹 허락 4). 바꿀 때 둘 다.
//   CEO 메시지 = 주황(support-orange), 스토리 = 파랑(support-blue), 일반 = 초록(support-green-dark),
//   겹친 쪽 = 짝과 상관없이 중립 꼴(틀 2px border-primary + 흰 바탕). 어느 파트인지는 쪽 번호 옆 파트 점이 말한다.
import type { PartKey } from '../../../entities/translation/model/index.ts';

export interface PartLook {
  /** 쪽 칸 틀. */
  frame: string;
  /** 쪽 번호 글자. */
  number: string;
  /** 파트 고르기 단추와 범례의 점. */
  swatch: string;
}

export const PART_LOOK: Readonly<Record<PartKey, PartLook>> = {
  ceo: {
    frame: 'border-2 border-support-orange bg-support-orange-subtle',
    number: 'font-bold text-support-orange-dark',
    swatch: 'bg-support-orange',
  },
  story: {
    frame: 'border-2 border-support-blue bg-support-blue-subtle',
    number: 'font-bold text-support-blue-dark',
    swatch: 'bg-support-blue',
  },
  general: {
    frame: 'border-2 border-support-green-dark bg-support-green-subtle',
    number: 'font-bold text-support-green-dark',
    swatch: 'bg-support-green-dark',
  },
};

/** 두 파트 이상이 겹친 쪽. */
export const OVERLAP_LOOK: PartLook = {
  frame: 'border-2 border-border-primary bg-background-primary',
  number: 'font-bold text-text-primary',
  swatch: 'border-2 border-border-primary bg-background-primary',
};

/** 칠하지 않은 쪽. */
export const PLAIN_LOOK: Omit<PartLook, 'swatch'> = {
  frame: 'border border-border-tertiary bg-background-primary',
  number: 'text-text-tertiary',
};
