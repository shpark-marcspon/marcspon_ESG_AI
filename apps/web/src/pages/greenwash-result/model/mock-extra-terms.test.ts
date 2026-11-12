// (밴드 FS1 ③: mockResults.test.ts 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 목 저장소의 결과·검토(밴드 FW2 ① §3): 목의 결과·검토 전부가 거울을 지나는가, 목록 씨앗 다섯, 끝내기와 지은 결과 [R7],
// 구독 즉시 현재값, PUT 갈아 끼우기 [B3]·확정 뒤 409, 문서 조회·PDF. 거울은 headless/index.ts 로 가져온다 [R2].
import { afterEach, describe, expect, it, vi } from 'vitest';

import { parseResult } from '../../../entities/greenwash/api/index.ts';
import {
  MOCK_DEFAULT_TERMS,
  createMockStore,
} from '../../../entities/greenwash/api/mock/index.ts';
import type { GreenwashResult } from '../../../entities/greenwash/model/index.ts';
import { isExtraTermRow } from './summary.ts';

afterEach(() => {
  vi.useRealTimers();
});

async function resultOf(
  control: ReturnType<typeof createMockStore>,
  runId: string,
): Promise<GreenwashResult> {
  const parsed = parseResult(await control.store.getResult(runId));
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
}

describe('목록 씨앗', () => {
  it('검토 중 결과는 failedPages 와 position 이 있고, 검토 대기 결과는 추가 단어 둘(하나는 기본 목록과 겹침)', async () => {
    const control = createMockStore();
    const inReview = await resultOf(control, 'run-101');
    expect(inReview.candidateStats?.failedPages.map((f) => f.page)).toEqual([
      7,
    ]);
    // 한 결과 안에 position 있는 문장 여럿과 null 인 문장 여럿(발주서 덧붙임 1)
    expect(
      inReview.items.filter((item) => item.position !== null).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      inReview.items.filter((item) => item.position === null).length,
    ).toBeGreaterThanOrEqual(2);
    const pending = await resultOf(control, 'run-102');
    expect(pending.extraTerms).toEqual(['초록 물결', '탄소 중립']);
    const badge = pending.wordCounts.total.map((row) => [
      row.term,
      isExtraTermRow(row.term, pending.extraTerms, MOCK_DEFAULT_TERMS),
    ]);
    expect(badge).toContainEqual(['초록 물결', true]);
    expect(badge).toContainEqual(['탄소중립', false]);
  });
});
