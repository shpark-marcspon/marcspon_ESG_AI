// 비밀번호 칸 + 보기 단추(밴드 LG1, 시안 c-pw). 보기 단추는 aria-pressed 로 켜짐을 알린다. 키트 input(outline, 40 높이 — 시안 button-lg 40, 밴드 DT1 C2).
import { forwardRef, useState } from 'react';

import {
  EyeClosedIcon,
  EyeOpenIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import type { InputProps } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import { IconButton } from '../../../shared/ui/button/index.ts';

export interface PasswordInputProps extends Omit<InputProps, 'type'> {
  /** 보기 단추의 이름(예 「비밀번호 보기」). */
  showLabel: string;
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ showLabel, className, ...props }, ref) => {
    const [shown, setShown] = useState(false);
    return (
      <div className="relative flex">
        <Input
          {...props}
          ref={ref}
          type={shown ? 'text' : 'password'}
          className={cn('h-10 pr-12', className)}
        />
        <IconButton
          aria-label={showLabel}
          aria-pressed={shown}
          onClick={() => setShown((value) => !value)}
          className="absolute right-1 top-1/2 size-9 -translate-y-1/2 [&_svg]:size-5"
        >
          {shown ?
            <EyeOpenIcon aria-hidden />
          : <EyeClosedIcon aria-hidden />}
        </IconButton>
      </div>
    );
  },
);
PasswordInput.displayName = 'PasswordInput';
