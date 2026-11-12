import * as React from "react";

import { Slot } from "@radix-ui/react-slot";
import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

/** 제품 디자인 토큰과 상호작용 상태를 통합한 공통 Button. */
const buttonVariants = cva(
  "box-border inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-component border-0 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-button-black text-text-primary-inverse hover:bg-button-black-hover active:bg-button-black-hover disabled:hover:bg-button-black disabled:hover:text-text-primary-inverse",
        destructive:
          "bg-destructive text-destructive-foreground hover:opacity-90",
        outline:
          "border border-solid border-button-grey bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-active disabled:hover:bg-button-white disabled:hover:text-text-secondary",
        secondary:
          "bg-button-grey text-text-tertiary hover:bg-button-grey-hover active:bg-button-grey-hover disabled:hover:bg-button-grey disabled:hover:text-text-tertiary",
        ghost:
          "bg-transparent text-text-tertiary hover:bg-background-overlay-subtle hover:text-text-secondary",
        link: "h-auto bg-transparent p-0 align-baseline font-semibold leading-normal text-text-tertiary hover:bg-transparent hover:text-text-tertiary hover:underline active:bg-transparent active:text-[#2D3748] disabled:hover:bg-transparent disabled:hover:text-text-tertiary disabled:hover:no-underline",
        solidGreyRectangle:
          "bg-button-grey text-text-tertiary hover:bg-button-grey-hover active:bg-button-grey-hover disabled:hover:bg-button-grey disabled:hover:text-text-tertiary",
        solidGreyRound:
          "rounded-full bg-button-grey text-text-tertiary hover:bg-button-grey-hover active:bg-button-grey-hover disabled:hover:bg-button-grey disabled:hover:text-text-tertiary",
        solidBlackRectangle:
          "bg-button-black text-text-primary-inverse hover:bg-button-black-hover active:bg-button-black-hover disabled:hover:bg-button-black disabled:hover:text-text-primary-inverse",
        solidBlackRound:
          "rounded-full bg-button-black text-text-primary-inverse hover:bg-button-black-hover active:bg-button-black-hover disabled:hover:bg-button-black disabled:hover:text-text-primary-inverse",
        solidOrangeRectangle:
          "bg-button-orange text-text-primary-inverse hover:bg-button-orange-hover active:bg-button-orange-hover disabled:hover:bg-button-orange disabled:hover:text-text-primary-inverse",
        solidOrangeRound:
          "rounded-full bg-button-orange text-text-primary-inverse hover:bg-button-orange-hover active:bg-button-orange-hover disabled:hover:bg-button-orange disabled:hover:text-text-primary-inverse",
        outlineGreyRectangle:
          "border border-solid border-button-grey bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary",
        outlineGreyRound:
          "rounded-full border border-solid border-button-grey bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary",
        outlineBlackRectangle:
          "border border-solid border-button-black bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary",
        outlineBlackRound:
          "rounded-full border border-solid border-button-black bg-button-white text-text-secondary hover:bg-button-white-hover active:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary",
        outlineOrangeRectangle:
          "border border-solid border-border-brand bg-background-brand text-text-brand hover:bg-background-brand-hover active:bg-background-brand-hover disabled:hover:bg-background-brand disabled:hover:text-text-brand",
        outlineOrangeRound:
          "rounded-full border border-solid border-border-brand bg-background-brand text-text-brand hover:bg-background-brand-hover active:bg-background-brand-hover disabled:hover:bg-background-brand disabled:hover:text-text-brand",
        text: "h-auto rounded-control bg-transparent p-0 text-text-tertiary hover:bg-background-overlay-subtle hover:text-text-secondary active:bg-background-overlay-subtle active:text-text-secondary disabled:hover:bg-transparent disabled:hover:text-text-tertiary",
        icon: "bg-transparent text-text-quaternary hover:bg-background-overlay-subtle active:bg-background-brand active:text-text-brand disabled:hover:bg-transparent disabled:hover:text-text-quaternary",
        // chakra `variant="unstyled"` 대응. 배경·패딩·크기를 모두 비우고 색은 상속한다.
        // (가이드 아이콘처럼 아이콘만 보여야 하는 버튼용)
        unstyled:
          "h-auto min-h-0 min-w-0 rounded-none bg-transparent p-0 text-inherit shadow-none hover:bg-transparent hover:text-inherit active:bg-transparent active:text-inherit disabled:hover:bg-transparent disabled:hover:text-inherit",
        scrollUp:
          "h-10 w-10 rounded-[6px] bg-button-white text-text-secondary shadow-[0_0_5px_2px_rgba(0,0,0,0.1)] hover:bg-button-white-hover disabled:hover:bg-button-white disabled:hover:text-text-secondary",
        uploadDownload:
          "h-fit w-fit rounded-component border border-solid border-border-tertiary bg-white px-8 py-14 text-text-tertiary hover:bg-background-overlay-subtle hover:text-text-secondary disabled:bg-white disabled:text-text-secondary disabled:hover:bg-white disabled:hover:text-text-secondary",
        industryAdd:
          "h-fit w-full rounded-dialog border border-solid border-border-quaternary bg-white px-8 py-6 text-text-tertiary hover:border-button-grey hover:bg-button-white-hover active:border-button-grey active:bg-button-white-active disabled:hover:border-border-quaternary disabled:hover:bg-white disabled:hover:text-text-tertiary",
        industryArrow:
          "h-fit w-full rounded-none bg-white p-[6px] text-text-tertiary hover:bg-button-white-hover active:bg-button-white-active disabled:hover:bg-white disabled:hover:text-text-tertiary",
        info: "h-fit w-full rounded-component border border-solid border-button-grey bg-white px-4 py-[18px] text-text-tertiary hover:bg-button-white-hover hover:text-text-secondary active:bg-button-white-active active:text-text-secondary disabled:hover:bg-white disabled:hover:text-text-tertiary",
      },
      size: {
        none: "px-0",
        xs: "h-[22px] rounded-control text-style-pre-caption-02",
        sm: "h-7 min-w-0 text-style-pre-caption-02",
        // chakra: 프로젝트 md는 minH 36px만 정의하지만 chakra 기본 md의 h: 10(40px)이
        // 병합돼 실제로는 높이 40px 고정으로 렌더된다. min-h만 두면 flex 컨테이너에서
        // 세로로 늘어나므로 같은 값으로 고정한다.
        md: "h-10 min-w-20 text-style-pre-body-05",
        lg: "h-14 px-4 text-style-pre-body-01",
        icon: "h-9 w-9",
        iconMd: "h-7 w-7 rounded-control p-0",
        iconSm: "h-5 w-5 rounded-control p-0",
      },
    },
    compoundVariants: [
      {
        variant: [
          "solidGreyRound",
          "solidBlackRound",
          "solidOrangeRound",
          "outlineGreyRound",
          "outlineBlackRound",
          "outlineOrangeRound",
        ],
        size: "xs",
        // chakra variantPx는 "round"(소문자) 검사라 *Round 변형에도 사각형 값이 적용됐다.
        className: "px-[6px]",
      },
      {
        variant: [
          "solidGreyRound",
          "solidBlackRound",
          "solidOrangeRound",
          "outlineGreyRound",
          "outlineBlackRound",
          "outlineOrangeRound",
        ],
        size: "sm",
        className: "px-2",
      },
      {
        variant: [
          "solidGreyRound",
          "solidBlackRound",
          "solidOrangeRound",
          "outlineGreyRound",
          "outlineBlackRound",
          "outlineOrangeRound",
        ],
        size: "md",
        className: "px-3",
      },
      {
        variant: [
          "default",
          "destructive",
          "outline",
          "secondary",
          "ghost",
          "solidGreyRectangle",
          "solidBlackRectangle",
          "solidOrangeRectangle",
          "outlineGreyRectangle",
          "outlineBlackRectangle",
          "outlineOrangeRectangle",
        ],
        size: "xs",
        className: "px-[6px]",
      },
      {
        variant: [
          "default",
          "destructive",
          "outline",
          "secondary",
          "ghost",
          "solidGreyRectangle",
          "solidBlackRectangle",
          "solidOrangeRectangle",
          "outlineGreyRectangle",
          "outlineBlackRectangle",
          "outlineOrangeRectangle",
        ],
        size: "sm",
        className: "px-2",
      },
      {
        variant: [
          "default",
          "destructive",
          "outline",
          "secondary",
          "ghost",
          "solidGreyRectangle",
          "solidBlackRectangle",
          "solidOrangeRectangle",
          "outlineGreyRectangle",
          "outlineBlackRectangle",
          "outlineOrangeRectangle",
        ],
        size: "md",
        className: "px-3",
      },
      {
        variant: "uploadDownload",
        size: ["none", "xs", "sm", "md", "lg", "icon", "iconMd", "iconSm"],
        className: "h-fit min-h-0 w-fit min-w-0 px-8 py-14",
      },
      {
        variant: "industryAdd",
        size: ["none", "xs", "sm", "md", "lg", "icon", "iconMd", "iconSm"],
        className: "h-fit min-h-0 w-full min-w-0 px-8 py-6",
      },
      {
        variant: "industryArrow",
        size: ["none", "xs", "sm", "md", "lg", "icon", "iconMd", "iconSm"],
        className: "h-fit min-h-0 w-full min-w-0 p-[6px]",
      },
      {
        variant: "info",
        size: ["none", "xs", "sm", "md", "lg", "icon", "iconMd", "iconSm"],
        className: "h-fit min-h-0 w-full min-w-0 px-4 py-[18px]",
      },
    ],
    defaultVariants: {
      variant: "solidGreyRectangle",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
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
      leftIcon,
      rightIcon,
      variant,
      size,
      asChild = false,
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    const content = (label: React.ReactNode) =>
      !loading ? (
        <>
          {leftIcon}
          {label}
          {rightIcon}
        </>
      ) : (
        <>
          <span
            className={cn(
              "inline-flex items-center justify-center gap-2",
              loading && "opacity-0",
            )}
          >
            {leftIcon}
            {label}
            {rightIcon}
          </span>
          {loading && (
            <span
              aria-hidden
              className="absolute inset-0 flex items-center justify-center"
            >
              <span className="h-[1em] w-[1em] animate-spin rounded-full border-2 border-current border-t-transparent" />
            </span>
          )}
        </>
      );
    // Slot requires one element even while loading. Keep the link/component itself.
    const child =
      asChild && React.isValidElement<{ children?: React.ReactNode }>(children)
        ? React.cloneElement(
            children,
            undefined,
            content(children.props.children),
          )
        : loading || leftIcon || rightIcon
          ? content(children)
          : children;
    return (
      <Comp
        {...props}
        ref={ref}
        aria-busy={loading || undefined}
        aria-disabled={asChild && (disabled || loading) ? true : undefined}
        className={cn(
          buttonVariants({ variant, size, className }),
          loading && "relative",
        )}
        disabled={asChild ? undefined : disabled || loading}
        onClickCapture={(event) => {
          if (disabled || loading) {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
          props.onClickCapture?.(event);
        }}
      >
        {child}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
