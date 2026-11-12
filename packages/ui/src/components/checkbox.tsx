"use client";

import * as React from "react";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

const checkboxVariants = cva(
  "peer shrink-0 rounded-control border border-solid border-border-tertiary bg-background text-background outline-none transition-colors focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:border-background-tertiary disabled:bg-background-tertiary disabled:text-text-disabled data-[state=checked]:border-background-secondary-inverse data-[state=checked]:bg-background-secondary-inverse data-[state=checked]:text-background-primary data-[state=indeterminate]:border-background-secondary-inverse data-[state=indeterminate]:bg-background-secondary-inverse data-[state=indeterminate]:text-background-primary",
  {
    variants: {
      variant: {
        default: "",
        orange:
          "data-[state=checked]:border-button-orange data-[state=checked]:bg-button-orange data-[state=indeterminate]:border-button-orange data-[state=indeterminate]:bg-button-orange",
      },
      shape: { square: "rounded-control", round: "rounded-full" },
      size: {
        sm: "h-3 w-3",
        md: "h-4 w-4",
        lg: "h-5 w-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
      shape: "square",
    },
  },
);

const DrawnCheckIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    className={cn("h-3 w-3", className)}
    aria-hidden
  >
    <path
      d="M5 13l4 4L19 7"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray="24"
      className="animate-check-draw"
    />
  </svg>
);

const DrawnIndeterminateIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    className={cn("h-3 w-3", className)}
    aria-hidden
  >
    <path
      d="M5 12h14"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
    />
  </svg>
);

export interface CheckboxProps
  extends
    React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>,
    VariantProps<typeof checkboxVariants> {}

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  CheckboxProps
>(({ children, className, variant, size, shape, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      checkboxVariants({ variant, size, shape }),
      "disabled:data-[state=checked]:border-background-tertiary disabled:data-[state=checked]:bg-background-tertiary disabled:data-[state=checked]:text-text-disabled disabled:data-[state=indeterminate]:border-background-tertiary disabled:data-[state=indeterminate]:bg-background-tertiary disabled:data-[state=indeterminate]:text-text-disabled",
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="group flex items-center justify-center text-current">
      {/* children 을 주면 기본 체크 아이콘 대신 그걸 그린다(chakra Checkbox 의 `icon`). */}
      {children ?? (
        <>
          <DrawnCheckIcon className="hidden group-data-[state=checked]:block" />
          <DrawnIndeterminateIcon className="hidden group-data-[state=indeterminate]:block" />
        </>
      )}
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

export { Checkbox, checkboxVariants };
