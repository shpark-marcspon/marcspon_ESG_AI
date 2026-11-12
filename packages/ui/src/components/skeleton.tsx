import * as React from "react";

import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

const skeletonVariants = cva(
  "pointer-events-none animate-skeleton-bg-fade select-none rounded-component bg-background-secondary text-transparent opacity-70",
  {
    variants: {
      variant: {
        default: "",
        profile: "h-10 w-10 rounded-full",
        textSm: "h-[18px] w-[200px]",
        textMd: "h-6 w-[200px]",
        textLg: "h-8 w-[200px]",
        capsuleBtnXs: "h-[22px] w-[60px] rounded-full",
        capsuleBtnSm: "h-7 w-20 rounded-full",
        capsuleBtnMd: "h-9 w-[100px] rounded-full",
        capsuleBtnLg: "h-14 w-[140px] rounded-full",
        boxBtnXs: "h-[22px] w-[60px]",
        boxBtnSm: "h-7 w-20",
        boxBtnMd: "h-9 w-[100px]",
        boxBtnLg: "h-14 w-[140px]",
        container: "h-20 w-full",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface SkeletonProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof skeletonVariants> {}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(skeletonVariants({ variant, className }))}
        {...props}
      />
    );
  },
);
Skeleton.displayName = "Skeleton";

export { Skeleton, skeletonVariants };
