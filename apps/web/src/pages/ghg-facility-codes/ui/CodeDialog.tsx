// S18 항목 추가·수정 모달(밴드 W12-0a ③ — 스펙 S18 4·4-1, 수정은 같은 꼴 [추정]). 글 칸 하나.
//   [저장]은 빈 칸이면 흐림(스펙 [확인]). 누르면 웹 검사(지금 쪽의 다른 항목과 같은 이름 → 「이미 있는 항목이에요」) 뒤 보낸다.
//   서버 422 fields.name 도 같은 자리. 그 밖의 결과(성공·사용 중·없음·실패)는 화면(onDone)이 한 줄로 받는다. 닫히면 연 단추로 초점.
import { useState } from 'react';

import { Input } from '@marcspon/ui/components/input';

import type {
  FacilityCodeAdminPort,
  WriteOutcome,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { validateCodeName } from '../../../entities/ghg/model/index.ts';
import type { FacilityCode } from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';

const words = GHG_TEXT.facilityCodes;
const FIELD_ID = 'ghg-code-name';
/** 서버 CodeName 의 max_length(apps/api-py/esgapi/organization/service/schemas/branches.py — 넘으면 422 fields.name 이 겹침 글로 보인다). */
export const CODE_NAME_MAX = 100;

export interface CodeDialogProps {
  port: FacilityCodeAdminPort;
  /** 겹침 검사에 쓰는 지금 쪽의 항목. */
  existing: readonly FacilityCode[];
  /** 수정이면 그 항목, 추가면 null. */
  editing: FacilityCode | null;
  returnFocus: HTMLElement;
  onDone(outcome: WriteOutcome<unknown>): void;
  onClose(): void;
}

export function CodeDialog({
  port,
  existing,
  editing,
  returnFocus,
  onDone,
  onClose,
}: CodeDialogProps) {
  const [name, setName] = useState(editing?.name ?? '');
  const [duplicate, setDuplicate] = useState(false);
  const [saving, setSaving] = useState(false);
  const empty = name.trim() === '';

  const save = async () => {
    if (empty || saving) return;
    if (validateCodeName(name, existing, editing?.id ?? null) === 'duplicate')
      return setDuplicate(true);
    setSaving(true);
    const outcome =
      editing ? await port.rename(editing.id, name) : await port.create(name);
    setSaving(false);
    if (
      outcome.kind === 'rejected' &&
      outcome.code === 'VALIDATION_ERROR' &&
      'name' in outcome.fields
    )
      return setDuplicate(true);
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
        data-testid="code-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus.isConnected) returnFocus.focus();
        }}
      >
        <DialogTitle className="text-style-pre-heading-02">
          {editing ? words.editTitle : words.addTitle}
        </DialogTitle>
        <div className="flex flex-col gap-2">
          <label
            htmlFor={FIELD_ID}
            className="flex items-center text-style-pre-body-05 text-text-secondary"
          >
            {words.field}
            <RequiredMark />
          </label>
          <Input
            id={FIELD_ID}
            value={name}
            maxLength={CODE_NAME_MAX}
            placeholder={words.placeholder}
            aria-invalid={duplicate || undefined}
            aria-describedby={duplicate ? `${FIELD_ID}-error` : undefined}
            onChange={(event) => {
              setName(event.target.value);
              setDuplicate(false);
            }}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing || event.key !== 'Enter')
                return;
              event.preventDefault();
              void save();
            }}
          />
          {duplicate && (
            <p
              id={`${FIELD_ID}-error`}
              role="alert"
              data-testid="code-duplicate"
              className="m-0 text-style-pre-caption-03 text-support-error-accent"
            >
              {words.duplicate}
            </p>
          )}
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
            disabled={empty}
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
