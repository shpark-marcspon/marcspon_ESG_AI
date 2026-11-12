// 온실가스 Scope 3 경로 컴포넌트(밴드 S3W1 ③ — 발주서 §2-3). app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다. 틀은 GhgLayout 그대로
//   (/ghg 의 자식 경로 — 새 router context 칸은 없다, 실어댑터는 root context 의 session.api 로 짓는다).
// /ghg/scope3?year= = S3-01 Scope 3 첫 화면. 연도는 search(router.tsx 가 네 자리 정수로 거름 — validateGhgYearSearch 를 같이 쓴다:
//   거름은 범위·기본값을 보지 않는다) — 없거나 고를 수 있는 해(model yearsOf — 전년도부터 다섯) 밖이면 전년도로 replace. 연도 바꿈은 replace.
//   제목 아래 Scope 탭 줄은 GhgRoutes 의 ScopeTabs(S2 자리와 같은 것)를 화면 prop tabs 로 넘긴다.
// 운영 관리자도 같은 화면·같은 흐름(작업 회사 — sid:MARC-ENT-374). useOperator 는 GhgRoutes 것을 쓴다.
// sendUpload 는 app/translation/TranslationRoutes.tsx 를 옮겨 적었다(가져오지 않는다 — 남의 모듈 땅). fetch 는 이 파일의 이 한 자리뿐이다.
import { useEffect, useMemo } from 'react';

import { getRouteApi, useNavigate } from '@tanstack/react-router';

import { createScope3Port } from '../../entities/ghg-scope3/api/index.ts';
import type { Scope3Port } from '../../entities/ghg-scope3/api/index.ts';
import { yearIn, yearsOf } from '../../entities/ghg-scope3/model/index.ts';
import { Scope3Screen } from '../../pages/ghg-scope3/index.ts';
import { ScopeTabs, useOperator } from './GhgRoutes.tsx';

const layoutApi = getRouteApi('/ghg');
const scope3Api = getRouteApi('/ghg/scope3');

/** 서명 주소로 파일 본문을 올린다(TranslationRoutes.tsx 를 옮겨 적음). Authorization 을 싣지 않는다(서명이 권한이다). */
export async function sendUpload(
  url: string,
  method: string,
  file: File,
): Promise<void> {
  // 쿠키·리퍼러·캐시를 싣지 않는다(서명 주소는 저장소 출처).
  const response = await globalThis.fetch(url, {
    method,
    body: file,
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`upload failed ${response.status}`);
}

/** Scope 3 실어댑터(세션 api 하나에 하나). */
function useScope3Port(): Scope3Port {
  const api = layoutApi.useRouteContext().session.api;
  return useMemo(() => createScope3Port({ api, sendUpload }), [api]);
}

/** /ghg/scope3?year= — S3-01 Scope 3 첫 화면. */
export function Scope3Route() {
  const port = useScope3Port();
  const operator = useOperator();
  const navigate = useNavigate();
  const search = scope3Api.useSearch();
  const years = useMemo(() => yearsOf(new Date()), []);
  const year = yearIn(search.year, years);
  useEffect(() => {
    if (year === null)
      void navigate({
        to: '/ghg/scope3',
        search: { year: years[0] },
        replace: true,
      });
  }, [year, navigate, years]);
  if (year === null) return null;
  return (
    <Scope3Screen
      port={port}
      year={year}
      years={years}
      operator={operator}
      tabs={<ScopeTabs year={year} />}
      onYear={(next) =>
        void navigate({
          to: '/ghg/scope3',
          search: { year: next },
          replace: true,
        })
      }
    />
  );
}
