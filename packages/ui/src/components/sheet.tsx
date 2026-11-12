"use client";

import * as React from "react";

import * as SheetPrimitive from "@radix-ui/react-dialog";
import { type VariantProps, cva } from "class-variance-authority";
import { X } from "lucide-react";

import { cn } from "../lib/utils";

const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;
const SheetTitle = SheetPrimitive.Title;
const SheetDescription = SheetPrimitive.Description;

const sheetVariants = cva(
  "twp fixed z-modal flex h-full flex-col bg-background shadow-lg outline-none transition data-[state=open]:animate-in data-[state=closed]:animate-out",
  {
    variants: {
      side: {
        right:
          "inset-y-0 right-0 border-l border-solid border-border-tertiary data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
        left: "inset-y-0 left-0 border-r border-solid border-border-tertiary data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left",
        top: "inset-x-0 top-0 h-auto border-b border-solid border-border-tertiary data-[state=open]:slide-in-from-top data-[state=closed]:slide-out-to-top",
        bottom:
          "inset-x-0 bottom-0 h-auto border-t border-solid border-border-tertiary data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
      },
      size: {
        full: "w-full",
        sm: "w-full max-w-[28rem]",
        lg: "w-full max-w-[640px]",
      },
    },
    defaultVariants: { side: "right", size: "full" },
  },
);

export interface SheetContentProps
  extends
    React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content>,
    VariantProps<typeof sheetVariants> {}

const SheetContent = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Content>,
  SheetContentProps
>(({ side, size, className, children, ...props }, ref) => (
  <SheetPrimitive.Portal>
    <SheetPrimitive.Overlay className="twp fixed inset-0 z-modal bg-[rgba(0,0,0,0.48)] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
    <SheetPrimitive.Content
      ref={ref}
      className={cn(sheetVariants({ side, size }), className)}
      {...props}
    >
      {children}
      <SheetPrimitive.Close
        aria-label="close"
        className="absolute right-3 top-2 flex h-10 w-10 items-center justify-center rounded-control text-text-tertiary hover:bg-background-secondary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <X className="h-4 w-4" />
      </SheetPrimitive.Close>
    </SheetPrimitive.Content>
  </SheetPrimitive.Portal>
));
SheetContent.displayName = SheetPrimitive.Content.displayName;

const SheetHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col gap-2 px-6 py-4", className)} {...props} />
);
SheetHeader.displayName = "SheetHeader";

const SheetFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("mt-auto flex gap-2 px-6 py-4", className)} {...props} />
);
SheetFooter.displayName = "SheetFooter";

const Drawer = Sheet;
const DrawerTrigger = SheetTrigger;
const DrawerClose = SheetClose;
const DrawerContent = SheetContent;
const DrawerHeader = SheetHeader;
const DrawerFooter = SheetFooter;
const DrawerTitle = SheetTitle;
const DrawerDescription = SheetDescription;

export {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  sheetVariants,
};
