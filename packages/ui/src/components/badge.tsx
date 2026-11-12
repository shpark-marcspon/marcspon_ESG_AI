import * as React from "react";

import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

/** 제품 디자인 토큰을 사용하는 공통 Badge variant. */
const badgeVariants = cva(
  "inline-flex w-max items-center justify-center rounded-control font-medium normal-case",
  {
    variants: {
      variant: {
        default: "bg-background-tertiary text-text-tertiary",
        green: "bg-support-green-subtle text-support-green",
        orange: "bg-support-orange-subtle text-support-orange-dark",
        turquoise: "bg-support-turquoise-subtle text-support-turquoise-dark",
        terquoise: "bg-support-turquoise-subtle text-support-turquoise-dark",
        yellow: "bg-support-yellow-subtle text-support-yellow-dark",
        blue: "bg-support-blue-subtle text-support-blue",
        red: "bg-support-red-subtle text-support-red",
        redDark: "bg-support-red-subtle text-support-red-dark",
        pink: "bg-support-pink-subtle text-support-pink-dark",
        grey: "bg-background-tertiary text-text-tertiary",
        success: "bg-support-success-subtle text-support-success-accent",
        error: "bg-support-error-subtle text-support-error-accent",
        na: "bg-background-secondary text-text-tertiary",
        purple: "bg-[#f4efff] text-[#854cef]",
        edk: "bg-support-orange-subtle text-support-orange",
        reportStandard: "bg-background-secondary text-support-orange",
      },
      size: {
        sm: "h-5 px-1 text-style-pre-caption-02 leading-5",
        md: "h-6 px-2 text-style-pre-body-04 leading-6",
        goal: "h-[30px] min-w-20 px-1 py-1 text-style-pre-body-04 leading-[30px]",
      },
    },
    defaultVariants: {
      variant: "grey",
      size: "sm",
    },
  },
);

export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(badgeVariants({ variant, size, className }))}
        {...props}
      />
    );
  },
);
Badge.displayName = "Badge";

export { Badge, badgeVariants };
