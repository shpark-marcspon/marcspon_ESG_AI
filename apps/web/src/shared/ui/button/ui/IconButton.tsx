// 아이콘만 있는 버튼. 키트 button 의 size iconMd(28)·iconSm(20) + variant icon 꼴을 따로 뺐다.
// 글자가 없으므로 이름(aria-label)을 반드시 받는다. 빠뜨리면 타입 오류다(Button.test.tsx 의 @ts-expect-error 가 지킨다).
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { type VariantProps, cva } from 'class-variance-authority';

const iconButtonVariants = cva(
  'box-border inline-flex shrink-0 items-center justify-center rounded-control border-0 bg-transparent p-0 text-text-quaternary transition-colors duration-200 hover:bg-background-overlay-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      size: {
        md: 'size-7 [&_svg]:size-4',
        sm: 'size-5 [&_svg]:size-4',
      },
    },
    defaultVariants: { size: 'md' },
  },
);

export interface IconButtonProps
  extends
    Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'>,
    VariantProps<typeof iconButtonVariants> {
  /** 버튼의 이름. 글자가 없으니 반드시 준다. */
  'aria-label': string;
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ className, size, type = 'button', ...props }, ref) => (
    <button
      {...props}
      ref={ref}
      type={type}
      className={cn(iconButtonVariants({ size }), className)}
    />
  ),
);
IconButton.displayName = 'IconButton';

export { IconButton, iconButtonVariants };
