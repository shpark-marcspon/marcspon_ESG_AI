// S15 사업장 상세(새 사업장 추가 겸용 — 밴드 W12-0a ②, 스펙 ② S15). 라우터·세션을 모른다: 실어댑터(port)와 이동 콜백을 props 로 받는다.
//   - 칸: 사업장명* · 인벤토리 사용 상태 토글(본사면 켜진 채 꺼짐) · 「자산/시설 정보」 표(체크박스·시설명 및 코드·세부시설명) ·
//     「삭제」(고른 줄을 화면 목록에서 뺌) · 「추가」(모달 — 화면 목록에만 넣음) · [취소]·[저장].
//   - 페이지 [저장]이 한 번에 보낸다: 새로면 POST 201 → onSaved(새 id, true)(경로가 상세 주소로 replace), 있으면 PUT 200 → 받은 값으로
//     다시 그림 + 「저장했어요」. 본문은 model branchSaveBody(빠진 줄 = 삭제 표시, 있던 줄 id 정수).
//   - 저장 단추 Policy(스펙 「공통」): 늘 켬 · 누를 때 검사 · 첫 오류 칸 초점 · 「필수 입력 항목이에요」. 겹침은 표 위 한 줄.
//     서버 422 fields.name → 이름 칸, fields.facilities(겹침)·facilityCodeId(지운 코드) → 표 위 한 줄(모듈 글 — 서버 message 0, 폼 그대로).
//   - [취소]: 바꾼 것이 있으면 확인 창 「저장하지 않고 나갈까요?」, 없으면 바로 onBack.
//   - 없는 id·지운 사업장(404) → 「사업장을 찾지 못했어요」 + [목록으로]. 회사 거절 → 글 한 줄(다시 시도 없음).
//   - 밴드 W12-0b1 ①(sid:MARC-ISSUE-426): PUT 404 는 낡은 자산/시설 줄 id 에도 오므로 다시 읽어 가른다(M1 — 있으면 폼 그대로 + 한 줄,
//     없으면 「사업장을 찾지 못했어요」) · 저장 요청이 걸린 동안 폼 전체를 fieldset disabled 로 잠근다(L1) · 회사 글은 운영 관리자면
//     companyOperator(operator prop).
//   - 밴드 K1b-3(sid:MARC-ISSUE-427): 판 버전(상세 updatedAt 글자)은 화면 상태 version 으로 들고 PUT 본문에 그대로 싣는다(branchPutBody —
//     GET·PUT 200 때 받은 글자로 바꿈, 날짜로 바꾸지 않음). 409 STALE·404 다시 읽기의 「있음」 → 폼 그대로 + 한 줄 stale + 줄 안
//     [다시 불러오기](고친 것이 있으면 확인 창) → 다시 읽어 판·버전을 새로.
import { useEffect, useRef, useState } from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Input } from '@marcspon/ui/components/input';
import { Switch } from '@marcspon/ui/components/switch';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  GhgOrganizationPort,
  WriteOutcome,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { useBranch } from '../../../entities/ghg/hooks/index.ts';
import {
  branchPutBody,
  branchSaveBody,
  draftOf,
  emptyDraft,
  sameDraft,
  validateBranch,
} from '../../../entities/ghg/model/index.ts';
import type {
  BranchDetail,
  BranchDraft,
  FacilityLine,
} from '../../../entities/ghg/model/index.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { ConfirmDialog } from './ConfirmDialog.tsx';
import { FacilityDialog } from './FacilityDialog.tsx';

const words = GHG_TEXT.branch;

export interface BranchScreenProps {
  port: GhgOrganizationPort;
  /** 있는 사업장의 id. null 이면 새 사업장(추가). */
  branchId: string | null;
  /** [취소]·[목록으로]. */
  onBack(): void;
  /** 새 사업장을 만든 뒤(201) — 그 id 의 상세로. */
  onCreated(id: string): void;
  /** 운영 관리자 세션인가(회사 거절 글을 가른다 — app/ghg 의 useOperator). */
  operator?: boolean;
}

/** 표 위·단추 줄의 한 줄. */
type Line =
  | 'duplicateFacility'
  | 'codeGone'
  | 'stale'
  | 'headquartersLocked'
  | 'inUse'
  | 'saveFailed'
  | { company: CompanyRefusal }
  | null;
/** 이름 칸의 오류. */
type NameError = 'required' | 'taken' | null;

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
/** GX2 S12-04a: 줄 56(판 `.f12b-td` 최소 56) · 체크 20(판 `.f12b-ck`, size lg). */
const cellClass =
  'h-14 border-0 border-b border-solid border-border-tertiary px-4 text-left';

export function BranchScreen({
  port,
  branchId,
  onBack,
  onCreated,
  operator = false,
}: BranchScreenProps) {
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;
  const read = useBranch(port, branchId);
  const status = read.status;
  if (branchId !== null && status.state !== 'ready') {
    if (status.state === 'loading')
      return (
        <div data-screen="ghg-branch">
          <LoadSkeleton label={GHG_TEXT.common.loading} />
        </div>
      );
    if (status.state === 'missing')
      return (
        <div data-screen="ghg-branch">
          <LoadFailure
            kind="missing"
            message={words.notFound}
            onList={onBack}
            listLabel={words.toList}
          />
        </div>
      );
    if (status.state === 'refused')
      return (
        <div data-screen="ghg-branch">
          <PageInfo
            role="alert"
            tone="error"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="company-refusal"
          >
            {companyText[status.company]}
          </PageInfo>
        </div>
      );
    return (
      <div data-screen="ghg-branch">
        <LoadFailure
          kind="failed"
          message={words.loadFailed}
          onRetry={read.retry}
          onList={onBack}
          listLabel={words.toList}
        />
      </div>
    );
  }
  return (
    <BranchForm
      key={branchId ?? 'new'}
      port={port}
      branchId={branchId}
      detail={status.state === 'ready' ? status.value : null}
      onBack={onBack}
      onCreated={onCreated}
      companyText={companyText}
    />
  );
}

function BranchForm({
  port,
  branchId,
  detail,
  onBack,
  onCreated,
  companyText,
}: {
  port: GhgOrganizationPort;
  branchId: string | null;
  detail: BranchDetail | null;
  onBack(): void;
  onCreated(id: string): void;
  companyText: Record<CompanyRefusal, string>;
}) {
  const [base, setBase] = useState<BranchDraft>(() =>
    detail ? draftOf(detail) : emptyDraft(),
  );
  const [draft, setDraft] = useState<BranchDraft>(base);
  /** 판 버전(서버 updatedAt 글자 그대로). 새 사업장이면 null. */
  const [version, setVersion] = useState<string | null>(
    detail?.updatedAt ?? null,
  );
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [nameError, setNameError] = useState<NameError>(null);
  const [line, setLine] = useState<Line>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [missing, setMissing] = useState(false);
  const [modal, setModal] = useState<HTMLElement | null>(null);
  const [leaving, setLeaving] = useState<HTMLElement | null>(null);
  const [asking, setAsking] = useState<HTMLElement | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const added = useRef(0);
  // 이름 오류가 나면 그 칸으로 초점(첫 오류 칸 — 저장 단추 Policy).
  const [focusName, setFocusName] = useState(0);
  useEffect(() => {
    if (focusName > 0) nameRef.current?.focus();
  }, [focusName]);

  if (missing)
    return (
      <div data-screen="ghg-branch">
        <LoadFailure
          kind="missing"
          message={words.notFound}
          onList={onBack}
          listLabel={words.toList}
        />
      </div>
    );

  const change = (next: Partial<BranchDraft>) => {
    setDraft((before) => ({ ...before, ...next }));
    setSaved(false);
  };
  const lines = draft.facilities;
  const allPicked =
    lines.length > 0 && lines.every((one) => picked.has(one.key));
  const togglePick = (key: string, on: boolean) =>
    setPicked((before) => {
      const next = new Set(before);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  const removePicked = () => {
    change({ facilities: lines.filter((one) => !picked.has(one.key)) });
    setPicked(new Set());
    setLine(null);
  };
  const addLine = (one: Omit<FacilityLine, 'key' | 'id'>) => {
    added.current += 1;
    change({
      facilities: [...lines, { ...one, key: `new-${added.current}`, id: null }],
    });
    setLine(null);
  };

  /** PUT 404: 사업장이 지워졌는지, 보낸 자산/시설 줄이 낡았는지 다시 읽어 가른다(M1). */
  const recheck = async (id: string) => {
    const again = await port.getBranch(id);
    if (again.kind === 'missing') return setMissing(true);
    if (again.kind === 'ok') return setLine('stale');
    if (again.kind === 'refused') return setLine({ company: again.company });
    return setLine('saveFailed');
  };

  const fail = async (
    outcome: Exclude<WriteOutcome<unknown>, { kind: 'ok' }>,
  ) => {
    if (outcome.kind === 'refused')
      return setLine({ company: outcome.company });
    if (outcome.kind !== 'rejected') return setLine('saveFailed');
    switch (outcome.code) {
      case 'VALIDATION_ERROR':
        if ('name' in outcome.fields) {
          setNameError(draft.name.trim() === '' ? 'required' : 'taken');
          setFocusName((n) => n + 1);
          return;
        }
        // 겹침은 fields.facilities, 지운 코드를 고름은 fields.facilityCodeId(서버 organization/service/apis/branches.py).
        if ('facilities' in outcome.fields) return setLine('duplicateFacility');
        if ('facilityCodeId' in outcome.fields) return setLine('codeGone');
        return setLine('saveFailed');
      case 'HEADQUARTERS_LOCKED':
        return setLine('headquartersLocked');
      case 'IN_USE':
        return setLine('inUse');
      case 'STALE':
        // 그사이 다른 곳이 저장했다 — 아무것도 쓰이지 않았다. 폼 그대로 + [다시 불러오기].
        return setLine('stale');
      case 'NOT_FOUND':
        // PUT 의 404 는 사업장이 지워졌거나 보낸 줄 id 가 낡았다 — 다시 읽어 가른다(POST 의 404 는 화면이 보내지 않는 줄 id — 저장 실패로).
        if (branchId !== null) return recheck(branchId);
        return setLine('saveFailed');
      default:
        return setLine('saveFailed');
    }
  };

  /** [다시 불러오기]: 지금 판을 읽어 폼·버전을 새로(고친 것은 버린다). */
  const reload = async () => {
    if (branchId === null || reloading) return;
    setReloading(true);
    const again = await port.getBranch(branchId);
    setReloading(false);
    if (again.kind === 'missing') return setMissing(true);
    if (again.kind === 'refused') return setLine({ company: again.company });
    if (again.kind !== 'ok') return setLine('saveFailed');
    const next = draftOf(again.value);
    setBase(next);
    setDraft(next);
    setVersion(again.value.updatedAt);
    setPicked(new Set());
    setNameError(null);
    setSaved(false);
    setLine(null);
  };

  const save = async () => {
    if (saving) return;
    setSaved(false);
    setLine(null);
    setNameError(null);
    const problem = validateBranch(draft);
    if (problem === 'nameRequired') {
      setNameError('required');
      setFocusName((n) => n + 1);
      return;
    }
    if (problem === 'duplicateFacility') return setLine('duplicateFacility');
    let body;
    try {
      body = branchSaveBody(draft);
    } catch {
      return setLine('saveFailed');
    }
    if (branchId !== null && version === null) return setLine('saveFailed');
    setSaving(true);
    const outcome =
      branchId === null ?
        await port.createBranch(body)
      : await port.saveBranch(branchId, branchPutBody(draft, version!));
    if (outcome.kind !== 'ok') {
      await fail(outcome);
      return setSaving(false);
    }
    setSaving(false);
    if (branchId === null) return onCreated(outcome.value.id);
    const next = draftOf(outcome.value);
    setBase(next);
    setDraft(next);
    setVersion(outcome.value.updatedAt);
    setPicked(new Set());
    setSaved(true);
  };

  const lineText =
    line === null ? null
    : typeof line === 'object' ? companyText[line.company]
    : words[line];

  return (
    <div data-screen="ghg-branch" className="flex flex-col gap-6">
      <PageTitle title={branchId === null ? words.titleNew : words.titleEdit} />
      <Card>
        <fieldset
          disabled={saving || reloading}
          data-testid="branch-form"
          className="m-0 flex min-w-0 flex-col gap-6 border-0 p-0"
        >
          <div className={FORM_ROWS_CLASS}>
            <div className={FORM_ROW_CLASS}>
              <label htmlFor="ghg-branch-name" className={FORM_LABEL_CLASS}>
                {words.name}
                <RequiredMark />
              </label>
              <div className={cn(FORM_VALUE_CLASS, 'flex flex-col gap-1')}>
                <Input
                  id="ghg-branch-name"
                  ref={nameRef}
                  value={draft.name}
                  placeholder={words.namePlaceholder}
                  maxLength={200}
                  aria-invalid={nameError !== null || undefined}
                  aria-describedby={
                    nameError ? 'ghg-branch-name-error' : undefined
                  }
                  onChange={(event) => {
                    change({ name: event.target.value });
                    setNameError(null);
                  }}
                  className="max-w-[400px]"
                />
                {nameError && (
                  <p
                    id="ghg-branch-name-error"
                    data-testid="name-error"
                    className="m-0 text-style-pre-caption-03 text-support-error-accent"
                  >
                    {nameError === 'required' ?
                      words.required
                    : words.nameTaken}
                  </p>
                )}
              </div>
            </div>
            <div className={FORM_ROW_CLASS}>
              <span id="ghg-branch-inventory" className={FORM_LABEL_CLASS}>
                {words.inventory}
              </span>
              <div className={cn(FORM_VALUE_CLASS, 'items-center')}>
                {/* GX2 L-11: 스위치 이름을 aria-label 로 직접(「인벤토리 사용 상태」) — 라벨 span 과 같은 글. */}
                <Switch
                  aria-label={words.inventory}
                  checked={draft.isHeadquarters || draft.inventoryEnabled}
                  disabled={draft.isHeadquarters}
                  onCheckedChange={(checked) =>
                    change({ inventoryEnabled: checked })
                  }
                />
              </div>
            </div>
          </div>
          <section className="flex flex-col gap-3" aria-labelledby="ghg-lines">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3
                id="ghg-lines"
                className="m-0 text-style-pre-heading-02 text-text-primary"
              >
                {words.facilities}
              </h3>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  aria-disabled={picked.size === 0 || undefined}
                  className={cn(
                    buttonVariants({ variant: 'outlineGrey', size: 'sm' }),
                    picked.size === 0 && 'cursor-not-allowed opacity-40',
                  )}
                  onClick={() => {
                    if (picked.size > 0) removePicked();
                  }}
                >
                  {words.removeLines}
                </button>
                <Button
                  variant="outlineGrey"
                  size="sm"
                  onClick={(event) => setModal(event.currentTarget)}
                >
                  <PlusIcon aria-hidden />
                  {words.addLine}
                </Button>
              </div>
            </div>
            {/* 줄과 [다시 불러오기]를 한 줄에(밴드 K1b-3). 줄이 비면 둘레도 숨긴다 — 단추는 줄이 stale 일 때만 있다. */}
            <div className="flex flex-wrap items-center gap-2 has-[>p:empty]:hidden">
              <p
                role="alert"
                data-testid="branch-line"
                className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
              >
                {lineText && (
                  <>
                    <CircleWarningIcon aria-hidden />
                    {lineText}
                  </>
                )}
              </p>
              {line === 'stale' && branchId !== null && (
                <Button
                  variant="outlineGrey"
                  size="sm"
                  data-testid="branch-reload"
                  onClick={(event) => {
                    if (sameDraft(draft, base)) void reload();
                    else setAsking(event.currentTarget);
                  }}
                >
                  {words.reload}
                </Button>
              )}
            </div>
            <div className="w-full overflow-x-auto">
              <table
                aria-labelledby="ghg-lines"
                className="w-full table-fixed border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary"
              >
                <colgroup>
                  <col style={{ width: 48 }} />
                  <col />
                  <col />
                </colgroup>
                <thead>
                  <tr>
                    <th scope="col" className={headClass}>
                      <Checkbox
                        size="lg"
                        className="align-middle"
                        aria-label={words.selectAll}
                        checked={
                          allPicked ? true
                          : picked.size > 0 ?
                            'indeterminate'
                          : false
                        }
                        disabled={lines.length === 0}
                        onCheckedChange={(checked) =>
                          setPicked(
                            checked === true ?
                              new Set(lines.map((one) => one.key))
                            : new Set(),
                          )
                        }
                      />
                    </th>
                    <th scope="col" className={headClass}>
                      {words.columns.code}
                    </th>
                    <th scope="col" className={headClass}>
                      {words.columns.detail}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {lines.length === 0 ?
                    <tr>
                      <td
                        colSpan={3}
                        className={cn(
                          cellClass,
                          'text-center text-text-tertiary',
                        )}
                      >
                        {words.noFacilities}
                      </td>
                    </tr>
                  : lines.map((one) => (
                      <tr key={one.key} data-line-key={one.key}>
                        <td className={cellClass}>
                          <Checkbox
                            size="lg"
                            className="align-middle"
                            aria-label={words.selectLine(
                              `${one.facilityName} ${one.detailName}`,
                            )}
                            checked={picked.has(one.key)}
                            onCheckedChange={(checked) =>
                              togglePick(one.key, checked === true)
                            }
                          />
                        </td>
                        <td className={cn(cellClass, 'break-all')}>
                          {one.facilityName}
                        </td>
                        <td className={cn(cellClass, 'break-all')}>
                          {one.detailName}
                        </td>
                      </tr>
                    ))
                  }
                </tbody>
              </table>
            </div>
          </section>
          <div className="flex items-center justify-end gap-2">
            <span
              role="status"
              data-testid="branch-saved"
              className="text-style-pre-caption-03 text-text-tertiary empty:hidden"
            >
              {saved ? words.saved : null}
            </span>
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              disabled={saving}
              onClick={(event) => {
                if (sameDraft(draft, base)) onBack();
                else setLeaving(event.currentTarget);
              }}
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
          </div>
        </fieldset>
      </Card>
      {modal && (
        <FacilityDialog
          port={port}
          lines={lines}
          returnFocus={modal}
          onAdd={(one) => {
            addLine(one);
            setModal(null);
          }}
          onClose={() => setModal(null)}
        />
      )}
      {leaving && (
        <ConfirmDialog
          title={words.leaveConfirm}
          cancel={words.stay}
          confirm={words.leave}
          returnFocus={leaving}
          testId="leave-dialog"
          onConfirm={onBack}
          onClose={() => setLeaving(null)}
        />
      )}
      {asking && (
        <ConfirmDialog
          title={words.reloadConfirm}
          cancel={words.stay}
          confirm={words.reloadConfirmOk}
          returnFocus={asking}
          testId="reload-dialog"
          onConfirm={() => {
            setAsking(null);
            void reload();
          }}
          onClose={() => setAsking(null)}
        />
      )}
    </div>
  );
}
