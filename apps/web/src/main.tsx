// sort-imports-ignore — CSS import 순서는 캐스케이드다(app.css 가 맨 끝에서 이긴다). 정렬 플러그인이 옮기지 못하게 이 파일만 끈다.
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createBrowserHistory } from '@tanstack/react-router';
import { createAppRouter } from './app/router.tsx';
import './app/styles/fonts.css';
import './app/styles/tailwind.css';
import './app/styles/app.css';

// 진입. 경로 표는 app/router.tsx 한 곳이다(밴드 RT1 — TanStack Router, 코드로 적는 경로).
// 이 파일과 router.tsx 는 그린워싱 화면·pdfjs.ts·목 저장소를 정적으로 가져오지 않는다(화면은 모두 게으르게 부른다 — router.tsx 머리말).
const router = createAppRouter({ history: createBrowserHistory() });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
