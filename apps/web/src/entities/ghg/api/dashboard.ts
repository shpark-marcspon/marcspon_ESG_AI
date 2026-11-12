// 대시보드(S1) 실어댑터(밴드 DB1 ② — 서버 S12a-3 ②·S3K2a ②·DB1 ①). entries.ts 꼴, 읽기 하나:
//     board   GET   /inventory/scope12/dashboard?year=   → Scope12DashboardOut(설정 안 된 해 = configured 거짓 · 200)
// 갈래: ok | refused(회사 거절 셋 — companyRefusalOf) | failed(끊김·꼴 틀림·그 밖 거절). 서버 message 는 싣지 않는다.
import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import type { Api, CompanyRefusal } from '../../../shared/api/index.ts';
import type { Dashboard } from '../model/index.ts';
import { parseDashboard } from './contract/index.ts';

export type DashboardRead =
  | { kind: 'ok'; value: Dashboard }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export interface GhgDashboardPort {
  board(year: number): Promise<DashboardRead>;
}

export interface CreateGhgDashboardPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

export function createGhgDashboardPort({
  api,
}: CreateGhgDashboardPortOptions): GhgDashboardPort {
  const { client } = api;
  return {
    async board(year) {
      if (!Number.isInteger(year)) return { kind: 'failed' };
      try {
        const { data } = await client.GET('/inventory/scope12/dashboard', {
          params: { query: { year } },
        });
        const value = parseDashboard(data);
        return value === null ? { kind: 'failed' } : { kind: 'ok', value };
      } catch (error) {
        const company = companyRefusalOf(asFailure(error));
        return company ? { kind: 'refused', company } : { kind: 'failed' };
      }
    },
  };
}
