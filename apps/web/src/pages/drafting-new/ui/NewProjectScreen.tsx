// RP-02 새 보고서 프로젝트 · 전년도 보고서 올림(밴드 RPW1 ①, 시안 v188 RP-02_r1). 라우터를 모른다.
// 두 갈래: projectId null = 새로(/drafting/new — 보고연도·이름을 받는다) · projectId 값 = 다시 올리기(…/$projectId/document — 이름·연도는 보기만).
// [다음] = createProject(새로만) → uploadPdf(POST /documents → 서명 PUT → confirm) → attachDocument → onDone(그 id — 경로가 RP-03 으로 replace).
//   - confirm 의 hasText 거짓이면 달지 않고 멈춤 「텍스트를 찾지 못했어요」 · null 이면 PUT …/document 에 맡김(422 DOCUMENT_NO_TEXT_LAYER → 같은 글).
//     텍스트 없음이면 빨간 상자 + [다른 PDF 올리기], [다음] 끔 — 파일을 바꾸면 다시 켠다(RPW2 D#12).
//   - 파일 줄: 고른 파일의 크기 · 쪽 수 · [취소](올리는 중에만 — 서명 PUT 을 끊음. 만든 프로젝트는 남는다, RPW2 ⑨·RPW3 D3. 그 밖엔 드롭존 ✕ 하나). 날짜는 뺀다.
//   - 그 밖 올림·달기 실패 → 「PDF 를 읽지 못했어요」. 만든 뒤 올림이 실패하면 프로젝트는 남는다 — 다시 누르면 만들기를 건너뛴다(쥔 id).
//   - 만들기 거절 VALIDATION_ERROR 의 fields year·name 은 그 칸 아래 한 줄, 그 밖 「프로젝트를 만들지 못했어요」. 회사 거절은 회사 글.
// 회사 고름은 없다(§2-0 ② — sid:MARC-ENT-374). 「올리는 중 62%」의 바이트 % 는 fetch 로 잴 수 없어 「올리는 중」만(보고 「다르게 한 것」).
// 「페이지 읽는 중 n/m」 상태는 없다 — 올림은 confirm 까지(§2-0 ④). 서버 message 는 싣지 않는다.
import { useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  DraftingStore,
} from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { useProject } from '../../../entities/drafting/hooks/index.ts';
import { lengthOf } from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { FileDropzone } from '../../../shared/ui/file-dropzone/index.ts';
import type { DraggableInputItem } from '../../../shared/ui/file-dropzone/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';

const words = DR_TEXT.create;

/** 받는 형식. */
const ACCEPT = ['.pdf'];
/** 파일 줄에 날짜를 싣지 않는다(시안 — 크기·쪽 수만). */
const NO_DATE = () => '';
/** 이름 글자 수 상한(DraftingProjectCreateIn.name — 코드 포인트). */
export const NAME_MAX = 80;
/** 보고연도 범위(DraftingProjectCreateIn.year). */
const YEAR_MIN = 2000;
const YEAR_MAX = 2100;

export interface NewProjectScreenProps {
  store: DraftingStore;
  /** 다시 올리기의 프로젝트(새로면 null). */
  projectId: number | null;
  /** 참이면 다시 올리기(projectId 가 null 이면 주소 id 가 틀린 것 — 요청 없이 찾지 못함). 기본은 projectId 가 있을 때. */
  reupload?: boolean;
  operator: boolean;
  /** 지금(고를 해의 가운데 — 시험이 고정한다). */
  now?: Date;
  onCancel(): void;
  /** 문서를 단 프로젝트(→ RP-03). */
  onDone(projectId: number): void;
}

/** 화면 아래 한 줄 오류. */
type Problem =
  | { kind: 'noText' | 'readFailed' | 'createFailed' }
  | { kind: 'company'; company: CompanyRefusal };

/** 고를 수 있는 해: 내년부터 다섯(큰 해 먼저). */
export function yearChoices(now: Date): number[] {
  const year = now.getFullYear();
  return [year + 1, year, year - 1, year - 2, year - 3].filter(
    (one) => one >= YEAR_MIN && one <= YEAR_MAX,
  );
}

/** 이름 칸 오류(없으면 null). */
export function nameProblem(name: string): string | null {
  const length = lengthOf(name.trim());
  if (length === 0) return words.nameRequired;
  if (length > NAME_MAX) return words.nameTooLong(NAME_MAX);
  return null;
}

export function NewProjectScreen({
  store,
  projectId,
  reupload = projectId !== null,
  operator,
  now = new Date(),
  onCancel,
  onDone,
}: NewProjectScreenProps) {
  const yearId = useId();
  const nameId = useId();
  const problemId = useId();
  const years = yearChoices(now);
  const [year, setYear] = useState(now.getFullYear());
  const [name, setName] = useState<string | null>(null);
  const [items, setItems] = useState<DraggableInputItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<number | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [fields, setFields] = useState<{ year?: boolean; name?: boolean }>({});
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [touched, setTouched] = useState(false);
  /** 올리는 중의 끊개(그 밖 null). */
  const upload = useRef<AbortController | null>(null);
  const documentCard = useRef<HTMLElement>(null);
  const loaded = useProject(store, projectId);
  const project =
    reupload && projectId === null ?
      { ...loaded, status: { state: 'not_found' as const } }
    : loaded;
  const companyText = operator ? DR_TEXT.companyOperator : DR_TEXT.company;
  // 다시 올리기 첫 불러오기: 제목 + STEP 띠 뒤 300ms 뒤 LoadSkeleton(sid:MARC-ENT-443 ①, 밴드 RPW5 #4).
  const skeleton = useDelayed(reupload && project.status.state === 'loading');

  const shownName = name ?? words.nameDefault(year);
  const nameError =
    reupload ? null
    : fields.name ? words.nameRequired
    : touched ? nameProblem(shownName)
    : null;
  const file = items[0]?.file ?? null;
  const ready =
    !busy &&
    file !== null &&
    problem?.kind !== 'noText' &&
    (reupload ?
      project.status.state === 'ready'
    : nameProblem(shownName) === null);

  const onChangeItems = (next: DraggableInputItem[]) => {
    if (next.length === 0) upload.current?.abort();
    setProblem(null);
    setPageCount(null);
    setItems(next.slice(-1));
  };

  /** 파일을 걷고 파일 창을 다시 연다(D#12). */
  const pickOther = () => {
    onChangeItems([]);
    documentCard.current
      ?.querySelector<HTMLInputElement>('input[type="file"]')
      ?.click();
  };

  const submit = async () => {
    setTouched(true);
    if (!file || busy) return;
    if (!reupload && nameProblem(shownName) !== null) return;
    setBusy(true);
    setProblem(null);
    setFields({});
    const control = new AbortController();
    upload.current = control;
    try {
      let id = reupload ? projectId : created;
      if (reupload && id === null) return;
      if (id === null) {
        const out = await store.createProject({ year, name: shownName.trim() });
        if (out.kind !== 'ok') {
          if (out.kind === 'refused')
            setProblem({ kind: 'company', company: out.company });
          else if (
            out.kind === 'rejected' &&
            out.code === 'VALIDATION_ERROR' &&
            (out.fields?.year || out.fields?.name)
          )
            setFields({ year: !!out.fields.year, name: !!out.fields.name });
          else setProblem({ kind: 'createFailed' });
          return;
        }
        id = out.value.id;
        setCreated(id);
      }
      if (control.signal.aborted) return;
      const uploaded = await store.uploadPdf(file, control.signal);
      if (control.signal.aborted) return;
      if (uploaded.kind !== 'ok') {
        setProblem(
          uploaded.kind === 'refused' ?
            { kind: 'company', company: uploaded.company }
          : (
            uploaded.kind === 'rejected' &&
            uploaded.code === 'DOCUMENT_NO_TEXT_LAYER'
          ) ?
            { kind: 'noText' }
          : { kind: 'readFailed' },
        );
        return;
      }
      setPageCount(uploaded.value.pageCount);
      if (uploaded.value.hasText === false) {
        setProblem({ kind: 'noText' });
        return;
      }
      const attached = await store.attachDocument(
        id,
        uploaded.value.documentId,
      );
      if (attached.kind === 'ok') {
        onDone(id);
        return;
      }
      setProblem(
        attached.kind === 'refused' ?
          { kind: 'company', company: attached.company }
        : (
          attached.kind === 'rejected' &&
          attached.code === 'DOCUMENT_NO_TEXT_LAYER'
        ) ?
          { kind: 'noText' }
        : { kind: 'readFailed' },
      );
    } finally {
      upload.current = null;
      setBusy(false);
    }
  };

  const title = reupload ? words.reuploadTitle : words.title;

  if (reupload && project.status.state !== 'ready') {
    const status = project.status;
    return (
      <div data-screen="drafting-new" className="flex flex-col gap-6">
        <PageTitle
          title={title}
          descriptionPending={status.state === 'loading'}
        />
        <StepFlow
          current={1}
          steps={DR_TEXT.steps.items}
          label={DR_TEXT.steps.label}
        />
        {status.state === 'refused' ?
          <PageInfo
            role="alert"
            tone="error"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="company-refusal"
          >
            {companyText[status.company]}
          </PageInfo>
        : status.state === 'not_found' ?
          <LoadFailure
            kind="missing"
            message={words.projectMissing}
            listLabel={DR_TEXT.common.toList}
            onList={onCancel}
          />
        : status.state === 'failed' ?
          <LoadFailure
            kind="failed"
            message={words.projectLoadFailed}
            retryLabel={DR_TEXT.common.retry}
            onRetry={project.retry}
          />
        : skeleton && <LoadSkeleton />}
      </div>
    );
  }

  const problemText =
    problem === null ? null
    : problem.kind === 'company' ? companyText[problem.company]
    : words[problem.kind];

  return (
    <div data-screen="drafting-new" className="flex flex-col gap-6">
      <PageTitle
        title={title}
        description={reupload ? words.reuploadLead : words.lead}
      />
      <StepFlow
        current={1}
        steps={DR_TEXT.steps.items}
        label={DR_TEXT.steps.label}
      />
      <Card className="flex flex-col gap-4" data-card="project">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.projectSection}
        </h3>
        <div className={FORM_ROWS_CLASS}>
          <Row id={yearId} label={words.yearLabel}>
            {reupload && project.status.state === 'ready' ?
              <span data-testid="project-year" className="tabular-nums">
                {project.status.value.year}
              </span>
            : <>
                <NativeSelect
                  id={yearId}
                  value={String(year)}
                  disabled={busy || created !== null}
                  aria-invalid={fields.year || undefined}
                  onChange={(event) => setYear(Number(event.target.value))}
                >
                  {years.map((one) => (
                    <option key={one} value={one}>
                      {one}
                    </option>
                  ))}
                </NativeSelect>
                <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
                  {fields.year ? words.yearInvalid : words.yearHint}
                </p>
              </>
            }
          </Row>
          <Row id={nameId} label={words.nameLabel}>
            {reupload && project.status.state === 'ready' ?
              <span data-testid="project-name">
                {project.status.value.name}
              </span>
            : <>
                <Input
                  id={nameId}
                  value={shownName}
                  disabled={busy || created !== null}
                  aria-invalid={nameError !== null || undefined}
                  aria-describedby={nameError ? `${nameId}-error` : undefined}
                  onChange={(event) => {
                    setFields((old) => ({ ...old, name: false }));
                    setName(event.target.value);
                  }}
                  onBlur={() => setTouched(true)}
                  className={cn(
                    'w-1/2',
                    nameError !== null && 'border-support-error',
                  )}
                />
                {nameError && (
                  <p
                    id={`${nameId}-error`}
                    className="m-0 flex items-start gap-1 [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0 text-style-pre-caption-03 text-support-error"
                  >
                    <CircleWarningIcon aria-hidden />
                    {nameError}
                  </p>
                )}
              </>
            }
          </Row>
        </div>
      </Card>
      <Card
        ref={documentCard}
        className="flex flex-col gap-4"
        data-card="document"
      >
        <div className="flex items-baseline gap-2">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.documentSection}
          </h3>
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.documentHint}
          </span>
        </div>
        <FileDropzone
          itemList={items}
          onChangeItemList={onChangeItems}
          accept={ACCEPT}
          maxCount={1}
          today={NO_DATE}
          guide={words.dropGuide}
          formats={words.dropFormats}
          isUploading={busy}
          invalid={problem !== null && problem.kind !== 'createFailed'}
          {...(problemText ? { describedBy: problemId } : {})}
          text={{
            uploading: words.uploading,
            uploadFailed: words.readFailed,
            rejectReason: { type: words.notPdf },
          }}
          itemMeta={(item) => (
            <>
              {item.size !== undefined && (
                <span
                  data-testid="file-size"
                  className="shrink-0 text-style-pre-caption-03 text-text-tertiary tabular-nums"
                >
                  {words.size(item.size)}
                </span>
              )}
              {pageCount !== null && (
                <span
                  data-testid="file-meta"
                  className="shrink-0 text-style-pre-caption-03 text-text-tertiary"
                >
                  {words.pages(pageCount)}
                </span>
              )}
              {/* 차례 「크기 · 올리는 중 · [취소]」 — 드롭존이 메타 뒤에 그리는 상태 글 대신 여기서 그린다. */}
              {busy && (
                <>
                  <span
                    data-testid="file-uploading"
                    className="shrink-0 text-style-pre-caption-03 text-text-tertiary"
                  >
                    {words.uploading}
                  </span>
                  <Button
                    variant="outlineGrey"
                    shape="round"
                    size="sm"
                    className="ml-auto"
                    aria-label={words.cancelFile(item.name)}
                    onClick={() => onChangeItems([])}
                  >
                    {words.cancel}
                  </Button>
                </>
              )}
            </>
          )}
        />
        <div
          id={problemId}
          role="alert"
          data-testid="create-problem"
          data-problem={problem?.kind}
          className="empty:hidden"
        >
          {problemText && (
            <PageInfo tone="error" icon={<CircleWarningIcon aria-hidden />}>
              {problemText}
            </PageInfo>
          )}
        </div>
        {problem?.kind === 'noText' && (
          <div className="flex">
            <Button
              variant="outlineGrey"
              shape="round"
              size="sm"
              onClick={pickOther}
            >
              {words.otherPdf}
            </Button>
          </div>
        )}
      </Card>
      <div className="flex flex-wrap items-center justify-end gap-3">
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          onClick={onCancel}
        >
          {words.cancel}
        </Button>
        <Button
          variant="solidBlack"
          shape="round"
          size="md"
          loading={busy}
          disabled={!ready}
          onClick={() => void submit()}
        >
          {words.next}
        </Button>
      </div>
    </div>
  );
}

function Row({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className={FORM_ROW_CLASS}>
      <label htmlFor={id} className={FORM_LABEL_CLASS}>
        {label}
        <RequiredMark />
      </label>
      <div className={cn(FORM_VALUE_CLASS, 'flex-col justify-center gap-1.5')}>
        {children}
      </div>
    </div>
  );
}
