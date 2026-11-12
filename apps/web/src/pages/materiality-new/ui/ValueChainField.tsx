// IR-02 「가치사슬 활동 (선택)」 칸(밴드 IRW2 ② — 판 IR-02_r1 v166, 부록 A2·A5·A6). 행은 부르는 쪽(폼)이 쥐고, 이 칸은 넣는 길만 쥔다.
//   밑줄 탭 [엑셀 올리기]·[붙여 넣기]·[직접 입력](IRW3 — 판 v170) → 넣기 전 자리(shared file-dropzone · 점선 글 칸 · 빈 행 하나의 표)
//   → 넣으면 같은 표(편집·[행 추가]·[모두 지우기]). 표가 있으면 넣기 자리는 숨고 [모두 지우기]·마지막 행 지우기로
//   돌아온다. 붙여 넣기·직접 입력이면 파일 줄 없음(판에 없음).
// 파일 줄 = 공용 FileDropzone 목록 한 줄(이름 · meta · 날짜 · 실패면 「넣지 못함」 — IRW6, sid:MARC-ISSUE-434). 읽힌 줄은 hideDrop 이라
//   칸 없이 [×] 만 남고 누르면 [모두 지우기]와 같은 일(IRW7, sid:MARC-ISSUE-439 — IRW6 전과 같다). 실패 줄·disabled 면 readOnly 라 [×] 0.
// 직접 입력의 빈 행은 화면만의 행이다(행이 0 이면 그린다 — 지우거나 [모두 지우기]면 다시 빈 행 하나). 칸에 적으면 그때 행이 된다.
//   표가 다섯 칸 다 빈 행뿐일 때 탭을 바꾸면 행을 비워 그 탭의 넣기 자리로(빈 행은 input·검사에서 어차피 빠진다 — model filledRows).
// 올리기: 판정(judgeFiles — .xlsx·1MB·한 개)은 이 칸이 한다 — 드롭존에는 규칙을 주지 않아 드롭존 안의 거부 줄이 겹쳐 보이지 않는다
//   (shared 0줄). size → A6-① · type·count → 「표가 비어 있거나…」(둘 다 파일 줄에 「넣지 못함」, 요청 0) → 통과면
//   store.readValueChain(맨 바이트) → ok 는 model rowsFromServer, ok:false 는 kind 로 부록 A5 · 끊김·5xx 는 A6-⑥.
// 붙여 넣기: 글이 바뀔 때마다 model rowsFromPaste → 읽으면 표, 아니면 글 칸이 남고 오류 글. 행이 없는 글(열 이름 줄뿐)은 글 칸 그대로.
// 밸류체인을 못 맞춘 행은 넣고 그 칸만 비운다 — 넣자마자(또는 [평가 시작] 뒤) 빨간 테두리와 표 위 글, 고르면 사라진다.
// 서버 message 는 화면에 0 — 글은 IR_TEXT 한 곳.
// [양식 받기](밴드 IRW15 ① — 결정 MARC-ENT-668): 엑셀 올리기 탭 드롭 칸의 열 안내 줄 바로 아래. 정적 파일(apps/web/public/templates/ —
//   머리 다섯만, 서버 HEADER 와 같음은 api-py tests/tools/test_value_chain_template.py)을 <a download> 로 내려받는다. 꼴은 영문번역
//   TR-02 [양식 내려받기](shared DownloadButton — outlineGrey · square · sm · 내려받기 아이콘)와 같게 공용 Button asChild 로 짓는다
//   (DownloadButton 은 <p> 를 품어 드롭 칸의 안내 <p> 안에 넣을 수 없다 — shared 0줄). 누름·Enter·Space 는 드롭 칸으로 올리지 않는다(파일 창 0).
// 떠나기 경고 빈틈(밴드 IRW17): 행(폼 draft)에 안 잡히는 것 — 붙여 넣기 칸의 글(표로 안 읽힌 글 포함)·파일 줄(읽힌·읽는 중·넣지 못함)
//   — 이 하나라도 있으면 onDirtyChange(true). 폼이 draft 비교와 OR 로 묶는다.
import { useEffect, useRef, useState } from 'react';

import {
  CloseIcon,
  DownloadIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@marcspon/ui/components/table';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  MaterialityStore,
  MaterialityValueChainRead,
} from '../../../entities/materiality/api/index.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import {
  VALUE_CHAIN_KEYS,
  VALUE_CHAIN_MAX_CHARS,
  VALUE_CHAIN_MAX_ROWS,
  VALUE_CHAIN_STAGES,
  blankValueChainRow,
  businessUnitCount,
  rowsFromPaste,
  rowsFromServer,
  stagelessRows,
} from '../../../entities/materiality/model/index.ts';
import type {
  ValueChainParsed,
  ValueChainRow,
  ValueChainStage,
} from '../../../entities/materiality/model/index.ts';
import { Button, IconButton } from '../../../shared/ui/button/index.ts';
import {
  FileDropzone,
  judgeFiles,
} from '../../../shared/ui/file-dropzone/index.ts';
import type { DraggableInputItem } from '../../../shared/ui/file-dropzone/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import { FieldError } from './FieldError.tsx';

const words = IR_TEXT.newRun.valueChain;
const errors = words.errors;

/** 판정 규칙(.xlsx 한 개 · 1MB — 서버 MAX_BYTES 와 같은 1,048,576 바이트). */
const RULE = { accept: ['.xlsx'], maxMb: 1, maxCount: 1 } as const;

type Source = 'file' | 'paste' | 'manual';

/** 표 열 너비(판 colgroup — 15% · 23% · 150px · 15% · 나머지 · 52px). */
const COLUMN_WIDTHS = ['15%', '23%', '150px', '15%', undefined, '52px'];

/** 판 d-vc: th 높이 40 · 왼쪽 맞춤 · 좌우 8(키트 TableHead 의 text-center px-4 를 덮음) · td 8. 머리 바탕·위아래 선은 공용 결과 표
 *  머리와 같은 값(shared/ui/data-table DataTable 의 th — 6c D1, IRW6). */
const HEAD =
  'h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-2 text-left';
const CELL = 'p-2';

/** 다섯 칸이 다 빈 행뿐인가(행 0 포함). */
const allBlank = (rows: readonly ValueChainRow[]) =>
  rows.every((row) => VALUE_CHAIN_KEYS.every((key) => row[key].trim() === ''));

/** 표로 넣지 못한 까닭 → 글(부록 A5 — 붙여 넣기의 같은 까닭도 같은 글). */
function parsedError(parsed: ValueChainParsed): string | null {
  if (parsed.ok) return null;
  switch (parsed.error) {
    case 'columns':
      return errors.columns(parsed.columns);
    case 'too_many_rows':
      return errors.tooManyRows;
    case 'too_long':
      return errors.tooLong(
        parsed.row,
        words.columns[parsed.column]!,
        parsed.max,
      );
    case 'no_rows':
      return errors.notTable;
  }
}

/** 서버 거절 kind → 글(부록 A5). */
function rejectedError(
  read: Extract<MaterialityValueChainRead, { ok: false }>,
): string {
  const column = read.column === null ? undefined : words.columns[read.column];
  switch (read.kind) {
    case 'bad_header':
      return errors.badHeader;
    case 'too_large':
      return errors.tooLarge;
    case 'too_many_rows':
      return errors.tooManyRows;
    case 'too_many_scanned_rows':
      return errors.tooManyScannedRows;
    case 'too_long':
      return read.row === null || read.column === null || column === undefined ?
          errors.notTable
        : errors.tooLong(read.row, column, VALUE_CHAIN_MAX_CHARS[read.column]!);
    case 'not_text':
      return read.row === null || column === undefined ?
          errors.notTable
        : errors.notText(read.row, column);
    default:
      return errors.notTable;
  }
}

/** 빈 양식 주소(origin 뿌리 — vite base 「/」. pages 는 shared/lib/address 를 가져오지 않는다(app/guards/layers.test.ts) — 하위 경로
 *  서빙으로 base 를 바꾸면 여기도). */
const TEMPLATE_URL = `/templates/${encodeURIComponent(words.templateFile)}`;

/** [양식 받기] — 드롭 칸 안에 있어 누름·키를 칸으로 올리지 않는다. */
function TemplateLink() {
  return (
    <Button asChild variant="outlineGrey" shape="square" size="sm">
      <a
        href={TEMPLATE_URL}
        download={words.templateFile}
        data-testid="value-chain-template"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <DownloadIcon aria-hidden />
        {words.template}
      </a>
    </Button>
  );
}

export interface ValueChainFieldProps {
  store: MaterialityStore;
  rows: readonly ValueChainRow[];
  onRows(rows: ValueChainRow[]): void;
  /** [평가 시작]을 눌렀는가(밸류체인 빈 칸을 늘 보인다). */
  tried: boolean;
  /** 칸 id 의 머리(밸류체인 고름 칸 = `${idBase}-stage-${행 차례}` — 첫 오류 칸 초점). */
  idBase: string;
  /** 넣는 동안([평가 시작] 기다림) 끔. */
  disabled?: boolean;
  /** 붙여 넣기 칸 글이 비지 않았거나 파일 줄이 하나라도 있는가 — 바뀔 때마다(IRW17 떠나기 경고). */
  onDirtyChange?(dirty: boolean): void;
}

export function ValueChainField({
  store,
  rows,
  onRows,
  tried,
  idBase,
  disabled = false,
  onDirtyChange,
}: ValueChainFieldProps) {
  const [source, setSource] = useState<Source>('file');
  const [paste, setPaste] = useState('');
  /** 표를 낸 파일(드롭존이 준 항목 그대로 — 붙여 넣기면 null). */
  const [fileItem, setFileItem] = useState<DraggableInputItem | null>(null);
  /** 넣지 못한 파일(파일 줄에 「넣지 못함」). */
  const [failedItem, setFailedItem] = useState<DraggableInputItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState<string | null>(null);
  /** 넣자마자 밸류체인 빈 칸을 보인다(못 맞춘 행이 있었을 때). */
  const [alert, setAlert] = useState(false);
  const readSeq = useRef(0);
  /** 행 밖에 남은 넣은 것(붙여 넣기 글 · 파일 줄). */
  const held =
    paste.trim() !== '' ||
    fileItem !== null ||
    failedItem !== null ||
    reading !== null;
  useEffect(() => {
    onDirtyChange?.(held);
  }, [held, onDirtyChange]);

  /** 직접 입력이고 행이 0 이면 화면만의 빈 행 하나. */
  const shown =
    rows.length === 0 && source === 'manual' ? [blankValueChainRow()] : rows;
  const stageless = stagelessRows(rows);
  const showStage = (tried || alert) && stageless.length > 0;
  const errorId = `${idBase}-vc-error`;

  const put = (next: ValueChainRow[], item: DraggableInputItem | null) => {
    onRows(next);
    setFileItem(item);
    setFailedItem(null);
    setError(null);
    setAlert(stagelessRows(next).length > 0);
  };

  const fail = (item: DraggableInputItem, text: string) => {
    setFailedItem(item);
    setError(text);
  };

  const clear = () => {
    readSeq.current += 1;
    setReading(null);
    onRows([]);
    setFileItem(null);
    setFailedItem(null);
    setError(null);
    setAlert(false);
  };

  const onFiles = (items: DraggableInputItem[]) => {
    const files = items.flatMap((item) => (item.file ? [item.file] : []));
    if (files.length === 0) return;
    const judged = judgeFiles(files, [], RULE);
    const first = files[0]!;
    const item = items.find((each) => each.file === first)!;
    if (judged.rejected.length > 0) {
      fail(
        item,
        judged.rejected.some((each) => each.reason === 'size') ?
          errors.tooLarge
        : errors.notTable,
      );
      return;
    }
    const seq = ++readSeq.current;
    setReading(first.name);
    setFailedItem(null);
    setError(null);
    store.readValueChain(first).then(
      (read) => {
        if (seq !== readSeq.current) return;
        setReading(null);
        if (!read.ok) {
          fail(item, rejectedError(read));
          return;
        }
        const parsed = rowsFromServer(read.rows);
        if (parsed.ok) put(parsed.rows, item);
        else fail(item, parsedError(parsed) ?? errors.notTable);
      },
      () => {
        if (seq !== readSeq.current) return;
        setReading(null);
        fail(item, errors.unreadable);
      },
    );
  };

  const onPaste = (text: string) => {
    setPaste(text);
    setFailedItem(null);
    if (text.trim() === '') {
      setError(null);
      return;
    }
    const parsed = rowsFromPaste(text);
    if (parsed.ok) {
      put(parsed.rows, null);
      setPaste('');
      return;
    }
    setError(parsed.error === 'no_rows' ? null : parsedError(parsed));
  };

  const setCell = (index: number, patch: Partial<ValueChainRow>) =>
    onRows(shown.map((row, at) => (at === index ? { ...row, ...patch } : row)));

  const removeRow = (index: number) => {
    const next = shown.filter((_, at) => at !== index);
    if (next.length === 0) clear();
    else onRows(next);
  };

  return (
    <div data-testid="value-chain" className="flex w-full flex-col gap-3">
      <Tabs
        variant="line"
        value={source}
        onValueChange={(next) => {
          setSource(next as Source);
          setError(null);
          setFailedItem(null);
          if (rows.length > 0 && allBlank(rows)) {
            onRows([]);
            setFileItem(null);
            setAlert(false);
          }
        }}
      >
        <TabsList aria-label={words.tabsLabel}>
          <TabsTrigger value="file" disabled={disabled}>
            {words.tabFile}
          </TabsTrigger>
          <TabsTrigger value="paste" disabled={disabled}>
            {words.tabPaste}
          </TabsTrigger>
          <TabsTrigger value="manual" disabled={disabled}>
            {words.tabManual}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {shown.length === 0 ?
        <>
          {source === 'file' ?
            <FileDropzone
              itemList={[]}
              onChangeItemList={onFiles}
              guide={words.dropTitle}
              formats={
                <>
                  {words.dropHint}
                  <span className="mt-3 flex justify-center">
                    <TemplateLink />
                  </span>
                </>
              }
              isUploading={reading !== null || disabled}
              invalid={error !== null}
              describedBy={error !== null ? errorId : undefined}
            />
          : <Textarea
              aria-label={words.pasteLabel}
              placeholder={words.pastePlaceholder}
              value={paste}
              disabled={disabled}
              aria-invalid={error !== null || undefined}
              aria-describedby={error !== null ? errorId : undefined}
              onChange={(event) => onPaste(event.target.value)}
              rows={5}
              className="min-h-24 border-dashed border-text-quaternary"
            />
          }
          {failedItem !== null && (
            <FileLine
              item={{ ...failedItem, status: 'failed' }}
              testId="file-line-failed"
            />
          )}
          {error !== null && (
            <FieldError id={errorId} role="alert" testId="value-chain-error">
              {error}
            </FieldError>
          )}
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {words.empty}
          </p>
        </>
      : <>
          {fileItem !== null && (
            <FileLine
              item={fileItem}
              testId="file-line"
              meta={words.fileLine(rows.length, businessUnitCount(rows))}
              onRemove={disabled ? undefined : clear}
            />
          )}
          {showStage && (
            <FieldError role="alert" testId="stage-error">
              {errors.stage(stageless)}
            </FieldError>
          )}
          <Table data-testid="value-chain-table" className="table-fixed">
            <colgroup>
              {COLUMN_WIDTHS.map((width, index) => (
                <col key={index} style={width ? { width } : undefined} />
              ))}
            </colgroup>
            <TableHeader>
              <TableRow>
                {words.columns.map((name) => (
                  <TableHead key={name} className={HEAD}>
                    {name}
                  </TableHead>
                ))}
                <TableHead className={cn(HEAD, 'text-center')}>
                  <span className="sr-only">{words.removeHead}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((row, index) => {
                const n = index + 1;
                const bad = showStage && stageless.includes(n);
                return (
                  <TableRow key={index}>
                    {VALUE_CHAIN_KEYS.map((key, column) =>
                      key === 'value_chain_stage' ?
                        <TableCell key={key} className={CELL}>
                          <NativeSelect
                            id={`${idBase}-stage-${index}`}
                            aria-label={words.cell(n, words.columns[column]!)}
                            aria-invalid={bad || undefined}
                            disabled={disabled}
                            value={row.value_chain_stage}
                            onChange={(event) =>
                              setCell(index, {
                                value_chain_stage: event.target.value as
                                  ValueChainStage | '',
                              })
                            }
                            className={cn(
                              'w-full min-w-0',
                              bad && '[&_select]:border-support-error',
                            )}
                          >
                            <option value="">{words.choose}</option>
                            {VALUE_CHAIN_STAGES.map((stage, at) => (
                              <option key={stage} value={stage}>
                                {words.stages[at]}
                              </option>
                            ))}
                          </NativeSelect>
                        </TableCell>
                      : <TableCell key={key} className={CELL}>
                          <Input
                            aria-label={words.cell(n, words.columns[column]!)}
                            value={row[key]}
                            maxLength={VALUE_CHAIN_MAX_CHARS[column]}
                            disabled={disabled}
                            onChange={(event) =>
                              setCell(index, { [key]: event.target.value })
                            }
                          />
                        </TableCell>,
                    )}
                    <TableCell className={cn(CELL, 'text-center')}>
                      <IconButton
                        size="md"
                        aria-label={words.removeRow(n)}
                        disabled={disabled}
                        onClick={() => removeRow(index)}
                      >
                        <CloseIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outlineGrey"
              size="sm"
              disabled={disabled || shown.length >= VALUE_CHAIN_MAX_ROWS}
              onClick={() => onRows([...shown, blankValueChainRow()])}
            >
              <PlusIcon aria-hidden />
              {words.addRow}
            </Button>
            {/* 판 「넣기 전 · [직접 입력]」 은 [행 추가]만 */}
            {rows.length > 0 && (
              <Button
                variant="outlineGrey"
                size="sm"
                disabled={disabled}
                onClick={clear}
              >
                {words.clear}
              </Button>
            )}
          </div>
          {rows.length === 0 && (
            <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
              {words.empty}
            </p>
          )}
        </>
      }
    </div>
  );
}

/** 파일 줄(판 e-file): 공용 FileDropzone 목록 한 줄(이름 · meta · 날짜 · 실패면 「넣지 못함」 — IRW6, sid:MARC-ISSUE-434).
 *  공용 li 에 testid 가 없어 바깥 div 에 단다. onRemove 가 있으면 hideDrop(드롭존 0 · [×] 하나 → onRemove — IRW7),
 *  없으면 readOnly(드롭존·[×] 0). 어느 쪽이든 guide 는 그려지지 않는다. */
function FileLine({
  item,
  meta,
  testId,
  onRemove,
}: {
  item: DraggableInputItem;
  meta?: string;
  testId: string;
  onRemove?: () => void;
}) {
  return (
    <div data-testid={testId}>
      <FileDropzone
        readOnly={onRemove === undefined}
        hideDrop
        itemList={[item]}
        onChangeItemList={(next) => {
          if (next.length === 0) onRemove?.();
        }}
        guide={words.dropTitle}
        text={{ uploadFailed: words.failed, removeFile: words.removeFile }}
        itemMeta={() =>
          meta === undefined ? null : (
            <span
              data-testid="file-meta"
              className="shrink-0 text-style-pre-caption-02 text-text-tertiary"
            >
              {meta}
            </span>
          )
        }
      />
    </div>
  );
}
