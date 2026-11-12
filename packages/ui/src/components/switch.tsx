"use client";

import * as React from "react";

import * as SwitchPrimitive from "@radix-ui/react-switch";

import { cn } from "../lib/utils";

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      "group peer relative inline-flex h-5 w-10 shrink-0 cursor-pointer items-center rounded-full bg-transparent outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed",
      className,
    )}
    {...props}
  >
    <span
      aria-hidden
      className="pointer-events-none absolute inset-y-0 left-0 w-9 rounded-full bg-background-tertiary transition-colors group-data-[state=checked]:bg-background-brand-inverse"
    />
    <SwitchPrimitive.Thumb className="pointer-events-none relative z-[1] block h-4 w-4 rounded-full bg-background-primary transition-transform data-[state=checked]:translate-x-[18px] data-[state=unchecked]:translate-x-0.5 group-disabled:opacity-40" />
  </SwitchPrimitive.Root>
));
Switch.displayName = SwitchPrimitive.Root.displayName;

export { Switch };
