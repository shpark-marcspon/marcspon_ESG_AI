// 로그인 카드 안의 한 줄 오류·안내(밴드 LG1, 시안 CM-01a 의 e-info--invalid). PageInfo + 아이콘.
// 꼴: 오류(빨간 띠, 기본) · 안내(회색 띠 — 「임시 비밀번호로 다시 로그인해 주세요」, 디자인 감독 ④)
//     · 중요(주황 띠 + 정보 아이콘 — 세션 끝남, 카드 위. 시안 CM-03 e-info--important, 밴드 DT1 C1).
// role: 방금 생긴 실패는 alert, 화면에 들어올 때부터 있는 안내(세션 만료 등)는 status.
import type { ReactNode } from 'react';

import {
  CircleWarningIcon,
  LockIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { PageInfoIcon } from '../../../shared/ui/page-info/index.ts';

export interface AuthAlertProps {
  role: 'alert' | 'status';
  /** error = 빨간 오류 띠(기본), info = 회색 안내 띠, important = 주황 안내 띠. */
  tone?: 'error' | 'info' | 'important';
  /** 잠김이면 자물쇠 아이콘(시안 CM-01a 의 잠김 상태). */
  lock?: boolean;
  /** 시험이 까닭을 가른다. */
  reason: string;
  children: ReactNode;
}

export function AuthAlert({
  role,
  tone = 'error',
  lock = false,
  reason,
  children,
}: AuthAlertProps) {
  const icon =
    lock ? <LockIcon aria-hidden />
    : tone === 'info' || tone === 'important' ? <PageInfoIcon />
    : <CircleWarningIcon aria-hidden />;
  return (
    <PageInfo
      tone={
        tone === 'info' ? 'default'
        : tone === 'important' ?
          'important'
        : 'error'
      }
      role={role}
      data-reason={reason}
      icon={icon}
    >
      {children}
    </PageInfo>
  );
}
