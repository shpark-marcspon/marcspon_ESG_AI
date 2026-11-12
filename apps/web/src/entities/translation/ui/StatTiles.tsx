// 요약 수치 칸(밴드 TRW0b, 시안 TR-04·04a 「번역한 쪽 · 번역하지 못한 쪽 · 용어집 미반영 · 검수 이슈/자동 수정한 쪽」).
// 그린워싱 결과 화면의 Stat(pages/greenwash-result) 꼴을 따라 지었다 — 가져오지 않는다(pages 끼리 막힘).
// 수치 없음은 null → 「–」(단위 없이), 0 은 「0쪽」·「0건」(둘을 가른다).
// A·B 견주기 칸(pair, 밴드 TRW2 · 6c 10-26)은 「12 / 9」 — 두 수 같은 꼴·CountUp 따로, 「/」 는 tertiary, 단위는 끝에 하나.
// 읽는 중 칸(pending, 밴드 TRW8 ⑧ — PDF 「확인할 곳」): 값·메모 자리 SkeletonBar · li data-pending. 칸 수·자리는 그대로 두고 값만 들어온다.
//   rise 는 처음 그릴 때 한 번: pending 칸은 누를 칸이 올 자리라 처음부터 단추로 감싸(disabled·aria-busy) 값이 와도 요소 종류가 같고(rise 는 Card 가 붙을 때 굳혀 같은 Card 에서 떼지 않음),
//   누를 것 없이 값이 와 감쌈이 바뀌면(새 Card) 한 번이라도 pending 이었던 칸은 rise 를 빼 다시 움직이지 않게 한다. pending 을 안 준 칸은 DOM 그대로.
import { useState } from 'react';
import type { CSSProperties } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { Card } from '../../../shared/ui/card/index.ts';
import { CountUp } from '../../../shared/ui/motion/index.ts';
import { SkeletonBar } from '../../../shared/ui/skeleton-bar/index.ts';
import { TR_TEXT } from '../config/text.ts';

const words = TR_TEXT.stats;

/** 칸마다 70ms 씩 늦게 떠오른다(그린워싱 ResultScreen 의 rise 를 옮겨 적음 — pages 를 가져오지 않는다, 밴드 TRP4 ②-7). */
const rise = (order: number) =>
  ({ '--gw-m-delay': `${order * 70}ms` }) as CSSProperties;

export interface StatTile {
  key: string;
  label: string;
  value: number | null;
  unit: 'page' | 'count' | 'place';
  note?: string;
  /** 누를 수 있는 칸(밴드 TRW7 ③a — PDF 「확인할 곳」). 있으면 칸이 단추. 없으면 DOM 그대로. */
  onOpen?(): void;
  /** A·B 견주기 — 있으면 value 대신 「A / B」. */
  pair?: Readonly<Record<'A' | 'B', number | null>>;
  /** 값을 읽는 중(밴드 TRW8 ⑧) — 값·메모 자리 SkeletonBar, 단추 감쌈은 disabled·aria-busy. value·note 는 보지 않는다. */
  pending?: true;
}

const shown = (value: number | null) =>
  value === null ? words.none : <CountUp value={value} durationMs={800} />;

export interface StatTilesProps {
  items: readonly StatTile[];
  /** 1025 이상 열 수(밴드 TRW7 ③a — PDF 묶음 [전체] 다섯 칸). 기본 4(DOM 그대로). */
  columns?: 4 | 5;
}

export function StatTiles({ items, columns = 4 }: StatTilesProps) {
  // 한 번이라도 pending 이었던 칸 열쇠(「그리기 중 props 로 state 고치기」 꼴 — shared/lib/useLoad 의 useSameKey 와 같음).
  const pendingKeys = items.flatMap((item) => (item.pending ? [item.key] : []));
  const [pended, setPended] = useState<ReadonlySet<string>>(
    () => new Set(pendingKeys),
  );
  if (pendingKeys.some((key) => !pended.has(key)))
    setPended(new Set([...pended, ...pendingKeys]));
  return (
    // 1025 이상 4열(밴드 TRP2 TC18 — tailwind screens 에 md 가 없어 md:grid-cols-4 는 생성되지 않았다. sm·lg 만 있다)
    <ul
      className={cn(
        'm-0 grid list-none grid-cols-2 gap-4 p-0',
        columns === 5 ? 'lg:grid-cols-5' : 'lg:grid-cols-4',
      )}
    >
      {items.map((item, index) => (
        <li
          key={item.key}
          data-stat={item.key}
          data-pending={item.pending ? '' : undefined}
        >
          {item.onOpen === undefined && item.pending === undefined ?
            <Tile item={item} index={index} rise={!pended.has(item.key)} />
          : <button
              type="button"
              {...(item.pending ?
                { disabled: true, 'aria-busy': true }
              : { 'data-testid': 'stat-open' })}
              className="block h-full w-full cursor-pointer rounded-dialog border-0 bg-transparent p-0 text-left disabled:cursor-default"
              onClick={item.onOpen}
            >
              <Tile
                item={item}
                index={index}
                rise={item.pending === true || !pended.has(item.key)}
              />
            </button>
          }
        </li>
      ))}
    </ul>
  );
}

function Tile({
  item,
  index,
  rise: risesNow,
}: {
  item: StatTile;
  index: number;
  /** 들어오는 움직임(gw-m-rise) — 붙을 때의 값으로 굳힌다(같은 Card 에서 떼면 움직임 도중 끊김). pending 이었다가 감쌈이 바뀌어 새로 붙은 칸은 false. */
  rise: boolean;
}) {
  const [rises] = useState(risesNow);
  return (
    <>
      {/* 안쪽 24 · 숫자 display-03(시안 .g-stat — greenwash-result ResultScreen 의 Stat 과 같은 꼴, 32 를 주는 토큰이 없다) */}
      {/* rise 는 Card 에만 — li 상자는 움직이지 않는다(e2e 의 칸 높이 단언) */}
      <Card
        className={cn(rises && 'gw-m-rise', 'flex h-full flex-col gap-1.5 p-6')}
        {...(rises ? { style: rise(index) } : {})}
      >
        <span className="text-style-pre-body-05 text-text-tertiary">
          {item.label}
        </span>
        {item.pending ?
          <>
            {/* 값 줄(display-03 한 줄 높이) · 메모 줄(caption 한 줄 높이) 자리 */}
            <span className="text-style-pre-display-03">
              <SkeletonBar className="h-[1lh] w-16" />
            </span>
            <span className="text-style-pre-caption-03">
              <SkeletonBar className="h-[1lh] w-28" />
            </span>
          </>
        : <TileValue item={item} />}
      </Card>
    </>
  );
}

function TileValue({ item }: { item: StatTile }) {
  return (
    <>
      <span className="text-style-pre-display-03 tabular-nums text-text-primary">
        <span data-testid="stat-value">
          {item.pair === undefined ?
            shown(item.value)
          : <>
              <span data-style="A">{shown(item.pair.A)}</span>
              <span className="text-text-tertiary">{words.pairSeparator}</span>
              <span data-style="B">{shown(item.pair.B)}</span>
            </>
          }
        </span>
        {(item.pair === undefined ?
          item.value !== null
        : item.pair.A !== null || item.pair.B !== null) && (
          <small className="ml-1 text-style-pre-body-05 text-text-tertiary">
            {words.units[item.unit]}
          </small>
        )}
      </span>
      {item.note !== undefined && (
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {item.note}
        </span>
      )}
    </>
  );
}
