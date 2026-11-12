// 검토 표를 띄워 보는 화면. 부품이 아니라 「부품을 쓰는 쪽」의 예다.
//   1) 자료를 가져온다        → 정적 JSON 또는 코드로 만든 가짜 행. 서버가 생기면 이 자리가 API 호출이 된다
//   2) parseTableInput 으로 검증한다
//   3) 열 구성과 계산 함수를 정해 ReviewTable 에 넘긴다
// 주소는 /dev/table(DEV·VITE_DEMOS 빌드에만 — src/app/router.tsx). 쿼리로 고른다:
//   ?data=sample | fake | local     자료(기본 sample). fake 는 &rows=5000 으로 행 수를 정한다
//   &screen=cards                              둘째 화면(카드)으로 본다
//   &calcDelay=800                             계산 대역이 답을 늦게 준다(재계산 대기를 보려고)
//   &calcFail=1                                계산 대역이 행마다 처음 1번을 실패한다(계산 실패와 「다시 계산」을 보려고)
//   &probe=1                                   행이 다시 그려진 횟수를 window.__rowRenders 에 센다(재는 데만 쓴다)
import { useEffect, useMemo, useState } from 'react';

import { appPath, withParams } from '../../shared/lib/address.ts';
import {
  ReviewTable,
  parseTableInput,
} from '../../widgets/review-table/index.ts';
import type { TableInput } from '../../widgets/review-table/index.ts';
import { ReviewCards } from './ReviewCards.tsx';
import { DEMO_COLUMNS } from './columns.tsx';
import { makeFakeInput } from './fakeRows.ts';
import {
  delayedStandIn,
  failingStandIn,
  standInCalculate,
} from './standInCalc.ts';

const FILES: Record<string, string> = {
  sample: 'sample/review-table.json',
  local: 'local/review-table.json',
};

type Loaded =
  | { state: 'loading' }
  | { state: 'ready'; input: TableInput }
  | { state: 'error'; errors: string[] };

declare global {
  interface Window {
    __rowRenders?: number;
  }
}

export function TablePage() {
  const params = useMemo(() => new URLSearchParams(location.search), []);
  const data = params.get('data') ?? 'sample';
  const rowCount = Math.max(
    1,
    Math.min(100000, Number(params.get('rows')) || 5000),
  );
  const delay = Number(params.get('calcDelay')) || 0;
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  useEffect(() => {
    let alive = true;
    const settle = (raw: unknown) => {
      if (!alive) return;
      const parsed = parseTableInput(raw);
      setLoaded(
        parsed.ok ?
          { state: 'ready', input: parsed.input }
        : { state: 'error', errors: parsed.errors },
      );
    };
    if (data === 'fake') {
      settle(makeFakeInput(rowCount));
    } else {
      const file = FILES[data] ?? FILES.sample!;
      fetch(appPath(file))
        .then((response) => {
          if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
          return response.json() as Promise<unknown>;
        })
        .then(settle)
        .catch(
          (error: unknown) =>
            alive && setLoaded({ state: 'error', errors: [String(error)] }),
        );
    }
    return () => {
      alive = false;
    };
  }, [data, rowCount]);

  const failTimes = Math.max(0, Number(params.get('calcFail')) || 0);
  const calculate = useMemo(() => {
    const base = delay > 0 ? delayedStandIn(delay) : standInCalculate;
    return failTimes > 0 ? failingStandIn(failTimes, base, delay) : base;
  }, [delay, failTimes]);
  const onRenderRow = useMemo(
    () =>
      params.get('probe') ?
        () => void (window.__rowRenders = (window.__rowRenders ?? 0) + 1)
      : undefined,
    [params],
  );
  // 띠의 링크: 바꾸려는 인자만 바꾸고 주소의 나머지(&screen=cards, &calcFail=1 …)는 그대로 둔다. null 은 그 인자를 뺀다.
  const link = (patch: Record<string, string | null>) =>
    withParams(location.search, { view: 'table', ...patch });
  const Screen = params.get('screen') === 'cards' ? ReviewCards : ReviewTable;

  return (
    <div className="app">
      <header className="app-bar">
        <a href={appPath('dev/viewer')}>문서 뷰어</a>
        <span>
          {/* rows 는 가짜 자료의 행 수다. 다른 자료로 갈 때는 뺀다. */}
          자료: <a href={link({ data: 'sample', rows: null })}>예시</a> ·{' '}
          <a href={link({ data: 'fake', rows: '5000' })}>가짜 5,000행</a> ·{' '}
          <a href={link({ data: 'local', rows: null })}>실제 자료(붙였으면)</a>
        </span>
        <span>
          화면: <a href={link({ screen: null })}>표</a> ·{' '}
          <a href={link({ screen: 'cards' })}>카드(둘째 화면)</a>
        </span>
        <span>검토 상태는 이 화면 안에만 있다. 배출량 재계산은 대역이다.</span>
      </header>
      <main className="app-main" data-table-state={loaded.state}>
        {loaded.state === 'loading' && <p className="app-message">읽는 중…</p>}
        {loaded.state === 'error' && (
          <p className="app-message" role="alert">
            자료를 쓸 수 없다.{'\n'}
            {loaded.errors.slice(0, 20).join('\n')}
          </p>
        )}
        {loaded.state === 'ready' && (
          <>
            {loaded.input.notice && (
              <p className="app-notice">{loaded.input.notice}</p>
            )}
            <div className="app-fill">
              <Screen
                rows={loaded.input.rows}
                categories={loaded.input.categories}
                columns={DEMO_COLUMNS}
                calculate={calculate}
                onRenderRow={onRenderRow}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
