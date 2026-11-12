// S2 온실가스 데이터(밴드 W12-0b2 ③ 자리 → 밴드 W12-1a ③ 리스트 — 스펙 ① S2, 시안 28575:23233·28535:7000, sid:MARC-ENT-469 4).
//   고객사 사용자·운영 관리자(작업 회사) 같은 화면. 지역/시장기반·담당자·참고자료·Scope 3 탭은 1차 숨김(자리 0).
//   - 머리: 제목 「온실가스 데이터」(그 아래 prop tabs — 경로 컴포넌트가 넘긴 Scope 탭 줄, 밴드 S3W1 ③). 그 아래 한 줄에 연도 · 「인덱스 검색」 · 오른쪽 [인덱스 설정](→ S17 같은 연도, D10) — 저장 뒤면 그 앞에
//     「저장됐어요」(prop saved — S12-04 뒤 공용 토스트. 이 화면이 <Toaster> host, S3 상세 모달의 저장 토스트도 여기 뜬다).
//   - 연도 드롭다운(올해부터 다섯 — Q5). 바꾸면 onYear — 경로가 주소를 바꾸면 year 가 바뀌어 그 해 리스트(rows)를 새로 읽는다.
//   - 읽기는 입력 리스트(GET /scope12/rows). configured 거짓(그 해 숨기지 않은 고른 잎 0) → 빈 상태 두 줄(시안 원문)만 — 초기 세팅 창은
//     S12-02a 에서 걷음(sid:MARC-ENT-644). [인덱스 설정]이 묻지 않고 바로 onIndexSettings(year).
//   - configured → 배출량 현황 카드(EmissionCard — q 없는 마지막 응답 base 로) + 배출범위마다 표(InventoryTable — 지금 검색 결과 table 로).
//   - 검색(「인덱스 검색」)은 서버 q: 입력이 멈추고 300ms 뒤 한 번, 늦게 온 앞 검색 답은 버린다(번호 가드). 빈 글이면 표 = base.
//     0 건 → 「검색 결과가 없어요」. 422 fields.q → 검색 줄 아래 한 줄. 검색은 카드를 바꾸지 않는다(Q11).
//   - 첫 읽기 실패만 화면 자리 한 줄 + 다시 시도. 다시 읽기(연도 바꿈·검색) 실패는 한 줄 notice — 판은 그대로(sid:MARC-ISSUE-459).
//     늦게 온 앞 읽기(앞 해) 답은 버린다(S17 의 검증 B1 과 같은 번호 가드).
//   - 회사 거절 셋은 두 역할 글(첫 읽기 → 화면 자리, 다시 읽기 → 한 줄).
//   - 화면은 라우터·세션을 모른다(콜백 onYear·onIndexSettings, prop year·years·operator·saved).
//   - 일괄 업로드·다운로드(밴드 W12-5 ②③, e6 값 Q2): 표 카드 맨 위 오른쪽 줄의 단추 둘. 빈 해·검색 0 건에도 줄은 남고 빈 해는 끈다(눌러 봐야 404). 올린 뒤 연도 줄에 한 줄.
//   - sid:MARC-ISSUE-468(밴드 W12-1a ①): 연도는 공용 NativeSelect(D6) · [인덱스 설정]은 제목 줄이 아니라 연도 줄 오른쪽, 「저장됐어요」는 그 단추 앞(D10).
import { useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

import type {
  CompanyRefusal,
  EntryRowsRead,
  GhgEntryPort,
  GhgOrganizationPort,
  GhgPoolAdminPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { ENTRY_SEARCH_MAX } from '../../../entities/ghg/model/index.ts';
import type {
  EntryRows,
  EntryUploadResult,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { Empty } from '../../../shared/ui/empty/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  LoadSkeleton,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { SearchField } from '../../../shared/ui/search-field/index.ts';
import {
  Toaster,
  dismissToast,
  toast,
} from '../../../shared/ui/toast/index.ts';
import { EmissionCard } from './EmissionCard.tsx';
import { EntryDetailDialog } from './EntryDetailDialog.tsx';
import { EntryDownloadDialog } from './EntryDownloadDialog.tsx';
import { EntryUploadDialog } from './EntryUploadDialog.tsx';
import { InventoryTable } from './InventoryTable.tsx';

const words = GHG_TEXT.inventory;
const bulkWords = words.bulk;
/** [발주서 초안] 검색 입력이 멈춘 뒤 보내기까지. */
const SEARCH_DELAY_MS = 300;

export interface InventoryScreenProps {
  port: GhgEntryPort;
  /** 사업장 목록(양식 받기 ② — 밴드 W12-5 Q4). */
  organization: GhgOrganizationPort;
  /** 주소의 연도(경로가 years 안으로 거른 값). */
  year: number;
  /** 고를 수 있는 연도(올해부터 내림 — model yearsOf. 처음 해는 전년도 — defaultYearOf). */
  years: readonly number[];
  /** 운영 관리자 세션이면 회사 거절 글이 companyOperator. */
  operator?: boolean;
  /** 풀 실어댑터(운영 관리자만 — S3 상세 S8 [배출계수 수정], 밴드 W12-3 Q5). 고객사는 null. */
  pool?: GhgPoolAdminPort | null;
  /** S17 저장 뒤 들어왔으면 머리 옆 「저장됐어요」. */
  saved?: boolean;
  /** 제목 아래 Scope 탭 줄(경로 컴포넌트가 넘긴다 — 밴드 S3W1 ③). 안 넘기면 그리지 않는다. */
  tabs?: ReactNode;
  /** 연도 바꿈. */
  onYear(year: number): void;
  /** [인덱스 설정] → S17(같은 연도 — S12-02a 뒤 묻지 않고 바로). */
  onIndexSettings(year: number): void;
  /** S3 상세의 S12-05 안내 [조직구조로](안 넘기면 단추 0). */
  onOrganization?: () => void;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
}

type Loaded =
  | { state: 'loading' }
  | { state: 'failed' }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'ready'; base: EntryRows };

type Notice = 'reloadFailed' | { company: CompanyRefusal } | null;

/** 화면 + 토스트 host(S12-04 — 갈래(읽는 중·회사 거절·판)가 바뀌어도 host 는 늘 붙어 있다). */
export function InventoryScreen(props: InventoryScreenProps) {
  return (
    <>
      <InventoryBody {...props} />
      <Toaster />
    </>
  );
}

function InventoryBody({
  port,
  organization,
  year,
  years,
  operator = false,
  pool = null,
  saved = false,
  tabs,
  onYear,
  onIndexSettings,
  onOrganization,
  save,
}: InventoryScreenProps) {
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });
  const [notice, setNotice] = useState<Notice>(null);
  /** S3 상세를 연 잎(화면 안 상태 — 밴드 W12-1b Q3). */
  const [detail, setDetail] = useState<string | null>(null);
  const [q, setQ] = useState('');
  /** 지금 검색어의 결과(null = 검색 없음 — 표는 base). */
  const [table, setTable] = useState<EntryRows | null>(null);
  const [searchInvalid, setSearchInvalid] = useState(false);
  /** 연 창(S4·S5). */
  const [bulk, setBulk] = useState<'upload' | 'download' | null>(null);
  /** 값이 든 올리기의 답(연도 줄 한 줄 — 다음 연도 바꿈·다음 올리기에 걷는다). */
  const [uploaded, setUploaded] = useState<EntryUploadResult | null>(null);
  const uploadRef = useRef<HTMLButtonElement>(null);
  const downloadRef = useRef<HTMLButtonElement>(null);
  const searchErrorId = useId();
  const retryFocus = useRetryFocus<HTMLHeadingElement>(
    loaded.state === 'loading' ? 'loading'
    : loaded.state === 'failed' ? 'failed'
    : 'ready',
  );
  const hasList = useRef(false);
  /** 마지막으로 부른 base 읽기(연도)의 번호 — 늦게 온 앞 해 답은 버린다. */
  const asked = useRef(0);
  /** 마지막으로 부른 검색의 번호 — 늦게 온 앞 검색어·앞 해 검색 답은 버린다. base 번호와 나눈다(검색이 연도 읽기를 무효로 만들지 않게 — 검증 B1). */
  const searchAsked = useRef(0);
  const query = useRef('');
  query.current = q;

  /** 다시 읽기 실패 한 줄(판은 그대로). */
  const failNotice = (out: EntryRowsRead) =>
    setNotice(
      out.kind === 'refused' ? { company: out.company } : 'reloadFailed',
    );

  /** 지금 검색어로 표만 읽는다(빈 글이면 표 = base). */
  const search = async (year: number, text: string, ticket: number) => {
    if (text.trim() === '') {
      setTable(null);
      setSearchInvalid(false);
      return;
    }
    const out = await port.rows(year, text);
    if (ticket !== searchAsked.current) return;
    if (out.kind === 'ok') {
      setTable(out.value);
      setSearchInvalid(false);
      setNotice(null);
    } else if (out.kind === 'rejected' && 'q' in out.fields)
      setSearchInvalid(true);
    else failNotice(out.kind === 'rejected' ? { kind: 'failed' } : out);
  };

  /** 그 해 리스트를 읽는다(q 없는 base — 카드·configured, 검색어가 있으면 이어 표). 판이 없을 때(첫 읽기)만 실패가 화면 자리. */
  const load = async (): Promise<boolean> => {
    const ticket = ++asked.current;
    // 연도가 바뀌면 앞 해로 나간 검색 답도 버린다.
    searchAsked.current += 1;
    if (!hasList.current) setLoaded({ state: 'loading' });
    const out = await port.rows(year);
    if (ticket !== asked.current) return false;
    if (out.kind === 'ok') {
      hasList.current = true;
      setLoaded({ state: 'ready', base: out.value });
      setNotice(null);
      // 설정 안 된 해는 검색 칸이 없다 — 남은 검색어로 읽지 않는다.
      if (out.value.configured)
        await search(year, query.current, ++searchAsked.current);
      else setTable(null);
      return true;
    }
    if (!hasList.current)
      setLoaded(
        out.kind === 'refused' ?
          { state: 'refused', company: out.company }
        : { state: 'failed' },
      );
    else failNotice(out);
    return false;
  };
  useEffect(() => {
    setUploaded(null);
    void load();
    // load 는 port·year 로만 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, year]);

  /** S12-04: S17 저장 뒤 들어오면 공용 토스트 「저장됐어요」(경로 state ghgSaved 흐름 그대로 — 발주서 Q13).
   *  saved 가 걷히면(연도 바꿈 — R7) 그 토스트도 걷는다. */
  const savedToast = useRef<number | null>(null);
  useEffect(() => {
    if (saved) savedToast.current = toast({ message: words.saved });
    else if (savedToast.current !== null) {
      dismissToast(savedToast.current);
      savedToast.current = null;
    }
  }, [saved]);

  /** 검색어가 바뀌면 멈춘 뒤 한 번(첫 그림·연도 바꿈은 load 가 이어 읽는다). */
  const typed = useRef(false);
  useEffect(() => {
    if (!typed.current) return;
    const ticket = ++searchAsked.current;
    if (q.trim() === '') {
      void search(year, q, ticket);
      return;
    }
    const timer = setTimeout(
      () => void search(year, q, ticket),
      SEARCH_DELAY_MS,
    );
    return () => clearTimeout(timer);
    // search 는 port·year 로만 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const head = (
    <>
      <PageTitle title={words.title} headingRef={retryFocus.doneRef} />
      {tabs}
    </>
  );
  /** 연도 줄 오른쪽(D10): 「저장됐어요」 + [인덱스 설정]. */
  const actions = (
    <div className="ml-auto flex items-center gap-2.5">
      {uploaded !== null && (
        <p
          role="status"
          data-testid="inventory-uploaded"
          className="m-0 text-style-pre-body-05 text-support-success"
        >
          {bulkWords.filled(uploaded.filled)}
          {uploaded.unresolved > 0 &&
            ` ${bulkWords.unresolved(uploaded.unresolved)}`}
        </p>
      )}
      <Button
        variant="solidBlack"
        shape="round"
        size="md"
        onClick={() => onIndexSettings(year)}
      >
        {words.indexSettings}
      </Button>
    </div>
  );

  if (loaded.state === 'refused')
    return (
      <div data-screen="ghg-inventory" className="flex flex-col gap-6">
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
      <div data-screen="ghg-inventory" className="flex flex-col gap-6">
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

  // 검색 결과는 base 와 같은 해일 때만 — 연도를 바꾼 뒤 검색을 다시 읽기 전(또는 실패)에 앞 해 표가 남지 않게(가지 리뷰 B1).
  const shown =
    table !== null && table.year === loaded.base.year ? table : loaded.base;
  const noticeText =
    notice === null ? null
    : typeof notice === 'object' ? companyText[notice.company]
    : words[notice];

  /** 표 카드 맨 위 오른쪽 줄(e6 Q2). 빈 해는 끈다 — 검색 결과가 아니라 base 로 본다. */
  const bulkLine = (
    <div data-testid="inventory-bulk" className="flex justify-end gap-2">
      <Button
        ref={uploadRef}
        variant="solidGrey"
        size="sm"
        disabled={!loaded.base.configured}
        onClick={() => {
          setUploaded(null);
          setBulk('upload');
        }}
      >
        {bulkWords.uploadOpen}
      </Button>
      <Button
        ref={downloadRef}
        variant="solidGrey"
        size="sm"
        disabled={!loaded.base.configured}
        onClick={() => setBulk('download')}
      >
        {bulkWords.downloadOpen}
      </Button>
    </div>
  );

  return (
    <div data-screen="ghg-inventory" className="flex flex-col gap-6">
      {head}
      <div
        data-testid="inventory-filters"
        className="flex flex-wrap items-center gap-2"
      >
        <NativeSelect
          aria-label={words.yearLabel}
          value={year}
          onChange={(event) => {
            const next = years.find((y) => `${y}` === event.target.value);
            if (next !== undefined) onYear(next);
          }}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              {words.yearOption(y)}
            </option>
          ))}
        </NativeSelect>
        {loaded.base.configured && (
          <div className="flex flex-col gap-1">
            <SearchField
              aria-label={words.searchLabel}
              placeholder={words.searchLabel}
              maxLength={ENTRY_SEARCH_MAX}
              aria-invalid={searchInvalid || undefined}
              aria-describedby={searchInvalid ? searchErrorId : undefined}
              className="w-60"
              value={q}
              onChange={(event) => {
                typed.current = true;
                setQ(event.target.value);
              }}
            />
            {searchInvalid && (
              <p
                id={searchErrorId}
                data-testid="inventory-search-error"
                className="m-0 text-style-pre-caption-03 text-support-error-accent"
              >
                {words.searchInvalid}
              </p>
            )}
          </div>
        )}
        <p
          role="alert"
          data-testid="inventory-notice"
          className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
        >
          {noticeText && (
            <>
              <CircleWarningIcon aria-hidden />
              {noticeText}
            </>
          )}
        </p>
        {actions}
      </div>
      {!loaded.base.configured ?
        <Card className="flex flex-col gap-4">
          {bulkLine}
          <Empty
            data-testid="inventory-empty"
            title={words.emptyTitle}
            description={words.emptyBody}
          />
        </Card>
      : <>
          <EmissionCard rows={loaded.base} />
          <Card data-testid="inventory-tables" className="flex flex-col gap-4">
            {bulkLine}
            <div className="flex flex-col gap-8">
              {shown.scopes.length === 0 ?
                <Empty
                  data-testid="inventory-search-empty"
                  title={words.searchEmpty}
                />
              : shown.scopes.map((scope) => (
                  <InventoryTable
                    key={scope.scopeId}
                    scope={scope}
                    years={shown.years}
                    decimals={shown.decimals}
                    unit={shown.unit}
                    onOpen={setDetail}
                  />
                ))
              }
            </div>
          </Card>
        </>
      }
      {detail !== null && (
        <EntryDetailDialog
          key={`${year}:${detail}`}
          port={port}
          year={year}
          nodeId={detail}
          operator={operator}
          pool={pool}
          onClose={(wrote) => {
            setDetail(null);
            if (wrote) void load();
          }}
          onOrganization={onOrganization}
        />
      )}
      {bulk === 'upload' && (
        <EntryUploadDialog
          port={port}
          organization={organization}
          year={year}
          companyText={companyText}
          returnFocus={() => uploadRef.current}
          onWrote={load}
          onUploaded={(result) => {
            setBulk(null);
            setUploaded(result);
            void load();
          }}
          onClose={() => setBulk(null)}
          save={save}
        />
      )}
      {bulk === 'download' && (
        <EntryDownloadDialog
          port={port}
          year={year}
          companyText={companyText}
          returnFocus={() => downloadRef.current}
          onClose={() => setBulk(null)}
          save={save}
        />
      )}
    </div>
  );
}
