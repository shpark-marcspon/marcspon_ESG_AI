// RP-00 작성 안내(밴드 RPW6, 시안 v196 RP-00_r1 — TR-00 IntroScreen 꼴을 옮겨 지음, 가져오지 않는다. sid:MARC-ENT-530).
//   제목 줄 → 소개 카드(설명 두 줄 · 시작 안내) → 작성 과정 카드(3단계 띠) → 올리는 것 카드(표) → 받는 것 카드(표) →
//   안내 PageInfo → 오른쪽 아래 [시작하기]. 글은 DR_TEXT.intro(판 그대로). 움직임 0(앞 넷과 같다).
// 표 둘은 DataTable(정렬 없음). 시안 열 너비 18%·14% 를 TR-00 과 같은 1440 셈값 215·167px 로 둔다(meta.width 가 px 만 받는다 —
//   카드 안 1192 = 1440 − LNB 120 − 거터 32×2 − 카드 32×2). layout="fixed", 줄 높이는 .g-desc td(위아래 8).
// [시작하기]는 두 종류 사용자 모두에게 보인다(원고작성은 운영 관리자도 [새 프로젝트]를 쓴다 — RP-01 과 같다, TR-00·DV-00·IR-00 꼴).
import { useId } from 'react';

import { ChevronRightIcon } from '@marcspon/common/generated/icons/MyIcons';

import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';

const words = DR_TEXT.intro;

/** 시안 18%·14% 의 1440 셈값(위 머리말). */
const WIDE = 215;
const NARROW = 167;

interface GiveRow {
  index: number;
  item: string;
  body: string;
  need: string;
}

interface GetRow {
  index: number;
  result: string;
  body: string;
}

const GIVE_ROWS: GiveRow[] = words.give.rows.map(
  ([item, body, need], index) => ({ index, item, body, need }),
);

const GET_ROWS: GetRow[] = words.get.rows.map(([result, body], index) => ({
  index,
  result,
  body,
}));

const GIVE_COLUMNS: DataTableColumnDef<GiveRow>[] = [
  {
    id: 'item',
    accessorKey: 'item',
    header: words.give.head[0],
    enableSorting: false,
    meta: { width: WIDE },
  },
  {
    id: 'body',
    accessorKey: 'body',
    header: words.give.head[1],
    enableSorting: false,
  },
  {
    id: 'need',
    accessorKey: 'need',
    header: words.give.head[2],
    enableSorting: false,
    meta: { width: NARROW },
  },
];

const GET_COLUMNS: DataTableColumnDef<GetRow>[] = [
  {
    id: 'result',
    accessorKey: 'result',
    header: words.get.head[0],
    enableSorting: false,
    meta: { width: WIDE },
  },
  {
    id: 'body',
    accessorKey: 'body',
    header: words.get.head[1],
    enableSorting: false,
  },
];

/** 표 줄 높이: 시안 .g-desc td 의 위아래 8(GW-00 과 같다). 공용 DataTable 을 고치지 않고 칸 자손으로 덮는다. */
const ROW_PADDING = '[&_td]:box-content [&_td]:py-2';

export interface IntroScreenProps {
  onStart(): void;
}

export function IntroScreen({ onStart }: IntroScreenProps) {
  const flowId = useId();
  const give = useDataTable({
    data: GIVE_ROWS,
    columns: GIVE_COLUMNS,
    getRowId: (row) => String(row.index),
  });
  const get = useDataTable({
    data: GET_ROWS,
    columns: GET_COLUMNS,
    getRowId: (row) => String(row.index),
  });
  return (
    <div data-screen="drafting-intro" className="flex flex-col gap-6">
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
        <p className="m-0 text-style-pre-body-03 text-text-secondary">
          {words.hint}
        </p>
      </Card>

      <Card className="flex flex-col gap-6">
        <h3
          id={flowId}
          className="m-0 text-style-pre-heading-02 text-text-primary"
        >
          {words.flowTitle}
        </h3>
        <ol
          aria-labelledby={flowId}
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

      <Card className="flex flex-col gap-4">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.give.title}
        </h3>
        <DataTable
          table={give}
          layout="fixed"
          aria-label={words.give.title}
          className={ROW_PADDING}
        />
      </Card>

      <Card className="flex flex-col gap-4">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.get.title}
        </h3>
        <DataTable
          table={get}
          layout="fixed"
          aria-label={words.get.title}
          className={ROW_PADDING}
        />
      </Card>

      <PageInfo icon={<PageInfoIcon />} data-testid="intro-info">
        {words.info}
      </PageInfo>

      <div className="flex justify-end">
        <Button variant="solidBlack" shape="round" size="md" onClick={onStart}>
          {words.start}
        </Button>
      </div>
    </div>
  );
}
