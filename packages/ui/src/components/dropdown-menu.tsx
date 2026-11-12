"use client";

import * as React from "react";

import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";

import { cn } from "../lib/utils";

/**
 * 기본을 비모달(modal=false)로 둔다. Radix 기본(modal)은 열릴 때 body에
 * 스크롤 잠금(overflow hidden)과 pointer-events: none을 걸어 chakra Menu와 달리
 * 페이지 레이아웃이 흔들리고 바깥 요소가 잠긴다. 필요하면 modal을 명시해 켤 수 있다.
 */
const DropdownMenu = ({
  modal = false,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Root>) => (
  <DropdownMenuPrimitive.Root modal={modal} {...props} />
);
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "twp z-popover min-w-[8rem] overflow-hidden rounded-component border border-solid border-border-quaternary bg-background p-1 text-foreground shadow-[0_0_6px_rgba(0,0,0,0.12)]",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[.8] data-[state=open]:duration-200 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-[.8] data-[state=closed]:duration-100",
        className,
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      // 호버/키보드 하이라이트: Radix 는 마우스가 올라간 항목에 data-highlighted 를 붙이고 포커스도 옮긴다.
      // 셀렉트 옵션(select.tsx)과 같은 background-secondary 로 맞춘다.
      "relative flex cursor-pointer select-none items-center rounded-component outline-none transition-colors [transition-duration:50ms] ease-in hover:bg-background-secondary focus:bg-background-secondary data-[highlighted]:bg-background-secondary data-[disabled]:pointer-events-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40",
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

export {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
};
