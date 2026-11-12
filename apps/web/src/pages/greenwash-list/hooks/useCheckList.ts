// 문서 목록 훅(밴드 FW2 ②, GW-01). 저장소의 목록 원재료(listCheckRows)를 읽어 domain 으로 줄을 짓고 거른다.
//   - 거르기 상태(검색·보고연도·상태 탭·내가 올린 것만)를 든다. 처음은 전체.
//   - 보고연도 고르기 칸의 값은 줄들의 보고연도(늦은 해 먼저, 없음은 뺀다).
//   - [다시 실행]은 useRerunAction(useRerun.ts — GW-03 과 같은 핵심, 밴드 WC1 ③). 거절되면 rerunError 에 그 실행 id 와 사유를 둔다
//     (화면은 role="alert"). 도는 동안(rerunning = 그 실행 id) 두 번째 누름은 부르지 않고 null(밴드 FW2 ⑤ M1).
//   - 숫자(문서 n건·실행 n회)는 거르기 전 기준: 문서 = 목록 줄 수(판 사슬의 마지막만), 실행 = 그 줄들 문서의 실행 수.
//   - retry(밴드 LE1 ①): 목록 읽기의 [다시 시도]. loading 을 거쳐 다시 읽는다.
//     무효 조건: 「문서 n건」이 앞 판까지 센 수라면 바꾼다(시안 숫자만으로는 가를 수 없다 — 디자인 물을 것).
import { useMemo, useState } from 'react';

import type {
  GreenwashStore,
  StoreErrorKind,
} from '../../../entities/greenwash/api/index.ts';
import { useRerunAction } from '../../../entities/greenwash/hooks/index.ts';
import {
  buildCheckRows,
  filterCheckRows,
} from '../../../entities/greenwash/model/index.ts';
import type {
  CheckRow,
  CheckRowFilter,
  CheckRowTab,
  CheckRowsSource,
} from '../../../entities/greenwash/model/index.ts';
import { useLoad } from '../../../shared/lib/useLoad.ts';

export type CheckListStatus =
  | { state: 'loading' }
  | { state: 'ready'; source: CheckRowsSource }
  | { state: 'failed' };

export interface CheckList {
  status: CheckListStatus;
  /** 목록을 다시 읽는다(loading 부터, 화면의 [다시 시도]). */
  retry(): void;
  /** 거른 줄. 읽기 전이면 빈 목록. */
  rows: readonly CheckRow[];
  /** 거르기 전 줄 수(문서 n건). */
  documentCount: number;
  /** 거르기 전 줄들 문서의 실행 수(실행 n회). */
  runCount: number;
  companyName: string;
  years: readonly number[];
  filter: CheckRowFilter;
  setQuery(query: string): void;
  setReportYear(year: number | null): void;
  setTab(tab: CheckRowTab): void;
  setMineOnly(mineOnly: boolean): void;
  /** 실패한 줄의 [다시 실행]. 새 runId, 거절되면 null. */
  rerun(runId: string): Promise<string | null>;
  /** [다시 실행]이 도는 중인 실행 id. 없으면 null. 도는 동안 다른 [다시 실행]은 부르지 않는다. */
  rerunning: string | null;
  rerunError: { runId: string; error: StoreErrorKind } | null;
}

const ALL: CheckRowFilter = {
  query: '',
  reportYear: null,
  tab: 'all',
  mineOnly: false,
};

export function useCheckList(store: GreenwashStore): CheckList {
  const { status: read, retry } = useLoad([store], () => store.listCheckRows());
  const status = useMemo<CheckListStatus>(
    () =>
      read.state === 'ready' ? { state: 'ready', source: read.data }
      : read.state === 'failed' ? { state: 'failed' }
      : { state: 'loading' },
    [read],
  );
  const [filter, setFilter] = useState<CheckRowFilter>(ALL);

  const source = status.state === 'ready' ? status.source : null;
  const all = useMemo(() => (source ? buildCheckRows(source) : []), [source]);
  const rows = useMemo(
    () => (source ? filterCheckRows(all, filter, source.currentUserId) : []),
    [all, filter, source],
  );
  const years = useMemo(
    () =>
      [
        ...new Set(
          all
            .map((row) => row.doc.reportYear)
            .filter((year): year is number => year !== null),
        ),
      ].sort((a, b) => b - a),
    [all],
  );
  const runCount = useMemo(() => {
    if (!source) return 0;
    const shown = new Set(all.map((row) => row.doc.documentId));
    return source.runs.filter((run) => shown.has(run.documentId)).length;
  }, [all, source]);

  const { rerun, rerunning, rerunError } = useRerunAction(store);

  return {
    status,
    retry,
    rows,
    documentCount: all.length,
    runCount,
    companyName: source?.companyName ?? '',
    years,
    filter,
    setQuery: (query) => setFilter((f) => ({ ...f, query })),
    setReportYear: (reportYear) => setFilter((f) => ({ ...f, reportYear })),
    setTab: (tab) => setFilter((f) => ({ ...f, tab })),
    setMineOnly: (mineOnly) => setFilter((f) => ({ ...f, mineOnly })),
    rerun,
    rerunning,
    rerunError,
  };
}
