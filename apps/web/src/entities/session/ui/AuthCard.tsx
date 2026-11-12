// 로그인·비밀번호 바꾸기 화면의 틀(밴드 LG1, 시안 CM-01·02 의 c-stage·c-card·c-brand). 메뉴 없는 화면이다.
// 회색 바탕 가운데에 흰 카드(너비 440, 안쪽 40, rounded-dialog). 카드 머리는 로고 자리 + 제목.
// 카드 위 안내(notice): 시안 CM-03 상태 예시 7 의 세션 끝남 띠 — 카드와 같은 440 폭, 카드와 사이 16(밴드 DT1 C1). 없으면 카드만.
import type { ReactNode } from 'react';

import { SESSION_TEXT } from '../config/text.ts';

export interface AuthCardProps {
  /** data-screen 값(시험이 화면을 가른다). */
  screen: string;
  /** 카드 이름이 될 제목의 id. */
  labelledBy: string;
  /** 로고 자리 아래 머리(제목·안내). */
  heading: ReactNode;
  /** 카드 위 한 줄 안내(세션 끝남). 없으면 그리지 않는다. */
  notice?: ReactNode;
  children: ReactNode;
}

export function AuthCard({
  screen,
  labelledBy,
  heading,
  notice,
  children,
}: AuthCardProps) {
  return (
    <main
      className="twp box-border flex min-h-screen flex-col items-center justify-center gap-4 bg-background-secondary px-4 py-12 font-pretendard text-text-secondary"
      data-screen={screen}
    >
      {notice && (
        <div className="box-border w-[440px] max-w-full">{notice}</div>
      )}
      <section
        aria-labelledby={labelledBy}
        className="box-border flex w-[440px] max-w-full flex-col gap-6 rounded-dialog bg-background-primary p-10"
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="box-border flex h-9 w-[120px] items-center justify-center rounded-control border border-dashed border-border-secondary text-style-pre-caption-02 font-bold text-text-tertiary">
            {SESSION_TEXT.brand.logo}
          </div>
          {heading}
        </div>
        {children}
      </section>
    </main>
  );
}
