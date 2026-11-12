"use client";

import * as React from "react";
import { Search, X } from "lucide-react";

import { cn } from "../lib/utils";
import { Input, type InputProps } from "./input";

export interface SearchInputProps extends InputProps {
  wrapperClassName?: string;
  searchIconButtonProps?: React.ButtonHTMLAttributes<HTMLButtonElement>;
  deleteIconButtonProps?: React.ButtonHTMLAttributes<HTMLButtonElement>;
  searchQuery?: string;
  size?: "sm" | "md";
}

export const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  (
    {
      className,
      deleteIconButtonProps,
      searchIconButtonProps,
      searchQuery,
      size = "sm",
      wrapperClassName,
      ...props
    },
    ref,
  ) => {
    const showClear = searchQuery !== undefined && !!searchQuery;
    return (
      <div className={cn("relative h-9", wrapperClassName)}>
        <Input
          ref={ref}
          inputSize={size === "md" ? "md" : "sm"}
          className={cn(
            "h-full py-1",
            // chakra SearchInput: pl = md?16:8, pr = pl + 8(gap) + 아이콘영역(16, 지우기 표시 시 36)
            size === "md" ? "pl-4" : "pl-2",
            showClear
              ? size === "md"
                ? "pr-[60px]"
                : "pr-[52px]"
              : size === "md"
                ? "pr-10"
                : "pr-8",
            className,
          )}
          {...props}
        />
        <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1">
          {showClear && (
            <button
              type="button"
              aria-label="검색어 지우기"
              className="text-text-quaternary"
              {...deleteIconButtonProps}
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            aria-label="검색"
            className="text-text-tertiary"
            {...searchIconButtonProps}
          >
            <Search className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  },
);
SearchInput.displayName = "SearchInput";

export default SearchInput;
