"use client";

import * as React from "react";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

const tabsListVariants = cva("flex", {
  variants: {
    variant: {
      box: "h-8 w-fit gap-0.5 rounded-component bg-background-secondary p-1",
      line: "h-10 w-full border-b-2 border-solid border-border-tertiary",
      page: "h-10 w-full border-b border-solid border-border-tertiary",
      editor: "h-[30px] w-full gap-1",
      modal: "h-7 w-full gap-2",
    },
  },
  defaultVariants: { variant: "line" },
});

const tabsTriggerVariants = cva(
  "relative transition-colors duration-200 focus-visible:z-[1] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40",
  {
    variants: {
      variant: {
        box: "rounded-control bg-background-secondary px-2 py-0.5 text-style-pre-caption-02 text-text-quaternary data-[state=active]:bg-background-brand-inverse data-[state=active]:text-text-primary-inverse",
        line: '-mb-0.5 border-b-2 border-solid border-transparent px-4 py-1 text-style-pre-body-05 text-text-tertiary active:bg-grey-200 disabled:active:bg-transparent data-[state=active]:border-text-brand data-[state=active]:text-text-brand aria-required:after:absolute aria-required:after:right-1 aria-required:after:top-1/2 aria-required:after:h-1 aria-required:after:w-1 aria-required:after:-translate-x-1/2 aria-required:after:-translate-y-1/2 aria-required:after:rounded-full aria-required:after:bg-text-brand aria-required:after:content-[\"\"]',
        page: '-mb-px border-b-2 border-solid border-transparent px-4 py-[9px] text-style-pre-body-05 text-text-tertiary data-[state=active]:border-text-secondary data-[state=active]:text-text-secondary aria-required:after:absolute aria-required:after:right-1 aria-required:after:top-1/2 aria-required:after:h-1 aria-required:after:w-1 aria-required:after:-translate-x-1/2 aria-required:after:-translate-y-1/2 aria-required:after:rounded-full aria-required:after:bg-text-brand aria-required:after:content-[\"\"]',
        editor:
          "rounded-[6px] px-2 py-1 text-style-pre-body-05 text-text-tertiary hover:bg-button-grey data-[state=active]:bg-button-grey data-[state=active]:text-text-secondary",
        modal:
          "rounded-full bg-background-secondary px-3 py-[3px] text-style-pre-body-05 text-text-tertiary hover:bg-button-grey data-[state=active]:bg-support-orange data-[state=active]:text-text-primary-inverse data-[state=active]:hover:bg-support-orange data-[state=active]:hover:text-text-primary-inverse",
      },
    },
    defaultVariants: { variant: "line" },
  },
);

type TabsVariant = NonNullable<
  VariantProps<typeof tabsListVariants>["variant"]
>;
type TabsColorScheme = "white" | "gray";
interface TabsStyleContextValue {
  colorScheme: TabsColorScheme;
  variant: TabsVariant;
}
const TabsStyleContext = React.createContext<TabsStyleContextValue>({
  colorScheme: "white",
  variant: "line",
});

export interface TabsProps extends React.ComponentPropsWithoutRef<
  typeof TabsPrimitive.Root
> {
  colorScheme?: TabsColorScheme;
  variant?: TabsVariant;
}

function Tabs({
  colorScheme = "white",
  variant = "line",
  ...props
}: TabsProps) {
  return (
    <TabsStyleContext.Provider value={{ colorScheme, variant }}>
      <TabsPrimitive.Root {...props} />
    </TabsStyleContext.Provider>
  );
}

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => {
  const { colorScheme, variant } = React.useContext(TabsStyleContext);
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        tabsListVariants({ variant }),
        variant === "box" &&
          colorScheme === "gray" &&
          "border border-solid border-border-quaternary",
        className,
      )}
      {...props}
    />
  );
});
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => {
  const { variant } = React.useContext(TabsStyleContext);
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(tabsTriggerVariants({ variant }), className)}
      {...props}
    />
  );
});
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => {
  const { variant } = React.useContext(TabsStyleContext);
  return (
    <TabsPrimitive.Content
      ref={ref}
      className={cn(
        "outline-none",
        variant === "page" && "px-8 pb-8 pt-6",
        variant === "editor" && "p-3",
        className,
      )}
      {...props}
    />
  );
});
TabsContent.displayName = TabsPrimitive.Content.displayName;

export {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  tabsListVariants,
  tabsTriggerVariants,
};
