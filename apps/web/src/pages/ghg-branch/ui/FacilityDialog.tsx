// S15 「자산/시설 추가」 모달(밴드 W12-0a ② — 스펙 S15 5-1·5-2). 저장은 상세 화면의 줄 목록에만 넣는다(onAdd — 서버 요청 0).
//   - 시설명 및 코드* 드롭다운: GET /facility-codes 를 웹에서 가나다로(GX2 L-8), 글은 이름(code 글자 0). 목록이 비면 드롭다운 자리에 안내 글.
//   - 세부시설명* 글 칸. [저장]은 늘 켬 · 누를 때 검사(빔 → 「필수 입력 항목이에요」 + 그 칸 초점, 판의 줄과 겹침 → 한 줄).
//   - 닫히면 연 단추로 초점(AD-01 모달 꼴).
import { useMemo, useRef, useState } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';

import type { GhgOrganizationPort } from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { useFacilityCodes } from '../../../entities/ghg/hooks/index.ts';
import {
  codesInKoreanOrder,
  validateFacilityLine,
} from '../../../entities/ghg/model/index.ts';
import type {
  FacilityLine,
  FacilityLineProblem,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';

const words = GHG_TEXT.facilityModal;

export interface FacilityDialogProps {
  port: GhgOrganizationPort;
  /** 판에 지금 있는 줄(겹침 검사). */
  lines: readonly FacilityLine[];
  returnFocus: HTMLElement;
  onAdd(line: Omit<FacilityLine, 'key' | 'id'>): void;
  onClose(): void;
}

const CODE_ID = 'ghg-facility-code';
const errorClass = 'm-0 text-style-pre-caption-03 text-support-error-accent';

export function FacilityDialog({
  port,
  lines,
  returnFocus,
  onAdd,
  onClose,
}: FacilityDialogProps) {
  const codes = useFacilityCodes(port);
  const [codeId, setCodeId] = useState('');
  const [detail, setDetail] = useState('');
  const [problem, setProblem] = useState<FacilityLineProblem | null>(null);
  const detailRef = useRef<HTMLInputElement>(null);
  // GX2 L-8: 서버 차례가 가나다가 아니라(DB 정렬 규칙) 웹에서 가나다로.
  const list = useMemo(
    () =>
      codes.status.state === 'ready' ?
        codesInKoreanOrder(codes.status.value)
      : [],
    [codes.status],
  );

  const save = () => {
    const found = validateFacilityLine(lines, codeId, detail);
    setProblem(found);
    // NativeSelect 는 ref 를 넘기지 않는다(React 18 함수 부품) — id 로 찾는다.
    if (found === 'codeRequired')
      return document.getElementById(CODE_ID)?.focus();
    if (found === 'detailRequired') return detailRef.current?.focus();
    if (found !== null) return;
    const code = list.find((one) => one.id === codeId);
    if (!code) return;
    onAdd({
      facilityCodeId: code.id,
      facilityName: code.name,
      detailName: detail.trim(),
    });
  };

  const codeField = () => {
    const status = codes.status;
    if (status.state === 'loading')
      return (
        <p
          role="status"
          className="m-0 text-style-pre-body-06 text-text-tertiary"
        >
          {GHG_TEXT.common.loading}
        </p>
      );
    if (status.state === 'refused')
      return (
        <p role="alert" className={errorClass}>
          {GHG_TEXT.company[status.company]}
        </p>
      );
    if (status.state === 'failed')
      return (
        <div className="flex items-center gap-2">
          <p role="alert" className={errorClass}>
            {words.codesFailed}
          </p>
          <Button variant="outlineGrey" size="sm" onClick={codes.retry}>
            {GHG_TEXT.common.retry}
          </Button>
        </div>
      );
    if (list.length === 0)
      return (
        <p
          data-testid="no-codes"
          className="m-0 text-style-pre-body-06 text-text-tertiary"
        >
          {words.noCodes}
        </p>
      );
    return (
      <NativeSelect
        id={CODE_ID}
        value={codeId}
        aria-invalid={problem === 'codeRequired' || undefined}
        onChange={(event) => {
          setCodeId(event.target.value);
          setProblem(null);
        }}
        className="w-full"
      >
        <option value="">{words.codePlaceholder}</option>
        {list.map((code) => (
          <option key={code.id} value={code.id}>
            {code.name}
          </option>
        ))}
      </NativeSelect>
    );
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="facility-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus.focus();
        }}
      >
        <DialogTitle className="text-style-pre-heading-02">
          {words.title}
        </DialogTitle>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label
              htmlFor={CODE_ID}
              className="flex items-center text-style-pre-body-05 text-text-secondary"
            >
              {words.code}
              <RequiredMark />
            </label>
            {codeField()}
            {problem === 'codeRequired' && (
              <p className={errorClass}>{GHG_TEXT.branch.required}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <label
              htmlFor="ghg-facility-detail"
              className="flex items-center text-style-pre-body-05 text-text-secondary"
            >
              {words.detail}
              <RequiredMark />
            </label>
            <Input
              ref={detailRef}
              id="ghg-facility-detail"
              value={detail}
              maxLength={200}
              placeholder={words.detailPlaceholder}
              aria-invalid={problem === 'detailRequired' || undefined}
              onChange={(event) => {
                setDetail(event.target.value);
                setProblem(null);
              }}
            />
            {problem === 'detailRequired' && (
              <p className={errorClass}>{GHG_TEXT.branch.required}</p>
            )}
          </div>
          {problem === 'duplicateFacility' && (
            <p
              role="alert"
              data-testid="facility-duplicate"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
            >
              <CircleWarningIcon aria-hidden />
              {GHG_TEXT.branch.duplicateFacility}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            onClick={onClose}
          >
            {words.cancel}
          </Button>
          <Button variant="solidBlack" shape="round" size="md" onClick={save}>
            {words.save}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
