// (밴드 FS1 ③: results.test.ts 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 결과·검토 domain(밴드 FW2 ① §3): 요약 셈, 「추가」, 검토 잇기·거르기, PUT 본문, 확정 본문, 제외 사유 글, 서버 단계 맞춤,
// 바깥 상자, 목록 줄, 시각 꾸미기. 표 꼴. 심은 파손 (나)는 confirmUpdate 의 시험이 잡는다((가) 의 riskTagCounts 는 밴드 GW2R ① 에서 걷었다).
import { describe, expect, it } from 'vitest';

import { fitScale, outerBox } from './geometry.ts';

describe('바깥 상자', () => {
  it('상자들의 합집합, 빈 목록이면 null', () => {
    expect(
      outerBox([
        [72, 140.5, 523.2, 154],
        [70, 156, 301.8, 169.5],
      ]),
    ).toEqual([70, 140.5, 523.2, 169.5]);
    expect(outerBox([[1, 2, 3, 4]])).toEqual([1, 2, 3, 4]);
    expect(outerBox([])).toBeNull();
  });
});

// 밴드 GFS1(sid:MARC-ISSUE-449): 칸이 쪽보다 좁으면 칸 폭 ÷ 쪽 폭(0.01 내림), 넓으면 1 그대로(키우지 않음), 모르면 1.
describe('쪽 그림 배율(fitScale)', () => {
  it('좁은 칸 → 칸 폭 ÷ 쪽 폭(0.01 내림) · 그 배율의 쪽 폭은 칸 안', () => {
    const scale = fitScale(600, 842);
    expect(scale).toBe(0.71);
    expect(842 * scale).toBeLessThanOrEqual(600);
  });
  it('넓은 칸 → 1 그대로(키우지 않음)', () => {
    expect(fitScale(900, 842)).toBe(1);
    expect(fitScale(842, 842)).toBe(1);
  });
  it('칸 폭·쪽 폭을 모르면(0) 1', () => {
    expect(fitScale(0, 842)).toBe(1);
    expect(fitScale(600, 0)).toBe(1);
  });
});
