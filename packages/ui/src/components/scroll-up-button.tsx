"use client";

import * as React from "react";

import { Button } from "./button";

interface ScrollUpButtonProps {
  target?: HTMLElement;
}

/** 스크롤 컨테이너를 감지해 표시되는 공용 상단 이동 버튼. */
const ScrollUpButton = ({ target }: ScrollUpButtonProps) => {
  const [hasScroll, setHasScroll] = React.useState(false);

  const handleScrollUp = React.useCallback(() => {
    if (target) {
      target.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
  }, [target]);

  React.useEffect(() => {
    const checkForScroll = () => {
      if (target) {
        setHasScroll(
          target.scrollHeight > target.clientHeight && target.scrollTop !== 0,
        );
        return;
      }

      setHasScroll(
        document.documentElement.scrollHeight > window.innerHeight &&
          window.scrollY !== 0,
      );
    };

    checkForScroll();
    const scrollTarget: HTMLElement | Window = target ?? window;
    scrollTarget.addEventListener("scroll", checkForScroll);
    window.addEventListener("resize", checkForScroll);

    return () => {
      scrollTarget.removeEventListener("scroll", checkForScroll);
      window.removeEventListener("resize", checkForScroll);
    };
  }, [target]);

  if (!hasScroll) return null;

  return (
    <div className="twp contents">
      <Button
        type="button"
        variant="scrollUp"
        size="none"
        onClick={handleScrollUp}
        aria-label="scroll-up"
        className="fixed bottom-10 right-10 z-modal p-0"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden>
          <path
            d="M12 21V6M12 6L6 12.1486M12 6L18 12.1486"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M6 3H11.9986H18"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </Button>
    </div>
  );
};

export { ScrollUpButton };
