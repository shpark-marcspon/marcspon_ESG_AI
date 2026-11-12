// AD-02 판 목록 읽기(밴드 AD2R ③, AD2W ① — 모듈 슬롯의 port.list). 판 하나 읽기는 prompt-model 훅(usePromptModel)이 한다.
//   - 목록: 처음·[다시 시도]는 loading 을 거치고, 저장·적용 뒤 다시 받기(refresh)는 지금 화면을 둔 채 받는다. [더 보기]는 다음 쪽을 이어 붙인다.
//     늦게 온 답은 세대 셈이 버린다.
//   - AD2W ④(cd 답 10-22): 저장 뒤 다시 받기(refreshKeep)는 실패해도 지금 목록을 둔다 — 받았는지(true/false)만 돌려준다(화면이 띠 한 줄로 알린다).
import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  AiSettingPort,
  VersionPage,
} from '../../../entities/ai-setting/model/index.ts';

export type AiSettingsState =
  | { phase: 'loading' }
  | { phase: 'failed' }
  | { phase: 'ready'; page: VersionPage; more: boolean; loadingMore: boolean };

export function useAiSettings(port: AiSettingPort) {
  const [state, setState] = useState<AiSettingsState>({ phase: 'loading' });
  const generation = useRef(0);

  /** 첫 쪽을 받는다. keep 이면 실패해도 지금 상태를 둔다. 받았으면 true. */
  const load = useCallback(
    (quiet: boolean, keep = false) => {
      const mine = ++generation.current;
      if (!quiet) setState({ phase: 'loading' });
      return port.list(0).then(
        (outcome) => {
          if (mine !== generation.current) return false;
          if (outcome.kind !== 'ok') {
            if (!keep) setState({ phase: 'failed' });
            return false;
          }
          setState({
            phase: 'ready',
            page: outcome.page,
            more: outcome.page.rows.length < outcome.page.total,
            loadingMore: false,
          });
          return true;
        },
        () => {
          if (mine === generation.current && !keep)
            setState({ phase: 'failed' });
          return false;
        },
      );
    },
    [port],
  );

  useEffect(() => {
    void load(false);
    const counter = generation;
    return () => {
      counter.current++;
    };
  }, [load]);

  /** 다음 쪽을 이어 붙인다(실패하면 지금 줄을 둔 채 [더 보기]가 다시 켜진다). */
  const loadMore = useCallback(() => {
    if (state.phase !== 'ready' || !state.more || state.loadingMore) return;
    const mine = ++generation.current;
    const before = state.page;
    setState({ ...state, loadingMore: true });
    void port.list(before.rows.length).then(
      (outcome) => {
        if (mine !== generation.current) return;
        if (outcome.kind !== 'ok') {
          setState({ ...state, loadingMore: false });
          return;
        }
        const rows = [...before.rows, ...outcome.page.rows];
        setState({
          phase: 'ready',
          page: { ...outcome.page, rows },
          more: rows.length < outcome.page.total,
          loadingMore: false,
        });
      },
      () => {
        if (mine === generation.current)
          setState({ ...state, loadingMore: false });
      },
    );
  }, [port, state]);

  return {
    state,
    retry: useCallback(() => void load(false), [load]),
    refresh: useCallback(() => load(true), [load]),
    /** 저장 뒤 다시 받기 — 실패하면 지금 목록을 둔다(받았으면 true). */
    refreshKeep: useCallback(() => load(true, true), [load]),
    loadMore,
  };
}
