// 쪽 그림용 PDF 읽기 훅(밴드 FW2 ④, GW-05 가운데 칸). 실행 → 문서 → PDF 차례로 읽는다.
//   getRun(runId) 의 RunSnapshot.documentId 로 openDocumentPdf 를 부른다(밴드 FW2 ⑤ M2: 목록 원재료에서 찾으면
//   목록 읽기가 거절되거나 실행이 목록에 없을 때 「불러오는 중」에서 멈췄다. 실제 짝은 runs_get 하나다).
//   loading → ready(file: File, 또는 null = PDF 가 없음 — 목의 씨앗 문서) | missing(실행·PDF 읽기가 없음 404 — 밴드 LA1 ②,
//   sid:MARC-ENT-260 ③ 「없음엔 다시 시도 없음」) | failed(그 밖의 거절).
// retry(밴드 LE1 ①): 미리보기 칸의 [다시 시도]. loading 을 거쳐 실행·PDF 를 다시 읽는다(새 File 이라 ui 가 다시 연다).
// 실제 짝: 이 탭에서 올린 File, 없으면 서버 원본 GET /documents/{id}/file(실어댑터 — 밴드 GR3). File 을 여는 것(object URL·pdf.js)은 ui 몫이다.
import { useMemo } from 'react';

import { storeErrorKind } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { useLoad } from '../../../shared/lib/useLoad.ts';

export type DocumentPdfState =
  | { state: 'loading' }
  | { state: 'ready'; file: File | null }
  | { state: 'missing' }
  | { state: 'failed' };

export interface DocumentPdf {
  status: DocumentPdfState;
  /** 다시 읽는다(loading 부터). */
  retry(): void;
}

export function useDocumentPdf(
  store: GreenwashStore,
  runId: string,
): DocumentPdf {
  const { status, retry } = useLoad([store, runId], () =>
    store.getRun(runId).then((run) => store.openDocumentPdf(run.documentId)),
  );
  const state = useMemo<DocumentPdfState>(
    () =>
      status.state === 'ready' ? { state: 'ready', file: status.data }
      : status.state === 'failed' ?
        storeErrorKind(status.error) === 'not_found' ?
          { state: 'missing' }
        : { state: 'failed' }
      : { state: 'loading' },
    [status],
  );
  return { status: state, retry };
}
