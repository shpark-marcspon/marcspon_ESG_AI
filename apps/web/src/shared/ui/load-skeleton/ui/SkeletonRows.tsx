// 표 몸의 스켈레톤 줄(밴드 LD1 ②, sid:MARC-ENT-443 ②, 6c 표). <tbody> 안에 넣는 <tr> 묶음 — DataTable 과 손으로 그린 표(admin 셋)가 같이 쓴다.
//   - 첫 그림부터 줄 rows(기본 5)개와 칸 columns.length 개로 자리를 잡는다. 줄 높이 = 진짜 줄 높이(h-14 = 56, border-box — 감독 답 LD1 §6. 시안 52 보다 튐 0 이 이긴다).
//   - delayed(기본) 면 막대만 300ms(useDelayed) 뒤에 그린다: 그 전에 끝나면 빈 줄만 잠깐(보이는 것 없음), 높이는 그대로.
//     delayed={false} 면 막대를 바로 그린다(쓰는 쪽이 이미 늦춘 값).
//   - 칸마다 막대 하나(높이 12). 폭은 SkeletonWidth(model/widths.ts), 맞춤은 칸 맞춤(가운데 mx-auto, 오른쪽 ml-auto).
//   - 줄은 보조기기에서 숨긴다(aria-hidden tr). 표의 aria-busy 는 쓰는 쪽이 단다(DataTable 은 스스로 단다).
import { cn } from '@marcspon/ui/lib/utils';

import { SkeletonBar } from '../../skeleton-bar/index.ts';
import { useDelayed } from '../hooks/index.ts';
import { skeletonWidthAt } from '../model/index.ts';
import type { SkeletonAlign, SkeletonWidth } from '../model/index.ts';

export interface SkeletonColumn {
  /** 막대 폭. 기본 'long'(긴 글 칸). */
  width?: SkeletonWidth;
  /** 칸 맞춤. 기본 왼쪽. */
  align?: SkeletonAlign;
}

export interface SkeletonRowsProps {
  /** 칸마다 하나(진짜 표의 열 차례). */
  columns: readonly SkeletonColumn[];
  /** 줄 수. 기본 5(6c). */
  rows?: number;
  /** 참(기본)이면 막대를 300ms 뒤에. 거짓이면 바로. */
  delayed?: boolean;
}

const BAR_ALIGN: Record<SkeletonAlign, string> = {
  left: '',
  center: 'mx-auto',
  right: 'ml-auto',
};

function SkeletonRows({
  columns,
  rows = 5,
  delayed = true,
}: SkeletonRowsProps) {
  const late = useDelayed(delayed);
  const bars = !delayed || late;
  return (
    <>
      {Array.from({ length: rows }, (_, row) => (
        <tr key={row} aria-hidden data-skeleton-row="">
          {columns.map((column, index) => (
            <td
              key={index}
              className="h-14 border-0 border-b border-solid border-border-tertiary px-4"
            >
              {bars && (
                <SkeletonBar
                  className={cn('h-3', BAR_ALIGN[column.align ?? 'left'])}
                  style={{
                    width: skeletonWidthAt(column.width ?? 'long', row),
                  }}
                />
              )}
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
SkeletonRows.displayName = 'SkeletonRows';

export { SkeletonRows };
