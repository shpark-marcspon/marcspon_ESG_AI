// 파트 상태 → 화면 글(밴드 TRW0b). 셈은 model/status.ts, 글은 config/text.ts — 칸 규칙에서 config 를 가져오는 것은 ui 칸뿐이라 여기서 잇는다.
import { TR_TEXT } from '../config/text.ts';
import { batchSummary, screenTitleKey } from '../model/index.ts';
import type { RejectionKey, SummaryState, TabState } from '../model/index.ts';

const state = TR_TEXT.state;

/** 탭 옆 작은 상태 글. */
export function tabLabel(tab: TabState): string {
  return state.tab[tab];
}

/** 화면 제목(TR-03 세 갈래). */
export function screenTitle(parts: readonly { state: TabState }[]): string {
  return TR_TEXT.screenTitle[screenTitleKey(parts)];
}

/** 「3파트 중 1파트 완료 · 2파트 진행 중」. */
export function remainingLine(parts: readonly { state: TabState }[]): string {
  return TR_TEXT.tabs.remaining(
    parts.length,
    batchSummary(parts).map(({ state: key, n }) => ({
      label: state.summary[key],
      n,
    })),
  );
}

/** 묶음 셈 하나하나(「완료 2」·「진행 중 1」) — 배지마다 변형을 고르게 상태도 함께(밴드 TRP2 TC2). */
export function summaryItems(
  parts: readonly { state: TabState }[],
): { state: SummaryState; text: string }[] {
  return batchSummary(parts).map(({ state: key, n }) => ({
    state: key,
    text: state.summaryItem(state.summary[key], n),
  }));
}

/** 막은 까닭 → 까닭·안내(디자인 e9 — 분량 많음 + 그 밖 일반 실패. CEO 한도는 입력 화면이 막아 일반 실패 글, 밴드 TRW4). */
export function rejectionText(reason: RejectionKey): {
  reason: string;
  guide: string;
} {
  const { reason: text, guide } = TR_TEXT.rejection[reason];
  return { reason: text, guide };
}

/** 목록·표의 상태 한 덩이(「실패」·「진행 중 · 번역 20/38쪽」·「실패 · 일부 쪽」). */
export function partStatusLabel(
  tab: TabState,
  reason?: RejectionKey,
  pages?: { done: number; total: number },
): string {
  if (tab === 'running')
    return pages ?
        state.runningPages(pages.done, pages.total)
      : state.runningPrepare;
  if (tab === 'failed' && reason !== undefined)
    return TR_TEXT.rejection[reason].tail;
  return state.tab[tab];
}
