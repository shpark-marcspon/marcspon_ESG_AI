// 쪽 위에 겹치는 강조 상자들. 쪽과 크기가 같은 투명한 판에, 상자를 화면 좌표로 놓는다.
// 모양 없는 컴포넌트다: 무엇을 어디에 놓는지와 상태 표시(data-*)와 누르기는 여기서 하고, 색·선·채움은 모른다.
//
// 묶음(같은 자리의 강조들) 하나가 상자 여럿일 수 있다(여러 줄에 걸친 문장). DOM 은 이렇게 둔다:
//   <div data-mode>                 판. 쪽을 꽉 채운다
//     <div>                         고른 강조가 든 표·문단 전체(context). 누를 수 없다
//     <div>                         묶음의 틀(group). 크기가 없다. 조각들을 한 덩어리로 묶는다(하나에 마우스를 올리면 :hover 가 이 틀에도 걸린다)
//       <button data-highlight-ids data-selected data-pointed data-narrowed>   조각마다 하나. 어느 조각을 눌러도 같은 항목이 골라진다
// 표시(data-selected 등)는 조각마다 똑같이 붙인다. 그래서 상자가 하나뿐인 강조는 조각 하나짜리 묶음일 뿐이다.
// Tab 으로는 첫 조각에만 간다(강조 하나에 한 번만 서게). 나머지 조각은 마우스로만 누른다.
//
// ★ 모양을 입히는 길은 셋이다(전부 안 줘도 상자는 제자리에 놓이고 눌린다):
//   classNames   판·틀·context 에 붙일 클래스 이름. 보기 방식의 차이는 화면의 CSS 가 판의 data-mode 를 보고 낸다
//   pieceProps   조각마다의 className·style·title. 종류의 색처럼 자료에서 오는 값은 여기로 넣는다(style 의 자리·크기는 덮어쓰지 못한다)
//   renderCount  겹친 개수 딱지를 그리는 함수. 안 주면 딱지가 없다
// 이렇게 고른 까닭: 지금 화면의 CSS 가 `[data-mode] .조각:not([data-selected])`, `.틀:hover .조각`, `.틀:has(:focus-visible)` 처럼
// 요소들의 관계로 모양을 낸다. 클래스 이름만 받으면 그 CSS 를 그대로 쓸 수 있다. 조각을 통째로 그리는 함수(render prop)를 받으면
// 자리·표시·누르기·Tab 순서를 쓰는 쪽이 다시 붙여야 해서, 화면을 바꿀 때 빠뜨릴 것이 는다.
import type { CSSProperties, ReactNode } from 'react';

import {
  boxToScreenRect,
  contextBoxes,
  groupHighlights,
  isDrawn,
} from '../model/index.ts';
import type {
  Highlight,
  HighlightGroup,
  PageSize,
  Rotation,
} from '../model/index.ts';
import type { DrawState } from './useDocViewer.ts';

export interface PieceLook {
  className?: string;
  style?: CSSProperties;
  title?: string;
}

export interface HighlightOverlayProps {
  /** 이 쪽의 강조들. useDocViewer 의 highlightsOn(문서 id, 쪽). */
  highlights: readonly Highlight[];
  /** 쪽의 크기(PDF 좌표). */
  page: PageSize;
  scale: number;
  rotation: Rotation;
  /** 무엇을 그릴지 정하는 값 묶음(보기 방식, 꺼 둔 종류, 고른 것, 가리킨 것, 좁힌 자리를 쓸지). useDocViewer 의 draw. */
  draw: DrawState;
  /** 상자를 눌렀다. 같은 자리에 겹친 강조의 id 를 전부 넘긴다. useDocViewer 의 pick. */
  onPick(highlightIds: string[]): void;
  classNames?: { layer?: string; group?: string; context?: string };
  pieceProps?(group: HighlightGroup): PieceLook;
  renderCount?(count: number, group: HighlightGroup): ReactNode;
}

export function HighlightOverlay({
  highlights,
  page,
  scale,
  rotation,
  draw,
  onPick,
  classNames,
  pieceProps,
  renderCount,
}: HighlightOverlayProps) {
  const { mode, selectedIds, pointedIds, useInnerBox } = draw;
  // 그릴 것을 먼저 추리고 나서 묶는다. 그래서 겹친 개수(×n)와 누를 때 도는 항목은 지금 그려진 것만 센다.
  const drawn = highlights.filter((h) => isDrawn(h, draw));
  const groups = groupHighlights(drawn, selectedIds, useInnerBox, pointedIds);
  const contexts = contextBoxes(highlights, selectedIds, useInnerBox);

  return (
    <div
      className={classNames?.layer}
      data-mode={mode}
      style={{ position: 'absolute', inset: 0 }}
    >
      {contexts.map((box) => (
        <div
          key={`context/${box.join(',')}`}
          className={classNames?.context}
          style={{
            position: 'absolute',
            boxSizing: 'border-box',
            pointerEvents: 'none',
            ...boxToScreenRect(box, page, scale, rotation),
          }}
        />
      ))}
      {groups.map((group) => {
        const count = group.highlightIds.length;
        const ids = group.highlightIds.join(' ');
        const look = pieceProps?.(group);
        return (
          <div key={group.key} className={classNames?.group}>
            {group.boxes.map((box, index) => (
              <button
                key={index}
                type="button"
                className={look?.className}
                // 자리와 크기는 뒤에 펼친다. 쓰는 쪽의 style 이 덮어쓰지 못하게.
                // box-sizing: 쓰는 쪽이 테두리나 안쪽 여백을 줘도 상자의 바깥 크기가 그대로이게.
                style={{
                  ...look?.style,
                  position: 'absolute',
                  boxSizing: 'border-box',
                  ...boxToScreenRect(box, page, scale, rotation),
                }}
                data-highlight-ids={ids}
                data-selected={group.selected}
                data-pointed={group.pointed}
                data-narrowed={group.narrowed}
                title={look?.title}
                // 첫 조각만 Tab 순서와 화면 읽기 프로그램에 남긴다. 같은 강조를 줄 수만큼 되풀이해 읽지 않게.
                tabIndex={index === 0 ? undefined : -1}
                aria-hidden={index === 0 ? undefined : true}
                onClick={() => onPick(group.highlightIds)}
              >
                {/* 겹친 개수는 마지막 조각(글이 끝나는 줄)에 한 번만 넣는다. */}
                {count > 1 &&
                  index === group.boxes.length - 1 &&
                  renderCount?.(count, group)}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}
