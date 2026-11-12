// 새 번역 화면(밴드 TRW1a ②, 시안 TR-02·02a 확정 판 v136). 라우터를 모른다 — 저장소와 콜백 props 를 받는다.
// 1 파일(.docx·.txt 하나 → uploadDocument, 쪽 수는 서버가 센 [PAGE n] 최댓값 — TRP6) · 2 쪽 범위(쪽 수를 알면 PageGrid + 글자 칸,
// 모르면 글자 칸만 — over_last 검사 없음) · 3 용어집 둘(readGlossary, 고객사 필수) · 4 회사 정보 셋(필수)·스타일·참고 문체 ·
// 시작 전 확인 · [번역 시작](틀린 칸이 있거나 올리는 중·시작하는 중이면 끔 — aria-disabled 로 초점은 남긴다. 칸 오류는 파일을 올린 뒤부터) · [취소].
// [번역 시작] 한 번 = startBatch 한 번(두 번 눌러도 한 번 — ref). 일부 파트만 시작하면 onStarted 에 못 한 파트를 넘기고(감독 판단 4 ⓐ),
// 하나도 못 하면 이 화면에 남아 오류 한 줄(ⓑ). 옵션 바이트를 넘으면 TR-02a 글. 서버 message 는 보이지 않는다.
// 「앞 번역 설정 불러오기」·「같은 파일 다시 고르기」는 없다(TRW1b).
// [TRW6 ②] input="pdf"(TR-P02): .pdf 하나 → uploadPdf(쪽 수·글자 층은 confirm 답 — pages 경로를 부르지 않는다, W4) · 제목·파일 칸 글 ·
//   범위 카드 머리 안내 둘 · 칸 아래 PDF 기준 글 · hasText false 면 안내 한 줄(시작은 막지 않는다) · 시작 전 확인에 「머리글 · 꼬리말」 ·
//   단추 위 회색 줄 · startBatch 에 flowId. 워드(기본)는 DOM·요청이 BASE 그대로.
import { useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { Switch } from '@marcspon/ui/components/switch';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  GlossaryPair,
  GlossaryRead,
  StartInput,
  TranslationStore,
  UploadedPdf,
} from '../../../entities/translation/api/index.ts';
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  PART_KEYS,
  PDF_FLOW_ID,
  formatRange,
  pageCountOf,
} from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
} from '../../../entities/translation/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { FileDropzone } from '../../../shared/ui/file-dropzone/index.ts';
import type { DraggableInputItem } from '../../../shared/ui/file-dropzone/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { formProblems, readRanges, sizeText } from '../model/index.ts';
import { GlossaryField } from './GlossaryField.tsx';
import { PageGrid, PageGridLegend } from './PageGrid.tsx';
import { PartRangeFields } from './PartRangeFields.tsx';
import { PdfPageGrid } from './PdfPageGrid.tsx';
import { PreflightCard } from './PreflightCard.tsx';

const words = TR_TEXT.newTranslation;
const pdfWords = TR_TEXT.pdfNew;

/** 받는 형식(쪽마다 [PAGE n] 이 있는 추출본). */
const ACCEPT = ['.docx', '.txt'];
/** PDF 입력의 받는 형식(TR-P02). */
const PDF_ACCEPT = ['.pdf'];

type StyleChoice = 'A' | 'B' | 'AB';

export interface StartedBatch {
  documentId: string;
  batchKey: string;
  started: readonly PartKey[];
  failed: readonly PartKey[];
}

export interface NewTranslationScreenProps {
  store: TranslationStore;
  /** 오늘(파일 줄 날짜). 기본 new Date(). */
  now?: () => Date;
  onCancel(): void;
  onStarted(batch: StartedBatch): void;
  /** 입력 꼴(기본 word — 추출본). pdf 면 TR-P02(밴드 TRW6 ②). */
  input?: 'word' | 'pdf';
  /** PDF 입력이고 주면 쪽 칸 썸네일(밴드 TRW9). 워드는 받아도 쓰지 않는다. */
  openPdf?: OpenPdf;
}

interface GlossaryState {
  file?: { name: string; pairCount: number };
  pairs?: readonly GlossaryPair[];
  errors: string[];
}
const EMPTY_GLOSSARY: GlossaryState = { errors: [] };

/** 용어집 거절 → 화면 글(TR-02a, 밴드 TRW11). 종류마다 하나 — 새 종류가 생기면 never 검사가 잡는다. */
function glossaryError(read: Extract<GlossaryRead, { ok: false }>): string {
  const text = words.glossaryRejected;
  switch (read.kind) {
    case 'too_large':
      return text.too_large;
    case 'not_xlsx':
      return text.notXlsx;
    case 'unsafe_xlsx':
      return text.unsafe_xlsx;
    case 'bad_header':
      return text.bad_header;
    case 'empty_cell':
      return text.empty_cell(read.row);
    case 'not_text':
      return text.not_text(read.row);
    case 'too_long':
      return text.too_long(read.row);
    case 'duplicate_ko':
      return text.duplicate_ko(read.row);
    case 'too_many_rows':
      // 서버: 짝이 500 을 넘으면 그 행, 훑는 행이 10,000 을 넘으면 null.
      return read.row === null ?
          text.too_many_scanned_rows
        : text.too_many_rows;
    case 'no_rows':
      return text.no_rows;
    default: {
      const unhandled: never = read.kind;
      return unhandled;
    }
  }
}

const today = (now: () => Date) => {
  const at = now();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
};

export function NewTranslationScreen({
  store,
  now = () => new Date(),
  onCancel,
  onStarted,
  input = 'word',
  openPdf,
}: NewTranslationScreenProps) {
  const pdf = input === 'pdf';
  const ids = useId();
  const [items, setItems] = useState<DraggableInputItem[]>([]);
  // 워드 올림은 hasText 를 쓰지 않는다(늘 null 로 둔다 — 안내 줄은 PDF 만).
  const [doc, setDoc] = useState<(UploadedPdf & { itemId: string }) | null>(
    null,
  );
  const [uploading, setUploading] = useState(false);
  const [uploadFailed, setUploadFailed] = useState(false);
  const [texts, setTexts] = useState<Record<PartKey, string>>({
    ceo: '',
    story: '',
    general: '',
  });
  const [active, setActive] = useState<PartKey>('ceo');
  const [evaluation, setEvaluation] = useState<GlossaryState>(EMPTY_GLOSSARY);
  const [client, setClient] = useState<GlossaryState>(EMPTY_GLOSSARY);
  const [company, setCompany] = useState({
    name: '',
    preferredSubject: '',
    industryStandards: '',
  });
  const [style, setStyle] = useState<StyleChoice>('B');
  const [peerOn, setPeerOn] = useState(false);
  const [peerText, setPeerText] = useState('');
  const [starting, setStarting] = useState(false);
  const startingRef = useRef(false);
  const [startError, setStartError] = useState<'too_long' | 'failed' | null>(
    null,
  );
  /** 올림 차례(늦게 온 앞 올림의 답을 버린다). */
  const uploadSeq = useRef(0);

  const pageCount = doc?.pageCount ?? null;
  const pdfFile =
    doc === null ? null : (
      (items.find((item) => item.id === doc.itemId)?.file ?? null)
    );
  const { ranges, errors } = readRanges(texts, pageCount);
  const problems = formProblems({
    uploaded: doc !== null,
    ranges,
    errors,
    clientGlossary: client.pairs !== undefined,
    company,
  });
  const blocked = problems.length > 0 || uploading || starting;
  // 칸 오류는 파일을 올린 뒤부터 보인다(빈 화면에 빨간 글을 깔지 않는다). 끈 [번역 시작]은 눌리지 않는다(shared Button).
  const showProblems = doc !== null;
  const has = (code: (typeof problems)[number]['code']) =>
    showProblems && problems.some((problem) => problem.code === code);
  const filled = PART_KEYS.filter((part) => ranges[part] !== null);

  const upload = (item: DraggableInputItem) => {
    const file = item.file;
    if (!file) return;
    const seq = ++uploadSeq.current;
    setUploading(true);
    setUploadFailed(false);
    setDoc(null);
    const sent: Promise<UploadedPdf> =
      pdf ?
        store.uploadPdf(file)
      : store.uploadDocument(file).then((made) => ({ ...made, hasText: null }));
    sent.then(
      (made) => {
        if (seq !== uploadSeq.current) return;
        setDoc({ ...made, itemId: item.id });
        setItems((list) =>
          list.map((each) =>
            each.id === item.id ? { ...each, status: undefined } : each,
          ),
        );
        setUploading(false);
      },
      () => {
        if (seq !== uploadSeq.current) return;
        setItems((list) =>
          list.map((each) =>
            each.id === item.id ? { ...each, status: 'failed' } : each,
          ),
        );
        setUploadFailed(true);
        setUploading(false);
      },
    );
  };

  const onChangeItems = (next: DraggableInputItem[]) => {
    const added = next.find(
      (item) => !items.some((each) => each.id === item.id),
    );
    if (added) {
      const marked = {
        ...added,
        date: today(now),
        status: 'uploading' as const,
      };
      setItems([marked]);
      upload(marked);
      return;
    }
    setItems(next);
    if (next.length === 0) {
      uploadSeq.current += 1;
      setDoc(null);
      setUploading(false);
      setUploadFailed(false);
    }
  };

  const pickGlossary =
    (set: (state: GlossaryState) => void) => (file: File) => {
      store.readGlossary(file).then(
        (read) =>
          set(
            read.ok ?
              {
                file: { name: file.name, pairCount: read.rowCount },
                pairs: read.pairs,
                errors: [],
              }
            : { file: undefined, errors: [glossaryError(read)] },
          ),
        () => set({ errors: [words.upload.failedHelp] }),
      );
    };

  const paint = (part: PartKey, range: Range | null) =>
    setTexts((prev) => ({
      ...prev,
      [part]: range === null ? '' : formatRange(range),
    }));

  const start = () => {
    if (
      blocked ||
      startingRef.current ||
      doc === null ||
      client.pairs === undefined
    )
      return;
    startingRef.current = true;
    setStarting(true);
    setStartError(null);
    const input: StartInput = {
      documentId: doc.documentId,
      parts: filled.map((part) => ({ part, range: ranges[part]! })),
      company: {
        name: company.name.trim(),
        preferredSubject: company.preferredSubject.trim(),
        industryStandards: company.industryStandards.trim(),
      },
      style:
        style === 'AB' ?
          { compareAb: true, single: 'B' }
        : { compareAb: false, single: style },
      glossary: {
        ...(evaluation.pairs === undefined ? {} : { base: evaluation.pairs }),
        final: client.pairs,
      },
      peerGroupStyle: peerOn && peerText.trim() !== '' ? peerText : null,
      // PDF 만 싣는다(워드 본문에는 flowId 키가 없다 — W5).
      ...(pdf ? { flowId: PDF_FLOW_ID } : {}),
    };
    store.startBatch(input).then(
      (result) => {
        startingRef.current = false;
        setStarting(false);
        if (result.kind === 'too_long') {
          setStartError('too_long');
          return;
        }
        onStarted({
          documentId: result.documentId,
          batchKey: result.batchKey,
          started: result.runs.map((run) => run.part),
          failed: result.failed,
        });
      },
      () => {
        startingRef.current = false;
        setStarting(false);
        setStartError('failed');
      },
    );
  };

  const total = filled.reduce(
    (sum, part) => sum + pageCountOf(ranges[part]),
    0,
  );

  return (
    <div data-screen="translation-new" className="flex flex-col gap-6">
      <PageTitle
        title={pdf ? pdfWords.title : words.title}
        description={pdf ? pdfWords.description : words.description}
      />
      <StepFlow
        current={1}
        steps={words.steps}
        label={words.stepsLabel}
        prefix={words.stepPrefix}
      />

      <Card className="flex flex-col gap-4" data-card="file">
        <Heading>{words.upload.heading}</Heading>
        <FileDropzone
          itemList={items}
          onChangeItemList={onChangeItems}
          accept={pdf ? PDF_ACCEPT : ACCEPT}
          maxCount={1}
          guide={pdf ? pdfWords.upload.guide : words.upload.guide}
          {...(pdf ? { formats: pdfWords.upload.formats } : {})}
          isUploading={uploading}
          text={{
            uploading: words.upload.uploading,
            uploadFailed: words.upload.failed,
            rejectReason: {
              type: pdf ? pdfWords.upload.rejected : words.upload.rejected,
            },
          }}
          itemMeta={(item) =>
            doc !== null && doc.itemId === item.id ?
              <span
                data-testid="file-meta"
                className="shrink-0 text-style-pre-caption-03 text-text-tertiary"
              >
                {words.upload.meta(doc.pageCount, sizeText(doc.sizeBytes))}
              </span>
            : null
          }
        />
        {uploadFailed && (
          <FieldError role="alert">{words.upload.failedHelp}</FieldError>
        )}
        {pdf && doc !== null && doc.hasText === false && (
          <PageInfo
            tone="error"
            icon={<PageInfoIcon />}
            data-testid="pdf-no-text"
          >
            {pdfWords.upload.noText}
          </PageInfo>
        )}
        <Help>{pdf ? pdfWords.upload.note : words.upload.note}</Help>
      </Card>

      <Card className="flex flex-col gap-4" data-card="parts">
        <Heading>{words.rangeHeading}</Heading>
        {pdf && (
          <div data-testid="pdf-range-guide" className="flex flex-col gap-1">
            <Helper>{pdfWords.range.limit}</Helper>
            <Helper>{pdfWords.range.basis}</Helper>
          </div>
        )}
        <PartRangeFields
          input={input}
          grid={
            pageCount !== null && (
              <>
                {pdf && openPdf !== undefined && pdfFile !== null ?
                  <PdfPageGrid
                    file={pdfFile}
                    openPdf={openPdf}
                    pageCount={pageCount}
                    ranges={ranges}
                    active={active}
                    onPaint={paint}
                  />
                : <PageGrid
                    pageCount={pageCount}
                    ranges={ranges}
                    active={active}
                    onPaint={paint}
                  />
                }
                <PageGridLegend />
              </>
            )
          }
          pageCount={pageCount}
          ranges={ranges}
          texts={texts}
          errors={errors}
          active={active}
          onText={(part, text) =>
            setTexts((prev) => ({ ...prev, [part]: text }))
          }
          onActive={setActive}
        />
        {has('no_parts') && (
          <FieldError role="alert">{TR_TEXT.range.noParts}</FieldError>
        )}
        {/* 쪽 범위 오류가 하나라도 있으면 카드 끝에 안내 상자(밴드 TRP2 TE9, 시안 TR-02a) */}
        {Object.keys(errors).length > 0 && (
          <PageInfo
            tone="error"
            icon={<PageInfoIcon />}
            data-testid="range-error-help"
          >
            {pdf ?
              pdfWords.range.overLastHelp
            : TR_TEXT.range.errors.overLastHelp}
          </PageInfo>
        )}
      </Card>

      <Card className="flex flex-col gap-5" data-card="glossary">
        <Heading>{words.glossaryHeading}</Heading>
        <div className={FORM_ROWS_CLASS}>
          <GlossaryField
            title={TR_TEXT.glossary.evaluation.title}
            required={false}
            help={TR_TEXT.glossary.evaluation.help}
            file={evaluation.file}
            errors={evaluation.errors}
            onPick={pickGlossary(setEvaluation)}
            loadTemplate={() => store.glossaryTemplate()}
            testId="glossary-evaluation"
          />
          <GlossaryField
            title={TR_TEXT.glossary.client.title}
            required
            help={TR_TEXT.glossary.client.help}
            file={client.file}
            errors={
              has('client_glossary') && client.errors.length === 0 ?
                [TR_TEXT.glossary.client.missing]
              : client.errors
            }
            onPick={pickGlossary(setClient)}
            loadTemplate={() => store.glossaryTemplate()}
            testId="glossary-client"
          />
        </div>
        <Help>{TR_TEXT.glossary.note}</Help>
      </Card>

      <Card className="flex flex-col gap-5" data-card="company">
        <Heading>{words.company.heading}</Heading>
        <div className={FORM_ROWS_CLASS}>
          <TextField
            id={`${ids}-name`}
            label={words.company.name}
            value={company.name}
            invalid={has('company_name')}
            error={has('company_name') ? words.company.nameMissing : undefined}
            onChange={(name) => setCompany((prev) => ({ ...prev, name }))}
            // 칸 폭 절반(밴드 TRP3 ② TE8 — 시안 TR-02 회사 영문명 width 50%, 1440 에서 500)
            inputClassName="w-1/2"
          />
          <TextField
            id={`${ids}-subject`}
            multiline
            label={words.company.subject}
            value={company.preferredSubject}
            placeholder={words.company.subjectExample}
            invalid={has('company_subject')}
            help={words.company.subjectHelp}
            onChange={(preferredSubject) =>
              setCompany((prev) => ({ ...prev, preferredSubject }))
            }
          />
          <TextField
            id={`${ids}-standards`}
            multiline
            label={words.company.standards}
            value={company.industryStandards}
            placeholder={words.company.standardsExample}
            invalid={has('company_standards')}
            onChange={(industryStandards) =>
              setCompany((prev) => ({ ...prev, industryStandards }))
            }
          />
          <FormRow label={words.style.label}>
            <div
              role="radiogroup"
              aria-label={words.style.label}
              className="flex flex-col items-start gap-2"
            >
              {(['A', 'B', 'AB'] as const).map((choice) => (
                <label
                  key={choice}
                  className="flex cursor-pointer items-center gap-2 text-style-pre-body-06 text-text-secondary"
                >
                  {/* 16 · 고른 것은 5px #383C40 테두리(밴드 TRP2 TC9, 시안 .e-radio) */}
                  <input
                    className="m-0 box-border size-4 shrink-0 cursor-pointer appearance-none rounded-full border border-solid border-border-tertiary bg-background-primary checked:border-[5px] checked:border-border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary"
                    type="radio"
                    name={`${ids}-style`}
                    value={choice}
                    checked={style === choice}
                    onChange={() => setStyle(choice)}
                  />
                  {words.style[choice]}
                </label>
              ))}
              {style === 'AB' && <Help>{words.style.compareNote}</Help>}
            </div>
          </FormRow>
          <FormRow label={words.peer.label}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary">
                <Switch
                  className="w-9"
                  checked={peerOn}
                  onCheckedChange={setPeerOn}
                  aria-label={words.peer.toggle}
                />
                {words.peer.toggle}
              </label>
              {peerOn && (
                <Button
                  variant="outlineGrey"
                  size="sm"
                  onClick={() => setPeerText(words.peer.example)}
                >
                  {words.peer.fillExample}
                </Button>
              )}
            </div>
            {peerOn && (
              <Textarea
                aria-label={words.peer.label}
                value={peerText}
                onChange={(event) => setPeerText(event.target.value)}
                rows={6}
                className="h-40 px-4 py-3"
              />
            )}
            <Help>{words.peer.help}</Help>
          </FormRow>
        </div>
      </Card>

      {filled.length > 0 && (
        <PreflightCard
          pages={{
            total,
            parts: filled.map((part) => ({
              part,
              range: ranges[part]!,
              count: pageCountOf(ranges[part]),
            })),
          }}
          runs={filled.length}
          style={style}
          headerFooter={pdf}
        />
      )}

      {startError !== null && (
        <PageInfo
          tone="error"
          icon={<PageInfoIcon />}
          role="alert"
          data-testid="start-error"
        >
          {startError === 'too_long' ? words.tooLong : words.startFailed}
        </PageInfo>
      )}

      {pdf && <Help>{pdfWords.retryNote}</Help>}

      <div className="flex flex-wrap items-center justify-end gap-3">
        {problems.length > 0 && (
          <span
            data-testid="start-blocked"
            className="text-style-pre-caption-03 text-text-tertiary"
          >
            {words.blocked(problems.length)}
          </span>
        )}
        <Button
          variant="outlineGrey"
          size="md"
          shape="round"
          onClick={onCancel}
        >
          {words.cancel}
        </Button>
        <Button
          asChild
          variant="solidBlack"
          size="md"
          shape="round"
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

function Help({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
      {children}
    </p>
  );
}

/** 아이콘 붙은 회색 안내 한 줄(TR-P02 범위 카드 머리 — 판 e-helper). */
function Helper({ children }: { children: ReactNode }) {
  return (
    <p className="m-0 flex items-start gap-1 [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0 text-style-pre-caption-03 text-text-tertiary">
      <PageInfoIcon />
      {children}
    </p>
  );
}

function FieldError({
  children,
  role,
}: {
  children: ReactNode;
  role?: 'alert';
}) {
  return (
    <p
      role={role}
      className="m-0 flex items-start gap-1 [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0 text-style-pre-caption-03 text-support-error"
    >
      <CircleWarningIcon aria-hidden />
      {children}
    </p>
  );
}

function TextField({
  id,
  label,
  value,
  placeholder,
  invalid,
  error,
  help,
  multiline = false,
  inputClassName,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  invalid: boolean;
  error?: string;
  help?: string;
  /** 참이면 키트 Textarea(높이 96 · 안쪽 12 16 — 밴드 TRP2 TC10, 시안 사업 분야·공시 기준). */
  multiline?: boolean;
  /** 한 줄 칸(Input)에 덧붙이는 클래스(폭 등). */
  inputClassName?: string;
  onChange(value: string): void;
}) {
  return (
    <div className={FORM_ROW_CLASS}>
      <label htmlFor={id} className={FORM_LABEL_CLASS}>
        {label}
        <RequiredMark />
      </label>
      <div className={cn(FORM_VALUE_CLASS, 'flex-col justify-center gap-1.5')}>
        {multiline ?
          <Textarea
            id={id}
            value={value}
            placeholder={placeholder}
            aria-invalid={invalid || undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            onChange={(event) => onChange(event.target.value)}
            className={cn('h-24 px-4 py-3', invalid && 'border-support-error')}
          />
        : <Input
            id={id}
            value={value}
            placeholder={placeholder}
            aria-invalid={invalid || undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            onChange={(event) => onChange(event.target.value)}
            className={cn(inputClassName, invalid && 'border-support-error')}
          />
        }
        {error && (
          <p
            id={`${id}-error`}
            className="m-0 flex items-start gap-1 [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0 text-style-pre-caption-03 text-support-error"
          >
            <CircleWarningIcon aria-hidden />
            {error}
          </p>
        )}
        {help && (
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {help}
          </p>
        )}
      </div>
    </div>
  );
}

/** 양식 줄 하나(이름 칸 160 · 값 칸 세로 — 밴드 TRP2 TE8, 시안 TR-02 .e-formrows). 이름은 글자뿐(칸 이름은 값 쪽 aria 가 단다). */
function FormRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={FORM_ROW_CLASS}>
      <div className={FORM_LABEL_CLASS}>{label}</div>
      <div className={cn(FORM_VALUE_CLASS, 'flex-col justify-center gap-2')}>
        {children}
      </div>
    </div>
  );
}
