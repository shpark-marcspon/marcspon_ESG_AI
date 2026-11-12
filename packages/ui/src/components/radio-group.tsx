"use client";

import * as React from "react";

import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

const RadioGroup = React.forwardRef<
  React.ElementRef<typeof RadioGroupPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>
>(({ className, ...props }, ref) => (
  <RadioGroupPrimitive.Root
    ref={ref}
    className={cn("grid gap-2", className)}
    {...props}
  />
));
RadioGroup.displayName = RadioGroupPrimitive.Root.displayName;

const radioGroupItemVariants = cva(
  "aspect-square shrink-0 rounded-full border border-solid border-border-tertiary bg-background-primary outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40 data-[state=checked]:border-0 data-[state=checked]:bg-background-secondary-inverse",
  {
    variants: {
      size: {
        sm: "h-3 w-3 [&_[data-radio-indicator]]:h-1.5 [&_[data-radio-indicator]]:w-1.5",
        md: "h-4 w-4 [&_[data-radio-indicator]]:h-2 [&_[data-radio-indicator]]:w-2",
        lg: "h-5 w-5 [&_[data-radio-indicator]]:h-2.5 [&_[data-radio-indicator]]:w-2.5",
      },
    },
    defaultVariants: { size: "md" },
  },
);

export interface RadioGroupItemProps
  extends
    React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item>,
    VariantProps<typeof radioGroupItemVariants> {}

const RadioGroupItem = React.forwardRef<
  React.ElementRef<typeof RadioGroupPrimitive.Item>,
  RadioGroupItemProps
>(({ className, size, ...props }, ref) => (
  <RadioGroupPrimitive.Item
    ref={ref}
    className={cn(radioGroupItemVariants({ size, className }))}
    {...props}
  >
    <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
      <span
        data-radio-indicator
        className="block rounded-full bg-background-primary"
      />
    </RadioGroupPrimitive.Indicator>
  </RadioGroupPrimitive.Item>
));
RadioGroupItem.displayName = RadioGroupPrimitive.Item.displayName;

export { RadioGroup, RadioGroupItem, radioGroupItemVariants };
