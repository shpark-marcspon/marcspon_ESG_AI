// 새 점검 폼 훅(밴드 FW1b ①, 시안 GW-02·02a). 모양을 모른다: 값·동작·사유 코드만 낸다.
//
// - 파일: 드롭존은 제어 부품이다. 새 항목을 받으면 status 'uploading' 으로 두고 store.createDocument 를 부른다.
//   거절되면 항목 status 'failed'(문구는 ui 가 드롭존 text.uploadFailed 로). 글자 없는 PDF 는 성공(hasText false)이다.
//   maxCount 1 이라 파일을 바꾸려면 지우기(×)를 먼저 한다. 지우면 문서도 놓는다(목 단계에서 버린다).
// - 쪽: 파트마다 글자 칸 하나. 글자를 바꾸면 늘 글자는 그대로 두고, 오류가 없을 때만 쪽 집합을 바꾼다.
//   썸네일 칠하기(누르기·끌기)는 쪽 집합을 바꾸고 글자를 압축 꼴로 다시 쓴다. 문서 쪽 수가 정해지거나 바뀌면 글자를 다시 읽는다.
// - 검사: 「점검 시작」을 누를 때 한다(버튼을 꺼 두지 않는다). 누른 뒤에는 고칠 때마다 사유가 다시 셈된다.
//   단 글자 없는 PDF 는 canStart=false(시안 GW-02a 대로 버튼을 끈다).
// - 실행 만들기는 열쇠(Idempotency-Key, 밴드 GR2 · sid:MARC-ISSUE-225)를 싣는다: 쥔 열쇠가 없으면 누를 때 새로 짓는다.
//   답이 끊기면(startError unreachable — 실행이 만들어졌는지 모른다) 열쇠를 쥔 채 단추를 켜 두고, 다시 누르면 같은 열쇠로 보낸다
//   (서버가 앞 실행을 돌려줘 실행은 하나). 끊김 뒤 입력을 바꿔 누르면 서버가 409(startError key_reused)를 내는데, 그때도 열쇠를 쥔다 —
//   새 열쇠로 보내면 실행이 둘이 될 수 있다(sid:MARC-ISSUE-312). 화면은 목록 확인으로 이끈다.
//   성공·다른 거절이면 열쇠를 버린다(다음 누름은 새 열쇠). 훅이 내려가면(화면을 떠나면) 같이 버려진다.
// - 근거 검색 범위는 고르지 않는다: 늘 지정한 파트의 쪽 안(2026-10-16 사용자 결정).
// - 대상 단어: 실행에는 추가 단어를 싣지 않는다(extraTerms 늘 [] — 서버가 관리자 판 단어로 센다). 「3. 점검 설정」 카드를 지우면서(시안 댓글,
//   sid:MARC-ENT-603) 기본 단어 목록 읽기(listDefaultTerms)도 걷었다 — 이 화면은 그 목록을 부르지 않는다.
// - 수정본 연결은 없다(v115, sid:MARC-ENT-354 2): previousDocumentId 는 늘 null, 이전 문서 목록을 읽지 않는다.
// - 보고연도 기본은 올해다. 시계는 now 로 받는다(시험에서 고정). 모든 빌드에서 싣는다 — 실어댑터가 실행 전 문서 PATCH 로 옮긴다(밴드 GW2R ③ Q8).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  newIdempotencyKey,
  storeErrorKind,
} from '../../../entities/greenwash/api/index.ts';
import type {
  CreatedDocument,
  GreenwashStore,
  NewIdempotencyKey,
  StoreErrorKind,
} from '../../../entities/greenwash/api/index.ts';
import {
  PART_KEYS,
  formatPageRange,
  parsePageRange,
  totalPages,
} from '../../../entities/greenwash/model/index.ts';
import type {
  PageRangeError,
  PartKey,
  PartPages,
} from '../../../entities/greenwash/model/index.ts';
import {
  paintModeAt,
  paintRange,
  togglePage,
  validateNewCheck,
} from '../model/index.ts';
import type { FormProblem, PaintMode } from '../model/index.ts';

/** 드롭존 항목 꼴(shared/ui/file-dropzone 의 DraggableInputItem 과 구조가 같다. hooks 는 shared/ui 를 가져오지 않는다). */
export interface UploadItem {
  id: string;
  name: string;
  size?: number;
  date: string;
  file?: File;
  status?: 'uploading' | 'failed';
}

export interface UploadedDocument extends CreatedDocument {
  itemId: string;
  file: File;
  fileName: string;
}

export interface PartField {
  /** 글자 칸의 글자(사람이 친 그대로). */
  text: string;
  /** 지금 쪽 집합(오름차순). */
  pages: readonly number[];
  /** 글자의 오류. 없으면 null. */
  error: PageRangeError | null;
}

export interface UseNewCheckFormOptions {
  store: GreenwashStore;
  /** 지금 시각. 기본 new Date(). */
  now?: () => Date;
  /** 실행 만들기 열쇠를 짓는 함수. 기본 newIdempotencyKey(시험이 고정한다). */
  newKey?: NewIdempotencyKey;
}

export interface NewCheckForm {
  // 파일
  items: readonly UploadItem[];
  onChangeItems(next: UploadItem[]): void;
  document: UploadedDocument | null;
  uploading: boolean;
  /** 올린 파일이 크기 한도로 거절됨(413 — 고를 때 드롭존이 못 막은 것). 그 항목을 지우면 거짓. */
  uploadTooLarge: boolean;
  // 보고연도
  reportYear: number | null;
  setReportYear(year: number | null): void;
  yearOptions: readonly number[];
  // 쪽
  fields: Readonly<Record<PartKey, PartField>>;
  parts: PartPages;
  setPartText(part: PartKey, text: string): void;
  activePart: PartKey;
  setActivePart(part: PartKey): void;
  /** 고른 파트에서 쪽 하나를 넣거나 뺀다(키보드 누르기). */
  pressPage(page: number): void;
  /** 끌기 시작(시작 쪽의 토글 방향을 정하고 그 쪽을 칠한다). */
  beginPaint(page: number): void;
  /** 끄는 중 지금 쪽까지 칠한다. 끌기 중이 아니면 아무것도 안 한다. */
  paintTo(page: number): void;
  endPaint(): void;
  /** 점검할 쪽 합계. */
  checkedPages: number;
  // 시작
  /** 시작 버튼을 켤 것인가(글자 없는 PDF 면 끈다. 실행 만들기 끊김은 켜 둔다 — 다시 누르면 같은 열쇠). */
  canStart: boolean;
  /** 「점검 시작」을 누른 뒤의 사유 목록. 누르기 전에는 비어 있다. 차례는 화면의 칸 차례(첫 사유의 칸으로 초점을 옮긴다). */
  problems: readonly FormProblem[];
  submitting: boolean;
  /** 실행 만들기가 거절됐으면 그 사유(밴드 FW2 ①, sid:MARC-ISSUE-99 1). 다시 누르면 지운다. */
  startError: StartError | null;
  /** 검사하고, 사유가 없으면 실행을 만들어 runId 를 돌려준다. 사유가 있거나 거절되면 null(거절은 startError). */
  start(): Promise<string | null>;
}

/** 실행 시작·[다시 실행]이 거절된 사유. 저장소의 StoreError 갈래(없으면 rejected). */
export type StartError = StoreErrorKind;

/** 실행에 싣는 추가 단어 — 늘 비었다(밴드 GW2R ①). */
const NO_EXTRA_TERMS: readonly string[] = [];

const emptyFields = (): Record<PartKey, PartField> => ({
  ceo: { text: '', pages: [], error: null },
  company: { text: '', pages: [], error: null },
  climate: { text: '', pages: [], error: null },
});

export function useNewCheckForm({
  store,
  now = () => new Date(),
  newKey = newIdempotencyKey,
}: UseNewCheckFormOptions): NewCheckForm {
  // 올해는 처음 그릴 때 한 번 정한다.
  const [thisYear] = useState(() => now().getFullYear());
  const [items, setItems] = useState<readonly UploadItem[]>([]);
  // 지역 이름은 uploaded(전역 document 와 헷갈리지 않게. headless 층 시험의 DOM 규칙, 밴드 FW2 ⓪). 돌려주는 칸 이름은 document.
  const [uploaded, setUploaded] = useState<UploadedDocument | null>(null);
  const [reportYear, setReportYear] = useState<number | null>(thisYear);
  const [fields, setFields] = useState<Record<PartKey, PartField>>(emptyFields);
  const [activePart, setActivePart] = useState<PartKey>('ceo');
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [startError, setStartError] = useState<StartError | null>(null);

  // 항목 id 를 견주려고 최신 목록을 적어 둔다(onChangeItems 만 목록의 id 를 바꾼다).
  const itemsRef = useRef(items);
  const uploadsRef = useRef(new Map<string, number>());
  /** 크기 한도로 거절된 항목 id(413 — GP1 §1-8). 항목이 목록에서 빠지면 안내도 사라진다. */
  const [tooLargeIds, setTooLargeIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const uploadSeqRef = useRef(0);
  /** 실행 만들기 열쇠. 보내는 동안과 끊긴 뒤에만 있다(성공·다른 거절이면 버린다). */
  const runKeyRef = useRef<string | null>(null);
  const paintRef = useRef<{
    part: PartKey;
    base: readonly number[];
    mode: PaintMode;
    from: number;
  } | null>(null);

  const pageCount = uploaded?.pageCount;
  // 문서 쪽 수가 정해지거나 바뀌면 글자를 다시 읽는다(글자는 그대로, 오류가 없을 때만 쪽을 바꾼다).
  useEffect(() => {
    setFields((current) => {
      const next = { ...current };
      for (const key of PART_KEYS) next[key] = reparse(current[key], pageCount);
      return next;
    });
  }, [pageCount]);

  const onChangeItems = useCallback(
    (next: UploadItem[]) => {
      const before = new Set(itemsRef.current.map((item) => item.id));
      const nextIds = new Set(next.map((item) => item.id));
      setUploaded((current) =>
        current && !nextIds.has(current.itemId) ? null : current,
      );
      const added = next.filter((item) => !before.has(item.id) && item.file);
      const marked = next.map((item) =>
        added.includes(item) ? { ...item, status: 'uploading' as const } : item,
      );
      itemsRef.current = marked;
      setItems(marked);
      // 올림마다 표지를 둔다: 지운 뒤 같은 id 로 다시 넣으면 앞 올림의 늦은 답을 버린다(검증 권고 2).
      for (const id of [...uploadsRef.current.keys()])
        if (!nextIds.has(id)) uploadsRef.current.delete(id);
      for (const item of added) {
        const file = item.file!;
        const token = ++uploadSeqRef.current;
        // 같은 id 로 다시 넣으면 앞 크기 거절 표지는 버린다
        setTooLargeIds((ids) => {
          if (!ids.has(item.id)) return ids;
          const next = new Set(ids);
          next.delete(item.id);
          return next;
        });
        uploadsRef.current.set(item.id, token);
        const current = () => uploadsRef.current.get(item.id) === token;
        store.createDocument(file).then(
          (created) => {
            if (!current()) return;
            setItems((list) =>
              list.map((it) =>
                it.id === item.id ? { ...it, status: undefined } : it,
              ),
            );
            setUploaded({
              ...created,
              itemId: item.id,
              file,
              fileName: item.name,
            });
          },
          (error: unknown) => {
            if (!current()) return;
            setItems((list) =>
              list.map((it) =>
                it.id === item.id ? { ...it, status: 'failed' } : it,
              ),
            );
            if (storeErrorKind(error) === 'too_large')
              setTooLargeIds((ids) => new Set(ids).add(item.id));
          },
        );
      }
    },
    [store],
  );

  const setPartText = useCallback(
    (part: PartKey, text: string) => {
      setFields((current) => ({
        ...current,
        [part]: reparse({ ...current[part], text }, pageCount),
      }));
    },
    [pageCount],
  );

  // 썸네일 칠하기는 그 파트의 글자 칸을 칠한 쪽의 압축 꼴로 다시 쓴다. 글자 칸에 오류가 있었으면 그 글자와 오류도 함께 사라진다:
  // 의도다(밴드 FW2 ⓪, sid:MARC-ISSUE-99 7) — 칠하기는 쪽 집합(마지막으로 맞았던 값)에서 출발하므로, 보이는 글자를 그 집합에 맞춘다.
  const setPages = useCallback((part: PartKey, pages: readonly number[]) => {
    setFields((current) => ({
      ...current,
      [part]: { text: formatPageRange(pages), pages, error: null },
    }));
  }, []);

  const pressPage = useCallback(
    (page: number) =>
      setPages(activePart, togglePage(fields[activePart].pages, page)),
    [activePart, fields, setPages],
  );

  const beginPaint = useCallback(
    (page: number) => {
      const base = fields[activePart].pages;
      const mode = paintModeAt(base, page);
      paintRef.current = { part: activePart, base, mode, from: page };
      setPages(activePart, paintRange(base, mode, page, page));
    },
    [activePart, fields, setPages],
  );

  const paintTo = useCallback(
    (page: number) => {
      const paint = paintRef.current;
      if (!paint) return;
      setPages(
        paint.part,
        paintRange(paint.base, paint.mode, paint.from, page),
      );
    },
    [setPages],
  );

  const endPaint = useCallback(() => {
    paintRef.current = null;
  }, []);

  const parts: PartPages = useMemo(
    () => ({
      ceo: fields.ceo.pages,
      company: fields.company.pages,
      climate: fields.climate.pages,
    }),
    [fields],
  );

  const uploading = items.some((item) => item.status === 'uploading');
  const uploadTooLarge = items.some(
    (item) => item.status === 'failed' && tooLargeIds.has(item.id),
  );
  const formDocument = useMemo(
    () =>
      uploaded && !uploading ?
        { pageCount: uploaded.pageCount, hasText: uploaded.hasText }
      : null,
    [uploaded, uploading],
  );
  const partErrors = useMemo(
    () => ({
      ceo: fields.ceo.error,
      company: fields.company.error,
      climate: fields.climate.error,
    }),
    [fields],
  );
  const problems =
    attempted ?
      validateNewCheck({ uploaded: formDocument, parts, partErrors })
    : [];

  const start = useCallback(async () => {
    setAttempted(true);
    const found = validateNewCheck({
      uploaded: formDocument,
      parts,
      partErrors,
    });
    setStartError(null);
    if (found.length > 0 || !uploaded) return null;
    setSubmitting(true);
    // 끊긴 뒤면 쥔 열쇠 그대로(서버에 실행이 생겼어도 하나로 이어진다)
    const key = runKeyRef.current ?? newKey();
    runKeyRef.current = key;
    try {
      const { runId } = await store.createRun(
        uploaded.documentId,
        {
          parts,
          extraTerms: NO_EXTRA_TERMS,
          reportYear,
          previousDocumentId: null,
        },
        key,
      );
      runKeyRef.current = null;
      return runId;
    } catch (error) {
      const kind = storeErrorKind(error);
      if (kind !== 'unreachable' && kind !== 'key_reused')
        runKeyRef.current = null;
      setStartError(kind);
      return null;
    } finally {
      setSubmitting(false);
    }
  }, [uploaded, formDocument, partErrors, parts, reportYear, newKey, store]);

  const yearOptions = useMemo(
    () => Array.from({ length: 7 }, (_, i) => thisYear + 1 - i),
    [thisYear],
  );

  return {
    items,
    onChangeItems,
    document: uploaded,
    uploading,
    uploadTooLarge,
    reportYear,
    setReportYear,
    yearOptions,
    fields,
    parts,
    setPartText,
    activePart,
    setActivePart,
    pressPage,
    beginPaint,
    paintTo,
    endPaint,
    checkedPages: totalPages(parts),
    canStart: !(uploaded && !uploaded.hasText),
    problems,
    submitting,
    startError,
    start,
  };
}

/** 글자를 다시 읽는다: 오류가 없으면 쪽을 바꾸고, 있으면 쪽은 그대로 두고 오류만 단다. */
function reparse(field: PartField, pageCount: number | undefined): PartField {
  const result = parsePageRange(field.text, pageCount);
  return result.ok ?
      { text: field.text, pages: result.pages, error: null }
    : { text: field.text, pages: field.pages, error: result.error };
}
