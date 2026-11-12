// DV-00 검증 안내(밴드 DV2a ②, 시안 v148 DV-00_r1 — 그린워싱 GW-00 IntroScreen 꼴을 옮겨 지음, 가져오지 않는다).
//   제목 줄 → 안내 카드(설명 두 줄 · 구분 표(맞음·어긋남·계산 못 함·리스크 배지) · 시작 안내) → 검증 과정 카드(3단계 띠) →
//   두 칸(올리는 것 · 받는 것) → 오른쪽 아래 [시작하기]. 글은 DV_TEXT.intro(판 그대로).
// 구분 배지의 색은 판 그대로: 맞음 success · 어긋남 error · 계산 못 함 orange · 리스크 grey(키트 Badge).
import { useId } from 'react';
import type { ReactNode } from 'react';

import { ChevronRightIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';

import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_BODY_CLASS,
} from '../../../shared/ui/form-rows/index.ts';

const words = DV_TEXT.intro;

/** 구분 표 줄의 배지 색(판 차례 — 맞음·어긋남·계산 못 함·리스크). */
const BADGES = ['success', 'error', 'orange', 'grey'] as const;

interface KindRow {
  index: number;
  kind: string;
  meaning: string;
  example: string;
}

const ROWS: KindRow[] = words.table.rows.map(
  ([kind, meaning, example], index) => ({ index, kind, meaning, example }),
);

const COLUMNS: DataTableColumnDef<KindRow>[] = [
  {
    id: 'kind',
    header: words.table.head[0],
    enableSorting: false,
    meta: { width: 120 },
    cell: ({ row }) => (
      <Badge variant={BADGES[row.original.index]}>{row.original.kind}</Badge>
    ),
  },
  {
    id: 'meaning',
    accessorKey: 'meaning',
    header: words.table.head[1],
    enableSorting: false,
  },
  {
    id: 'example',
    accessorKey: 'example',
    header: words.table.head[2],
    enableSorting: false,
    meta: { width: 420 },
    cell: ({ row }) => (
      <span className="text-text-tertiary">{row.original.example}</span>
    ),
  },
];

export interface IntroScreenProps {
  onStart(): void;
}

export function IntroScreen({ onStart }: IntroScreenProps) {
  const processId = useId();
  const table = useDataTable({
    data: ROWS,
    columns: COLUMNS,
    getRowId: (row) => String(row.index),
  });
  return (
    <div data-screen="dataverify-intro" className="flex flex-col gap-6">
      <PageTitle title={words.title} />

      <Card className="flex flex-col gap-4">
        <h3 className="m-0 text-style-pre-heading-02 text-text-brand">
          {words.heading}
        </h3>
        <p className="m-0 text-style-pre-body-03 text-text-secondary">
          {words.lead[0]}
          <br />
          {words.lead[1]}
        </p>
        <DataTable table={table} aria-label={words.heading} layout="fixed" />
        <p className="m-0 text-style-pre-body-03 text-text-secondary">
          {words.hint}
        </p>
      </Card>

      <Card className="flex flex-col gap-5">
        <h3
          id={processId}
          className="m-0 text-style-pre-heading-02 text-text-primary"
        >
          {words.flowTitle}
        </h3>
        <ol
          aria-labelledby={processId}
          data-testid="process-band"
          className="m-0 grid list-none grid-cols-3 border-0 border-b border-t-4 border-solid border-b-border-tertiary border-t-border-brand p-0"
        >
          {words.flow.map((step, index) => (
            <li
              key={step.step}
              className="relative box-border flex flex-col gap-1 px-6 pb-6 pt-5"
            >
              <b className="text-style-pre-body-04 text-text-primary">
                {step.step}
              </b>
              <strong className="text-style-pre-body-01 text-text-brand">
                {step.title}
              </strong>
              <span className="text-style-pre-body-06 text-text-tertiary">
                {step.body}
              </span>
              {index < words.flow.length - 1 && (
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
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <RowsCard title={words.give.title} rows={words.give.rows} />
        <RowsCard title={words.get.title} rows={words.get.rows} />
      </div>

      <div className="flex justify-end">
        <Button variant="solidBlack" shape="round" size="md" onClick={onStart}>
          {words.start}
        </Button>
      </div>
    </div>
  );
}

/** 머리·값 두 칸 줄의 카드(판 e-formrows — 이름 160 · 값 400 16, 밴드 DV3 W3). */
function RowsCard({
  title,
  rows,
}: {
  title: ReactNode;
  rows: readonly (readonly [string, string])[];
}) {
  return (
    <Card className="flex flex-col gap-4">
      <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
        {title}
      </h3>
      <dl className={FORM_ROWS_CLASS}>
        {rows.map(([head, value]) => (
          <div key={head} className={FORM_ROW_CLASS}>
            <dt className={FORM_LABEL_CLASS}>{head}</dt>
            <dd className={FORM_VALUE_BODY_CLASS}>{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
