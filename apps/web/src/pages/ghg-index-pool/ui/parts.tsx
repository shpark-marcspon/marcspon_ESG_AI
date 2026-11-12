// S19·S20 화면 안에서 같이 쓰는 작은 부품(밴드 W12-0b1 ③). pages 끼리 가져오지 않으므로(L 규칙) pages/ghg-branch 의 ConfirmDialog 꼴을
// 이 폴더에 옮겨 적었다(공통화는 sid:MARC-ISSUE-335 꼴 후속). 글자 모달(열 1~3 추가·수정)도 여기.
import { useState } from 'react';
import type { ReactNode } from 'react';

import { Input } from '@marcspon/ui/components/input';

import type { PoolWrite } from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';

const words = GHG_TEXT.pool;
/** 서버 NAME_MAX(inventory/service/utils/ghg_pool.py). */
export const NODE_NAME_MAX = 100;

export interface ConfirmDialogProps {
  title: string;
  cancel: string;
  confirm: string;
  returnFocus: HTMLElement | null;
  testId: string;
  busy?: boolean;
  onConfirm(): void;
  onClose(): void;
}

/** 확인 창 하나(가운데 제목 + [취소]·[확인]). 닫히면 연 단추로 초점. */
export function ConfirmDialog({
  title,
  cancel,
  confirm,
  returnFocus,
  testId,
  busy = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid={testId}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus?.isConnected) returnFocus.focus();
        }}
      >
        <DialogTitle className="text-center text-style-pre-heading-02">
          {title}
        </DialogTitle>
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            disabled={busy}
            onClick={onClose}
          >
            {cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            loading={busy}
            onClick={onConfirm}
          >
            {confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export interface NameDialogProps {
  title: string;
  initial: string;
  returnFocus: HTMLElement | null;
  send(name: string): Promise<PoolWrite<unknown>>;
  /** 이름 칸 밖의 결과(성공·없음·실패) — 화면이 한 줄로 받는다. */
  onDone(outcome: PoolWrite<unknown>): void;
  onClose(): void;
}

/** 열 1~3 의 글자 모달(「이름*」, 100자). [저장]은 늘 켬 · 누를 때 빈 칸 검사 · 422 fields.name → 그 칸에 겹침 글. */
export function NameDialog({
  title,
  initial,
  returnFocus,
  send,
  onDone,
  onClose,
}: NameDialogProps) {
  const [name, setName] = useState(initial);
  const [problem, setProblem] = useState<'required' | 'taken' | null>(null);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (saving) return;
    if (name.trim() === '') {
      setProblem('required');
      document.getElementById('ghg-pool-name')?.focus();
      return;
    }
    setSaving(true);
    const outcome = await send(name);
    setSaving(false);
    if (
      outcome.kind === 'rejected' &&
      outcome.code === 'VALIDATION_ERROR' &&
      'name' in outcome.fields
    ) {
      setProblem('taken');
      return;
    }
    onDone(outcome);
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="name-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus?.isConnected) returnFocus.focus();
        }}
      >
        <DialogTitle className="text-style-pre-heading-02">{title}</DialogTitle>
        <div className="flex flex-col gap-2">
          <label
            htmlFor="ghg-pool-name"
            className="flex items-center text-style-pre-body-05 text-text-secondary"
          >
            {words.nameField}
            <RequiredMark />
          </label>
          <Input
            id="ghg-pool-name"
            value={name}
            maxLength={NODE_NAME_MAX}
            placeholder={words.namePlaceholder}
            aria-invalid={problem !== null || undefined}
            aria-describedby={problem ? 'ghg-pool-name-error' : undefined}
            onChange={(event) => {
              setName(event.target.value);
              setProblem(null);
            }}
          />
          <FieldError id="ghg-pool-name-error">
            {problem === 'required' ?
              words.required
            : problem === 'taken' ?
              words.nameTaken
            : null}
          </FieldError>
        </div>
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            disabled={saving}
            onClick={onClose}
          >
            {words.cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            loading={saving}
            onClick={() => void save()}
          >
            {words.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 칸 아래 오류 한 줄(비면 그리지 않는다). */
export function FieldError({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  if (children === null || children === undefined || children === false)
    return null;
  return (
    <p
      id={id}
      data-testid={id}
      className="m-0 text-style-pre-caption-03 text-support-error-accent"
    >
      {children}
    </p>
  );
}

/** 흔한 고르기 상자 — 공통 NativeSelect(sid:MARC-ENT-430, 36·모서리 8·tertiary·▾ — sid:MARC-ISSUE-573). 폼 칸이라 w-full. */
export function Choice({
  id,
  label,
  value,
  placeholder,
  options,
  disabled,
  invalid,
  describedBy,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  options: readonly { value: string; label: string }[];
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
  onChange(value: string): void;
}) {
  return (
    <NativeSelect
      id={id}
      aria-label={label}
      value={value}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      onChange={(event) => onChange(event.target.value)}
      className="w-full min-w-0"
    >
      <option value="">{placeholder}</option>
      {options.map((one) => (
        <option key={one.value} value={one.value}>
          {one.label}
        </option>
      ))}
    </NativeSelect>
  );
}
