// 파일 드롭존의 헤드리스 훅. 판정(domain)을 부르고, 목록·끌어다 놓기·파일 창 열기·키보드를 다룬다. 모양(클래스·색)을 모른다.
// 이름은 키트 use-file-dropzone 을 따른다: itemList · selectFileCallback · onClickRemoveItem · onError · maxMb · maxCount · readOnly.
// 키트와 다른 자리: 형식은 키트의 acceptFileObject(lib/accept-file-type) 대신 우리 꼴 accept(확장자·MIME 목록)로 받는다.
// 목록은 쓰는 쪽이 갖는다(itemList + onChangeItemList). 실제 업로드(네트워크)는 하지 않는다: 올리는 중·실패는 항목의 status 로만 보인다.
import { useCallback, useRef, useState } from 'react';
import type {
  ChangeEvent,
  DragEvent,
  KeyboardEvent,
  MutableRefObject,
} from 'react';

import { acceptAttribute, judgeFiles, toDateText } from '../model/index.ts';
import type { Rejected } from '../model/index.ts';

/** 목록의 항목. 키트 DraggableInputItem 꼴에 status 를 더했다. */
export interface DraggableInputItem {
  id: string;
  name: string;
  url?: string;
  size?: number;
  /** YYYY-MM-DD 글자. 그대로 보인다. */
  date: string;
  file?: File;
  fileUrl?: string;
  status?: 'uploading' | 'failed';
}

export interface UseFileDropzoneOptions {
  itemList: readonly DraggableInputItem[];
  onChangeItemList(next: DraggableInputItem[]): void;
  /** 받을 형식: 확장자(".xlsx")·MIME("application/pdf")·와일드카드("image/*"). 없으면 모두. */
  accept?: readonly string[];
  /** 파일 하나의 크기 상한(MB). */
  maxMb?: number;
  /** 목록 전체의 개수 상한. */
  maxCount?: number;
  /** 참이면 새 파일을 받지도 지우지도 않는다. */
  readOnly?: boolean;
  /** 참이면 파일 창을 열지 않고 끌어다 놓기도 받지 않는다(올리는 중). */
  disabled?: boolean;
  /** 거부된 파일이 있을 때 한 번 부른다(이번에 고른 것 가운데 거부된 것 전부). */
  onError?(rejected: Rejected<File>[]): void;
  /** 새 항목의 날짜. 기본은 오늘(YYYY-MM-DD). */
  today?(): string;
}

export interface ZoneProps {
  role: 'button';
  tabIndex: 0 | -1;
  'aria-disabled'?: true;
  onClick(): void;
  onKeyDown(event: KeyboardEvent<HTMLElement>): void;
  onDragEnter(event: DragEvent<HTMLElement>): void;
  onDragOver(event: DragEvent<HTMLElement>): void;
  onDragLeave(event: DragEvent<HTMLElement>): void;
  onDrop(event: DragEvent<HTMLElement>): void;
}

export interface InputProps {
  ref: MutableRefObject<HTMLInputElement | null>;
  type: 'file';
  hidden: true;
  tabIndex: -1;
  multiple: boolean;
  accept?: string;
  onChange(event: ChangeEvent<HTMLInputElement>): void;
}

export interface FileDropzoneState {
  itemList: readonly DraggableInputItem[];
  /** 고른 파일들을 판정해 받은 것을 목록 끝에 더한다. 거부된 것은 rejected 와 onError 로 알린다. */
  selectFileCallback(files: FileList | readonly File[] | null): void;
  onClickRemoveItem(id: string): void;
  /** 마지막으로 고른 묶음에서 거부된 것. 새로 고르면 바뀐다. */
  rejected: Rejected<File>[];
  /** 지금 파일을 끌어 칸 위에 두고 있는가. */
  isDragging: boolean;
  /** 숨긴 파일 입력을 눌러 파일 창을 연다. */
  openFileDialog(): void;
  /** 칸(파일 창을 여는 자리)에 펼칠 속성. button 역할, Enter·Space 로 연다. */
  zoneProps: ZoneProps;
  /** 숨긴 <input type=file> 에 펼칠 속성. */
  inputProps: InputProps;
}

let sequence = 0;
const nextId = () => `file-${Date.now().toString(36)}-${(sequence += 1)}`;

export function useFileDropzone({
  itemList,
  onChangeItemList,
  accept,
  maxMb,
  maxCount,
  readOnly = false,
  disabled = false,
  onError,
  today = () => toDateText(new Date()),
}: UseFileDropzoneOptions): FileDropzoneState {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [rejected, setRejected] = useState<Rejected<File>[]>([]);
  const [isDragging, setDragging] = useState(false);
  const closed = readOnly || disabled;

  const selectFileCallback = useCallback(
    (files: FileList | readonly File[] | null) => {
      if (closed || !files) return;
      const picked = Array.from(files);
      if (picked.length === 0) return;
      const judgement = judgeFiles(picked, itemList, {
        accept,
        maxMb,
        maxCount,
      });
      setRejected(judgement.rejected);
      if (judgement.rejected.length > 0) onError?.(judgement.rejected);
      if (judgement.accepted.length > 0) {
        const date = today();
        onChangeItemList([
          ...itemList,
          ...judgement.accepted.map((file): DraggableInputItem => ({
            id: nextId(),
            name: file.name,
            size: file.size,
            date,
            file,
          })),
        ]);
      }
    },
    [
      closed,
      itemList,
      accept,
      maxMb,
      maxCount,
      onError,
      onChangeItemList,
      today,
    ],
  );

  const onClickRemoveItem = useCallback(
    (id: string) => {
      if (readOnly) return;
      onChangeItemList(itemList.filter((item) => item.id !== id));
    },
    [readOnly, itemList, onChangeItemList],
  );

  const openFileDialog = useCallback(() => {
    if (closed) return;
    inputRef.current?.click();
  }, [closed]);

  const zoneProps: ZoneProps = {
    role: 'button',
    tabIndex: closed ? -1 : 0,
    'aria-disabled': closed ? true : undefined,
    onClick: openFileDialog,
    onKeyDown: (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault(); // Space 가 쪽을 내리지 않게
      openFileDialog();
    },
    onDragEnter: (event) => {
      event.preventDefault();
      if (!closed) setDragging(true);
    },
    onDragOver: (event) => {
      event.preventDefault(); // 이것이 없으면 브라우저가 drop 을 주지 않는다
    },
    onDragLeave: (event) => {
      // 칸 안의 자식으로 옮겨 갈 때는 떠난 것이 아니다
      if (
        event.relatedTarget instanceof Node &&
        event.currentTarget.contains(event.relatedTarget)
      )
        return;
      setDragging(false);
    },
    onDrop: (event) => {
      event.preventDefault();
      setDragging(false);
      selectFileCallback(event.dataTransfer?.files ?? null);
    },
  };

  const inputProps: InputProps = {
    ref: inputRef,
    type: 'file',
    hidden: true,
    tabIndex: -1,
    multiple: maxCount === undefined || maxCount > 1,
    accept: acceptAttribute(accept),
    onChange: (event) => {
      selectFileCallback(event.target.files);
      // 같은 파일을 다시 골라도 change 가 나게 비운다
      event.target.value = '';
    },
  };

  return {
    itemList,
    selectFileCallback,
    onClickRemoveItem,
    rejected,
    isDragging,
    openFileDialog,
    zoneProps,
    inputProps,
  };
}
