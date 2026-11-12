// S17 온실가스 데이터 설정 — 고객사 인덱스 고르기(밴드 W12-0b2 ② — 스펙 ② S17, 시안 28593:27731, sid:MARC-ENT-469 3·4, sid:MARC-ISSUE-426).
//   - 머리: 브레드크럼 「온실가스 데이터 > 인덱스 설정」 · 제목 「온실가스 데이터 설정」(시안 — 감독 10-29) · 오른쪽 위 [취소][저장](저장은 늘 켬).
//   - 연도 드롭다운(올해부터 다섯 — Q5) · 「인덱스 검색」(웹에서 거름 — 맞는 항목과 조상) · 4열 판(열 1~3 은 길 고르기, 체크는 배출활동·자산/시설 열만,
//     항목 뒤 (availableCount), 부분 「−」) · 위 경로 줄(마지막 단 강조) · 「선택한 인덱스」 표(행 ✕, 「전체 해제」 — 확인 없이).
//   - 못 고르는 잎(기본 계수 없음 — S12-05 뒤 시설 0 은 고른다, sid:MARC-ENT-644)은 체크 흐림 + 까닭 글. 시설 0 이면 위 안내 한 줄 + [조직구조로]. J1: 처음 고른 잎은 그래도 해제·다시 고르기가 된다(model choosable).
//   - 저장: 뺀 잎 가운데 hasData 참이 n 이면 경고 창 → 확인해야 PUT(본문 = 잎만, 서버 차례). 성공 → onSaved(year).
//     422 fields.year → 「고를 수 없는 연도예요」 + onYear(올해) · fields.facilityNodeIds → 한 줄 + 트리 다시 읽음(고른 것은 서버 것으로, 없는 id 뺌 — 459 M4).
//   - 첫 읽기 실패만 화면 자리 한 줄 + 다시 시도. 다시 읽기 실패(422 뒤·연도 바꿈)는 한 줄 notice — 판은 그대로(sid:MARC-ISSUE-459 M1·M3).
//     판이 앞 해 것인 채로 [저장]을 누르면 PUT 대신 다시 읽는다(앞 해 고름을 새 해에 싣지 않는다).
//   - [취소]·연도 바꿈: 바꾼 것이 있으면 「변경 내용을 저장하지 않고 나갈까요?」. 확인 창은 <form onSubmit>·닫히면 연 단추로 초점(460).
//   - 화면은 라우터·세션을 모른다(콜백 onSaved·onCancel·onYear·onOrganization, prop year·years·operator).
//   - sid:MARC-ISSUE-468(밴드 W12-1a ①): 못 고르는 잎의 까닭은 이름 아래 둘째 줄(이름은 자르지 않음 — B1) · 연도는 공용 NativeSelect(D6) ·
//     「선택한 인덱스」 머리는 카드 머리 토큰(D7) · ✕ 열 빈 머리 칸(D8) · 경고 창 머리/몸(D9) · 검색 중 위 단 체크는 보이는 잎만(R4·M1 — 보이는
//     트리를 넘김) · 고를 잎·골라진 잎 0 인 활동 체크 흐림(R5·M4) · 저장 중 연도·[취소]·체크·「전체 해제」·✕ 막음(M2) · 다시 읽는 동안
//     판 aria-busy·체크 막음(M3 — 도착이 고친 것을 말없이 덮지 않게).
import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
  CloseIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  GhgSelectionPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  blockedReason,
  choosable,
  droppedWithData,
  filterTree,
  initialChosen,
  isLeaf,
  parentCheckable,
  parentState,
  pathTo,
  pruneChosen,
  sameChosen,
  selectionBody,
  toggleLeaf,
  toggleParent,
  treeColumns,
  treeLeaves,
  treePath,
  weave,
} from '../../../entities/ghg/model/index.ts';
import type {
  SelectionNode,
  SelectionTree,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  LoadSkeleton,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { ConfirmModal } from './ConfirmModal.tsx';

const words = GHG_TEXT.indexSettings;
const LEVELS = ['scope', 'source_type', 'activity', 'facility'] as const;

export interface IndexSettingsScreenProps {
  port: GhgSelectionPort;
  /** 주소의 연도(경로가 years 안으로 거른 값). */
  year: number;
  /** 고를 수 있는 연도(올해부터 내림 — model yearsOf. 처음 해는 전년도 — defaultYearOf). */
  years: readonly number[];
  /** 운영 관리자 세션이면 회사 거절 글이 companyOperator. */
  operator?: boolean;
  /** 저장 성공 → S2 자리(같은 연도). */
  onSaved(year: number): void;
  /** [취소](바꾼 것이 있으면 확인 뒤) → S2 자리. */
  onCancel(): void;
  /** 연도 바꿈(바꾼 것이 있으면 확인 뒤) — 경로가 주소를 바꾸면 year 가 바뀌어 다시 읽는다. */
  onYear(year: number): void;
  /** 시설 0 안내의 [조직구조로]. */
  onOrganization(): void;
}

type Loaded =
  | { state: 'loading' }
  | { state: 'failed' }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'ready'; tree: SelectionTree };

type Notice =
  | 'reloadFailed'
  | 'badYear'
  | 'badNodes'
  | 'saveFailed'
  | { company: CompanyRefusal }
  | null;

type Confirm =
  | { kind: 'leave'; then(): void; from: HTMLElement | null }
  | { kind: 'data'; count: number; from: HTMLElement | null }
  | { kind: 'save'; from: HTMLElement | null }
  | null;

const columnClass =
  'flex min-w-0 flex-col border-0 border-r border-solid border-border-tertiary last:border-r-0';
const itemClass =
  'flex min-h-11 w-full items-center gap-2 rounded-control px-3 py-2 text-left text-style-pre-body-06 text-text-primary';

export function IndexSettingsScreen({
  port,
  year,
  years,
  operator = false,
  onSaved,
  onCancel,
  onYear,
  onOrganization,
}: IndexSettingsScreenProps) {
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });
  const [initial, setInitial] = useState<ReadonlySet<string>>(new Set());
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [path, setPath] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState<Notice>(null);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [saving, setSaving] = useState(false);
  /** 판이 있는 채로 다시 읽는 중(연도 바꿈·422 뒤) — 판을 막는다(M3). */
  const [reloading, setReloading] = useState(false);
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    loaded.state === 'loading' ? 'loading'
    : loaded.state === 'failed' ? 'failed'
    : 'ready',
  );
  const hasTree = useRef(false);
  /** 마지막으로 부른 읽기의 번호 — 늦게 온 앞 읽기(앞 해) 답은 버린다(검증 B1). */
  const asked = useRef(0);

  /** 트리를 읽는다. 판이 없을 때(첫 읽기)만 실패가 화면 자리, 있으면 한 줄 notice — 판은 그대로. */
  const load = async () => {
    const ticket = ++asked.current;
    if (!hasTree.current) setLoaded({ state: 'loading' });
    else setReloading(true);
    const out = await port.tree(year);
    if (ticket !== asked.current) return;
    setReloading(false);
    if (out.kind === 'ok') {
      const tree = weave(out.value.nodes);
      const first = initialChosen(out.value.nodes);
      hasTree.current = true;
      setLoaded({ state: 'ready', tree: out.value });
      setInitial(first);
      setChosen(pruneChosen(tree, first));
      setPath((old) => treePath(tree, old));
      // 다시 읽기 실패 글만 걷는다(422·연도 글은 다시 읽은 뒤에도 남는다).
      setNotice((old) => (old === 'reloadFailed' ? null : old));
      return;
    }
    if (!hasTree.current)
      setLoaded(
        out.kind === 'refused' ?
          { state: 'refused', company: out.company }
        : { state: 'failed' },
      );
    else
      setNotice(
        out.kind === 'refused' ? { company: out.company } : 'reloadFailed',
      );
  };
  useEffect(() => {
    void load();
    // load 는 port·year 로만 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, year]);

  const tree = loaded.state === 'ready' ? loaded.tree : null;
  const woven = useMemo(() => weave(tree?.nodes ?? []), [tree]);
  const shown = useMemo(
    () => weave(filterTree(tree?.nodes ?? [], query)),
    [tree, query],
  );
  const shownPath = treePath(shown, path);
  const columns = treeColumns(shown, shownPath);
  const dirty = !sameChosen(chosen, initial);
  /** 저장 중(M2)·다시 읽는 중(M3)이면 고름을 바꾸지 못한다. */
  const locked = saving || reloading;
  const noFacilities =
    woven.leaves.length > 0 &&
    woven.leaves.every((leaf) => leaf.availableCount === 0);
  // GX2 S12-05: 고른 표는 나무 차례(범위 → 배출활동 구분 — 판 S12-05), 서버 평평한 차례 아님.
  const chosenRows = treeLeaves(woven).filter((leaf) => chosen.has(leaf.id));

  /** 바꾼 것이 있으면 확인 뒤, 없으면 바로. */
  const guard = (then: () => void, from: HTMLElement | null) => {
    if (dirty) setConfirm({ kind: 'leave', then, from });
    else then();
  };

  const send = async () => {
    if (!tree) return;
    if (tree.year !== year) {
      // 앞 해 판이 남아 있다(다시 읽기 실패) — 새 해에 싣지 않고 다시 읽는다.
      await load();
      return;
    }
    setSaving(true);
    const out = await port.save(year, selectionBody(woven, chosen));
    setSaving(false);
    if (out.kind === 'ok') return onSaved(year);
    if (out.kind === 'refused') return setNotice({ company: out.company });
    if (out.kind === 'rejected' && out.code === 'VALIDATION_ERROR') {
      if ('year' in out.fields) {
        setNotice('badYear');
        return onYear(years[0] ?? year);
      }
      if ('facilityNodeIds' in out.fields) {
        setNotice('badNodes');
        return void load();
      }
    }
    setNotice('saveFailed');
  };

  const save = (event: MouseEvent<HTMLButtonElement>) => {
    const dropped = droppedWithData(woven, initial, chosen);
    if (dropped.length > 0)
      setConfirm({
        kind: 'data',
        count: dropped.length,
        from: event.currentTarget,
      });
    // S12C1 da787b28: 그 밖에도 바로 보내지 않고 확인 창 하나(데이터 경고가 뜨면 그 창 하나만 — 둘 연달아 0).
    else setConfirm({ kind: 'save', from: event.currentTarget });
  };

  const head = (
    <>
      <nav
        aria-label={words.breadcrumbLabel}
        className="flex items-center gap-1 text-style-pre-caption-03 text-text-tertiary"
      >
        <span>{words.breadcrumb[0]}</span>
        <ChevronRightIcon aria-hidden className="size-3" />
        <span aria-current="page" className="text-text-primary">
          {words.breadcrumb[1]}
        </span>
      </nav>
      <PageTitle
        title={words.title}
        headingRef={retryFocus.doneRef}
        actions={
          loaded.state === 'ready' && (
            <>
              <Button
                variant="solidGrey"
                shape="round"
                size="md"
                disabled={saving}
                onClick={(event) => guard(onCancel, event.currentTarget)}
              >
                {words.cancel}
              </Button>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                loading={saving}
                onClick={save}
              >
                {words.save}
              </Button>
            </>
          )
        }
      />
    </>
  );

  if (loaded.state === 'refused')
    return (
      <div data-screen="ghg-index-settings" className="flex flex-col gap-6">
        {head}
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="company-refusal"
        >
          {companyText[loaded.company]}
        </PageInfo>
      </div>
    );

  if (loaded.state !== 'ready')
    return (
      <div data-screen="ghg-index-settings" className="flex flex-col gap-6">
        {head}
        {loaded.state === 'loading' ?
          <LoadSkeleton label={GHG_TEXT.common.loading} />
        : <div
            role="alert"
            data-testid="load-failure"
            className="flex flex-col items-start gap-4"
          >
            <PageInfo
              tone="error"
              icon={<CircleWarningIcon aria-hidden />}
              className="w-full"
            >
              {words.loadFailed}
            </PageInfo>
            <Button
              ref={retryFocus.actionRef}
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={retryFocus.arm(() => void load())}
            >
              {GHG_TEXT.common.retry}
            </Button>
          </div>
        }
      </div>
    );

  const checkFor = (node: SelectionNode) => {
    if (isLeaf(node)) {
      const reason = blockedReason(node, initial);
      return (
        <>
          <Checkbox
            aria-label={words.check(node.name)}
            aria-describedby={reason ? `ghg-why-${node.id}` : undefined}
            checked={chosen.has(node.id)}
            disabled={
              locked || (!chosen.has(node.id) && !choosable(node, initial))
            }
            onCheckedChange={() =>
              setChosen((old) => toggleLeaf(node, old, initial))
            }
          />
          {reason && (
            <span id={`ghg-why-${node.id}`} className="sr-only">
              {words[reason]}
            </span>
          )}
        </>
      );
    }
    if (node.level !== 'activity') return null;
    // 보이는 트리(shown) 기준 — 검색에 맞는 잎만 셈하고 바꾼다(R4·M1).
    const state = parentState(shown, node.id, chosen);
    return (
      <Checkbox
        aria-label={words.check(node.name)}
        disabled={locked || !parentCheckable(shown, node.id, chosen)}
        checked={
          state === 'all' ? true
          : state === 'some' ?
            'indeterminate'
          : false
        }
        onCheckedChange={() =>
          setChosen((old) => toggleParent(shown, node.id, old))
        }
      />
    );
  };

  const itemOf = (node: SelectionNode, index: number) => {
    const picked = shownPath[index] === node.id;
    const reason = isLeaf(node) ? blockedReason(node, initial) : null;
    const label = (
      <span className="flex min-w-0 items-baseline gap-1">
        <span
          data-testid={`ghg-name-${node.id}`}
          className="min-w-0 break-words"
        >
          {node.name}
        </span>
        <span className="shrink-0 text-text-quaternary">
          {words.count(node.availableCount)}
        </span>
      </span>
    );
    return (
      <li
        key={node.id}
        data-testid={`ghg-node-${node.id}`}
        className={cn(
          'flex items-center gap-2 rounded-control',
          picked && 'bg-background-secondary',
        )}
      >
        {isLeaf(node) ?
          <label
            className={cn(
              itemClass,
              'cursor-pointer',
              reason && 'cursor-default opacity-60',
            )}
          >
            {checkFor(node)}
            <span className="flex min-w-0 flex-col">
              {label}
              {reason && (
                <span
                  aria-hidden
                  data-testid={`ghg-why-line-${node.id}`}
                  className="text-style-pre-caption-03 text-text-tertiary"
                >
                  {words[reason]}
                </span>
              )}
            </span>
          </label>
        : <div className={cn(itemClass, 'gap-2 px-0 pl-3')}>
            {checkFor(node)}
            <button
              type="button"
              aria-pressed={picked}
              className="flex min-w-0 flex-1 cursor-pointer items-center gap-1 border-0 bg-transparent p-0 text-left"
              onClick={() => setPath([...shownPath.slice(0, index), node.id])}
            >
              {label}
            </button>
          </div>
        }
      </li>
    );
  };

  const noticeText =
    notice === null ? null
    : typeof notice === 'object' ? companyText[notice.company]
    : words[notice];
  const trail = shownPath.map((id) => woven.byId.get(id)?.name ?? '');

  return (
    <div data-screen="ghg-index-settings" className="flex flex-col gap-6">
      {head}
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect
          aria-label={words.yearLabel}
          value={year}
          disabled={saving}
          onChange={(event) => {
            const next = years.find((y) => `${y}` === event.target.value);
            if (next !== undefined) guard(() => onYear(next), event.target);
          }}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {words.yearOption(y)}
            </option>
          ))}
        </NativeSelect>
        <SearchField
          aria-label={words.searchLabel}
          placeholder={words.searchPlaceholder}
          value={query}
          maxLength={100}
          onChange={(event) => setQuery(event.target.value)}
          className="w-60"
        />
        <p
          role="alert"
          data-testid="index-settings-notice"
          className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
        >
          {noticeText && (
            <>
              <CircleWarningIcon aria-hidden />
              {noticeText}
            </>
          )}
        </p>
      </div>
      {noFacilities && (
        <PageInfo data-testid="no-facilities">
          {/* GX2 S12-05: PageInfo 가 글을 div 하나로 감싸 겉 gap 이 안 닿는다 — 안쪽 줄에 글↔단추 8. */}
          <span
            data-testid="no-facilities-line"
            className="flex flex-wrap items-center gap-2"
          >
            {words.noFacilities}
            <Button
              variant="outlineBlack"
              shape="round"
              size="sm"
              onClick={onOrganization}
            >
              {words.toOrganization}
            </Button>
          </span>
        </PageInfo>
      )}
      <Card
        aria-busy={reloading || undefined}
        data-testid="index-board"
        className="flex flex-col gap-0 p-0"
      >
        {woven.roots.length === 0 ?
          <p data-testid="empty-pool" className="m-0 p-6 text-text-tertiary">
            {words.emptyPool}
          </p>
        : <>
            <p
              aria-label={words.pathLabel}
              data-testid="index-path"
              className="m-0 flex items-center gap-2 border-0 border-b border-solid border-border-tertiary px-6 py-4 text-style-pre-body-04"
            >
              {trail.map((name, index) => (
                <span key={index} className="flex items-center gap-2">
                  {index > 0 && <ChevronRightIcon aria-hidden />}
                  <span
                    className={cn(
                      index === trail.length - 1 && 'text-text-brand',
                    )}
                  >
                    {name}
                  </span>
                </span>
              ))}
            </p>
            {shown.roots.length === 0 ?
              <p className="m-0 p-6 text-text-tertiary">{words.emptySearch}</p>
            : <div className="grid grid-cols-4">
                {LEVELS.map((level, index) => (
                  <section
                    key={level}
                    aria-label={words.columns[level]}
                    className={columnClass}
                  >
                    <h3 className="m-0 border-0 border-b border-solid border-border-tertiary py-3 text-center text-style-pre-body-04">
                      {words.columns[level]}
                    </h3>
                    {columns[index]!.length === 0 ?
                      <p className="m-0 p-3 text-text-tertiary">
                        {words.emptyColumn}
                      </p>
                    : <ul className="m-0 flex list-none flex-col gap-1 p-3">
                        {columns[index]!.map((node) => itemOf(node, index))}
                      </ul>
                    }
                  </section>
                ))}
              </div>
            }
          </>
        }
      </Card>
      <Card className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.chosenTitle}
          </h3>
          <Button
            variant="text"
            size="sm"
            disabled={locked || chosen.size === 0}
            onClick={() => setChosen(new Set())}
          >
            {words.clearAll}
            <CloseIcon aria-hidden />
          </Button>
        </div>
        <table
          aria-label={words.chosenTitle}
          className="w-full border-collapse text-style-pre-body-06"
        >
          <thead>
            <tr>
              {LEVELS.map((level) => (
                <th
                  key={level}
                  scope="col"
                  className="border-0 border-y border-solid border-border-tertiary px-4 py-3 text-left text-text-tertiary"
                >
                  {words.chosenColumns[level]}
                </th>
              ))}
              <th
                scope="col"
                data-testid="chosen-remove-head"
                className="border-0 border-y border-solid border-border-tertiary px-4 py-3"
              >
                <span className="sr-only">{words.removeColumn}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {chosenRows.length === 0 ?
              <tr>
                <td colSpan={5} className="px-4 py-6 text-text-tertiary">
                  {words.noneChosen}
                </td>
              </tr>
            : chosenRows.map((leaf) => {
                const line = pathTo(woven, leaf.id);
                return (
                  <tr key={leaf.id} data-testid={`chosen-${leaf.id}`}>
                    {LEVELS.map((level) => (
                      <td
                        key={level}
                        className="border-0 border-b border-solid border-border-tertiary px-4 py-3"
                      >
                        {line.find((node) => node.level === level)?.name ?? ''}
                      </td>
                    ))}
                    <td className="border-0 border-b border-solid border-border-tertiary px-4 py-3 text-right">
                      <Button
                        variant="text"
                        size="sm"
                        aria-label={words.removeChosen(leaf.name)}
                        disabled={locked}
                        onClick={() =>
                          setChosen((old) => {
                            const next = new Set(old);
                            next.delete(leaf.id);
                            return next;
                          })
                        }
                      >
                        <CloseIcon aria-hidden />
                      </Button>
                    </td>
                  </tr>
                );
              })
            }
          </tbody>
        </table>
      </Card>
      {confirm?.kind === 'leave' && (
        <ConfirmModal
          title={words.leaveConfirm}
          cancel={words.stay}
          confirm={words.leave}
          returnFocus={confirm.from}
          testId="leave-confirm"
          onClose={() => setConfirm(null)}
          onConfirm={() => {
            setConfirm(null);
            confirm.then();
          }}
        />
      )}
      {confirm?.kind === 'save' && (
        <ConfirmModal
          title={words.saveConfirm}
          cancel={words.cancel}
          confirm={words.confirm}
          returnFocus={confirm.from}
          testId="save-confirm"
          onClose={() => setConfirm(null)}
          onConfirm={() => {
            setConfirm(null);
            void send();
          }}
        />
      )}
      {confirm?.kind === 'data' && (
        <ConfirmModal
          title={words.dataWarning(confirm.count)}
          body={words.dataWarningBody}
          cancel={words.cancel}
          confirm={words.confirm}
          returnFocus={confirm.from}
          testId="data-warning"
          onClose={() => setConfirm(null)}
          onConfirm={() => {
            setConfirm(null);
            void send();
          }}
        />
      )}
    </div>
  );
}
