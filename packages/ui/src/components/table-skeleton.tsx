import { Children } from "react";

import { Skeleton } from "./skeleton";

export function TableRowSkeleton() {
  return (
    <div className="flex w-full items-center gap-5 px-4 py-[18px]">
      <Skeleton className="mr-10 h-5 w-5 rounded-control" />
      <Skeleton className="h-3 w-[20%]" />
      <Skeleton className="h-3 w-[18%]" />
      <Skeleton className="h-3 w-[18%]" />
      <Skeleton className="h-3 w-[18%]" />
      <Skeleton className="h-3 w-[25%]" />
      <Skeleton className="h-3 w-[25%]" />
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="flex w-full flex-col">
      {Children.toArray(Array.from({ length: 6 }, () => <TableRowSkeleton />))}
    </div>
  );
}
