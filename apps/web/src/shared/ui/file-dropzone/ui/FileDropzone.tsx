// 파일 드롭존(끌어다 놓기 칸 + 파일 목록). 키트 file-dropzone 대신 다시 만들었다(밴드 FK2, FV3 4.3·7.2).
//
// 키트와 다른 자리:
//   - 칸은 키보드로 연다: button 역할, Tab 으로 닿고 Enter·Space 로 파일 창을 연다(키트는 키보드로 열 수 없었다).
//   - 판정은 domain 의 순수 함수(judgeFiles). 확장자는 정확히 비교하고, MIME 와일드카드는 따로, 같은 이름은 한 번에 고른 것끼리도 본다.
//   - 거부된 파일은 사유와 함께 칸 아래에 보인다(걸러서 통과).
//   - emptyContent 로 칸을 통째로 바꾸는 동작은 들이지 않았다.
//   - hideDrop — 칸만 숨김, [×] 는 남김 · sid:MARC-ISSUE-439. readOnly 와 같이 오면 readOnly 가 이긴다(칸·[×] 둘 다 없음).
//   - 문구는 props 로 받는다. 기본 문구(지우기·업로드 중·업로드 실패·거부 사유)는 shared/ui/text.ts 에 있다.
// 하지 않는 것: 실제 업로드(네트워크), bulk-upload-dialog. 올리는 중은 isUploading 과 항목의 status 로만 보인다.
import * as React from 'react';

import {
  CloseIcon,
  UploadIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Spinner } from '@marcspon/ui/components/spinner';
import { cn } from '@marcspon/ui/lib/utils';

import { IconButton } from '../../button/index.ts';
import { PARTS_TEXT } from '../../text.ts';
import type { RejectLimits } from '../../text.ts';
import { useFileDropzone } from '../hooks/index.ts';
import type {
  DraggableInputItem,
  UseFileDropzoneOptions,
} from '../hooks/index.ts';
import { formatsLabel } from '../model/index.ts';
import type { RejectReason } from '../model/index.ts';

export type { RejectLimits };

/** 거부 사유 문구 하나: 고정 글자, 또는 한도 값(형식·MB·개수)을 받아 글자를 만드는 함수. */
export type RejectReasonText = string | ((limits: RejectLimits) => string);

export interface FileDropzoneText {
  removeFile: string;
  uploading: string;
  uploadFailed: string;
  rejectReason: Record<RejectReason, RejectReasonText>;
}

/**
 * 바꿀 문구. 거부 사유도 일부만 줄 수 있다(빠진 것은 components/text.ts 의 기본).
 * 기본 거부 사유는 한도 값을 끼운다: 형식은 accept 의 확장자(formatsLabel), 크기는 maxMb, 개수는 maxCount(밴드 FW1 ⓪).
 */
export type FileDropzoneTextInput = Partial<
  Omit<FileDropzoneText, 'rejectReason'>
> & { rejectReason?: Partial<Record<RejectReason, RejectReasonText>> };

export interface FileDropzoneProps extends Omit<
  UseFileDropzoneOptions,
  'disabled'
> {
  /** 칸 안의 안내 글(예: 「파일을 끌어다 놓거나 눌러서 고르세요」). */
  guide: React.ReactNode;
  /** 칸 안의 형식·크기 안내(예: 「xlsx, pdf · 20MB 이하」). */
  formats?: React.ReactNode;
  /** 참이면 칸이 흐려지고 도는 표시를 보인다. 칸은 열리지 않는다. */
  isUploading?: boolean;
  /** 기본 문구를 바꾼다(components/text.ts 의 값 위에 덮는다). */
  text?: FileDropzoneTextInput;
  /**
   * 파일 줄의 meta 칸(밴드 FW2 ⓪, 시안 e-file 의 meta 「60쪽 · 18.4MB」). 이름 바로 뒤, 날짜 앞에 놓인다.
   * 글자 꼴(색)은 돌려주는 요소가 정한다. 안 주거나 null 이면 칸이 없다.
   */
  itemMeta?: (item: DraggableInputItem) => React.ReactNode;
  /** 참이면 칸에 aria-invalid 를 단다(밴드 FZ1). 보이는 꼴은 바꾸지 않는다 — 오류 글은 쓰는 쪽이 칸 밖에 그린다. */
  invalid?: boolean;
  /** 칸의 aria-describedby. 쓰는 쪽이 오류 글 요소의 id 를 넘긴다(밴드 FZ1). */
  describedBy?: string;
  /**
   * 참이면 끌어다 놓기 칸과 숨긴 입력을 그리지 않는다. 파일 줄과 ✕(지우기)는 남는다(sid:MARC-ISSUE-439).
   * readOnly 의 뜻은 그대로다: readOnly 면 이 값과 상관없이 칸도 ✕ 도 없다.
   */
  hideDrop?: boolean;
  className?: string;
}

function FileDropzone({
  guide,
  formats,
  isUploading = false,
  text,
  itemMeta,
  invalid = false,
  describedBy,
  hideDrop = false,
  className,
  ...options
}: FileDropzoneProps) {
  const words: FileDropzoneText = {
    removeFile: text?.removeFile ?? PARTS_TEXT.removeFile,
    uploading: text?.uploading ?? PARTS_TEXT.uploading,
    uploadFailed: text?.uploadFailed ?? PARTS_TEXT.uploadFailed,
    rejectReason: {
      type: text?.rejectReason?.type ?? PARTS_TEXT.rejectReason.type,
      size: text?.rejectReason?.size ?? PARTS_TEXT.rejectReason.size,
      duplicate:
        text?.rejectReason?.duplicate ?? PARTS_TEXT.rejectReason.duplicate,
      count: text?.rejectReason?.count ?? PARTS_TEXT.rejectReason.count,
    },
  };
  const limits: RejectLimits = {
    formats: formatsLabel(options.accept),
    maxMb: options.maxMb,
    maxCount: options.maxCount,
  };
  const reasonText = (reason: RejectReason) => {
    const entry = words.rejectReason[reason];
    return typeof entry === 'function' ? entry(limits) : entry;
  };
  const dropzone = useFileDropzone({ ...options, disabled: isUploading });
  const readOnly = options.readOnly ?? false;
  const showDrop = !readOnly && !hideDrop;
  return (
    <div className={cn('flex flex-col', className)}>
      {showDrop && (
        <>
          <div
            {...dropzone.zoneProps}
            aria-busy={isUploading || undefined}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            data-dragging={dropzone.isDragging || undefined}
            className={cn(
              'flex min-h-[200px] w-full cursor-pointer flex-col items-center justify-center gap-1 rounded-component border border-dashed border-text-quaternary px-4 text-center transition-colors duration-200 hover:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary',
              dropzone.isDragging && 'bg-background-secondary',
              isUploading && 'cursor-wait opacity-40 hover:bg-transparent',
            )}
          >
            {isUploading ?
              <Spinner
                aria-label={words.uploading}
                className="size-6 text-text-brand"
              />
            : <UploadIcon aria-hidden className="size-6 text-text-tertiary" />}
            <p className="text-style-pre-body-04 text-text-secondary">
              {guide}
            </p>
            {formats != null && (
              <p className="text-style-pre-caption-02 text-text-tertiary">
                {formats}
              </p>
            )}
          </div>
          {/* 숨긴 입력은 칸 밖에 둔다: 칸 안에 두면 input.click() 의 클릭이 칸으로 올라와 다시 창을 연다 */}
          <input {...dropzone.inputProps} />
        </>
      )}
      {/* 거부 사유를 알리는 자리. 늘 그려 두고 안의 줄만 바꾼다(처음부터 있어야 화면 읽기 프로그램이 바뀐 것을 읽는다).
          role="status" 를 쓴다: 사용자가 방금 한 일의 결과라 끼어들지 않고(polite) 알리면 되고, 판정 묶음 하나를 통째로(atomic) 읽는 것이 맞다.
          role="alert"(assertive)는 쓰지 않았다. 목록 의미는 안의 ul 이 지킨다. 비어 있을 때 자리를 차지하지 않게 바깥 간격은 안의 ul 이 갖는다. */}
      <div role="status" aria-live="polite">
        {dropzone.rejected.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1">
            {dropzone.rejected.map(({ file, reason }, index) => (
              <li
                key={`${file.name}-${index}`}
                data-reason={reason}
                className="text-style-pre-caption-02 text-support-error"
              >
                {file.name} · {reasonText(reason)}
              </li>
            ))}
          </ul>
        )}
      </div>
      {dropzone.itemList.length > 0 && (
        <ul className={cn('flex flex-col gap-2', showDrop && 'mt-3')}>
          {dropzone.itemList.map((item) => (
            <li key={item.id} className="flex h-7 items-center gap-2">
              {!readOnly && (
                <IconButton
                  size="md"
                  className="text-text-tertiary"
                  aria-label={`${item.name} ${words.removeFile}`}
                  onClick={() => dropzone.onClickRemoveItem(item.id)}
                >
                  <CloseIcon />
                </IconButton>
              )}
              <span className="min-w-0 truncate text-style-pre-body-02 text-text-secondary">
                {item.name}
              </span>
              {itemMeta?.(item)}
              <span className="shrink-0 text-style-pre-caption-03 text-text-quaternary">
                {item.date}
              </span>
              {item.status === 'uploading' && (
                <span className="shrink-0 text-style-pre-caption-03 text-text-tertiary">
                  {words.uploading}
                </span>
              )}
              {item.status === 'failed' && (
                <span className="shrink-0 text-style-pre-caption-03 text-support-error">
                  {words.uploadFailed}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
FileDropzone.displayName = 'FileDropzone';

export { FileDropzone };
