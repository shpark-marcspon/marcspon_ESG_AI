// 원고작성 읽기 훅(밴드 RPW1 ① — 온실가스 hooks/useRead.ts 꼴, 가져오지 않는다). 실어댑터의 읽기를 useLoad 로 — key 가 바뀌면 다시 읽는다.
// 상태: loading → ready(값) | refused(회사 거절 셋) | not_found | failed. 화면은 상태와 retry·reload 만 받는다.
// 결과·원본 PDF(경계 ③)는 저장소의 갈래(ResultOutcome·PdfOutcome)에 loading 하나를 더해 그대로 낸다.
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import type {
  CompanyRefusal,
  DraftingStore,
  PdfOutcome,
  ReadOutcome,
  ResultOutcome,
} from '../api/index.ts';
import type { Project, ProjectPage, RunPage } from '../model/index.ts';

export type ReadState<T> =
  | { state: 'loading' }
  | { state: 'ready'; value: T }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'not_found' }
  | { state: 'failed' };

export interface ReadHandle<T> {
  status: ReadState<T>;
  retry(): void;
  reload(): void;
}

/** 읽기 하나를 상태로. key 가 null 이면 읽지 않는다(loading 그대로). */
export function useRead<T>(
  key: readonly unknown[] | null,
  load: () => Promise<ReadOutcome<T>>,
): ReadHandle<T> {
  const { status, retry, reload } = useLoad(key, load);
  const out = useMemo<ReadState<T>>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') return { state: 'failed' };
    const outcome = status.data;
    switch (outcome.kind) {
      case 'ok':
        return { state: 'ready', value: outcome.value };
      case 'refused':
        return { state: 'refused', company: outcome.company };
      case 'not_found':
        return { state: 'not_found' };
      default:
        return { state: 'failed' };
    }
  }, [status]);
  return { status: out, retry, reload };
}

/** RP-01 목록. */
export function useProjects(store: DraftingStore): ReadHandle<ProjectPage> {
  return useRead([store], () => store.listProjects());
}

/** 프로젝트 하나(RP-02 다시 올리기·RP-03·RP-04). */
export function useProject(
  store: DraftingStore,
  projectId: number | null,
): ReadHandle<Project> {
  return useRead(projectId === null ? null : [store, projectId], () =>
    store.getProject(projectId!),
  );
}

/** 프로젝트의 실행 목록(RP-04 실행 고르기 — 경계 ④). */
export function useRuns(
  store: DraftingStore,
  projectId: number,
): ReadHandle<RunPage> {
  return useRead([store, projectId], () => store.listRuns(projectId));
}

/** RP-04 결과(경계 ③). 끝나기 전(409 RUN_NOT_DONE)은 not_done — 화면은 done 실행에서만 부른다. */
export function useResult(
  store: DraftingStore,
  runId: number,
): { status: ResultOutcome | { kind: 'loading' }; retry(): void } {
  const { status, retry } = useLoad([store, runId], () =>
    store.getResult(runId),
  );
  return {
    status:
      status.state === 'loading' ? { kind: 'loading' }
      : status.state === 'failed' ? { kind: 'failed' }
      : status.data,
    retry,
  };
}

/** 원본 PDF 파일(경계 ③ — 저장소 openPdf 가 문서마다 한 벌을 쥔다). */
export function usePdfFile(
  store: DraftingStore,
  documentId: number,
): { status: PdfOutcome | { kind: 'loading' }; retry(): void } {
  const { status, retry } = useLoad([store, documentId], () =>
    store.openPdf(documentId),
  );
  return {
    status:
      status.state === 'loading' ? { kind: 'loading' }
      : status.state === 'failed' ? { kind: 'failed' }
      : status.data,
    retry,
  };
}
