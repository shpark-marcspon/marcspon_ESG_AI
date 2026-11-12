import * as React from "react";

import { cn } from "../lib/utils";

const Icon = React.forwardRef<
  HTMLSpanElement,
  React.HTMLAttributes<HTMLSpanElement>
>(({ className, ...props }, ref) => (
  <span
    ref={ref}
    className={cn("inline-flex shrink-0 leading-[100%]", className)}
    {...props}
  />
));
Icon.displayName = "Icon";

export { Icon };
