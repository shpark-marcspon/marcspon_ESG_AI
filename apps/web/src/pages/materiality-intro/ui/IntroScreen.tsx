// IR-00 평가 안내(밴드 IRW2 ② — 시안 v166 IR-00_r1, 데이터 검증 DV-00 IntroScreen 꼴을 옮겨 지음, 가져오지 않는다).
//   제목 줄 → 「중대성평가 IRO란」 카드(설명 두 줄 · 구분 표 줄 둘(환경·사회 영향 긍정·부정 · 재무 영향 리스크·기회 배지)) →
//   「IRO 도출 과정」 카드(3단계 띠 — 판 g-stepband, 이름 글은 IR_TEXT.flow, body 는 옛 입력·결과 표 둘의 요약) →
//   오른쪽 아래 시작 안내(회색 작은 글) + [시작하기]. 밴드 IRW17 — 1차 댓글 9589017e·c755af0e·ac96f3dc·cb02d6d1·f0a1e9f6.
// 글은 IR_TEXT.intro(판 그대로). 배지 색은 판 그대로: 긍정·기회 success · 부정·리스크 error(키트 Badge). 데이터 0·서버 0.
// 표 열 너비는 판의 %(16·32·20)를 1440 화면 카드 안 너비로 옮긴 px(DataTable meta.width 는 px).
import { useId } from 'react';
import type { ReactNode } from 'react';

import { ChevronRightIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';

import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';

const words = IR_TEXT.intro;
const kinds = words.kinds;

interface Line {
  id: string;
  name: ReactNode;
  body: ReactNode;
  example: ReactNode;
}

/** 이름 칸: 굵은 이름(또는 배지) + 작은 영문 줄. */
const named = (name: ReactNode, sub?: string) => (
  <span className="flex flex-col gap-0.5">
    {name}
    {sub !== undefined && (
      <span className="text-style-pre-caption-03 text-text-tertiary">
        {sub}
      </span>
    )}
  </span>
);
const bold = (text: string) => (
  <b className="text-style-pre-body-04 text-text-primary">{text}</b>
);

const KIND_LINES: Line[] = [
  {
    id: 'impact',
    name: named(bold(kinds.impact.name), kinds.impact.sub),
    body: (
      <>
        {kinds.impact.meaning}{' '}
        <Badge variant="success">{kinds.impact.positive}</Badge>{' '}
        <Badge variant="error">{kinds.impact.negative}</Badge>{' '}
        {kinds.impact.meaningTail}
      </>
    ),
    example: kinds.impact.example,
  },
  {
    id: 'financial',
    name: named(
      <span className="flex flex-col gap-1">
        {bold(kinds.financial.name)}
        <span className="flex gap-1">
          <Badge variant="error">{kinds.financial.risk}</Badge>
          <Badge variant="success">{kinds.financial.opportunity}</Badge>
        </span>
      </span>,
      kinds.financial.sub,
    ),
    body: kinds.financial.meaning,
    example: (
      <span className="flex flex-col gap-1">
        <span data-testid="example-risk">
          <Badge variant="error">{kinds.financial.risk}</Badge>{' '}
          {kinds.financial.riskExample}
        </span>
        <span data-testid="example-opportunity">
          <Badge variant="success">{kinds.financial.opportunity}</Badge>{' '}
          {kinds.financial.opportunityExample}
        </span>
      </span>
    ),
  },
];

/** 구분 표 열(이름 · 뜻 · 예시). */
const KIND_COLUMNS: DataTableColumnDef<Line>[] = [
  {
    id: 'name',
    header: kinds.head[0],
    enableSorting: false,
    meta: { width: 170 },
    cell: ({ row }) => row.original.name,
  },
  {
    id: 'body',
    header: kinds.head[1],
    enableSorting: false,
    cell: ({ row }) => row.original.body,
  },
  {
    id: 'example',
    header: kinds.head[2],
    enableSorting: false,
    meta: { width: 340 },
    cell: ({ row }) => (
      <span className="text-text-tertiary">{row.original.example}</span>
    ),
  },
];

/** 표 긴 칸 위아래 12(DV-00 꼴 — 공용 DataTable 을 고치지 않고 칸 자손으로 덮는다). 긴 글은 줄바꿈. */
const ROW_CLASS = '[&_td]:py-3 [&_td]:whitespace-normal';

export interface IntroScreenProps {
  onStart(): void;
}

export function IntroScreen({ onStart }: IntroScreenProps) {
  const processId = useId();
  const kindTable = useDataTable({
    data: KIND_LINES,
    columns: KIND_COLUMNS,
    getRowId: (row) => row.id,
  });
  return (
    <div data-screen="materiality-intro" className="flex flex-col gap-6">
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
        <DataTable
          table={kindTable}
          aria-label={words.heading}
          className={ROW_CLASS}
        />
      </Card>

      <Card className="flex flex-col gap-6">
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
                {IR_TEXT.flow.items[index]!.label}
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

      <div className="flex items-center justify-end gap-3">
        <p
          data-testid="intro-hint"
          className="m-0 text-style-pre-body-06 text-text-tertiary"
        >
          {words.hint}
        </p>
        <Button variant="solidBlack" shape="round" size="md" onClick={onStart}>
          {words.start}
        </Button>
      </div>
    </div>
  );
}
