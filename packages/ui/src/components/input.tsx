import * as React from "react";

import { type VariantProps, cva } from "class-variance-authority";

import { fieldBaseStyles, outlinedFieldStyles } from "../lib/field-styles";
import { cn } from "../lib/utils";

const inputVariants = cva(`flex ${fieldBaseStyles}`, {
  variants: {
    variant: {
      underlineInverse:
        "rounded-none border-0 border-b border-solid border-text-primary-inverse bg-transparent text-text-primary-inverse focus:border-border-secondary [&:-webkit-autofill]:shadow-[0_0_0px_1000px_transparent_inset] [&:-webkit-autofill]:[-webkit-text-fill-color:#fff] [&:-webkit-autofill]:[transition:background-color_5000s_ease-in-out_0s]",
      unstyled: "rounded-none border-0 bg-transparent p-0",
      filled:
        "rounded-component border border-solid border-transparent bg-background-secondary focus:border-border-secondary",
      outline: `rounded-component ${outlinedFieldStyles}`,
      outlineRound: `rounded-full ${outlinedFieldStyles}`,
      underline:
        "rounded-none border-0 border-b border-solid border-border-tertiary bg-inherit px-0 focus:border-border-secondary",
      icon: `rounded-component ${outlinedFieldStyles}`,
    },
    inputSize: {
      inline: "h-[26px] p-0 text-style-pre-body-03",
      sm: "h-6 px-2",
      md: "h-9 px-3",
      lg: "h-16 px-4 text-style-pre-body-03",
    },
  },
  compoundVariants: [{ variant: "icon", className: "pr-8" }],
  defaultVariants: {
    variant: "outline",
    inputSize: "md",
  },
});

export interface InputProps
  extends
    Omit<React.ComponentProps<"input">, "size">,
    VariantProps<typeof inputVariants> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, variant, inputSize, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(inputVariants({ variant, inputSize, className }))}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input, inputVariants };
