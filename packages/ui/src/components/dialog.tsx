"use client";

import * as React from "react";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type VariantProps, cva } from "class-variance-authority";

import { cn } from "../lib/utils";

const dialogContentVariants = cva(
  "twp fixed z-modal flex max-h-[calc(100vh-32px)] max-w-[calc(100vw-32px)] flex-col overflow-auto rounded-dialog bg-background text-text-secondary shadow-lg outline-none will-change-transform [backface-visibility:hidden] data-[state=open]:animate-in motion-reduce:data-[state=open]:animate-none data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:duration-200 data-[state=open]:[animation-timing-function:cubic-bezier(0,0,0.2,1)] data-[state=closed]:animate-out motion-reduce:data-[state=closed]:animate-none data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:duration-100 data-[state=closed]:[animation-timing-function:cubic-bezier(0.4,0,1,1)]",
  {
    variants: {
      variant: {
        panel: "left-1/2 top-1/2 [translate:-50%_-50%] gap-0 p-0",
        alert: "left-1/2 top-1/2 [translate:-50%_-50%] px-4 pb-8 pt-16",
        confirm: "left-1/2 top-1/2 [translate:-50%_-50%] p-4",
        default: "left-1/2 top-1/2 [translate:-50%_-50%] gap-6 p-8",
        fullPadding:
          "left-8 top-8 h-[calc(100vh-64px)] w-[calc(100vw-64px)] max-w-none gap-6 p-8",
        bottom: "bottom-8 left-1/2 [translate:-50%_0] gap-6 p-8",
        rightSide:
          "right-[51px] top-1/2 [translate:0_-50%] px-[30px] pb-2 pl-8 pt-[42px]",
        register:
          "left-1/2 top-1/2 h-[90vh] w-[90vw] [translate:-50%_-50%] p-8",
      },
      size: {
        workspace: "w-[calc(100vw-192px)]",
        full: "min-w-full",
        xl: "w-[calc(100vw-64px)]",
        lg: "w-[800px]",
        md: "w-[640px]",
        sm: "w-[420px]",
        register: "min-h-[90vh] w-[90vw]",
        indexSelecter: "w-[1320px]",
        indexDetail: "min-h-full w-[calc(100vw-192px)]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "lg",
    },
  },
);

type DialogStyleContextValue = Required<
  Pick<VariantProps<typeof dialogContentVariants>, "variant" | "size">
>;

const DialogStyleContext = React.createContext<DialogStyleContextValue>({
  variant: "default",
  size: "lg",
});

export interface DialogProps
  extends
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Root>,
    VariantProps<typeof dialogContentVariants> {}

function Dialog({ variant = "default", size = "lg", ...props }: DialogProps) {
  return (
    <DialogStyleContext.Provider value={{ variant: variant, size: size }}>
      <DialogPrimitive.Root {...props} />
    </DialogStyleContext.Provider>
  );
}

const DialogTrigger = DialogPrimitive.Trigger;
const DialogClose = DialogPrimitive.Close;
const DialogDescription = DialogPrimitive.Description;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "twp fixed inset-0 z-modal bg-[rgba(0,0,0,0.48)] data-[state=open]:animate-in motion-reduce:data-[state=open]:animate-none data-[state=open]:fade-in-0 data-[state=open]:duration-200 data-[state=open]:[animation-timing-function:cubic-bezier(0,0,0.2,1)] data-[state=closed]:animate-out motion-reduce:data-[state=closed]:animate-none data-[state=closed]:fade-out-0 data-[state=closed]:duration-100 data-[state=closed]:[animation-timing-function:cubic-bezier(0.4,0,1,1)]",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

export interface DialogContentProps
  extends
    React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>,
    VariantProps<typeof dialogContentVariants> {
  scrollBehavior?: "inside" | "outside";
}

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(
  (
    { className, children, variant, size, scrollBehavior = "inside", ...props },
    ref,
  ) => {
    const context = React.useContext(DialogStyleContext);
    const resolvedStyle = {
      variant: variant ?? context.variant,
      size: size ?? context.size,
    };
    // Provider 는 Content 바깥에 둔다. 안쪽에 두면 `asChild` 일 때 Radix Slot 이 props(className, role, ref…)를
    // 실제 자식(<form> 등)이 아니라 Provider 요소에 합쳐 버려, role="dialog" 요소가 사라지고 스타일도 빠진다.
    const content = (
      <DialogStyleContext.Provider value={resolvedStyle}>
        <DialogPrimitive.Content
          ref={ref}
          className={cn(
            dialogContentVariants({
              ...resolvedStyle,
            }),
            scrollBehavior === "outside" &&
              "relative left-auto top-auto max-h-none shrink-0 overflow-visible [translate:0_0]",
            className,
          )}
          {...props}
        >
          {children}
        </DialogPrimitive.Content>
      </DialogStyleContext.Provider>
    );
    return (
      <DialogPrimitive.Portal>
        <DialogOverlay />
        {scrollBehavior === "outside" ? (
          <div className="twp fixed inset-0 z-modal overflow-y-auto">
            <div className="box-border flex min-h-full items-center justify-center py-20">
              {content}
            </div>
          </div>
        ) : (
          content
        )}
      </DialogPrimitive.Portal>
    );
  },
);
DialogContent.displayName = DialogPrimitive.Content.displayName;

const dialogHeaderVariants = cva("", {
  variants: {
    variant: {
      panel: "",
      alert: "mb-2 text-center text-style-pre-heading-02 text-text-secondary",
      confirm:
        "mb-3 flex items-center gap-1 border-b border-solid border-[#bbb] pb-3 text-style-pre-body-01 text-text-secondary",
      default: "text-style-pre-heading-02",
      fullPadding: "text-style-pre-heading-02",
      bottom: "text-style-pre-heading-02",
      rightSide: "text-style-pre-heading-02",
      register: "text-style-pre-heading-02 leading-6",
    },
  },
});

const DialogHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { variant } = React.useContext(DialogStyleContext);
  return (
    <div
      ref={ref}
      className={cn(dialogHeaderVariants({ variant }), className)}
      {...props}
    />
  );
});
DialogHeader.displayName = "DialogHeader";

const dialogBodyVariants = cva("", {
  variants: {
    variant: {
      panel: "",
      alert: "text-style-pre-body-06 text-center text-text-tertiary",
      confirm: "mb-4 flex gap-2 text-style-pre-body-01 text-text-secondary",
      default: "text-style-pre-body-06",
      fullPadding: "text-style-pre-body-06",
      bottom: "text-style-pre-body-06",
      rightSide: "text-style-pre-body-06 pt-[23px]",
      register: "text-style-pre-body-06 pt-[23px]",
    },
  },
});

const DialogBody = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { variant } = React.useContext(DialogStyleContext);
  return (
    <div
      ref={ref}
      className={cn(dialogBodyVariants({ variant }), className)}
      {...props}
    />
  );
});
DialogBody.displayName = "DialogBody";

const DialogFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { variant } = React.useContext(DialogStyleContext);
  return (
    <div
      ref={ref}
      className={cn(
        "flex gap-2",
        variant === "confirm" ? "justify-end" : "justify-center",
        variant === "alert" && "mt-8",
        (variant === "rightSide" || variant === "register") && "pb-[23px]",
        className,
      )}
      {...props}
    />
  );
});
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn(className)} {...props} />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

function DialogCloseGlyph(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" {...props}>
      <path
        fill="currentColor"
        d="M.439,21.44a1.5,1.5,0,0,0,2.122,2.121L11.823,14.3a.25.25,0,0,1,.354,0l9.262,9.263a1.5,1.5,0,1,0,2.122-2.121L14.3,12.177a.25.25,0,0,1,0-.354l9.263-9.262A1.5,1.5,0,0,0,21.439.44L12.177,9.7a.25.25,0,0,1-.354,0L2.561.44A1.5,1.5,0,0,0,.439,2.561L9.7,11.823a.25.25,0,0,1,0,.354Z"
      />
    </svg>
  );
}

interface DialogCloseIconButtonProps extends React.ComponentPropsWithoutRef<
  typeof DialogPrimitive.Close
> {
  /** Header 안에 배치할 때는 inline, 콘텐츠 모서리에 둘 때는 absolute를 사용한다. */
  placement?: "absolute" | "inline";
}

const DialogCloseIconButton = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Close>,
  DialogCloseIconButtonProps
>(
  (
    {
      className,
      children,
      placement = "absolute",
      "aria-label": ariaLabel = "close",
      ...props
    },
    ref,
  ) => (
    <DialogPrimitive.Close
      ref={ref}
      aria-label={ariaLabel}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-control bg-transparent text-grey-500 transition-colors duration-200 hover:bg-black/5 active:bg-black/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none disabled:hover:bg-transparent",
        placement === "absolute"
          ? "absolute right-3 top-2 h-8 w-8"
          : "static h-6 w-6 text-text-quaternary",
        className,
      )}
      {...props}
    >
      {children ?? <DialogCloseGlyph className="h-3 w-3" />}
    </DialogPrimitive.Close>
  ),
);
DialogCloseIconButton.displayName = "DialogCloseIconButton";

export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogCloseIconButton,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
  DialogTrigger,
  dialogContentVariants,
  dialogHeaderVariants,
  dialogBodyVariants,
  type DialogCloseIconButtonProps,
};
