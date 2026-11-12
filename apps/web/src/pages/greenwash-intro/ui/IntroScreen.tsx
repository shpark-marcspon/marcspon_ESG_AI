// GW-00 소개(밴드 FW1b ③). 시안 GW-00_r1(캔버스 v64)의 구성:
//   제목 줄 → 소개 카드(설명 두 줄 · 등급 설명 표) → 점검 과정 카드(3단계 띠 · 시작 안내 — 시안 댓글, sid:MARC-ENT-603) → PDF 안내 PageInfo → 오른쪽 아래 [시작하기].
// 등급 설명 표는 RiskBadge + FK2 DataTable(정렬 없음). 열 너비 120 / 나머지 / 420(디자인 대조 물음 10, 밴드 FW2 ②). 글은 문구 표 GW_TEXT.intro.
// 3단계 띠(밴드 FW2 ⓪, 디자인 대조 고칠 것 5, 시안 .g-stepband): 칸 바탕 없음, 위 4px 주황 선·아래 1px 선, 「Step n」 14 Bold primary,
//   이름 16 Bold 주황(text-brand), 설명 14 tertiary, 칸 사이 28 동그라미(1px 선) 꺾쇠. 목록 이름은 제목 「점검 과정」(aria-labelledby).
// [시작하기]는 md 알약(쪽 끝 버튼은 모두 md, 디자인 대조 고칠 것 6).
import { useId } from 'react';

import { ChevronRightIcon } from '@marcspon/common/generated/icons/MyIcons';

import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  RISK_LEVELS,
  RiskBadge,
} from '../../../entities/greenwash/ui/index.ts';
import type { RiskLevel } from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';

const words = GW_TEXT.intro;

interface LevelRow {
  level: RiskLevel;
  meaning: string;
  example: string;
}

const ROWS: LevelRow[] = RISK_LEVELS.map((level) => ({
  level,
  ...words.levels[level],
}));

const COLUMNS: DataTableColumnDef<LevelRow>[] = [
  {
    id: 'level',
    header: words.columns.level,
    enableSorting: false,
    meta: { width: 120 },
    cell: ({ row }) => <RiskBadge level={row.original.level} />,
  },
  {
    id: 'meaning',
    accessorKey: 'meaning',
    header: words.columns.meaning,
    enableSorting: false,
  },
  {
    id: 'example',
    accessorKey: 'example',
    header: words.columns.example,
    enableSorting: false,
    meta: { width: 420 },
    cell: ({ row }) => (
      <span className="text-text-tertiary">{row.original.example}</span>
    ),
  },
];

export interface IntroScreenProps {
  onStart(): void;
  /** 거짓이면 [시작하기]를 숨긴다(로그인하지 않은 세션 — 운영 관리자도 고객사 사용자와 같이 쓴다, sid:MARC-ENT-409). 기본 참. */
  canWrite?: boolean;
}

export function IntroScreen({ onStart, canWrite = true }: IntroScreenProps) {
  const processId = useId();
  const table = useDataTable({
    data: ROWS,
    columns: COLUMNS,
    getRowId: (row) => row.level,
  });
  return (
    <div data-screen="intro" className="flex flex-col gap-6">
      <PageTitle title={words.title} />

      <Card className="flex flex-col gap-4">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.aboutHeading}
        </h3>
        <p className="m-0 text-style-pre-body-03 text-text-secondary">
          {words.about[0]}
          <br />
          {words.about[1]}
        </p>
        {/* 등급 설명 줄: 줄 높이 56 에 위아래 8 을 더한다(시안 .g-desc td — height table-row + padding 8px 16px, content-box 라 73. GW3R2 SC2).
            공용 DataTable 을 고치지 않고 칸 자손으로 덮는다 */}
        <DataTable
          table={table}
          aria-label={words.tableLabel}
          className="[&_td]:box-content [&_td]:py-2"
        />
      </Card>

      <Card className="flex flex-col gap-5">
        <h3
          id={processId}
          className="m-0 text-style-pre-heading-02 text-text-primary"
        >
          {words.processHeading}
        </h3>
        <ol
          aria-labelledby={processId}
          data-testid="process-band"
          className="m-0 grid list-none grid-cols-3 border-0 border-b border-t-4 border-solid border-b-border-tertiary border-t-border-brand p-0"
        >
          {words.process.map((step, index) => (
            <li
              key={step.step}
              className="relative box-border flex flex-col gap-1 px-6 pb-6 pt-5"
            >
              <b className="text-style-pre-body-04 text-text-primary">
                {step.step}
              </b>
              <strong className="text-style-pre-body-01 text-text-brand">
                {step.name}
              </strong>
              <span className="text-style-pre-body-06 text-text-tertiary">
                {step.body}
              </span>
              {index < words.process.length - 1 && (
                <span
                  aria-hidden
                  className="absolute -right-3.5 top-5 z-10 box-border flex size-7 items-center justify-center rounded-full border border-solid border-border-tertiary bg-background-primary text-text-tertiary [&_svg]:size-3.5"
                >
                  <ChevronRightIcon />
                </span>
              )}
            </li>
          ))}
        </ol>
        {/* 시작 안내는 점검 과정 아래(시안 댓글 — sid:MARC-ENT-603) */}
        <p
          data-testid="start-hint"
          className="m-0 text-style-pre-body-03 text-text-secondary"
        >
          {words.startHint}
        </p>
      </Card>

      <PageInfo icon={<PageInfoIcon />} data-testid="pdf-info">
        {words.pdfInfo}
      </PageInfo>

      {canWrite && (
        <div className="flex justify-end">
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onStart}
          >
            {words.start}
          </Button>
        </div>
      )}
    </div>
  );
}
