// 버튼. 키트 packages/ui 의 button 을 참고본으로 다시 만들었다(밴드 FK2, FV3-FG 6절).
//
// 키트와 다른 자리:
//   - 꼴(Rectangle/Round)을 변형 이름에 섞지 않고 축을 나눴다: variant(색) · shape(꼴) · size(크기).
//     둥글기 클래스는 shape×size 의 짝(compoundVariants)에서만 나온다. 그래서 한 요소에 둥글기 클래스가 늘 하나다.
//     (키트는 rounded-component 바탕 위에 rounded-full·rounded-control 이 더 붙는데, tailwind-merge 1.14 가 이 별칭들을 합치지 못한다.)
//   - solidGrey 의 글자는 text-grey-800(#383C40. 디자이너 값, 2026-10-15 사용자 결정). 키트는 text-text-tertiary.
//   - text 변형은 바탕·테두리만 없다. 높이·안쪽 여백·둥글기는 size·shape 축을 그대로 따른다(키트의 h-auto p-0 rounded-control 은 들이지 않았다).
//   - 아이콘–글자 사이 2px(gap-0.5), 아이콘 16. 초점은 2px border-secondary 바깥선을 2px 띄운다.
//   - 글자는 크기 축에서 나온다: xs·sm 12 Medium(pre-caption-02), md 14 Medium(pre-body-05), lg 16 Bold(pre-body-01). sm 최소 너비 56.
//     lg 최소 너비 80(md 와 같다. lg 가 md 보다 좁아지지 않게. 밴드 FW1b ⓪, band-reports/FW1-design-review.md 「lg 버튼에 최소 너비가 없다」).
//     round sm 의 좌우는 10(표 안 행 버튼, FG5 [구조]). 밴드 FW1 ⓪, band-reports/FK2-design-review.md 2.
//   - outlineOrange 는 흰 바탕 + hover #F3F4F5(button-white·button-white-hover. Figma Basic Btn). 키트는 연한 주황 바탕이고 hover 토큰이 없다.
//     연한 주황 바탕 + 주황 테두리는 Figma Filter Btn 의 On 꼴이다. 필요하면 필터 버튼에서 따로 둔다(FK2-design-review.md 질문 4).
// 색 클래스는 키트 cva 의 같은 이름 변형(…Rectangle)에서 옮겼다.
import * as React from 'react';

import { Spinner } from '@marcspon/ui/components/spinner';
import { cn } from '@marcspon/ui/lib/utils';
import { Slot } from '@radix-ui/react-slot';

import { type VariantProps, cva } from 'class-variance-authority';

import { PARTS_TEXT } from '../../text.ts';

export const BUTTON_VARIANTS = [
  'solidBlack',
  'solidGrey',
  'solidOrange',
  'outlineGrey',
  'outlineBlack',
  'outlineOrange',
  'text',
] as const;
export const BUTTON_SHAPES = ['square', 'round'] as const;
export const BUTTON_SIZES = ['xs', 'sm', 'md', 'lg'] as const;

const buttonVariants = cva(
  'relative box-border inline-flex shrink-0 items-center justify-center gap-0.5 whitespace-nowrap border-0 transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary disabled:cursor-not-allowed disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        solidBlack:
          'bg-button-black text-text-primary-inverse hover:bg-button-black-hover active:bg-button-black-hover disabled:hover:bg-button-black disabled:hover:text-text-primary-inverse',
        solidGrey:
          'bg-button-grey text-grey-800 hover:bg-button-grey-hover active:bg-button-grey-hover disabled:hover:bg-button-grey disabled:hover:text-grey-800',
        solidOrange:
          'bg-button-orange text-text-primary-inverse hover:bg-button-orange-hover active:bg-button-orange-hover disabled:hover:bg-button-orange disabled:hover:text-text-primary-inverse',
        outlineGrey:
          'border border-solid border-button-grey bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary',
        outlineBlack:
          'border border-solid border-button-black bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary',
        outlineOrange:
          'border border-solid border-border-brand bg-button-white text-text-brand hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-brand',
        text: 'bg-transparent text-text-tertiary hover:bg-background-overlay-subtle hover:text-text-secondary active:bg-background-overlay-subtle active:text-text-secondary disabled:hover:bg-transparent disabled:hover:text-text-tertiary',
      },
      // 꼴 축 자체에는 클래스가 없다. 둥글기와 좌우 안쪽 여백은 아래 compoundVariants 가 크기와 짝지어 단다.
      shape: { square: '', round: '' },
      size: {
        xs: 'h-[22px] text-style-pre-caption-02',
        sm: 'h-7 min-w-14 text-style-pre-caption-02',
        md: 'h-9 min-w-20 text-style-pre-body-05',
        lg: 'h-10 min-w-20 text-style-pre-body-01',
      },
    },
    compoundVariants: [
      { shape: 'square', size: 'xs', className: 'rounded-control px-1.5' },
      { shape: 'square', size: 'sm', className: 'rounded-component px-2' },
      { shape: 'square', size: 'md', className: 'rounded-component px-3' },
      { shape: 'square', size: 'lg', className: 'rounded-component px-4' },
      { shape: 'round', size: 'xs', className: 'rounded-full px-1.5' },
      { shape: 'round', size: 'sm', className: 'rounded-full px-2.5' },
      { shape: 'round', size: 'md', className: 'rounded-full px-4' },
      { shape: 'round', size: 'lg', className: 'rounded-full px-4' },
    ],
    defaultVariants: { variant: 'solidGrey', shape: 'square', size: 'md' },
  },
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** 자식 요소(예: a)를 버튼처럼 그린다. 자식은 하나여야 한다. */
  asChild?: boolean;
  /** 참이면 글자 자리에 도는 표시를 보이고 누를 수 없다. */
  loading?: boolean;
  /** 도는 표시의 이름. 주지 않으면 문구 표(components/text.ts)의 값. */
  loadingLabel?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className,
      disabled,
      loading = false,
      loadingLabel = PARTS_TEXT.loading,
      leftIcon,
      rightIcon,
      variant,
      shape,
      size,
      asChild = false,
      type,
      onClickCapture,
      onKeyDownCapture,
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : 'button';
    const content = (label: React.ReactNode) =>
      loading ?
        <>
          <span className="inline-flex items-center justify-center gap-0.5 opacity-0">
            {leftIcon}
            {label}
            {rightIcon}
          </span>
          <span className="absolute inset-0 flex items-center justify-center">
            <Spinner aria-label={loadingLabel} />
          </span>
        </>
      : <>
          {leftIcon}
          {label}
          {rightIcon}
        </>;
    // Slot 은 자식 요소 하나를 받는다. 도는 표시와 아이콘은 그 자식의 안쪽에 넣는다(키트와 같은 방식).
    const child =
      (
        asChild &&
        React.isValidElement<{ children?: React.ReactNode }>(children)
      ) ?
        React.cloneElement(
          children,
          undefined,
          content(children.props.children),
        )
      : content(children);
    const blocked = Boolean(disabled) || loading;
    return (
      <Comp
        {...props}
        ref={ref}
        aria-busy={loading || undefined}
        aria-disabled={asChild && blocked ? true : undefined}
        className={cn(buttonVariants({ variant, shape, size }), className)}
        // asChild 가 아니면 기본 type 은 button 이다(form 안에서 눌러도 submit 하지 않게). 쓰는 쪽 type 이 이긴다.
        // asChild 면 자식 요소(a 등)에 type 을 붙이지 않는다.
        type={asChild ? type : (type ?? 'button')}
        disabled={asChild ? undefined : blocked}
        onClickCapture={(event: React.MouseEvent<HTMLButtonElement>) => {
          if (blocked) {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
          onClickCapture?.(event);
        }}
        // asChild 의 자식은 disabled 속성이 없어 Enter·Space 가 그대로 닿는다. 꺼졌거나 불러오는 중이면 캡처 단계에서 막는다.
        onKeyDownCapture={(event: React.KeyboardEvent<HTMLButtonElement>) => {
          if (blocked && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
          onKeyDownCapture?.(event);
        }}
      >
        {child}
      </Comp>
    );
  },
);
Button.displayName = 'Button';

export { Button, buttonVariants };
