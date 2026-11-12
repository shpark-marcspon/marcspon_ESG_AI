// 원본 PDF 훅(밴드 TRW6 ①): store.openRunPdf(문서 id) — 저장소가 문서마다 한 벌 들고 있어 다시 그려도 요청은 하나.
//   loading → ready(File) | missing(404·409) | failed(그 밖 — retry 가 새로 보낸다). documentId 가 null 이면 loading.
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import type { TranslationStore } from '../api/index.ts';

export type RunPdfState =
  | { state: 'loading' }
  | { state: 'ready'; file: File }
  | { state: 'missing' }
  | { state: 'failed' };

export interface RunPdfHandle {
  status: RunPdfState;
  retry(): void;
}

export function useRunPdf(
  store: TranslationStore,
  documentId: string | null,
): RunPdfHandle {
  const { status, retry } = useLoad(
    documentId === null ? null : [store, 'pdf', documentId],
    () => store.openRunPdf(documentId!),
  );
  const out = useMemo<RunPdfState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') return { state: 'failed' };
    const pdf = status.data;
    return pdf.kind === 'ready' ?
        { state: 'ready', file: pdf.file }
      : { state: pdf.kind };
  }, [status]);
  return { status: out, retry };
}
