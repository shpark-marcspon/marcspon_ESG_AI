"use client";

import * as React from "react";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";

import { cn } from "../lib/utils";

function TooltipProvider({
  delayDuration = 0,
  disableHoverableContent = true,
  skipDelayDuration = 0,
  ...props
}: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      delayDuration={delayDuration}
      disableHoverableContent={disableHoverableContent}
      skipDelayDuration={skipDelayDuration}
      {...props}
    />
  );
}

const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

interface TooltipContentProps extends React.ComponentPropsWithoutRef<
  typeof TooltipPrimitive.Content
> {
  arrowColor?: React.CSSProperties["color"];
  /** 배경을 덮어쓴 툴팁이 화살표 색을 맞출 때 사용 (예: fill-background-secondary-inverse) */
  arrowClassName?: string;
  /** 디자인 규칙상 모든 툴팁은 화살표를 가진다. 특별한 경우에만 false 로 끈다. */
  showArrow?: boolean;
}

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  TooltipContentProps
>(
  (
    {
      arrowColor,
      arrowClassName,
      className,
      children,
      showArrow = true,
      side = "bottom",
      sideOffset = 8,
      ...props
    },
    ref,
  ) => (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        side={side}
        sideOffset={sideOffset}
        className={cn(
          "twp pointer-events-none z-tooltip flex max-w-[180px] rounded-component bg-[#2D3748] px-3 py-2 text-style-pre-body-05 text-text-primary-inverse shadow-md [&_.twp]:text-inherit animate-in fade-in-0 zoom-in-95 duration-150 data-[side=bottom]:slide-in-from-top-1 data-[side=top]:slide-in-from-bottom-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:duration-100",
          className,
        )}
        {...props}
      >
        {children}
        {showArrow && (
          <TooltipPrimitive.Arrow
            width={10}
            height={5}
            className={cn("fill-[#2D3748]", arrowClassName)}
            style={arrowColor ? { fill: arrowColor } : undefined}
          />
        )}
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  ),
);
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
  type TooltipContentProps,
};
