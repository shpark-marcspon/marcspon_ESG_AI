// 용어집 칸 하나(밴드 TRW0a ②, 시안 TR-02·02a 「3. 용어집」 — 평가용어집(선택)·고객사 용어집(필수)이 같은 꼴). 모양 부품: props 만 받는다.
// - 빈 꼴: 키트 파일 칸(shared/ui/file-dropzone, .xlsx 하나). 고르면 onPick(파일).
// - 있는 꼴: 파일 이름 · 「국문 → 영문 n개」 · [바꾸기](파일 창을 열어 onPick).
// - [양식 내려받기]는 두 꼴 다(shared DownloadButton — loadTemplate 이 준 파일을 내려받게 한다).
// - 오류는 받은 글 그대로 한 줄씩(갈래 글은 어댑터 몫 — TR3a 뒤).
// 꼴(밴드 TRP2 TE8, 시안 TR-02 .e-formrows): 양식 줄 하나 — 이름 칸 160(제목·선택 표시) · 값 칸(파일 · [바꾸기] · [양식 내려받기] 한 줄,
//   빈 꼴은 파일 칸 아래 [양식 내려받기]) · 아래 오류·설명. 부르는 쪽이 FORM_ROWS_CLASS 묶음으로 감싼다.
// 빈 꼴 파일 칸의 안내·양식 내려받기 실패 글은 디자인 e9 의 답(config/text.ts).
// TRW0b(sid:MARC-ISSUE-307 2·3): [바꾸기] 의 숨긴 input 도 드롭존과 같은 판정(judgeFiles — 꼴·크기)을 거친 뒤 onPick.
//   칸 둘(평가·고객사)의 같은 이름 단추([바꾸기]·[양식 내려받기])는 칸을 이름 붙은 묶음(role="group", 이름 = 칸 제목)으로 가른다
//   — DownloadButton 이 aria-label 을 받지 않아(shared 0줄) 단추 이름 대신 묶음 이름으로.
import { useId, useRef } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { DownloadButton } from '../../../shared/ui/download-button/index.ts';
import {
  FileDropzone,
  judgeFiles,
} from '../../../shared/ui/file-dropzone/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';

const words = TR_TEXT.glossary;

/** 받는 형식(국문·영문 두 열의 엑셀). */
const ACCEPT = ['.xlsx'];
/** 드롭존과 같은 판정 규칙(꼴·크기 — 크기 상한은 드롭존처럼 두지 않는다). */
const RULE = { accept: ACCEPT, maxCount: 1 } as const;

export interface GlossaryFieldProps {
  title: string;
  required: boolean;
  /** 칸 아래 설명 한 줄(시안의 「평가에 맞춰 정리한 용어예요…」 꼴). */
  help?: string;
  /** 올린 용어집(이름·국문 → 영문 쌍 수). 없으면 빈 꼴. */
  file?: { name: string; pairCount: number };
  /** 오류 글(한 줄씩). */
  errors?: readonly string[];
  onPick(file: File): void;
  loadTemplate: () => Promise<{ blob: Blob; fileName: string }>;
  /** 칸의 data-testid. */
  testId?: string;
}

export function GlossaryField({
  title,
  required,
  help,
  file,
  errors = [],
  onPick,
  loadTemplate,
  testId,
}: GlossaryFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const template = (
    <DownloadButton
      label={words.template}
      failedText={words.templateFailed}
      load={loadTemplate}
      testId={testId === undefined ? undefined : `${testId}-template`}
      shape="square"
      size="sm"
    />
  );
  return (
    <div
      role="group"
      aria-labelledby={titleId}
      data-testid={testId}
      className={FORM_ROW_CLASS}
    >
      <div className={cn(FORM_LABEL_CLASS, 'flex-wrap')}>
        <span id={titleId}>
          {title}
          {required && <RequiredMark />}
        </span>
        {!required && (
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.evaluation.optional}
          </span>
        )}
      </div>
      <div className={cn(FORM_VALUE_CLASS, 'flex-col items-start gap-2')}>
        {file ?
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-style-pre-body-02 text-text-secondary">
              {file.name}
            </span>
            <span className="text-style-pre-caption-03 text-text-tertiary">
              {words.pairs(file.pairCount)}
            </span>
            <Button
              variant="outlineGrey"
              size="sm"
              onClick={() => inputRef.current?.click()}
            >
              {words.replace}
            </Button>
            {template}
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT.join(',')}
              hidden
              data-testid={testId === undefined ? undefined : `${testId}-input`}
              onChange={(event) => {
                const picked = event.target.files?.[0];
                if (
                  picked &&
                  judgeFiles([picked], [], RULE).accepted.length > 0
                )
                  onPick(picked);
                event.target.value = '';
              }}
            />
          </div>
        : <>
            <div className="w-full">
              <FileDropzone
                itemList={[]}
                onChangeItemList={(items) => {
                  const picked = items.at(-1)?.file;
                  if (picked) onPick(picked);
                }}
                accept={ACCEPT}
                maxCount={1}
                guide={words.guide}
              />
            </div>
            {template}
          </>
        }
        {errors.length > 0 && (
          <ul role="alert" className="m-0 flex list-none flex-col gap-1 p-0">
            {errors.map((error, index) => (
              <li
                key={index}
                className="flex items-start gap-1 [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0 text-style-pre-caption-03 text-support-error"
              >
                <CircleWarningIcon aria-hidden />
                {error}
              </li>
            ))}
          </ul>
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
