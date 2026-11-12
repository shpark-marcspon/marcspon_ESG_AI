// 결과 표 편집 줄의 조각(판 IR-04·04a r3 — 밴드 IRW11): 편집 맥락(ResultView 가 쥔 한 값 — Q5)·글 상자·주소 칸·칸 아래 오류·줄 아래 단추 줄.
// 글 상자는 키트 Textarea(px-3 py-2 · resize-none · 손잡이 없음)를 칸 폭 가득, 글 길이만큼(field-sizing:content — 판 .d-ta).
// 오류는 칸 바로 아래 빨간 작은 글(판 e-helper--error 꼴) + 상자 빨간 테두리. 409 글은 그 줄 첫 고칠 칸 아래 + [새로 불러오기](위 6).
import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import type {
  EditError,
  EditField,
  MaterialityResult,
  ResultEdit,
} from '../../../entities/materiality/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';

const words = IR_TEXT.result.edit;

export type EditTab = 'shortlist' | 'impact' | 'pathway';

/** 편집 줄 하나(한 번에 하나 — Q5). fields 는 그 줄의 고칠 칸 전부(차례대로, 같은 바른 주소가 둘일 수 있다). */
export interface Editing {
  tab: EditTab;
  /** 그 탭 안 줄 번호(no). */
  no: number;
  fields: EditField[];
  /** 바른 주소 → 쓰는 글(같은 바른 주소의 상자는 한 글을 나눠 쓴다 — 보낼 때 하나, critic 덧). */
  draft: Record<string, string>;
  errors: Record<string, EditError>;
  conflict: boolean;
  failed: boolean;
  saving: boolean;
}

/** 표 칸이 쓰는 편집 맥락. */
export interface EditApi {
  /** 지금 보이는 결과(저장·다시 읽기 뒤 새 판). */
  result: MaterialityResult;
  /** 고침을 못 읽음 — 고치기 열·연필·배지 0(Q7). */
  readOnly: boolean;
  edits: readonly ResultEdit[];
  editing: Editing | null;
  dirty: boolean;
  open(tab: EditTab, no: number): void;
  setDraft(pointer: string, text: string): void;
  cancel(): void;
  save(): void;
  reload(): void;
  /** 화면 안 이동(탭·토픽·유형 탭 — Q9): 바꾼 글이 있으면 묻고, 없으면 편집 줄을 닫고 간다. */
  guard(action: () => void): void;
}

export const EditContext = createContext<EditApi | null>(null);

export function useEdit(): EditApi {
  const api = useContext(EditContext);
  if (api === null) throw new Error('EditContext missing');
  return api;
}

/** 이 탭의 이 줄이 편집 중인가. */
export const isEditing = (api: EditApi, tab: EditTab, no: number) =>
  api.editing !== null && api.editing.tab === tab && api.editing.no === no;

const ERROR_ID = (pointer: string) =>
  `edit-error-${pointer.replace(/[^a-zA-Z0-9]/g, '-')}`;

function Helper({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <p
      id={id}
      role="alert"
      data-testid="edit-error"
      className="m-0 mt-1 flex items-start gap-1 text-style-pre-caption-03 text-support-error-accent"
    >
      <CircleWarningIcon aria-hidden className="mt-px size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** 409 글(그 줄 첫 고칠 칸 아래) + [새로 불러오기]. */
function Conflict() {
  const api = useEdit();
  return (
    <>
      <Helper>{words.conflict}</Helper>
      <Button
        variant="outlineBlack"
        shape="round"
        size="sm"
        className="mt-1.5"
        data-testid="edit-reload"
        onClick={api.reload}
      >
        {words.reload}
      </Button>
    </>
  );
}

/** 글 상자 하나. first 면 열 때 초점·409 글 자리. */
export function EditBox({
  field,
  label,
  first = false,
  className,
}: {
  field: EditField;
  label: string;
  first?: boolean;
  className?: string;
}) {
  const api = useEdit();
  const editing = api.editing!;
  const error = editing.errors[field.pointer];
  const id = ERROR_ID(field.pointer);
  return (
    <div className={cn('flex min-w-0 flex-col', className)}>
      <Textarea
        aria-label={label}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? id : undefined}
        data-edit-field=""
        data-edit-first={first ? '' : undefined}
        rows={1}
        value={editing.draft[field.pointer] ?? ''}
        onChange={(event) => api.setDraft(field.pointer, event.target.value)}
        className={cn(
          'block min-h-0 w-full resize-none px-3 py-2 [field-sizing:content]',
          error && 'border-support-error-accent',
        )}
      />
      {error && <Helper id={id}>{words.errors[error]}</Helper>}
      {first && editing.conflict && <Conflict />}
    </div>
  );
}

/** 1-1 항목 하나(판 .d-item2): 작은 글 「{n}) {라벨}」 · 제목 글 상자 · 주소 한 줄. */
export function ItemBoxes({
  head,
  title,
  url,
  first,
}: {
  head: string;
  title: EditField;
  url: EditField;
  first: boolean;
}) {
  const api = useEdit();
  const editing = api.editing!;
  const error = editing.errors[url.pointer];
  const id = ERROR_ID(url.pointer);
  return (
    <div className="flex flex-col gap-1.5" data-edit-item="">
      <span className="text-style-pre-caption-03 text-text-tertiary">
        {head}
      </span>
      <EditBox field={title} label={words.title} first={first} />
      <div className="flex flex-col">
        <Input
          aria-label={words.url}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? id : undefined}
          data-edit-field=""
          placeholder={words.urlPlaceholder}
          value={editing.draft[url.pointer] ?? ''}
          onChange={(event) => api.setDraft(url.pointer, event.target.value)}
          className={cn('w-full', error && 'border-support-error-accent')}
        />
        {error && <Helper id={id}>{words.errors[error]}</Helper>}
      </div>
    </div>
  );
}

/** 편집 줄 아래 단추 줄(판 .d-rowact): 왼쪽 회색 안내(실패면 빨간 글) · 오른쪽 [취소][저장]. sticky 면 2-2(가로 스크롤)에서 양 끝에 붙음. */
export function EditActions({
  note,
  sticky = false,
}: {
  note: string;
  sticky?: boolean;
}) {
  const api = useEdit();
  const editing = api.editing!;
  return (
    <div
      data-testid="edit-actions"
      className="flex items-center justify-between gap-3"
    >
      <div className={cn(sticky && 'sticky left-4')}>
        {editing.failed ?
          <Helper>{words.saveFailed}</Helper>
        : <span
            data-testid="edit-note"
            className="text-style-pre-caption-03 text-text-tertiary"
          >
            {note}
          </span>
        }
      </div>
      <div className={cn('flex shrink-0 gap-1.5', sticky && 'sticky right-4')}>
        <Button
          variant="outlineBlack"
          shape="round"
          size="sm"
          onClick={api.cancel}
        >
          {words.cancel}
        </Button>
        <Button
          variant="solidBlack"
          shape="round"
          size="sm"
          disabled={!api.dirty}
          loading={editing.saving}
          onClick={api.save}
        >
          {words.save}
        </Button>
      </div>
    </div>
  );
}
