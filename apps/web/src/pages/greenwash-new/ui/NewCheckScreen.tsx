// GW-02 새 점검 · GW-02a 글자 없는 PDF(밴드 FW1b ②, v115 GW-02_r2·GW-02a_r2 — 밴드 GW2R ①). 구성:
//   제목 줄(브레드크럼 없음) → STEP 1 → 카드 둘(1. 문서 올리기 / 2. 파트별 쪽 범위) → 오른쪽 아래 [취소]·[점검 시작].
//   「3. 점검 설정」 카드(근거 검색 범위·대상 단어 — 보이기만, 실행에 싣는 값 0)는 지웠다(시안 댓글, sid:MARC-ENT-603).
// GW-02a(글자 없는 PDF)는 카드 1 만 보이고, 오류 안내와 꺼진 [점검 시작](md)을 둔다 [R6].
// 동작은 headless 의 useNewCheckForm 이 쥐고, 저장소(store)와 PDF 여는 구현(openPdf)은 props 로 받는다.
// 보고연도 고르기는 공용 NativeSelect(ENT-430 — 네이티브 select 그대로, 꼴은 selectLook 한 자리).
// 수정본 연결 줄은 없다(v115 — sid:MARC-ENT-354 2, 밴드 GW2R ①).
// [점검 시작] 오류(밴드 FW2 ⓪, 디자인 대조 고칠 것 7): 사유는 칸마다 그 칸 아래에 둔다 — 파일 없음은 드롭존 아래, 300쪽 초과는 파일 줄 아래,
//   파트 없음은 파트 칸 묶음 아래, 쪽 범위는 이미 칸 아래. 누르면 첫 사유의 칸으로 스크롤하고 초점을 옮긴다.
//   버튼은 꺼 두지 않는다(글자 없는 PDF 만 끈다 — 시안 02a). 쪽 끝 버튼은 모두 md 알약(디자인 대조 고칠 것 6).
// 보고연도 줄은 모든 빌드에 있다(밴드 GW2R ③ Q8 — 실어댑터가 실행 전 문서 PATCH 로 싣는다. 옛 documentFields 갈래 걷음).
import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  MAX_PAGE_COUNT,
  MAX_UPLOAD_MB,
} from '../../../entities/greenwash/model/index.ts';
import { StepFlow } from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { FileDropzone } from '../../../shared/ui/file-dropzone/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { useNewCheckForm } from '../hooks/index.ts';
import type { FormProblem } from '../model/index.ts';
import { PartRanges } from './PartRanges.tsx';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from './formRows.ts';

const words = GW_TEXT.newCheck;

export interface NewCheckScreenProps {
  store: GreenwashStore;
  openPdf: OpenPdf;
  /** 보고연도 기본(올해)을 정할 시계. 기본 new Date(). */
  now?: () => Date;
  onCancel(): void;
  onStarted(runId: string): void;
}

export function NewCheckScreen({
  store,
  openPdf,
  now,
  onCancel,
  onStarted,
}: NewCheckScreenProps) {
  const form = useNewCheckForm({ store, now });
  const ids = useId();
  const uploadRef = useRef<HTMLDivElement>(null);
  const noText = form.document !== null && !form.document.hasText;
  const fileProblem = form.problems.find(
    (problem) =>
      problem.code === 'no_file' || problem.code === 'too_many_pages',
  );
  const partIds = `${ids}-part`;

  // 시작을 막은 뒤 첫 사유의 칸으로 스크롤·초점(그린 뒤라야 칸 아래 오류가 있다).
  // 누름마다 한 번만 옮긴다(handled 에 적는다): 사유가 바뀌며 다시 그려도 초점을 다시 뺏지 않는다.
  const [focusRequest, setFocusRequest] = useState(0);
  const handled = useRef(0);
  const firstProblem = form.problems[0];
  useEffect(() => {
    if (focusRequest === handled.current || !firstProblem) return;
    handled.current = focusRequest;
    const upload = uploadRef.current;
    const target: HTMLElement | null | undefined =
      firstProblem.code === 'no_file' ?
        upload?.querySelector<HTMLElement>('[role="button"]')
      : firstProblem.code === 'too_many_pages' ?
        upload?.querySelector<HTMLElement>('li button')
      : firstProblem.code === 'page_range' ?
        document.getElementById(`${partIds}-${firstProblem.part}`)
      : firstProblem.code === 'no_parts' ?
        document.getElementById(`${partIds}-ceo`)
      : null;
    target?.scrollIntoView?.({ block: 'center' });
    target?.focus({ preventScroll: true });
  }, [focusRequest, firstProblem, partIds]);

  return (
    <div data-screen="new" className="flex flex-col gap-6">
      <PageTitle title={words.title} description={words.description} />
      <StepFlow current={1} />

      <Card className="flex flex-col gap-5">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.upload.heading}
        </h3>
        <div ref={uploadRef} className="flex flex-col gap-2">
          <FileDropzone
            itemList={form.items}
            onChangeItemList={form.onChangeItems}
            accept={['.pdf']}
            maxMb={MAX_UPLOAD_MB}
            maxCount={1}
            guide={words.upload.guide}
            formats={words.upload.formats(MAX_PAGE_COUNT, MAX_UPLOAD_MB)}
            text={{
              uploadFailed: words.upload.uploadFailed,
              // 고를 때 막는 글도 서버 413 안내와 같은 글(GP1 §1-8)
              rejectReason: { size: words.upload.tooLarge(MAX_UPLOAD_MB) },
            }}
            itemMeta={(item) => {
              const uploaded = form.document;
              if (!uploaded || uploaded.itemId !== item.id) return null;
              return (
                <span
                  data-testid="file-meta"
                  // 글자 없는 PDF 도 회색 꼬리(시안 .e-file .meta — 경고는 아래 no-text 상자가 한다, GW3R2 SC8)
                  className="shrink-0 text-style-pre-caption-03 text-text-tertiary"
                >
                  {words.upload.fileMeta(
                    words.upload.pageMeta(uploaded.pageCount),
                    words.upload.fileSize(uploaded.file.size),
                    uploaded.hasText,
                  )}
                </span>
              );
            }}
          />
          {form.uploadTooLarge && (
            // 서버(또는 앞단)가 크기로 거절 — 「잠시 뒤 다시」가 아니라 한도를 말한다(GP1 §1-8)
            <FieldError testId="too-large" role="alert">
              {words.upload.tooLarge(MAX_UPLOAD_MB)}
            </FieldError>
          )}
          {fileProblem && (
            // 초점 대상(드롭존·지우기 단추)은 FileDropzone 안이라 aria-describedby 로 이을 수 없어 role="alert" 로 읽힌다.
            <FieldError testId="start-problems" role="alert">
              {problemText(fileProblem)}
            </FieldError>
          )}
        </div>
        {noText && (
          <>
            <PageInfo
              tone="error"
              icon={<PageInfoIcon />}
              data-testid="no-text"
            >
              {words.upload.noText}
            </PageInfo>
            <Help>{words.upload.noTextHow}</Help>
          </>
        )}
        <div className={FORM_ROWS_CLASS}>
          <Row label={words.year.label}>
            <NativeSelect
              aria-label={words.year.label}
              value={form.reportYear ?? ''}
              onChange={(event) =>
                form.setReportYear(
                  event.target.value === '' ? null : Number(event.target.value),
                )
              }
            >
              <option value="">{words.year.none}</option>
              {form.yearOptions.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </NativeSelect>
          </Row>
        </div>
      </Card>

      {!noText && (
        <Card className="flex flex-col gap-5" data-card="parts">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.parts.heading}
          </h3>
          <PartRanges form={form} openPdf={openPdf} idBase={partIds} />
        </Card>
      )}

      {form.startError !== null && (
        <PageInfo
          tone="error"
          role="alert"
          icon={<PageInfoIcon />}
          data-testid="start-error"
          data-error={form.startError}
        >
          {form.startError === 'unreachable' ?
            GW_TEXT.runUnreachable.start
          : form.startError === 'key_reused' ?
            words.keyReused.message
          : words.startRejected}
        </PageInfo>
      )}
      {
        // 409 키 재사용이면 안내 아래 [목록 보기](디자인 74 답 — sid:MARC-ISSUE-312). [점검 시작]은 켜 둔다(같은 열쇠로 보낸다).
        form.startError === 'key_reused' && (
          <div className="flex">
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              data-testid="start-error-to-list"
              onClick={onCancel}
            >
              {words.keyReused.toList}
            </Button>
          </div>
        )
      }
      <div className="flex justify-end gap-2">
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          onClick={onCancel}
        >
          {
            // 끊김이면 [취소] 자리가 목록으로 이끄는 단추다(밴드 GR1 — 디자인 e9 답 「+ [목록으로]」)
            form.startError === 'unreachable' ?
              GW_TEXT.load.toList
            : words.cancel
          }
        </Button>
        <Button
          variant="solidBlack"
          shape="round"
          size="md"
          disabled={!form.canStart}
          loading={form.submitting}
          onClick={async () => {
            const runId = await form.start();
            if (runId !== null) onStarted(runId);
            else setFocusRequest((n) => n + 1);
          }}
        >
          {words.start}
        </Button>
      </div>
    </div>
  );
}

/** 칸 아래 사유 글(파일 칸의 둘만 여기서 쓴다. 다른 칸은 그 칸이 제 문구를 낸다). */
function problemText(problem: FormProblem): string {
  switch (problem.code) {
    case 'no_file':
      return words.problems.no_file;
    case 'too_many_pages':
      return words.problems.too_many_pages(problem.pageCount, problem.max);
    default:
      return '';
  }
}

/** 칸 아래 오류 한 줄(PartRanges 의 쪽 범위 오류와 같은 꼴). */
export function FieldError({
  id,
  testId,
  role,
  children,
}: {
  id?: string;
  testId?: string;
  role?: 'alert';
  children: ReactNode;
}) {
  return (
    <p
      id={id}
      role={role}
      data-testid={testId}
      className="m-0 text-style-pre-caption-03 text-support-error"
    >
      {children}
    </p>
  );
}

/** 폼 한 줄: 왼쪽 이름 160, 오른쪽 값. */
function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className={FORM_ROW_CLASS}>
      <div className={FORM_LABEL_CLASS}>{label}</div>
      <div className={cn(FORM_VALUE_CLASS, 'flex-wrap items-center gap-3')}>
        {children}
      </div>
    </div>
  );
}

function Help({ children }: { children: ReactNode }) {
  return (
    <span className="text-style-pre-caption-03 text-text-tertiary">
      {children}
    </span>
  );
}
