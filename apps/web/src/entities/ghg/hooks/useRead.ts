// 온실가스 읽기 훅 넷(밴드 W12-0a ① — 중대성평가 useRuns 꼴). 실어댑터의 읽기를 useLoad 로 — key 가 바뀌면 다시 읽는다.
// 상태: loading → ready(값) | refused(회사 거절 셋) | failed | missing(상세만, 404). 화면은 상태와 retry·reload 만 받는다.
//   retry  = [다시 시도](늘 loading 부터) · reload = 쓰기 뒤 다시 읽기(앞 값을 낸 채).
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import type {
  CompanyRefusal,
  DetailOutcome,
  FacilityCodeAdminPort,
  GhgDashboardPort,
  GhgOrganizationPort,
  ReadOutcome,
} from '../api/index.ts';
import type {
  AdminFacilityCodePage,
  BranchDetail,
  BranchPage,
  Dashboard,
  FacilityCode,
} from '../model/index.ts';

export type ReadState<T> =
  | { state: 'loading' }
  | { state: 'ready'; value: T }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'failed' };

export type DetailState = ReadState<BranchDetail> | { state: 'missing' };

export interface ReadHandle<S> {
  status: S;
  retry(): void;
  reload(): void;
}

function useRead<T>(
  key: readonly unknown[] | null,
  load: () => Promise<ReadOutcome<T> | DetailOutcome>,
): ReadHandle<ReadState<T> | { state: 'missing' }> {
  const { status, retry, reload } = useLoad(key, load);
  const out = useMemo<ReadState<T> | { state: 'missing' }>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') return { state: 'failed' };
    const outcome = status.data;
    switch (outcome.kind) {
      case 'ok':
        return { state: 'ready', value: outcome.value as T };
      case 'refused':
        return { state: 'refused', company: outcome.company };
      case 'missing':
        return { state: 'missing' };
      default:
        return { state: 'failed' };
    }
  }, [status]);
  return { status: out, retry, reload };
}

/** S15 사업장 목록 한 쪽(q·page 가 바뀌면 다시 읽는다). */
export function useBranches(
  port: GhgOrganizationPort,
  q: string,
  page: number,
): ReadHandle<ReadState<BranchPage>> {
  return useRead<BranchPage>([port, q, page], () =>
    port.listBranches({ q, page }),
  ) as ReadHandle<ReadState<BranchPage>>;
}

/** S15 사업장 상세. id 가 null(새 사업장)이면 읽지 않는다(loading 그대로 — 화면이 가른다). */
export function useBranch(
  port: GhgOrganizationPort,
  id: string | null,
): ReadHandle<DetailState> {
  return useRead<BranchDetail>(id === null ? null : [port, id], () =>
    port.getBranch(id!),
  );
}

/** S15 모달 드롭다운의 코드 목록(공통 하나 — 서버 차례). */
export function useFacilityCodes(
  port: GhgOrganizationPort,
): ReadHandle<ReadState<FacilityCode[]>> {
  return useRead<FacilityCode[]>([port], () =>
    port.listFacilityCodes(),
  ) as ReadHandle<ReadState<FacilityCode[]>>;
}

/** S18 코드 목록 한 쪽(운영 관리자). */
export function useAdminFacilityCodes(
  port: FacilityCodeAdminPort,
  page: number,
): ReadHandle<ReadState<AdminFacilityCodePage>> {
  return useRead<AdminFacilityCodePage>([port, page], () =>
    port.list(page),
  ) as ReadHandle<ReadState<AdminFacilityCodePage>>;
}

/** S1 대시보드 한 판(밴드 DB1 ② — 해가 바뀌면 다시 읽는다). */
export function useDashboard(
  port: GhgDashboardPort,
  year: number,
): ReadHandle<ReadState<Dashboard>> {
  return useRead<Dashboard>([port, year], () => port.board(year)) as ReadHandle<
    ReadState<Dashboard>
  >;
}
