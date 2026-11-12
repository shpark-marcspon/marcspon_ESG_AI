// 썸네일 칠하기 색(밴드 FW1b ②). 칠하기 색은 이 표 한 곳에만 둔다(키트 토큰. 시안 gw-r1.css 의 p-ceo·p-co·p-cl·p-both 와 같은 색 줄기).
//   CEO 메시지 = 주황(support-orange), 회사소개 = 파랑(support-blue), 기후·환경 = 초록(support-green-dark),
//   겹친 쪽 = 짝과 상관없이 중립 꼴: 틀 2px border-primary(#383C40) + 흰 바탕. 어느 파트인지는 쪽 번호 옆 파트 점(겹친 파트 수만큼)이 말한다
//   (디자인 대조 물음 5, band-reports/FW2-design-review.md. 옛 꼴 주황 틀 + 파랑 바깥선은 회사소개+기후·환경 겹침에도 주황·파랑이었다).
import type { PartKey } from '../../../entities/greenwash/model/index.ts';

export interface PartLook {
  /** 썸네일 틀. */
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
  company: {
    frame: 'border-2 border-support-blue bg-support-blue-subtle',
    number: 'font-bold text-support-blue-dark',
    swatch: 'bg-support-blue',
  },
  climate: {
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
