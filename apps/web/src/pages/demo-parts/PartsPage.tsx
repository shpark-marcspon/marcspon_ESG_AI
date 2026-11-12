// 다시 만든 부품을 늘어놓아 보는 시험 화면(/dev/parts). 밴드 FK2.
// 부품마다 절 하나(data-part="<부품>"). e2e/parts.spec.ts 가 이 화면을 열어 실제 크기·색을 잰다.
// 부품은 shared/ui/<부품>/index.ts 로만 가져온다(app/guards/layers.test.ts 가 지킨다).
import { useState } from 'react';
import type { ReactNode } from 'react';

import {
  ChartSquareIcon,
  DashboardIcon,
  FileCheckIcon,
  FolderPlusIcon,
  GlobeIcon,
  InventoryIcon,
  SearchCheckIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import {
  COMPARE_KINDS,
  CompareBadge,
  ConfirmReviewDialog,
  ExcludeReasonDialog,
  LockBanner,
  REVIEW_VALUES,
  RISK_LEVELS,
  ReviewChoice,
  ReviewMark,
  RiskBadge,
  RunStatusBadge,
  StepFlow,
  VersionFlowStrip,
} from '../../entities/greenwash/ui/index.ts';
import type {
  ExcludeReasonValue,
  ReviewValue,
  RunStatus,
} from '../../entities/greenwash/ui/index.ts';
import { AppShell } from '../../shared/ui/app-shell/index.ts';
import type { AppShellMenuItem } from '../../shared/ui/app-shell/index.ts';
import {
  BUTTON_SHAPES,
  BUTTON_SIZES,
  BUTTON_VARIANTS,
  Button,
  IconButton,
} from '../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../shared/ui/card/index.ts';
import { DataTable, useDataTable } from '../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../shared/ui/data-table/index.ts';
import {
  DIALOG_SIZES,
  Dialog,
  DialogBody,
  DialogClose,
  DialogCloseIconButton,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../../shared/ui/dialog/index.ts';
import { DownloadButton } from '../../shared/ui/download-button/index.ts';
import { Empty } from '../../shared/ui/empty/index.ts';
import { FileDropzone } from '../../shared/ui/file-dropzone/index.ts';
import type { DraggableInputItem } from '../../shared/ui/file-dropzone/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_BODY_CLASS,
  FORM_VALUE_CLASS,
} from '../../shared/ui/form-rows/index.ts';
import { LoadSkeleton } from '../../shared/ui/load-skeleton/index.ts';
import {
  PAGE_INFO_TONES,
  PageInfo,
  PageInfoIcon,
} from '../../shared/ui/page-info/index.ts';
import { SearchField } from '../../shared/ui/search-field/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../shared/ui/tabs/index.ts';

function Section({
  part,
  title,
  children,
}: {
  part: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section
      data-part={part}
      aria-labelledby={`part-${part}`}
      className="flex flex-col gap-4 border-b border-border-tertiary py-8"
    >
      <h2
        id={`part-${part}`}
        className="text-style-pre-body-01 text-text-primary"
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

/** 견본 내려받기: 저장소가 없어 늘 거절한다(실패 글 줄을 본다). */
const failLoad = () => Promise.reject(new Error('견본'));

function ButtonSection() {
  return (
    <Section part="button" title="버튼">
      <table className="border-separate border-spacing-2">
        <thead>
          <tr>
            <th className="text-left text-style-pre-caption-02 text-text-tertiary">
              변형 / 꼴
            </th>
            {BUTTON_SIZES.map((size) => (
              <th
                key={size}
                className="text-left text-style-pre-caption-02 text-text-tertiary"
              >
                {size}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {BUTTON_VARIANTS.flatMap((variant) =>
            BUTTON_SHAPES.map((shape) => (
              <tr key={`${variant}-${shape}`}>
                <td className="text-style-pre-caption-02 text-text-tertiary">
                  {variant} / {shape}
                </td>
                {BUTTON_SIZES.map((size) => (
                  <td key={size}>
                    <Button
                      variant={variant}
                      shape={shape}
                      size={size}
                      data-testid={`button-${variant}-${shape}-${size}`}
                    >
                      버튼
                    </Button>
                  </td>
                ))}
              </tr>
            )),
          )}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="solidBlack" shape="round" disabled>
          꺼짐
        </Button>
        <Button
          variant="outlineGrey"
          leftIcon={<FolderPlusIcon />}
          data-testid="button-icon"
        >
          아이콘 왼쪽
        </Button>
        <Button
          variant="outlineBlack"
          shape="round"
          rightIcon={<FolderPlusIcon />}
        >
          아이콘 오른쪽
        </Button>
        <Button variant="solidOrange" loading data-testid="button-loading">
          불러오는 중
        </Button>
        <Button variant="text" asChild>
          <a href="#parts">링크 꼴</a>
        </Button>
        <IconButton aria-label="폴더 더하기" data-testid="icon-button-md">
          <FolderPlusIcon />
        </IconButton>
        <IconButton aria-label="폴더 더하기 작게" size="sm">
          <FolderPlusIcon />
        </IconButton>
      </div>
      {/* 내려받기 단추 견본(sid:MARC-ISSUE-363): 기본 · solidBlack · square sm · outlineGrey round sm(밴드 WS2, sid:MARC-ISSUE-371). 받기는 늘 실패(저장소 없음). */}
      <div className="flex flex-wrap items-center gap-3">
        <DownloadButton
          label="내려받기"
          failedText="받지 못했어요."
          load={failLoad}
          testId="download-default"
        />
        <DownloadButton
          label="모두 받기"
          failedText="받지 못했어요."
          load={failLoad}
          variant="solidBlack"
          testId="download-solid-black"
        />
        <DownloadButton
          label="양식"
          failedText="받지 못했어요."
          load={failLoad}
          shape="square"
          size="sm"
          testId="download-square-sm"
        />
        <DownloadButton
          label="결과 받기"
          failedText="받지 못했어요."
          load={failLoad}
          variant="outlineGrey"
          shape="round"
          size="sm"
          testId="download-round-sm"
        />
      </div>
    </Section>
  );
}

function EmptySection() {
  return (
    <Section part="empty" title="빈 목록">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-component border border-border-tertiary">
          <Empty
            data-testid="empty-with-action"
            title="등록된 정보가 없어요"
            description="자료를 올리면 여기에 보여요"
            action={
              <Button variant="solidGrey" shape="round" size="md">
                자료 올리기
              </Button>
            }
          />
        </div>
        <div className="rounded-component border border-border-tertiary">
          <Empty data-testid="empty-plain" title="검색된 정보가 없어요" />
        </div>
      </div>
    </Section>
  );
}

function DialogSection() {
  return (
    <Section part="dialog" title="모달">
      <div className="flex flex-wrap gap-3">
        {DIALOG_SIZES.map((size) => (
          <Dialog key={size}>
            <DialogTrigger asChild>
              <Button variant="outlineGrey" data-testid={`dialog-open-${size}`}>
                모달 {size} 열기
              </Button>
            </DialogTrigger>
            <DialogContent size={size} data-testid={`dialog-${size}`}>
              <DialogHeader>
                <DialogTitle data-testid={`dialog-title-${size}`}>
                  모달 {size}
                </DialogTitle>
              </DialogHeader>
              <DialogCloseIconButton aria-label="닫기" />
              <DialogDescription className="text-style-pre-body-06 text-text-tertiary">
                크기 {size} 의 모달이에요
              </DialogDescription>
              <DialogBody>
                {size === 'lg' ?
                  Array.from({ length: 40 }, (_, index) => (
                    <p key={index}>
                      긴 본문 {index + 1} 줄. 모달 안에서 스크롤돼요.
                    </p>
                  ))
                : <p>짧은 본문이에요.</p>}
              </DialogBody>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outlineBlack" shape="round" size="md">
                    취소
                  </Button>
                </DialogClose>
                <DialogClose asChild>
                  <Button variant="solidBlack" shape="round" size="md">
                    확인
                  </Button>
                </DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        ))}
      </div>
    </Section>
  );
}

interface Claim {
  id: string;
  page: string;
  sentence: string;
  score: number | null;
}
/** 지어낸 예시 줄. 실제 보고서의 글이 아니다. */
const CLAIMS: Claim[] = [
  {
    id: 'c1',
    page: '12',
    sentence: '우리는 친환경 소재만 씁니다',
    score: 0.82,
  },
  { id: 'c2', page: '3', sentence: '탄소 배출을 크게 줄였습니다', score: 0.47 },
  {
    id: 'c3',
    page: '27',
    sentence: '재생 에너지 전환을 검토합니다',
    score: null,
  },
];
const CLAIM_COLUMNS: DataTableColumnDef<Claim>[] = [
  { id: 'sentence', accessorKey: 'sentence', header: '문장' },
  {
    id: 'page',
    accessorFn: (row) => Number(row.page),
    header: '페이지',
    // 로딩 줄 막대 폭(밴드 LD1, 6c 쪽 수 24~32). 문장·점수는 기본 긴 글.
    // 열 폭(밴드 DT1, layout fixed): 칸 내용의 가장 넓은 폭(max-content — 머리 글·정렬 표시 포함, 1280×900 에서 잼, 올림) + 좌우 32. 문장은 폭 없음(남은 폭).
    meta: { align: 'right', skeleton: [24, 32], width: 86 },
  },
  {
    id: 'score',
    accessorFn: (row) => row.score ?? undefined,
    header: '점수',
    sortUndefined: 'last',
    cell: ({ row }) => row.original.score?.toFixed(2) ?? '-',
    meta: { align: 'right', width: 74 },
  },
  {
    id: 'action',
    header: '보기',
    enableSorting: false,
    // 표 안 행 버튼은 Outline Grey 알약 sm 28(FG5 [구조], 밴드 FW1 ⓪).
    cell: () => (
      <Button variant="outlineGrey" shape="round" size="sm">
        열기
      </Button>
    ),
    meta: { align: 'center', skeleton: [72, 88], width: 88 },
  },
];

function TableExample({
  testId,
  data,
  loading,
  clickable,
}: {
  testId: string;
  data: Claim[];
  loading?: boolean;
  clickable?: boolean;
}) {
  const [clicked, setClicked] = useState<string | null>(null);
  const table = useDataTable({
    data,
    columns: CLAIM_COLUMNS,
    getRowId: (row) => row.id,
  });
  return (
    <div data-testid={testId} className="flex flex-col gap-2">
      <DataTable
        table={table}
        aria-label={testId}
        layout="fixed"
        loading={loading}
        onClickRow={clickable ? (row) => setClicked(row.id) : undefined}
        empty={<Empty title="검색된 문장이 없어요" />}
      />
      {clickable && (
        <p
          data-testid={`${testId}-clicked`}
          className="text-style-pre-caption-02 text-text-tertiary"
        >
          누른 줄: {clicked ?? '없음'}
        </p>
      )}
    </div>
  );
}

/** 묶음 줄 견본(밴드 DT1 ③, sid:MARC-ISSUE-384 — DV3 결과 표 꼴): 지어낸 검사 둘 × 해 둘~셋. 앞 세 열은 묶음 첫 줄에서 rowSpan. */
interface SpanLine {
  id: string;
  group: string;
  rule: string;
  items: string;
  size: number;
  first: boolean;
  year: string;
  verdict: string;
  formula: string;
}
const SPAN_GROUPS = [
  {
    group: '1',
    rule: '합계 맞음',
    items: '전기 + 연료 = 합계',
    years: [
      ['2023', '맞음', '120 + 30 = 150'],
      ['2024', '다름', '118 + 35 ≠ 150'],
      ['2025', '맞음', '110 + 40 = 150'],
    ],
  },
  {
    group: '2',
    rule: '전년 대비',
    items: '용수 사용량',
    years: [
      ['2024', '맞음', '(52 − 50) / 50 = 4%'],
      ['2025', '맞음', '(55 − 52) / 52 = 5.8%'],
    ],
  },
] as const;
/** 지어낸 예시 줄. 실제 보고서의 값이 아니다. */
const SPAN_LINES: SpanLine[] = SPAN_GROUPS.flatMap((group) =>
  group.years.map(([year, verdict, formula], index) => ({
    id: `${group.group}-${year}`,
    group: group.group,
    rule: group.rule,
    items: group.items,
    size: group.years.length,
    first: index === 0,
    year,
    verdict,
    formula,
  })),
);
/** 묶음 열(묶음 첫 줄에서 size 만큼 rowSpan). */
const SPAN_GROUP_COLUMNS = new Set(['group', 'rule', 'items']);

function SpanExample() {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const toggle = (id: string) =>
    setOpen((now) => {
      const next = new Set(now);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const columns: DataTableColumnDef<SpanLine>[] = [
    {
      id: 'group',
      accessorKey: 'group',
      header: '순번',
      meta: { align: 'right', width: 72 },
    },
    { id: 'rule', accessorKey: 'rule', header: '규칙', meta: { width: 120 } },
    { id: 'items', accessorKey: 'items', header: '항목' },
    { id: 'year', accessorKey: 'year', header: '해', meta: { width: 80 } },
    {
      id: 'verdict',
      accessorKey: 'verdict',
      header: '판정',
      meta: { width: 88 },
    },
    {
      id: 'formula',
      header: '계산 식',
      cell: ({ row }) => (
        <Button
          variant="outlineGrey"
          shape="round"
          size="sm"
          aria-expanded={open.has(row.original.id)}
          onClick={() => toggle(row.original.id)}
        >
          {open.has(row.original.id) ? '식 닫기' : '식 보기'}
        </Button>
      ),
      meta: { align: 'right', width: 112 },
    },
  ];
  const table = useDataTable({
    data: SPAN_LINES,
    columns,
    getRowId: (row) => row.id,
    // rowSpan 표는 정렬을 끈다 — 표는 받은 차례대로 묶는다.
    enableSorting: false,
  });
  return (
    <div data-testid="table-span">
      <DataTable
        table={table}
        aria-label="table-span"
        layout="fixed"
        rowSpanOf={(line, columnId) =>
          !SPAN_GROUP_COLUMNS.has(columnId) ? undefined
          : line.first ? line.size
          : 0
        }
        renderExpanded={(line) =>
          open.has(line.id) ?
            <span data-testid="span-formula">{line.formula}</span>
          : null
        }
        rowAttrs={(line) => ({
          'data-testid': 'span-row',
          'data-group': line.group,
        })}
      />
    </div>
  );
}

function FormRowsSection() {
  return (
    <Section part="form-rows" title="양식 줄">
      {/* 밴드 DT1 ③: shared/ui/form-rows 의 클래스 상수(시안 .e-formrows). 라벨 160 · 줄 높이 64 이상. */}
      <div data-testid="form-rows" className={FORM_ROWS_CLASS}>
        <div className={FORM_ROW_CLASS}>
          <span className={FORM_LABEL_CLASS}>보고서</span>
          <div className={FORM_VALUE_CLASS}>
            <Button variant="outlineGrey" size="sm">
              파일 고르기
            </Button>
          </div>
        </div>
        <div className={FORM_ROW_CLASS}>
          <span className={FORM_LABEL_CLASS}>받는 것</span>
          <p className={FORM_VALUE_BODY_CLASS}>검증 결과 표와 계산 식</p>
        </div>
      </div>
    </Section>
  );
}

function TableSection() {
  return (
    <Section part="data-table" title="목록 표">
      <TableExample testId="table-main" data={CLAIMS} clickable />
      {/* 첫 불러오기(밴드 LD1): loading 은 날 값 — 머리줄 그대로, 몸은 자리 잡은 줄 5, 막대는 300ms 뒤. */}
      <TableExample testId="table-loading-rows" data={[]} loading />
      <TableExample testId="table-empty" data={[]} />
      {/* 묶음 줄(밴드 DT1 ③): 앞 세 열 rowSpan · [식 보기] 펼침 줄 · 줄마다 data-testid·data-group. */}
      <SpanExample />
    </Section>
  );
}

function DropzoneExample({
  testId,
  initial = [],
  isUploading,
}: {
  testId: string;
  initial?: DraggableInputItem[];
  isUploading?: boolean;
}) {
  const [items, setItems] = useState<DraggableInputItem[]>(initial);
  return (
    <div data-testid={testId}>
      <FileDropzone
        guide="파일을 끌어다 놓거나 눌러서 고르세요"
        formats="xlsx, pdf · 파일 하나 1MB 이하 · 3개까지"
        itemList={items}
        onChangeItemList={setItems}
        accept={['.xlsx', '.pdf']}
        maxMb={1}
        maxCount={3}
        isUploading={isUploading}
      />
    </div>
  );
}

/** 오류 칸(밴드 FZ1): 칸에 aria-invalid 를 달고 칸 아래 오류 글을 aria-describedby 로 잇는다. 테두리 꼴은 그대로. */
function DropzoneErrorExample() {
  const [items, setItems] = useState<DraggableInputItem[]>([]);
  return (
    <div data-testid="dropzone-invalid" className="flex flex-col gap-1.5">
      <FileDropzone
        guide="파일을 끌어다 놓거나 눌러서 고르세요"
        formats="xlsx · 파일 하나 1MB 이하"
        itemList={items}
        onChangeItemList={setItems}
        accept={['.xlsx']}
        maxMb={1}
        maxCount={1}
        invalid
        describedBy="dropzone-invalid-error"
      />
      <p
        id="dropzone-invalid-error"
        className="m-0 text-style-pre-caption-02 text-support-error"
      >
        파일을 하나 올려 주세요
      </p>
    </div>
  );
}

function DropzoneSection() {
  return (
    <Section part="file-dropzone" title="파일 드롭존">
      <div className="grid grid-cols-2 gap-6">
        <DropzoneExample testId="dropzone-empty" />
        <DropzoneExample
          testId="dropzone-files"
          initial={[
            { id: 'f1', name: '배출량_2025.xlsx', date: '2026-10-01' },
            {
              id: 'f2',
              name: '지속가능경영보고서_초안.pdf',
              date: '2026-10-02',
            },
          ]}
        />
        <DropzoneExample
          testId="dropzone-uploading"
          isUploading
          initial={[
            {
              id: 'u1',
              name: '올리는_중.xlsx',
              date: '2026-10-15',
              status: 'uploading',
            },
          ]}
        />
        <DropzoneExample
          testId="dropzone-failed"
          initial={[
            {
              id: 'x1',
              name: '실패한_파일.pdf',
              date: '2026-10-15',
              status: 'failed',
            },
          ]}
        />
        <DropzoneErrorExample />
      </div>
    </Section>
  );
}

// ── 밴드 FW1 ①: 화면 뼈대와 기본 표시 부품 ──

/** 지어낸 메뉴. 모듈 이름은 시안의 자리 표시를 따랐다. */
const MENU: AppShellMenuItem[] = [
  { id: 'dashboard', label: '대시보드', icon: <DashboardIcon /> },
  { id: 'ghg', label: '온실가스', icon: <InventoryIcon />, disabled: true },
  { id: 'greenwash', label: '그린워싱 점검', icon: <SearchCheckIcon /> },
  {
    id: 'materiality',
    label: '중대성평가',
    icon: <ChartSquareIcon />,
    // 하위 줄 견본(밴드 LN1): 늘 펼침, 글만, 꺼진 줄은 흐림.
    childrenLabel: '중대성평가 하위',
    children: [
      { id: 'materiality-iro', label: 'IRO 목록' },
      { id: 'materiality-off', label: '준비 중', disabled: true },
    ],
  },
  { id: 'validation', label: '데이터 검증', icon: <FileCheckIcon /> },
  { id: 'translation', label: '영문번역', icon: <GlobeIcon /> },
];

function ShellSection() {
  const [current, setCurrent] = useState('greenwash');
  return (
    <Section part="app-shell" title="화면 뼈대 · 카드 · 제목 줄 · 단계 띠">
      <div
        data-testid="app-shell-demo"
        className="h-[560px] overflow-hidden rounded-component border border-solid border-border-tertiary"
      >
        <AppShell
          menu={MENU}
          currentId={current}
          onSelect={setCurrent}
          menuLabel="모듈 메뉴"
          title="그린워싱 점검"
          logo="로고 자리"
          headerRight={
            <span className="text-style-pre-body-04 text-text-secondary">
              담당자님 안녕하세요
            </span>
          }
        >
          <PageTitle
            title="새 점검"
            description="PDF 를 올리고 점검할 페이지를 정해요"
            actions={
              <Button variant="outlineGrey" shape="round" size="md">
                목록으로
              </Button>
            }
          />
          <StepFlow current={1} />
          <Card data-testid="card-demo">
            <p className="m-0 text-style-pre-body-06 text-text-secondary">
              흰 카드(모서리 16, 안쪽 32)예요.
            </p>
          </Card>
        </AppShell>
      </div>
      <div className="flex flex-col gap-2" data-testid="step-flow-all">
        {[1, 2, 3].map((step) => (
          <StepFlow key={step} current={step} label={`점검 단계 ${step}`} />
        ))}
      </div>
    </Section>
  );
}

function LoadSkeletonSection() {
  return (
    <Section part="load-skeleton" title="불러오는 중 자리">
      {/* 결과 화면 머리(밴드 LD1 ④): 데이터에서 오는 제목·설명만 막대. */}
      <div data-testid="page-title-pending">
        <PageTitle
          title="점검 결과"
          titlePending
          descriptionPending
          actions={
            <Button variant="outlineGrey" shape="round" size="md">
              목록으로
            </Button>
          }
        />
      </div>
      <div data-testid="page-title-ready">
        <PageTitle
          title="2025 지속가능경영보고서.pdf"
          description="총 42페이지 · 점검 문장 18개"
          actions={
            <Button variant="outlineGrey" shape="round" size="md">
              목록으로
            </Button>
          }
        />
      </div>
      <div data-testid="load-skeleton-card">
        <LoadSkeleton label="결과를 불러오는 중" />
      </div>
    </Section>
  );
}

function PageInfoSection() {
  const words = {
    default: '문서 속 이미지는 분석하지 않아요',
    important: '확정 전 결과예요. 엑셀에도 「확정 전 결과」라고 적혀요',
    error: '글자가 없는 PDF 는 점검할 수 없어요',
    caution: '몇 페이지를 못 읽어도 나머지 페이지는 계속 점검해요',
  } as const;
  return (
    <Section part="page-info" title="한 줄 안내">
      {PAGE_INFO_TONES.map((tone) => (
        <PageInfo
          key={tone}
          tone={tone}
          icon={<PageInfoIcon />}
          data-testid={`page-info-${tone}`}
        >
          {words[tone]}
        </PageInfo>
      ))}
    </Section>
  );
}

function TabsSearchSection() {
  const [query, setQuery] = useState('');
  return (
    <Section part="tabs-search" title="탭 · 검색 칸">
      <Tabs variant="box" defaultValue="mid">
        <TabsList aria-label="상자 탭" data-testid="tabs-box">
          <TabsTrigger value="all">전체</TabsTrigger>
          <TabsTrigger value="mid">검토</TabsTrigger>
          <TabsTrigger value="done">확정</TabsTrigger>
        </TabsList>
      </Tabs>
      <Tabs variant="line" defaultValue="all">
        <TabsList aria-label="줄 탭" data-testid="tabs-line">
          <TabsTrigger value="all">전체</TabsTrigger>
          <TabsTrigger value="ceo">인사말</TabsTrigger>
          <TabsTrigger value="story">본문</TabsTrigger>
        </TabsList>
      </Tabs>
      <SearchField
        aria-label="검색어"
        placeholder="문서 이름으로 찾기"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        data-testid="search-field"
        className="w-64"
      />
    </Section>
  );
}

const RUN_STATUSES: RunStatus[] = [
  { kind: 'analyzing', progress: 62 },
  { kind: 'failed' },
  { kind: 'pending' },
  { kind: 'reviewing', reviewed: 14, total: 22 },
  { kind: 'confirmed', by: '담당자 B', at: '10-06' },
];

function GreenwashBadgeSection() {
  return (
    <Section part="greenwash-badges" title="그린워싱 배지">
      <div className="flex flex-wrap items-center gap-3">
        {RISK_LEVELS.map((level) => (
          <RiskBadge key={level} level={level} data-testid={`risk-${level}`} />
        ))}
        {RISK_LEVELS.map((level) => (
          <RiskBadge key={`${level}-n`} level={level} count={9} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {RUN_STATUSES.map((status) => (
          <span key={status.kind} data-testid={`run-status-${status.kind}`}>
            <RunStatusBadge status={status} />
          </span>
        ))}
      </div>
    </Section>
  );
}

// ── 밴드 FW1 ②: 검토·확정·비교 표시 부품(모양만) ──

function ReviewSection() {
  const [choice, setChoice] = useState<ReviewValue>('unreviewed');
  const [excludeOpen, setExcludeOpen] = useState(false);
  const [excluded, setExcluded] = useState<ExcludeReasonValue | null>(null);
  const [confirmCount, setConfirmCount] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(0);
  return (
    <Section part="greenwash-review" title="그린워싱 검토 · 확정">
      <div className="flex flex-wrap items-center gap-3">
        {REVIEW_VALUES.map((value) => (
          <ReviewMark key={value} value={value} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <ReviewChoice value={choice} onChange={setChoice} />
        <span
          data-testid="review-choice-value"
          className="text-style-pre-caption-02 text-text-tertiary"
        >
          지금 값: {choice}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          data-testid="exclude-open"
          onClick={() => setExcludeOpen(true)}
        >
          제외 사유 모달 열기
        </Button>
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          data-testid="confirm-open-8"
          onClick={() => setConfirmCount(8)}
        >
          확정 모달 열기(미검토 8)
        </Button>
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          data-testid="confirm-open-0"
          onClick={() => setConfirmCount(0)}
        >
          확정 모달 열기(미검토 0)
        </Button>
        <span
          data-testid="review-result"
          className="text-style-pre-caption-02 text-text-tertiary"
        >
          제외:{' '}
          {excluded ? `${excluded.reason} / ${excluded.note || '-'}` : '없음'} ·
          확정 누름 {confirmed}번
        </span>
      </div>
      <ExcludeReasonDialog
        open={excludeOpen}
        onOpenChange={setExcludeOpen}
        quote="「온실가스 배출량을 크게 줄였습니다.」"
        quoteMeta="기후·환경 30페이지 · Mid"
        onSubmit={(value) => {
          setExcluded(value);
          setExcludeOpen(false);
        }}
      />
      <ConfirmReviewDialog
        open={confirmCount !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmCount(null);
        }}
        unreviewedCount={confirmCount ?? 0}
        onConfirm={() => {
          setConfirmed((count) => count + 1);
          setConfirmCount(null);
        }}
      />
      <LockBanner at="2026-10-16 10:20" by="담당자 A" />
    </Section>
  );
}

function CompareSection() {
  return (
    <Section part="greenwash-compare" title="그린워싱 수정본 비교">
      <VersionFlowStrip
        versions={[
          {
            id: 'v1',
            name: 'v1',
            meta: '2026-09-24 · 1회차',
            high: 9,
            mid: 10,
            badges: <RunStatusBadge status={{ kind: 'confirmed' }} />,
          },
          {
            id: 'v2',
            name: 'v2',
            meta: '2026-10-01 · 2회차 (마지막 실행)',
            high: 6,
            mid: 9,
            badges: <RunStatusBadge status={{ kind: 'pending' }} />,
          },
          {
            id: 'v3',
            name: 'v3',
            meta: '2026-10-08 · 1회차',
            high: 4,
            mid: 8,
            pick: 'base',
            badges: <RunStatusBadge status={{ kind: 'confirmed' }} />,
          },
          {
            id: 'v4',
            name: 'v4',
            meta: '2026-10-15 · 2회차',
            high: 3,
            mid: 7,
            pick: 'current',
            badges: (
              <RunStatusBadge
                status={{ kind: 'reviewing', reviewed: 14, total: 22 }}
              />
            ),
          },
        ]}
      />
      <div className="flex flex-wrap items-start gap-3">
        {COMPARE_KINDS.map((kind) => (
          <CompareBadge key={kind} kind={kind} />
        ))}
      </div>
    </Section>
  );
}

export function PartsPage() {
  return (
    <main id="parts" className="twp mx-auto max-w-[1200px] px-8 py-6">
      <h1 className="text-style-pre-body-01 text-text-primary">
        다시 만든 부품 (시험 화면)
      </h1>
      <ButtonSection />
      <EmptySection />
      <DialogSection />
      <TableSection />
      <FormRowsSection />
      <DropzoneSection />
      <ShellSection />
      <LoadSkeletonSection />
      <PageInfoSection />
      <TabsSearchSection />
      <GreenwashBadgeSection />
      <ReviewSection />
      <CompareSection />
    </main>
  );
}
