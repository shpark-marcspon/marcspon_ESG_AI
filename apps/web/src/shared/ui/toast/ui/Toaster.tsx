// 토스트 그림(밴드 S12Q1 ② — 값은 band-handoffs/S12Q1-figma-values.md ⑤, 선은 band-handoffs/S12Q1-permits.md).
//   - 자리: 화면 위 가운데, 머리(64) 아래 24 = 위 88 · 층 z-toast(모달 z-modal 위) · 새 것이 위 · 사이 8 · 최대 3.
//   - 성공: bg-background-primary-inverse · text-text-primary-inverse · role="status"(aria-live polite) · 닫기 단추 없음 · duration 뒤 사라짐.
//     실패: bg-support-error-subtle · text-support-error-accent · role="alert" · 앞 CircleWarningIcon 16 · 오른쪽 ✕ 16(이름 prop) · 닫을 때까지 머묾.
//   - 마우스가 올라 있거나 초점이 안에 있으면 시간이 멈춘다. 초점은 옮기지 않는다.
//   - 포털은 토스트가 있을 때만 body 끝에 붙인다: Radix 모달이 열 때 다른 body 자식을 aria-hidden 으로 가리므로, 모달 뒤에 붙어야
//     가려지지 않는다(발주서 ★D). 모달은 body 에 pointer-events:none 을 거니 토스트는 pointer-events-auto.
//   - 움직임: toast.css(220ms — 움직임 줄임이면 0). 나갈 때 움직임 뒤 걷고, 움직임 줄임이면 바로 걷는다.
//   - host 가 사라지면 남은 토스트를 걷는다(다른 화면으로 새지 않게). 그래서 host 는 화면의 갈래(읽는 중·판)와 상관없이 늘 붙어 있게
//     둔다 — 토스트를 띄우는 효과보다 뒤(형제 뒤)에 두면 StrictMode 의 두 번 붙이기에도 남는다.
import { useEffect, useRef, useSyncExternalStore } from 'react';

import {
  CircleWarningIcon,
  CloseIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { createPortal } from 'react-dom';

import {
  MAX,
  clearToasts,
  dismissToast,
  removeToast,
  snapshot,
  subscribe,
} from './store.ts';
import type { ToastItem } from './store.ts';
import './toast.css';

/** 성공 톤이 머무는 시간(e6 ⑤ 3초). */
export const TOAST_DURATION_MS = 3000;
/** 한 번에 보이는 수(e6 ⑤). */
export const TOAST_MAX = MAX;
/** 나가는 움직임 길이(toast.css 와 같은 값). */
const LEAVE_MS = 220;

export interface ToasterProps {
  /** 성공 톤이 머무는 시간(ms) — 시험이 바꾼다(발주서 Q15). */
  duration?: number;
}

const reducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function ToastView({ item, duration }: { item: ToastItem; duration: number }) {
  const paused = useRef({ hover: false, focus: false });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const left = useRef(duration);
  const startedAt = useRef(0);

  const stop = () => {
    if (timer.current === null) return;
    clearTimeout(timer.current);
    timer.current = null;
    left.current -= Date.now() - startedAt.current;
  };
  const start = () => {
    if (item.tone !== 'success' || item.leaving || timer.current !== null)
      return;
    if (paused.current.hover || paused.current.focus) return;
    startedAt.current = Date.now();
    timer.current = setTimeout(
      () => {
        timer.current = null;
        dismissToast(item.id);
      },
      Math.max(0, left.current),
    );
  };

  useEffect(() => {
    start();
    return stop;
    // 시간은 처음 한 번 — 멈춤·다시는 손이 정한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!item.leaving) return;
    stop();
    if (reducedMotion()) {
      removeToast(item.id);
      return;
    }
    const out = setTimeout(() => removeToast(item.id), LEAVE_MS);
    return () => clearTimeout(out);
  }, [item.leaving, item.id]);

  const pause = (key: 'hover' | 'focus', on: boolean) => {
    paused.current[key] = on;
    if (on) stop();
    else start();
  };

  const error = item.tone === 'error';
  return (
    <div
      role={error ? 'alert' : 'status'}
      aria-live={error ? 'assertive' : 'polite'}
      aria-atomic="true"
      data-testid="toast"
      data-tone={item.tone}
      className={cn(
        'pointer-events-auto box-border flex max-w-[480px] items-center gap-2 rounded-component px-4 py-3 text-style-pre-body-06 drop-shadow-[0_0_5px_rgba(0,0,0,0.12)]',
        error ?
          'bg-support-error-subtle text-support-error-accent'
        : 'bg-background-primary-inverse text-text-primary-inverse',
        item.leaving ? 'toast-m-out' : 'toast-m-in',
      )}
      onMouseEnter={() => pause('hover', true)}
      onMouseLeave={() => pause('hover', false)}
      onFocus={() => pause('focus', true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          pause('focus', false);
      }}
    >
      {error && <CircleWarningIcon aria-hidden className="size-4 shrink-0" />}
      <span className="line-clamp-2 min-w-0 break-words">{item.message}</span>
      {error && (
        <button
          type="button"
          aria-label={item.closeLabel}
          className="flex size-4 shrink-0 cursor-pointer items-center justify-center border-0 bg-transparent p-0 text-current [&_svg]:size-4"
          // 모달이 열려 있으면 바깥 누름이 모달을 닫는다 — 토스트 누름은 모달까지 올리지 않는다.
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => dismissToast(item.id)}
        >
          <CloseIcon aria-hidden />
        </button>
      )}
    </div>
  );
}

export function Toaster({ duration = TOAST_DURATION_MS }: ToasterProps) {
  const items = useSyncExternalStore(subscribe, snapshot, snapshot);
  useEffect(() => clearToasts, []);
  if (items.length === 0 || typeof document === 'undefined') return null;
  return createPortal(
    <div
      data-testid="toaster"
      className="twp pointer-events-none fixed inset-x-0 top-[88px] z-toast flex flex-col items-center gap-2 px-4"
    >
      {items.map((item) => (
        <ToastView key={item.id} item={item} duration={duration} />
      ))}
    </div>,
    document.body,
  );
}
