// DV-02 새 검증(밴드 DV2a ②, 시안 v148 DV-02_r1 + 2e ⑤⑦). 라우터를 모른다 — 저장소와 콜백 props 를 받는다.
// STEP 띠(1) → 1 데이터 넣기(키트 Tabs box: [파일 올리기] shared file-dropzone(.json 하나, 256KiB) · [붙여 넣기] 글 칸) → 미리 읽기 줄 →
// 2 기업 정보(기업명 · SASB 글자 칸(Q5) · 중대토픽 조각 + Enter · 보고연도 고르기(Q6)) → 3 검사 내용(정적) → [취소]·[검증 시작].
// 파일은 저장소에 올리지 않는다(문서 없는 흐름 — File.text() → readEdk → 거울). 「환경」 0 항목이어도 막지 않는다(서버가 경고 결과).
// [검증 시작]은 데이터를 읽기 전·크기 넘음·읽는 중·보내는 중이면 끔(눌러도 요청 0). 기업 칸이 틀리면 켜 둔 채 누르면 빈 칸마다 알리고
//   첫 오류 칸으로 초점을 옮긴다(요청 0 — 2e ⑤ 가 발주서 §2-2 「틀린 칸이면 끔」보다 앞선다). 한 번 = startRun 한 번(두 번 눌러도 — ref).
// 끝의 갈래: started → onStarted · too_large → 크기 글 · unreadable → 읽지 못함 글 · failed·unreachable → 시작 실패 글(넣은 내용은 그대로).
// 칸 오류는 [검증 시작]을 누른 뒤부터 보인다(빈 화면에 빨간 글을 깔지 않는다). 서버 message 는 보이지 않는다.
// 출처(밴드 DV2b): 파일이면 options.source = {kind:'file', name: File.name}, 붙여 넣기면 {kind:'paste'}. 크기 셈은 source 까지 넣고 잰다.
//   파일 이름이 서버 꼴 밖(`/`·제어 문자·255자 넘음 — model isSourceName)이면 [검증 시작]을 끄고 데이터 칸 오류 글(errors.badName, DV2c)을 보인다.
// DV2a 가지 리뷰 후속(DV2b): 붙여 넣기 읽기·크기 셈은 useMemo · 보내는 중 [취소] 끔 · 첫 오류 칸 초점은 칸 글이 깔린 뒤(useEffect) ·
//   토픽 칸 aria-describedby · 화면을 떠나면 저장소의 열쇠를 버린다(store.forget).
// 서버 입력 꼴(밴드 DV5): 읽은 데이터에 회사 칸이 실려 오면 빈 칸만 채운다(글자 칸은 빈칸뿐, 토픽은 빈 목록, 보고연도는 고르기를 안 건드렸고
//   그 연도가 고르기 안일 때). 사용자가 쓴 칸은 덮지 않는다. 채운 그 읽기 결과가 보이는 동안 안내 한 줄(role=status).
// EDK 인벤토리 엑셀(밴드 DVX1 ②): 받는 형식 .xlsx(첫째, 1MiB)·.json(256KiB — 넘으면 읽기 전에 크기 글). 확장자(소문자)로 가른다: .xlsx 는
//   store.readEdkXlsx(서버가 저장 없이 data 로 바꿈) → model readXlsxAnswer(같은 readData 한 길) / 거절은 kind 글 / 던짐은 읽지 못함 글.
//   보고연도를 고르지 않았으면 파일의 마지막 연도로(DV5 의 빈 칸만 규칙 — 안내는 yearFilled). 뺀 테마는 미리 읽기 아래 한 줄(수만).
//   올리기 칸 머리 오른쪽 [엑셀 양식 내려받기](shared DownloadButton — 화면 보고연도를 마지막 연도로). 서버 message 는 보이지 않는다.
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';

import { CloseIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import {
  EDK_MAX_CELL_CHARS,
  EDK_MAX_ITEMS,
  EDK_XLSX_MAX_BYTES,
} from '../../../entities/dataverify/api/index.ts';
import type {
  DataverifyStore,
  EdkReadKind,
} from '../../../entities/dataverify/api/index.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  OPTIONS_MAX_OCTETS,
  PASTE_SOURCE,
  buildInput,
  fileSource,
  isSourceName,
} from '../../../entities/dataverify/model/index.ts';
import type { Company } from '../../../entities/dataverify/model/index.ts';
import { Button, IconButton } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { DownloadButton } from '../../../shared/ui/download-button/index.ts';
import { FileDropzone } from '../../../shared/ui/file-dropzone/index.ts';
import type { DraggableInputItem } from '../../../shared/ui/file-dropzone/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import {
  addTopic,
  companyOf,
  companyProblems,
  optionsTooLarge,
  readData,
  readXlsxAnswer,
  sizeText,
  yearChoices,
} from '../model/index.ts';
import type { CompanyDraft, DataRead, FileRead } from '../model/index.ts';

const words = DV_TEXT.newCheck;

/** 받는 형식(.xlsx 첫째 · .json). 칸의 크기 상한은 엑셀의 1MiB(file-dropzone 이 MB×1024×1024 로 잰다) — .json 의 256KiB 는 readFile 머리에서. */
const ACCEPT = ['.xlsx', '.json'];
const MAX_MB = EDK_XLSX_MAX_BYTES / (1024 * 1024);
const isXlsx = (name: string) => name.toLowerCase().endsWith('.xlsx');

type Source = 'file' | 'paste';
type StartError = 'too_large' | 'unreadable' | 'failed';

interface CheckRow {
  step: string;
  body: string;
}

/** 빈 칸만 채운 회사(바뀐 칸이 없으면 prev 그대로). 보고연도는 yearOpen 이고 고르기 안일 때만. */
function fillEmpty(
  prev: CompanyDraft,
  fill: Partial<Company>,
  yearOpen: boolean,
  years: readonly string[],
): CompanyDraft {
  const next = { ...prev };
  if (fill.name !== undefined && prev.name.trim() === '') next.name = fill.name;
  if (fill.sasbIndustry !== undefined && prev.sasbIndustry.trim() === '')
    next.sasbIndustry = fill.sasbIndustry;
  if (fill.materialTopics !== undefined && prev.materialTopics.length === 0)
    next.materialTopics = fill.materialTopics.reduce(
      addTopic,
      prev.materialTopics,
    );
  if (
    fill.reportingYear !== undefined &&
    yearOpen &&
    years.includes(fill.reportingYear)
  )
    next.reportingYear = fill.reportingYear;
  const same = (Object.keys(prev) as (keyof CompanyDraft)[]).every(
    (key) => next[key] === prev[key],
  );
  return same ? prev : next;
}

const CHECK_ROWS: CheckRow[] = words.checks.map(([step, body]) => ({
  step,
  body,
}));

/** 검사 내용 표(정적 — 정렬 없음, 밴드 DV3 W1). 긴 칸은 줄바꿈. */
const CHECK_COLUMNS: DataTableColumnDef<CheckRow>[] = [
  {
    id: 'step',
    accessorKey: 'step',
    header: words.checksHead[0],
    enableSorting: false,
    // 잰 폭(1280 가장 긴 단계 max-content + 32, 밴드 DVW1 ②-4)
    meta: { width: 84 },
    cell: ({ row }) => (
      <span className="whitespace-nowrap">{row.original.step}</span>
    ),
  },
  {
    id: 'body',
    accessorKey: 'body',
    header: words.checksHead[1],
    enableSorting: false,
  },
];

/** 표 긴 칸 위아래 12(시안 .e-table 긴 칸 mod-r1.css 8). 공용 DataTable 을 고치지 않고 칸 자손으로 덮는다. */
const ROW_PADDING = '[&_td]:py-3';

export interface NewScreenProps {
  store: DataverifyStore;
  /** 오늘(보고연도 고르기). 기본 new Date(). */
  now?: () => Date;
  onCancel(): void;
  onStarted(runId: string): void;
}

export function NewScreen({
  store,
  now = () => new Date(),
  onCancel,
  onStarted,
}: NewScreenProps) {
  const ids = useId();
  const [{ years, fallback }] = useState(() => yearChoices(now()));
  const [source, setSource] = useState<Source>('file');
  const [items, setItems] = useState<DraggableInputItem[]>([]);
  const [fileRead, setFileRead] = useState<
    | (FileRead<EdkReadKind> & { itemId: string; bytes: number; name: string })
    | null
  >(null);
  const [reading, setReading] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [company, setCompany] = useState<CompanyDraft>({
    name: '',
    sasbIndustry: '',
    materialTopics: [],
    reportingYear: fallback,
  });
  const [topicDraft, setTopicDraft] = useState('');
  /** 그리기마다 맞추는 회사 거울(늦게 끝난 파일 읽기가 지금 칸을 본다). */
  const companyRef = useRef(company);
  companyRef.current = company;
  /** 보고연도를 사용자가 골랐는가(골랐으면 파일로 채우지 않는다). */
  const yearPicked = useRef(false);
  /** 회사 빈 칸을 채운 읽기 결과(그 결과가 보이는 동안 안내). */
  const [filledBy, setFilledBy] = useState<FileRead<EdkReadKind> | null>(null);
  const [starting, setStarting] = useState(false);
  const startingRef = useRef(false);
  const [startError, setStartError] = useState<StartError | null>(null);
  const checksTable = useDataTable({
    data: CHECK_ROWS,
    columns: CHECK_COLUMNS,
    getRowId: (row) => row.step,
  });
  /** 읽기 차례(늦게 온 앞 파일의 답을 버린다). */
  const readSeq = useRef(0);

  const pasteRead: DataRead | null = useMemo(
    () => (pasteText.trim() === '' ? null : readData(pasteText)),
    [pasteText],
  );
  const read = source === 'file' ? fileRead : pasteRead;

  /** 읽은 결과에 회사 칸이 있으면 빈 칸만 채운다. */
  const fillFrom = (next: FileRead<EdkReadKind>) => {
    if (next.kind !== 'ok' || next.company === undefined) return;
    const fill = next.company;
    const merge = (prev: CompanyDraft) =>
      fillEmpty(prev, fill, !yearPicked.current, years);
    if (merge(companyRef.current) === companyRef.current) return;
    setCompany(merge);
    setFilledBy(next);
  };
  useEffect(() => {
    if (pasteRead !== null) fillFrom(pasteRead);
    // 붙여 넣은 글을 새로 읽었을 때만(fillFrom 은 그리기마다 새 함수 — 지금 칸은 ref 로 본다).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pasteRead]);
  const data = read?.kind === 'ok' ? read : null;
  const fileName = fileRead?.name ?? null;
  /** 보낼 출처(파일 이름이 서버 꼴 밖이면 null — 보내지 않는다). */
  const inputSource = useMemo(
    () =>
      source === 'paste' ? PASTE_SOURCE
      : fileName !== null && isSourceName(fileName) ? fileSource(fileName)
      : null,
    [source, fileName],
  );
  const badName = source === 'file' && data !== null && inputSource === null;
  const sized = useMemo(
    () =>
      data !== null &&
      optionsTooLarge(data.data, company, inputSource ?? undefined),
    [data, company, inputSource],
  );
  const tooLarge = read?.kind === 'too_large' || sized;
  /** 엑셀에서 읽은 데이터인가(크기 글을 「읽은 항목이 너무 많아」로). */
  const fromXlsx = data?.xlsx !== undefined;
  const problems = companyProblems(company);
  // 데이터를 읽기 전·크기 넘음·파일 이름이 꼴 밖·읽는 중·보내는 중이면 끔. 기업 칸 문제는 끄지 않는다 — 누르면 칸 글을 깔고 첫 오류 칸으로(2e ⑤).
  const ready = data !== null && !tooLarge && !badName;
  const blocked = reading || starting || !ready;
  const [tried, setTried] = useState(false);
  const showProblems = tried;
  const has = (code: 'name' | 'sasb' | 'topics') =>
    showProblems &&
    problems.some(
      (problem) =>
        problem.code === code ||
        (problem.code === 'ill_formed' && problem.field === code),
    );
  const missing = (code: 'name' | 'sasb' | 'topics') =>
    showProblems && problems.some((problem) => problem.code === code);

  const dataError = (): string | null => {
    if (source === 'file') {
      if (fileRead?.kind === 'converted_too_large' || (sized && fromXlsx))
        return words.errors.convertedTooLarge;
      if (tooLarge) return words.errors.fileTooLarge;
      if (fileRead?.kind === 'not_json' || fileRead?.kind === 'shape')
        return words.errors.fileUnreadable;
      if (fileRead?.kind === 'xlsx_unreachable')
        return words.errors.xlsxUnreachable;
      if (fileRead?.kind === 'xlsx_rejected')
        return xlsxError(fileRead.reason, fileRead.row, fileRead.column);
      if (badName) return words.errors.badName;
      return null;
    }
    if (tooLarge) return words.errors.pasteTooLarge;
    if (pasteRead?.kind === 'not_json') return words.errors.pasteNotJson;
    if (pasteRead?.kind === 'shape') return words.errors.fileUnreadable;
    return null;
  };

  const readFile = (item: DraggableInputItem) => {
    const file = item.file;
    if (!file) return;
    const seq = ++readSeq.current;
    setReading(true);
    setFileRead(null);
    const done = (next: FileRead<EdkReadKind>) => {
      if (seq !== readSeq.current) return;
      const stored = {
        ...next,
        itemId: item.id,
        bytes: file.size,
        name: file.name,
      };
      setFileRead(stored);
      fillFrom(stored);
      setItems((list) =>
        list.map((each) =>
          each.id === item.id ? { ...each, status: undefined } : each,
        ),
      );
      setReading(false);
    };
    if (isXlsx(file.name)) {
      store.readEdkXlsx(file).then(
        (answer) => done(readXlsxAnswer(answer)),
        () => done({ kind: 'xlsx_unreachable' }),
      );
      return;
    }
    // .json 의 상한은 칸(1MiB)보다 작다 — 넘으면 읽지 않는다(BASE 의 칸 거름과 같은 끝).
    if (file.size > OPTIONS_MAX_OCTETS) {
      done({ kind: 'too_large' });
      return;
    }
    file.text().then(
      (text) => done(readData(text, file.size)),
      () => done({ kind: 'not_json' }),
    );
  };

  const onChangeItems = (next: DraggableInputItem[]) => {
    setStartError(null);
    const added = next.find(
      (item) => !items.some((each) => each.id === item.id),
    );
    if (added) {
      // 날짜는 싣지 않는다(파일 줄 = 「테마 n개 · 항목 n개 · 크기」 — 2e ⑦).
      const marked = { ...added, date: '', status: 'uploading' as const };
      setItems([marked]);
      readFile(marked);
      return;
    }
    setItems(next);
    if (next.length === 0) {
      readSeq.current += 1;
      setFileRead(null);
      setReading(false);
    }
  };

  const onTopicKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' || event.nativeEvent.isComposing) return;
    event.preventDefault();
    setCompany((prev) => ({
      ...prev,
      materialTopics: addTopic(prev.materialTopics, topicDraft),
    }));
    setTopicDraft('');
  };

  // 첫 오류 칸 초점은 칸 글(aria-describedby)이 깔린 그리기 뒤에 옮긴다(누를 때마다 한 번 — 새 객체).
  const [focusTo, setFocusTo] = useState<{ id: string } | null>(null);
  useEffect(() => {
    if (focusTo !== null) document.getElementById(focusTo.id)?.focus();
  }, [focusTo]);

  // 화면을 떠나면 쥔 열쇠를 버린다(다음 화면의 새 검증은 새 열쇠).
  useEffect(() => () => store.forget(), [store]);

  const start = () => {
    if (blocked || startingRef.current || data === null || inputSource === null)
      return;
    if (problems.length > 0) {
      setTried(true);
      const first = problems[0]!;
      const field = first.code === 'ill_formed' ? first.field : first.code;
      setFocusTo({
        id: `${ids}-${field === 'topics' ? 'topics-input' : field}`,
      });
      return;
    }
    startingRef.current = true;
    setStarting(true);
    setStartError(null);
    store.startRun(buildInput(companyOf(company), data.data), inputSource).then(
      (result) => {
        startingRef.current = false;
        setStarting(false);
        if (result.kind === 'started') {
          onStarted(result.runId);
          return;
        }
        setStartError(
          result.kind === 'too_large' || result.kind === 'unreadable' ?
            result.kind
          : 'failed',
        );
      },
      () => {
        startingRef.current = false;
        setStarting(false);
        setStartError('failed');
      },
    );
  };

  const dataErrorId = `${ids}-data-error`;
  const error =
    startError === 'too_large' ?
      source === 'file' ?
        fromXlsx ? words.errors.convertedTooLarge
        : words.errors.fileTooLarge
      : words.errors.pasteTooLarge
    : startError === 'unreadable' ? words.errors.fileUnreadable
    : dataError();

  return (
    <div data-screen="dataverify-new" className="flex flex-col gap-6">
      <PageTitle title={words.title} description={words.lead} />
      <StepFlow
        current={1}
        steps={DV_TEXT.steps.items.map((item) => item.label)}
        label={DV_TEXT.steps.label}
      />

      <Card className="flex flex-col gap-4" data-card="data">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Heading>{words.dataTitle}</Heading>
          <div className="flex flex-col items-end gap-1">
            <DownloadButton
              label={words.templateDownload}
              failedText={words.templateFailed}
              load={() => store.downloadEdkTemplate(company.reportingYear)}
              testId="template"
              size="sm"
            />
            <Note>{words.templateHint}</Note>
          </div>
        </div>
        <Tabs
          variant="line"
          value={source}
          onValueChange={(next) => {
            setSource(next as Source);
            setStartError(null);
          }}
        >
          <TabsList aria-label={words.tabsLabel}>
            <TabsTrigger value="file">{words.tabFile}</TabsTrigger>
            <TabsTrigger value="paste">{words.tabPaste}</TabsTrigger>
          </TabsList>
        </Tabs>
        {/* 탭을 바꾸면 칸이 새로 붙어 비친다(밴드 DV3 ②-7 — 탭 단추는 밖이라 초점이 그대로) */}
        <div key={source} className="gw-m-fade">
          {source === 'file' ?
            <FileDropzone
              itemList={items}
              onChangeItemList={onChangeItems}
              accept={ACCEPT}
              maxMb={MAX_MB}
              maxCount={1}
              guide={words.dropTitle}
              formats={words.dropHint}
              isUploading={reading}
              // 칸 오류(data-error 가 보이는 갈래)일 때만 aria 를 잇는다(DV2d — FZ1 prop).
              invalid={error !== null}
              describedBy={error !== null ? dataErrorId : undefined}
              text={{
                removeFile: words.removeFile,
                uploading: words.reading,
                rejectReason: {
                  type: words.errors.notJsonFile,
                  size: words.errors.fileTooLarge,
                },
              }}
              itemMeta={(item) =>
                fileRead?.kind === 'ok' && fileRead.itemId === item.id ?
                  <span
                    data-testid="file-meta"
                    className="shrink-0 text-style-pre-caption-02 text-text-tertiary"
                  >
                    {words.fileLine(
                      fileRead.preview.themes,
                      fileRead.preview.items,
                      sizeText(fileRead.bytes),
                    )}
                  </span>
                : null
              }
            />
          : <Textarea
              aria-label={words.pasteLabel}
              placeholder={words.pastePlaceholder}
              value={pasteText}
              aria-invalid={error !== null || undefined}
              onChange={(event) => {
                setPasteText(event.target.value);
                setStartError(null);
              }}
              rows={8}
            />
          }
        </div>
        {source === 'file' && reading && <Help>{words.readingHint}</Help>}
        {data !== null && (
          <PageInfo icon={<PageInfoIcon />} data-testid="preview">
            {words.preview(
              data.preview.envItems,
              data.preview.envKeyItems,
              DV_TEXT.yearSpan(data.preview.years),
            )}
          </PageInfo>
        )}
        {data !== null &&
          data.xlsx !== undefined &&
          data.xlsx.skipped.themes > 0 && (
            <Help testId="skipped-themes">
              {words.skippedThemes(
                data.xlsx.skipped.themes,
                data.xlsx.skipped.items,
              )}
            </Help>
          )}
        {error !== null && (
          <FieldError id={dataErrorId} role="alert" testId="data-error">
            {error}
          </FieldError>
        )}
      </Card>

      <Card className="flex flex-col gap-5" data-card="company">
        <Heading>{words.companyTitle}</Heading>
        {/* 이름 160 + 값 칸 줄 넷(시안 .e-formrows — 밴드 DV3 W2) */}
        <div className={FORM_ROWS_CLASS}>
          <TextField
            id={`${ids}-name`}
            label={words.name}
            value={company.name}
            invalid={has('name')}
            error={missing('name') ? words.required.name : undefined}
            onChange={(name) => setCompany((prev) => ({ ...prev, name }))}
          />
          <TextField
            id={`${ids}-sasb`}
            label={words.sasb}
            value={company.sasbIndustry}
            invalid={has('sasb')}
            error={missing('sasb') ? words.required.sasb : undefined}
            onChange={(sasbIndustry) =>
              setCompany((prev) => ({ ...prev, sasbIndustry }))
            }
          />
          <div className={FORM_ROW_CLASS}>
            <span id={`${ids}-topics`} className={FORM_LABEL_CLASS}>
              {words.topics}
              <RequiredMark />
            </span>
            <div
              className={cn(
                FORM_VALUE_CLASS,
                'flex-col justify-center gap-1.5',
              )}
            >
              <div
                role="group"
                aria-labelledby={`${ids}-topics`}
                className="flex flex-wrap items-center gap-2"
              >
                {company.materialTopics.map((topic) => (
                  <span
                    key={topic}
                    data-testid="topic"
                    className="inline-flex h-8 items-center gap-1 rounded-control bg-background-secondary pl-3 pr-1 text-style-pre-body-04 text-text-secondary"
                  >
                    {topic}
                    <IconButton
                      size="sm"
                      aria-label={words.topicRemove(topic)}
                      onClick={() =>
                        setCompany((prev) => ({
                          ...prev,
                          materialTopics: prev.materialTopics.filter(
                            (each) => each !== topic,
                          ),
                        }))
                      }
                    >
                      <CloseIcon />
                    </IconButton>
                  </span>
                ))}
                <Input
                  id={`${ids}-topics-input`}
                  aria-label={words.topicAdd}
                  aria-required={
                    company.materialTopics.length === 0 || undefined
                  }
                  placeholder={words.topicPlaceholder}
                  value={topicDraft}
                  aria-invalid={has('topics') || undefined}
                  aria-describedby={
                    missing('topics') ? `${ids}-topics-error` : undefined
                  }
                  onChange={(event) => setTopicDraft(event.target.value)}
                  onKeyDown={onTopicKey}
                  className={cn(
                    'w-60',
                    has('topics') && 'border-support-error',
                  )}
                />
                <Note>{words.topicsHint}</Note>
              </div>
              {missing('topics') && (
                <FieldError id={`${ids}-topics-error`}>
                  {words.required.topics}
                </FieldError>
              )}
            </div>
          </div>
          <div className={FORM_ROW_CLASS}>
            <label htmlFor={`${ids}-year`} className={FORM_LABEL_CLASS}>
              {words.year}
              <RequiredMark />
            </label>
            <div className={cn(FORM_VALUE_CLASS, 'items-center')}>
              <NativeSelect
                id={`${ids}-year`}
                required
                value={company.reportingYear}
                onChange={(event) => {
                  yearPicked.current = true;
                  // 엑셀이 고른 보고연도를 바꾸면 그 안내는 맞지 않는다(엑셀은 보고연도만 채운다).
                  if (filledBy?.kind === 'ok' && filledBy.xlsx !== undefined)
                    setFilledBy(null);
                  setCompany((prev) => ({
                    ...prev,
                    reportingYear: event.target.value,
                  }));
                }}
              >
                {years.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </NativeSelect>
            </div>
          </div>
        </div>
        <div role="status" data-testid="company-filled">
          {filledBy !== null &&
            filledBy === read &&
            ((
              filledBy.kind === 'ok' &&
              filledBy.xlsx !== undefined &&
              filledBy.company?.reportingYear !== undefined
            ) ?
              <Help>{words.yearFilled(filledBy.company.reportingYear)}</Help>
            : <Help>{words.companyFilled}</Help>)}
        </div>
        <Note>{words.companyHint}</Note>
      </Card>

      <Card className="flex flex-col gap-4" data-card="checks">
        <Heading>{words.checksTitle}</Heading>
        <DataTable
          table={checksTable}
          aria-label={words.checksTitle}
          layout="fixed"
          className={ROW_PADDING}
        />
      </Card>

      {startError === 'failed' && (
        <PageInfo
          tone="error"
          icon={<PageInfoIcon />}
          role="alert"
          data-testid="start-error"
        >
          {words.errors.startFailed}
        </PageInfo>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          disabled={starting}
          onClick={onCancel}
        >
          {words.cancel}
        </Button>
        <Button
          asChild
          variant="solidBlack"
          shape="round"
          size="md"
          loading={starting}
          disabled={blocked}
          className={
            blocked ?
              'aria-disabled:cursor-not-allowed aria-disabled:opacity-40'
            : undefined
          }
        >
          <button type="button" data-testid="start" onClick={start}>
            {words.start}
          </button>
        </Button>
      </div>
    </div>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return (
    <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
      {children}
    </h3>
  );
}

function Help({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <p
      data-testid={testId}
      className="m-0 text-style-pre-caption-02 text-text-tertiary"
    >
      {children}
    </p>
  );
}

/** 엑셀 읽기 거절 → 글(kind 마다 — 서버 글은 쓰지 않는다). */
function xlsxError(
  kind: EdkReadKind,
  row: number | null,
  column: number | null,
): string {
  const xlsx = words.errors.xlsx;
  switch (kind) {
    case 'bad_cell':
      return xlsx.bad_cell(row);
    case 'no_theme':
      return xlsx.no_theme(row);
    case 'too_many_rows':
      return xlsx.too_many_rows(EDK_MAX_ITEMS);
    case 'long_cell':
      return xlsx.long_cell(row, column, EDK_MAX_CELL_CHARS);
    default:
      return xlsx[kind];
  }
}

/** 기업 정보 카드의 도움 글(400 12 — 시안 .g-small, 밴드 DV3 W2). */
function Note({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
      {children}
    </p>
  );
}

function FieldError({
  children,
  id,
  role,
  testId,
}: {
  children: ReactNode;
  id?: string;
  role?: 'alert';
  testId?: string;
}) {
  return (
    <p
      id={id}
      role={role}
      data-testid={testId}
      className="m-0 text-style-pre-caption-02 text-support-error"
    >
      {children}
    </p>
  );
}

function TextField({
  id,
  label,
  value,
  invalid,
  error,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  invalid: boolean;
  error?: string;
  onChange(value: string): void;
}) {
  return (
    <div className={FORM_ROW_CLASS}>
      <label htmlFor={id} className={FORM_LABEL_CLASS}>
        {label}
        <RequiredMark />
      </label>
      <div className={cn(FORM_VALUE_CLASS, 'flex-col justify-center gap-1.5')}>
        <Input
          id={id}
          value={value}
          aria-required
          aria-invalid={invalid || undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => onChange(event.target.value)}
          className={cn('w-1/2', invalid && 'border-support-error')}
        />
        {error && (
          <p
            id={`${id}-error`}
            className="m-0 text-style-pre-caption-02 text-support-error"
          >
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
