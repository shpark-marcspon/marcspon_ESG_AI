// 상세 표의 체크·히스토리 칸과 표 위 줄(밴드 S3W3b — 값 파일 1·5절, 발주서 1-6).
//   칸은 고름을 컨텍스트로 읽는다: 고름을 columns 의존에 넣으면 칸 함수가 새로 지어져 칸이 다시 달리고 초점이 사라진다(Space 뒤 초점 유지).
//   막힌 단추엔 툴팁이 안 뜬다 — 트리거를 단추가 아니라 감싼 span(초점 받음)에 단다(a 값 파일 QC3).
//   히스토리 단추는 잠겨도 막지 않는다(읽기). C12·C15 도 막지 않는다(sid:MARC-ENT-579 는 계수 수정만).
//   [원본 다운로드](밴드 S3Q1 ① — 값 파일 ①): 단추 무리 맨 앞 회색 sm·아이콘 0. 그 카테고리 지금 실행(runId)에 올린 파일 통째(서버가 이름을 준다).
//   잠겨도 켬(읽기 — LockedTip 으로 감싸지 않는다). 받는 중엔 그 단추만 막고 「받는 중…」. 실패 글은 부르는 쪽이 표 위 줄 아래에 그린다.
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';

import { Checkbox } from '@marcspon/ui/components/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';

import type { Scope3Port } from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  pickState,
  rowNumber,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  ResultRow,
  RowEditKind,
} from '../../../entities/ghg-scope3/model/index.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { Button } from '../../../shared/ui/button/index.ts';

const words = S3_TEXT.rowEdit;
const originalWords = S3_TEXT.original;

export type SaveFile = (blob: Blob, fileName: string) => void;

/** [원본 다운로드]의 상태(S3Q1). runId 가 없으면 take 는 아무것도 하지 않는다(부르는 쪽이 단추를 그리지 않는다). */
export function useOriginalDownload({
  port,
  runId,
  save = saveBlob,
}: {
  port: Scope3Port;
  runId: string | null;
  save?: SaveFile;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const busyRef = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const take = async () => {
    if (runId === null || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    const out = await port.original(runId);
    busyRef.current = false;
    if (!alive.current) return; // 받는 사이 상세를 닫음 — 글을 남기지 않는다
    setBusy(false);
    if (out.kind === 'ok') save(out.value.blob, out.value.fileName);
    else
      setProblem(
        out.kind === 'notFound' ? originalWords.notFound
        : out.kind === 'refused' ? S3_TEXT.company[out.company]
        : originalWords.failed,
      );
  };
  return { busy, problem, take };
}

/** 표 위 줄 단추 무리 맨 앞(값 파일 ① — [산정 제외]와 같은 꼴, 아이콘 0). 받는 중은 막힘 + 글 「받는 중…」(e6 11-10 (가) — aria-busy 없음). */
export function OriginalButton({
  busy,
  onTake,
}: {
  busy: boolean;
  onTake(): void;
}) {
  return (
    <Button
      variant="solidGrey"
      shape="square"
      size="sm"
      disabled={busy}
      data-testid="s3-original"
      onClick={onTake}
    >
      {busy ? originalWords.busy : originalWords.button}
    </Button>
  );
}

export interface RowPick {
  chosen: ReadonlySet<string>;
  /** 잠김·지금 결과 없음 — 체크·두 단추 막음. */
  blocked: boolean;
  /** 지금 결과가 있어 이력을 읽을 수 있다. */
  canHistory: boolean;
  choose(ids: readonly string[], on: boolean): void;
  openHistory(rowId: string, button: HTMLElement): void;
}

const NO_PICK: RowPick = {
  chosen: new Set(),
  blocked: true,
  canHistory: false,
  choose: () => {},
  openHistory: () => {},
};

export const RowPickContext = createContext<RowPick>(NO_PICK);
/** 그 표의 지금 쪽 줄 id(머리 체크 — 지금 쪽만, B1). */
export const PageIdsContext = createContext<readonly string[]>([]);

export function HeadCheck() {
  const { chosen, blocked, choose } = useContext(RowPickContext);
  const ids = useContext(PageIdsContext);
  return (
    <Checkbox
      aria-label={words.pickPage}
      data-testid="s3-pick-page"
      checked={pickState(chosen, ids)}
      disabled={blocked || ids.length === 0}
      onCheckedChange={(value) => choose(ids, value === true)}
    />
  );
}

export function RowCheck({ row }: { row: ResultRow }) {
  const { chosen, blocked, choose } = useContext(RowPickContext);
  const { rowId } = row;
  return (
    <Checkbox
      aria-label={words.pickRow(rowNumber(rowId) ?? S3_TEXT.result.empty)}
      data-testid="s3-pick-row"
      checked={rowId !== null && chosen.has(rowId)}
      disabled={blocked || rowId === null}
      onCheckedChange={(value) => {
        if (rowId !== null) choose([rowId], value === true);
      }}
    />
  );
}

export function HistoryButton({ row }: { row: ResultRow }) {
  const { canHistory, openHistory } = useContext(RowPickContext);
  const { rowId } = row;
  return (
    <Button
      variant="solidGrey"
      shape="square"
      size="sm"
      aria-haspopup="dialog"
      disabled={!canHistory || rowId === null}
      data-testid="s3-history-open"
      onClick={(event: MouseEvent<HTMLButtonElement>) => {
        if (rowId !== null) openHistory(rowId, event.currentTarget);
      }}
    >
      {words.history.open}
    </Button>
  );
}

/** 잠겼으면 감싼 span 에 툴팁, 아니면 그대로. */
function LockedTip({
  locked,
  children,
}: {
  locked: boolean;
  children: ReactNode;
}) {
  if (!locked) return children;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            data-testid="s3-edit-locked"
            className="inline-flex"
          >
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent>{words.locked}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export interface EditButtonsProps {
  locked: boolean;
  blocked: boolean;
  excludeCount: number;
  restoreCount: number;
  onAsk(kind: RowEditKind, button: HTMLElement): void;
}

/** 표 위 줄 단추 둘(산정 제외·복구 — 오른쪽 끝 자리는 부르는 쪽 무리가 잡는다, [원본 다운로드] 뒤). */
export function EditButtons({
  locked,
  blocked,
  excludeCount,
  restoreCount,
  onAsk,
}: EditButtonsProps) {
  const restoreBlocked = blocked || restoreCount === 0;
  return (
    <div className="flex items-center gap-2">
      <LockedTip locked={locked}>
        <Button
          variant="solidGrey"
          shape="square"
          size="sm"
          disabled={blocked || excludeCount === 0}
          data-testid="s3-exclude"
          onClick={(event: MouseEvent<HTMLButtonElement>) =>
            onAsk('exclude', event.currentTarget)
          }
        >
          {words.exclude}
        </Button>
      </LockedTip>
      <LockedTip locked={locked}>
        <Button
          // 막혔을 때는 [산정 제외]와 같은 막힘 꼴(공용 disabled 는 바탕색이 variant 그대로라 검정이 짙다 — S3Q2 · 감독 de 안 A · c3 11-11).
          variant={restoreBlocked ? 'solidGrey' : 'solidBlack'}
          shape="square"
          size="sm"
          disabled={restoreBlocked}
          data-testid="s3-restore"
          onClick={(event: MouseEvent<HTMLButtonElement>) =>
            onAsk('restore', event.currentTarget)
          }
        >
          {words.restore}
        </Button>
      </LockedTip>
    </div>
  );
}
