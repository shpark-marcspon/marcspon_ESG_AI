// RP-03 목차 설정(밴드 RPW1 ②, 시안 v188 RP-03_r1 — 발주서 §2-2). 라우터를 모른다.
// 왼쪽 트리(OutlineTree — 더하기 셋·줄 아이콘·끌기·단축키) + 오른쪽 고른 줄의 이름·요구 내용(NodeEditor — 순서·단계는 트리에서만, RPW12). 지우기는 하위 함께 — 확인 창. 셈은 model/tree.ts·drop.ts(순수).
//   더한 뒤에는 새 줄을 고르고 이름 칸에 초점 + 글 전체 선택. 초점은 그린 뒤에 옮긴다(focusAsk) — 새 줄·새 이름 칸이 그때 생긴다.
// 저장 = PUT …/outline {nodes}(key 는 고쳐도 그대로). 422 fields 가 `nodes.<i>.title|requirement` 면 그 줄, 아니면 목차 위 한 줄. 실패는 [다시 시도].
// [초안 만들기](§2-0 ⑧): 고친 것이 있으면 먼저 저장 → 앞 실행이 있으면 「초안 화면으로」(그 실행), 없으면 POST /runs {projectId}(base 0) → 그 실행.
//   누름이 겹쳐도 요청은 하나(ref 로 막음 — 저장소도 같은 판·본문엔 같은 열쇠). 거절은 한 줄(서버 글·설정 화면 이름 0), 연결 실패는 다른 한 줄(RPW2 M5).
// 머리: [목록으로] 오른쪽 위 · 저장 시각은 저장 응답을 받은 브라우저 시각(서버 칸 없음 — 처음 값 없음). 오른쪽 칸은 라벨 왼쪽 표 꼴(form-rows).
// 나갈 때 물음: 고친 것이 있는지 onDirtyChange 로 틀에 알리고, 틀이 막은 이동을 leave 로 받아 창으로 묻는다(app/admin AiSettingsRoute 꼴).
import {
  useEffect,
  useId,
  useLayoutEffect,
  useReducer,
  useRef,
  useState,
} from 'react';

import {
  CircleWarningIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  DraftingStore,
} from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { useProject, useRead } from '../../../entities/drafting/hooks/index.ts';
import { minuteOf } from '../../../entities/drafting/model/index.ts';
import type {
  OutlineNode,
  Project,
} from '../../../entities/drafting/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import {
  LoadSkeleton,
  useDelayed,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';
import {
  MAX_LEAVES,
  MAX_NODES,
  addChild,
  addSibling,
  addTop,
  ancestorsOf,
  bodyOf,
  changedKeys,
  countsOf,
  descendantsOf,
  edit,
  fieldsOf,
  isDirty,
  isLeaf,
  moveTo,
  placePaste,
  problemsOf,
  randomKey,
  removeAt,
  subtreeEnd,
} from '../model/index.ts';
import type {
  Drop,
  FieldProblem,
  KeyMaker,
  Move,
  PasteHow,
  PasteRow,
} from '../model/index.ts';
import { NodeEditor } from './NodeEditor.tsx';
import { OutlineTree } from './OutlineTree.tsx';
import { PasteDialog } from './PasteDialog.tsx';
import { fitRow } from './fitRow.ts';

const words = DR_TEXT.outline;

export interface OutlineLeave {
  /** 틀이 이동을 막고 묻는 중. */
  pending: boolean;
  proceed(): void;
  reset(): void;
}

export interface OutlineScreenProps {
  store: DraftingStore;
  /** 주소의 프로젝트 id(정수가 아니면 null — 요청 없이 찾지 못함). */
  projectId: number | null;
  operator: boolean;
  onList(): void;
  /** 그 실행의 RP-04 로. */
  onRun(runId: number): void;
  onDirtyChange?(dirty: boolean): void;
  leave?: OutlineLeave;
  /** 새 마디 key 짓기(기본 무작위 — 시험은 고정 차례). */
  nodeKey?: KeyMaker;
}

/** 목차 아래 한 줄. */
type Notice =
  | {
      kind:
        | 'saveFailed'
        | 'saveRejected'
        | 'startRefused'
        | 'startFailed'
        | 'saved';
    }
  | { kind: 'company'; company: CompanyRefusal };

export function OutlineScreen(props: OutlineScreenProps) {
  const loaded = useProject(props.store, props.projectId);
  const status =
    props.projectId === null ? { state: 'not_found' as const } : loaded.status;
  const companyText =
    props.operator ? DR_TEXT.companyOperator : DR_TEXT.company;
  // 첫 불러오기: 제목 + STEP 띠 뒤 300ms 뒤 LoadSkeleton(sid:MARC-ENT-443 ①, 밴드 RPW5 #4).
  const skeleton = useDelayed(status.state === 'loading');

  if (status.state !== 'ready')
    return (
      <div data-screen="drafting-outline" className="flex flex-col gap-6">
        <PageTitle
          title={words.title}
          descriptionPending={status.state === 'loading'}
        />
        <StepFlow
          current={2}
          steps={DR_TEXT.steps.items}
          label={DR_TEXT.steps.label}
        />
        {status.state === 'refused' ?
          <PageInfo
            role="alert"
            tone="error"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="company-refusal"
          >
            {companyText[status.company]}
          </PageInfo>
        : status.state === 'not_found' ?
          <LoadFailure
            kind="missing"
            message={words.projectMissing}
            listLabel={DR_TEXT.common.toList}
            onList={props.onList}
          />
        : status.state === 'failed' ?
          <LoadFailure
            kind="failed"
            message={words.projectLoadFailed}
            retryLabel={DR_TEXT.common.retry}
            onRetry={loaded.retry}
          />
        : skeleton && <LoadSkeleton />}
      </div>
    );
  return <Editor {...props} project={status.value} />;
}

function Editor({
  store,
  operator,
  project,
  onList,
  onRun,
  onDirtyChange,
  leave,
  nodeKey = randomKey,
}: OutlineScreenProps & { project: Project }) {
  const noticeId = useId();
  const [saved, setSaved] = useState<OutlineNode[]>(
    () => project.outline?.outline.nodes ?? [],
  );
  const [nodes, setNodes] = useState<OutlineNode[]>(saved);
  const [selected, setSelected] = useState<number | null>(
    nodes.length > 0 ? 0 : null,
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [serverRows, setServerRows] = useState<Map<string, FieldProblem[]>>(
    () => new Map(),
  );
  const [showProblems, setShowProblems] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);
  /** 붙여넣기 창(RPW9). */
  const [pasteOpen, setPasteOpen] = useState(false);
  const [stored, setStored] = useState(project.outline !== null);
  const hasRun = project.latestRun !== null;
  const documentId = project.pdf?.documentId ?? null;
  const pdfInfo = useRead(
    documentId === null ? null : [store, documentId],
    () => store.getDocument(documentId!),
  );
  const [savedAfterRun, setSavedAfterRun] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  /** 저장한 목차 판 id(실행 열쇠를 가른다 — 고쳐 저장하면 새 키). */
  const outlineRef = useRef(project.outline?.outlineId ?? null);
  const pressed = useRef(false);

  const dirty = isDirty(saved, nodes);
  const changed = changedKeys(saved, nodes);
  const counts = countsOf(nodes);
  const local = problemsOf(nodes);
  const rowProblems = (key: string): FieldProblem[] => [
    ...new Set([
      ...(showProblems ? (local.rows.get(key) ?? []) : []),
      ...(serverRows.get(key) ?? []),
    ]),
  ];
  const companyText = operator ? DR_TEXT.companyOperator : DR_TEXT.company;

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);

  const change = (next: OutlineNode[], at: number | null) => {
    setNodes(next);
    setSelected(next.length === 0 ? null : at);
    setNotice(null);
  };

  const listRef = useRef<HTMLUListElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  /** 그린 뒤 옮길 초점 — 새 줄·새 이름 칸은 그린 뒤에 생기고, 줄이 옮겨지면 브라우저가 초점을 잃는다. */
  const focusAsk = useRef<'row' | 'rowQuiet' | 'name' | 'nameSelected' | null>(
    null,
  );
  const [, redraw] = useReducer((count: number) => count + 1, 0);
  const askFocus = (target: NonNullable<typeof focusAsk.current>) => {
    focusAsk.current = target;
    redraw();
  };
  /** 고른 줄로 초점. quiet — 포인터에서 온 초점(끌기 끝·손잡이 클릭)이라 초점 테두리를 그리지 않는다(RPW8 N1). 키보드·창 닫힘은 테두리를 보인다. */
  const focusRow = (quiet = false) => {
    const box = listRef.current;
    const row = box?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!box || !row) return;
    // preventScroll: 브라우저가 창을 멋대로 굴리지 않게 — 보이기는 fitRow 가 넘친 만큼만.
    // focusVisible 은 TS 5.6 lib.dom 에 아직 없어 넓힌 꼴로 넘긴다.
    const options: FocusOptions & { focusVisible?: boolean } =
      quiet ?
        { preventScroll: true, focusVisible: false }
      : { preventScroll: true };
    // Chromium 은 focusVisible:false 로 잡힌 줄이 초점 그대로 다시 focus() 를 받으면 테두리를 계속 숨긴다 —
    // 키보드 길(Tab 단계 내림처럼 줄이 그대로)에서 테두리가 돌아오게 한 번 놓았다 다시 잡는다(RPW8 검증 B1).
    if (
      !quiet &&
      document.activeElement === row &&
      !row.matches(':focus-visible')
    )
      row.blur();
    row.focus(options);
    fitRow(box, row);
  };
  useLayoutEffect(() => {
    const target = focusAsk.current;
    if (target === null) return;
    focusAsk.current = null;
    if (target === 'row' || target === 'rowQuiet')
      return void focusRow(target === 'rowQuiet');
    nameRef.current?.focus();
    if (target === 'nameSelected') nameRef.current?.select();
  });

  /** 줄을 더하고 이름 칸으로(글 전체 선택). */
  const added = ([next, index]: [OutlineNode[], number]) => {
    change(next, index);
    askFocus('nameSelected');
  };
  const onAddTop = () => {
    const current =
      selected !== null && selected < nodes.length ? selected : null;
    if (current === null) return added(addTop(nodes, words.newTitle, nodeKey));
    let top = current;
    while (nodes[top]!.depth > 1) top -= 1;
    added(addTop(nodes, words.newTitle, nodeKey, subtreeEnd(nodes, top)));
  };
  /** 순서·단계 바꿈(줄 Tab·줄 아이콘). 못 옮기면 고침·안내를 건드리지 않는다. 초점은 줄에 남는다. */
  const onRowMove = (move: Move, index: number) => {
    const [next, moved] = move(nodes, index);
    if (moved !== index || next.some((one, i) => one !== nodes[i]))
      change(next, moved);
    askFocus('row');
  };
  const onDrop = (index: number, drop: Drop) =>
    change(...moveTo(nodes, index, drop));
  /** 붙여넣기 — 읽은 줄을 넣고 넣은 첫 줄을 고른다. 초점은 창이 닫힌 뒤(onPasted). 저장은 기존 [저장]. */
  const onPaste = (rows: PasteRow[], how: PasteHow) => {
    setPasteOpen(false);
    change(...placePaste(nodes, rows, how, nodeKey, saved));
  };
  const onPasted = () => focusRow();

  /** 저장(고친 것이 없으면 건너뜀). 저장했거나 할 것이 없으면 참. */
  const save = async (): Promise<boolean> => {
    if (!dirty && stored) return true;
    setShowProblems(true);
    if (local.rows.size > 0) return false;
    if (local.tooMany) {
      setNotice({ kind: 'saveRejected' });
      return false;
    }
    const sent = bodyOf(nodes);
    const outcome = await store.saveOutline(project.id, sent);
    if (outcome.kind === 'ok') {
      outlineRef.current = outcome.value.outlineId;
      setSavedAt(minuteOf(new Date().toISOString()));
      setSaved(nodes);
      setStored(true);
      setServerRows(new Map());
      setShowProblems(false);
      setNotice({ kind: 'saved' });
      if (hasRun) setSavedAfterRun(true);
      return true;
    }
    if (outcome.kind === 'refused')
      setNotice({ kind: 'company', company: outcome.company });
    else if (outcome.kind === 'rejected') {
      const { rows, whole } = fieldsOf(sent, outcome.fields);
      setServerRows(rows);
      setNotice(whole || rows.size === 0 ? { kind: 'saveRejected' } : null);
    } else setNotice({ kind: 'saveFailed' });
    return false;
  };

  const onSave = async () => {
    if (pressed.current) return;
    pressed.current = true;
    setBusy(true);
    try {
      await save();
    } finally {
      pressed.current = false;
      setBusy(false);
    }
  };

  const onStart = async () => {
    if (pressed.current) return;
    pressed.current = true;
    setBusy(true);
    try {
      if (!(await save())) return;
      if (project.latestRun !== null) {
        onDirtyChange?.(false);
        onRun(project.latestRun.id);
        return;
      }
      const started = await store.startRun(
        { projectId: project.id },
        outlineRef.current,
      );
      if (started.kind === 'ok') {
        onDirtyChange?.(false);
        onRun(started.value.runId);
        return;
      }
      setNotice(
        started.kind === 'refused' ?
          { kind: 'company', company: started.company }
        : started.kind === 'failed' ? { kind: 'startFailed' }
        : { kind: 'startRefused' },
      );
    } finally {
      pressed.current = false;
      setBusy(false);
    }
  };

  const at = selected !== null && selected < nodes.length ? selected : null;
  const node = at === null ? null : nodes[at]!;
  const problems = node ? rowProblems(node.key) : [];
  const noticeText =
    notice === null ? null
    : notice.kind === 'company' ? companyText[notice.company]
    : notice.kind === 'startRefused' ? DR_TEXT.startRefused
    : notice.kind === 'startFailed' ? DR_TEXT.startFailed
    : notice.kind === 'saveRejected' && local.tooMany && nodes.length > 0 ?
      words.tooMany(MAX_NODES, MAX_LEAVES)
    : words[notice.kind];

  return (
    <div data-screen="drafting-outline" className="flex flex-col gap-6">
      <PageTitle
        title={words.title}
        description={`${words.lead(project.year, project.name)}${
          pdfInfo.status.state === 'ready' ?
            words.leadFile(
              pdfInfo.status.value.fileName,
              pdfInfo.status.value.pageCount,
            )
          : ''
        }`}
        className="items-start"
        actions={
          <Button
            variant="outlineGrey"
            shape="round"
            size="md"
            onClick={onList}
          >
            {words.toList}
          </Button>
        }
      />
      <StepFlow
        current={2}
        steps={DR_TEXT.steps.items}
        label={DR_TEXT.steps.label}
      />
      <Card className="flex flex-col gap-4" data-card="outline">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.treeTitle}
          </h3>
          <span className="text-style-pre-caption-03 text-text-tertiary tabular-nums">
            <span data-testid="outline-counts">
              {words.counts(counts.depths, counts.leaves)}
            </span>
            {savedAt !== null && (
              <span data-testid="outline-saved-at">
                {words.savedAt(savedAt)}
              </span>
            )}
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {nodes.length === 0 && (
              <span
                data-testid="need-nodes"
                className="text-style-pre-caption-03 text-text-tertiary"
              >
                {words.needNodes}
              </span>
            )}
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              disabled={busy || !dirty}
              onClick={() => void onSave()}
            >
              {words.save}
            </Button>
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              loading={busy}
              disabled={busy || nodes.length === 0}
              onClick={() => void onStart()}
            >
              {project.latestRun !== null ? words.toDraft : words.start}
            </Button>
          </div>
        </div>
        {dirty && (
          <p
            data-testid="outline-dirty"
            className="m-0 text-style-pre-caption-03 text-text-secondary"
          >
            {words.dirty}
          </p>
        )}
        {savedAfterRun && !dirty && (
          <PageInfo tone="caution" data-testid="changed-after-run">
            {words.changedAfterRun}
          </PageInfo>
        )}
        <p
          id={noticeId}
          role={notice?.kind === 'saved' ? 'status' : 'alert'}
          data-testid="outline-notice"
          data-notice={notice?.kind}
          className={cn(
            'm-0 flex items-center gap-2 text-style-pre-caption-03 empty:hidden [&_svg]:size-4 [&_svg]:shrink-0',
            notice?.kind === 'saved' ?
              'text-text-secondary'
            : 'text-support-error',
          )}
        >
          {noticeText && (
            <>
              {notice?.kind !== 'saved' && <CircleWarningIcon aria-hidden />}
              {noticeText}
              {notice?.kind === 'saveFailed' && (
                <Button
                  variant="outlineGrey"
                  shape="round"
                  size="sm"
                  onClick={() => void onSave()}
                >
                  {DR_TEXT.common.retry}
                </Button>
              )}
            </>
          )}
        </p>
        {nodes.length === 0 ?
          <div className="flex flex-col items-center gap-4 rounded-component border border-solid border-border-tertiary bg-background-primary px-6 py-16 text-style-pre-body-03 text-text-secondary">
            <span data-testid="outline-empty">{words.empty}</span>
            <div className="flex items-center gap-2">
              <Button
                variant="solidBlack"
                shape="round"
                size="sm"
                disabled={busy}
                onClick={onAddTop}
              >
                <PlusIcon aria-hidden />
                {words.addTop}
              </Button>
              <Button
                variant="text"
                size="md"
                className="underline"
                disabled={busy}
                onClick={() => setPasteOpen(true)}
              >
                {words.paste.open}
              </Button>
            </div>
          </div>
        : <div className="grid items-start gap-6 lg:grid-cols-2">
            <OutlineTree
              nodes={nodes}
              at={at}
              changed={changed}
              rowProblems={rowProblems}
              busy={busy}
              dragOff={
                removing !== null || pasteOpen || leave?.pending === true
              }
              listRef={listRef}
              onSelect={(index, focus) => {
                setSelected(index);
                if (focus) askFocus(focus);
              }}
              onAddTop={onAddTop}
              onPaste={() => setPasteOpen(true)}
              onAddSibling={() =>
                at !== null &&
                added(addSibling(nodes, at, words.newTitle, nodeKey))
              }
              onAddChild={() =>
                at !== null &&
                added(addChild(nodes, at, words.newTitle, nodeKey))
              }
              onEnterName={() => askFocus('name')}
              onMove={onRowMove}
              onRemove={setRemoving}
              onDrop={onDrop}
              onDragEnd={() => askFocus('rowQuiet')}
            />
            <div
              className="flex flex-col gap-4 lg:sticky lg:top-6"
              data-testid="outline-editor"
            >
              {node !== null && at !== null && (
                <NodeEditor
                  key={node.key}
                  node={node}
                  path={ancestorsOf(nodes, at)}
                  leaf={isLeaf(nodes, at)}
                  leaves={counts.leaves}
                  problems={problems}
                  disabled={busy}
                  nameRef={nameRef}
                  onEdit={(patch) => {
                    setNodes(edit(nodes, at, patch));
                    setNotice(null);
                    setServerRows((old) => {
                      if (!old.has(node.key)) return old;
                      const next = new Map(old);
                      next.delete(node.key);
                      return next;
                    });
                  }}
                  onNameEnter={() =>
                    added(addSibling(nodes, at, words.newTitle, nodeKey))
                  }
                  onRemove={() => setRemoving(at)}
                />
              )}
            </div>
          </div>
        }
      </Card>
      {removing !== null && nodes[removing] && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setRemoving(null);
          }}
        >
          <DialogContent
            size="sm"
            data-testid="remove-dialog"
            onCloseAutoFocus={(event) => {
              // 닫으면 초점은 고른 줄로(지운 뒤엔 새로 고른 줄) — 열던 줄은 없어졌을 수 있다.
              event.preventDefault();
              focusRow();
            }}
          >
            <DialogTitle className="text-center text-style-pre-heading-02">
              {words.removeConfirm(nodes[removing].title)}
            </DialogTitle>
            {descendantsOf(nodes, removing) > 0 && (
              <DialogDescription className="text-center">
                {words.removeChildren(descendantsOf(nodes, removing))}
              </DialogDescription>
            )}
            <DialogFooter>
              <Button
                variant="outlineBlack"
                shape="round"
                size="md"
                onClick={() => setRemoving(null)}
              >
                {words.cancel}
              </Button>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={() => {
                  const next = removeAt(nodes, removing);
                  setRemoving(null);
                  change(
                    next,
                    next.length === 0 ?
                      null
                    : Math.min(removing, next.length - 1),
                  );
                }}
              >
                {words.removeYes}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
      {pasteOpen && (
        <PasteDialog
          nodes={nodes}
          busy={busy}
          onClose={() => setPasteOpen(false)}
          onInsert={onPaste}
          onInserted={onPasted}
        />
      )}
      {leave?.pending && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) leave.reset();
          }}
        >
          <DialogContent size="sm" data-testid="leave-dialog">
            <DialogTitle className="text-center text-style-pre-heading-02">
              {words.leaveTitle}
            </DialogTitle>
            <DialogDescription className="text-center">
              {words.leaveBody}
            </DialogDescription>
            <DialogFooter>
              <Button
                variant="outlineBlack"
                shape="round"
                size="md"
                onClick={() => leave.reset()}
              >
                {words.leaveStay}
              </Button>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                onClick={() => leave.proceed()}
              >
                {words.leaveGo}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
