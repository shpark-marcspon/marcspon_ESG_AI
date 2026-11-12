import * as React from "react";

import { LoaderCircle } from "lucide-react";

import { cn } from "../lib/utils";

const Spinner = React.forwardRef<
  SVGSVGElement,
  React.ComponentPropsWithoutRef<typeof LoaderCircle>
>(({ className, "aria-label": ariaLabel = "loading", ...props }, ref) => (
  <LoaderCircle
    ref={ref}
    role="status"
    aria-label={ariaLabel}
    className={cn("h-5 w-5 animate-spin", className)}
    {...props}
  />
));
Spinner.displayName = "Spinner";

export { Spinner };
