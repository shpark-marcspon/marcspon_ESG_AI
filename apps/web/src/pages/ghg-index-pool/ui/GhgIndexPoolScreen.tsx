// S19 인벤토리 관리 > 온실가스 인덱스(운영 관리자 공통 풀 — 밴드 W12-0b1 ③, 스펙 ② S19, 결정 sid:MARC-ENT-469 3·5).
// 라우터·세션을 모른다: 풀 실어댑터(port)·코드 목록 어댑터(codes — S18 의 /admin/facility-codes, ★G)를 props 로 받는다.
//   - 제목 「온실가스 인덱스」 · 검색(→ q, 맞는 노드와 조상만) · 4열 판(배출범위·배출원 유형·배출활동·자산/시설명) · 열 끝 추가 넷.
//   - 항목을 고르면 오른쪽 열이 그 자식. 처음은 왼쪽부터 첫 항목(배출활동까지 — model firstPath). 자산/시설 판은 잎을 고를 때만(Q7).
//   - 열 1~3 항목 줄에 「⋯」 작은 메뉴(수정·삭제 — 스펙 [우리 해석]). 글자 모달(이름* 100자) → POST·PATCH · 삭제 확인 창 → nodes/delete
//     (409 HAS_CHILDREN·IN_USE 글 · 404 한 줄 + 다시 읽음). ≡·업로드·다운로드는 숨김(469-5).
//   - 열 4 추가 → 새 자산/시설 판 · 잎 고름 → 그 판(FacilityPanel).
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
  DotsThreeVerticalIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  FacilityCodeAdminPort,
  GhgPoolAdminPort,
  PoolWrite,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  POOL_LEVELS,
  columnsOf,
  firstPath,
} from '../../../entities/ghg/model/index.ts';
import type {
  FacilityCode,
  PoolLevel,
  PoolNode,
  PoolOptions,
} from '../../../entities/ghg/model/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import { Toaster } from '../../../shared/ui/toast/index.ts';
import { FacilityPanel } from './FacilityPanel.tsx';
import { ConfirmDialog, NameDialog } from './parts.tsx';

const words = GHG_TEXT.pool;
/** 검색을 보내기 전에 기다리는 ms(조직구조 목록과 같다). */
export const POOL_SEARCH_DELAY_MS = 300;
/** 코드 목록 쪽 돌기 상한(★G — 쪽 100 × 열 쪽). */
export const CODE_PAGE_LIMIT = 10;

export interface GhgIndexPoolScreenProps {
  port: GhgPoolAdminPort;
  /** 자산/시설명 및 코드 드롭다운의 원천(운영 관리자 /admin/facility-codes — 쪽을 돌아 다 읽는다). */
  codes: FacilityCodeAdminPort;
  /** S20 기준연도 드롭다운의 끝(올해). */
  thisYear: number;
}

/** 모든 쪽을 돌아 코드를 읽는다(상한 CODE_PAGE_LIMIT 쪽). */
async function readAllCodes(
  codes: FacilityCodeAdminPort,
): Promise<FacilityCode[] | null> {
  const out: FacilityCode[] = [];
  for (let page = 1; page <= CODE_PAGE_LIMIT; page += 1) {
    const read = await codes.list(page);
    if (read.kind !== 'ok') return null;
    out.push(
      ...read.value.results.map(({ id, code, name }) => ({ id, code, name })),
    );
    if (!read.value.hasNext) break;
  }
  return out;
}

type Modal =
  | {
      kind: 'add';
      level: Exclude<PoolLevel, 'facility'>;
      parentId: string | null;
      from: HTMLElement;
    }
  | { kind: 'rename'; node: PoolNode; from: HTMLElement }
  | { kind: 'delete'; node: PoolNode; from: HTMLElement }
  | null;

type Notice = 'hasChildren' | 'inUseDelete' | 'notFound' | 'writeFailed' | null;

export function GhgIndexPoolScreen({
  port,
  codes,
  thisYear,
}: GhgIndexPoolScreenProps) {
  /** 부모 id('' = 범위 단) → 읽은 자식. */
  const [children, setChildren] = useState<Record<string, PoolNode[]>>({});
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState('');
  const [sentQuery, setSentQuery] = useState('');
  const [found, setFound] = useState<PoolNode[] | null>(null);
  const [path, setPath] = useState<string[]>([]);
  /** 새 자산/시설 판을 연 부모(배출활동) id. */
  const [adding, setAdding] = useState<string | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  const [menuOf, setMenuOf] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [options, setOptions] = useState<PoolOptions | null>(null);
  const [codeList, setCodeList] = useState<FacilityCode[] | null>(null);
  const reads = useRef(0);

  const load = useCallback(
    async (parentId: string) => {
      const out = await port.listNodes(parentId === '' ? {} : { parentId });
      if (out.kind !== 'ok') return setFailed(true);
      setChildren((before) => ({ ...before, [parentId]: out.value }));
    },
    [port],
  );

  // 처음: 범위 단 · 선택 목록 · 코드 목록.
  useEffect(() => {
    void load('');
    void port.options().then((out) => {
      if (out.kind === 'ok') setOptions(out.value);
    });
    void readAllCodes(codes).then(setCodeList);
  }, [load, port, codes]);

  // 검색: 멈춘 뒤 q 로(맞는 노드와 조상만). 빈 글이면 열 읽기로 돌아간다.
  useEffect(() => {
    if (query === sentQuery) return;
    const timer = setTimeout(() => setSentQuery(query), POOL_SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query, sentQuery]);
  useEffect(() => {
    const text = sentQuery.trim();
    const ticket = (reads.current += 1);
    if (text === '') return setFound(null);
    void port.listNodes({ q: text }).then((out) => {
      if (ticket !== reads.current) return;
      if (out.kind !== 'ok') return setFailed(true);
      setFound(out.value);
    });
  }, [port, sentQuery]);

  const nodes = found ?? Object.values(children).flat();
  // 고른 길(state)을 왼쪽부터 첫 항목으로 이은 것이 보이는 길이다(지워짐·검색 밖이면 거기서 첫 항목으로).
  const shown = firstPath(nodes, path);
  const columns = columnsOf(nodes, shown);
  const want = found ? '' : shown.slice(0, 3).join('/');

  // 열 읽기 모드: 보이는 길의 자식을 아직 안 읽었으면 한 번만 읽는다(요청한 부모 id 는 requested 가 막는다).
  const requested = useRef(new Set<string>());
  useEffect(() => {
    if (want === '') return;
    for (const id of want.split('/')) {
      if (requested.current.has(id)) continue;
      requested.current.add(id);
      void load(id);
    }
  }, [want, load]);

  const select = (index: number, node: PoolNode) => {
    setMenuOf(null);
    setNotice(null);
    setAdding(null);
    setPath([...shown.slice(0, index), node.id]);
  };

  /** 쓰기 뒤: 검색 중이면 q 를 다시, 아니면 읽어 둔 열을 모두 다시(하위 수가 부모 열에 보이므로). */
  const reload = async () => {
    if (found) {
      const out = await port.listNodes({ q: sentQuery.trim() });
      if (out.kind === 'ok') setFound(out.value);
      return;
    }
    await Promise.all(['', ...requested.current].map(load));
  };

  const afterWrite = async (outcome: PoolWrite<unknown>) => {
    setModal(null);
    if (outcome.kind === 'ok') setNotice(null);
    else if (outcome.kind === 'rejected' && outcome.code === 'HAS_CHILDREN')
      setNotice('hasChildren');
    else if (outcome.kind === 'rejected' && outcome.code === 'IN_USE')
      setNotice('inUseDelete');
    else if (outcome.kind === 'rejected' && outcome.code === 'NOT_FOUND')
      setNotice('notFound');
    else setNotice('writeFailed');
    await reload();
  };

  const remove = async (node: PoolNode) => {
    setBusy(true);
    const outcome = await port.deleteNodes([node.id]);
    setBusy(false);
    // 지웠거나 이미 없으면(404) 그 노드의 읽은 자식을 버리고 길을 그 앞에서 자른다.
    if (
      outcome.kind === 'ok' ||
      (outcome.kind === 'rejected' && outcome.code === 'NOT_FOUND')
    ) {
      requested.current.delete(node.id);
      setChildren((before) =>
        Object.fromEntries(
          Object.entries(before).filter(([parent]) => parent !== node.id),
        ),
      );
      const at = shown.indexOf(node.id);
      if (at >= 0) setPath(shown.slice(0, at));
    }
    await afterWrite(outcome);
  };

  if (failed)
    return (
      <div data-screen="admin-ghg-index" className="flex flex-col gap-6">
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
        >
          {words.loadFailed}
        </PageInfo>
      </div>
    );

  const leafId = shown[3] ?? null;
  const activityId = shown[2] ?? null;

  return (
    <div data-screen="admin-ghg-index" className="flex flex-col gap-6">
      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
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
            data-testid="pool-notice"
            className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
          >
            {notice && (
              <>
                <CircleWarningIcon aria-hidden />
                {words[notice]}
              </>
            )}
          </p>
        </div>
        {found && found.length === 0 && (
          <p
            data-testid="pool-empty-search"
            className="m-0 text-style-pre-body-06 text-text-tertiary"
          >
            {words.emptySearch}
          </p>
        )}
        <div className="grid grid-cols-4 gap-0 border border-solid border-border-tertiary">
          {POOL_LEVELS.map((level, index) => {
            const column = columns[index]!;
            const parentId = index === 0 ? null : (shown[index - 1] ?? null);
            const open = index === 0 || parentId !== null;
            const loading = !found && open && !((parentId ?? '') in children);
            return (
              <section
                key={level}
                data-column={level}
                aria-labelledby={`ghg-pool-col-${level}`}
                className="flex min-w-0 flex-col border-0 border-r border-solid border-border-tertiary last:border-r-0"
              >
                <h3
                  id={`ghg-pool-col-${level}`}
                  className="m-0 h-10 border-0 border-b border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 leading-10 text-text-tertiary"
                >
                  {words.columns[level]}
                </h3>
                {loading ?
                  <LoadSkeleton label={GHG_TEXT.common.loading} />
                : <ul className="m-0 flex list-none flex-col p-0">
                    {open && column.length === 0 && (
                      <li className="px-4 py-3 text-style-pre-body-06 text-text-tertiary">
                        {words.emptyColumn}
                      </li>
                    )}
                    {column.map((node) => {
                      const chosen = shown[index] === node.id;
                      return (
                        <li
                          key={node.id}
                          data-node-id={node.id}
                          className={cn(
                            'relative flex items-center border-0 border-b border-solid border-border-tertiary',
                            chosen && 'bg-background-secondary',
                          )}
                        >
                          <button
                            type="button"
                            aria-current={chosen || undefined}
                            className="flex h-12 min-w-0 flex-1 items-center gap-2 border-0 bg-transparent px-4 text-left text-style-pre-body-06 text-text-primary"
                            onClick={() => select(index, node)}
                          >
                            <span className="min-w-0 flex-1 truncate">
                              {node.name}
                            </span>
                            {level !== 'facility' && (
                              <>
                                <span
                                  data-testid="child-count"
                                  className="text-style-pre-caption-03 text-text-tertiary"
                                >
                                  <span aria-hidden>{node.childCount}</span>
                                  <span className="sr-only">
                                    {words.childCount(node.childCount)}
                                  </span>
                                </span>
                                <ChevronRightIcon
                                  aria-hidden
                                  className="size-4 text-text-tertiary"
                                />
                              </>
                            )}
                          </button>
                          {level !== 'facility' && (
                            <button
                              type="button"
                              aria-label={words.menuLabel(node.name)}
                              aria-expanded={menuOf === node.id}
                              className="mr-2 inline-flex size-8 items-center justify-center rounded-control border-0 bg-transparent p-0 text-text-tertiary [&_svg]:size-4"
                              onClick={() =>
                                setMenuOf(menuOf === node.id ? null : node.id)
                              }
                            >
                              {/* GX2 D4(sid:MARC-ISSUE-461): ⋮ — 2×3 점은 드래그 손잡이처럼 읽힌다. */}
                              <DotsThreeVerticalIcon
                                aria-hidden
                                data-icon="dots-vertical"
                              />
                            </button>
                          )}
                          {menuOf === node.id && (
                            <div
                              role="group"
                              aria-label={words.menuLabel(node.name)}
                              className="absolute right-2 top-11 z-10 flex flex-col rounded-control border border-solid border-border-tertiary bg-background-primary shadow-sm"
                            >
                              <button
                                type="button"
                                className="h-9 border-0 bg-transparent px-4 text-left text-style-pre-body-06"
                                onClick={(event) => {
                                  setMenuOf(null);
                                  setModal({
                                    kind: 'rename',
                                    node,
                                    from: event.currentTarget,
                                  });
                                }}
                              >
                                {words.edit}
                              </button>
                              <button
                                type="button"
                                className="h-9 border-0 bg-transparent px-4 text-left text-style-pre-body-06"
                                onClick={(event) => {
                                  setMenuOf(null);
                                  setModal({
                                    kind: 'delete',
                                    node,
                                    from: event.currentTarget,
                                  });
                                }}
                              >
                                {words.remove}
                              </button>
                            </div>
                          )}
                        </li>
                      );
                    })}
                    {open && !found && (
                      <li>
                        <button
                          type="button"
                          className="h-12 w-full border-0 bg-transparent px-4 text-left text-style-pre-body-06 text-text-secondary"
                          onClick={(event) => {
                            setNotice(null);
                            if (level === 'facility') {
                              setPath(shown.slice(0, 3));
                              setAdding(activityId);
                              return;
                            }
                            setModal({
                              kind: 'add',
                              level,
                              parentId,
                              from: event.currentTarget,
                            });
                          }}
                        >
                          {words.add[level]}
                        </button>
                      </li>
                    )}
                  </ul>
                }
              </section>
            );
          })}
        </div>
      </Card>
      {(leafId !== null || adding !== null) && options && codeList && (
        <FacilityPanel
          key={leafId ?? `new-${adding}`}
          port={port}
          options={options}
          codes={codeList}
          leafId={leafId}
          parentId={leafId === null ? adding! : activityId!}
          thisYear={thisYear}
          onCreated={async (id) => {
            setAdding(null);
            setPath([...shown.slice(0, 3), id]);
            await reload();
          }}
          onSaved={() => void reload()}
          onDeleted={async () => {
            setPath(shown.slice(0, 3));
            await reload();
          }}
          onCancelNew={() => setAdding(null)}
        />
      )}
      {modal?.kind === 'add' && (
        <NameDialog
          title={words.nameDialogAdd(words.columns[modal.level])}
          initial=""
          returnFocus={modal.from}
          send={(name) =>
            port.createNode({
              level: modal.level,
              parentId: modal.parentId,
              name,
            })
          }
          onDone={(outcome) => void afterWrite(outcome)}
          onClose={() => setModal(null)}
        />
      )}
      {modal?.kind === 'rename' && (
        <NameDialog
          title={words.nameDialogEdit(words.columns[modal.node.level])}
          initial={modal.node.name}
          returnFocus={modal.from}
          send={(name) => port.renameNode(modal.node.id, name)}
          onDone={(outcome) => void afterWrite(outcome)}
          onClose={() => setModal(null)}
        />
      )}
      {modal?.kind === 'delete' && (
        <ConfirmDialog
          title={words.deleteConfirm}
          cancel={words.cancel}
          confirm={words.confirmDelete}
          returnFocus={modal.from}
          testId="pool-delete-dialog"
          busy={busy}
          onConfirm={() => void remove(modal.node)}
          onClose={() => setModal(null)}
        />
      )}
      <Toaster />
    </div>
  );
}
