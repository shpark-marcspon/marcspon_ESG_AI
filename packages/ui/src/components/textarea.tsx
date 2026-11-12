import * as React from "react";

import { type VariantProps, cva } from "class-variance-authority";

import { fieldBaseStyles, outlinedFieldStyles } from "../lib/field-styles";
import { cn } from "../lib/utils";

const textareaVariants = cva(`${fieldBaseStyles} resize-none`, {
  variants: {
    variant: {
      outline: `min-h-20 rounded-component px-3 py-2 focus:placeholder:opacity-0 ${outlinedFieldStyles}`,
      inputlike: `min-h-20 rounded-component px-3 py-2 ${outlinedFieldStyles}`,
      filled: "min-h-20 rounded-component bg-background-secondary px-3 py-2",
      flushed:
        "min-h-20 rounded-none border-0 border-b border-solid border-border-tertiary px-0 py-2 focus:border-border-secondary",
      unstyled: "min-h-20 border-0 bg-transparent p-0",
    },
  },
  defaultVariants: { variant: "outline" },
});

export interface TextareaProps
  extends
    React.TextareaHTMLAttributes<HTMLTextAreaElement>,
    VariantProps<typeof textareaVariants> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, variant, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(textareaVariants({ variant, className }))}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export { Textarea, textareaVariants };
